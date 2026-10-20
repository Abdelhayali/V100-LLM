package com.localai.bridge.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.localai.bridge.LiveService
import com.localai.bridge.data.LiveLine
import com.localai.bridge.data.PronounceResult
import com.localai.bridge.data.SessionDto
import com.localai.bridge.data.TutorTurn
import com.localai.bridge.data.VaultKey
import com.localai.bridge.data.liveAsk
import com.localai.bridge.data.profile
import com.localai.bridge.data.profileSave
import com.localai.bridge.data.profileRebuild
import com.localai.bridge.data.liveStart
import com.localai.bridge.data.liveState
import com.localai.bridge.data.liveStop
import com.localai.bridge.data.tutorPronounce
import com.localai.bridge.data.tutorSentence
import com.localai.bridge.data.tutorTurn
import com.localai.bridge.data.vaultSessions
import com.localai.bridge.data.vaultUnlock
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Page(title: String, openDrawer: () -> Unit, body: @Composable () -> Unit) {
    Scaffold(topBar = {
        TopAppBar(title = { Text(title) }, navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) { body() }
    }
}

@Composable
private fun Small(text: String, color: Color? = null) = Text(text, style = MaterialTheme.typography.bodySmall,
    color = color ?: MaterialTheme.colorScheme.onSurfaceVariant)

/** Speech recognizer launcher for one language ("ar-EG" / "en-US"). */
@Composable
private fun rememberListener(onText: (String) -> Unit): (String, String) -> Unit {
    val vm = LocalContext.current
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let(onText)
    }
    return { lang, prompt ->
        runCatching {
            launcher.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang).putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, lang)
                .putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true).putExtra(RecognizerIntent.EXTRA_PROMPT, prompt))
        }
        Unit
    }
}

// ------------------------------------------------------------------ private vault
@Composable
fun VaultScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<List<SessionDto>>(emptyList()) }
    var showCode by remember { mutableStateOf<String?>(null) }
    var restoring by remember { mutableStateOf(false) }
    var code by remember { mutableStateOf("") }
    fun load() = scope.launch { runCatching { vm.api?.vaultSessions() }.onSuccess { list = it.orEmpty() }.onFailure { vm.toast = it.message } }
    fun unlock(restore: ByteArray? = null, firstTime: Boolean = false) {
        val act = ctx as? FragmentActivity ?: return
        VaultKey.unlock(act, restore, onKey = { k ->
            vm.setVaultKey(k)
            scope.launch {
                runCatching { vm.api?.vaultUnlock() }.onSuccess { load(); if (firstTime) showCode = VaultKey.recoveryCode(k) }
                    .onFailure { vm.setVaultKey(null); vm.toast = "The PC refused this key (it does not match the vault on the PC)" }
            }
        }, onError = { vm.toast = it })
    }
    LaunchedEffect(vm.vaultUnlocked) { if (vm.vaultUnlocked) load() }
    showCode?.let { c ->
        AlertDialog(onDismissRequest = { showCode = null }, title = { Text("Write down your recovery code") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(c, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Small("Without it, a new or reset phone can never open these chats - not even from the PC. Keep it somewhere safe and private.")
            } },
            confirmButton = { TextButton(onClick = { showCode = null }) { Text("I saved it") } })
    }
    if (restoring) AlertDialog(onDismissRequest = { restoring = false }, title = { Text("Restore the vault key") },
        text = { OutlinedTextField(code, { code = it }, label = { Text("Recovery code") }) },
        confirmButton = { TextButton(onClick = {
            val k = VaultKey.parseRecovery(code)
            if (k == null) vm.toast = "That is not a valid recovery code" else { restoring = false; unlock(k) }
        }) { Text("Restore") } },
        dismissButton = { TextButton(onClick = { restoring = false }) { Text("Cancel") } })

    Page("Private vault", openDrawer) {
        Small("Chats here are encrypted on your PC with a key that only this phone holds, behind your fingerprint. Without " +
            "it they cannot be read, not even on the PC. They are never used for memories. The vault locks when you leave the app.")
        if (!VaultKey.canUseBiometric(ctx)) {
            Text("This phone has no fingerprint or face unlock set up, which the vault needs.", color = MaterialTheme.colorScheme.error)
            return@Page
        }
        if (!vm.vaultUnlocked) {
            Button(onClick = { unlock(firstTime = !VaultKey.hasKey(ctx)) }, modifier = Modifier.fillMaxWidth().height(64.dp)) {
                Text(if (VaultKey.hasKey(ctx)) "🔓 Unlock with fingerprint" else "🔐 Create the vault (fingerprint)")
            }
            TextButton(onClick = { restoring = true }) { Text("Restore from a recovery code (new phone)") }
            Small("Files you attach in a private chat are stored on the PC like other uploads (not encrypted).")
            return@Page
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.newVaultChat() }) { Text("New private chat") }
            OutlinedButton(onClick = { vm.setVaultKey(null) }) { Text("Lock") }
        }
        list.forEach { s ->
            Card(Modifier.fillMaxWidth().clickable { vm.screen = Screen.CHAT; vm.openVaultChat(s.id) },
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                Text(s.title, Modifier.padding(14.dp), maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
        }
        if (list.isEmpty()) Small("No private chats yet.")
    }
}

// ------------------------------------------------------------------ language tutor
private data class TutorMsg(val mine: Boolean, val text: String, val turn: TutorTurn? = null)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TutorScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var lang by remember { mutableStateOf("en") }
    var level by remember { mutableStateOf("intermediate") }
    var mode by remember { mutableStateOf("talk") }
    var busy by remember { mutableStateOf(false) }
    val chat = remember { mutableStateListOf<TutorMsg>() }
    var sentence by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<PronounceResult?>(null) }
    val rec = if (lang == "en") "en-US" else "ar-EG"
    val ctx = LocalContext.current
    var reading by remember { mutableStateOf(false) }
    var heard by remember { mutableStateOf("") }
    var own by remember { mutableStateOf("") }
    var readAfterSpeech by remember { mutableStateOf(false) }   // your own text: read it to me, then listen
    fun isArabic(s: String) = s.any { it in '\u0600'..'\u06FF' }
    val reader = remember { LiveReader(ctx) }
    DisposableEffect(Unit) { onDispose { reader.release() } }
    val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> if (!ok) vm.toast = "Needs the microphone" }

    val listen = rememberListener { text ->
        if (mode == "talk") {
            chat.add(TutorMsg(true, text)); busy = true
            scope.launch {
                runCatching {
                    vm.api?.tutorTurn(lang, level, text, chat.dropLast(1).map { (if (it.mine) "user" else "assistant") to it.text })
                }.onSuccess { t -> if (t != null) { chat.add(TutorMsg(false, t.reply, t)); vm.speaker.speak(t.reply) } }
                    .onFailure { vm.toast = it.message }
                busy = false
            }
        } else {
            busy = true
            scope.launch {
                runCatching { vm.api?.tutorPronounce(lang, sentence, text) }.onSuccess { result = it }.onFailure { vm.toast = it.message }
                busy = false
            }
        }
    }
    fun newSentence() { busy = true; result = null; scope.launch {
        runCatching { vm.api?.tutorSentence(lang, level) }.onSuccess { sentence = it.orEmpty() }.onFailure { vm.toast = it.message }
        busy = false } }
    fun readAloud() {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            mic.launch(Manifest.permission.RECORD_AUDIO); return
        }
        vm.speaker.stop(); result = null; heard = ""; reading = true
        val sLang = if (isArabic(sentence)) "ar" else if (sentence.any { it.isLetter() }) "en" else lang
        reader.start(if (sLang == "ar") "ar-EG" else "en-US", onPartial = { heard = it }, onFinal = { text ->
            reading = false; heard = text
            if (text.isBlank()) vm.toast = "I did not hear anything - try again"
            else {
                busy = true
                scope.launch {
                    runCatching { vm.api?.tutorPronounce(sLang, sentence, text) }.onSuccess { result = it }.onFailure { vm.toast = it.message }
                    busy = false
                }
            }
        })
    }
    LaunchedEffect(readAfterSpeech) {
        if (!readAfterSpeech) return@LaunchedEffect
        var waited = 0
        while (!vm.speaking && waited < 50) { delay(100); waited++ }   // speech may take a moment to start
        while (vm.speaking) delay(150)
        delay(300)
        readAfterSpeech = false
        readAloud()
    }

    Page("Language tutor", openDrawer) {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            FilterChip(selected = lang == "en", onClick = { lang = "en"; chat.clear(); sentence = "" }, label = { Text("English") })
            FilterChip(selected = lang == "ar", onClick = { lang = "ar"; chat.clear(); sentence = "" }, label = { Text("العربية") })
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("beginner", "intermediate", "advanced").forEach { l ->
                FilterChip(selected = level == l, onClick = { level = l }, label = { Text(l.replaceFirstChar { it.uppercase() }) })
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            FilterChip(selected = mode == "talk", onClick = { mode = "talk" }, label = { Text("Conversation") })
            FilterChip(selected = mode == "say", onClick = { mode = "say"; if (sentence.isBlank()) newSentence() }, label = { Text("Pronunciation") })
        }
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (mode == "talk") {
            Small("Speak, and the tutor answers, corrects your mistakes and suggests a more natural way to say it.")
            chat.forEach { m ->
                Card(colors = CardDefaults.cardColors(containerColor = if (m.mine) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.surfaceContainerHigh), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(m.text)
                        m.turn?.let { t ->
                            t.corrections.forEach { c ->
                                Text("✗ ${c.wrong}  →  ✓ ${c.right}", color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.SemiBold)
                                if (c.why.isNotBlank()) Small(c.why)
                            }
                            if (t.better.isNotBlank()) Small("Better: ${t.better}", Color(0xFF2E9D57))
                            t.score?.let { Small("Score: ${it.toInt()}/10") }
                            TextButton(onClick = { vm.speaker.speak(t.reply) }) { Text("▶ Hear again") }
                        }
                    }
                }
            }
            Button(onClick = { vm.speaker.stop(); listen(rec, if (lang == "en") "Speak English" else "تكلم بالعربية") },
                enabled = !busy, modifier = Modifier.fillMaxWidth().height(64.dp)) {
                Text(if (chat.isEmpty()) "🎤 Start talking" else "🎤 Answer", style = MaterialTheme.typography.titleMedium)
            }
            if (chat.isNotEmpty()) TextButton(onClick = { chat.clear() }) { Text("New conversation") }
        } else {
            Small("Tap Read and say the sentence. It stays on screen, and each word lights up as you say it.")
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                OutlinedTextField(own, { own = it }, label = { Text("Or type your own word or sentence") },
                    modifier = Modifier.weight(1f), maxLines = 3)
                Button(enabled = own.isNotBlank() && !reading && !busy, onClick = {
                    reader.cancel(); sentence = own.trim(); result = null; heard = ""
                    vm.speaker.speak(sentence); readAfterSpeech = true
                }) { Text("▶ Say it") }
            }
            if (readAfterSpeech) Small("Listen… then read it back.", MaterialTheme.colorScheme.primary)
            if (sentence.isNotBlank()) {
                val words = remember(sentence) { sentence.split(Regex("\\s+")).filter { it.isNotBlank() } }
                val done = if (result == null) followWords(words, heard) else 0
                Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                    FlowRow(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        words.forEachIndexed { i, w ->
                            val mark = result?.words?.takeIf { it.size == words.size }?.getOrNull(i)
                            Text(w, style = MaterialTheme.typography.headlineSmall,
                                fontWeight = if (reading && i == done) FontWeight.Bold else FontWeight.Normal,
                                color = when {
                                    mark != null -> if (mark.ok) Color(0xFF2E9D57) else MaterialTheme.colorScheme.error
                                    i < done -> Color(0xFF2E9D57)
                                    reading && i == done -> MaterialTheme.colorScheme.primary
                                    else -> MaterialTheme.colorScheme.onSurface
                                },
                                modifier = Modifier.clickable { vm.speaker.speak(w) })
                        }
                    }
                }
                if (reading) Text("🎤 Listening… $heard", color = MaterialTheme.colorScheme.primary)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { vm.speaker.speak(sentence) }, enabled = !reading) { Text("▶ Hear it") }
                    if (reading) Button(onClick = { reader.stop() }) { Text("■ Done") }
                    else Button(onClick = { readAloud() }, enabled = !busy) { Text("🎤 Read it") }
                    TextButton(onClick = { reader.cancel(); reading = false; heard = ""; newSentence() }, enabled = !busy) { Text("Next") }
                }
            }
            result?.let { r ->
                Text("Score: ${r.score}%", style = MaterialTheme.typography.titleLarge,
                    color = if (r.score >= 85) Color(0xFF2E9D57) else if (r.score >= 60) Color(0xFFC27C0E) else MaterialTheme.colorScheme.error)
                if (r.words.size != sentence.split(Regex("\\s+")).count { it.isNotBlank() }) FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    r.words.forEach { w ->
                        Text(w.word, color = if (w.ok) Color(0xFF2E9D57) else MaterialTheme.colorScheme.error,
                            fontWeight = if (w.ok) FontWeight.Normal else FontWeight.Bold,
                            modifier = Modifier.clickable { vm.speaker.speak(w.word) })
                    }
                }
                Small("Tap a word to hear it.")
                if (r.tips.isNotBlank()) Text(r.tips, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

// ------------------------------------------------------------------ live meeting
@Composable
fun LiveScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var id by remember { mutableStateOf(LiveService.meetingId.takeIf { LiveService.running }.orEmpty()) }
    val lines = remember { mutableStateListOf<LiveLine>() }
    var status by remember { mutableStateOf(if (LiveService.running) "live" else "") }
    var behind by remember { mutableStateOf(0) }
    var resultSid by remember { mutableStateOf("") }
    var q by remember { mutableStateOf("") }
    var answer by remember { mutableStateOf("") }
    var asking by remember { mutableStateOf(false) }
    var lang by remember { mutableStateOf("") }
    var addTasks by remember { mutableStateOf(true) }
    val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> if (!ok) vm.toast = "Needs the microphone" }
    val listen = rememberListener { q = it }

    LaunchedEffect(id) {
        while (id.isNotBlank()) {
            runCatching { vm.api?.liveState(id, lines.size) }.getOrNull()?.let { s ->
                lines.addAll(s.lines); status = s.status; behind = s.behind
                s.result?.sessionId?.takeIf { it.isNotBlank() }?.let { resultSid = it }
                if (s.status == "error") vm.toast = s.result?.error ?: "The meeting notes failed"
            }
            if (status == "done" || status == "error") break
            delay(3000)
        }
    }
    Page("Live meeting", openDrawer) {
        Small("The transcript appears while the meeting runs (Arabic or English, ~20-40 s behind). Ask about it at any " +
            "time. When you stop, you get a summary, decisions and action items. Keeps recording with the screen off.")
        if (status.isEmpty() || status == "done" || status == "error") {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf("" to "Auto language", "ar" to "العربية", "en" to "English").forEach { (k, l) ->
                    FilterChip(selected = lang == k, onClick = { lang = k }, label = { Text(l) })
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Add action items to my tasks", Modifier.weight(1f)); Switch(checked = addTasks, onCheckedChange = { addTasks = it })
            }
            Button(onClick = {
                if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                    mic.launch(Manifest.permission.RECORD_AUDIO); return@Button
                }
                scope.launch {
                    runCatching { vm.api?.liveStart(lang) }.onSuccess { mid ->
                        if (mid.isNullOrBlank()) return@onSuccess
                        lines.clear(); resultSid = ""; answer = ""; id = mid; status = "live"; LiveService.start(ctx, mid)
                    }.onFailure { vm.toast = "Could not start: ${it.message}" }
                }
            }, modifier = Modifier.fillMaxWidth().height(64.dp)) { Text("🎙 Start live meeting", style = MaterialTheme.typography.titleMedium) }
            if (resultSid.isNotBlank()) Button(onClick = { vm.screen = Screen.CHAT; vm.openSession(resultSid) }) { Text("Open the meeting notes") }
        } else {
            Text(when (status) { "live" -> "● Live" + if (behind > 0) " · transcribing $behind piece(s)…" else ""; else -> "Writing the meeting notes…" },
                color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.titleMedium)
            if (status == "live") Button(onClick = {
                LiveService.stop(ctx)
                scope.launch { runCatching { vm.api?.liveStop(id, addTasks) }; status = "finishing" }
            }, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error), modifier = Modifier.fillMaxWidth()) {
                Text("■ Stop and make notes") }
            else LinearProgressIndicator(Modifier.fillMaxWidth())
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                OutlinedTextField(q, { q = it }, label = { Text("Ask about the meeting") }, modifier = Modifier.weight(1f), singleLine = true)
                IconButton(onClick = { listen(if (lang == "en") "en-US" else "ar-EG", "Ask about the meeting") }) { Text("🎤") }
            }
            Button(enabled = q.isNotBlank() && !asking, onClick = {
                asking = true
                scope.launch { runCatching { vm.api?.liveAsk(id, q) }.onSuccess { answer = it.orEmpty() }.onFailure { vm.toast = it.message }; asking = false }
            }) { Text(if (asking) "Thinking…" else "Ask") }
            if (answer.isNotBlank()) Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                Text(answer, Modifier.padding(12.dp)) }
        }
        lines.takeLast(80).forEach { l ->
            Row { Small("%d:%02d  ".format(l.t.toInt() / 60, l.t.toInt() % 60)); Text(l.text, style = MaterialTheme.typography.bodyMedium) }
        }
    }
}

// ------------------------------------------------------------------ personal profile (Settings)
@Composable
fun ProfileCard(vm: MainViewModel) {
    val scope = rememberCoroutineScope()
    var p by remember { mutableStateOf<com.localai.bridge.data.ProfileDto?>(null) }
    var text by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { runCatching { vm.api?.profile() }.getOrNull()?.let { p = it; text = it.text } }
    LaunchedEffect(p?.building) {
        while (p?.building == 1) { delay(4000); runCatching { vm.api?.profile() }.getOrNull()?.let { p = it; if (!editing) text = it.text } }
    }
    Text("Personal profile", style = MaterialTheme.typography.titleMedium)
    Small("The AI learns how you write and what you work on from your chats, notes and memories (never private or temporary " +
        "chats) and refreshes it every night. It is added to every chat so answers fit you. You can read and edit it.")
    val cur = p ?: run { Small("Loading…"); return }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Use my profile in chats", Modifier.weight(1f))
        Switch(checked = cur.enabled == 1, onCheckedChange = { on ->
            scope.launch { runCatching { vm.api?.profileSave(on, null) }.getOrNull()?.let { p = it } }
        })
    }
    if (cur.building == 1) { LinearProgressIndicator(Modifier.fillMaxWidth()); Small("Building your profile…") }
    if (editing) {
        OutlinedTextField(text, { text = it }, modifier = Modifier.fillMaxWidth(), minLines = 6)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { scope.launch { runCatching { vm.api?.profileSave(cur.enabled == 1, text) }.getOrNull()?.let { p = it }; editing = false } }) { Text("Save") }
            TextButton(onClick = { text = cur.text; editing = false }) { Text("Cancel") }
        }
    } else {
        Text(cur.text.ifBlank { "No profile yet. Tap Rebuild now." }, style = MaterialTheme.typography.bodyMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { editing = true }) { Text("Edit") }
            OutlinedButton(enabled = cur.building != 1, onClick = {
                scope.launch { runCatching { vm.api?.profileRebuild() }.onSuccess { if (it != null) p = it }.onFailure { vm.toast = it.message } }
            }) { Text("Rebuild now") }
        }
    }
}

// ------------------------------------------------------------------ reading along (pronunciation)
private fun norm(w: String) = w.lowercase().replace(Regex("[\u064B-\u0652\u0670\u0640]"), "")   // no tashkeel / tatweel
    .replace(Regex("[أإآ]"), "ا").replace("ة", "ه").replace("ى", "ي").filter { it.isLetterOrDigit() }

/** How many words of the sentence have been said so far (in order, allowing a skipped or misheard word). */
internal fun followWords(words: List<String>, heard: String): Int {
    val target = words.map(::norm)
    var pos = 0
    for (h in heard.split(Regex("\\s+")).map(::norm).filter { it.isNotEmpty() }) {
        val hit = (pos until minOf(pos + 3, target.size)).firstOrNull { j ->
            target[j] == h || (h.length > 3 && target[j].length > 3 && target[j].startsWith(h.take(3))
                && kotlin.math.abs(target[j].length - h.length) <= 2)
        }
        if (hit != null) pos = hit + 1
    }
    return pos
}

/** In-app speech recognizer with live partial results, so the sentence stays visible while you read it. */
class LiveReader(private val ctx: android.content.Context) {
    private var sr: android.speech.SpeechRecognizer? = null
    private var finished = false

    fun start(lang: String, onPartial: (String) -> Unit, onFinal: (String) -> Unit) {
        cancel()
        finished = false
        var last = ""
        fun finish(text: String) { if (!finished) { finished = true; onFinal(text) } }
        sr = android.speech.SpeechRecognizer.createSpeechRecognizer(ctx).apply {
            setRecognitionListener(object : android.speech.RecognitionListener {
                override fun onPartialResults(b: android.os.Bundle?) {
                    b?.getStringArrayList(android.speech.SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                        ?.takeIf { it.isNotBlank() }?.let { last = it; onPartial(it) }
                }
                override fun onResults(b: android.os.Bundle?) =
                    finish(b?.getStringArrayList(android.speech.SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.ifBlank { last } ?: last)
                override fun onError(error: Int) = finish(last)
                override fun onReadyForSpeech(p: android.os.Bundle?) {}
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(v: Float) {}
                override fun onBufferReceived(b: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onEvent(t: Int, b: android.os.Bundle?) {}
            })
            startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang).putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, lang)
                .putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                // let the learner pause between words without the recognizer giving up
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2500L)
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 2500L))
        }
    }

    fun stop() { sr?.stopListening() }          // ends now; the result still arrives
    fun cancel() { finished = true; sr?.destroy(); sr = null }
    fun release() = cancel()
}
