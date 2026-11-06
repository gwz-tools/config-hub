package ru.prostokvn.app

import java.net.HttpURLConnection
import java.net.URL

/** HTTPS-only feed; redirects disallowed; host+repository+branch are fixed. */
object PolicyNetwork {
    const val BASE = "https://raw.githubusercontent.com/gwz-tools/config-hub/routing-feed/"
    const val MANIFEST = "${BASE}manifest.json"
    private const val MAX_ASSET = 2_000_000

    data class Fetch(val code: Int, val bytes: ByteArray, val etag: String?)

    fun fetch(name: String, etag: String? = null, limit: Int = MAX_ASSET): Fetch {
        require(name == "manifest.json" || name in listOf(
            "direct.txt", "proxy.txt", "block.txt", "direct.rule-set.json",
            "proxy.rule-set.json", "block.rule-set.json"))
        val connection = URL(BASE + name).openConnection() as HttpURLConnection
        connection.connectTimeout = 8_000
        connection.readTimeout = 8_000
        connection.instanceFollowRedirects = false
        connection.setRequestProperty("Accept", "application/json,text/plain;q=0.8")
        if (etag != null) connection.setRequestProperty("If-None-Match", etag)
        return try {
            val code = connection.responseCode
            if (code == HttpURLConnection.HTTP_NOT_MODIFIED) {
                require(etag != null) { "unexpected HTTP 304" }
                Fetch(code, ByteArray(0), etag)
            }
            else {
                require(code == HttpURLConnection.HTTP_OK) { "HTTP $code" }
                val buffer = connection.inputStream.use { stream ->
                    val out = java.io.ByteArrayOutputStream()
                    val chunk = ByteArray(8192)
                    while (true) {
                        val n = stream.read(chunk)
                        if (n < 0) break
                        require(out.size() + n <= limit) { "oversized routing file" }
                        out.write(chunk, 0, n)
                    }
                    out.toByteArray()
                }
                Fetch(code, buffer, connection.getHeaderField("ETag"))
            }
        } finally { connection.disconnect() }
    }
}
