import json
import os
from pathlib import Path
import tempfile
import unittest

import mamin_hub_update as hub


UUID = "123e4567-e89b-12d3-a456-426614174000"


def hit(ip, functional=4, latency=0.25):
    return {
        "line": f"vless://{UUID}@{ip}:443?security=reality&type=tcp",
        "functional": functional,
        "latency": latency,
        "statuses": {"youtube": 200},
    }


class MaminHubTests(unittest.TestCase):
    def test_empty_probe_keeps_last_good_and_sequence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            original = hit("1.1.1.1")["line"] + "\n"
            hub.atomic_write(root / hub.PRIVATE_FEED, original.encode())
            hub.atomic_write(root / hub.SEQUENCE_FILE, b'{"sequence": 5}')
            staged = root / "new.json"
            staged.write_text('{"sequence": 6}')
            with self.assertRaisesRegex(ValueError, "required"):
                hub.promote(root, staged, [], min_live=3, max_live=20)
            self.assertEqual((root / hub.PRIVATE_FEED).read_text(), original)
            self.assertEqual(json.loads((root / hub.SEQUENCE_FILE).read_text())["sequence"], 5)

    def test_low_probe_keeps_last_good(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            hub.atomic_write(root / hub.PRIVATE_FEED, b"previous\n")
            staged = root / "new.json"
            staged.write_text('{"sequence": 3}')
            with self.assertRaises(ValueError):
                hub.promote(root, staged, [hit("1.1.1.1"), hit("1.0.0.1")], 3, 20)
            self.assertEqual((root / hub.PRIVATE_FEED).read_bytes(), b"previous\n")
            self.assertFalse((root / hub.SEQUENCE_FILE).exists())

    def test_only_valid_verified_unique_published(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage = root / "signed.json"
            stage.write_text('{"sequence": 9}')
            results = [hit("1.1.1.1", latency=0.7),
                       hit("1.0.0.1", latency=0.2),
                       hit("8.8.8.8", latency=0.3),
                       hit("8.8.8.8", latency=0.3),
                       {"line": "not-vless", "functional": 4, "latency": 0.0}]
            count = hub.promote(root, stage, results, min_live=3, max_live=3)
            self.assertEqual(count, 3)
            published = (root / hub.PRIVATE_FEED).read_text().splitlines()
            self.assertEqual(len(published), 3)
            self.assertEqual(published[0], hit("1.0.0.1")["line"])
            self.assertEqual(json.loads((root / hub.SEQUENCE_FILE).read_text())["sequence"], 9)
            self.assertEqual(os.stat(root / hub.PRIVATE_FEED).st_mode & 0o777, 0o600)

    def test_large_deterioration_keeps_previous_healthy_eight(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = "\n".join(hit(f"1.0.0.{i}")["line"] for i in range(1, 9)) + "\n"
            hub.atomic_write(root / hub.PRIVATE_FEED, baseline.encode())
            state = root / "state.json"
            state.write_text('{"sequence": 10}')
            with self.assertRaisesRegex(ValueError, "required"):
                hub.promote(root, state, [hit("1.1.1.1"), hit("8.8.8.8"),
                                         hit("9.9.9.9")], min_live=3, max_live=20)
            self.assertEqual((root / hub.PRIVATE_FEED).read_text(), baseline)

    def test_missing_signed_sequence_blocks_publication(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(ValueError, "sequence"):
                hub.promote(root, root / "missing.json", [hit("1.1.1.1"),
                            hit("1.0.0.1"), hit("8.8.8.8")], 3, 20)
            self.assertFalse((root / hub.PRIVATE_FEED).exists())


if __name__ == "__main__":
    unittest.main()
