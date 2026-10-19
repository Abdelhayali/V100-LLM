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
 * Voice commands: "stop" / "توقف" end it, "new chat" / "محادثة جديدة" starts a fresh chat.
 *
 * Listens in the chosen language (Arabic by default) with the other one allowed where the phone supports language
 * detection: a recognizer set to English cannot understand Arabic, kept failing and beeping. It beeps once per turn,
 * not on every silent restart.
 */
class DriveMode(private val ctx: Context, private val events: Events) {
    interface Events {
        fun onState(state: String)            // listening | thinking | speaking | off
        fun onHeard(text: String)
        fun onCommand(cmd: String)            // stop | new | interrupt
        fun onQuestion(text: String)
        fun onProblem(message: String)
    }

    private val main = Handler(Looper.getMainLooper())
    private var rec: SpeechRecognizer? = null
    private val beep = runCatching { ToneGenerator(AudioManager.STREAM_MUSIC, 60) }.getOrNull()
    private var beepNext = false                 // beep when the next listening session is ready (once per turn)
    private var failures = 0
    var active = false
        private set
    var language = "ar-EG"                       // main language; the other one is allowed when the phone can detect it
    var bargeIn = false                          // listen for "stop" while the reply is read (Settings, off by default)
    private var interruptMode = false

    fun available() = SpeechRecognizer.isRecognitionAvailable(ctx)

    fun start() { active = true; failures = 0; listen(fromTurn = true, delayMs = 1800) }   // after the spoken greeting

    fun stop() {
        active = false
        interruptMode = false
        main.removeCallbacksAndMessages(null)
        main.post { rec?.cancel(); rec?.destroy(); rec = null }
        events.onState("off")
    }

    /** Listen for the next question (after a reply was read, or at the start). */
    fun listen(fromTurn: Boolean = true, delayMs: Long = 400) {
        if (!active) return
        interruptMode = false
        if (fromTurn) beepNext = true
        main.removeCallbacksAndMessages(null)
        main.postDelayed({ rec?.cancel(); doListen() }, delayMs)
    }

    /** While the reply is being read: listen only for "stop" (when enabled in Settings). */
    fun listenForInterrupt() {
        if (!active || !bargeIn) return
        interruptMode = true
        main.removeCallbacksAndMessages(null)
        main.postDelayed({ if (interruptMode) { rec?.cancel(); doListen() } }, 800)
    }

    private fun intent(): Intent {
        val other = if (language.startsWith("ar")) "en-US" else "ar-EG"
        return Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, ctx.packageName)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, language)
            // Android 14+ (Google): detect between the two languages in one session
            .putExtra("android.speech.extra.ENABLE_LANGUAGE_DETECTION", true)
            .putStringArrayListExtra("android.speech.extra.LANGUAGE_DETECTION_ALLOWED_LANGUAGES", arrayListOf(language, other))
    }

    private fun doListen() {
        if (!active) return
        val r = rec ?: SpeechRecognizer.createSpeechRecognizer(ctx).also { rec = it; it.setRecognitionListener(listener) }
        runCatching { r.startListening(intent()) }.onFailure { restart(1500, fresh = true) }
    }

    private fun restart(delayMs: Long, fresh: Boolean = false) {
        if (!active) return
        main.removeCallbacksAndMessages(null)
        main.postDelayed({
            if (fresh) { rec?.destroy(); rec = null }
            doListen()
        }, delayMs)
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            if (interruptMode) return
            if (beepNext) { beepNext = false; beep?.startTone(ToneGenerator.TONE_PROP_BEEP, 110) }   // speak now
            events.onState("listening")
        }
        override fun onBeginningOfSpeech() { failures = 0 }
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onPartialResults(partialResults: Bundle?) {}
        override fun onEvent(eventType: Int, params: Bundle?) {}

        override fun onError(error: Int) {
            if (!active) return
            when (error) {
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> { events.onProblem("Microphone permission is needed"); stop() }
                SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> restart(300)   // silence: quietly again
                SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED, SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE -> {
                    events.onProblem("This phone cannot recognize $language: install it in Google app > Voice > Offline speech")
                    restart(2000, fresh = true)
                }
                else -> {   // busy / client / network: start a fresh recognizer, slower each time
                    failures++
                    if (failures > 8) { events.onProblem("Speech recognition keeps failing - check the internet connection"); stop(); return }
                    restart(600L * failures, fresh = true)
                }
            }
        }

        override fun onResults(results: Bundle?) {
            if (!active) return
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty().trim()
            if (text.isBlank()) { restart(300); return }
            val t = text.lowercase().trim(' ', '.', '!', '؟', '?')
            if (interruptMode) {   // only "stop" counts; anything else is the phone hearing its own voice
                if (t in INTERRUPT || t in STOP) events.onCommand("interrupt") else restart(300)
                return
            }
            events.onHeard(text)
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
        val INTERRUPT = setOf("stop reading", "quiet", "be quiet", "enough", "skip", "cancel", "اسكت", "كفى", "كفاية",
            "توقف عن القراءة", "بس")
        val NEW = setOf("new chat", "new conversation", "start over", "محادثة جديدة", "محادثه جديده", "دردشة جديدة")
    }
}
