package com.localai.bridge.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** Server URL and token, encrypted at rest with an Android Keystore key. */
class Prefs(context: Context) {
    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "bridge_secure",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    var serverUrl: String
        get() = prefs.getString("url", "") ?: ""
        set(v) = prefs.edit().putString("url", v).apply()

    var token: String
        get() = prefs.getString("token", "") ?: ""
        set(v) = prefs.edit().putString("token", v).apply()

    var lastSession: String
        get() = prefs.getString("last_session", "") ?: ""
        set(v) = prefs.edit().putString("last_session", v).apply()

    var themeMode: String
        get() = prefs.getString("theme", "system") ?: "system"
        set(v) = prefs.edit().putString("theme", v).apply()

    var webSearch: Boolean
        get() = prefs.getBoolean("web_search", false)
        set(v) = prefs.edit().putBoolean("web_search", v).apply()

    var autoApprove: Boolean
        get() = prefs.getBoolean("auto_approve", false)
        set(v) = prefs.edit().putBoolean("auto_approve", v).apply()

    /** Summarize old messages automatically when the context gets full. */
    var autoCompress: Boolean
        get() = prefs.getBoolean("auto_compress", true)
        set(v) = prefs.edit().putBoolean("auto_compress", v).apply()

    /** Context usage (percent) that triggers auto-compression. */
    var compressAt: Int
        get() = prefs.getInt("compress_at", 75)
        set(v) = prefs.edit().putInt("compress_at", v).apply()

    val isPaired get() = serverUrl.isNotBlank() && token.isNotBlank()

    fun clear() = prefs.edit().clear().apply()
}
