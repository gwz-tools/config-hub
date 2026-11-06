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
import android.net.NetworkRequest
import android.net.VpnService
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
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
import java.util.concurrent.atomic.AtomicBoolean

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
    private var networkCallbackThread: HandlerThread? = null
    @Volatile private var selectedUnderlyingNetwork: Network? = null
    @Volatile private var selectedUnderlyingInterface: String? = null
    private val firstProtectedSocketLogged = AtomicBoolean(false)
    // Android system resolver is explicitly bound to the physical upstream.
    // This avoids assuming UDP/53 access to a public resolver on cellular.
    private val systemDns by lazy { KvnLocalResolver { physicalNetworkForDns() } }
    private var runningJob: Job? = null
    private var trafficProbe: KvnTrafficProbe? = null
    @Volatile private var stopping = false

    override fun onCreate() {
        super.onCreate()
        // Notification errors must never crash the entire Android process.
        runCatching { createChannel() }.onFailure { VpnDiagnostics.failure(this, it) }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopVpn()
            return START_NOT_STICKY
        }
        if (runningJob?.isActive == true) return START_NOT_STICKY
        stopping = false
        VpnDiagnostics.enter(this, "start")
        // Mandatory: promote before any slow native setup; Android may kill slow foreground services.
        try { startForeground(NOTIFICATION_ID, notification("Подключение…")) }
        catch (e: Throwable) {
            VpnDiagnostics.failure(this, e)
            VpnState.update(VpnState.Phase.ERROR, "Android запретил фоновую VPN-службу (${e.javaClass.simpleName})")
            stopSelf()
            return START_NOT_STICKY
        }
        VpnState.update(VpnState.Phase.STARTING)
        runningJob = scope.launch {
            try {
                VpnDiagnostics.enter(this@KvnVpnService, "permissions")
                if (prepare(this@KvnVpnService) != null) error("Системное разрешение VPN отсутствует")
                VpnDiagnostics.enter(this@KvnVpnService, "rules")
                val store = StoredProfile(this@KvnVpnService)
                val snapshot = PolicyStore(this@KvnVpnService).ensureBundled()
                    ?: error("Проверенные правила недоступны")
                val diagnosticDirect = store.consumeDiagnosticDirectNextStart()
                val manual = store.manualEnabled
                VpnDiagnostics.enter(this@KvnVpnService, "pool")
                val candidateProfiles: List<VlessProfile> = if (diagnosticDirect) {
                    emptyList() // No VLESS fetch or use in explicit direct test.
                } else if (manual) {
                    val link = store.read() ?: error("Добавьте свой VLESS-профиль в настройках")
                    listOf(VlessProfile.parse(link))
                } else {
                    AutoPool(this@KvnVpnService).resolve().also {
                        check(it.isNotEmpty()) {
                            "Нет доступных проверенных VLESS-узлов. Проверьте интернет или повторите позже."
                        }
                    }
                }
                VpnDiagnostics.enter(this@KvnVpnService, "config")
                val config = when {
                    diagnosticDirect -> VpnConfig.buildDirectDiagnostic(snapshot)
                    manual -> VpnConfig.build(candidateProfiles.first(), snapshot, store.splitRouting)
                    else -> VpnConfig.buildAuto(candidateProfiles, snapshot, store.splitRouting)
                }
                val connectionLabel = when {
                    diagnosticDirect -> "ТЕСТ DIRECT · БЕЗ ШИФРОВАНИЯ"
                    manual -> candidateProfiles.first().name
                    else -> "AUTO · ${candidateProfiles.size} узлов"
                }
                val work = getExternalFilesDir(null) ?: filesDir
                val setup = SetupOptions().apply {
                    basePath = filesDir.absolutePath
                    workingPath = work.absolutePath
                    tempPath = cacheDir.absolutePath
                    // Official sing-box Android client enables this workaround
                    // on Android 9+ (Go runtime stack issue #68760).
                    // Our Samsung test device runs Android 17.
                    fixAndroidStack = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
                    debug = false
                    logMaxLines = 500
                }
                VpnDiagnostics.enter(this@KvnVpnService, "native_setup")
                synchronized(nativeSetupLock) {
                    if (!nativeSetupCompleted) {
                        Libbox.setup(setup)
                        nativeSetupCompleted = true
                    }
                }
                VpnDiagnostics.enter(this@KvnVpnService, "command_server")
                val server = CommandServer(this@KvnVpnService, this@KvnVpnService)
                commandServer = server
                server.start()
                VpnDiagnostics.enter(this@KvnVpnService, "engine_start")
                server.startOrReloadService(config, OverrideOptions())
                if (diagnosticDirect) {
                    // Structured counters (no hostnames/URLs) expose whether TUN
                    // produces any TCP/UDP connections and return traffic.
                    trafficProbe = KvnTrafficProbe(scope).also { it.start() }
                }
                if (stopping) {
                    cleanup()
                    return@launch
                }
                VpnDiagnostics.enter(this@KvnVpnService, "tun")
                check(tunnel != null) { "VPN-интерфейс Android не создан" }
                if (!stopping) {
                    VpnDiagnostics.connected(this@KvnVpnService)
                    VpnState.update(VpnState.Phase.ON, connectionLabel)
                    updateNotification(if (diagnosticDirect) "ТЕСТ DIRECT — без шифрования" else "VPN запущен")
                }
            } catch (e: kotlinx.coroutines.CancellationException) {
                // User requested STOP while the native engine was starting.
                cleanup()
                if (stopping) {
                    VpnDiagnostics.stopped(this@KvnVpnService)
                    VpnState.update(VpnState.Phase.OFF)
                }
            } catch (e: Throwable) {
                // Also catches JNI LinkageError and other non-Exception startup failures.
                // Native SIGABRT/SIGSEGV cannot be caught, hence the stage journal above.
                VpnDiagnostics.failure(this@KvnVpnService, e)
                // libbox throws a Go proxyerror with the actionable message in
                // e.message. Logging only the type hid five identical failures.
                // This is a local debug build; do not upload raw logs to GitHub.
                val nativeReason = (e.message ?: e.toString()).take(320)
                Log.e("KVN", "VPN engine failed at startup: ${e.javaClass.simpleName}: $nativeReason")
                VpnState.update(VpnState.Phase.ERROR,
                    "Движок VPN: $nativeReason")
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
            VpnDiagnostics.stopped(this@KvnVpnService)
            VpnState.update(VpnState.Phase.OFF)
            stopSelf()
        }
    }

    @Synchronized private fun cleanup() {
        runCatching { trafficProbe?.close() }
        trafficProbe = null
        runCatching { commandServer?.closeService() }
        runCatching { commandServer?.close() }
        commandServer = null
        runCatching { tunnel?.close() }
        tunnel = null
        stopPhysicalNetworkMonitor()
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
        VpnDiagnostics.enter(this, "tun_open")
        Log.i("KVN", "Native engine requested Android TUN")
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
        Log.i("KVN", "TUN established (mtu=${options.mtu}, autoRoute=${options.autoRoute})")
        return pfd.fd
    }
    override fun usePlatformAutoDetectInterfaceControl() = true
    override fun autoDetectInterfaceControl(fd: Int) {
        val protected = protect(fd)
        if (!protected) Log.e("KVN", "VPN socket protect() returned false")
        check(protected) { "Невозможно исключить сокет из VPN" }
        if (firstProtectedSocketLogged.compareAndSet(false, true)) {
            Log.i("KVN", "First outbound socket protected from VPN routing")
        }
    }
    override fun localDNSTransport(): LocalDNSTransport = systemDns

    private fun physicalNetworkForDns(): Network? {
        selectedUnderlyingNetwork?.let { return it }
        // Callback delivery is asynchronous; DNS can be requested before it arrives.
        // Never select the VPN itself as an upstream resolver network.
        val physical = connectivity.allNetworks.firstOrNull { network ->
            val caps = connectivity.getNetworkCapabilities(network)
            val name = connectivity.getLinkProperties(network)?.interfaceName
            caps != null && name != null && !name.startsWith("tun") &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN) &&
                !caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
        }
        if (physical == null) Log.w("KVN", "No physical network available for Android DNS")
        return physical
    }
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
        stopPhysicalNetworkMonitor()
        // Android 9+ registerDefaultNetworkCallback() can report our VPN itself
        // instead of the underlying cellular/Wi-Fi network. This leaves libbox
        // without a usable default outbound interface. Follow SFA's strategy.
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .addCapability(NetworkCapabilities.NET_CAPABILITY_NOT_RESTRICTED)
            .addCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
            .build()
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { notifyInterface(listener, network) }
            override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
                notifyInterface(listener, network)
            }
            override fun onLinkPropertiesChanged(network: Network, link: android.net.LinkProperties) {
                notifyInterface(listener, network)
            }
            override fun onLost(network: Network) {
                // An old network disappearing must not erase a newly selected one.
                if (selectedUnderlyingNetwork == network) {
                    selectedUnderlyingNetwork = null
                    selectedUnderlyingInterface = null
                    Log.w("KVN", "Physical upstream lost")
                    listener.updateDefaultInterface("", -1, false, false)
                }
            }
            override fun onUnavailable() { Log.w("KVN", "No physical upstream available") }
        }
        val thread = HandlerThread("kvn-physical-network").apply { start() }
        networkCallbackThread = thread
        networkCallback = cb
        val handler = Handler(thread.looper)
        try {
            when {
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
                    connectivity.registerBestMatchingNetworkCallback(request, cb, handler)
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.P ->
                    connectivity.requestNetwork(request, cb, handler)
                else ->
                    connectivity.registerDefaultNetworkCallback(cb, handler)
            }
            Log.i("KVN", "Physical-network monitor registered; SDK=${Build.VERSION.SDK_INT}")
        } catch (e: Throwable) {
            stopPhysicalNetworkMonitor()
            Log.e("KVN", "Unable to register physical-network monitor: ${e.javaClass.simpleName}")
            throw e
        }
    }
    private fun notifyInterface(listener: InterfaceUpdateListener, network: Network) {
        val caps = connectivity.getNetworkCapabilities(network) ?: return
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ||
            !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)) return
        val link = connectivity.getLinkProperties(network) ?: return
        val name = link.interfaceName ?: return
        if (name.startsWith("tun")) return
        val id = runCatching { NetworkInterface.getByName(name)?.index ?: 0 }.getOrDefault(0)
        if (id <= 0) {
            Log.w("KVN", "Physical upstream interface index not yet available")
            return
        }
        val expensive = !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED)
        selectedUnderlyingNetwork = network
        if (selectedUnderlyingInterface != name) {
            selectedUnderlyingInterface = name
            Log.i("KVN", "Selected physical upstream: $name (index=$id)")
        }
        listener.updateDefaultInterface(name, id, expensive, false)
    }
    private fun stopPhysicalNetworkMonitor() {
        networkCallback?.let { runCatching { connectivity.unregisterNetworkCallback(it) } }
        networkCallback = null
        networkCallbackThread?.quitSafely()
        networkCallbackThread = null
        selectedUnderlyingNetwork = null
        selectedUnderlyingInterface = null
    }
    override fun closeDefaultInterfaceMonitor(listener: InterfaceUpdateListener) {
        stopPhysicalNetworkMonitor()
    }
    override fun getInterfaces(): NetworkInterfaceIterator {
        val result = mutableListOf<BoxNetworkInterface>()
        for (network in connectivity.allNetworks) {
            val link = connectivity.getLinkProperties(network) ?: continue
            val caps = connectivity.getNetworkCapabilities(network) ?: continue
            val name = link.interfaceName ?: continue
            if (name.startsWith("tun") ||
                caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ||
                !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)) continue
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
                // Inet6Address.hostAddress can contain a scope such as
                // fe80::1%rmnet_data0. sing-box libbox parses interface prefixes
                // with Go netip.ParsePrefix, which panics on scoped IPv6.
                addresses = IterStrings(jni.interfaceAddresses.map {
                    NetworkPrefixFormatter.toPrefix(it.address, it.networkPrefixLength.toInt())
                })
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
