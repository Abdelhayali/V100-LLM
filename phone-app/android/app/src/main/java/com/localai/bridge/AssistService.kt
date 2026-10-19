package com.localai.bridge

import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import android.speech.RecognitionService
import java.io.File

/**
 * LocalAI Bridge as the phone's digital assistant (Settings > Apps > Default apps > Digital assistant app):
 * long-press home (or the assistant gesture) opens the app listening, with a screenshot of what was on the screen
 * attached when "Use screenshot" is on, so you can ask about it.
 */
class AssistService : VoiceInteractionService()

class AssistSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession = AssistSession(this)
}

class AssistSession(private val svc: VoiceInteractionSessionService) : VoiceInteractionSession(svc) {
    private var shot: File? = null
    private var opened = false

    override fun onHandleScreenshot(screenshot: Bitmap?) {
        if (screenshot != null) runCatching {
            val f = File(svc.cacheDir, "assist_${System.currentTimeMillis()}.png")
            f.outputStream().use { screenshot.compress(Bitmap.CompressFormat.PNG, 100, it) }
            shot = f
        }
        open()
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        // the screenshot arrives right after onShow when allowed; wait a moment for it, then open the app
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ open() }, 700)
    }

    private fun open() {
        if (opened) return
        opened = true
        val i = Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            .putExtra("widget_action", "assist")
        shot?.let { i.putExtra("assist_screenshot", it.absolutePath) }
        startAssistantActivity(i)
        hide()
    }
}

/** Android requires an assistant to name a recognition service; the app uses the phone's own recognizer instead. */
class AssistRecognitionService : RecognitionService() {
    override fun onStartListening(recognizerIntent: Intent?, listener: Callback?) {
        runCatching { listener?.error(android.speech.SpeechRecognizer.ERROR_CLIENT) }
    }
    override fun onCancel(listener: Callback?) {}
    override fun onStopListening(listener: Callback?) {}
}
