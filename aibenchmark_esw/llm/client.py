"""Provider generation with explicit attempts and replayable public messages."""
import copy
import math
import re
import time
from typing import Optional, List, Dict, Any, Set
from aibenchmark_esw.sandbox.c_source import mask_noncode


def is_fatal_provider_error(error):
    status = getattr(error, "status_code", None)
    return (isinstance(error, ImportError)
            or type(error).__name__ in {"AuthenticationError", "PermissionDeniedError",
                                       "NotFoundError", "UnsupportedParamsError", "BadRequestError"}
            or (isinstance(status, int) and status in (400, 401, 403, 404, 422)))


def _transient(error):
    status = getattr(error, "status_code", None)
    return (isinstance(error, (TimeoutError, ConnectionError))
            or type(error).__name__ in {"Timeout", "APITimeoutError", "RateLimitError",
                                       "APIConnectionError", "ServiceUnavailableError"}
            or (isinstance(status, int) and (status in (408, 409, 429) or 500 <= status < 600)))


class LLMClient:
    def __init__(self, model_name: str, api_key: Optional[str] = None,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 request_timeout: float = 60.0, max_retries: int = 0,
                 retry_backoff_seconds: float = 1.0, prompt_strategy: str = "single",
                 review_turn: bool = False):
        if temperature is not None and (isinstance(temperature, bool)
                or not isinstance(temperature, (int, float))
                or not math.isfinite(temperature) or not 0 <= temperature <= 2):
            raise ValueError("temperature must be a finite number between 0 and 2")
        if max_tokens is not None and (isinstance(max_tokens, bool)
                or not isinstance(max_tokens, int) or max_tokens < 1):
            raise ValueError("max_tokens must be a positive integer")
        if (isinstance(request_timeout, bool) or not isinstance(request_timeout, (int, float))
                or not math.isfinite(request_timeout) or request_timeout <= 0):
            raise ValueError("request_timeout must be a finite positive number")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or not 0 <= max_retries <= 10:
            raise ValueError("max_retries must be an integer between 0 and 10")
        if (isinstance(retry_backoff_seconds, bool)
                or not isinstance(retry_backoff_seconds, (int, float))
                or not math.isfinite(retry_backoff_seconds) or not 0 <= retry_backoff_seconds <= 60):
            raise ValueError("retry_backoff_seconds must be between 0 and 60")
        if prompt_strategy not in ("single", "plan"):
            raise ValueError("prompt_strategy must be single or plan")
        if not isinstance(review_turn, bool):
            raise ValueError("review_turn must be a boolean")
        self.model_name, self.api_key = model_name, api_key
        self.temperature, self.max_tokens = temperature, max_tokens
        self.request_timeout = request_timeout
        self.max_retries, self.retry_backoff_seconds = max_retries, retry_backoff_seconds
        self.prompt_strategy, self.review_turn = prompt_strategy, review_turn
        self.last_generation: Any = None
        self.expected_functions: Set[str] = set()
        self.cancel_event = None

    def settings(self):
        return {"temperature": self.temperature, "max_tokens": self.max_tokens,
                "request_timeout_seconds": self.request_timeout,
                "max_retries": self.max_retries, "retry_backoff_seconds": self.retry_backoff_seconds,
                "prompt_strategy": self.prompt_strategy, "review_turn": self.review_turn}

    def build_prompt(self, task_prompt: str, header_code: str, starter_code: str,
                     target_standard: str = "c99", prompt_overrides=None,
                     system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        if target_standard not in ("c99", "c11", "c17"):
            raise ValueError("target_standard must be c99, c11, or c17")
        overrides = prompt_overrides or {}
        if not isinstance(overrides, dict) or set(overrides) - {"allow_dynamic_memory", "extra_rules"}:
            raise ValueError("Unknown prompt override")
        if not isinstance(overrides.get("allow_dynamic_memory", False), bool):
            raise ValueError("allow_dynamic_memory must be a boolean")
        extra = overrides.get("extra_rules", [])
        if not isinstance(extra, list) or any(not isinstance(rule, str) or not rule.strip() for rule in extra):
            raise ValueError("extra_rules must be a list of nonempty strings")
        rules = [f"Write clean, portable {target_standard.upper()} code."]
        if not overrides.get("allow_dynamic_memory", False):
            rules.append("Do NOT use dynamic memory allocation (no malloc/calloc/realloc/free).")
        rules += ["Always check pointers for NULL.",
                  "Follow MISRA-C principles: use fixed-width integers (<stdint.h>).",
                  "Return ONLY the complete implementation code for the requested C file inside a ```c ... ``` code block."]
        rules.extend(extra)
        instruction = ("You are an expert embedded software engineer specializing in safety-critical firmware.\nRules:\n"
                       + "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, 1)))
        if system_prompt is not None:
            if not isinstance(system_prompt, str) or not system_prompt.strip():
                raise ValueError("System prompt override must be nonempty text")
            instruction = system_prompt
        self.expected_functions = set(re.findall(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*;", mask_noncode(header_code)))
        user = (f"# Embedded Coding Task\n\n{task_prompt}\n\n## API Header Specification:\n"
                f"```c\n{header_code}\n```\n\n## Starter Code / File Template:\n"
                f"```c\n{starter_code}\n```\n\nProvide the complete implementation for the source file.")
        return [{"role": "system", "content": instruction}, {"role": "user", "content": user}]

    def _check_cancelled(self):
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise InterruptedError("Generation cancelled")

    def _complete(self, provider, messages):
        kwargs = {"model": self.model_name, "messages": copy.deepcopy(messages), "timeout": self.request_timeout}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.api_key:
            kwargs["api_key"] = self.api_key
        self.last_generation["request_messages"].append(copy.deepcopy(messages))
        for attempt in range(self.max_retries + 1):
            self._check_cancelled()
            record: Dict[str, Any] = {"turn": len(self.last_generation["request_messages"]),
                      "attempt": attempt + 1, "latency_seconds": None, "error": None}
            self.last_generation["attempts"].append(record)
            start = time.perf_counter()
            try:
                response = provider.completion(**kwargs)
                break
            except Exception as error:
                record["error"] = type(error).__name__
                if not _transient(error) or is_fatal_provider_error(error) or attempt >= self.max_retries:
                    raise
                delay = min(60.0, self.retry_backoff_seconds * 2 ** attempt)
                record["retry_delay_seconds"] = delay
                if self.cancel_event is None:
                    time.sleep(delay)
                elif self.cancel_event.wait(delay):
                    raise InterruptedError("Generation cancelled")
            finally:
                record["latency_seconds"] = round(time.perf_counter() - start, 6)
        if not response.choices:
            raise ValueError("Model returned no completion choices")
        choice = response.choices[0]
        raw_text = choice.message.content or ""
        if not isinstance(raw_text, str):
            raise ValueError("Model completion content must be text")
        usage = getattr(response, "usage", None)
        tokens = {name: getattr(usage, name, None) for name in
                  ("prompt_tokens", "completion_tokens", "total_tokens")} if usage is not None else None
        turn = {"resolved_model": getattr(response, "model", None),
                "finish_reason": getattr(choice, "finish_reason", None),
                "usage": tokens, "response_text": raw_text}
        self.last_generation["turns"].append(turn)
        self.last_generation.update(resolved_model=turn["resolved_model"], finish_reason=turn["finish_reason"])
        known = [item["usage"] for item in self.last_generation["turns"] if item["usage"] is not None]
        self.last_generation["usage"] = ({name: sum(item[name] for item in known)
            if all(isinstance(item.get(name), int) and not isinstance(item[name], bool) for item in known)
            else None for name in ("prompt_tokens", "completion_tokens", "total_tokens")} if known else None)
        self.last_generation["usage_complete"] = (len(known) == len(self.last_generation["turns"])
                                                     and all(item["error"] is None for item in self.last_generation["attempts"]))
        messages.append({"role": "assistant", "content": raw_text})
        self.last_generation["messages"] = copy.deepcopy(messages)
        if turn["finish_reason"] == "length":
            self.last_generation["partial_response"] = raw_text
            raise ValueError("Model output was truncated at the token limit; increase --max-tokens")
        return raw_text

    def generate_solution(self, messages: List[Dict[str, str]]) -> str:
        self.last_generation = {"requested_model": self.model_name, "resolved_model": None,
                                **self.settings(), "latency_seconds": None, "finish_reason": None,
                                "usage": None, "attempts": [], "turns": [],
                                "messages": copy.deepcopy(messages), "request_messages": []}
        start = time.perf_counter()
        try:
            try:
                import litellm
            except ImportError as error:
                raise ImportError("litellm is required for live LLM API evaluation. Install it using: pip install litellm") from error
            conversation = copy.deepcopy(messages)
            if self.prompt_strategy == "plan":
                conversation.append({"role": "user", "content":
                    "Provide a short implementation plan listing the public API, edge cases, and validation checks. Do not produce code yet."})
                self._complete(litellm, conversation)
                conversation.append({"role": "user", "content":
                    "Now provide only the complete C implementation that meets the task contract, inside a c code block."})
            raw_text = self._complete(litellm, conversation)
            if self.review_turn:
                conversation.append({"role": "user", "content":
                    "Review the implementation against the API and boundary cases. Return only the corrected complete C implementation in a c code block."})
                raw_text = self._complete(litellm, conversation)
            return self.extract_c_code(raw_text, self.expected_functions)
        finally:
            self.last_generation["latency_seconds"] = round(time.perf_counter() - start, 6)

    @staticmethod
    def extract_c_code(response_text: Optional[str], expected_functions=None) -> str:
        """Prefer implementations of the API over declarations and usage examples."""
        if not response_text:
            return ""
        blocks = re.findall(r"```([^\r\n`]*)\r?\n(.*?)```", response_text, flags=re.DOTALL)
        c_blocks = [code.strip() for language, code in blocks
                    if language.strip().split() and language.strip().split()[0].lower() in {"c", "cpp", "c++"}]
        candidates = c_blocks or [code.strip() for _, code in blocks]
        if not candidates:
            candidates = [code.strip() for code in re.findall(r"```(.*?)```", response_text, flags=re.DOTALL)]
        expected = set(expected_functions or ())
        def rank(code):
            definitions = set(re.findall(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{", mask_noncode(code)))
            definitions -= {"if", "for", "while", "switch"}
            implementation = definitions - {"main", "setUp", "tearDown"}
            return (len(expected & definitions), bool(implementation), "main" not in definitions,
                    len(implementation), len(code))
        return max(reversed(candidates), key=rank) if candidates else response_text.strip()
