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
