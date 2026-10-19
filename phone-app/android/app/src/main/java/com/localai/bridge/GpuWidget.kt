package com.localai.bridge

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import com.localai.bridge.data.Api
import com.localai.bridge.data.Prefs
import com.localai.bridge.data.v100Status
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** Home-screen widget: what the PC's GPU is doing (model, VRAM, temperatures) and quick Ask / Voice buttons. */
class GpuWidget : AppWidgetProvider() {
    companion object {
        private const val REFRESH = "com.localai.bridge.WIDGET_REFRESH"

        fun refreshAll(ctx: Context) {
            val mgr = AppWidgetManager.getInstance(ctx)
            val ids = mgr.getAppWidgetIds(ComponentName(ctx, GpuWidget::class.java))
            if (ids.isEmpty()) return
            val prefs = Prefs(ctx)
            CoroutineScope(Dispatchers.IO).launch {
                val text = if (!prefs.isPaired) "Open the app and pair with your PC" else runCatching {
                    val s = Api(prefs.serverUrl, prefs.token).v100Status()
                    if (!s.launcher) "Launcher not running on the PC" else buildString {
                        append(if (s.health == "stopped") "No model loaded" else s.modelName.ifBlank { s.model })
                        if (s.health == "loading") append(" (loading)")
                        append("\nVRAM %.1f / %.1f GB".format(s.vramUsedMb / 1024.0, s.vramTotalMb / 1024.0))
                        s.gpuTemp?.let { append(" · GPU %.0f °C".format(it)) }
                        s.cpuTemp?.let { append(" · CPU %.0f °C".format(it)) }
                    }
                }.getOrElse { "PC not reachable" }
                ids.forEach { mgr.updateAppWidget(it, views(ctx, text)) }
            }
        }

        private fun views(ctx: Context, status: String) = RemoteViews(ctx.packageName, R.layout.widget_gpu).apply {
            setTextViewText(R.id.widget_status, status)
            setTextViewText(R.id.widget_time, java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(java.util.Date()))
            fun open(code: Int, action: String) = PendingIntent.getActivity(ctx, code,
                Intent(ctx, MainActivity::class.java).putExtra("widget_action", action)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            setOnClickPendingIntent(R.id.widget_ask, open(1, "ask"))
            setOnClickPendingIntent(R.id.widget_voice, open(2, "voice"))
            setOnClickPendingIntent(R.id.widget_refresh, PendingIntent.getBroadcast(ctx, 3,
                Intent(ctx, GpuWidget::class.java).setAction(REFRESH), PendingIntent.FLAG_IMMUTABLE))
            setOnClickPendingIntent(R.id.widget_status, open(4, "models"))
        }
    }

    override fun onUpdate(ctx: Context, mgr: AppWidgetManager, ids: IntArray) {
        ids.forEach { mgr.updateAppWidget(it, views(ctx, "…")) }
        refreshAll(ctx)
    }

    override fun onReceive(ctx: Context, intent: Intent) {
        super.onReceive(ctx, intent)
        if (intent.action == REFRESH) refreshAll(ctx)
    }
}
