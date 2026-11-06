package ru.prostokvn.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONArray
import java.io.ByteArrayOutputStream
import java.net.URL
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import java.security.KeyStore
import javax.net.ssl.HttpsURLConnection

/**
 * AUTO only consumes the public GWZHUB-verified branch and its independent cloud
 * checked fallback. fast.txt contains candidates, NOT verified nodes; do not use it.
 * Never put private subscriptions or client secrets in source or logs.
 */
object AutoPoolCatalog {
    fun parse(text: String, max: Int = 12): List<String> {
        val unique = linkedSetOf<String>()
        for (line in text.lineSequence()) {
            val link = line.trim().removePrefix("\uFEFF")
            if (!link.startsWith("vless://", ignoreCase = true) || link.length > 4096) continue
            if (runCatching { VlessProfile.parse(link) }.isFailure) continue
            if (unique.none { it.substringBefore('#') == link.substringBefore('#') }) unique.add(link)
            if (unique.size >= max) break
        }
        return unique.toList()
    }

    fun merge(sourceA: List<String>, sourceB: List<String>, max: Int = 12): List<String> =
        parse((sourceA + sourceB).joinToString("\n"), max)
}

class AutoPool(private val context: Context) {
    companion object {
        private const val UPDATE_INTERVAL = 6L * 60 * 60 * 1000
        private const val MAX_FILE_BYTES = 100_000
        private const val KEY_ALIAS = "kvn-auto-pool-v1"
        private const val KEY_PREF = "verified-vless-pool"
        // The primary feed is checked by the actual GWZHUB publisher. Its live
        // list may be small. Cloud is independent and is NOT Russian-ISP proof.
        private val sources = listOf(
            "https://raw.githubusercontent.com/gwz-tools/config-hub/verified/live-vless.txt",
            "https://raw.githubusercontent.com/gwz-tools/config-hub/main/cloud-vless.txt"
        )
    }

    private val prefs = context.getSharedPreferences("kvn_auto_pool", Context.MODE_PRIVATE)

    /** Uses last-known-good encrypted cache if the feed cannot be reached. */
    @Synchronized
    fun resolve(): List<VlessProfile> {
        val old = cachedLinks()
        val now = System.currentTimeMillis()
        val last = prefs.getLong("updated_at", 0)
        if (old.isNotEmpty() && last > 0 && now >= last && now - last < UPDATE_INTERVAL) {
            return old.mapNotNull { runCatching { VlessProfile.parse(it) }.getOrNull() }
        }
        val fresh = ArrayList<String>()
        for (source in sources) {
            val text = runCatching { download(source) }.getOrNull() ?: continue
            fresh.addAll(AutoPoolCatalog.parse(text))
        }
        val selected = AutoPoolCatalog.merge(fresh, old)
        if (fresh.isNotEmpty() && selected.isNotEmpty()) {
            // Persist a single AES-GCM encrypted blob, never the cleartext links.
            runCatching { save(selected, now) }
            return selected.mapNotNull { runCatching { VlessProfile.parse(it) }.getOrNull() }
        }
        if (old.isNotEmpty()) return old.mapNotNull { runCatching { VlessProfile.parse(it) }.getOrNull() }
        return emptyList()
    }

    fun cachedCount(): Int = cachedLinks().size

    private fun download(source: String): String {
        val url = URL(source)
        require(url.protocol == "https" && url.host == "raw.githubusercontent.com")
        val connection = (url.openConnection() as HttpsURLConnection).apply {
            instanceFollowRedirects = false
            connectTimeout = 5000
            readTimeout = 6000
            requestMethod = "GET"
            setRequestProperty("Accept", "text/plain")
        }
        try {
            require(connection.responseCode == 200) { "Источник временно недоступен" }
            val bytes = ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val buffer = ByteArray(4096)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    require(bytes.size() + read <= MAX_FILE_BYTES) { "Слишком большой список VLESS" }
                    bytes.write(buffer, 0, read)
                }
            }
            return bytes.toString("UTF-8")
        } finally {
            connection.disconnect()
        }
    }

    private fun secretKey(): SecretKey {
        val keystore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keystore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build())
        return generator.generateKey()
    }

    private fun cachedLinks(): List<String> {
        val encoded = prefs.getString(KEY_PREF, null) ?: return emptyList()
        return runCatching {
            val raw = Base64.decode(encoded, Base64.NO_WRAP)
            require(raw.size > 12 + 16)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, raw.copyOfRange(0, 12)))
            val text = cipher.doFinal(raw.copyOfRange(12, raw.size)).toString(Charsets.UTF_8)
            val array = JSONArray(text)
            val links = (0 until array.length()).map { array.getString(it) }
            AutoPoolCatalog.parse(links.joinToString("\n"))
        }.getOrDefault(emptyList())
    }

    private fun save(links: List<String>, now: Long) {
        val payload = JSONArray(links).toString().toByteArray(Charsets.UTF_8)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val data = cipher.iv + cipher.doFinal(payload)
        check(prefs.edit()
            .putString(KEY_PREF, Base64.encodeToString(data, Base64.NO_WRAP))
            .putLong("updated_at", now)
            .commit()) { "Не удалось сохранить проверенный пул" }
    }
}
