package ru.prostokvn.app

import org.json.JSONObject
import java.security.MessageDigest

/** Pure validation: no network, Android services or writes. */
object PolicyValidator {
    val files = listOf("direct.txt", "proxy.txt", "block.txt", "direct.rule-set.json", "proxy.rule-set.json", "block.rule-set.json")
    private val domainPattern = Regex("^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$")

    fun version(manifest: JSONObject): String {
        require(manifest.getInt("schema_version") == 1) { "unsupported schema" }
        require(manifest.getString("default_route") == "PROXY") { "invalid default route" }
        val version = manifest.getString("version")
        require(Regex("^[a-f0-9]{20}$").matches(version)) { "invalid version" }
        val declared = manifest.getJSONObject("files")
        require(declared.keys().asSequence().toSet() == files.toSet()) { "unexpected file list" }
        val fields = files.sorted().joinToString(",", "{", "}") { name ->
            val meta = declared.getJSONObject(name)
            val size = meta.getInt("bytes")
            require(size in 0..2_000_000) { "invalid file size" }
            val hash = meta.getString("sha256")
            require(Regex("^[a-f0-9]{64}$").matches(hash)) { "invalid SHA256" }
            val domains = if (meta.isNull("domains")) "null" else meta.getInt("domains").also {
                require(it >= 0) { "invalid domain count" }
            }.toString()
            "\"$name\":{\"bytes\":$size,\"domains\":$domains,\"sha256\":\"$hash\"}"
        }
        require(sha256(fields.toByteArray(Charsets.UTF_8)).take(20) == version) { "manifest version mismatch" }
        return version
    }

    fun verify(manifest: JSONObject, data: Map<String, ByteArray>): String {
        val version = version(manifest)
        require(data.keys == files.toSet()) { "incomplete bundle" }
        val declared = manifest.getJSONObject("files")
        for ((name, bytes) in data) {
            val meta = declared.getJSONObject(name)
            require(bytes.size == meta.getInt("bytes")) { "file size mismatch: $name" }
            require(sha256(bytes) == meta.getString("sha256")) { "SHA256 mismatch: $name" }
        }
        val domains = listOf("direct", "proxy", "block").associateWith { action ->
            val rows = data.getValue("$action.txt").toString(Charsets.UTF_8)
                .lineSequence().filter { it.isNotEmpty() }.toList()
            require(rows == rows.distinct().sorted()) { "unsorted or duplicate domains" }
            require(rows.all { domainPattern.matches(it) }) { "invalid domain" }
            require(declared.getJSONObject("$action.txt").getInt("domains") == rows.size) { "domain count mismatch" }
            val ruleset = JSONObject(data.getValue("$action.rule-set.json").toString(Charsets.UTF_8))
            require(ruleset.keys().asSequence().toSet() == setOf("version", "rules")) { "unexpected ruleset fields" }
            require(ruleset.getInt("version") == 3) { "unsupported ruleset" }
            val rules = ruleset.getJSONArray("rules")
            if (rows.isEmpty()) require(rules.length() == 0) else {
                require(rules.length() == 1)
                val rule = rules.getJSONObject(0)
                require(rule.keys().asSequence().toSet() == setOf("domain_suffix")) { "unexpected rule fields" }
                val suffixes = rule.getJSONArray("domain_suffix")
                require((0 until suffixes.length()).map { suffixes.getString(it) } == rows) { "TXT/JSON mismatch" }
            }
            rows
        }
        val direct = domains.getValue("direct").toHashSet()
        val proxy = domains.getValue("proxy").toHashSet()
        fun overlaps(value: String, other: Set<String>): Boolean {
            var suffix = value
            while (true) {
                if (suffix in other) return true
                val dot = suffix.indexOf('.')
                if (dot < 0) return false
                suffix = suffix.substring(dot + 1)
            }
        }
        require(direct.none { overlaps(it, proxy) } && proxy.none { overlaps(it, direct) }) { "DIRECT/PROXY conflict" }
        return version
    }

    fun sha256(value: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(value).joinToString("") { "%02x".format(it) }
}
