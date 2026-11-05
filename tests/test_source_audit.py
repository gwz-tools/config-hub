import base64
import unittest
from unittest.mock import patch
import source_audit as a


class AuditTests(unittest.TestCase):
    def test_vless_text_dedup(self):
        b=b'vless://one@1.1.1.1:443#one\nvless://one@1.1.1.1:443#two\nvless://two@1.1.1.1:443#three'
        self.assertEqual(a.describe('https://raw.githubusercontent.com/a/b/main/x.txt',b)[0:2],('vless_text',2))

    def test_base64(self):
        b=base64.b64encode(b'vless://one@1.1.1.1:443#one\nvless://two@1.1.1.1:443#two')
        self.assertEqual(a.describe('https://raw.githubusercontent.com/a/b/main/x.txt',b)[0:2],('vless_base64',2))

    def test_routing_list_never_subscribed(self):
        b=b'vless://one@1.1.1.1:443#name'
        self.assertEqual(a.describe('https://raw.githubusercontent.com/a/b/main/WHITE-CIDR-RU-all.txt',b)[0],'routing_rules')

    def test_html_200_not_subscription(self):
        self.assertEqual(a.describe('https://gitverse.ru/a',b'<html>OK</html>','text/html')[0],'webpage_not_feed')

    def test_api_and_directory_not_feeds(self):
        self.assertEqual(a.inspect('https://github.com/owner/repo')['status'],'not_feed')
        self.assertEqual(a.inspect('https://api.github.com/search/repositories?q=vless')['status'],'not_feed')

    def test_dont_access_unapproved_hosts(self):
        self.assertFalse(a.approved('http://raw.githubusercontent.com/a/b'))
        self.assertFalse(a.approved('https://127.0.0.1/config'))
        self.assertFalse(a.approved('https://evil.example/x'))


if __name__ == '__main__':
    unittest.main()
