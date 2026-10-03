import re
import math
import time
from typing import Optional, List, Dict


class LLMClient:
    def __init__(self, model_name: str, api_key: Optional[str] = None,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 request_timeout: float = 60.0):
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
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.request_timeout = request_timeout
        self.last_generation = None

    def build_prompt(self, task_prompt: str, header_code: str, starter_code: str,
                     target_standard: str = "c99") -> List[Dict[str, str]]:
        if target_standard not in ("c99", "c11", "c17"):
            raise ValueError("target_standard must be c99, c11, or c17")
        system_instruction = (
            "You are an expert embedded software engineer specializing in safety-critical firmware.\n"
            "Rules:\n"
            f"1. Write clean, portable {target_standard.upper()} code.\n"
            "2. Do NOT use dynamic memory allocation (no malloc/calloc/free).\n"
            "3. Always check pointers for NULL.\n"
            "4. Follow MISRA-C principles: use fixed-width integers (<stdint.h>).\n"
            "5. Return ONLY the complete implementation code for the requested C file inside a ```c ... ``` code block."
        )

        user_content = (
            f"# Embedded Coding Task\n\n"
            f"{task_prompt}\n\n"
            f"## API Header Specification:\n"
            f"```c\n{header_code}\n```\n\n"
            f"## Starter Code / File Template:\n"
            f"```c\n{starter_code}\n```\n\n"
            f"Provide the complete implementation for the source file."
        )

        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ]

    def generate_solution(self, messages: List[Dict[str, str]]) -> str:
        try:
            import litellm
        except ImportError:
            raise ImportError(
                "litellm is required for live LLM API evaluation. "
                "Install it using: pip install litellm"
            )

        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "timeout": self.request_timeout,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.api_key:
            kwargs["api_key"] = self.api_key

        self.last_generation = {
            "requested_model": self.model_name, "resolved_model": None,
            "temperature": self.temperature, "max_tokens": self.max_tokens,
            "request_timeout_seconds": self.request_timeout,
            "latency_seconds": None, "finish_reason": None, "usage": None,
        }
        start = time.perf_counter()
        try:
            response = litellm.completion(**kwargs)
        finally:
            self.last_generation["latency_seconds"] = round(time.perf_counter() - start, 6)
        if not response.choices:
            raise ValueError("Model returned no completion choices")
        choice = response.choices[0]
        self.last_generation["resolved_model"] = getattr(response, "model", None)
        self.last_generation["finish_reason"] = getattr(choice, "finish_reason", None)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.last_generation["usage"] = {
                name: getattr(usage, name, None)
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
        if self.last_generation["finish_reason"] == "length":
            raise ValueError("Model output was truncated at the token limit; increase --max-tokens")
        raw_text = choice.message.content
        return self.extract_c_code(raw_text)

    @staticmethod
    def extract_c_code(response_text: Optional[str]) -> str:
        """Prefer the largest C/C++ fence, then a generic fence or raw source."""
        if not response_text:
            return ""

        # Parse all fences together so a generic block's closing delimiter
        # cannot be mistaken for a C block's opening delimiter.
        blocks = re.findall(r"```([^\r\n`]*)\r?\n(.*?)```", response_text, flags=re.DOTALL)
        c_blocks = [code.strip() for language, code in blocks
                    if language.strip().split() and language.strip().split()[0].lower() in {"c", "cpp", "c++"}]
        candidates = c_blocks or [code.strip() for _, code in blocks]
        if not candidates:
            candidates = [code.strip() for code in re.findall(r"```(.*?)```", response_text, flags=re.DOTALL)]
        if candidates:
            # Later blocks win ties, favoring a final revised implementation.
            return max(reversed(candidates), key=len)
        return response_text.strip()
