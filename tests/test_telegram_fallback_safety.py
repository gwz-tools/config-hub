import importlib.util
import json
import unittest
from pathlib import Path

p = Path("experiments/telegram-fallback/safety.py")
spec = importlib.util.spec_from_file_location("telegram_safety", p)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class TelegramFallbackSafetyTests(unittest.TestCase):
    def setUp(self):
        self.policy = s.load()

    def test_default_deny_and_not_native_mtproxy(self):
        self.assertFalse(self.policy["enabled"])
        self.assertFalse(self.policy["production_ready"])
        self.assertFalse(self.policy["telegram_native_proxy_compatible"])
        with self.assertRaises(s.PolicyDenied):
            s.authorize_destination("149.154.167.1", 443, self.policy)

    def test_reject_dns_rebinding_and_private_ipv4(self):
        for dest in ("telegram.org", "127.0.0.1", "10.0.0.1", "192.168.1.2",
                     "169.254.1.1", "::1", "fe80::1", "::ffff:149.154.167.1",
                     "64:ff9b::959a:a701"):
            p = dict(self.policy, allowed_destinations=[dest])
            with self.assertRaises(s.PolicyDenied):
                s.validate_policy(p)

    def test_limited_literal_ip_is_allowed_only_when_registered(self):
        p = dict(self.policy, allowed_destinations=["1.1.1.1"])
        self.assertEqual(s.authorize_destination("1.1.1.1", 443, p), ("1.1.1.1", 443))
        for dest, port in (("1.1.1.1", 22), ("8.8.8.8", 443), ("example.org", 443)):
            with self.assertRaises(s.PolicyDenied):
                s.authorize_destination(dest, port, p)

    def test_resource_caps_fail_closed(self):
        p = dict(self.policy, max_queue_bytes=10000000)
        with self.assertRaises(s.PolicyDenied):
            s.validate_policy(p)
        p = dict(self.policy, require_authenticated_client=False)
        with self.assertRaises(s.PolicyDenied):
            s.validate_policy(p)

    def test_backpressure_and_ack(self):
        q = s.BoundedQueue(10, 8)
        with self.assertRaises(s.PolicyDenied):
            q.enqueue(4)
        q.ready()
        q.enqueue(8)
        with self.assertRaises(s.PolicyDenied):
            q.enqueue(3)
        q.acknowledge(6)
        self.assertEqual(q.pending, 2)
        q.close()
        self.assertEqual(q.pending, 0)
        with self.assertRaises(s.PolicyDenied):
            q.enqueue(1)


if __name__ == "__main__":
    unittest.main()
