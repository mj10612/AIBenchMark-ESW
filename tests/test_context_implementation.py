import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from aibenchmark_esw.llm.client import ContextWindowError, LLMClient

PROMPT = [{'role': 'system', 'content': 'C only'}, {'role': 'user', 'content': 'Implement probe'}]
PLAN = 'Check the probe API and boundaries.'
CODES = ('int probe(void){return 101;}', 'int probe(void){return 202;}', 'int probe(void){return 303;}')


class ContextWindowExceededError(Exception):
    pass


def response(code):
    return SimpleNamespace(model='fixture', usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
                           choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=code))])


def provider_with_limit(message_limit):
    provider = Mock(model_cost={'mock': {'max_input_tokens': 20}})
    provider.token_counter.side_effect = lambda **kw: 40 if len(kw['messages']) > message_limit else 10
    return provider


class TestContextImplementation(unittest.TestCase):
    def assert_required_tail(self, messages, code, instruction, prompt=PROMPT):
        self.assertEqual(messages[:-2], prompt)
        self.assertEqual(messages[-2], {'role': 'assistant', 'content': code})
        self.assertEqual(messages[-1]['role'], 'user')
        self.assertIn(instruction, messages[-1]['content'])

    def test_required_review_or_repair_context_cannot_fit(self):
        for strategy in ('single', 'plan'):
            for turn in ('review', 'repair'):
                with self.subTest(strategy=strategy, turn=turn):
                    provider = provider_with_limit(3)
                    replies = ([response(PLAN)] if strategy == 'plan' else []) + [response(code) for code in CODES]
                    provider.completion.side_effect = replies
                    client = LLMClient('mock', prompt_strategy=strategy, review_turn=turn == 'review')
                    with patch.dict(sys.modules, {'litellm': provider}), self.assertRaisesRegex(ContextWindowError, 'context allows'):
                        client.generate_solution(PROMPT)
                        if turn == 'repair':
                            client.repair_solution('probe.c: compiler error')
                    expected_calls = 2 if strategy == 'plan' else 1
                    self.assertEqual(provider.completion.call_count, expected_calls)
                    self.assertEqual(len(client.last_generation['attempts']), expected_calls)
                    self.assertEqual(client.last_generation['messages'][-1]['content'], CODES[0])

    def test_plan_review_preserves_initial_prompt_and_implementation(self):
        for prompt in (PROMPT[1:], PROMPT, [PROMPT[0], {'role': 'system', 'content': 'No allocation'}, PROMPT[1]]):
            with self.subTest(initial_messages=len(prompt)):
                provider = provider_with_limit(len(prompt) + 2)
                provider.completion.side_effect = [response(PLAN), response(CODES[0]), response(CODES[1])]
                client = LLMClient('mock', prompt_strategy='plan', review_turn=True)
                with patch.dict(sys.modules, {'litellm': provider}):
                    self.assertEqual(client.generate_solution(prompt), CODES[1])
                messages = provider.completion.call_args.kwargs['messages']
                self.assert_required_tail(messages, CODES[0], 'Review the implementation', prompt)
                self.assertTrue(client.last_generation['context_trimmed'])
                self.assertEqual(len(client.last_generation['turns']), 3)
                self.assertEqual(client.last_generation['usage']['total_tokens'], 15)

    def test_repeated_repairs_keep_latest_code_and_current_diagnostics(self):
        provider = provider_with_limit(4)
        provider.completion.side_effect = [response(code) for code in CODES]
        client = LLMClient('mock', repair_turns=2)
        with patch.dict(sys.modules, {'litellm': provider}):
            client.generate_solution(PROMPT)
            self.assertEqual(client.repair_solution('first diagnostic'), CODES[1])
            self.assertEqual(client.repair_solution('second diagnostic'), CODES[2])
        self.assert_required_tail(provider.completion.call_args.kwargs['messages'], CODES[1], 'second diagnostic')
        self.assertEqual(client.last_generation['request_messages'][1][-2]['content'], CODES[0])
        self.assertEqual([turn['_turn_kind'] for turn in client.last_generation['turns']], ['implement', 'repair', 'repair'])
        self.assertEqual(client.last_generation['usage']['total_tokens'], 15)

    def test_provider_context_retry_keeps_review_or_repair_dependency(self):
        for turn in ('review', 'repair'):
            with self.subTest(turn=turn):
                provider = Mock(model_cost={}, token_counter=None)
                provider.completion.side_effect = [response(PLAN), response(CODES[0]),
                    ContextWindowExceededError('too large'), response(CODES[1])]
                client = LLMClient('mock', prompt_strategy='plan', review_turn=turn == 'review')
                with patch.dict(sys.modules, {'litellm': provider}):
                    code = client.generate_solution(PROMPT)
                    if turn == 'repair':
                        code = client.repair_solution('current compiler diagnostic')
                self.assertEqual(code, CODES[1])
                instruction = 'Review the implementation' if turn == 'review' else 'current compiler diagnostic'
                self.assert_required_tail(provider.completion.call_args.kwargs['messages'], CODES[0], instruction)
                self.assertEqual(provider.completion.call_count, 4)
                self.assertTrue(client.last_generation['attempts'][2]['context_retry'])
                self.assertEqual(len(client.last_generation['turns']), 3)

    def test_provider_cannot_retry_by_dropping_required_implementation(self):
        for turn in ('review', 'repair'):
            with self.subTest(turn=turn):
                provider = Mock(model_cost={}, token_counter=None)
                provider.completion.side_effect = [response(CODES[0]), ContextWindowExceededError('too large'), response(CODES[1])]
                client = LLMClient('mock', review_turn=turn == 'review')
                with patch.dict(sys.modules, {'litellm': provider}), self.assertRaises(ContextWindowExceededError):
                    client.generate_solution(PROMPT)
                    if turn == 'repair':
                        client.repair_solution('current compiler diagnostic')
                self.assertEqual(provider.completion.call_count, 2)
                self.assertEqual(provider.completion.call_args.kwargs['messages'][-2]['content'], CODES[0])

    def test_provider_context_retry_is_bounded_with_required_code_intact(self):
        provider = Mock(model_cost={}, token_counter=None)
        provider.completion.side_effect = [response(PLAN), response(CODES[0]),
            ContextWindowExceededError('too large'), ContextWindowExceededError('still too large'), response(CODES[1])]
        client = LLMClient('mock', prompt_strategy='plan', review_turn=True)
        with patch.dict(sys.modules, {'litellm': provider}), self.assertRaises(ContextWindowExceededError):
            client.generate_solution(PROMPT)
        self.assertEqual(provider.completion.call_count, 4)
        self.assert_required_tail(provider.completion.call_args.kwargs['messages'], CODES[0], 'Review the implementation')
