# KVN Android Xray TUN prototype

Source observation: Mamin VPN 0.9.43 APK has the following structure:
- Original Java app says MIT in its APK notices.
- AndroidLibXrayLite 26.9.30, Xray-core, libgojni.so (per APK).
- TunnelConnection.open() establishes Android VpnService.Builder TUN
  with address 172.30.254.2/30 and DNS 172.30.254.1;
  passes the TUN file descriptor to CoreController.startLoop(config, fd).
- No separate tun2socks library was present in the supplied APK.

The experimental implementation in KVN uses the documented official
AndroidLibXrayLite API, with the upstream AAR pinned by SHA-256.
This is NOT a transplant of the patched custom Mamin binary.

Preserved:
- Package ru.prostokvn.app and existing KVN interface.
- Current KVN encrypted profile storage and manual VLESS import.
- KVN primary verified VLESS URL first, cloud fallback, old cache.
- KVN signed policy files direct/proxy/block.
- One-shot explicit DIRECT diagnostic, no encryption in that mode.
- Old sing-box service source retained for rollback in Git history.

Limitations until Samsung device verification:
- The first candidate from the verified KVN pool is chosen; this is not
  the previous sing-box URLTest which re-evaluated every three minutes.
- Native Xray start success is not the same as successful HTTPS delivery.
- The official upstream 26.9.30 library is not byte-identical to
  the patched Mamin VPN 0.9.43 libgojni.so.
- The four-ABI release retains old libbox until the Xray proof works.
- No personal/server credentials from Mamin are copied or exposed.
- LGPL and MPL attribution/relink compliance before public release.

Keep the PR draft until real phone traffic is confirmed.
