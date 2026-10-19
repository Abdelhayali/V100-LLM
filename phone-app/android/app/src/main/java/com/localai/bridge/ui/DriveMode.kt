package com.localai.bridge.ui

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * Hands-free loop for driving: listen -> send the question -> the reply is read aloud -> listen again.
 * Voice commands: "stop" / "stop driving" / "توقف" end it, "new chat" / "محادثة جديدة" starts a fresh chat.
 * Uses the phone's speech recognizer directly (no pop-up), so nothing has to be touched once it runs.
 */
class DriveMode(private val ctx: Context, private val events: Events) {
    interface Events {
        fun onState(state: String)            // listening | thinking | speaking | off
        fun onHeard(text: String)
        fun onCommand(cmd: String)            // stop | new
        fun onQuestion(text: String)
        fun onProblem(message: String)
    }

    private val main = Handler(Looper.getMainLooper())
    private var rec: SpeechRecognizer? = null
    private val beep = runCatching { ToneGenerator(AudioManager.STREAM_MUSIC, 70) }.getOrNull()
    var active = false
        private set
    var language = ""                          // "" = phone default, else e.g. "ar-EG", "en-US"

    fun available() = SpeechRecognizer.isRecognitionAvailable(ctx)

    fun start() { active = true; listen() }

    fun stop() {
        active = false
        main.removeCallbacksAndMessages(null)
        main.post { rec?.cancel(); rec?.destroy(); rec = null }
        events.onState("off")
    }

    /** Start listening again (after a reply was read, or after silence). */
    fun listen(delayMs: Long = 250) {
        if (!active) return
        main.removeCallbacksAndMessages(null)
        main.postDelayed({ doListen() }, delayMs)
    }

    private fun doListen() {
        if (!active) return
        val r = rec ?: SpeechRecognizer.createSpeechRecognizer(ctx).also { rec = it; it.setRecognitionListener(listener) }
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, ctx.packageName)
            .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
            .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
        if (language.isNotBlank()) i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
        runCatching { r.startListening(i) }.onFailure { events.onProblem("Speech recognizer failed: ${it.message}"); listen(1500) }
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            beep?.startTone(ToneGenerator.TONE_PROP_BEEP, 120)   // you can speak now
            events.onState("listening")
        }
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onPartialResults(partialResults: Bundle?) {}
        override fun onEvent(eventType: Int, params: Bundle?) {}

        override fun onError(error: Int) {
            if (!active) return
            when (error) {
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> { events.onProblem("Microphone permission is needed"); stop() }
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> { rec?.destroy(); rec = null; listen(800) }
                SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> listen(150)   // silence: keep listening
                else -> listen(1200)
            }
        }

        override fun onResults(results: Bundle?) {
            if (!active) return
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty().trim()
            if (text.isBlank()) { listen(150); return }
            events.onHeard(text)
            val t = text.lowercase().trim(' ', '.', '!', '؟', '?')
            when {
                t in STOP -> events.onCommand("stop")
                t in NEW -> events.onCommand("new")
                else -> { events.onState("thinking"); events.onQuestion(text) }
            }
        }
    }

    companion object {
        val STOP = setOf("stop", "stop driving", "stop driving mode", "exit", "goodbye", "توقف", "إيقاف", "ايقاف", "اوقف",
            "أوقف", "خلاص", "انهاء", "إنهاء")
        val NEW = setOf("new chat", "new conversation", "start over", "محادثة جديدة", "محادثه جديده", "دردشة جديدة")
    }
}
