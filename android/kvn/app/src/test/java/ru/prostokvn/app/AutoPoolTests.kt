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
