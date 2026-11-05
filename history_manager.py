"""Bounded GWZHUB collection history (not a VPN liveness checker)."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CURRENT_FILE = Path('data/validated.txt')
LAST_GOOD = Path('history/last_good.txt')
PREVIOUS = Path('history/previous_validated.txt')
STATUS_FILE = Path('history/source_status.json')
QUALITY_FILE = Path('history/quality/compact.json')
SUCCESS_FILE = Path('history/recent_success.json')
WINDOW_SIZE = 10
WINDOW_MASK = (1 << WINDOW_SIZE) - 1
MAX_RECORDS = 20_000
MIN_VALID_RECORDS = 80
DROP_LIMIT = 0.5


def read_lines(path):
    if not path.exists():
        return []
    return [s.strip() for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def fingerprint(line):
    return hashlib.sha256(line.split('#', 1)[0].strip().encode('utf-8')).hexdigest()


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(content, encoding='utf-8')
    temporary.replace(path)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')


def load_object(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise RuntimeError(f'History file corrupt: {path}') from exc
    if not isinstance(value, dict):
        raise RuntimeError(f'History file invalid: {path}')
    return value


def advance_windows(current, previous):
    """One presence bit per accepted collection, at most 10 runs and 20k hashes."""
    seen = {fingerprint(s) for s in current if s.startswith('vless://')}
    new = {}
    for key in sorted(seen):
        if len(new) >= MAX_RECORDS:
            break
        old = previous.get(key, 0)
        old = old if isinstance(old, int) and 0 <= old <= WINDOW_MASK else 0
        new[key] = ((old << 1) | 1) & WINDOW_MASK
    if len(new) < MAX_RECORDS:
        stale = []
        for key, mask in previous.items():
            if key in seen or not isinstance(mask, int):
                continue
            shifted = (mask << 1) & WINDOW_MASK
            if shifted:
                stale.append((shifted, key))
        for mask, key in sorted(stale, reverse=True)[:MAX_RECORDS - len(new)]:
            new[key] = mask
    return new


def update_history():
    current = read_lines(CURRENT_FILE)
    previous = read_lines(LAST_GOOD)
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    status = {'time': now, 'current_count': len(current), 'previous_count': len(previous)}
    if len(current) < MIN_VALID_RECORDS or (previous and len(current) < len(previous) * DROP_LIMIT):
        status['decision'] = 'rejected_keep_previous'
        write_json(STATUS_FILE, status)
        print(json.dumps(status))
        return False

    state = load_object(QUALITY_FILE)
    if state and state.get('version') != 1:
        raise RuntimeError('Unsupported compact history format')
    prior = state.get('records', {})
    if not isinstance(prior, dict):
        raise RuntimeError('Invalid compact history records')
    records = advance_windows(current, prior)
    runs = load_object(SUCCESS_FILE)
    summary = runs.get('runs', [])
    if not isinstance(summary, list):
        raise RuntimeError('Invalid success history')
    summary = [x for x in summary if isinstance(x, dict)][-(WINDOW_SIZE - 1):]
    summary.append({'time': now, 'collected': len(current), 'tracked': len(records)})

    write_json(QUALITY_FILE, {'version': 1, 'window': WINDOW_SIZE, 'records': records})
    write_json(SUCCESS_FILE, {'version': 1, 'runs': summary})
    if previous:
        write_text(PREVIOUS, '\n'.join(previous) + '\n')
    write_text(LAST_GOOD, '\n'.join(current) + '\n')
    status['decision'] = 'dataset_updated' if previous else 'initial_dataset_saved'
    status['tracked_fingerprints'] = len(records)
    status['successful_runs_retained'] = len(summary)
    write_json(STATUS_FILE, status)
    print(json.dumps(status))
    return True


if __name__ == '__main__':
    if not update_history():
        raise SystemExit(1)
