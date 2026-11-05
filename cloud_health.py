"""Bounded, credential-free history of actual cloud VLESS tunnel checks.

Presence in a subscription is NOT a successful check. Only observations from
cloud_verified.test_candidate count; untested nodes are not marked failed.
Cloud runner success does not prove reachability from a Russian ISP.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

VERSION = 1
SEVEN_DAYS = 7 * 86400
ONE_DAY = 86400
MAX_CHECKS = 32   # approximately seven days at six-hour intervals, with margin
MAX_NODES = 500


def identity(link):
    return hashlib.sha256(link.strip().split('#', 1)[0].encode('utf-8')).hexdigest()


def blank():
    return {'version': VERSION, 'cursor': 0, 'nodes': {}}


def load(path):
    path = Path(path)
    if not path.exists():
        return blank()
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != VERSION or not isinstance(data.get('nodes'), dict):
        raise ValueError('Unsupported cloud health state; refusing to overwrite')
    if not isinstance(data.get('cursor'), int) or data['cursor'] < 0:
        raise ValueError('Invalid health rotation cursor')
    return data


def healthy_history(node):
    checks = node.get('checks', [])
    return bool(checks and isinstance(checks, list) and isinstance(checks[-1], dict)
                and checks[-1].get('ok') == 1)


def score(node, now=None):
    """0..100: recent success 45%, week success 35%, latency 15%, recency 5%.

    With smoothing, one lucky success cannot claim 100% reliability.
    This ranks only the cloud vantage, not a local ISP or geography.
    """
    now = int(time.time() if now is None else now)
    checks = [c for c in node.get('checks', [])
              if isinstance(c, dict) and isinstance(c.get('t'), int)
              and now - SEVEN_DAYS < c['t'] <= now]
    if not checks:
        return 0.0
    day = [c for c in checks if now - ONE_DAY < c['t']]
    def smooth(items):
        return (1 + sum(x.get('ok') == 1 for x in items)) / (2 + len(items))
    latencies = [c['ms'] for c in checks if c.get('ok') == 1
                 and isinstance(c.get('ms'), (int, float)) and c['ms'] >= 0]
    recent_ms = sorted(latencies)[len(latencies) // 2] if latencies else 3000
    latency = max(0.0, min(1.0, (3000 - recent_ms) / 2700))
    age = now - checks[-1]['t']
    freshness = max(0.0, 1.0 - age / ONE_DAY)
    return round(45 * smooth(day) + 35 * smooth(checks) + 15 * latency + 5 * freshness, 2)


def choose(candidates, state, limit):
    """Retest up to one third recent healthy nodes; rotate through the rest."""
    if limit < 1 or not candidates:
        return []
    limit = min(limit, len(candidates))
    by_id = {identity(link): link for link in candidates}
    pinned = [(score(state['nodes'][key]), key) for key in by_id
              if key in state['nodes'] and healthy_history(state['nodes'][key])]
    pinned.sort(key=lambda x: (-x[0], x[1]))
    keep = min(limit // 3, 16)
    chosen = [by_id[key] for _, key in pinned[:keep]]
    used = {identity(link) for link in chosen}
    cursor = state['cursor'] % len(candidates)
    visited = 0
    while len(chosen) < limit and visited < len(candidates):
        link = candidates[cursor]
        cursor = (cursor + 1) % len(candidates)
        visited += 1
        key = identity(link)
        if key not in used:
            chosen.append(link)
            used.add(key)
    state['cursor'] = cursor
    return chosen


def observe(state, tested, successes, now=None):
    """One 6h-run observation per tested candidate; no penalty for untested."""
    now = int(time.time() if now is None else now)
    good = {identity(r['line']): r for r in successes}
    nodes = state['nodes']
    for link in tested:
        key = identity(link)
        entry = nodes.setdefault(key, {'checks': []})
        checks = entry.get('checks', [])
        if not isinstance(checks, list):
            raise ValueError('Corrupt cloud node checks; refusing to overwrite')
        checks = [x for x in checks if isinstance(x, dict)
                  and isinstance(x.get('t'), int) and now - SEVEN_DAYS < x['t'] <= now]
        # Rerunning the same scheduled slot must not give a node extra "successes".
        slot = now // 21600
        checks = [x for x in checks if x['t'] // 21600 != slot]
        record = {'t': now, 'ok': int(key in good)}
        if key in good:
            latency = good[key].get('latency', 0)
            if not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency < 0:
                raise ValueError('Invalid measured latency')
            record['ms'] = int(round(latency * 1000))
        checks.append(record)
        entry['checks'] = checks[-MAX_CHECKS:]
    # Trim stale nodes and prevent unbounded history even if source pools grow.
    for key in list(nodes):
        checks = nodes[key].get('checks', [])
        checks = [x for x in checks if now - SEVEN_DAYS < x.get('t', 0) <= now]
        if checks:
            nodes[key]['checks'] = checks[-MAX_CHECKS:]
        else:
            del nodes[key]
    if len(nodes) > MAX_NODES:
        ranked = sorted(nodes, key=lambda k: (nodes[k]['checks'][-1]['t'], score(nodes[k], now)), reverse=True)
        state['nodes'] = {key: nodes[key] for key in ranked[:MAX_NODES]}
    return state


def rank(results, state, now=None):
    now = int(time.time() if now is None else now)
    return sorted(results, key=lambda r: (-score(state['nodes'].get(identity(r['line']), {}), now),
                                          r['latency'], identity(r['line'])))


def save(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.health-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, separators=(',', ':'), sort_keys=True)
            f.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
