package ru.prostokvn.app

import java.net.Inet6Address
import java.net.InetAddress
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class NetworkPrefixFormatterTests {
    @Test fun scopedIpv6DoesNotReachGoNetipParser() {
        // Represents the exact type of address observed in the Samsung crash:
        // fe80::c096:dbff:fe6c:c703%rmnet_data0/64.
        val bytes = InetAddress.getByName("fe80::c096:dbff:fe6c:c703").address
        val scoped = Inet6Address.getByAddress(null, bytes, 3)
        assertTrue(scoped.hostAddress.contains("%"))
        val result = NetworkPrefixFormatter.toPrefix(scoped, 64)
        assertFalse(result.contains("%"))
        assertEquals("${InetAddress.getByAddress(bytes).hostAddress}/64", result)
    }

    @Test fun normalIpv6AndIpv4RemainValid() {
        val v6 = NetworkPrefixFormatter.toPrefix(InetAddress.getByName("2001:db8::1"), 64)
        assertTrue(v6.endsWith("/64"))
        assertFalse(v6.contains("%"))
        assertEquals("192.0.2.24/24",
            NetworkPrefixFormatter.toPrefix(InetAddress.getByName("192.0.2.24"), 24))
    }

    @Test fun prefixLengthIsValidatedForAddressFamily() {
        assertThrows(IllegalArgumentException::class.java) {
            NetworkPrefixFormatter.toPrefix(InetAddress.getByName("127.0.0.1"), 64)
        }
        assertThrows(IllegalArgumentException::class.java) {
            NetworkPrefixFormatter.toPrefix(InetAddress.getByName("::1"), 129)
        }
    }
}
