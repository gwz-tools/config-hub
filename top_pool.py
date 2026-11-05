"""TOP candidate selection from compact collection-presence history.

Do not interpret collection presence as verified VPN connectivity.
"""
import json
from pathlib import Path
from history_manager import QUALITY_FILE, fingerprint, read_lines

VALIDATED_FILE = Path('data/validated.txt')
OUTPUT_FILE = Path('data/top_pool.txt')
FAST_FILE = Path('fast.txt')
TOP_LIMIT = 50


def build_pool():
    if not QUALITY_FILE.exists():
        print('No compact history; retaining existing TOP pool')
        return False
    state = json.loads(QUALITY_FILE.read_text(encoding='utf-8'))
    if state.get('version') != 1 or not isinstance(state.get('records'), dict):
        raise RuntimeError('Compact history format invalid')
    records = state['records']
    eligible = {}
    for cfg in read_lines(VALIDATED_FILE):
        if not cfg.startswith('vless://'):
            continue
        identity = fingerprint(cfg)
        mask = records.get(identity, 0)
        if isinstance(mask, int) and (mask & 1):
            eligible.setdefault(identity, (mask.bit_count(), cfg))
    if len(eligible) < 5:
        print('Insufficient candidates; retaining TOP pool')
        return False

    # Preserve previously published candidates during a storage-only migration.
    # Actual tunnel quality ranking will be implemented separately.
    result = []
    selected = set()
    for cfg in read_lines(FAST_FILE):
        ident = fingerprint(cfg)
        if ident in eligible and ident not in selected:
            result.append(eligible[ident][1])
            selected.add(ident)
            if len(result) >= TOP_LIMIT:
                break
    for ident, (seen_count, cfg) in sorted(eligible.items(), key=lambda item: (-item[1][0], item[0])):
        if len(result) >= TOP_LIMIT:
            break
        if ident not in selected:
            result.append(cfg)
            selected.add(ident)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text('\n'.join(result) + '\n', encoding='utf-8')
    print('TOP pool:', len(result))
    return True


if __name__ == '__main__':
    build_pool()
