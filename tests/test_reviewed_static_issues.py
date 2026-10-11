import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.sandbox.c_source import mask_noncode
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class TestReviewedStaticIssues(unittest.TestCase):
    def analyze(self, source, extended=False):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.c"
            path.write_text(source, encoding="utf-8")
            return StaticAnalyzer("off", extended_rules=extended).analyze(path)

    def test_comment_opener_cannot_overlap_its_closer(self):
        for source in ("/*/ malloc(1); */ int x;", "/*//// malloc(1);\nfree(0); */ int x;"):
            with self.subTest(source=source):
                self.assertNotIn("malloc", mask_noncode(source))
                self.assertEqual(self.analyze(source).error_count, 0)

    def test_nested_struct_union_fields_are_storage(self):
        for kind in ("struct", "union"):
            source = f'{kind} outer {{ struct inner {{ int x; }} sub; int free; void *malloc; }};'
            self.assertEqual(self.analyze(source).error_count, 0)

    def test_allocators_may_be_local_values_and_parameters(self):
        for source in ('int f(void){int free=3;return free;}',
                       'int f(int calloc){return calloc;}',
                       'int f(int (*free)(void)){return free();}'):
            with self.subTest(source=source):
                self.assertEqual(self.analyze(source).error_count, 0)

    def test_shadowed_names_do_not_suppress_other_functions_or_outer_scopes(self):
        for source in ('int helper(int read){return read;}\nint evil(void){return read(0,0,0);}',
                       'int helper(void){int free=3;return free;}\nvoid evil(void){free(0);}',
                       'void evil(void){{int read=0;(void)read;}read(0,0,0);}'):
            with self.subTest(source=source):
                self.assertEqual(self.analyze(source).error_count, 1)

    def test_indirect_host_references_and_external_prototypes_are_detected(self):
        for source in ('void go(void){reg(system);}', 'static struct ops o={system};',
                       'extern int system(const char *);void f(void){system(0);}'):
            with self.subTest(source=source):
                self.assertEqual(self.analyze(source).error_count, 1)

    def test_finding_points_to_actual_reference_after_exempt_member(self):
        source = 'void f(struct foo *b,void *p){\n b->free=0;\n\n free(p);\n}'
        self.assertEqual(self.analyze(source).findings[0]["line"], 4)
        source = 'void f(struct foo *b){\n b->read();\n\n read(0,0,0);\n}'
        self.assertEqual(self.analyze(source).findings[0]["line"], 4)

    def test_standalone_signed_unsigned_types_warn(self):
        for source in ('unsigned x;', 'signed y;', 'unsigned f(void){return 0;}',
                       'int f(void){return (signed)1;}'):
            with self.subTest(source=source):
                self.assertTrue(any(f["rule_id"] == "builtin.misra.4.6" for f in self.analyze(source).findings))

    def test_indexing_and_sizeof_bounds_are_not_vlas(self):
        for source in ('int get(const int *t,int index){return t[index];}',
                       'void f(void){int a[sizeof(int)];}',
                       'void f(void){uint8_t a[sizeof(header_t)*2];}',
                       'void f(void){int a[sizeof(int)+COUNT];}'):
            with self.subTest(source=source):
                self.assertFalse(any(f["rule_id"] == "builtin.misra.18.8" for f in self.analyze(source, True).findings))
        self.assertTrue(any(f["rule_id"] == "builtin.misra.18.8" for f in
                            self.analyze('void f(int n){int a[sizeof(int)+n];}', True).findings))

    def test_each_busy_loop_uses_its_own_body(self):
        for source in ('void loop(void){while(1){}}\nvoid other(void){return;}',
                       'void f(void){while(1){break;}for(;;){}}',
                       'void f(void){while(1);return;}'):
            with self.subTest(source=source):
                self.assertTrue(any(f["rule_id"] == "builtin.busy-wait" for f in self.analyze(source, True).findings))
        self.assertFalse(any(f["rule_id"] == "builtin.busy-wait" for f in
                             self.analyze('void f(void){while(1){if(ready)break;}}', True).findings))
