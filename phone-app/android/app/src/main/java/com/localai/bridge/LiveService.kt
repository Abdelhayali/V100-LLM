package com.localai.bridge

import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.localai.bridge.data.Api
import com.localai.bridge.data.Prefs
import java.io.File
import java.io.RandomAccessFile
import java.util.concurrent.LinkedBlockingQueue
import kotlin.concurrent.thread

/**
 * Live meeting: records 16 kHz mono audio and sends it to the PC in 20-second WAV pieces while it keeps recording,
 * so the transcript appears during the meeting. Keeps going with the screen off.
 */
class LiveService : Service() {
    companion object {
        private const val CH = "live_meeting"
        private const val RATE = 16000
        private const val PIECE_SEC = 20
        @Volatile var running = false
            private set
        @Volatile var meetingId = ""
            private set
        @Volatile var startedAt = 0L
            private set
        @Volatile var piecesSent = 0
            private set
        @Volatile var lastError = ""

        fun start(ctx: Context, id: String) {
            if (running) return
            ContextCompat.startForegroundService(ctx, Intent(ctx, LiveService::class.java).putExtra("id", id))
        }
        fun stop(ctx: Context) = ctx.stopService(Intent(ctx, LiveService::class.java))
    }

    @Volatile private var stopFlag = false
    private val outbox = LinkedBlockingQueue<Triple<File, Int, Double>>()

    override fun onBind(intent: Intent?): IBinder? = null

    @SuppressLint("MissingPermission")
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val id = intent?.getStringExtra("id").orEmpty()
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH, "Live meeting", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 11, Intent(this, MainActivity::class.java).putExtra("widget_action", "live"),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(this, CH).setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Live meeting: recording").setContentText("Live transcript on your PC · tap to open")
            .setOngoing(true).setUsesChronometer(true).setContentIntent(open).build()
        if (Build.VERSION.SDK_INT >= 30) startForeground(52, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE) else startForeground(52, n)
        if (id.isBlank()) { stopSelf(); return START_NOT_STICKY }
        meetingId = id; running = true; startedAt = System.currentTimeMillis(); piecesSent = 0; lastError = ""
        val prefs = Prefs(this)
        val api = Api(prefs.serverUrl, prefs.token)
        thread(isDaemon = true) { record() }
        thread(isDaemon = true) {                         // uploader: pieces go out in order, retried if the network drops
            while (!stopFlag || outbox.isNotEmpty()) {
                val (f, idx, off) = outbox.poll(500, java.util.concurrent.TimeUnit.MILLISECONDS) ?: continue
                var ok = false
                repeat(5) { if (!ok) ok = runCatching { api.uploadLiveChunkBlocking(id, f, idx, off) }.getOrDefault(false).also { if (!it) Thread.sleep(3000) } }
                if (ok) { piecesSent++; f.delete() } else lastError = "a piece could not be sent (kept on the phone)"
            }
        }
        return START_NOT_STICKY
    }

    @SuppressLint("MissingPermission")
    private fun record() {
        val minBuf = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, RATE, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, RATE * 2))
        val dir = File(filesDir, "live").apply { mkdirs() }
        val buf = ShortArray(RATE / 10)
        var idx = 0
        try {
            rec.startRecording()
            while (!stopFlag) {
                val f = File(dir, "piece_${System.currentTimeMillis()}_$idx.wav")
                val raf = RandomAccessFile(f, "rw").apply { setLength(0); write(ByteArray(44)) }
                var samples = 0L
                val end = System.currentTimeMillis() + PIECE_SEC * 1000
                while (!stopFlag && System.currentTimeMillis() < end) {
                    val n = rec.read(buf, 0, buf.size)
                    if (n > 0) {
                        val bytes = ByteArray(n * 2)
                        for (i in 0 until n) { bytes[2 * i] = (buf[i].toInt() and 0xff).toByte(); bytes[2 * i + 1] = (buf[i].toInt() shr 8).toByte() }
                        raf.write(bytes); samples += n
                    }
                }
                writeHeader(raf, samples)
                raf.close()
                if (samples > RATE) outbox.put(Triple(f, idx, idx * PIECE_SEC.toDouble())) else f.delete()
                idx++
            }
        } catch (e: Exception) { lastError = "recording failed: ${e.message}" }
        runCatching { rec.stop() }; rec.release()
    }

    private fun writeHeader(raf: RandomAccessFile, samples: Long) {
        val data = samples * 2
        fun le32(v: Long) = byteArrayOf(v.toByte(), (v shr 8).toByte(), (v shr 16).toByte(), (v shr 24).toByte())
        fun le16(v: Int) = byteArrayOf(v.toByte(), (v shr 8).toByte())
        raf.seek(0)
        raf.write("RIFF".toByteArray()); raf.write(le32(36 + data)); raf.write("WAVEfmt ".toByteArray())
        raf.write(le32(16)); raf.write(le16(1)); raf.write(le16(1)); raf.write(le32(RATE.toLong())); raf.write(le32(RATE * 2L))
        raf.write(le16(2)); raf.write(le16(16)); raf.write("data".toByteArray()); raf.write(le32(data))
    }

    override fun onDestroy() {
        stopFlag = true
        Thread.sleep(300)
        running = false
        super.onDestroy()
    }
}
