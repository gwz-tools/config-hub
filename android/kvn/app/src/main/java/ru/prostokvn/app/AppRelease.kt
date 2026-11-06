package ru.prostokvn.app

import android.content.Context
import android.content.Intent
import androidx.core.net.toUri
import androidx.core.content.pm.PackageInfoCompat
import java.net.HttpURLConnection
import java.net.URL

/** In-app release check, NOT silent APK installer. Uses official GitHub release page only. */
object AppRelease {
    const val METADATA = "https://raw.githubusercontent.com/gwz-tools/config-hub/main/app-release.json"

    fun check(context: Context): ReleaseMetadata.NewRelease? {
        val c = URL(METADATA).openConnection() as HttpURLConnection
        c.connectTimeout = 8_000
        c.readTimeout = 8_000
        c.instanceFollowRedirects = false
        return try {
            require(c.responseCode == 200)
            val bytes = c.inputStream.use { stream ->
                val out = java.io.ByteArrayOutputStream()
                val buf = ByteArray(2048)
                while (true) {
                    val n = stream.read(buf)
                    if (n < 0) break
                    require(out.size() + n <= 8192)
                    out.write(buf, 0, n)
                }
                out.toByteArray()
            }
            val installed = PackageInfoCompat.getLongVersionCode(
                context.packageManager.getPackageInfo(context.packageName, 0))
            ReleaseMetadata.available(bytes, installed) { page ->
                val releaseConnection = URL(page).openConnection() as HttpURLConnection
                releaseConnection.requestMethod = "HEAD"
                releaseConnection.connectTimeout = 8_000
                releaseConnection.readTimeout = 8_000
                releaseConnection.instanceFollowRedirects = false
                try { releaseConnection.responseCode } finally { releaseConnection.disconnect() }
            }
        } finally { c.disconnect() }
    }

    fun openTrustedRelease(context: Context, release: ReleaseMetadata.NewRelease) {
        require(ReleaseMetadata.isTrustedPage(release.page))
        // Android requires user consent and matching APK signing key for update.
        context.startActivity(Intent(Intent.ACTION_VIEW, release.page.toUri()).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        })
    }
}
