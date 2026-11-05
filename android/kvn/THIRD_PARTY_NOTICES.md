# Third-party notices / Сторонние компоненты

Native VPN engine: sing-box `v1.14.4`, original project https://github.com/SagerNet/sing-box .
Copyright Project S / SagerNet contributors. Licensed under GNU GPL-3.0-or-later.

Binary distribution for prototype: `singbox-android/libbox` release `1.14.4`
https://github.com/singbox-android/libbox/releases/tag/1.14.4
SHA-256: `d2685924a657705beda44e94c6dc499e781df1ad20d65474e3591ec2f8b96465`.
This community build is **not** published by the original sing-box maintainers; the pinned
SHA-256 detects artifact changes but is not a substitute for an independently reproducible
build, source audit, or verified publisher chain. For production, build libbox from the official
sing-box pinned source and independently review source and binary.

The Android KVN app links the GPL sing-box engine. Accordingly, distribute the
combined application under a GPL-3.0-compatible license and provide complete corresponding
source and license/attribution. The full GNU GPL v3 text is included in `LICENSE-GPL-3.0`.

Do not publish user VPN credentials, subscription tokens, private keys or signing keys.
