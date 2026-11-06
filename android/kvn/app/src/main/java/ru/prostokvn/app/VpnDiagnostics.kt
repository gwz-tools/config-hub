package ru.prostokvn.app

import android.content.Context

/**
 * Only symbolic startup stages and error TYPES are stored.
 * No VLESS URLs, UUIDs, keys, hostnames, SNI, or native log lines are persisted.
 *
 * When Android or the native engine terminates the process without a Java exception,
 * the last "pending" stage remains visible after the user reopens KVN.
 */
object VpnDiagnostics {
    private const val NAME = "kvn_vpn_diagnostics"
    private const val STAGE = "stage"
    private const val PENDING = "pending"
    private const val ERROR = "error_type"
    private const val MESSAGE = "error_message"
    private val validStages = setOf(
        "start", "permissions", "rules", "pool", "config",
        "native_setup", "command_server", "engine_start", "tun_open", "tun", "connected", "stopped"
    )

    fun enter(context: Context, stage: String) {
        val safe = stage.takeIf { it in validStages } ?: "start"
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit()
            .putString(STAGE, safe)
            .putBoolean(PENDING, true)
            .remove(ERROR).remove(MESSAGE)
            .commit()
    }

    fun connected(context: Context) {
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit()
            .putString(STAGE, "connected").putBoolean(PENDING, false).remove(ERROR).remove(MESSAGE).commit()
    }

    fun stopped(context: Context) {
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit()
            .putString(STAGE, "stopped").putBoolean(PENDING, false).remove(ERROR).remove(MESSAGE).commit()
    }

    fun failure(context: Context, error: Throwable) {
        val type = error.javaClass.simpleName.take(48).ifBlank { "UnknownError" }
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit()
            .putBoolean(PENDING, false)
            .putString(ERROR, type)
            .putString(MESSAGE, (error.message ?: error.toString()).take(360))
            .commit()
    }

    /** Human-friendly public diagnostic with no server credentials. */
    fun summary(context: Context): String? {
        val p = context.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        val stage = p.getString(STAGE, "") ?: ""
        val error = p.getString(ERROR, null)
        if (error != null) return "VPN: сбой на этапе $stage ($error): ${p.getString(MESSAGE, "подробности отсутствуют")}"
        return if (p.getBoolean(PENDING, false)) {
            "Предыдущее подключение прервалось на этапе $stage. Перезапустите VPN или отправьте журнал Android."
        } else null
    }
}
