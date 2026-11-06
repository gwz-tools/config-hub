package ru.prostokvn.app

import java.net.URLDecoder
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.util.UUID

/** Never log the original URI: it contains the server UUID and may contain private credentials. */
data class VlessProfile(
    val server: String,
    val port: Int,
    val uuid: String,
    val name: String,
    val security: String,
    val sni: String,
    val fingerprint: String,
    val publicKey: String,
    val shortId: String,
    val flow: String,
    val transport: String,
    val path: String,
    val host: String,
    val serviceName: String
) {
    companion object {
        fun parse(link: String): VlessProfile {
            val trimmed = link.trim()
            require(trimmed.length in 25..4096) { "Некорректная длина профиля" }
            val uri = try { URI(trimmed) } catch (_: Exception) { throw IllegalArgumentException("Некорректная VLESS-ссылка") }
            require(uri.scheme.equals("vless", ignoreCase = true)) { "Нужна ссылка vless://" }
            require(uri.rawUserInfo != null && !uri.rawUserInfo.contains(':')) { "Не указан UUID VLESS" }
            val user = URLDecoder.decode(uri.rawUserInfo, "UTF-8")
            try { UUID.fromString(user) } catch (_: Exception) { throw IllegalArgumentException("Некорректный UUID") }
            val server = uri.host?.trim('[', ']')?.takeIf { it.isNotBlank() }
                ?: throw IllegalArgumentException("Не указан сервер")
            require(server.length <= 253 && !server.any { it.isWhitespace() }) { "Некорректный сервер" }
            require(uri.port in 1..65535) { "Не указан порт" }
            // java.net.URI keeps parsing testable without Android runtime stubs.
            val params = (uri.rawQuery ?: "").split("&").mapNotNull { field ->
                val key = field.substringBefore("=", "")
                if (key.isBlank()) null else {
                    try {
                        URLDecoder.decode(key, "UTF-8") to
                            URLDecoder.decode(field.substringAfter("=", ""), "UTF-8")
                    } catch (_: Exception) { null }
                }
            }.toMap()
            fun param(name: String, default: String = "") =
                (params[name] ?: default).trim()
            val security = param("security", "tls").lowercase()
            require(security == "tls" || security == "reality") { "Поддерживаются VLESS TLS и Reality" }
            val type = param("type", "tcp").lowercase()
            require(type in setOf("tcp", "ws", "grpc")) { "Тип транспорта $type пока не поддерживается" }
            val flow = param("flow")
            require(flow.isEmpty() || flow == "xtls-rprx-vision") { "Неизвестный VLESS flow" }
            require(flow.isEmpty() || type == "tcp") { "Vision требует TCP" }
            val pk = param("pbk")
            if (security == "reality") require(pk.length in 32..100) { "Не указан публичный ключ Reality (pbk)" }
            val sni = param("sni").ifBlank { server }
            require(sni.isNotEmpty() && sni.length <= 253 && !sni.any { it.isWhitespace() }) { "Некорректный SNI" }
            val fp = param("fp", "chrome")
            require(fp.isNotEmpty() && fp.length <= 32) { "Некорректный fingerprint" }
            val name = (uri.fragment ?: "").take(64).ifBlank { server }
            return VlessProfile(server, uri.port, user, name, security, sni, fp, pk,
                param("sid"), flow, type, param("path", "/"), param("host"), param("serviceName"))
        }
    }

    fun outbound(): JSONObject = JSONObject().apply {
        put("type", "vless")
        put("tag", "proxy")
        put("server", server)
        put("server_port", port)
        put("uuid", uuid)
        if (flow.isNotBlank()) put("flow", flow)
        put("tls", JSONObject().apply {
            put("enabled", true)
            put("server_name", sni)
            put("insecure", false)
            put("utls", JSONObject().put("enabled", true).put("fingerprint", fingerprint))
            if (security == "reality") put("reality", JSONObject().put("enabled", true)
                .put("public_key", publicKey).put("short_id", shortId))
        })
        when (transport) {
            "ws" -> put("transport", JSONObject().put("type", "ws").put("path", path).apply {
                if (host.isNotBlank()) put("headers", JSONObject().put("Host", host))
            })
            "grpc" -> put("transport", JSONObject().put("type", "grpc").put("service_name", serviceName))
        }
    }
}

/** A complete sing-box 1.14.x configuration. Split routing comes from the verified local policy snapshot. */
object VpnConfig {
    fun build(profile: VlessProfile, snapshot: PolicyStore.Snapshot, splitRouting: Boolean): String =
        buildWithOutbounds(JSONArray().put(profile.outbound()), snapshot, splitRouting)

    /**
     * sing-box URLTest performs real HTTP probes through each VLESS node, chooses
     * a working outbound, and reevaluates every 3 minutes. No simulated connection.
     * The same verified DIRECT/PROXY rules are used for manual and AUTO.
     */
    fun buildAuto(profiles: List<VlessProfile>, snapshot: PolicyStore.Snapshot, splitRouting: Boolean): String {
        require(profiles.isNotEmpty()) { "Нет VLESS-узлов для автоматического подключения" }
        val candidates = profiles.take(12)
        val outboundList = JSONArray()
        val tags = JSONArray()
        candidates.forEachIndexed { index, profile ->
            val tag = "node-${index + 1}"
            tags.put(tag)
            outboundList.put(profile.outbound().put("tag", tag))
        }
        outboundList.put(JSONObject().put("type", "urltest").put("tag", "proxy")
            .put("outbounds", tags)
            .put("url", "https://www.gstatic.com/generate_204")
            .put("interval", "3m")
            .put("tolerance", 50)
            .put("idle_timeout", "30m")
            .put("interrupt_exist_connections", true))
        return buildWithOutbounds(outboundList, snapshot, splitRouting)
    }

    /** One-shot Android TUN test. DIRECT is unencrypted; normal AUTO is untouched. */
    fun buildDirectDiagnostic(snapshot: PolicyStore.Snapshot): String =
        buildWithOutbounds(JSONArray(), snapshot, false, diagnosticDirect = true)

    private fun buildWithOutbounds(
        outboundList: JSONArray,
        snapshot: PolicyStore.Snapshot,
        splitRouting: Boolean,
        diagnosticDirect: Boolean = false
    ): String {
        fun list(file: String): JSONArray = JSONArray().apply {
            snapshot.directory.resolve(file).useLines { lines ->
                lines.map(String::trim).filter { it.isNotEmpty() && !it.startsWith('#') }.forEach { put(it) }
            }
        }
        val rules = JSONArray()
        // Capture DNS before domain rules so DNS cannot accidentally escape the tunnel.
        rules.put(JSONObject().put("protocol", "dns").put("action", "hijack-dns"))
        if (splitRouting && !diagnosticDirect) {
            val blocks = list("block.txt")
            if (blocks.length() > 0) rules.put(JSONObject().put("domain_suffix", blocks).put("action", "reject"))
            val direct = list("direct.txt")
            if (direct.length() > 0) rules.put(JSONObject().put("domain_suffix", direct)
                .put("action", "route").put("outbound", "direct"))
            val proxy = list("proxy.txt")
            if (proxy.length() > 0) rules.put(JSONObject().put("domain_suffix", proxy)
                .put("action", "route").put("outbound", "proxy"))
        }
        val dnsRules = JSONArray()
        if (splitRouting && !diagnosticDirect) {
            val direct = list("direct.txt")
            if (direct.length() > 0) dnsRules.put(JSONObject().put("domain_suffix", direct).put("action", "route")
                .put("server", "local"))
        }
        return JSONObject().apply {
            put("log", JSONObject().put("level", "warn"))
            put("dns", JSONObject().put("servers", JSONArray()
                .put(JSONObject().put("tag", "remote").put("type", "udp")
                    .put("server", "1.1.1.1").apply {
                        if (!diagnosticDirect) put("detour", "proxy")
                    })
                .put(JSONObject().put("tag", "local").put("type", "udp")
                    .put("server", "77.88.8.8")))
                .put("rules", dnsRules)
                .put("final", if (diagnosticDirect) "local" else "remote")
                .put("strategy", "ipv4_only"))
            put("inbounds", JSONArray().put(JSONObject()
                .put("type", "tun").put("tag", "tun-in")
                .put("address", JSONArray().put("172.19.0.1/30").put("fdfe:dcba:9876::1/126"))
                .put("mtu", 1500).put("auto_route", true).put("strict_route", true)
                .put("dns_mode", "hijack").put("stack", "system")))
            val direct = JSONObject().put("type", "direct").put("tag", "direct")
            put("outbounds", if (diagnosticDirect) JSONArray().put(direct)
                 else outboundList.put(direct))
            put("route", JSONObject().put("auto_detect_interface", true)
                .put("rules", rules).put("default_domain_resolver", "local")
                .put("final", if (diagnosticDirect) "direct" else "proxy"))
        }.toString()
    }
}
