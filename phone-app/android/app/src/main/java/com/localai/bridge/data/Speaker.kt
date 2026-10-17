package com.localai.bridge.data

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/**
 * Reads replies aloud with the phone's own text-to-speech engine (offline voices, no server).
 * Arabic and English are detected per sentence, so a mixed reply switches voice in the middle.
 */
class Speaker(context: Context) {
    private var ready = false
    private var pending: String? = null
    var rate = 1.0f
    var onState: (speaking: Boolean) -> Unit = {}
    var onMissingVoice: (lang: String) -> Unit = {}
    private var lastId = ""

    private val tts: TextToSpeech = TextToSpeech(context.applicationContext) { status ->
        ready = status == TextToSpeech.SUCCESS
        pending?.let { pending = null; speak(it) }
    }

    init {
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) = onState(true)
            override fun onDone(id: String?) { if (id == lastId) onState(false) }
            @Deprecated("Deprecated in Java")
            override fun onError(id: String?) = onState(false)
            override fun onStop(id: String?, interrupted: Boolean) = onState(false)
        })
    }

    fun speak(text: String) {
        if (!ready) { pending = text; return }
        tts.stop()
        tts.setSpeechRate(rate)
        val parts = segments(clean(text))
        if (parts.isEmpty()) return
        var warned = false
        parts.forEachIndexed { i, (arabic, s) ->
            val loc = if (arabic) Locale("ar") else Locale.US
            val r = tts.setLanguage(loc)
            if ((r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) && !warned) {
                warned = true; onMissingVoice(if (arabic) "Arabic" else "English")
            }
            val id = "u${System.nanoTime()}_$i"
            if (i == parts.lastIndex) lastId = id
            tts.speak(s, if (i == 0) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD, null, id)
        }
    }

    fun stop() { tts.stop(); onState(false) }
    fun shutdown() = tts.shutdown()

    companion object {
        private val arabicChar = Regex("[\\u0600-\\u06FF\\u0750-\\u077F\\u08A0-\\u08FF\\uFB50-\\uFDFF\\uFE70-\\uFEFF]")
        private val latinChar = Regex("[A-Za-z]")

        /** Markdown and code are not read: code blocks become a short mention, links keep their text. */
        fun clean(t: String): String = t
            .replace(Regex("(?s)<think>.*?</think>"), " ")
            .replace(Regex("(?s)```.*?```"), "\n(code)\n")
            .replace(Regex("`([^`]*)`"), "$1")
            .replace(Regex("!?\\[([^\\]]*)]\\([^)]*\\)"), "$1")
            .replace(Regex("https?://\\S+"), "")
            .replace(Regex("(?m)^\\s*[#>|]+\\s*"), "")
            .replace(Regex("[*_~]{1,3}"), "")
            .replace(Regex("(?m)^\\s*[-•]\\s+"), "")
            .replace(Regex("\\|"), " ")
            .replace(Regex("[ \\t]+"), " ")
            .trim()

        /** Split into sentences and group neighbours of the same script: [(isArabic, text)]. */
        fun segments(t: String): List<Pair<Boolean, String>> {
            val out = mutableListOf<Pair<Boolean, String>>()
            for (s in t.split(Regex("(?<=[.!?؟。\\n])\\s+")).map { it.trim() }.filter { it.isNotEmpty() }) {
                val ar = arabicChar.findAll(s).count()
                val la = latinChar.findAll(s).count()
                val isAr = if (ar == 0 && la == 0) out.lastOrNull()?.first ?: false else ar >= la
                if (out.isNotEmpty() && out.last().first == isAr && out.last().second.length < 3500)
                    out[out.lastIndex] = isAr to (out.last().second + " " + s)
                else out += isAr to s
            }
            return out
        }
    }
}
