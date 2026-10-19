package com.localai.bridge

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/**
 * While a reply runs on the PC and the app is in the background, Android may suspend the app and its connection.
 * This small foreground service keeps watch (one light request every 4 s) and posts "Reply ready" when the PC is done,
 * then stops. It only runs while a reply is in progress.
 */
class ReplyWatchService : Service() {
    companion object {
        private const val CH_WAIT = "reply_wait"
        const val CH_DONE = "reply_done"
        private const val ID_WAIT = 41
        private const val ID_DONE = 42
        @Volatile private var running = false

        fun start(ctx: Context, url: String, token: String, sessionId: String, title: String) {
            if (running) return
            val i = Intent(ctx, ReplyWatchService::class.java)
                .putExtra("url", url).putExtra("token", token).putExtra("sid", sessionId).putExtra("title", title)
            runCatching { ContextCompat.startForegroundService(ctx, i) }
        }

        fun stop(ctx: Context) { if (running) ctx.stopService(Intent(ctx, ReplyWatchService::class.java)) }

        fun channels(ctx: Context) {
            val nm = ctx.getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(CH_WAIT, "Reply in progress", NotificationManager.IMPORTANCE_LOW)
                .apply { description = "Shown while your PC is still writing a reply" })
            nm.createNotificationChannel(NotificationChannel(CH_DONE, "Reply finished", NotificationManager.IMPORTANCE_HIGH)
                .apply { description = "When a reply is ready while the app is in the background" })
        }
    }

    @Volatile private var stopFlag = false

    override fun onBind(intent: Intent?): IBinder? = null

    private fun openApp(): PendingIntent = PendingIntent.getActivity(
        this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        channels(this)
        val url = intent?.getStringExtra("url").orEmpty().trimEnd('/')
        val token = intent?.getStringExtra("token").orEmpty()
        val sid = intent?.getStringExtra("sid").orEmpty()
        val title = intent?.getStringExtra("title").orEmpty().ifBlank { "Chat" }
        val wait: Notification = NotificationCompat.Builder(this, CH_WAIT)
            .setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("Your PC is writing a reply")
            .setContentText(title).setOngoing(true).setContentIntent(openApp()).build()
        if (Build.VERSION.SDK_INT >= 29) startForeground(ID_WAIT, wait, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else startForeground(ID_WAIT, wait)
        running = true
        if (url.isEmpty() || sid.isEmpty()) { stopSelf(); return START_NOT_STICKY }
        thread(isDaemon = true) {
            val t0 = System.currentTimeMillis()
            var misses = 0
            while (!stopFlag && System.currentTimeMillis() - t0 < 3 * 3600_000L) {
                Thread.sleep(4_000)
                val state = runCatching { stillRunning(url, token, sid) }.getOrNull()
                if (state == null) { if (++misses > 450) break; continue }   // PC unreachable for a while: give up
                misses = 0
                if (!state) { if (!stopFlag) done(title); break }
            }
            stopSelf()
        }
        return START_NOT_STICKY
    }

    /** true = still writing, false = finished; throws if the PC cannot be reached. */
    private fun stillRunning(url: String, token: String, sid: String): Boolean {
        val c = URL("$url/api/sessions/$sid").openConnection() as HttpURLConnection
        c.setRequestProperty("Authorization", "Bearer $token")
        c.connectTimeout = 10_000; c.readTimeout = 20_000
        try {
            if (c.responseCode == 404) return false
            val body = c.inputStream.bufferedReader().readText()
            return Regex("\"running\"\\s*:\\s*true").containsMatchIn(body)
        } finally { c.disconnect() }
    }

    private fun done(title: String) {
        val n = NotificationCompat.Builder(this, CH_DONE)
            .setSmallIcon(android.R.drawable.stat_notify_chat).setContentTitle("Reply ready")
            .setContentText(title).setAutoCancel(true).setContentIntent(openApp())
            .setPriority(NotificationCompat.PRIORITY_HIGH).setDefaults(NotificationCompat.DEFAULT_ALL).build()
        runCatching { getSystemService(NotificationManager::class.java).notify(ID_DONE, n) }
    }

    override fun onDestroy() {
        stopFlag = true
        running = false
        super.onDestroy()
    }
}
