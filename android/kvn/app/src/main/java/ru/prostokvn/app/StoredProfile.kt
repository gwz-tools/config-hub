package ru.prostokvn.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Private to the application, encrypted by a non-exportable Android Keystore AES key. */
class StoredProfile(private val context: Context) {
    private val prefs = context.getSharedPreferences("kvn_profile", Context.MODE_PRIVATE)
    private val alias = "kvn-vless-profile-v1"
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(alias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build())
        return generator.generateKey()
    }
    fun save(link: String) {
        VlessProfile.parse(link) // Reject bad configurations before replacing the working profile.
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val text = cipher.doFinal(link.trim().toByteArray(Charsets.UTF_8))
        prefs.edit().putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("cipher", Base64.encodeToString(text, Base64.NO_WRAP)).apply()
    }
    fun read(): String? {
        val iv = prefs.getString("iv", null) ?: return null
        val cipherText = prefs.getString("cipher", null) ?: return null
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
        return cipher.doFinal(Base64.decode(cipherText, Base64.NO_WRAP)).toString(Charsets.UTF_8)
    }
    fun summary(): String = try { read()?.let { VlessProfile.parse(it).name } ?: "Профиль не добавлен" }
        catch (_: Exception) { "Профиль повреждён — добавьте его заново" }
    /** AUTO is the default. A pasted personal profile is optional and opt-in. */
    var manualEnabled: Boolean
        get() = prefs.getBoolean("manual_enabled", false)
        set(value) { prefs.edit().putBoolean("manual_enabled", value).apply() }

    var splitRouting: Boolean
        get() = prefs.getBoolean("split_routing", true)
        set(value) { prefs.edit().putBoolean("split_routing", value).apply() }
}
