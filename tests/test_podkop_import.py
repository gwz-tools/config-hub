import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "routing"))
import import_podkop as imp
import export_ruleset as exported
import build


class PodkopImportTests(unittest.TestCase):
    def test_domain_export_normalizes_deduplicates(self):
        result = imp.parse_domains("VK.COM\n*.vk.com.\nmail.ru, ya.ru // note\n# heading\n")
        self.assertEqual(result, ["mail.ru", "vk.com", "ya.ru"])

    def test_export_rejects_uci_and_secrets(self):
        for body in ("option proxy_string 'vless://uuid@server:443'\n",
                     "https://example.com/feed.txt\n", "root:password\n"):
            with self.assertRaises(ValueError):
                imp.parse_domains(body)

    def test_full_comparison_requires_agreement(self):
        match = imp.inspect_exports({"dunay": "vk.com\nsber.ru", "zorik": "sber.ru\nvk.com"})
        self.assertFalse(match["requires_review"])
        self.assertEqual(len(match["common"]), 2)
        self.assertEqual(match["missing_by_source"]["dunay"], [])

    def test_partial_comparison_fails_closed(self):
        diff = imp.inspect_exports({"dunay": "vk.com\nsber.ru", "zorik": "sber.ru"})
        self.assertTrue(diff["requires_review"])
        self.assertEqual(diff["missing_by_source"]["zorik"], ["vk.com"])

    def test_ruleset_schema_has_no_decisions_or_dns(self):
        policy = {
            "default_public_route": "PROXY",
            "direct_domains": ["vk.com"],
            "proxy_domains": ["api.vk.com", "ifconfig.me"],
            "block_domains": [],
        }
        compiled = build.compile_policy(policy)
        direct = exported.ruleset_for(compiled, "DIRECT")
        proxy = exported.ruleset_for(compiled, "PROXY")
        self.assertEqual(direct, {"version": 3, "rules": [{"domain_suffix": ["vk.com"]}]})
        self.assertIn("api.vk.com", proxy["rules"][0]["domain_suffix"])
        self.assertNotIn("dns", json.dumps(direct))
        self.assertNotIn("outbound", json.dumps(direct))


if __name__ == "__main__":
    unittest.main()
