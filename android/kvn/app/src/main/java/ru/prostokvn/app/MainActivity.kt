package ru.prostokvn.app

import android.app.AlertDialog
import android.os.Bundle
import android.widget.Button
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

/** Status dashboard: never claims traffic interception before an engine exists. */
class MainActivity : ComponentActivity() {
    private lateinit var rules: TextView
    private lateinit var checkStatus: TextView
    private lateinit var refresh: Button
    private var loading = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightStatusBars = true
        WindowCompat.getInsetsController(window, window.decorView).isAppearanceLightNavigationBars = true
        setContentView(R.layout.activity_main)
        for (id in listOf(R.id.connection_heading, R.id.rules_heading, R.id.updates_heading)) {
            ViewCompat.setAccessibilityHeading(findViewById(id), true)
        }
        val root = findViewById<android.view.View>(R.id.root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        rules = findViewById(R.id.rules_details)
        checkStatus = findViewById(R.id.check_status)
        refresh = findViewById(R.id.refresh_rules)
        refresh.setOnClickListener { PolicyRefreshWorker.requestNow(this) }
        findViewById<Button>(R.id.check_release).setOnClickListener { checkRelease() }
        val manager = WorkManager.getInstance(this)
        manager.getWorkInfosForUniqueWorkLiveData(PolicyRefreshWorker.ON_DEMAND).observe(this) { work ->
            loading = work.any { !it.state.isFinished }
            refresh.isEnabled = !loading
            refresh.setText(if (loading) R.string.rules_waiting else R.string.refresh_rules)
            renderRules()
        }
        manager.getWorkInfosForUniqueWorkLiveData(PolicyRefreshWorker.PERIODIC_STATUS).observe(this) {
            if (it.none { info -> info.state == WorkInfo.State.RUNNING }) renderRules()
        }
        lifecycleScope.launch {
            withContext(Dispatchers.IO) { PolicyStore(this@MainActivity).ensureBundled() }
            PolicyRefreshWorker.configure(this@MainActivity)
            renderRules()
        }
    }

    override fun onResume() {
        super.onResume()
        if (::rules.isInitialized) {
            PolicyRefreshWorker.configure(this)
            renderRules()
        }
    }

    private fun renderRules() {
        lifecycleScope.launch {
            val snapshot = withContext(Dispatchers.IO) { PolicyStore(this@MainActivity).current() }
            if (snapshot == null) {
                rules.text = getString(R.string.no_rules)
                findViewById<TextView>(R.id.direct_count).setText(R.string.number_na)
                findViewById<TextView>(R.id.proxy_count).setText(R.string.number_na)
                findViewById<TextView>(R.id.block_count).setText(R.string.number_na)
            } else {
                val files = snapshot.manifest.getJSONObject("files")
                rules.text = getString(R.string.rules_summary, snapshot.version)
                findViewById<TextView>(R.id.direct_count).text = files.getJSONObject("direct.txt").getInt("domains").toString()
                findViewById<TextView>(R.id.proxy_count).text = files.getJSONObject("proxy.txt").getInt("domains").toString()
                findViewById<TextView>(R.id.block_count).text = files.getJSONObject("block.txt").getInt("domains").toString()
            }
            val prefs = getSharedPreferences("routing_updater", MODE_PRIVATE)
            val checked = prefs.getLong("lastChecked", 0)
            val last = if (checked == 0L) getString(R.string.not_checked) else
                DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(checked))
            checkStatus.text = getString(R.string.check_summary, last,
                if (prefs.contains("lastError")) getString(R.string.cached_after_error) else "")
        }
    }

    private fun checkRelease() {
        val button = findViewById<Button>(R.id.check_release)
        button.isEnabled = false
        button.setText(R.string.checking_release)
        lifecycleScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { AppRelease.check(this@MainActivity) }
                if (result == null) toast(R.string.no_release) else AlertDialog.Builder(this@MainActivity)
                    .setTitle(getString(R.string.new_release, result.label))
                    .setMessage(R.string.release_consent)
                    .setPositiveButton(R.string.open_release) { _, _ ->
                        try { AppRelease.openTrustedRelease(this@MainActivity, result) }
                        catch (_: android.content.ActivityNotFoundException) { toast(R.string.no_browser) }
                    }
                    .setNegativeButton(R.string.later, null).show()
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                toast(R.string.release_failed)
            } finally {
                button.isEnabled = true
                button.setText(R.string.check_release)
            }
        }
    }

    private fun toast(message: Int) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()
}
