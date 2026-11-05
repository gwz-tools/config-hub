import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud_diversity
import cloud_verified as cloud

UUID = "123e4567-e89b-12d3-a456-426614174000"
IPS = ["51.158.206.12", "51.158.206.20", "51.158.206.30",
       "77.90.2.130", "8.8.8.8"]


def link(ip):
    return (f"vless://{UUID}@{ip}:443?"
            "encryption=none&security=reality&type=tcp&sni=example.com&"
            "pbk=examplepublickey&sid=01&fp=chrome#test")


def result(address):
    loc = IPS.index(address)
    country = ["NL", "NL", "NL", "DE", "US"][loc]
    asn = [12876, 12876, 12876, 2920, 15169][loc]
    return {
        "line": link(address), "functional": 4, "latency": 0.25,
        "statuses": {name: 200 for name in cloud.SERVICE_URLS},
        "entry_ip": address, "entry_country": country, "entry_asn": asn,
        "exit_country": country, "exit_asn": asn,
    }


class DiversityIntegrationTests(unittest.TestCase):
    def setup_args(self, root, addresses, min_live=3):
        source = root / "candidates.txt"
        source.write_text("\n".join(link(x) for x in addresses) + "\n")
        return argparse.Namespace(
            source=source, output=root / "cloud-vless.txt",
            metadata=root / "status.json", health_file=root / "cloud-health.json",
            max_candidates=12, max_published=10, min_live=min_live,
            workers=2, sing_box="unused", diversity=True,
        )

    def test_three_independent_prefixes_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.setup_args(Path(tmp), IPS)
            def fake(config, _bin, diversity):
                self.assertTrue(diversity)
                return result(config.split("@", 1)[1].split(":", 1)[0])
            with patch.object(cloud, "test_candidate", side_effect=fake):
                cloud.build(args)
            values = args.output.read_text().splitlines()
            self.assertEqual(len(values), 3)
            self.assertEqual(len({cloud_diversity.network_key(
                x.split("@", 1)[1].split(":", 1)[0]) for x in values}), 3)
            meta = json.loads(args.metadata.read_text())
            self.assertEqual(meta["passed"], 5)
            self.assertEqual(meta["published_count"], 3)
            self.assertEqual(meta["diversity"]["unique_entry_asns"], 3)
            self.assertEqual(len(meta["success_scores"]), 3)

    def test_fallback_if_three_are_same_subnet(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.setup_args(Path(tmp), IPS[:4])
            previous = link("1.0.0.1") + "\n"
            args.output.write_text(previous)
            def fake(config, _bin, _diversity):
                return result(config.split("@", 1)[1].split(":", 1)[0])
            with patch.object(cloud, "test_candidate", side_effect=fake):
                cloud.build(args)
            meta = json.loads(args.metadata.read_text())
            self.assertEqual(meta["passed"], 4)
            self.assertEqual(meta["diversity"]["selected"], 2)
            self.assertFalse(meta["published"])
            self.assertTrue(meta["stale_previous_list_retained"])
            self.assertEqual(args.output.read_text(), previous)

    def test_russian_location_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.setup_args(Path(tmp), IPS[2:], min_live=2)
            def fake(config, _bin, _diversity):
                ip = config.split("@", 1)[1].split(":", 1)[0]
                entry = result(ip)
                if ip == "8.8.8.8":
                    entry["exit_country"] = "RU"
                return entry
            with patch.object(cloud, "test_candidate", side_effect=fake):
                cloud.build(args)
            self.assertTrue(all("8.8.8.8" not in x for x in args.output.read_text().splitlines()))
            self.assertEqual(json.loads(args.metadata.read_text())["published_count"], 2)


if __name__ == "__main__":
    unittest.main()
