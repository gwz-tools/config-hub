import json
import tempfile
import unittest
from pathlib import Path
import cloud_health as h


def make(i):
    return f'vless://00000000-0000-4000-8000-{i:012d}@8.8.8.8:443?security=reality&type=tcp#name{i}'


class HealthTests(unittest.TestCase):
    def test_canonical_identity_and_no_secrets_in_health(self):
        self.assertEqual(h.identity(make(1)), h.identity(make(1).split('#')[0] + '#new-label'))
        s = h.blank()
        h.observe(s, [make(1)], [{'line': make(1), 'latency': 0.2}], now=1_800_000_000)
        self.assertNotIn('vless://', json.dumps(s))
        self.assertNotIn('8.8.8.8', json.dumps(s))
        self.assertNotIn('00000000-0000', json.dumps(s))

    def test_rotation_reaches_whole_collection(self):
        pool = [make(i) for i in range(150)]
        state = h.blank()
        found = set()
        for n in range(5):
            batch = h.choose(pool, state, 40)
            found.update(batch)
            successful = [{'line': x, 'latency': .3} for x in batch[:3]]
            h.observe(state, batch, successful, 1_800_000_000+n*21600)
        self.assertEqual(found, set(pool))
        self.assertTrue(any(v['checks'][-1]['ok'] == 1 for v in state['nodes'].values()))

    def test_untested_not_penalized_and_bounded(self):
        state = h.blank()
        a, b = make(1), make(2)
        t = 1_800_000_000
        h.observe(state, [a, b], [{'line': a, 'latency': .2}], t)
        before = list(state['nodes'][h.identity(b)]['checks'])
        h.observe(state, [a], [{'line': a, 'latency': .3}], t+21600)
        self.assertEqual(state['nodes'][h.identity(b)]['checks'], before)
        for n in range(40):
            h.observe(state, [a], [{'line': a, 'latency': .2}], t+21600*(n+2))
        self.assertLessEqual(len(state['nodes'][h.identity(a)]['checks']), 32)

    def test_rank_sustained_success_above_one_hit(self):
        a, b = make(1), make(2)
        t = 1_800_000_000
        state = h.blank()
        for n in range(4):
            h.observe(state, [a], [{'line': a, 'latency': .5}], t+n*21600)
        h.observe(state, [b], [{'line': b, 'latency': .5}], t+3*21600)
        results = [{'line': a, 'latency': .5}, {'line': b, 'latency': .5}]
        self.assertEqual(h.rank(results, state, t+3*21600)[0]['line'], a)

    def test_slot_deduplication_and_empty_state(self):
        state = h.blank()
        a = make(1)
        t = 1_800_000_000
        h.observe(state, [a], [{'line': a, 'latency': .25}], t)
        h.observe(state, [a], [], t+15)
        self.assertEqual(len(state['nodes'][h.identity(a)]['checks']), 1)
        self.assertEqual(state['nodes'][h.identity(a)]['checks'][0]['ok'], 0)

    def test_save_load_and_corrupt_guard(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'data/cloud-health.json'
            state = h.blank()
            h.observe(state, [make(1)], [{'line': make(1), 'latency': .4}], 1_800_000_000)
            h.save(path, state)
            self.assertEqual(h.load(path), state)
            path.write_text('{bad json')
            with self.assertRaises(ValueError):
                h.load(path)


if __name__ == '__main__':
    unittest.main()
