package ru.prostokvn.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class AutoPoolTests {
    @get:Rule val temporary = TemporaryFolder()
    private val id = "123e4567-e89b-12d3-a456-426614174000"

    private fun vless(server: String, sni: String = "example.com") =
        "vless://$id@$server:443?security=tls&type=tcp&sni=$sni#Test"

    @Test fun defaultAndEmptySniUseHostWithoutRejectingUrl() {
        assertEquals("example.com", VlessProfile.parse(vless("example.com", "")).sni)
        assertEquals("example.org", VlessProfile.parse(
            "vless://$id@example.org:443?type=tcp&security=tls").sni)
    }

    @Test fun autoPoolFiltersInvalidDeduplicatesAndCaps() {
        val source = listOf("# generated header", vless("example.com"),
            vless("example.com"), "https://not-a-vless.example/",
            vless("other.example.com"), "Количество: 0").joinToString("\n")
        val valid = AutoPoolCatalog.parse(source)
        assertEquals(2, valid.size)
        assertEquals(1, AutoPoolCatalog.parse(source, 1).size)
        assertEquals(2, AutoPoolCatalog.merge(valid, valid).size)
    }

    @Test fun autoUrltestContainsEveryNodeAndKeepsSplitRouting() {
        val directory = temporary.newFolder()
        File(directory, "block.txt").writeText("")
        File(directory, "direct.txt").writeText("example.ru\n")
        File(directory, "proxy.txt").writeText("example.org\n")
        val snapshot = PolicyStore.Snapshot("test", directory, JSONObject())
        val profiles = listOf(VlessProfile.parse(vless("one.example.com")),
            VlessProfile.parse(vless("two.example.com")))
        val config = JSONObject(VpnConfig.buildAuto(profiles, snapshot, true))
        val outs = config.getJSONArray("outbounds")
        assertEquals(4, outs.length())
        assertEquals("node-1", outs.getJSONObject(0).getString("tag"))
        assertEquals("node-2", outs.getJSONObject(1).getString("tag"))
        val auto = outs.getJSONObject(2)
        assertEquals("urltest", auto.getString("type"))
        assertEquals("proxy", auto.getString("tag"))
        assertEquals("3m", auto.getString("interval"))
        assertEquals(2, auto.getJSONArray("outbounds").length())
        assertEquals("proxy", config.getJSONObject("route").getString("final"))
        assertEquals("direct", config.getJSONObject("route").getJSONArray("rules")
            .getJSONObject(1).getString("outbound"))
    }

    @Test fun localDnsMustNotDetourThroughEmptyDirectOutbound() {
        val directory = temporary.newFolder()
        listOf("block", "direct", "proxy").forEach {
            File(directory, "${it}.txt").writeText(if (it == "direct") "example.ru\n" else "")
        }
        val snapshot = PolicyStore.Snapshot("test", directory, JSONObject())
        val profile = VlessProfile.parse(vless("one.example.com"))
        for (split in listOf(true, false)) {
            val configurations = listOf(
                JSONObject(VpnConfig.build(profile, snapshot, split)),
                JSONObject(VpnConfig.buildAuto(listOf(profile), snapshot, split))
            )
            for (config in configurations) {
                val servers = config.getJSONObject("dns").getJSONArray("servers")
                val local = (0 until servers.length())
                    .map { servers.getJSONObject(it) }
                    .single { it.getString("tag") == "local" }
                assertEquals("udp", local.getString("type"))
                assertEquals("77.88.8.8", local.getString("server"))
                assertFalse("LOCAL DNS must use its default direct dialer, not detour to empty outbound",
                    local.has("detour"))
                val remote = (0 until servers.length())
                    .map { servers.getJSONObject(it) }
                    .single { it.getString("tag") == "remote" }
                assertEquals("proxy", remote.getString("detour"))
            }
        }
    }

    @Test fun exportActualAutoConfigForNativeSingBoxValidation() {
        val destination = System.getProperty("kvn.validation.json") ?: return
        val directory = temporary.newFolder()
        listOf("block", "direct", "proxy").forEach { action ->
            File(directory, "${action}.txt").writeText(if (action == "direct") "example.ru\n" else "")
        }
        val snapshot = PolicyStore.Snapshot("test", directory, JSONObject())
        val profile = VlessProfile.parse(vless("one.example.com"))
        val output = File(destination)
        output.parentFile?.mkdirs()
        output.writeText(VpnConfig.buildAuto(listOf(profile), snapshot, true))
        File(output.parentFile, "vpn-direct.json")
            .writeText(VpnConfig.buildDirectDiagnostic(snapshot))
        assertEquals("urltest", JSONObject(output.readText()).getJSONArray("outbounds")
            .getJSONObject(1).getString("type"))
    }

    @Test fun dnsLocalMustNotDetourThroughEmptyDirectOutbound() {
        val directory = temporary.newFolder()
        listOf("block", "direct", "proxy").forEach {
            File(directory, "${it}.txt").writeText("")
        }
        val snapshot = PolicyStore.Snapshot("test", directory, JSONObject())
        val p = VlessProfile.parse(vless("test.example.com"))
        // Test both AUTO and manual paths: same DNS generator must be safe.
        val variants = listOf(
            VpnConfig.buildAuto(listOf(p), snapshot, true),
            VpnConfig.build(p, snapshot, false)
        )
        for (configText in variants) {
            val config = JSONObject(configText)
            val dns = config.getJSONObject("dns").getJSONArray("servers")
            val local = dns.getJSONObject(1)
            assertEquals("local", local.getString("tag"))
            assertEquals("udp", local.getString("type"))
            assertFalse("Local DNS cannot detour via empty direct outbound",
                local.has("detour"))
            assertEquals("proxy", dns.getJSONObject(0).getString("detour"))
            val outbounds = config.getJSONArray("outbounds")
            val direct = outbounds.getJSONObject(outbounds.length() - 1)
            assertEquals("direct", direct.getString("type"))
            assertFalse(direct.has("bind_interface"))
        }
    }

    @Test fun oneShotDirectDiagnosticHasNoProxyAndPreservesDnsHijack() {
        val directory = temporary.newFolder()
        listOf("block", "direct", "proxy").forEach {
            File(directory, "${it}.txt").writeText("")
        }
        val snapshot = PolicyStore.Snapshot("test", directory, JSONObject())
        val config = JSONObject(VpnConfig.buildDirectDiagnostic(snapshot))
        val outbound = config.getJSONArray("outbounds")
        assertEquals(1, outbound.length())
        assertEquals("direct", outbound.getJSONObject(0).getString("tag"))
        assertEquals("direct", config.getJSONObject("route").getString("final"))
        val dns = config.getJSONObject("dns")
        assertEquals("local", dns.getString("final"))
        val servers = dns.getJSONArray("servers")
        for (i in 0 until servers.length()) {
            assertFalse(servers.getJSONObject(i).has("detour"))
        }
        assertEquals("hijack-dns", config.getJSONObject("route")
            .getJSONArray("rules").getJSONObject(0).getString("action"))
        assertEquals("tun", config.getJSONArray("inbounds").getJSONObject(0).getString("type"))
    }

    @Test fun allModesUseUserspaceGvisorTunStack() {
        val directory = temporary.newFolder()
        listOf("block", "direct", "proxy").forEach { File(directory, "${it}.txt").writeText("") }
        val snapshot = PolicyStore.Snapshot("test", directory, JSONObject())
        val profile = VlessProfile.parse(vless("one.example.com"))
        val all = listOf(
            VpnConfig.buildAuto(listOf(profile), snapshot, true),
            VpnConfig.build(profile, snapshot, false),
            VpnConfig.buildDirectDiagnostic(snapshot)
        )
        for (json in all) {
            val tun = JSONObject(json).getJSONArray("inbounds").getJSONObject(0)
            assertEquals("gvisor", tun.getString("stack"))
            assertTrue(tun.getBoolean("auto_route"))
            assertEquals("hijack", tun.getString("dns_mode"))
        }
    }

    @Test fun manualOutboundDoesNotUseUrltest() {
        val directory = temporary.newFolder()
        listOf("block", "direct", "proxy").forEach { File(directory, "$it.txt").writeText("") }
        val snapshot = PolicyStore.Snapshot("test", directory, JSONObject())
        val config = JSONObject(VpnConfig.build(VlessProfile.parse(vless("one.example.com")),
            snapshot, false))
        val outbounds = config.getJSONArray("outbounds")
        assertEquals(2, outbounds.length())
        assertEquals("vless", outbounds.getJSONObject(0).getString("type"))
        assertEquals("proxy", outbounds.getJSONObject(0).getString("tag"))
    }
}
