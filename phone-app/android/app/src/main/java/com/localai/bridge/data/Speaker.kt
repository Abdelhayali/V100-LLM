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
    /** One voice the phone can speak with. */
    data class VoiceInfo(val name: String, val label: String, val quality: Int, val online: Boolean)

    private var ready = false
    /** Chosen voices by name ("" = the best one found automatically). */
    var arabicVoice = ""
    var englishVoice = ""
    var onReady: () -> Unit = {}
    private var pending: String? = null
    var rate = 1.0f
    var onState: (speaking: Boolean) -> Unit = {}
    var onMissingVoice: (lang: String) -> Unit = {}
    private var lastId = ""

    // Google's engine usually has the most natural Arabic voices: use it when installed, else the phone's default
    private val engine: String? = GOOGLE_TTS.takeIf {
        runCatching { context.packageManager.getPackageInfo(it, 0) }.isSuccess
    }
    private val tts: TextToSpeech = TextToSpeech(context.applicationContext, { status ->
        ready = status == TextToSpeech.SUCCESS
        if (ready) onReady()
        pending?.let { pending = null; speak(it) }
    }, engine)

    /** Voices for a language ("ar" / "en"), best first: highest quality, offline before online. */
    fun voices(lang: String): List<VoiceInfo> {
        if (!ready) return emptyList()
        val vs = runCatching { tts.voices.orEmpty() }.getOrDefault(emptySet())
            .filter { it.locale.language == lang && !it.features.orEmpty().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED) }
            .sortedWith(compareByDescending<android.speech.tts.Voice> { it.quality }.thenBy { it.isNetworkConnectionRequired }.thenBy { it.name })
        val n = mutableMapOf<String, Int>()
        return vs.map { v ->
            val country = v.locale.displayCountry.ifBlank { v.locale.country }
            val k = n.merge(country, 1, Int::plus)!!
            VoiceInfo(v.name, "${v.locale.displayLanguage}${if (country.isNotBlank()) " ($country)" else ""} · voice $k" +
                (if (v.isNetworkConnectionRequired) " · online" else " · offline") +
                (if (v.quality >= android.speech.tts.Voice.QUALITY_HIGH) " · high quality" else ""), v.quality, v.isNetworkConnectionRequired)
        }
    }

    private fun pick(arabic: Boolean): android.speech.tts.Voice? {
        val want = if (arabic) arabicVoice else englishVoice
        val all = runCatching { tts.voices.orEmpty() }.getOrDefault(emptySet())
        all.firstOrNull { it.name == want }?.let { return it }
        val best = voices(if (arabic) "ar" else "en").firstOrNull { !it.online } ?: voices(if (arabic) "ar" else "en").firstOrNull()
        return best?.let { b -> all.firstOrNull { it.name == b.name } }
    }

    /** Say a short sample with a given voice (Settings > voice list). */
    fun test(voiceName: String, arabic: Boolean) {
        if (!ready) return
        tts.stop()
        runCatching { tts.voices.firstOrNull { it.name == voiceName } }.getOrNull()?.let { tts.voice = it }
        tts.setSpeechRate(rate)
        lastId = "test"
        tts.speak(if (arabic) "مرحباً، هذا صوت المساعد. كيف يمكنني مساعدتك اليوم؟" else "Hello, this is your assistant's voice. How can I help you today?",
            TextToSpeech.QUEUE_FLUSH, null, "test")
    }

    fun engineName(): String = engine?.let { "Google" } ?: (runCatching { tts.defaultEngine }.getOrNull() ?: "phone default")

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
            val voice = pick(arabic)
            val r = if (voice != null) { tts.voice = voice; TextToSpeech.LANG_AVAILABLE } else tts.setLanguage(loc)
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
        const val GOOGLE_TTS = "com.google.android.tts"
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
