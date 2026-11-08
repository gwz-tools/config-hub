package ru.prostokvn.app

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.IOException

class PolicyTests {
    @get:Rule val temporary = TemporaryFolder()
    private val assets get() = File(checkNotNull(System.getProperty("gwzhub.assets")))
    private data class Bundle(val manifest: JSONObject, val data: Map<String, ByteArray>) {
        val bytes get() = manifest.toString().toByteArray()
        val version get() = manifest.getString("version")
    }
    private fun bundle(direct: List<String> = listOf("example.ru"), proxy: List<String> = listOf("example.org")): Bundle {
        val data = mutableMapOf<String, ByteArray>()
        for ((action, rows) in mapOf("direct" to direct, "proxy" to proxy, "block" to emptyList())) {
            data["$action.txt"] = (rows.joinToString("\n") + if (rows.isEmpty()) "" else "\n").toByteArray()
            val rules = JSONArray()
            if (rows.isNotEmpty()) rules.put(JSONObject().put("domain_suffix", JSONArray(rows)))
            data["$action.rule-set.json"] = JSONObject().put("version", 3).put("rules", rules).toString().toByteArray()
        }
        return rehash(JSONObject().put("schema_version", 1).put("default_route", "PROXY"), data)
    }
    private fun rehash(manifest: JSONObject, data: Map<String, ByteArray>): Bundle {
        val files = JSONObject()
        for (name in PolicyValidator.files) {
            val bytes = data.getValue(name)
            files.put(name, JSONObject().put("bytes", bytes.size).put("sha256", PolicyValidator.sha256(bytes))
                .put("domains", if (name.endsWith(".txt")) bytes.toString(Charsets.UTF_8).lineSequence().count { it.isNotEmpty() } else JSONObject.NULL))
        }
        manifest.put("files", files)
        val canonical = PolicyValidator.files.sorted().joinToString(",", "{", "}") { name ->
            val meta = files.getJSONObject(name)
            "\"$name\":{\"bytes\":${meta.getInt("bytes")},\"domains\":${meta.get("domains")},\"sha256\":\"${meta.getString("sha256")}\"}"
        }
        manifest.put("version", PolicyValidator.sha256(canonical.toByteArray()).take(20))
        return Bundle(manifest, data)
    }
    private fun store() = PolicyStore(temporary.newFolder()) { File(assets, it).readBytes() }
    private fun reject(block: () -> Unit) { assertThrows(Exception::class.java) { block() } }

    @Test fun bundledPolicyPassesRealValidator() {
        val data = PolicyValidator.files.associateWith { File(assets, it).readBytes() }
        assertEquals("a208defbf0fa6881fce9", PolicyValidator.verify(JSONObject(File(assets, "manifest.json").readText()), data))
    }
    @Test fun firstStartWorksOffline() { assertEquals("a208defbf0fa6881fce9", store().ensureBundled()?.version) }
    @Test fun contentTamperingRejected() {
        val b = bundle(); val bad = b.data.toMutableMap(); bad["direct.txt"] = "tampered.ru\n".toByteArray()
        reject { PolicyValidator.verify(b.manifest, bad) }
    }
    @Test fun sameSizeTamperingRejected() {
        val b = bundle(); val bad = b.data.toMutableMap(); bad["direct.txt"] = "example.us\n".toByteArray()
        reject { PolicyValidator.verify(b.manifest, bad) }
    }
    @Test fun metadataTamperingRejected() {
        val b = bundle(); b.manifest.getJSONObject("files").getJSONObject("direct.txt").put("domains", 999)
        reject { PolicyValidator.verify(b.manifest, b.data) }
    }
    @Test fun missingAssetRejected() { val b = bundle(); reject { PolicyValidator.verify(b.manifest, b.data - "proxy.txt") } }
    @Test fun wrongVersionRejected() { val b = bundle(); b.manifest.put("version", "00000000000000000000"); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun wrongDefaultRejected() { val b = bundle(); b.manifest.put("default_route", "DIRECT"); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun exactConflictRejected() { val b = bundle(proxy = listOf("example.ru")); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun suffixConflictRejected() { val b = bundle(proxy = listOf("sub.example.ru")); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun reverseSuffixConflictRejected() { val b = bundle(direct = listOf("sub.example.org")); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun unsortedDomainsRejected() { val b = bundle(direct = listOf("z.ru", "a.ru")); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun duplicateDomainsRejected() { val b = bundle(direct = listOf("a.ru", "a.ru")); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun invalidDomainRejected() { val b = bundle(direct = listOf("bad..ru")); reject { PolicyValidator.verify(b.manifest, b.data) } }
    @Test fun unexpectedRuleFieldsRejectedEvenWithValidHash() {
        val b = bundle(); val data = b.data.toMutableMap()
        val rs = JSONObject(data.getValue("direct.rule-set.json").toString(Charsets.UTF_8))
        rs.getJSONArray("rules").getJSONObject(0).put("ip_cidr", JSONArray().put("0.0.0.0/0"))
        data["direct.rule-set.json"] = rs.toString().toByteArray()
        val changed = rehash(b.manifest, data); reject { PolicyValidator.verify(changed.manifest, changed.data) }
    }
    @Test fun txtJsonMismatchRejectedEvenWithValidHash() {
        val b = bundle(); val data = b.data.toMutableMap()
        data["direct.rule-set.json"] = """{"version":3,"rules":[{"domain_suffix":["other.ru"]}]}""".toByteArray()
        val changed = rehash(b.manifest, data); reject { PolicyValidator.verify(changed.manifest, changed.data) }
    }
    @Test fun failedActivationPreservesCurrent() {
        val s = store(); val first = s.ensureBundled()!!; val b = bundle()
        reject { s.activate(b.bytes, b.data - "proxy.txt") }; assertEquals(first.version, s.current()?.version)
    }
    @Test fun corruptActiveRollsBackAcrossNewStoreInstance() {
        val root = temporary.newFolder(); val loader = { name: String -> File(assets, name).readBytes() }
        val s = PolicyStore(root, loader); val first = s.ensureBundled()!!; val b = bundle()
        s.activate(b.bytes, b.data); File(s.current()!!.directory, "direct.txt").writeText("broken")
        assertEquals(first.version, PolicyStore(root, loader).current()?.version)
        assertEquals(first.version, JSONObject(File(root, "active.json").readText()).getString("version"))
    }
    @Test fun corruptPointerRollsBack() {
        val root = temporary.newFolder(); val s = PolicyStore(root) { File(assets, it).readBytes() }
        val first = s.ensureBundled()!!; val b = bundle(); s.activate(b.bytes, b.data)
        File(root, "active.json").writeText("broken"); assertEquals(first.version, s.current()?.version)
    }
    @Test fun damagedBundledVersionCanBeReinstalled() {
        val s = store(); val active = s.ensureBundled()!!
        File(active.directory, "direct.txt").writeText("broken")
        assertEquals(active.version, s.ensureBundled()?.version)
    }
    @Test fun partialStagingIsNeverActivated() {
        val root = temporary.newFolder(); val s = PolicyStore(root) { File(assets, it).readBytes() }
        val first = s.ensureBundled()!!
        File(root, "versions/.pending-deadbeef").mkdirs()
        assertEquals(first.version, s.current()?.version)
    }
    @Test fun validatedBundleDownloadsAndActivatesAllSixFiles() {
        val s = store(); val b = bundle(); val names = mutableListOf<String>()
        val updater = PolicyUpdater(s) { name, _, _ -> names.add(name); PolicyNetwork.Fetch(200, if (name == "manifest.json") b.bytes else b.data.getValue(name), "tag") }
        val outcome = updater.refresh(null, null)
        assertEquals(b.version, outcome.version); assertEquals(b.version, s.current()?.version)
        assertEquals(7, names.size)
    }
    @Test fun http304OnlyUsesEtagBoundToVerifiedVersion() {
        val s = store(); val current = s.ensureBundled()!!
        val updater = PolicyUpdater(s) { name, etag, limit ->
            assertEquals("manifest.json", name); assertEquals("cached", etag); assertEquals(65536, limit)
            PolicyNetwork.Fetch(304, byteArrayOf(), etag)
        }
        assertEquals(current.version, updater.refresh("cached", current.version).version)
    }
    @Test fun unsolicited304Rejected() {
        val updater = PolicyUpdater(store()) { _, etag, _ -> assertNull(etag); PolicyNetwork.Fetch(304, byteArrayOf(), null) }
        reject { updater.refresh("stale", "unrelated-version") }
    }
    @Test fun rollbackInvalidatesEtagForDamagedVersion() {
        val s = store(); val old = s.ensureBundled()!!; val b = bundle(); s.activate(b.bytes, b.data)
        File(s.current()!!.directory, "direct.txt").writeText("broken")
        val updater = PolicyUpdater(s) { _, etag, _ -> assertNull(etag); throw IOException("offline") }
        reject { updater.refresh("tag-for-broken", b.version) }; assertEquals(old.version, s.current()?.version)
    }
    @Test fun interruptedDownloadKeepsOldVersion() {
        val s = store(); val old = s.ensureBundled()!!; val b = bundle()
        val updater = PolicyUpdater(s) { name, _, _ ->
            if (name == "proxy.txt") throw IOException("offline")
            PolicyNetwork.Fetch(200, if (name == "manifest.json") b.bytes else b.data.getValue(name), null)
        }
        reject { updater.refresh(null, null) }; assertEquals(old.version, s.current()?.version)
    }
    @Test fun invalidSameVersionManifestRejected() {
        val s = store(); val old = s.ensureBundled()!!
        val manifest = JSONObject(old.manifest.toString()).put("default_route", "DIRECT")
        val updater = PolicyUpdater(s) { _, _, _ -> PolicyNetwork.Fetch(200, manifest.toString().toByteArray(), "bad") }
        reject { updater.refresh(null, null) }; assertEquals(old.version, s.current()?.version)
    }
    @Test fun unchangedValidatedVersionDoesNotDownloadAssets() {
        val s = store(); val old = s.ensureBundled()!!; var calls = 0
        val updater = PolicyUpdater(s) { name, _, _ -> calls++; assertEquals("manifest.json", name); PolicyNetwork.Fetch(200, old.manifest.toString().toByteArray(), "fresh") }
        assertEquals("fresh", updater.refresh(null, null).etag); assertEquals(1, calls)
    }
    @Test fun sixHourBoundaryAndClockRollback() {
        val start = 1000L
        assertTrue(RefreshPolicy.isDue(0, start))
        assertFalse(RefreshPolicy.isDue(start, start + RefreshPolicy.intervalMillis - 1))
        assertTrue(RefreshPolicy.isDue(start, start + RefreshPolicy.intervalMillis))
        assertTrue(RefreshPolicy.isDue(start, start - 1))
    }
}
