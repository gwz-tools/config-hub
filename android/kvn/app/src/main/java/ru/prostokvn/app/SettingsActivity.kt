package ru.prostokvn.app

import android.app.AlertDialog
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import androidx.work.WorkInfo
import androidx.work.WorkManager
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.util.Date

/** VPN configuration and diagnostic controls kept off the single-button home screen. */
class SettingsActivity : ComponentActivity() {
    private lateinit var refresh: Button
    private var updating = false
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightStatusBars = true
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightNavigationBars = true
        setContentView(R.layout.activity_settings)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.root)) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        val store = StoredProfile(this)
        val modeSwitch = findViewById<Switch>(R.id.manual_mode)
        modeSwitch.isChecked = store.manualEnabled
        fun renderProfileMode() {
            findViewById<TextView>(R.id.saved_profile).text =
                if (store.manualEnabled) store.summary()
                else "Режим AUTO активен. Личный профиль не требуется."
        }
        renderProfileMode()
        modeSwitch.setOnCheckedChangeListener { _, enabled ->
            if (enabled && store.read() == null) {
                toast("Сначала сохраните личный VLESS-профиль или используйте AUTO")
                modeSwitch.isChecked = false
            } else {
                store.manualEnabled = enabled
                renderProfileMode()
            }
        }
        lifecycleScope.launch {
            val count = withContext(Dispatchers.IO) {
                AutoPool(this@SettingsActivity).cachedCount()
            }
            findViewById<TextView>(R.id.auto_pool_status).text =
                if (count > 0) "Сохранено $count проверенных узлов. Обновление при следующем подключении после 6 часов. Автовыбор каждые 3 минуты."
                else "При первом подключении КВН загрузит проверенный пул из GitHub. Ручная VLESS-ссылка не требуется."
        }
        findViewById<Button>(R.id.save_profile).setOnClickListener {
            val link = findViewById<EditText>(R.id.profile_link).text.toString().trim()
            try {
                val name = VlessProfile.parse(link).name
                store.save(link)
                store.manualEnabled = true
                modeSwitch.isChecked = true
                renderProfileMode()
                findViewById<EditText>(R.id.profile_link).text.clear()
                toast("Профиль сохранён. Для применения выключите и включите VPN.")
            } catch (e: Exception) { toast(e.message ?: "Некорректная ссылка") }
        }
        findViewById<Switch>(R.id.split_routing).apply {
            isChecked = store.splitRouting
            setOnCheckedChangeListener { _, enabled ->
                store.splitRouting = enabled
                toast("Режим сохранён. Для применения перезапустите VPN.")
            }
        }
        refresh = findViewById(R.id.refresh_rules)
        refresh.setOnClickListener { PolicyRefreshWorker.requestNow(this) }
        findViewById<Button>(R.id.check_release).setOnClickListener { checkRelease() }
        val manager = WorkManager.getInstance(this)
        manager.getWorkInfosForUniqueWorkLiveData(PolicyRefreshWorker.ON_DEMAND).observe(this) { work ->
            updating = work.any { !it.state.isFinished }
            refresh.isEnabled = !updating
            refresh.setText(if (updating) R.string.rules_waiting else R.string.refresh_rules)
            renderRules()
        }
        manager.getWorkInfosForUniqueWorkLiveData(PolicyRefreshWorker.PERIODIC_STATUS).observe(this) { work ->
            if (work.none { it.state == WorkInfo.State.RUNNING }) renderRules()
        }
        lifecycleScope.launch {
            withContext(Dispatchers.IO) { PolicyStore(this@SettingsActivity).ensureBundled() }
            PolicyRefreshWorker.configure(this@SettingsActivity)
            renderRules()
        }
    }
    override fun onResume() { super.onResume(); renderRules() }
    private fun renderRules() {
        lifecycleScope.launch {
            val snap = withContext(Dispatchers.IO) { PolicyStore(this@SettingsActivity).current() }
            val summary = if (snap == null) getString(R.string.no_rules) else {
                val files = snap.manifest.getJSONObject("files")
                "DIRECT: ${files.getJSONObject("direct.txt").getInt("domains")}, " +
                    "PROXY: ${files.getJSONObject("proxy.txt").getInt("domains")}, " +
                    "BLOCK: ${files.getJSONObject("block.txt").getInt("domains")}\n" +
                    "Правила: ${snap.version} · SHA-256 проверен"
            }
            findViewById<TextView>(R.id.rules_summary).text = summary
            val pref = getSharedPreferences("routing_updater", MODE_PRIVATE)
            val time = pref.getLong("lastChecked", 0)
            val last = if (time == 0L) getString(R.string.not_checked) else
                DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(time))
            findViewById<TextView>(R.id.check_status).text = getString(R.string.check_summary, last,
                if (pref.contains("lastError")) getString(R.string.cached_after_error) else "")
        }
    }
    private fun checkRelease() {
        val button = findViewById<Button>(R.id.check_release)
        button.isEnabled = false
        button.setText(R.string.checking_release)
        lifecycleScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { AppRelease.check(this@SettingsActivity) }
                if (result == null) toast(getString(R.string.no_release))
                else AlertDialog.Builder(this@SettingsActivity)
                    .setTitle(getString(R.string.new_release, result.label))
                    .setMessage(R.string.release_consent)
                    .setPositiveButton(R.string.open_release) { _, _ ->
                        try { AppRelease.openTrustedRelease(this@SettingsActivity, result) }
                        catch (_: android.content.ActivityNotFoundException) { toast(getString(R.string.no_browser)) }
                    }.setNegativeButton(R.string.later, null).show()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                toast(getString(R.string.release_failed))
            } finally {
                button.isEnabled = true
                button.setText(R.string.check_release)
            }
        }
    }
    private fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_LONG).show()
}
