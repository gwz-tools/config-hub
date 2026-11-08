package ru.prostokvn.app

import android.content.Context
import androidx.core.content.edit
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit
import java.util.concurrent.CancellationException

class PolicyRefreshWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        // Periodic and manual jobs share a transaction lock: never overwrite a newer job's ETag.
        refreshMutex.withLock {
            val prefs = applicationContext.getSharedPreferences("routing_updater", Context.MODE_PRIVATE)
            try {
                val result = PolicyUpdater(PolicyStore(applicationContext)).refresh(
                    prefs.getString("etag", null), prefs.getString("etagVersion", null))
                prefs.edit {
                    putString("etag", result.etag)
                    putString("etagVersion", result.version)
                    putLong("lastChecked", System.currentTimeMillis())
                    remove("lastError")
                }
                // No VPN reload: a tunnel engine does not exist in this test build.
                Result.success()
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                prefs.edit { putString("lastError", error.javaClass.simpleName) }
                if (runAttemptCount < 3) Result.retry() else Result.failure()
            }
        }
    }

    companion object {
        private val refreshMutex = Mutex()
        private const val PERIODIC = "gwzhub-routing-periodic"
        const val ON_DEMAND = "gwzhub-routing-on-demand"
        const val PERIODIC_STATUS = PERIODIC
        fun configure(context: Context) {
            val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
            val periodic = PeriodicWorkRequestBuilder<PolicyRefreshWorker>(6, TimeUnit.HOURS)
                .setConstraints(network)
                .setInitialDelay(6, TimeUnit.HOURS)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC, ExistingPeriodicWorkPolicy.KEEP, periodic)
            val prefs = context.getSharedPreferences("routing_updater", Context.MODE_PRIVATE)
            if (RefreshPolicy.isDue(prefs.getLong("lastChecked", 0), System.currentTimeMillis())) requestNow(context)
        }
        fun requestNow(context: Context) {
            val request = OneTimeWorkRequestBuilder<PolicyRefreshWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(ON_DEMAND, ExistingWorkPolicy.KEEP, request)
        }
    }
}
