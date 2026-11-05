import unittest
from unittest.mock import patch
import cloud_diversity as diversity


def row(ip, entry_asn, exit_asn, country='NL', entry_country='NL'):
    return {
        'line': f'fake://{ip}', 'entry_ip': ip, 'entry_asn': entry_asn,
        'exit_asn': exit_asn, 'exit_country': country,
        'entry_country': entry_country,
    }


class DiversityUnitTests(unittest.TestCase):
    def test_same_ipv4_24_cannot_dominate(self):
        rows = [row(f'51.158.206.{i + 1}', 100+i, 200+i) for i in range(5)]
        rows += [row('77.90.2.130', 333, 444, 'DE')]
        selected, meta = diversity.select(rows, 20)
        self.assertEqual(len(selected), 2)
        self.assertEqual(meta['unique_entry_prefixes'], 2)

    def test_operators_max_two_asns(self):
        rows = [row(f'77.9.{i}.2', 42, 43) for i in range(4)]
        selected, _ = diversity.select(rows, 20)
        self.assertEqual(len(selected), 2)

    def test_country_cap_three(self):
        rows = [row(f'90.40.{i}.3', i+1, i+100) for i in range(6)]
        selected, _ = diversity.select(rows, 20)
        self.assertEqual(len(selected), 3)

    def test_ru_entry_and_exit_rejected(self):
        rows = [row('51.158.2.1', 1, 2, 'RU'),
                row('51.158.3.1', 3, 4, 'DE', 'RU'),
                row('51.158.4.1', 5, 6, 'DE')]
        selected, _ = diversity.select(rows, 20)
        self.assertEqual(len(selected), 1)

    def test_unknown_or_private_ip_rejected(self):
        self.assertFalse(diversity.eligible({'entry_ip': '127.0.0.1'}))
        self.assertFalse(diversity.eligible(row('10.0.0.1', 4, 5)))
        self.assertFalse(diversity.eligible(row('1.1.1.1', 4, 5, 'ZZ')))
        self.assertEqual(diversity.network_key('2001:4860:4860::8888'),
                         '2001:4860:4860::/48')

    def test_geolocation_normalization_and_russia(self):
        info = {'success': True, 'ip': '8.8.8.8', 'country_code': 'US',
                'connection': {'asn': 'AS15169'}}
        self.assertEqual(diversity.normalize_geo(info)['asn'], 15169)
        info['country_code'] = 'RU'
        with self.assertRaises(ValueError):
            diversity.normalize_geo(info)
        info['country_code'] = 'US'
        info['connection']['asn'] = None
        with self.assertRaises(ValueError):
            diversity.normalize_geo(info)

    def test_egress_lookup_always_uses_local_proxy(self):
        class FakeRun:
            returncode = 0
            stdout = '{"success":true,"ip":"8.8.8.8","country_code":"US","connection":{"asn":15169}}'
        with patch.object(diversity.subprocess, 'run', return_value=FakeRun()) as mocked:
            self.assertEqual(diversity.exit_geo(4567)['country'], 'US')
            cmd = mocked.call_args.args[0]
            self.assertIn('--proxy', cmd)
            self.assertIn('http://127.0.0.1:4567', cmd)

    def test_rank_order_with_asn_fallback(self):
        rows = [row('77.90.1.2', 1, 10), row('77.90.2.2', 1, 10),
                row('77.90.3.2', 2, 20)]
        selected, summary = diversity.select(rows, 10)
        self.assertEqual(selected, rows)
        self.assertEqual(summary['unique_exit_asns'], 2)

    def test_multi_ipv6_same_48(self):
        rows = [row('2001:4860:4860::1', 1, 2), row('2001:4860:4860::2', 3, 4)]
        selected, _ = diversity.select(rows, 10)
        self.assertEqual(len(selected), 1)


if __name__ == '__main__':
    unittest.main()
