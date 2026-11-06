# Android APK signing: one-time setup for in-place updates

Current GitHub Actions builds produce a **different ephemeral debug signing certificate on every CI runner**. Android requires the exact same signing identity to update an installed APK, regardless of increasing `versionCode`. This explains installation failures between KVN 0.1.6, 0.1.7, 0.1.8 and 0.1.9 test builds.

## Required GitHub repository secrets

Open **GitHub > gwz-tools/config-hub > Settings > Secrets and variables > Actions > New repository secret** and configure exactly these two secrets:

- `KVN_SIGNING_KEYSTORE_BASE64`: base64 of the **binary PKCS#12 keystore** with a private key under alias `kvn` (one uninterrupted line).
- `KVN_SIGNING_PASSWORD`: password for both the PKCS#12 store and the key, set equal.

Create the PKCS#12 keystore **once** and keep an offline backup; do not generate a new one for each build. The GitHub workflow will base64-decode it into a temporary private runner file, sign each ABI APK with Android SDK `apksigner`, verify signatures and record SHA-256 checksums. Neither secret, the decoded keystore, nor private keys are uploaded as artifacts or committed.

If both secrets are set, the workflow publishes an artifact named **`kvn-android-stable-<run number>`**, containing four ABI-specific `*-stable.apk` files. If neither is set, CI publishes **`kvn-android-debug-<run number>`** with a warning that subsequent updates will require uninstall. If just one secret is set, CI fails intentionally to prevent silently distributing incorrectly signed builds.

If generating your own key using local JDK 17:

```powershell
keytool -genkeypair -alias kvn -keyalg RSA -keysize 3072 -validity 7300 -storetype PKCS12 -keystore KVN-stable-signing-key.p12 -dname "CN=KVN Android, O=GWZ Tools"
[Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\KVN-stable-signing-key.p12")) | Set-Clipboard
```

Choose one strong password when keytool asks; the same password is used for both key and store in PKCS#12. Paste the clipboard into the first secret. Put the password into the second secret. The generated keystore file must remain private. The filename has no significance to the Android package.

## After the repository secrets are configured

Once both Actions secrets are present, trigger a **new** run of KVN Android CI on this feature branch. Old artifacts are immutable and stay debug-signed. The new run should publish `kvn-android-stable-N`; select `app-arm64-v8a-stable.apk` for a Samsung SM-S918B. Inspect the signing certificate digest (not the private key) in CI logs, and keep the same secret keystore for all future updates.

## Migration limitation

The currently installed 0.1.9-test debug APK (and earlier CI versions) **cannot** be upgraded in place to an APK using this new stable signing identity. Android will reject it for signature mismatch. There is no safe signing shortcut to avoid this. Before migrating, preserve any manual VLESS link externally: uninstalling deletes application data, including the Android Keystore key used to encrypt saved profiles.

**After one final uninstall** and installation of the **first stable-signed** APK, all subsequent APK updates signed with these same two secrets and a higher `versionCode` should install in place, retaining app data.

Never share the keystore, its base64 value, or the password in a public GitHub issue, PR, commit, Actions log or untrusted chat. Keep secure offline copies. If the signing key is lost, later APKs cannot be signed to update the installed app.

## Verification

After CI completes, download the `kvn-android-stable-N` artifact, choose `app-arm64-v8a-stable.apk` for a Samsung ARM64 phone, and compare the published `.sha256` file with the binary. To inspect the signing certificate (safe public metadata), run Android SDK `apksigner verify --verbose --print-certs app-arm64-v8a-stable.apk`. Cert SHA-256 should be identical across future stable APK versions.

This only fixes installation/update identity. It does **not** prove real Android VPN connectivity. Native DNS startup was patched in 0.1.9-test and still requires physical-device verification.
