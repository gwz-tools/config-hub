package ru.prostokvn.app

import org.junit.Assert.*
import org.junit.Test

class ReleaseTests {
    private fun metadata(code: Long = 3, page: String = "https://github.com/gwz-tools/config-hub/releases/tag/v0.1.2") =
        """{"schema_version":1,"version_code":$code,"version_name":"0.1.2","release_page":"$page"}""".toByteArray()

    @Test fun newerOfficialReleaseIsOffered() { assertEquals(3L, ReleaseMetadata.parse(metadata(), 2)?.versionCode) }
    @Test fun publishedNewerReleaseIsOffered() {
        assertEquals(3L, ReleaseMetadata.available(metadata(), 2) { 200 }?.versionCode)
    }
    @Test fun missingNewerReleaseIsRejected() {
        assertThrows(Exception::class.java) { ReleaseMetadata.available(metadata(), 2) { 404 } }
    }
    @Test fun redirectedNewerReleaseIsRejected() {
        assertThrows(Exception::class.java) { ReleaseMetadata.available(metadata(), 2) { 302 } }
    }
    @Test fun oldVersionDoesNotFetchReleasePage() {
        assertNull(ReleaseMetadata.available(metadata(1), 2) { fail("must not request an older page"); 500 })
    }
    @Test fun currentOrOlderVersionIsNotOffered() { assertNull(ReleaseMetadata.parse(metadata(2), 2)); assertNull(ReleaseMetadata.parse(metadata(1), 2)) }
    @Test fun maliciousReleasePagesRejected() {
        for (page in listOf(
            "http://github.com/gwz-tools/config-hub/releases/tag/v1",
            "https://github.com.evil.org/gwz-tools/config-hub/releases/tag/v1",
            "https://github.com/other/repo/releases/tag/v1",
            "https://github.com/gwz-tools/config-hub/releases/tag/../v1",
            "https://github.com/gwz-tools/config-hub/releases/tag/%2E%2E",
            "https://github.com:8443/gwz-tools/config-hub/releases/tag/v1",
            "https://user@github.com/gwz-tools/config-hub/releases/tag/v1",
            "https://github.com/gwz-tools/config-hub/releases/tag/v1?redirect=bad",
            "https://github.com/gwz-tools/config-hub/releases/tag/v1#bad")) {
            assertFalse(page, ReleaseMetadata.isTrustedPage(page))
            assertThrows(Exception::class.java) { ReleaseMetadata.parse(metadata(page = page), 2) }
        }
    }
    @Test fun oversizedMetadataRejected() { assertThrows(Exception::class.java) { ReleaseMetadata.parse(ByteArray(8193), 2) } }
    @Test fun malformedMetadataRejected() { assertThrows(Exception::class.java) { ReleaseMetadata.parse("bad".toByteArray(), 2) } }
}
