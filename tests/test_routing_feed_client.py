import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "routing"))

from feed_client_reference import update, read_active, UpdateFailed
from publish_bundle import render_bundle


URL = "https://raw.githubusercontent.com/gwz-tools/config-hub/routing-feed/manifest.json"


def fake_fetcher(files, manifest, *, fail_on=None, corrupt_on=None, return_304=False):
    content = dict(files)
    content["manifest.json"] = json.dumps(manifest).encode()
    def fetch(url, etag=None, limit=None):
        name = url.rsplit("/", 1)[-1]
        if return_304 and name == "manifest.json" and etag:
            return (304, b"", etag)
        if name == fail_on:
            raise UpdateFailed("network interruption")
        data = content[name]
        if name == corrupt_on:
            data += b"\nevil.example\n"
        return (200, data, "tag1" if name == "manifest.json" else None)
    return fetch


class RoutingFeedUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        self.a, self.ma = render_bundle(["vk.com"], ["telegram.org"])
        self.b, self.mb = render_bundle(["vk.com", "ya.ru"], ["telegram.org"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_install_and_304(self):
        self.assertEqual(update(self.cache, URL, fake_fetcher(self.a, self.ma)), "updated")
        self.assertEqual(read_active(self.cache)[0], self.ma["version"])
        self.assertEqual(update(self.cache, URL, fake_fetcher(self.a, self.ma, return_304=True)), "unchanged")

    def test_atomic_update_and_old_version_retained(self):
        update(self.cache, URL, fake_fetcher(self.a, self.ma))
        self.assertEqual(update(self.cache, URL, fake_fetcher(self.b, self.mb)), "updated")
        self.assertEqual(read_active(self.cache)[0], self.mb["version"])
        self.assertTrue((self.cache / "versions" / self.ma["version"] / "manifest.json").exists())

    def test_download_failure_leaves_previous(self):
        update(self.cache, URL, fake_fetcher(self.a, self.ma))
        with self.assertRaises(UpdateFailed):
            update(self.cache, URL, fake_fetcher(self.b, self.mb, fail_on="proxy.txt"))
        self.assertEqual(read_active(self.cache)[0], self.ma["version"])

    def test_tamper_rejected_without_changing_pointer(self):
        update(self.cache, URL, fake_fetcher(self.a, self.ma))
        with self.assertRaises(UpdateFailed):
            update(self.cache, URL, fake_fetcher(self.b, self.mb, corrupt_on="direct.txt"))
        self.assertEqual(read_active(self.cache)[0], self.ma["version"])

    def test_first_boot_failure_does_not_activate(self):
        with self.assertRaises(UpdateFailed):
            update(self.cache, URL, fake_fetcher(self.b, self.mb, fail_on="direct.txt"))
        self.assertIsNone(read_active(self.cache))

    def test_reject_wrong_scheme_and_hostname(self):
        for target in ("http://example.com/manifest.json", "file:///tmp/manifest.json",
                       "https://example.com:8443/manifest.json",
                       "https://evil.com/manifest.json?redirect=x"):
            with self.assertRaises(UpdateFailed):
                update(self.cache, target, fake_fetcher(self.a, self.ma))

    def test_reject_mismatched_manifest_version(self):
        bad = dict(self.mb, version="0" * 20)
        with self.assertRaises(UpdateFailed):
            update(self.cache, URL, fake_fetcher(self.b, bad))
        self.assertIsNone(read_active(self.cache))


if __name__ == "__main__":
    unittest.main()
