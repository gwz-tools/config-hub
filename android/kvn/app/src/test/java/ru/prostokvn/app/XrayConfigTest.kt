package ru.prostokvn.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class XrayConfigTest {
    @get:Rule val temp = TemporaryFolder()
    private val id = "123e4567-e89b-12d3-a456-426614174000"
    private fun snapshot(): PolicyStore.Snapshot {
        val dir = temp.newFolder()
        File(dir, "direct.txt").writeText("example.ru\n")
        File(dir, "proxy.txt").writeText("example.org\n")
        File(dir, "block.txt").writeText("ads.example\n")
        return PolicyStore.Snapshot("test", dir, JSONObject())
    }

    @Test fun realityVlessUsesXrayJsonAndStrictProxyCatchall() {
        val link = "vless://" + id + "@example.com:443?security=reality&pbk=" +
            "a".repeat(43) + "&sni=www.example.com&type=tcp&flow=xtls-rprx-vision"
        val config = JSONObject(XrayConfig.build(VlessProfile.parse(link), snapshot(), true))
        assertEquals("tun", config.getJSONArray("inbounds").getJSONObject(0).getString("protocol"))
        val outbound = config.getJSONArray("outbounds").getJSONObject(0)
        assertEquals("vless", outbound.getString("protocol"))
        assertEquals("reality", outbound.getJSONObject("streamSettings").getString("security"))
        val users = outbound.getJSONObject("settings").getJSONArray("vnext")
            .getJSONObject(0).getJSONArray("users")
        assertEquals(id, users.getJSONObject(0).getString("id"))
        val rules = config.getJSONObject("routing").getJSONArray("rules")
        assertEquals("dns-out", rules.getJSONObject(0).getString("outboundTag"))
        assertEquals("proxy", rules.getJSONObject(rules.length() - 1).getString("outboundTag"))
        assertTrue(config.toString().contains("domain:example.ru"))
        assertTrue(config.toString().contains("domain:ads.example"))
    }

    @Test fun exportXrayConfigForOfficialNativeValidation() {
        val destination = System.getProperty("kvn.xray.validation.json") ?: return
        val link = "vless://" + id +
            "@test.example.com:443?type=tcp&security=tls&sni=www.example.com"
        val output = File(destination)
        output.parentFile?.mkdirs()
        output.writeText(XrayConfig.build(VlessProfile.parse(link), snapshot(), true))
        assertTrue(output.length() > 100)
    }

    @Test fun directOnlyWorksWhenExplicitlyAuthorized() {
        val config = JSONObject(XrayConfig.build(null, snapshot(), false, true))
        assertEquals("direct", config.getJSONArray("outbounds").getJSONObject(0).getString("tag"))
        val rules = config.getJSONObject("routing").getJSONArray("rules")
        assertEquals("direct", rules.getJSONObject(rules.length()-1).getString("outboundTag"))
        assertFalse(config.toString().contains("\"protocol\":\"vless\""))
    }
}
