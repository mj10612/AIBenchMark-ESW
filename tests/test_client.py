import unittest

from aibenchmark_esw.llm.client import LLMClient


class TestLLMClient(unittest.TestCase):
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
