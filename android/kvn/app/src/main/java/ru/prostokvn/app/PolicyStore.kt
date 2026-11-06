package ru.prostokvn.app

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/** Complete snapshots only; active/previous pointers are swapped on the same filesystem. */
class PolicyStore(private val root: File, private val assetLoader: (String) -> ByteArray) {
    constructor(context: Context) : this(File(context.applicationContext.filesDir, "routing"), { name ->
        context.applicationContext.assets.open("routing/$name").use { it.readBytes() }
    })

    private val versions get() = File(root, "versions")
    private val pointer get() = File(root, "active.json")
    private val previous get() = File(root, "previous.json")
    val files get() = PolicyValidator.files

    data class Snapshot(val version: String, val directory: File, val manifest: JSONObject)

    private fun load(pointerFile: File): Snapshot? = runCatching {
        val name = JSONObject(pointerFile.readText()).getString("version")
        require(Regex("^[a-f0-9]{20}$").matches(name))
        val dir = File(versions, name)
        val manifestFile = File(dir, "manifest.json")
        require(manifestFile.length() <= 64 * 1024)
        val manifest = JSONObject(manifestFile.readText())
        val data = files.associateWith {
            val file = File(dir, it)
            require(file.length() <= 2_000_000)
            file.readBytes()
        }
        require(PolicyValidator.verify(manifest, data) == name) { "pointer/version mismatch" }
        Snapshot(name, dir, manifest)
    }.getOrNull()

    fun current(): Snapshot? = synchronized(lock) {
        load(pointer) ?: load(previous)?.also { writePointer(pointer, it.version) }
    }

    fun verify(manifest: JSONObject, data: Map<String, ByteArray>) {
        PolicyValidator.verify(manifest, data)
    }

    fun ensureBundled(): Snapshot? = synchronized(lock) {
        current() ?: runCatching {
            activate(assetLoader("manifest.json"), files.associateWith(assetLoader))
            current()
        }.getOrNull()
    }

    fun activate(manifestBytes: ByteArray, data: Map<String, ByteArray>): String = synchronized(lock) {
        require(manifestBytes.size <= 64 * 1024)
        val manifest = JSONObject(manifestBytes.toString(Charsets.UTF_8))
        val id = PolicyValidator.verify(manifest, data)
        val old = current()
        if (old?.version == id) return@synchronized id
        check(versions.mkdirs() || versions.isDirectory)
        val staging = Files.createTempDirectory(versions.toPath(), ".pending-$id-").toFile()
        try {
            data.forEach { (name, bytes) -> durableWrite(File(staging, name), bytes) }
            durableWrite(File(staging, "manifest.json"), manifestBytes)
            val target = File(versions, id)
            // A damaged inactive version is replaceable; the active good version is untouched.
            if (target.exists()) check(target.deleteRecursively())
            Files.move(staging.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
            if (old != null) writePointer(previous, old.version)
            writePointer(pointer, id)
            id
        } finally { staging.deleteRecursively() }
    }

    private fun writePointer(target: File, version: String) {
        check(root.mkdirs() || root.isDirectory)
        val pending = File.createTempFile("${target.name}-", ".tmp", root)
        try {
            durableWrite(pending, JSONObject().put("version", version).toString().toByteArray())
            Files.move(pending.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        } finally { pending.delete() }
    }

    private fun durableWrite(file: File, bytes: ByteArray) {
        FileOutputStream(file).use { output -> output.write(bytes); output.fd.sync() }
    }

    companion object {
        private val lock = Any()
        fun sha256(value: ByteArray): String = PolicyValidator.sha256(value)
    }
}
