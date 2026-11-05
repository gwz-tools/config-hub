package ru.prostokvn.app

import kotlinx.coroutines.flow.MutableStateFlow

/** In-process state comes only from VPN service events, never persisted as Connected. */
object VpnState {
    enum class Phase { OFF, STARTING, ON, STOPPING, ERROR }
    data class Status(val phase: Phase, val detail: String = "")
    val value = MutableStateFlow(Status(Phase.OFF))
    fun update(phase: Phase, detail: String = "") { value.value = Status(phase, detail) }
}
