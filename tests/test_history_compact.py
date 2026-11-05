import json
import os
import tempfile
import unittest
from pathlib import Path
import history_manager as history
import top_pool


def configs(count):
    return [f'vless://00000000-0000-4000-8000-{i:012d}@192.0.2.{i%200+1}:443?security=reality&type=tcp#label{i}' for i in range(count)]


class CompactHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = Path.cwd()
        os.chdir(self.temp.name)
        Path('data').mkdir()
        Path('history').mkdir()

    def tearDown(self):
        os.chdir(self.cwd)
        self.temp.cleanup()

    def write_configs(self, items):
        Path('data/validated.txt').write_text('\n'.join(items) + '\n', encoding='utf-8')

    def test_ten_summaries_ten_bits_no_full_uris(self):
        self.write_configs(configs(81))
        for _ in range(15):
            self.assertTrue(history.update_history())
        summaries = json.loads(history.SUCCESS_FILE.read_text())
        self.assertEqual(len(summaries['runs']), 10)
        compact = json.loads(history.QUALITY_FILE.read_text())
        self.assertEqual(len(compact['records']), 81)
        self.assertTrue(all(v == 1023 for v in compact['records'].values()))
        self.assertNotIn('vless://', history.QUALITY_FILE.read_text())
        self.assertFalse(Path('history/quality/sources.json').exists())
        self.assertEqual(list(Path('history/quality').glob('20*.json')), [])

    def test_failed_refresh_does_not_advance_history(self):
        self.write_configs(configs(90))
        self.assertTrue(history.update_history())
        baseline = history.QUALITY_FILE.read_bytes()
        self.write_configs(configs(3))
        self.assertFalse(history.update_history())
        self.assertEqual(history.QUALITY_FILE.read_bytes(), baseline)
        self.assertEqual(len(json.loads(history.SUCCESS_FILE.read_text())['runs']), 1)
        self.assertEqual(len(history.read_lines(history.LAST_GOOD)), 90)

    def test_remark_change_not_another_connection(self):
        c = configs(1)[0]
        self.assertEqual(history.fingerprint(c), history.fingerprint(c.split('#')[0] + '#different'))

    def test_top_pool_preserves_existing_eligible(self):
        entries = configs(90)
        self.write_configs(entries)
        Path('fast.txt').write_text('\n'.join(entries[40:90]) + '\n')
        self.assertTrue(history.update_history())
        self.assertTrue(top_pool.build_pool())
        self.assertEqual(history.read_lines(Path('data/top_pool.txt')), entries[40:90])

    def test_old_observations_expire(self):
        old_key = history.fingerprint('vless://old')
        prev = {old_key: 1023}
        new = history.advance_windows(configs(100), prev)
        self.assertEqual(len(new), 101)
        for _ in range(10):
            new = history.advance_windows(configs(100), new)
        self.assertNotIn(old_key, new)


if __name__ == '__main__':
    unittest.main()
