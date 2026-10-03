import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from aibenchmark_esw.llm.client import LLMClient


class TestLLMClient(unittest.TestCase):
    def response(self, finish_reason="stop"):
        return Namespace(model="resolved-model-snapshot", usage=Namespace(
            prompt_tokens=12, completion_tokens=8, total_tokens=20), choices=[Namespace(
                finish_reason=finish_reason, message=Namespace(content="```c\nint x;\n```"))])

    def test_default_generation_omits_temperature_and_records_usage(self):
        provider = MagicMock()
        provider.completion.return_value = self.response()
        client = LLMClient("openai/test-model", api_key="private-key")
        with patch.dict("sys.modules", {"litellm": provider}):
            self.assertEqual(client.generate_solution([]), "int x;")
        kwargs = provider.completion.call_args.kwargs
        self.assertNotIn("temperature", kwargs)
        self.assertNotIn("max_tokens", kwargs)
        self.assertEqual(kwargs["timeout"], 60)
        self.assertEqual(client.last_generation["usage"]["total_tokens"], 20)
        self.assertEqual(client.last_generation["resolved_model"], "resolved-model-snapshot")
        self.assertNotIn("private-key", str(client.last_generation))
        self.assertGreaterEqual(client.last_generation["latency_seconds"], 0)

    def test_explicit_generation_controls_are_forwarded(self):
        provider = MagicMock()
        provider.completion.return_value = self.response()
        client = LLMClient("anthropic/test-model", temperature=0, max_tokens=1024, request_timeout=5)
        with patch.dict("sys.modules", {"litellm": provider}):
            client.generate_solution([])
        kwargs = provider.completion.call_args.kwargs
        self.assertEqual((kwargs["temperature"], kwargs["max_tokens"], kwargs["timeout"]), (0, 1024, 5))

    def test_truncation_keeps_usage_but_is_reported_as_generation_failure(self):
        provider = MagicMock()
        provider.completion.return_value = self.response("length")
        client = LLMClient("test-model")
        with patch.dict("sys.modules", {"litellm": provider}), self.assertRaisesRegex(ValueError, "truncated"):
            client.generate_solution([])
        self.assertEqual(client.last_generation["finish_reason"], "length")
        self.assertEqual(client.last_generation["usage"]["total_tokens"], 20)

    def test_api_failure_retains_duration_without_inventing_usage(self):
        provider = MagicMock()
        provider.completion.side_effect = RuntimeError("provider timeout")
        client = LLMClient("test-model")
        with patch.dict("sys.modules", {"litellm": provider}), self.assertRaises(RuntimeError):
            client.generate_solution([])
        self.assertGreaterEqual(client.last_generation["latency_seconds"], 0)
        self.assertIsNone(client.last_generation["usage"])

    def test_invalid_generation_controls_are_rejected(self):
        for settings in ({"temperature": float("nan")}, {"temperature": -1}, {"temperature": True},
                         {"max_tokens": 0}, {"max_tokens": 1.5}, {"max_tokens": True},
                         {"request_timeout": 0}, {"request_timeout": float("inf")}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                LLMClient("test-model", **settings)

    def test_c_block_takes_precedence_over_introductory_blocks(self):
        code = "#include <stdint.h>"
        for tag in ("", "text", "markdown", "python"):
            with self.subTest(tag=tag):
                response = f"Notes:\n```{tag}\nA long implementation plan, not C source.\n```\n```c\n{code}\n```"
                self.assertEqual(LLMClient.extract_c_code(response), code)

    def test_complete_implementation_takes_precedence_over_helper_snippet(self):
        full = "#include <stdint.h>\nvoid fn(void) {}"
        snippet = "#define FOO 1"
        for blocks in ((snippet, full), (full, snippet)):
            with self.subTest(blocks=blocks):
                response = "\n".join(f"```c\n{code}\n```" for code in blocks)
                self.assertEqual(LLMClient.extract_c_code(response), full)

    def test_language_identifiers_are_removed(self):
        code = "#include <stdint.h>"
        for tag in ("c", "C", "cpp", "CPP", "c++", "C++", "c filename=solution.c"):
            with self.subTest(tag=tag):
                self.assertEqual(LLMClient.extract_c_code(f"```{tag}\n{code}\n```"), code)

    def test_generic_fences_do_not_leak_language_identifiers(self):
        for tag in ("", "text", "unknown"):
            with self.subTest(tag=tag):
                self.assertEqual(LLMClient.extract_c_code(f"```{tag}\nint answer = 42;\n```"), "int answer = 42;")

    def test_later_block_wins_when_sizes_are_equal(self):
        self.assertEqual(LLMClient.extract_c_code("```c\nint x;\n```\n```c\nint y;\n```"), "int y;")

    def test_windows_newlines(self):
        self.assertEqual(LLMClient.extract_c_code("```C++\r\nint x;\r\n```"), "int x;")

    def test_raw_code_and_inline_fences(self):
        for text in ("  int x;\n", "```int x;```"):
            with self.subTest(text=text):
                self.assertEqual(LLMClient.extract_c_code(text), "int x;")

    def test_null_and_empty_responses(self):
        for text in (None, "", " \r\n\t", "```c\n\n```"):
            with self.subTest(text=text):
                self.assertEqual(LLMClient.extract_c_code(text), "")


if __name__ == "__main__":
    unittest.main()
