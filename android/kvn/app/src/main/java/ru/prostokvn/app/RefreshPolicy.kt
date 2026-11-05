package ru.prostokvn.app

import java.util.concurrent.TimeUnit

object RefreshPolicy {
    val intervalMillis: Long = TimeUnit.HOURS.toMillis(6)
    fun isDue(lastChecked: Long, now: Long): Boolean =
        lastChecked <= 0 || now < lastChecked || now - lastChecked >= intervalMillis
}
