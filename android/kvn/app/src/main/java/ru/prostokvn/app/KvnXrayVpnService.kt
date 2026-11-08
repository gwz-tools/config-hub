package ru.prostokvn.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import libv2ray.CoreCallbackHandler
import libv2ray.CoreController
import libv2ray.Libv2ray

/**
 * Experimental Xray backend in the ORIGINAL KVN package.
 * Matches Mamin VPN's documented Android TUN FD -> CoreController.startLoop.
 * KVN UI, encrypted profiles, live verified source and rule store are unchanged.
 */
class KvnXrayVpnService : VpnService() {
    companion object {
        private const val CHANNEL = "kvn_xray"
        private const val NOTIFY_ID = 7802
        private const val START = "ru.prostokvn.app.XRAY_START"
        private const val STOP = "ru.prostokvn.app.XRAY_STOP"
        fun requestStart(context: Context) {
            ContextCompat.startForegroundService(
                context, Intent(context, KvnXrayVpnService::class.java).setAction(START))
        }
        fun requestStop(context: Context) {
            context.startService(Intent(context, KvnXrayVpnService::class.java).setAction(STOP))
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var startup: Job? = null
    private var tunnel: ParcelFileDescriptor? = null
    private var controller: CoreController? = null
    @Volatile private var stopping = false

    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java)
            .createNotificationChannel(NotificationChannel(CHANNEL, "КВН Xray",
                NotificationManager.IMPORTANCE_LOW))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) {
            shutdown()
            return START_NOT_STICKY
        }
        if (startup?.isActive == true) return START_NOT_STICKY
        stopping = false
        try {
            startForeground(NOTIFY_ID, notification("Запускаем Xray…"))
        } catch (e: Exception) {
            VpnState.update(VpnState.Phase.ERROR, "Android не разрешил запуск VPN")
            stopSelf()
            return START_NOT_STICKY
        }
        VpnState.update(VpnState.Phase.STARTING)
        startup = scope.launch {
            try {
                check(prepare(this@KvnXrayVpnService) == null) {
                    "Нет разрешения Android на VPN"
                }
                val store = StoredProfile(this@KvnXrayVpnService)
                val direct = store.consumeDiagnosticDirectNextStart()
                val snapshot = PolicyStore(this@KvnXrayVpnService).ensureBundled()
                    ?: error("Нет проверенных правил КВН")
                val manual = store.manualEnabled
                val node = when {
                    direct -> null
                    manual -> VlessProfile.parse(store.read()
                        ?: error("Нет ручного VLESS-профиля"))
                    else -> AutoPool(this@KvnXrayVpnService).resolve().firstOrNull()
                        ?: error("Нет доступных узлов КВН")
                }
                if (stopping) return@launch
                val config = XrayConfig.build(node, snapshot, store.splitRouting, direct)

                // Official AndroidLibXrayLite bridge, not extracted Mamin binary.
                Libv2ray.initCoreEnv(filesDir.absolutePath, "")
                val callback = object : CoreCallbackHandler {
                    override fun startup(): Long = 0L
                    override fun shutdown(): Long = 0L
                    override fun onEmitStatus(status: Long, message: String?): Long {
                        // Status strings can contain private node data, do not log them.
                        if (status != 0L) Log.w("KVN-XRAY", "Xray status=" + status)
                        return 0L
                    }
                }
                val engine = Libv2ray.newCoreController(callback)
                controller = engine
                val builder = Builder()
                    .setSession("КВН Xray")
                    .setMtu(1500)
                    .addAddress("172.30.254.2", 30)
                    .addAddress("fd7a:115c:a1e0::2", 126)
                    .addRoute("0.0.0.0", 0)
                    .addRoute("::", 0)
                    .addDnsServer("172.30.254.1")
                    // Prevent Xray's own uplinks recursively entering our TUN.
                    .addDisallowedApplication(packageName)
                if (Build.VERSION.SDK_INT >= 29) builder.setMetered(false)
                tunnel = builder.establish() ?: error("Android не создал TUN")
                Log.i("KVN-XRAY", "Android TUN established; handing FD to Xray")
                engine.startLoop(config, tunnel!!.fd)
                check(engine.getIsRunning()) { "Xray-core не запустился" }
                if (stopping) return@launch
                Log.i("KVN-XRAY", "Xray started with KVN profile source")
                val label = when {
                    direct -> "XRAY DIRECT · БЕЗ ШИФРОВАНИЯ"
                    manual -> "XRAY · личный VLESS"
                    else -> "XRAY · проверенный пул КВН"
                }
                VpnState.update(VpnState.Phase.ON, label)
                runCatching {
                    getSystemService(NotificationManager::class.java)
                        .notify(NOTIFY_ID, notification("Xray запущен"))
                }
            } catch (e: Throwable) {
                // Never log full native exception text: configs may contain UUIDs.
                Log.e("KVN-XRAY", "Startup failure: " + e.javaClass.simpleName)
                VpnState.update(VpnState.Phase.ERROR,
                    "Xray: " + e.javaClass.simpleName + " (см. журнал KVN-XRAY)")
                cleanup()
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun notification(status: String): Notification {
        val open = PendingIntent.getActivity(this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_vpn_notification)
            .setContentTitle("КВН · Xray")
            .setContentText(status)
            .setContentIntent(open)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun shutdown() {
        stopping = true
        VpnState.update(VpnState.Phase.STOPPING)
        scope.launch {
            startup?.cancel()
            cleanup()
            VpnState.update(VpnState.Phase.OFF)
            stopSelf()
        }
    }

    @Synchronized private fun cleanup() {
        runCatching { controller?.stopLoop() }
        controller = null
        runCatching { tunnel?.close() }
        tunnel = null
    }

    override fun onRevoke() { shutdown() }
    override fun onDestroy() {
        stopping = true
        cleanup()
        scope.cancel()
        if (VpnState.value.value.phase != VpnState.Phase.ERROR)
            VpnState.update(VpnState.Phase.OFF)
        super.onDestroy()
    }
}
