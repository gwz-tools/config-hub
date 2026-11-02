import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import mamin_hub_diagnose as diag


class MaminStageDiagnosticsTests(unittest.TestCase):
    def test_curl_probe_returns_numeric_exit_without_leaking_output(self):
        fake = subprocess.CompletedProcess(["curl"], 28, stdout="000", stderr="secret-endpoint.example")
        with patch.object(diag.subprocess, "run", return_value=fake) as p:
            exit_code, code = diag.curl_probe(45678, diag.CONTROL_URL)
        self.assertEqual((exit_code, code), (28, 0))
        args = p.call_args.args[0]
        self.assertEqual(args[0], "curl")
        self.assertIn("--proxy", args)
        self.assertIn("http://127.0.0.1:45678", args)

    def test_error_categories_are_fixed_safe_names(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "private.log"
            p.write_text("Dial 123e4567-SECRET@private-host.example: connection reset by peer; TLS handshake failed")
            os.chmod(p, 0o600)
            categories = diag.classify_run_errors(p)
            self.assertIn("singbox_error_connection_reset", categories)
            self.assertIn("singbox_error_tls_or_reality", categories)
            self.assertNotIn("private-host.example", str(categories))
            self.assertNotIn("SECRET", str(categories))

    def test_absent_log_is_safe(self):
        self.assertEqual(diag.classify_run_errors(Path("/no/such/file/mamin.log")), [])


if __name__ == "__main__":
    unittest.main()
