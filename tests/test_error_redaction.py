import unittest

from aibenchmark_esw.errors import error_diagnostic


class TestErrorRedaction(unittest.TestCase):
    def test_credential_query_values_are_removed_from_diagnostics(self):
        for name in ('key', 'token', 'KEY', 'Token'):
            for separator in ('?', '&'):
                with self.subTest(name=name, separator=separator):
                    prefix = '?' if separator == '?' else '?format=text&'
                    url = f'https://example.invalid/generate{prefix}{name}=FAKE_AUDIT_VALUE&mode=json'
                    diagnostic = error_diagnostic(RuntimeError(url))
                    self.assertNotIn('FAKE_AUDIT_VALUE', diagnostic)
                    self.assertIn(f'{separator}{name}=[REDACTED]&mode=json', diagnostic)

    def test_query_redaction_preserves_fragment_and_noncredential_parameters(self):
        diagnostic = error_diagnostic(ValueError(
            'https://example.invalid/?token=FAKE_AUDIT_VALUE#details'))
        self.assertNotIn('FAKE_AUDIT_VALUE', diagnostic)
        self.assertIn('token=[REDACTED]#details', diagnostic)
        ordinary = 'https://example.invalid/?monkey=banana&token_count=12'
        self.assertIn(ordinary, error_diagnostic(ValueError(ordinary)))

    def test_query_redaction_consumes_apostrophes_in_credential_values(self):
        for value in ("prefix'FAKE_AUDIT_VALUE", "'FAKE_AUDIT_VALUE", "FAKE_AUDIT_VALUE'"):
            with self.subTest(value=value):
                diagnostic = error_diagnostic(ValueError(
                    f'https://example.invalid/?token={value}&mode=json'))
                self.assertEqual(diagnostic,
                    'ValueError: https://example.invalid/?token=[REDACTED]&mode=json')

    def test_query_like_fragment_content_is_preserved(self):
        for fragment in ('details?key=section-name', 'details&token=section-name'):
            for query in ('?token=FAKE_AUDIT_VALUE', ''):
                with self.subTest(fragment=fragment, query=query):
                    diagnostic = error_diagnostic(ValueError(
                        f'https://example.invalid/{query}#{fragment}'))
                    self.assertTrue(diagnostic.endswith(f'#{fragment}'))
                    self.assertNotIn('FAKE_AUDIT_VALUE', diagnostic)

    def test_quoted_urls_keep_diagnostic_delimiters(self):
        for quote in ('"', "'"):
            with self.subTest(quote=quote):
                diagnostic = error_diagnostic(ValueError(
                    f'failed at {quote}https://example.invalid/?key=FAKE_AUDIT_VALUE{quote}, retry'))
                self.assertEqual(diagnostic,
                    f'ValueError: failed at {quote}https://example.invalid/?key=[REDACTED]{quote}, retry')

    def test_apostrophes_inside_single_quoted_urls_are_redacted(self):
        diagnostic = error_diagnostic(ValueError(
            "request failed 'https://example.invalid/?token=prefix'FAKE_AUDIT_VALUE&mode=json'"))
        self.assertEqual(diagnostic,
            "ValueError: request failed 'https://example.invalid/?token=[REDACTED]&mode=json'")

    def test_multiple_url_queries_and_fragments_are_independent(self):
        diagnostic = error_diagnostic(ValueError(
            'https://one.invalid/?key=FAKE_AUDIT_VALUE#details&token=section-name '
            'https://two.invalid/?token=FAKE_OTHER_VALUE&mode=json#details?key=section-name'))
        self.assertEqual(diagnostic,
            'ValueError: https://one.invalid/?key=[REDACTED]#details&token=section-name '
            'https://two.invalid/?token=[REDACTED]&mode=json#details?key=section-name')
