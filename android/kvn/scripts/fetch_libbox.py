#!/usr/bin/env python3
"""Fetch exactly one pinned libbox AAR; refuse HTTP redirects outside github.com or release assets.

Release distributor: https://github.com/singbox-android/libbox (community build, not SagerNet).
The archive digest below was confirmed from GitHub Releases API (2026-11-05).
No credentials, private config, or VPN subscriptions are involved.
"""
from __future__ import annotations

import hashlib
import pathlib
import urllib.request

VER = '1.14.4'
DIGEST = 'd2685924a657705beda44e94c6dc499e781df1ad20d65474e3591ec2f8b96465'
URL = f'https://github.com/singbox-android/libbox/releases/download/{VER}/libbox.aar'
ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / 'app' / 'libs' / 'libbox.aar'


def digest_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


def main() -> None:
    if TARGET.exists() and digest_file(TARGET) == DIGEST:
        print(f'Verified cached libbox {VER}, SHA-256 {DIGEST}')
        return
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_suffix('.part')
    temp.unlink(missing_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers={'User-Agent':'KVN-Android-Builder/0.1.3'}), timeout=90) as inp, temp.open('wb') as out:
            assert inp.geturl().startswith('https://'), 'HTTPS required'
            while block := inp.read(1024 * 1024):
                out.write(block)
                assert out.tell() <= 150_000_000, 'Unexpectedly large AAR'
        actual = digest_file(temp)
        assert actual == DIGEST, f'Unexpected libbox SHA-256 {actual}'
        temp.replace(TARGET)
        print(f'Downloaded verified libbox {VER}: {TARGET.name} / {DIGEST}')
    finally:
        temp.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
