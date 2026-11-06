## 0.1.9-test — native DNS initialization fix (device verification pending)

- Fix confirmed libbox startup failure `start dns-transport: start dns/udp[local]: detour to an empty direct outbound makes no sense`: remove the `detour: direct` field only from the local UDP DNS server, retaining the proxy DNS detour, DIRECT/PROXY routing and AUTO pool.
- Add Kotlin regression test for AUTO and manual modes to ensure local DNS never references empty direct outbound.
- Add GitHub Actions native engine **runtime smoke test**: generate authentic VPN config in Kotlin, substitute only Android TUN with localhost mixed inbound on CI, and require sing-box 1.14.4 to stay running for eight seconds (config `check` alone missed the runtime failure).
- Signing continuity, VPN traffic and real-device behaviour remain unverified. Keep PR draft until confirmed.

## 0.1.8-test — actionable libbox startup diagnostics (device test required)

- In the Android 17 user log from 2026-11-06 11:18–11:19, libbox no longer aborts; five attempts fail with Go class `proxyerror` returned by `CommandServer.startOrReloadService`.
- The current app redacted **the whole native error message**, preventing root cause identification. New test build shows `Throwable.message` on the main page and in local logcat, retains it in private app diagnostics, and marks when `openTun` is called.
- Tapping VPN in AUTO and manual mode should now reveal the actual engine error (e.g. TUN, route, DNS, platform interface) instead of a generic failure.
- An APK with a new GitHub runner's debug signing key still cannot update an earlier build; stable secret-backed signing remains a separate release blocker.
- Not verified to pass VPN traffic yet. PR is DRAFT.

## 0.1.7-test — root-cause fix for native SIGABRT (device test pending)

- Diagnosed Samsung Android 17 native Go panic in user-provided logcat: `netip.ParsePrefix("fe80::...%rmnet_data0/64")` refuses IPv6 zone IDs.
- Fixed Android `KvnVpnService.getInterfaces()`: reconstruct IP from raw bytes via `NetworkPrefixFormatter` before adding network prefix, following upstream sing-box-for-android conversion.
- Added regression unit tests for scoped IPv6, IPv4, IPv6 and prefix bounds.
- Does not disable IPv6. No changes to public VLESS feed or DIRECT/PROXY routing.
- CI builds an APK but physical device must still confirm connection and traffic; don't merge PR until then.

## 0.1.6-test — Android runtime and profile stability (device confirmation pending)

- Enable upstream sing-box `fixAndroidStack` workaround on Android 9+ (SFA client reference).
- Save encrypted VLESS profile and AUTO/manual flags synchronously before attempting native startup, guarding against loss if Go runtime terminates.
- Show explicit personal-profile-saved message rather than confusing empty input, and last redacted startup stage in Settings.
- **Investigate Samsung Secure Folder**: VPN launched inside a Knox container may be restricted; verify the same APK outside Secure Folder before reporting a VPN failure as a library defect.
- Google Play/release signing is NOT configured. Each GitHub ephemeral runner has a different default debug certificate; CI debug APKs do NOT update previously installed versions in place. Need a secure, persistent signing keystore for future updates.
- CI success validates build/native JSON, not actual Android/Knox/ISP connectivity.

## 0.1.5-test — startup diagnostics / launcher repair (device verification pending)

- Catch Android service launch exceptions instead of terminating the activity immediately.
- Persist only redacted VPN startup stages and error types, even across process termination.
- Render prior incomplete startup stage on the home screen after reopening; do not claim connected on error.
- Restore white internal elements of the launcher mark without reinstating external white square.
- Validate actual Kotlin-generated AUTO VLESS config against official checksum-pinned sing-box 1.14.4 CLI during CI.
- Debug signing and actual Android 17 device traffic are not CI-proven; do not distribute as a verified VPN yet.

## 0.1.4-test — AUTO GWZHUB (device check pending)

- Default one-button start from verified/live-vless.txt with independent cloud-vless.txt fallback; no pasted link required.
- Encrypted last-known-good feed cache; refresh at connect if older than six hours.
- sing-box URLTest probes individual VLESS nodes over HTTPS every three minutes and switches outbound when needed.
- Manual VLESS is optional in Settings; fixes blank SNI fallback.
- Preserves DIRECT/PROXY split routing, updates, Android package ID and native engine.
- Note: Android CI is not proof of successful VPN traffic on a real Russian mobile provider; device testing is required.

# КВН — изменения

## 0.1.3-test (versionCode 4) — исходники, сборка НЕ подтверждена
- Главный экран упрощён: широкий логотип, одна большая кнопка VPN и состояние.
- Диагностика правил и проверка APK перенесены в «Настройки».
- Новый ввод VLESS-ссылок; TLS/Reality, TCP/Vision, WebSocket, gRPC.
- Профиль шифруется AES-256-GCM с Android Keystore; секретов в репозитории нет.
- Добавлен VpnService с libbox и проверка системного разрешения пользователя.
- Правила DIRECT/PROXY берутся из существующего проверенного локального набора.
- Нативный core 1.14.4 фиксируется по SHA-256 для воспроизводимости.
- Зафиксированы открытая лицензия движка и уведомление о сторонней сборке.
- Сохранён applicationId ru.prostokvn.app для совместимости с установленными тестами.

## 0.1.2-test (versionCode 3)
- Красно-белая тема, горизонтальный баннер, адаптивная иконка.
- Обновления, кеш и откат правил сохранены. VPN-движка не было.

## 0.1.1-test (versionCode 2)
- Первая подтверждённая Gradle APK, 38 JVM тестов, SHA-256, кеш и откат.
