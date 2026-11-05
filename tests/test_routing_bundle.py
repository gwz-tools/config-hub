import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "routing"))
from publish_bundle import render_bundle, verify_bundle


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.direct = ["vk.com", "sber.ru"]
        self.proxy = ["telegram.org", "openai.com"]
        self.files, self.manifest = render_bundle(self.direct, self.proxy)

    def test_reproducible_and_hash_verified(self):
        second, m2 = render_bundle(list(reversed(self.direct)), list(reversed(self.proxy)))
        self.assertEqual(self.files, second)
        self.assertEqual(self.manifest, m2)
        self.assertTrue(verify_bundle(self.files, self.manifest))

    def test_mutation_changes_version(self):
        _, newer = render_bundle(self.direct + ["ya.ru"], self.proxy)
        self.assertNotEqual(self.manifest["version"], newer["version"])

    def test_remove_domain_changes_version(self):
        files, newer = render_bundle(["vk.com"], self.proxy)
        self.assertNotEqual(self.manifest["version"], newer["version"])
        self.assertNotIn("sber.ru", files["direct.txt"].decode())

    def test_reject_tamper(self):
        corrupted = dict(self.files)
        corrupted["proxy.txt"] = b"openai.com\n"
        with self.assertRaises(ValueError):
            verify_bundle(corrupted, self.manifest)

    def test_reject_incomplete_snapshot(self):
        incomplete = dict(self.files)
        del incomplete["direct.txt"]
        with self.assertRaises(ValueError):
            verify_bundle(incomplete, self.manifest)

    def test_no_downgrade_or_conflict(self):
        with self.assertRaises(ValueError):
            render_bundle(["vk.com"], ["vk.com"])
        with self.assertRaises(ValueError):
            render_bundle(["vk.com"], ["api.vk.com"])

    def test_expected_policy(self):
        self.assertEqual(self.manifest["default_route"], "PROXY")
        self.assertTrue(self.manifest["update_policy"]["atomic_activation"])
        self.assertTrue(self.manifest["update_policy"]["retain_last_known_good"])


if __name__ == "__main__":
    unittest.main()
