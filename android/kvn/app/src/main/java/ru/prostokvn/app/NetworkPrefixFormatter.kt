package ru.prostokvn.app

import java.net.InetAddress

/**
 * The JNI libbox network monitor expects IP prefixes without IPv6 zone IDs.
 *
 * Android's Inet6Address.hostAddress may include a scope suffix like
 * "fe80::1%rmnet_data0". Go netip.ParsePrefix rejects scoped IPv6, and the
 * runtime used by libbox panics rather than returning a recoverable error.
 *
 * Reconstruct the IP address from its raw bytes, following the official
 * sing-box-for-android interface-address conversion. This reliably drops
 * the OS interface scope while keeping the 16-byte IPv6 address intact.
 */
object NetworkPrefixFormatter {
    fun toPrefix(address: InetAddress, prefixLength: Int): String {
        val maxBits = address.address.size * 8
        require(prefixLength in 0..maxBits) { "Invalid network prefix length" }
        val unscopedAddress = InetAddress.getByAddress(address.address).hostAddress
        return "$unscopedAddress/$prefixLength"
    }
}
