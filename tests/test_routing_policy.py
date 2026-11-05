import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("routing_build", "routing/build.py")
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class RoutingPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(Path("routing/policy.json").read_text(encoding="utf-8"))
        cls.compiled = routing.compile_policy(cls.policy)

    def test_expected_direct_and_proxy(self):
        self.assertEqual(routing.route("passport.yandex.ru", self.compiled), "DIRECT")
        self.assertEqual(routing.route("sub.vk.com", self.compiled), "DIRECT")
        self.assertEqual(routing.route("www.example.com", self.compiled), "PROXY")
        self.assertEqual(routing.route("checkip.amazonaws.com", self.compiled), "PROXY")

    def test_review_is_not_forced_direct(self):
        self.assertEqual(routing.route("cdn.yastatic.net", self.compiled), "PROXY")
        self.assertIn("yastatic.net", self.compiled["review_candidates"])

    def test_suffix_boundaries(self):
        self.assertEqual(routing.route("notyandex.ru", self.compiled), "PROXY")
        self.assertEqual(routing.domain("*.VK.COM."), "vk.com")

    def test_specific_override(self):
        policy = dict(self.policy, direct_domains=["example.com"], proxy_domains=["api.example.com"])
        compiled = routing.compile_policy(policy)
        self.assertEqual(routing.route("api.example.com", compiled), "PROXY")
        self.assertEqual(routing.route("www.example.com", compiled), "DIRECT")
        self.assertEqual(len(compiled["overrides"]), 1)

    def test_conflicts_fail(self):
        with self.assertRaises(ValueError):
            routing.compile_policy(dict(self.policy, direct_domains=["same.example"], proxy_domains=["same.example"]))

    def test_ip_services_never_forced_direct(self):
        with self.assertRaises(ValueError):
            routing.compile_policy(dict(self.policy, direct_domains=["ifconfig.me"]))

    def test_cidr_accepts_both_families_and_collapses(self):
        rows = routing.parse_cidrs("8.8.8.0/25\n8.8.8.128/25\n2606:4700:4700::1111/128\n")
        self.assertIn("8.8.8.0/24", rows)
        self.assertIn("2606:4700:4700::1111/128", rows)

    def test_wrongly_named_igareck_feed_rejected(self):
        with self.assertRaises(ValueError):
            routing.parse_cidrs("# WHITE-CIDR-RU-all\nvless://uuid@host:443\n")

    def test_no_private_or_default_routes(self):
        for value in ("0.0.0.0/0", "192.168.1.0/24", "::/0"):
            with self.assertRaises(ValueError):
                routing.parse_cidrs(value)


if __name__ == "__main__":
    unittest.main()
