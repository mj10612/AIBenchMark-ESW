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
