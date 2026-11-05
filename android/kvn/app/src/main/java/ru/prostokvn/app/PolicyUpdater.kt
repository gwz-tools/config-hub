package ru.prostokvn.app

import org.json.JSONObject

/** Testable update transaction; caller persists ETag/time only after success. */
class PolicyUpdater(
    private val store: PolicyStore,
    private val fetch: (String, String?, Int) -> PolicyNetwork.Fetch = { name, etag, limit ->
        PolicyNetwork.fetch(name, etag, limit)
    }
) {
    data class Outcome(val version: String, val etag: String?)

    fun refresh(savedEtag: String?, savedVersion: String?): Outcome {
        val current = store.ensureBundled()
        val etag = if (current != null && savedVersion == current.version) savedEtag else null
        val response = fetch("manifest.json", etag, 64 * 1024)
        if (response.code == 304) {
            require(current != null && etag != null) { "unexpected HTTP 304" }
            return Outcome(current.version, etag)
        }
        require(response.code == 200)
        require(response.bytes.size <= 64 * 1024)
        val manifest = JSONObject(response.bytes.toString(Charsets.UTF_8))
        val version = PolicyValidator.version(manifest)
        if (current?.version != version) {
            val data = store.files.associateWith {
                val asset = fetch(it, null, 2_000_000)
                require(asset.code == 200)
                asset.bytes
            }
            store.activate(response.bytes, data)
        }
        return Outcome(version, response.etag)
    }
}
