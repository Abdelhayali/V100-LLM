package com.localai.bridge.data

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import java.security.KeyStore
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * The private vault's key: 32 random bytes, kept on this phone wrapped by an Android Keystore key that can only be used
 * right after a fingerprint / face check. The PC gets the key only while the vault is unlocked and never stores it.
 * The recovery code is the same key in text form, to open the vault on a new phone.
 */
object VaultKey {
    private const val ALIAS = "localai_vault_wrap"
    private const val PREF = "vault_wrapped"

    fun canUseBiometric(ctx: Context) = BiometricManager.from(ctx)
        .canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) == BiometricManager.BIOMETRIC_SUCCESS

    fun hasKey(ctx: Context) = ctx.getSharedPreferences("vault", 0).contains(PREF)

    private fun wrapKey(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).setUserAuthenticationRequired(true).setInvalidatedByBiometricEnrollment(false)
            .apply {
                if (Build.VERSION.SDK_INT >= 30) setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
                else @Suppress("DEPRECATION") setUserAuthenticationValidityDurationSeconds(-1)
            }.build()
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply { init(spec) }.generateKey()
    }

    /**
     * Ask for the fingerprint and return the vault key (base64). The first time a new key is made (or [restore] is used).
     */
    fun unlock(activity: FragmentActivity, restore: ByteArray? = null, onKey: (String) -> Unit, onError: (String) -> Unit) {
        val prefs = activity.getSharedPreferences("vault", 0)
        val stored = prefs.getString(PREF, null)
        val creating = stored == null || restore != null
        val cipher = try {
            Cipher.getInstance("AES/GCM/NoPadding").apply {
                if (creating) init(Cipher.ENCRYPT_MODE, wrapKey())
                else {
                    val raw = Base64.decode(stored, Base64.NO_WRAP)
                    init(Cipher.DECRYPT_MODE, wrapKey(), GCMParameterSpec(128, raw.copyOfRange(0, 12)))
                }
            }
        } catch (e: Exception) { onError("Keystore error: ${e.message}"); return }
        val prompt = BiometricPrompt(activity, ContextCompat.getMainExecutor(activity), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                val c = result.cryptoObject?.cipher ?: return onError("no cipher")
                try {
                    if (creating) {
                        val key = restore ?: ByteArray(32).also { SecureRandom().nextBytes(it) }
                        val ct = c.doFinal(key)
                        prefs.edit().putString(PREF, Base64.encodeToString(c.iv + ct, Base64.NO_WRAP)).apply()
                        onKey(Base64.encodeToString(key, Base64.NO_WRAP))
                    } else {
                        val raw = Base64.decode(stored, Base64.NO_WRAP)
                        onKey(Base64.encodeToString(c.doFinal(raw.copyOfRange(12, raw.size)), Base64.NO_WRAP))
                    }
                } catch (e: Exception) { onError("Could not open the vault key: ${e.message}") }
            }
            override fun onAuthenticationError(code: Int, msg: CharSequence) = onError(msg.toString())
        })
        prompt.authenticate(BiometricPrompt.PromptInfo.Builder().setTitle("Private vault")
            .setSubtitle(if (creating) "Create the vault key" else "Unlock your private chats")
            .setNegativeButtonText("Cancel").setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG).build(),
            BiometricPrompt.CryptoObject(cipher))
    }

    /** The key as a recovery code (groups of 4 characters). */
    fun recoveryCode(keyB64: String): String =
        Base64.decode(keyB64, Base64.NO_WRAP).joinToString("") { "%02x".format(it) }.chunked(4).joinToString("-")

    fun parseRecovery(code: String): ByteArray? {
        val hex = code.filter { it.isLetterOrDigit() }.lowercase()
        if (hex.length != 64 || !hex.all { it in "0123456789abcdef" }) return null
        return ByteArray(32) { hex.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    }
}
