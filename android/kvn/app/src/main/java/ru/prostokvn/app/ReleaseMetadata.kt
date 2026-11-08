package ru.prostokvn.app

import org.json.JSONObject
import java.net.URI

object ReleaseMetadata {
    data class NewRelease(val versionCode: Long, val label: String, val page: String)

    fun available(bytes: ByteArray, installedCode: Long, pageStatus: (String) -> Int): NewRelease? {
        val next = parse(bytes, installedCode) ?: return null
        require(pageStatus(next.page) == 200) { "release page is not published" }
        return next
    }

    fun parse(bytes: ByteArray, installedCode: Long): NewRelease? {
        require(bytes.size <= 8192)
        val json = JSONObject(bytes.toString(Charsets.UTF_8))
        require(json.getInt("schema_version") == 1)
        val code = json.getLong("version_code")
        require(code > 0)
        val label = json.getString("version_name")
        require(label.isNotBlank() && label.length <= 40 && label.none { it.isISOControl() })
        val page = json.getString("release_page")
        require(isTrustedPage(page)) { "untrusted release page" }
        return if (code > installedCode) NewRelease(code, label, page) else null
    }

    fun isTrustedPage(page: String): Boolean = runCatching {
        val uri = URI(page)
        uri.scheme == "https" && uri.host == "github.com" && uri.port == -1 &&
            uri.userInfo == null && uri.rawQuery == null && uri.rawFragment == null &&
            Regex("^/gwz-tools/config-hub/releases/tag/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$").matches(uri.rawPath ?: "")
    }.getOrDefault(false)
}
