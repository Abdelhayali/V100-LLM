package com.localai.bridge

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.localai.bridge.data.Api
import com.localai.bridge.data.NotifyEvent
import com.localai.bridge.data.Prefs
import com.localai.bridge.data.notifyFeed
import java.util.concurrent.TimeUnit

/**
 * Every 15 minutes (Android's minimum for background work), even with the app closed: ask the PC for new events -
 * finished scheduled tasks and temperature alerts - and show them as notifications. Also refreshes the home-screen
 * widget. When the app is open, MainViewModel checks the same feed every 30 s.
 */
class NotifyWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    companion object {
        const val CH_EVENTS = "pc_events"

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<NotifyWorker>(15, TimeUnit.MINUTES).build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork("pc-events", ExistingPeriodicWorkPolicy.KEEP, req)
        }

        /** Show events newer than the last one shown; returns how many. */
        suspend fun check(ctx: Context): Int {
            val prefs = Prefs(ctx)
            if (!prefs.isPaired) return 0
            val feed = Api(prefs.serverUrl, prefs.token).notifyFeed(prefs.lastNotifyId)
            if (prefs.lastNotifyId == 0) {            // first run: start from now, do not replay old events
                prefs.lastNotifyId = feed.lastId; return 0
            }
            feed.events.forEach { show(ctx, it) }
            if (feed.lastId > prefs.lastNotifyId) prefs.lastNotifyId = feed.lastId
            return feed.events.size
        }

        fun show(ctx: Context, e: NotifyEvent) {
            val nm = ctx.getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(android.app.NotificationChannel(CH_EVENTS, "Scheduled tasks and alerts",
                NotificationManager.IMPORTANCE_HIGH).apply { description = "Finished scheduled tasks and temperature alerts" })
            val open = Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                .putExtra("open_session", e.sessionId.orEmpty())
            val pi = PendingIntent.getActivity(ctx, e.id, open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val n = NotificationCompat.Builder(ctx, CH_EVENTS)
                .setSmallIcon(if (e.kind == "temp") android.R.drawable.stat_sys_warning else android.R.drawable.stat_notify_chat)
                .setContentTitle(e.title).setContentText(e.body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(e.body))
                .setAutoCancel(true).setContentIntent(pi).setPriority(NotificationCompat.PRIORITY_HIGH)
                .setDefaults(NotificationCompat.DEFAULT_ALL).build()
            runCatching { nm.notify(1000 + e.id, n) }
        }
    }

    override suspend fun doWork(): Result {
        runCatching { check(applicationContext) }
        runCatching { GpuWidget.refreshAll(applicationContext) }
        return Result.success()
    }
}
