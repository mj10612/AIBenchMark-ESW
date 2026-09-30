import re
from typing import Optional, List, Dict


class LLMClient:
    def __init__(self, model_name: str, api_key: Optional[str] = None, temperature: float = 0.0):
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature

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
            "temperature": self.temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key

        response = litellm.completion(**kwargs)
        raw_text = response.choices[0].message.content
        return self.extract_c_code(raw_text)

    @staticmethod
    def extract_c_code(response_text: str) -> str:
        """
        Extracts code from ```c ... ``` or ``` ... ``` blocks.
        If no markdown blocks found, returns the stripped text.
        """
        code_match = re.search(r"```(?:c|C)?\s*\n(.*?)\n```", response_text, flags=re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Fallback: check any backtick block
        block_match = re.search(r"```(.*?)```", response_text, flags=re.DOTALL)
        if block_match:
            return block_match.group(1).strip()

        return response_text.strip()
