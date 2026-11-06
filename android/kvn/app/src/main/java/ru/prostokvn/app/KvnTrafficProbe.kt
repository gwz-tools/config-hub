package ru.prostokvn.app

import android.util.Log
import io.nekohasekai.libbox.CommandClient
import io.nekohasekai.libbox.CommandClientHandler
import io.nekohasekai.libbox.CommandClientOptions
import io.nekohasekai.libbox.ConnectionEvents
import io.nekohasekai.libbox.Libbox
import io.nekohasekai.libbox.LogIterator
import io.nekohasekai.libbox.OutboundGroupItemIterator
import io.nekohasekai.libbox.OutboundGroupIterator
import io.nekohasekai.libbox.StatusMessage
import io.nekohasekai.libbox.StringIterator
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicInteger

/**
 * Diagnostic only: secure, domain-free aggregate libbox connection telemetry.
 * Used in one-shot DIRECT test; never logs destination addresses or user profiles.
 *
 * Counter source: official libbox CommandStatus and CommandConnections streams.
 */
class KvnTrafficProbe(private val scope: CoroutineScope) : CommandClientHandler {
    private val newTcp = AtomicInteger(0)
    private val newUdp = AtomicInteger(0)
    private val statusSamples = AtomicInteger(0)
    private val client: CommandClient = CommandClient(this, CommandClientOptions().apply {
        addCommand(Libbox.CommandStatus)
        addCommand(Libbox.CommandConnections)
        statusInterval = 2_000_000_000L // nanoseconds; matches official SFA client
    })

    fun start() {
        scope.launch(Dispatchers.IO) {
            runCatching { client.connect() }.onFailure {
                Log.w("KVN", "Traffic telemetry unavailable: ${it.javaClass.simpleName}")
            }
        }
    }

    fun close() { runCatching { client.disconnect() } }

    override fun connected() {
        Log.i("KVN", "Traffic telemetry connected")
    }
    override fun disconnected(message: String?) {
        Log.i("KVN", "Traffic telemetry disconnected")
    }
    override fun setDefaultLogLevel(level: Int) {}
    override fun clearLogs() {}
    override fun writeLogs(messageList: LogIterator?) {}
    override fun writeGroups(message: OutboundGroupIterator?) {}
    override fun writeOutbounds(message: OutboundGroupItemIterator?) {}
    override fun initializeClashMode(modeList: StringIterator?, currentMode: String?) {}
    override fun updateClashMode(newMode: String?) {}

    override fun writeStatus(message: StatusMessage?) {
        if (message == null) return
        val sample = statusSamples.incrementAndGet()
        // Bounded logging: first two samples, then every 6 seconds, up to 1 minute.
        if (sample <= 2 || (sample <= 30 && sample % 3 == 0)) {
            Log.i("KVN", "TRAFFIC sample=$sample ingress=${message.connectionsIn} egress=${message.connectionsOut} up=${message.uplinkTotal}B down=${message.downlinkTotal}B available=${message.trafficAvailable} newTcp=${newTcp.get()} newUdp=${newUdp.get()}")
        }
    }

    override fun writeConnectionEvents(events: ConnectionEvents?) {
        val iterator = events?.iterator() ?: return
        while (iterator.hasNext()) {
            val event = iterator.next()
            // Go libbox: ConnectionEventNew=0. No IP, hostname or port logged.
            if (event.type != 0) continue
            when (event.connection?.network?.lowercase()) {
                "tcp" -> newTcp.incrementAndGet()
                "udp" -> newUdp.incrementAndGet()
            }
        }
    }
}
