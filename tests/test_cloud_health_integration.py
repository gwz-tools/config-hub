import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cloud_health
import cloud_verified as cloud

U = "123e4567-e89b-12d3-a456-426614174000"


def candidate(i):
    return (f"vless://{U}@1.1.1.{i}:443?"
            "encryption=none&security=reality&type=tcp&sni=example.com&"
            "pbk=examplePublicKey&sid=12ab&fp=chrome#name")


class CloudHealthIntegrationTests(unittest.TestCase):
    def prepare(self, folder, size=4, min_live=1):
        source = folder / "candidates.txt"
        source.write_text("\n".join(candidate(i) for i in range(1, size + 1)) + "\n")
        return argparse.Namespace(source=source, output=folder / "cloud-vless.txt",
                                  metadata=folder / "status.json",
                                  health_file=folder / "data/cloud-health.json",
                                  max_candidates=2, max_published=2, min_live=min_live,
                                  workers=2, sing_box="unused")

    def test_success_records_real_checks_and_publishes(self):
        with tempfile.TemporaryDirectory() as td:
            args = self.prepare(Path(td))
            def fake(link, _):
                return {"line": link, "functional": 4, "latency": .3,
                        "statuses": {name: 200 for name in cloud.SERVICE_URLS}}
            with patch.object(cloud, "test_candidate", side_effect=fake):
                cloud.build(args)
            status = json.loads(args.metadata.read_text())
            state = cloud_health.load(args.health_file)
            self.assertTrue(status["published"])
            self.assertEqual(status["candidates_tested"], 2)
            self.assertEqual(status["health_tracked_nodes"], 2)
            self.assertEqual(len(status["success_scores"]), 2)
            self.assertEqual(len(state["nodes"]), 2)
            self.assertNotIn("vless://", args.health_file.read_text())
            self.assertEqual(len(args.output.read_text().splitlines()), 2)

    def test_zero_success_preserves_subscription_and_rotates(self):
        with tempfile.TemporaryDirectory() as td:
            args = self.prepare(Path(td), min_live=2)
            args.output.write_text(candidate(1) + "\n")
            with patch.object(cloud, "test_candidate", return_value=None):
                cloud.build(args)
            state = cloud_health.load(args.health_file)
            status = json.loads(args.metadata.read_text())
            self.assertEqual(state["cursor"], 2)
            self.assertEqual(state["nodes"], {})
            self.assertFalse(status["health_state_updated"])
            self.assertTrue(status["stale_previous_list_retained"])
            self.assertEqual(args.output.read_text(), candidate(1) + "\n")

    def test_partial_success_records_only_actual_tests(self):
        with tempfile.TemporaryDirectory() as td:
            args = self.prepare(Path(td), min_live=2)
            args.output.write_text(candidate(4) + "\n")
            def fake(link, _):
                return {"line": link, "functional": 4, "latency": .4,
                        "statuses": {name: 200 for name in cloud.SERVICE_URLS}} if "1.1.1.1:" in link else None
            with patch.object(cloud, "test_candidate", side_effect=fake):
                cloud.build(args)
            state = cloud_health.load(args.health_file)
            samples = [v["checks"][0]["ok"] for v in state["nodes"].values()]
            self.assertEqual(sorted(samples), [0, 1])
            self.assertEqual(args.output.read_text(), candidate(4) + "\n")


if __name__ == "__main__":
    unittest.main()
