package ru.prostokvn.app

import android.app.Activity
import android.content.Intent
import android.net.VpnService
import android.os.Bundle
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

/** A true one-button VPN screen: state originates from KvnVpnService, not a simulated toggle. */
class MainActivity : ComponentActivity() {
    private val consent = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK && VpnService.prepare(this) == null) {
            startVpnSafely()
        } else if (result.resultCode != Activity.RESULT_CANCELED) {
            Toast.makeText(this, "Разрешение VPN не выдано", Toast.LENGTH_LONG).show()
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightStatusBars = true
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightNavigationBars = true
        setContentView(R.layout.activity_main)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.root)) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        findViewById<View>(R.id.open_settings).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        findViewById<FrameLayout>(R.id.power_button).setOnClickListener { toggleVpn() }
        lifecycleScope.launch {
            VpnState.value.collect { render(it) }
        }
    }

    override fun onResume() {
        super.onResume()
        // Keep automatic routing checks active even when settings are never opened.
        PolicyRefreshWorker.configure(this)
        // A native crash resets the in-memory flow; restore the redacted last
        // startup stage so users do not see a misleading clean "VPN выключен".
        render(VpnState.value.value)
    }

    private fun toggleVpn() {
        when (VpnState.value.value.phase) {
            VpnState.Phase.ON, VpnState.Phase.STARTING -> {
                try { KvnVpnService.requestStop(this) }
                catch (e: RuntimeException) {
                    VpnDiagnostics.failure(this, e)
                    VpnState.update(VpnState.Phase.ERROR,
                        "Android отказал в остановке VPN (${e.javaClass.simpleName})")
                }
            }
            VpnState.Phase.STOPPING -> Unit
            VpnState.Phase.OFF, VpnState.Phase.ERROR -> {
                // A manual VLESS profile is optional. AUTO connects from the
                // verified GWZHUB feed without any setup by the user.
                if (StoredProfile(this).manualEnabled && !StoredProfile(this).diagnosticDirectNextStart) {
                    try {
                        val stored = StoredProfile(this).read() ?: run {
                            Toast.makeText(this, "Вручную выбранный VLESS-профиль отсутствует", Toast.LENGTH_LONG).show()
                            startActivity(Intent(this, SettingsActivity::class.java))
                            return
                        }
                        VlessProfile.parse(stored)
                    } catch (_: Exception) {
                        Toast.makeText(this, "Проверьте VLESS-профиль в настройках", Toast.LENGTH_LONG).show()
                        startActivity(Intent(this, SettingsActivity::class.java))
                        return
                    }
                }
                val permission = VpnService.prepare(this)
                if (permission != null) consent.launch(permission)
                else startVpnSafely()
            }
        }
    }

    private fun startVpnSafely() {
        VpnDiagnostics.enter(this, "start")
        try {
            KvnVpnService.requestStart(this)
        } catch (e: RuntimeException) {
            VpnDiagnostics.failure(this, e)
            VpnState.update(VpnState.Phase.ERROR,
                "Android отказал в запуске VPN (${e.javaClass.simpleName})")
        }
    }

    private fun render(status: VpnState.Status) {
        val label = findViewById<TextView>(R.id.power_label)
        val detail = findViewById<TextView>(R.id.connection_state)
        val button = findViewById<FrameLayout>(R.id.power_button)
        when (status.phase) {
            VpnState.Phase.ON -> {
                label.text = "Выключить"
                detail.text = "VPN запущен · ${status.detail}"
                button.isEnabled = true
            }
            VpnState.Phase.STARTING -> {
                label.text = "Остановить"
                detail.text = "Создаём защищённый туннель…"
                button.isEnabled = true
            }
            VpnState.Phase.STOPPING -> {
                label.text = "Выключается"
                detail.text = "Завершаем VPN-соединение…"
                button.isEnabled = false
            }
            VpnState.Phase.ERROR -> {
                label.text = "Включить"
                detail.text = status.detail.ifBlank { "Не удалось запустить VPN" }
                button.isEnabled = true
            }
            VpnState.Phase.OFF -> {
                label.text = "Включить"
                detail.text = VpnDiagnostics.summary(this) ?: "VPN выключен"
                button.isEnabled = true
            }
        }
        button.contentDescription = "КВН. ${label.text}. ${detail.text}"
    }
}
