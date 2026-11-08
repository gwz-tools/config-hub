package ru.prostokvn.app

import org.json.JSONArray
import org.json.JSONObject

/** Xray TUN configuration using KVN encrypted profiles, verified feeds and policy. */
object XrayConfig {
    fun build(profile: VlessProfile?, snapshot: PolicyStore.Snapshot,
              splitRouting: Boolean, directDiagnostic: Boolean = false): String {
        require(directDiagnostic || profile != null) { "Не выбран VLESS-профиль" }
        val inbound = JSONObject().put("tag", "tun").put("protocol", "tun")
            .put("settings", JSONObject().put("name", "xray0").put("MTU", 1500))
            .put("sniffing", JSONObject().put("enabled", true)
                .put("routeOnly", true)
                .put("destOverride", JSONArray(listOf("http", "tls", "quic"))))

        val outbounds = JSONArray()
        if (!directDiagnostic) outbounds.put(requireNotNull(profile).xrayOutbound())
        outbounds.put(JSONObject().put("tag", "direct").put("protocol", "freedom"))
        outbounds.put(JSONObject().put("tag", "block").put("protocol", "blackhole"))
        outbounds.put(JSONObject().put("tag", "dns-out").put("protocol", "dns")
            .put("settings", JSONObject()))

        val route = JSONArray()
        fun field(outbound: String, key: String, values: JSONArray) {
            if (values.length() == 0) return
            route.put(JSONObject().put("type", "field").put(key, values)
                .put("outboundTag", outbound))
        }
        route.put(JSONObject().put("type", "field")
            .put("inboundTag", JSONArray().put("tun"))
            .put("port", "53").put("outboundTag", "dns-out"))
        field("direct", "ip", JSONArray(listOf(
            "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
            "169.254.0.0/16", "127.0.0.0/8", "fc00::/7", "fe80::/10"
        )))
        if (splitRouting && !directDiagnostic) {
            field("block", "domain", domains(snapshot, "block.txt"))
            field("direct", "domain", domains(snapshot, "direct.txt"))
            field("proxy", "domain", domains(snapshot, "proxy.txt"))
        }
        // Explicit last catch-all: no accidental cleartext fallback in proxy mode.
        route.put(JSONObject().put("type", "field")
            .put("network", "tcp,udp")
            .put("outboundTag", if (directDiagnostic) "direct" else "proxy"))

        val dns = JSONObject().put("queryStrategy", "UseIPv4")
            .put("hosts", JSONObject()
                .put("cloudflare-dns.com", "1.1.1.1")
                .put("dns.google", "8.8.8.8"))
            .put("servers", JSONArray()
                .put("https://cloudflare-dns.com/dns-query")
                .put("https://dns.google/dns-query")
                .put("localhost"))
        return JSONObject().put("log", JSONObject().put("loglevel", "warning"))
            .put("inbounds", JSONArray().put(inbound))
            .put("outbounds", outbounds)
            .put("routing", JSONObject().put("domainStrategy", "AsIs").put("rules", route))
            .put("dns", dns).put("stats", JSONObject()).toString()
    }

    private fun domains(snapshot: PolicyStore.Snapshot, file: String): JSONArray =
        JSONArray().apply {
            snapshot.directory.resolve(file).useLines { lines ->
                lines.map(String::trim)
                    .filter { it.isNotEmpty() && !it.startsWith("#") }
                    .forEach { put("domain:" + it) }
            }
        }

    private fun VlessProfile.xrayOutbound(): JSONObject {
        val user = JSONObject().put("id", uuid).put("encryption", "none")
        if (flow.isNotBlank()) user.put("flow", flow)
        val stream = JSONObject().put("network", transport).put("security", security)
        if (security == "reality") {
            stream.put("realitySettings", JSONObject()
                .put("show", false).put("serverName", sni)
                .put("fingerprint", fingerprint).put("publicKey", publicKey)
                .put("shortId", shortId).put("spiderX", "/"))
        } else {
            stream.put("tlsSettings", JSONObject().put("allowInsecure", false)
                .put("serverName", sni).put("fingerprint", fingerprint))
        }
        when (transport) {
            "ws" -> stream.put("wsSettings", JSONObject().put("path", path).apply {
                if (host.isNotBlank()) put("headers", JSONObject().put("Host", host))
            })
            "grpc" -> stream.put("grpcSettings", JSONObject().put("serviceName", serviceName))
        }
        return JSONObject().put("tag", "proxy").put("protocol", "vless")
            .put("settings", JSONObject().put("vnext", JSONArray()
                .put(JSONObject().put("address", server).put("port", port)
                    .put("users", JSONArray().put(user)))))
            .put("streamSettings", stream)
    }
}
