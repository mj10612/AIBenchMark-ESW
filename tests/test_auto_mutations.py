import unittest

from aibenchmark_esw import mutations
from aibenchmark_esw.dataset import DatasetLoader


class TestAutomaticMutations(unittest.TestCase):
    def test_generator_is_deterministic_masks_literals_and_changes_one_location(self):
        self.assertTrue(hasattr(mutations, "generate_mutations"))
        source = '/* x <= 10 */\nconst char *s="x <= 10";\nint f(int x){if(x <= 10)return x+1;return 0;}\n'
        generated = mutations.generate_mutations(source, max_mutants=8)
        self.assertTrue(generated)
        self.assertEqual(generated, mutations.generate_mutations(source, max_mutants=8))
        for mutation in generated:
            changed = mutation.apply(source)
            self.assertTrue(changed.startswith('/* x <= 10 */\nconst char *s="x <= 10";'))
            self.assertNotEqual(changed, source)

    def test_auto_report_keeps_reviewed_gate_and_bounded_counts(self):
        loader = DatasetLoader()
        report = mutations.run_mutations([loader.get_task("tier1_crc16")], loader,
                                         auto=True, max_mutants=4, jobs=2, min_score=0)
        self.assertTrue(report["passed"], report)
        row = report["tasks"][0]
        self.assertGreater(row["killed"], 0)
        self.assertEqual(len(row["automatic"]["mutants"]), 4)
        self.assertEqual(row["automatic"]["equivalent_suspect"], 0)
        self.assertIn("generator_version", report)

    def test_invalid_auto_settings_are_rejected(self):
        loader = DatasetLoader()
        for settings in ({"jobs": 0}, {"max_mutants": 0}, {"min_score": 1.1}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                mutations.run_mutations([], loader, auto=True, **settings)

    def test_generator_includes_null_return_and_constant_boundary_probes(self):
        self.assertTrue(hasattr(mutations, "generate_mutations"))
        source = "int f(int *p){if(p == NULL) return -1; if(*p > INT32_MAX) return 2; return *p+3;}"
        generated = mutations.generate_mutations(source, max_mutants=50)
        kinds = {mutation.name.rsplit("-", 1)[-1] for mutation in generated}
        self.assertTrue({"null", "return", "boundary", "increment", "decrement"}.issubset(kinds), kinds)
