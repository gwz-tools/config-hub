import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "routing"))
import build_confirmed as confirmed
import build


class ConfirmedRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.direct = confirmed.read_domains("routing/confirmed-direct-20261105.txt")
        cls.proxy = confirmed.read_domains("routing/confirmed-proxy-20261105.txt")
        cls.compiled = confirmed.compile_confirmed(cls.direct, cls.proxy)

    def test_counts(self):
        self.assertGreater(len(self.direct), 0)
        self.assertGreater(len(self.proxy), 0)
        self.assertEqual(self.direct, sorted(set(self.direct)))
        self.assertEqual(self.proxy, sorted(set(self.proxy)))

    def test_routing(self):
        self.assertEqual(build.route("auth.sber.ru", self.compiled), "DIRECT")
        self.assertEqual(build.route("cdn-vk.ru", self.compiled), "DIRECT")
        self.assertEqual(build.route("trvl.yandex.net", self.compiled), "DIRECT")
        self.assertEqual(build.route("api.openai.com", self.compiled), "PROXY")
        self.assertEqual(build.route("telegram.org", self.compiled), "PROXY")
        self.assertEqual(build.route("notvk.com", self.compiled), "PROXY")
        self.assertEqual(build.route("ifconfig.me", self.compiled), "PROXY")

    def test_fail_closed_on_conflicts(self):
        with self.assertRaises(ValueError):
            confirmed.compile_confirmed(["example.com"], ["example.com"])
        with self.assertRaises(ValueError):
            confirmed.compile_confirmed(["example.com"], ["api.example.com"])
        with self.assertRaises(ValueError):
            confirmed.compile_confirmed(["api.example.com"], ["example.com"])

    def test_review_domains_not_promoted(self):
        self.assertNotIn("5ka.ru", self.direct)
        self.assertNotIn("gorzdrav.spb.ru", self.direct)
        self.assertEqual(build.route("gorzdrav.spb.ru", self.compiled), "PROXY")


if __name__ == "__main__":
    unittest.main()
