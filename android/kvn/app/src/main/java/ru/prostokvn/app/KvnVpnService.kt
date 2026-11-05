package ru.prostokvn.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.Process
import android.system.OsConstants
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import io.nekohasekai.libbox.BridgeOptions
import io.nekohasekai.libbox.BridgeSession
import io.nekohasekai.libbox.CommandServer
import io.nekohasekai.libbox.CommandServerHandler
import io.nekohasekai.libbox.ConnectionOwner
import io.nekohasekai.libbox.InterfaceUpdateListener
import io.nekohasekai.libbox.Libbox
import io.nekohasekai.libbox.LocalDNSTransport
import io.nekohasekai.libbox.NeighborUpdateListener
import io.nekohasekai.libbox.NetworkInterfaceIterator
import io.nekohasekai.libbox.Notification as BoxNotification
import io.nekohasekai.libbox.OverrideOptions
import io.nekohasekai.libbox.PlatformInterface
import io.nekohasekai.libbox.PlatformUser
import io.nekohasekai.libbox.SetupOptions
import io.nekohasekai.libbox.ShellSession
import io.nekohasekai.libbox.StringIterator
import io.nekohasekai.libbox.SystemProxyStatus
import io.nekohasekai.libbox.TunOptions
import io.nekohasekai.libbox.WIFIState
import io.nekohasekai.libbox.NetworkInterface as BoxNetworkInterface
import java.net.InetSocketAddress
import java.net.NetworkInterface

/** Own VPN engine. Requires externally verified GPL sing-box libbox 1.14.4 AAR, not a third-party APK. */
class KvnVpnService : VpnService(), PlatformInterface, CommandServerHandler {
    companion object {
        const val ACTION_START = "ru.prostokvn.app.vpn.START"
        const val ACTION_STOP = "ru.prostokvn.app.vpn.STOP"
        private const val NOTIFICATION_ID = 7801
        private const val CHANNEL_ID = "kvn_vpn"
        private val nativeSetupLock = Any()
        private var nativeSetupCompleted = false

        fun requestStart(context: Context) {
            val intent = Intent(context, KvnVpnService::class.java).setAction(ACTION_START)
            ContextCompat.startForegroundService(context, intent)
        }
        fun requestStop(context: Context) {
            context.startService(Intent(context, KvnVpnService::class.java).setAction(ACTION_STOP))
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val connectivity by lazy { getSystemService(ConnectivityManager::class.java) }
    private var commandServer: CommandServer? = null
    private var tunnel: ParcelFileDescriptor? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var runningJob: Job? = null
    @Volatile private var stopping = false

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopVpn()
            return START_NOT_STICKY
        }
        if (runningJob?.isActive == true) return START_NOT_STICKY
        stopping = false
        // Mandatory: promote before any slow native setup; Android may kill slow foreground services.
        try { startForeground(NOTIFICATION_ID, notification("Подключение…")) }
        catch (e: Exception) {
            VpnState.update(VpnState.Phase.ERROR, "Нет разрешения на запуск VPN-службы")
            stopSelf()
            return START_NOT_STICKY
        }
        VpnState.update(VpnState.Phase.STARTING)
        runningJob = scope.launch {
            try {
                if (prepare(this@KvnVpnService) != null) error("Системное разрешение VPN отсутствует")
                val store = StoredProfile(this@KvnVpnService)
                val snapshot = PolicyStore(this@KvnVpnService).ensureBundled()
                    ?: error("Проверенные правила недоступны")
                val manual = store.manualEnabled
                val candidateProfiles: List<VlessProfile> = if (manual) {
                    val link = store.read() ?: error("Добавьте свой VLESS-профиль в настройках")
                    listOf(VlessProfile.parse(link))
                } else {
                    AutoPool(this@KvnVpnService).resolve().also {
                        check(it.isNotEmpty()) {
                            "Нет доступных проверенных VLESS-узлов. Проверьте интернет или повторите позже."
                        }
                    }
                }
                val config = if (manual) {
                    VpnConfig.build(candidateProfiles.first(), snapshot, store.splitRouting)
                } else {
                    VpnConfig.buildAuto(candidateProfiles, snapshot, store.splitRouting)
                }
                val connectionLabel = if (manual) candidateProfiles.first().name
                                      else "AUTO · ${candidateProfiles.size} узлов"
                val work = getExternalFilesDir(null) ?: filesDir
                val setup = SetupOptions().apply {
                    basePath = filesDir.absolutePath
                    workingPath = work.absolutePath
                    tempPath = cacheDir.absolutePath
                    debug = false
                    logMaxLines = 500
                }
                synchronized(nativeSetupLock) {
                    if (!nativeSetupCompleted) {
                        Libbox.setup(setup)
                        nativeSetupCompleted = true
                    }
                }
                val server = CommandServer(this@KvnVpnService, this@KvnVpnService)
                commandServer = server
                server.start()
                server.startOrReloadService(config, OverrideOptions())
                if (stopping) {
                    cleanup()
                    return@launch
                }
                check(tunnel != null) { "VPN-интерфейс Android не создан" }
                if (!stopping) {
                    VpnState.update(VpnState.Phase.ON, connectionLabel)
                    updateNotification("VPN запущен")
                }
            } catch (e: kotlinx.coroutines.CancellationException) {
                // User requested STOP while the native engine was starting.
                cleanup()
                if (stopping) VpnState.update(VpnState.Phase.OFF)
            } catch (e: Exception) {
                Log.e("KVN", "VPN startup failed (diagnostic details intentionally redacted)")
                VpnState.update(VpnState.Phase.ERROR,
                    when (e) {
                        is IllegalArgumentException, is IllegalStateException -> e.message?.take(180) ?: "Ошибка профиля"
                        else -> "Не удалось запустить VPN. Проверьте профиль и сеть."
                    })
                cleanup()
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun stopVpn() {
        stopping = true
        VpnState.update(VpnState.Phase.STOPPING)
        scope.launch {
            runningJob?.cancel()
            cleanup()
            VpnState.update(VpnState.Phase.OFF)
            stopSelf()
        }
    }

    @Synchronized private fun cleanup() {
        runCatching { commandServer?.closeService() }
        runCatching { commandServer?.close() }
        commandServer = null
        runCatching { tunnel?.close() }
        tunnel = null
        networkCallback?.let { runCatching { connectivity.unregisterNetworkCallback(it) } }
        networkCallback = null
    }

    override fun onRevoke() { stopVpn() }
    override fun onDestroy() {
        cleanup()
        scope.cancel()
        if (VpnState.value.value.phase != VpnState.Phase.ERROR) VpnState.update(VpnState.Phase.OFF)
        super.onDestroy()
    }

    private fun createChannel() {
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "КВН — VPN", NotificationManager.IMPORTANCE_LOW))
    }
    private fun notification(status: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_vpn_notification)
            .setContentTitle("КВН")
            .setContentText(status)
            .setContentIntent(open)
            .setOngoing(true).setOnlyAlertOnce(true).build()
    }
    private fun updateNotification(status: String) {
        if (Build.VERSION.SDK_INT >= 33 &&
            androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.POST_NOTIFICATIONS
            ) != android.content.pm.PackageManager.PERMISSION_GRANTED) return
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(status))
    }

    // libbox.PlatformInterface — TUN file descriptor stays owned by this service until closed.
    override fun openTun(options: TunOptions): Int {
        check(prepare(this) == null) { "Разрешение VPN отозвано" }
        val b = Builder().setSession("КВН").setMtu(options.mtu)
        val ipv4 = options.inet4Address
        while (ipv4.hasNext()) ipv4.next().let { b.addAddress(it.address(), it.prefix()) }
        val ipv6 = options.inet6Address
        while (ipv6.hasNext()) ipv6.next().let { b.addAddress(it.address(), it.prefix()) }
        if (options.autoRoute) {
            // Route IPv4 and IPv6 through TUN to avoid IPv6 bypass/leak.
            b.addRoute("0.0.0.0", 0)
            b.addRoute("::", 0)
            val dns = options.dnsServerAddress
            while (dns.hasNext()) b.addDnsServer(dns.next())
            // The VPN engine itself must not recurse through its own tunnel.
            b.addDisallowedApplication(packageName)
        }
        if (Build.VERSION.SDK_INT >= 29) b.setMetered(false)
        val pfd = b.establish() ?: error("Android отказал в создании TUN")
        tunnel = pfd
        return pfd.fd
    }
    override fun usePlatformAutoDetectInterfaceControl() = true
    override fun autoDetectInterfaceControl(fd: Int) { check(protect(fd)) { "Невозможно исключить сокет из VPN" } }
    override fun localDNSTransport(): LocalDNSTransport? = null
    override fun findConnectionOwner(ipProtocol: Int, sourceAddress: String?, sourcePort: Int,
                                     destinationAddress: String?, destinationPort: Int): ConnectionOwner {
        val owner = ConnectionOwner()
        if (Build.VERSION.SDK_INT >= 29) {
            owner.userId = connectivity.getConnectionOwnerUid(ipProtocol,
                InetSocketAddress(sourceAddress, sourcePort), InetSocketAddress(destinationAddress, destinationPort))
        } else owner.userId = Process.myUid()
        return owner
    }
    override fun startDefaultInterfaceMonitor(listener: InterfaceUpdateListener) {
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { notifyInterface(listener, network) }
            override fun onCapabilitiesChanged(network: Network, networkCapabilities: NetworkCapabilities) {
                notifyInterface(listener, network)
            }
            override fun onLost(network: Network) { listener.updateDefaultInterface("", -1, false, false) }
        }
        networkCallback?.let { runCatching { connectivity.unregisterNetworkCallback(it) } }
        networkCallback = cb
        connectivity.registerDefaultNetworkCallback(cb)
        connectivity.activeNetwork?.let { notifyInterface(listener, it) }
    }
    private fun notifyInterface(listener: InterfaceUpdateListener, network: Network) {
        val link = connectivity.getLinkProperties(network) ?: return
        val name = link.interfaceName ?: return
        if (name.startsWith("tun")) return
        val id = runCatching { NetworkInterface.getByName(name)?.index ?: 0 }.getOrDefault(0)
        val expensive = connectivity.isActiveNetworkMetered
        listener.updateDefaultInterface(name, id, expensive, false)
    }
    override fun closeDefaultInterfaceMonitor(listener: InterfaceUpdateListener) {
        networkCallback?.let { runCatching { connectivity.unregisterNetworkCallback(it) } }
        networkCallback = null
    }
    override fun getInterfaces(): NetworkInterfaceIterator {
        val result = mutableListOf<BoxNetworkInterface>()
        for (network in connectivity.allNetworks) {
            val link = connectivity.getLinkProperties(network) ?: continue
            val caps = connectivity.getNetworkCapabilities(network) ?: continue
            val name = link.interfaceName ?: continue
            if (name.startsWith("tun")) continue
            val jni = NetworkInterface.getByName(name) ?: continue
            result += BoxNetworkInterface().apply {
                this.name = name
                index = jni.index
                mtu = runCatching { jni.mtu }.getOrDefault(1500)
                type = when {
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> Libbox.InterfaceTypeWIFI
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> Libbox.InterfaceTypeCellular
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> Libbox.InterfaceTypeEthernet
                    else -> Libbox.InterfaceTypeOther
                }
                flags = OsConstants.IFF_UP or OsConstants.IFF_RUNNING
                metered = !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED)
                addresses = IterStrings(jni.interfaceAddresses.map { "${it.address.hostAddress}/${it.networkPrefixLength}" })
                dnsServer = IterStrings(link.dnsServers.mapNotNull { it.hostAddress })
                gateway = IterStrings(link.routes.mapNotNull { it.gateway?.hostAddress })
            }
        }
        val it = result.iterator()
        return object : NetworkInterfaceIterator {
            override fun hasNext() = it.hasNext()
            override fun next(): BoxNetworkInterface = it.next()
        }
    }
    private class IterStrings(strings: List<String>) : StringIterator {
        private val stored = strings
        private val items = stored.iterator()
        override fun len() = stored.size
        override fun hasNext() = items.hasNext()
        override fun next(): String = items.next()
    }
    override fun underNetworkExtension() = false
    override fun includeAllNetworks() = false
    override fun clearDNSCache() {}
    override fun readWIFIState(): WIFIState? = null
    override fun sendNotification(notification: BoxNotification?) {}
    override fun cancelNotification(identifier: String?, typeID: Int) {}
    override fun startNeighborMonitor(listener: NeighborUpdateListener?) {}
    override fun closeNeighborMonitor(listener: NeighborUpdateListener?) {}
    override fun registerMyInterface(name: String?) {}
    override fun usePlatformShell() = false
    override fun checkPlatformShell() { error("Системная оболочка отключена") }
    override fun openShellSession(user: PlatformUser?, command: String?, environ: StringIterator?,
                                  term: String?, rows: Int, cols: Int): ShellSession =
        error("Системная оболочка отключена")
    override fun lookupUser(username: String?): PlatformUser = error("Не поддерживается")
    override fun lookupSFTPServer(): String = error("Не поддерживается")
    override fun readSystemSSHHostKey(): String = error("Не поддерживается")
    override fun tailscaleHostname() = "КВН"
    override fun usePlatformBridge() = false
    override fun createBridge(options: BridgeOptions?): BridgeSession = error("Не поддерживается")

    // libbox.CommandServerHandler. No fake success; the state is set only after native TUN + core startup.
    override fun serviceStop() { stopVpn() }
    override fun serviceReload() { error("Перезапуск выполняется через кнопку VPN") }
    override fun getSystemProxyStatus() = SystemProxyStatus().apply { available = false; enabled = false }
    override fun setSystemProxyEnabled(enabled: Boolean) { error("Системный HTTP-прокси отключён") }
    override fun triggerNativeCrash() { error("Отключено") }
    override fun writeDebugMessage(message: String?) { /* do not log private profile material */ }
    override fun connectSSHAgent() = -1
}
