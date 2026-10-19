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
        fun onCommand(cmd: String)            // stop | new | interrupt | translate
        fun onQuestion(text: String)
        fun onProblem(message: String)
    }

    private val main = Handler(Looper.getMainLooper())
    private var rec: SpeechRecognizer? = null
    private val beep = runCatching { ToneGenerator(AudioManager.STREAM_MUSIC, 70) }.getOrNull()
    var active = false
        private set
    var language = ""                          // "" = phone default, else e.g. "ar-EG", "en-US"
    /** Listening for "stop" while the reply is read aloud (the phone's echo cancelling keeps its own voice out). */
    private var interruptMode = false

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
        interruptMode = false
        main.removeCallbacksAndMessages(null)
        main.postDelayed({ rec?.cancel(); doListen() }, delayMs)
    }

    /** While the reply is being read: listen only for "stop" / "new chat" (other words are the phone's own voice). */
    fun listenForInterrupt() {
        if (!active) return
        interruptMode = true
        main.removeCallbacksAndMessages(null)
        main.postDelayed({ if (interruptMode) { rec?.cancel(); doListen() } }, 600)
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
            if (interruptMode) return                         // quiet: the reply is still being read
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
            if (interruptMode) {   // silence or noise while reading: keep listening for "stop"
                if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) { events.onProblem("Microphone permission is needed"); stop(); return }
                if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) { rec?.destroy(); rec = null }
                main.postDelayed({ if (interruptMode) doListen() }, 300)
                return
            }
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
            if (interruptMode) {   // only commands count; anything else is the phone hearing its own voice
                when {
                    t in INTERRUPT || t in STOP || STOP.any { t.endsWith(" $it") } -> events.onCommand("interrupt")
                    t in NEW -> events.onCommand("new")
                    else -> main.postDelayed({ if (interruptMode) doListen() }, 200)
                }
                return
            }
            events.onHeard(text)
            when {
                t in STOP -> events.onCommand("stop")
                t in NEW -> events.onCommand("new")
                t in TRANSLATE -> events.onCommand("translate")
                else -> { events.onState("thinking"); events.onQuestion(text) }
            }
        }
    }

    companion object {
        val STOP = setOf("stop", "stop driving", "stop driving mode", "exit", "goodbye", "توقف", "إيقاف", "ايقاف", "اوقف",
            "أوقف", "خلاص", "انهاء", "إنهاء")
        /** Said while it is reading: stop reading and listen for the next question. */
        val INTERRUPT = setOf("stop reading", "quiet", "be quiet", "enough", "skip", "cancel", "اسكت", "كفى", "كفاية",
            "توقف عن القراءة", "بس")
        val TRANSLATE = setOf("translate mode", "translation mode", "translate", "translator", "stop translating",
            "وضع الترجمة", "ترجمة", "ترجم", "الترجمة", "إيقاف الترجمة", "ايقاف الترجمة")
        val NEW = setOf("new chat", "new conversation", "start over", "محادثة جديدة", "محادثه جديده", "دردشة جديدة")
    }
}
