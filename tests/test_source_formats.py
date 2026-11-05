"""No-network checks for the public VLESS source parser and registry."""
import base64
import unittest

import collector
from sources import get_sources


URL1 = ("vless://123e4567-e89b-12d3-a456-426614174000@1.1.1.1:443?"
        "type=tcp&security=reality&sni=example.org&pbk=abc#one")
URL2 = ("vless://123e4567-e89b-12d3-a456-426614174001@1.0.0.1:443?"
        "type=ws&security=tls&sni=example.net#two")


class FormatTests(unittest.TestCase):
    def test_plaintext(self):
        self.assertEqual(collector.extract_vless("# comment\n" + URL1 + "\n" + URL2), [URL1, URL2])

    def test_standard_base64(self):
        payload = base64.b64encode((URL1 + "\n" + URL2 + "\n").encode()).decode()
        self.assertEqual(collector.extract_vless(payload), [URL1, URL2])

    def test_urlsafe_unpadded_base64_mixed(self):
        payload = base64.urlsafe_b64encode(
            ("trojan://example@host:443\n" + URL1 + "\n").encode()
        ).decode().rstrip("=")
        self.assertEqual(collector.extract_vless(payload), [URL1])

    def test_html_and_url_indices_not_feeds(self):
        for value in ['<!doctype html><html><body>none</body></html>',
                      'https://example.org/feed1.txt\nhttps://example.org/feed2.txt',
                      '{"outbounds":[{"type":"direct"}]}', '']:
            self.assertEqual(collector.extract_vless(value), [])

    def test_garbage_b64_not_accepted(self):
        self.assertEqual(collector.extract_vless("a" * (16 * 1024 * 1024 + 4)), [])

    def test_registry_has_no_duplicate_names(self):
        names = [s["name"] for s in get_sources()]
        self.assertEqual(len(names), len(set(names)))

    def test_verified_sources_are_feed_urls_not_repos_or_self(self):
        names = {s['name']: s['url'] for s in get_sources()}
        for name in ('cyberportal_cp005', 'cyberportal_cp038', 'cyberportal_cp041',
                     'cyberportal_cp002', 'cyberportal_cp003', 'sakha_openray',
                     'mehrtat_vless', 'roosterkid_v2ray'):
            self.assertIn(name, names)
            self.assertTrue(names[name].startswith("https://"))
            self.assertTrue(names[name].endswith(".txt"))
            self.assertNotIn("gwz-tools/config-hub", names[name])
        self.assertNotIn('cyberportal_cp039', names)
        self.assertNotIn('cyberportal_cp044', names)


if __name__ == "__main__":
    unittest.main()
