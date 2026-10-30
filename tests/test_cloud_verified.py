import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cloud_verified as cloud

UUID = "123e4567-e89b-12d3-a456-426614174000"
REALITY = (f"vless://{UUID}@203.0.113.12:443?"
           "encryption=none&security=reality&type=tcp&sni=example.com&"
           "pbk=samplepublickey&sid=12ab&fp=chrome#first")
WS = (f"vless://{UUID}@203.0.113.13:443?"
      "encryption=none&security=tls&type=ws&sni=example.com&"
      "host=edge.example.com&path=%2Fws#second")


class CloudFeedTests(unittest.TestCase):
    def test_reality_parser(self):
        v = cloud.parse_vless(REALITY)
        self.assertEqual(v["type"], "vless")
        self.assertTrue(v["tls"]["reality"]["enabled"])
        self.assertEqual(v["tls"]["reality"]["short_id"], "12ab")

    def test_websocket_parser(self):
        v = cloud.parse_vless(WS)
        self.assertEqual(v["transport"]["path"], "/ws")
        self.assertEqual(v["transport"]["headers"]["Host"], "edge.example.com")

    def test_reject_private_ip(self):
        with self.assertRaises(ValueError):
            cloud.parse_vless(REALITY.replace("203.0.113.12", "127.0.0.1"))

    def test_duplicates_ignore_fragment(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "sources.txt"
            source.write_text(REALITY + "\n" + REALITY.replace("#first", "#new") +
                              "\n" + WS + "\n")
            got = cloud.unique_candidates(source, 20)
            self.assertEqual(len(got), 2)

    def test_prevent_empty_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "sources.txt"
            source.write_text(REALITY + "\n")
            target = root / "cloud-vless.txt"
            target.write_text(WS + "\n")
            metadata = root / "status.json"
            args = argparse.Namespace(source=source, output=target, metadata=metadata,
                                      max_candidates=10, max_published=10, min_live=1,
                                      workers=1, sing_box="sing-box")
            with patch.object(cloud, "test_candidate", return_value=None):
                cloud.build(args)
            self.assertEqual(target.read_text(), WS + "\n")
            self.assertTrue(json.loads(metadata.read_text())["stale_previous_list_retained"])

    def test_first_run_empty_fails_safe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "sources.txt"
            source.write_text(REALITY + "\n")
            args = argparse.Namespace(source=source, output=root / "cloud-vless.txt",
                                      metadata=root / "status.json", max_candidates=10,
                                      max_published=10, min_live=1, workers=1,
                                      sing_box="sing-box")
            with patch.object(cloud, "test_candidate", return_value=None):
                with self.assertRaises(RuntimeError):
                    cloud.build(args)
            self.assertFalse(args.output.exists())


if __name__ == "__main__":
    unittest.main()
