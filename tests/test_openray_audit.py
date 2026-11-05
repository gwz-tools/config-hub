import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("openray_audit", "optional_sources/audit_openray.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
LIMITS = {"min_total_lines": 6, "min_vless_candidates": 2, "max_vless_candidates": 10}
GOOD1 = "vless://48ff2b70-e180-582f-8866-d9a2edeed5f5@1.1.1.1:443?security=reality&type=tcp&pbk=abc#Netherlands"
GOOD2 = "vless://a8321cfe-39a2-48a0-a918-f01f7d9006ed@8.8.8.8:443?security=tls&type=ws#Poland"


class Tests(unittest.TestCase):
    def test_audit_dedup_and_mixed(self):
        lines = "\n".join([GOOD1, GOOD1, GOOD2, "ss://placeholder",
                           "vmess://placeholder", "trojan://placeholder"])
        got = mod.audit(lines, LIMITS)
        self.assertEqual(got["vless_valid"], 2)
        self.assertEqual(got["vless_duplicate"], 1)
        self.assertEqual(got["other_protocols"], 3)

    def test_reject_empty_truncated(self):
        with self.assertRaises(ValueError):
            mod.audit(GOOD1, LIMITS)

    def test_fail_closed_on_missing_key(self):
        with self.assertRaises(ValueError):
            mod.candidate_fingerprint(
                "vless://48ff2b70-e180-582f-8866-d9a2edeed5f5@1.1.1.1:443?security=reality"
            )

    def test_exclude_local_and_insecure(self):
        for val in ("vless://48ff2b70-e180-582f-8866-d9a2edeed5f5@127.0.0.1:443?security=tls",
                    GOOD2.replace("security=tls", "security=tls&allowInsecure=1")):
            with self.assertRaises(ValueError):
                mod.candidate_fingerprint(val)

    def test_production_disabled(self):
        c = json.loads(Path("optional_sources/openray.json").read_text())
        self.assertFalse(c["enabled_for_production"])
        self.assertEqual(c["max_download_bytes"], 100000)


if __name__ == "__main__":
    unittest.main()
