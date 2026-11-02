import base64
import json
import io
import hashlib
import zipfile
import mamin_signing_key as signing_key
from contextlib import redirect_stderr
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import mamin_verify_import as m


class MaminImportTests(unittest.TestCase):
    def test_exact_apk_sha256_and_bootstrap_public_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private = root / "private.pem"
            public = root / "public.der"
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA",
                            "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private)],
                           check=True, capture_output=True)
            subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout",
                            "-outform", "DER", "-out", str(public)],
                           check=True, capture_output=True)
            der = public.read_bytes()
            apk = root / "synthetic.apk"
            with zipfile.ZipFile(apk, "w") as z:
                z.writestr("classes.dex", b"header\n" + base64.b64encode(der) + b"\n" + b"x" * 1024)
            apk_hash = hashlib.sha256(apk.read_bytes()).hexdigest()
            key_hash = hashlib.sha256(der).hexdigest()
            with patch.object(signing_key, "APK_SHA256", apk_hash), \
                 patch.object(signing_key, "BOOTSTRAP_KEY_SHA256", key_hash):
                self.assertEqual(signing_key.pinned_bootstrap_key(apk), der)
                with apk.open("ab") as f:
                    f.write(b"tamper")
                with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                    signing_key.pinned_bootstrap_key(apk)

    def test_dedup_and_skip_bad_urls(self):
        good = 'vless://123e4567-e89b-12d3-a456-426614174000@1.1.1.1:443?security=reality&type=tcp'
        got = m.vetted_nodes({'nodes': [good, good, 'ftp://bad', 'vless://no-host']})
        self.assertEqual(got, [good])

    def test_invalid_signature_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'catalog.json'
            source.write_text(json.dumps({
                'format': 'mamin-bootstrap-v2',
                'algorithm': 'RS256',
                'key_id': m.KEY_ID,
                'payload': 'e30',
                'signature': 'AA'
            }), encoding='utf-8')
            output = root / 'verified'
            with patch.object(sys, 'argv',
                              ['import', '--catalog-file', str(source),
                               '--output-dir', str(output)]):
                with self.assertRaises((ValueError, RuntimeError)):
                    m.main()
            self.assertFalse(output.exists())

    def test_diagnostics_do_not_leak_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            secret = b'{"nodes":["vless://PRIVATE-CREDENTIAL@1.1.1.1:443"]}'
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({
                "format": "mamin-bootstrap-v2", "algorithm": "RS256",
                "key_id": m.KEY_ID,
                "payload": base64.urlsafe_b64encode(secret).decode().rstrip("="),
                "signature": "AA"
            }), encoding="utf-8")
            output = root / "verified"
            err = io.StringIO()
            with patch.object(sys, "argv", ["import", "--catalog-file", str(catalog),
                                             "--output-dir", str(output), "--diagnose"]):
                with redirect_stderr(err), self.assertRaises((ValueError, RuntimeError)):
                    m.main()
            log = err.getvalue()
            self.assertIn("RS256 audit: FAIL CLOSED", log)
            self.assertIn("Signature bytes:", log)
            self.assertNotIn("PRIVATE-CREDENTIAL", log)
            self.assertFalse(output.exists())

    def test_signed_catalogue_and_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key = root / 'key.pem'
            public_key = root / 'key.der'
            subprocess.run(
                ['openssl', 'genpkey', '-algorithm', 'RSA',
                 '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(key)],
                check=True, capture_output=True)
            subprocess.run(
                ['openssl', 'pkey', '-in', str(key), '-pubout',
                 '-outform', 'DER', '-out', str(public_key)],
                check=True, capture_output=True)
            link = 'vless://123e4567-e89b-12d3-a456-426614174000@1.1.1.1:443?security=reality&type=tcp'
            source = root / 'catalog.json'

            def make_catalog(sequence):
                now = int(time.time())
                payload = json.dumps({
                    'kind': 'mamin-bootstrap-v2',
                    'package': 'app.mamin.vpn',
                    'schema': 1,
                    'issued_at': now - 60,
                    'expires_at': now + 3600,
                    'sequence': sequence,
                    'nodes': [link]
                }).encode()
                payload_path = root / 'payload.bin'
                payload_path.write_bytes(payload)
                signature_path = root / 'signature.bin'
                subprocess.run(
                    ['openssl', 'dgst', '-sha256', '-sign', str(key),
                     '-out', str(signature_path), str(payload_path)],
                    check=True, capture_output=True)
                signed = {
                    'format': 'mamin-bootstrap-v2',
                    'algorithm': 'RS256',
                    'key_id': m.KEY_ID,
                    'payload': base64.urlsafe_b64encode(payload).decode().rstrip('='),
                    'signature': base64.urlsafe_b64encode(signature_path.read_bytes()).decode().rstrip('=')
                }
                source.write_text(json.dumps(signed), encoding='utf-8')

            output = root / 'verified'
            pinned_test_key = base64.b64encode(public_key.read_bytes()).decode()
            with patch.object(m, 'PUBLIC_KEY_DER_B64', pinned_test_key):
                make_catalog(2)
                with patch.object(sys, 'argv',
                                  ['import', '--catalog-file', str(source),
                                   '--output-dir', str(output)]):
                    m.main()
                stored = output / 'mamin-vless-reality.verified.txt'
                self.assertEqual(stored.read_text().strip(), link)

                make_catalog(1)
                with patch.object(sys, 'argv',
                                  ['import', '--catalog-file', str(source),
                                   '--output-dir', str(output)]):
                    with self.assertRaisesRegex(ValueError, 'rollback'):
                        m.main()
                self.assertEqual(stored.read_text().strip(), link)


if __name__ == '__main__':
    unittest.main()
