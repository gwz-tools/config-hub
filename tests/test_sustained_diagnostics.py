import importlib.util
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

spec = importlib.util.spec_from_file_location("sustained", "diagnostics/sustained.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


LINK = ("vless://123e4567-e89b-12d3-a456-426614174000@1.1.1.1:443?"
        "security=reality&type=tcp&pbk=publickey&fp=chrome#remark")


class SustainedTests(unittest.TestCase):
    def test_https_rejection_not_proxy_unreachable(self):
        self.assertEqual(s.classify(0, 403), "service_specific_http_rejection")
        self.assertEqual(s.classify(0, 451), "service_specific_http_rejection")
        self.assertEqual(s.classify(60, 0), "certificate_validation_failure")
        self.assertEqual(s.classify(35, 0), "tls_handshake_failure")
        self.assertEqual(s.classify(28, 0), "timeout")
        self.assertEqual(s.classify(0, 204), "success")

    def test_transport_metadata_has_no_credentials(self):
        d = s.transport_metadata(LINK)
        self.assertEqual(d["transport"], "tcp")
        self.assertEqual(d["security"], "reality")
        self.assertNotIn("uuid", d)
        self.assertNotIn("pbk", d)

    def test_summarization_counts_failures_and_latency(self):
        observations = [
            {"ok": True, "reason": "success", "latency_ms": 200},
            {"ok": False, "reason": "timeout"},
            {"ok": False, "reason": "timeout"},
            {"ok": True, "reason": "success", "latency_ms": 300},
        ]
        row = s.summarize(LINK, {"error": None, "observations": observations})
        self.assertEqual(row["max_consecutive_failures"], 2)
        self.assertEqual(row["success_pct"], 50)
        self.assertEqual(row["samples"], 4)
        self.assertEqual(row["reasons"]["timeout"], 2)
        self.assertNotIn("123e4567", str(row))

    @patch.object(s.subprocess, "run")
    def test_explicit_proxy_and_tls_verification(self, run):
        run.return_value = Mock(stdout="204 0.223 0", returncode=0)
        result = s.probe(1080)
        self.assertTrue(result["ok"])
        command = run.call_args.args[0]
        self.assertIn("--proxy", command)
        self.assertIn("http://127.0.0.1:1080", command)
        self.assertNotIn("--insecure", command)
        self.assertNotIn("-k", command)
        self.assertNotIn("--location", command)
        self.assertIn("--max-filesize", command)

    @patch.object(s.subprocess, "run")
    def test_probe_error_is_not_success(self, run):
        run.return_value = Mock(stdout="000 0.500 0", returncode=35)
        self.assertEqual(s.probe(1080)["reason"], "tls_handshake_failure")


if __name__ == "__main__":
    unittest.main()
