package com.localai.bridge

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import java.io.File

/** Records a meeting / voice note (AAC .m4a, small enough to upload) and keeps going with the screen off. */
class RecordService : Service() {
    companion object {
        private const val CH = "recording"
        @Volatile var recording = false
            private set
        @Volatile var startedAt = 0L
            private set
        @Volatile var file: File? = null
            private set

        fun start(ctx: Context) {
            if (recording) return
            ContextCompat.startForegroundService(ctx, Intent(ctx, RecordService::class.java))
        }

        /** Stops and returns the recording (null if nothing was recorded). */
        fun stop(ctx: Context): File? {
            val f = file
            ctx.stopService(Intent(ctx, RecordService::class.java))
            return f
        }
    }

    private var rec: MediaRecorder? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH, "Recording a voice note", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 9, Intent(this, MainActivity::class.java).putExtra("widget_action", "notes"),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(this, CH).setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Recording a voice note").setContentText("Tap to open and stop").setOngoing(true)
            .setUsesChronometer(true).setContentIntent(open).build()
        if (Build.VERSION.SDK_INT >= 30) startForeground(51, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        else startForeground(51, n)
        val dir = File(filesDir, "voice").apply { mkdirs() }
        val f = File(dir, "note_${System.currentTimeMillis()}.m4a")
        try {
            val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this) else @Suppress("DEPRECATION") MediaRecorder()
            r.setAudioSource(MediaRecorder.AudioSource.MIC)
            r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            r.setAudioChannels(1)
            r.setAudioSamplingRate(16000)
            r.setAudioEncodingBitRate(48000)            // ~22 MB per hour: fits the tunnel's upload limit
            r.setOutputFile(f.absolutePath)
            r.prepare(); r.start()
            rec = r; file = f; recording = true; startedAt = System.currentTimeMillis()
        } catch (e: Exception) {
            recording = false; file = null
            stopSelf()
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        runCatching { rec?.stop() }
        runCatching { rec?.release() }
        rec = null
        recording = false
        super.onDestroy()
    }
}
