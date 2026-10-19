package com.localai.bridge.ui

import com.localai.bridge.data.v100Status
import com.localai.bridge.data.rotateToken

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.localai.bridge.data.Api
import com.localai.bridge.data.agentAbort
import com.localai.bridge.data.AttachmentRef
import com.localai.bridge.data.MessageDto
import com.localai.bridge.data.PairPayload
import com.localai.bridge.data.PendingApproval
import com.localai.bridge.data.Prefs
import com.localai.bridge.data.ServerInfo
import com.localai.bridge.data.SessionDto
import com.localai.bridge.data.SessionStats
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

enum class Screen { CHAT, FILES, TERMINAL, MEMORY, SETTINGS, TASKS, AGENT, MODELS, API, ORGANIZER, SCHEDULES }

sealed interface ChatItem {
    val key: String

    data class User(
        override val key: String, val text: String, val attachments: List<AttachmentRef>,
        val messageId: Long? = null,   // server id; needed to edit the message
    ) : ChatItem
    data class Assistant(override val key: String, val text: String, val reasoning: String) : ChatItem
    data class Tool(
        override val key: String, val name: String, val args: JsonObject,
        val output: String?, val status: String,   // running | awaiting | done
        val attachments: List<AttachmentRef> = emptyList(),  // images/files the tool sent to the chat
    ) : ChatItem
    data class Notice(override val key: String, val text: String, val error: Boolean = false) : ChatItem
}

/** Thinking effort: id, label, what it does (the server turns it into a llama.cpp thinking budget). */
val THINKING_MODES = listOf(
    Triple("auto", "Auto", "model default"), Triple("off", "Off", "no thinking, fastest"),
    Triple("low", "Low", "thinks up to ~1k tokens"), Triple("medium", "Medium", "up to ~4k tokens"),
    Triple("high", "High", "up to ~16k tokens"), Triple("max", "Max", "as long as it needs, slow"),
)

/** OCR sub-model (Unlimited-OCR) for scanned PDFs, photos of documents and text in images. */
val OCR_MODES = listOf(
    Triple("off", "Off", "no OCR tool"),
    Triple("gpu", "A: GPU (swap)", "fast: unloads the chat model, reads on the V100, loads it again (~1 min extra)"),
    Triple("cpu", "B: CPU", "the chat model stays loaded; slower (~1-2 min per page)"),
)

class MainViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    var api: Api? = if (prefs.isPaired) Api(prefs.serverUrl, prefs.token) else null
        private set

    var paired by mutableStateOf(prefs.isPaired)
    var screen by mutableStateOf(Screen.CHAT)
    var info by mutableStateOf<ServerInfo?>(null)
    var connectionError by mutableStateOf<String?>(null)
    var toast by mutableStateOf<String?>(null)

    val sessions = mutableStateListOf<SessionDto>()
    var currentSessionId by mutableStateOf<String?>(null)
    var currentTitle by mutableStateOf("New chat")
    var currentModel by mutableStateOf("")
    val items = mutableStateListOf<ChatItem>()
    var streaming by mutableStateOf(false)
    var loadingSession by mutableStateOf(false)
    val approvals = mutableStateListOf<PendingApproval>()
    val questions = mutableStateListOf<com.localai.bridge.data.PendingQuestion>()   // ask_user choices waiting on the phone
    val plan = mutableStateListOf<com.localai.bridge.data.PlanStep>()               // the model's own step list (update_tasks)

    val pendingAttachments = mutableStateListOf<AttachmentRef>()
    var uploading by mutableStateOf(false)
    var draft by mutableStateOf("")
    var editingMessageId by mutableStateOf<Long?>(null)
    var themeMode by mutableStateOf(prefs.themeMode)   // system | light | dark
    var webSearch by mutableStateOf(prefs.webSearch)   // give the model internet search
    var sandbox by mutableStateOf(prefs.sandbox)          // run_code in the AppContainer sandbox
    var ocr by mutableStateOf(prefs.ocr)               // OCR sub-model: off/gpu/cpu
    var thinking by mutableStateOf(prefs.thinking)     // thinking effort: auto/off/low/medium/high/max
    var emailAccess by mutableStateOf(prefs.emailAccess)          // Gmail tools in chats (off by default)
    var organizerAccess by mutableStateOf(prefs.organizerAccess)  // tasks / notes / calendar tools (off by default)
    // one request may get access it needs (an "Ask the AI" button the user tapped), without changing the switches
    private var onceEmail = false
    private var onceOrganizer = false
    fun sendWithAccess(email: Boolean, organizer: Boolean) { onceEmail = email; onceOrganizer = organizer; send() }
    fun toggleEmailAccess() { emailAccess = !emailAccess; prefs.emailAccess = emailAccess
        toast = if (emailAccess) "Email access ON: the AI can read your mail and write drafts (sending asks you)" else "Email access OFF" }
    fun toggleOrganizerAccess() { organizerAccess = !organizerAccess; prefs.organizerAccess = organizerAccess
        toast = if (organizerAccess) "Tasks & calendar access ON" else "Tasks & calendar access OFF" }
    var autoApprove by mutableStateOf(prefs.autoApprove)   // run code / write files without asking
    var autoCompress by mutableStateOf(prefs.autoCompress)
    var compressAt by mutableStateOf(prefs.compressAt)       // percent of the context
    // read replies aloud (phone TTS, Arabic + English)
    val speaker = com.localai.bridge.data.Speaker(app).also { s ->
        s.rate = prefs.speechRate
        s.onState = { on -> speaking = on; if (!on) speakingKey = null }
        s.onMissingVoice = { lang -> toast = "No $lang voice on this phone: install it in Android Settings > Text-to-speech" }
    }
    var speaking by mutableStateOf(false)
    var speakingKey by mutableStateOf<String?>(null)
    var autoRead by mutableStateOf(prefs.autoRead)
    var speechRate by mutableStateOf(prefs.speechRate)
    private var turnEnded = false                            // got "done" or "error" (vs. connection dropped)
    private var reconnectJob: Job? = null

    // what the PC is doing (Running tasks screen + indicator); polled while the app is open
    var tasks by mutableStateOf<com.localai.bridge.data.TasksDto?>(null)
    private var tasksJob: Job? = null
    // PC status from the V100-LLM launcher (loaded model, VRAM, GPU load, CPU, RAM), polled while the app is open
    var pcStatus by mutableStateOf<com.localai.bridge.data.V100Status?>(null)
    private var pcJob: Job? = null
    private var turnCompleted = false

    // live status of a running reply (shown above the input while streaming)
    var stats by mutableStateOf<SessionStats?>(null)       // last context / speed numbers of this session
    var phase by mutableStateOf("")                         // sending|prompt|thinking|writing|tool_args|tool|approval
    var phaseTool by mutableStateOf("")
    var liveTokens by mutableStateOf(0)
    var liveTps by mutableStateOf<Double?>(null)
    var streamStartMs by mutableStateOf(0L)
    var lastEventMs by mutableStateOf(0L)
    private var startupDone = false

    private var streamJob: Job? = null
    private var backgroundAtMs = 0L   // when the app last went to the background
    private var keyCounter = 0
    private fun nextKey() = "k${keyCounter++}"

    init {
        if (paired) refreshAll()
    }

    // ---------------------------------------------------------------- pairing
    suspend fun pair(url: String, token: String): String? {
        val clean = url.trim().trimEnd('/')
        if (!clean.startsWith("https://") && !clean.startsWith("http://")) return "URL must start with https://"
        val test = Api(clean, token.trim())
        return try {
            info = test.info()
            prefs.serverUrl = clean
            prefs.token = token.trim()
            api = test
            paired = true
            startTaskPolling()
            refreshAll()
            null
        } catch (e: Exception) {
            e.message ?: e.toString()
        }
    }

    fun parsePairQr(text: String): PairPayload? =
        runCatching { Api("http://x", "").json.decodeFromString<PairPayload>(text) }.getOrNull()

    /** Change the bridge's access key and keep this phone paired with the new one. */
    fun changeKey() = viewModelScope.launch {
        val a = api ?: return@launch
        try {
            val t = a.rotateToken()
            require(t.length >= 20) { "the PC returned no key" }
            prefs.token = t
            api = Api(prefs.serverUrl, t)
            info = api?.info()
            toast = "Access key changed. Other devices (desktop app, other phones) must re-pair with the new QR."
        } catch (e: Exception) { toast = "Could not change the key: ${e.message}" }
    }

    fun unpair() {
        streamJob?.cancel()
        prefs.clear()
        prefs.themeMode = themeMode
        prefs.webSearch = webSearch
        prefs.autoApprove = false
        startupDone = false
        autoApprove = false
        api = null
        paired = false
        sessions.clear(); items.clear(); info = null; currentSessionId = null
    }

    // ---------------------------------------------------------------- sessions
    fun refreshAll() = viewModelScope.launch {
        val a = api ?: return@launch
        try {
            info = a.info()
            connectionError = null
            loadSessions()
            // Only on the first successful connection: reopen the last chat. Later refreshes (e.g. from
            // Settings) must not navigate away from the current screen.
            if (!startupDone) {
                startupDone = true
                val last = prefs.lastSession
                if (currentSessionId == null && last.isNotBlank() && sessions.any { it.id == last }) openSession(last)
                else if (currentSessionId == null) currentModel = info?.defaultModel.orEmpty()
            }
        } catch (e: Exception) {
            connectionError = e.message ?: "Cannot reach server"
        }
    }

    /** Re-fetch the model list from the PC (the LLM server may have loaded a different model). */
    fun refreshModels() = viewModelScope.launch {
        try { info = api?.info() } catch (e: Exception) { toast = e.message }
    }

    suspend fun loadSessions() {
        val list = api?.sessions() ?: return
        sessions.clear(); sessions.addAll(list)
    }

    fun newChat() {
        streamJob?.cancel()
        streaming = false
        currentSessionId = null
        currentTitle = "New chat"
        currentModel = info?.defaultModel.orEmpty()
        stats = null
        items.clear(); approvals.clear(); questions.clear(); plan.clear()
        screen = Screen.CHAT
    }

    fun openSession(id: String) = viewModelScope.launch {
        val a = api ?: return@launch
        streamJob?.cancel()
        streaming = false
        screen = Screen.CHAT
        loadingSession = true
        try {
            val s = a.session(id)
            currentSessionId = s.id
            currentTitle = s.title
            stats = s.stats
            currentModel = s.model?.takeIf { it.isNotBlank() } ?: info?.defaultModel.orEmpty()
            prefs.lastSession = s.id
            items.clear(); items.addAll(toItems(s.messages, s.summaryUpto))
            approvals.clear(); approvals.addAll(s.pendingApprovals)
        questions.clear(); questions.addAll(s.pendingQuestions)
        plan.clear(); plan.addAll(s.plan)
            questions.clear(); questions.addAll(s.pendingQuestions)
        plan.clear(); plan.addAll(s.plan)
            plan.clear(); plan.addAll(s.plan)
            if (s.running) {
                // the reply is still generating on the PC: re-attach to its stream
                trimToLastUser()
                streamJob = viewModelScope.launch { consume(a.resume(s.id)) }
            }
        } catch (e: Exception) {
            toast = e.message
        } finally {
            loadingSession = false
        }
    }

    /** When resuming, the replayed events re-create everything after the last user message. */
    private fun trimToLastUser() {
        val idx = items.indexOfLast { it is ChatItem.User }
        if (idx >= 0) while (items.size > idx + 1) items.removeAt(items.size - 1)
    }

    fun deleteSession(id: String) = viewModelScope.launch {
        try {
            api?.deleteSession(id)
            sessions.removeAll { it.id == id }
            if (id == currentSessionId) newChat()
        } catch (e: Exception) { toast = e.message }
    }

    fun renameSession(id: String, title: String) = viewModelScope.launch {
        try {
            api?.renameSession(id, title)
            if (id == currentSessionId) currentTitle = title
            loadSessions()
        } catch (e: Exception) { toast = e.message }
    }

    fun selectModel(model: String) {
        currentModel = model
        val id = currentSessionId ?: return
        viewModelScope.launch { runCatching { api?.setSessionModel(id, model) } }
    }

    private fun toItems(msgs: List<MessageDto>, summaryUpto: Long? = null): List<ChatItem> {
        val out = mutableListOf<ChatItem>()
        val toolIndex = mutableMapOf<String, Int>()
        val markerAfter = summaryUpto?.let { upto -> msgs.lastOrNull { it.id <= upto }?.id }
        for (m in msgs) {
            if (markerAfter != null && m.id > markerAfter && out.none { it is ChatItem.Notice && it.key == "summary" }) {
                out += ChatItem.Notice("summary", "Messages above were compressed into a summary - the AI remembers them in short form.")
            }
            when (m.role) {
                "user" -> out += ChatItem.User(nextKey(), m.content.orEmpty(), m.attachments, m.id)
                "assistant" -> {
                    if (!m.content.isNullOrBlank() || !m.reasoning.isNullOrBlank())
                        out += ChatItem.Assistant(nextKey(), m.content.orEmpty(), m.reasoning.orEmpty())
                    for (tc in m.toolCalls) {
                        val args = runCatching {
                            api!!.json.parseToJsonElement(tc.function.arguments).jsonObject
                        }.getOrDefault(JsonObject(emptyMap()))
                        toolIndex[tc.id] = out.size
                        out += ChatItem.Tool(tc.id, tc.function.name, args, null, "running")
                    }
                }
                "tool" -> {
                    val i = toolIndex[m.toolCallId]
                    if (i != null) out[i] = (out[i] as ChatItem.Tool).copy(
                        output = m.content, status = "done", attachments = m.attachments)
                }
            }
        }
        return out
    }

    // ---------------------------------------------------------------- chat
    fun send() {
        val a = api ?: return
        val text = draft.trim()
        if ((text.isEmpty() && pendingAttachments.isEmpty()) || streaming || uploading) return
        val atts = pendingAttachments.toList()
        val editId = editingMessageId
        draft = ""
        pendingAttachments.clear()
        editingMessageId = null
        plan.clear()   // a new request gets a new plan
        if (editId != null) {
            val idx = items.indexOfFirst { it is ChatItem.User && it.messageId == editId }
            if (idx >= 0) while (items.size > idx) items.removeAt(items.size - 1)
        }
        items += ChatItem.User(nextKey(), text, atts)
        streaming = true
        streamStartMs = System.currentTimeMillis()
        phase = "sending"
        streamJob = viewModelScope.launch {
            var stillRunning = false
            try {
                val sid = currentSessionId ?: a.createSession(currentModel).id.also {
                    currentSessionId = it
                    prefs.lastSession = it
                }
                if (editId != null) a.truncate(sid, editId)
                if (sessions.none { it.id == sid }) {
                    // show the new chat in the drawer immediately (named after this first message)
                    val title = text.replace(Regex("\\s+"), " ").take(48).ifBlank { atts.firstOrNull()?.filename ?: "Chat" }
                    sessions.add(0, com.localai.bridge.data.SessionDto(sid, title, currentModel, running = true))
                    currentTitle = title
                }
                val em = emailAccess || onceEmail
                val org = organizerAccess || onceOrganizer
                onceEmail = false; onceOrganizer = false
                consume(a.chat(sid, text, atts.map { it.id }, currentModel.ifBlank { null }, webSearch, autoApprove,
                    if (autoCompress) compressAt / 100.0 else 0.0, email = em, organizer = org, thinking = thinking, ocr = ocr, sandbox = sandbox))
            } catch (e: com.localai.bridge.data.ApiException) {
                if (e.code == 409) {
                    // the PC is still finishing the previous reply (e.g. the phone was off): show it instead of failing
                    stillRunning = true
                    items.removeAt(items.lastIndex)
                    draft = text; pendingAttachments.addAll(atts)
                    toast = "Your PC is still working on the previous reply - showing it now"
                } else items += ChatItem.Notice(nextKey(), e.message ?: e.toString(), error = true)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                items += ChatItem.Notice(nextKey(), e.message ?: e.toString(), error = true)
            } finally {
                streaming = false
            }
            if (stillRunning) reattach()
        }
    }

    private suspend fun consume(events: kotlinx.coroutines.flow.Flow<JsonObject>) {
        streaming = true
        turnCompleted = false
        turnEnded = false
        var dropped = false
        val now = System.currentTimeMillis()
        if (streamStartMs == 0L) streamStartMs = now
        lastEventMs = now
        if (phase.isEmpty()) phase = "sending"
        try {
            events.collect { handle(it) }
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) {
            dropped = true
        } finally {
            streaming = false
            phase = ""; streamStartMs = 0L; liveTokens = 0; liveTps = null
            runCatching { loadSessions() }
        }
        if (turnCompleted) {
            if (soundDone && backgroundAtMs == 0L) playDoneSound()   // reply finished while the chat is open
            syncFromServer()
        }
        else if (dropped || !turnEnded) {
            // phone slept / network changed: the PC keeps working, so reconnect and pick the reply up again
            items += ChatItem.Notice(nextKey(), "Connection lost - reconnecting…")
            scheduleReconnect()
        }
    }

    /** Number of things running on the PC that the current chat screen is not already showing. */
    val backgroundTaskCount: Int
        get() {
            val t = tasks ?: return 0
            val runs = t.runs.count { !(streaming && it.sessionId == currentSessionId) }
            val orphan = if (t.llmBusy == true && t.runs.isEmpty() && t.agents.isEmpty()) 1 else 0
            return runs + t.processes.count { it.session == null || it.session != currentSessionId } + orphan +
                (if (screen == Screen.AGENT) 0 else t.agents.size)
        }

    fun refreshTasks() = viewModelScope.launch {
        try { tasks = api?.tasks() } catch (_: Exception) { }
    }

    /** The PC says the open chat waits for an approval but no dialog is showing: fetch and show it. */
    private suspend fun restoreMissingApprovals() {
        val sid = currentSessionId ?: return
        val run = tasks?.runs?.firstOrNull { it.sessionId == sid } ?: return
        val needA = run.waitingApproval && approvals.isEmpty()
        val needQ = run.waitingQuestion && questions.isEmpty()
        if (!(needA || needQ) || loadingSession) return
        val s = runCatching { api!!.session(sid) }.getOrNull() ?: return
        if (sid != currentSessionId) return
        s.pendingApprovals.filter { p -> approvals.none { it.id == p.id } }.forEach { approvals += it }
        s.pendingQuestions.filter { p -> questions.none { it.id == p.id } }.forEach { questions += it }
    }

    private fun startTaskPolling() {
        tasksJob?.cancel()
        tasksJob = viewModelScope.launch {
            while (true) {
                if (screen != Screen.TASKS) runCatching { tasks = api?.tasks() }  // Tasks screen refreshes itself
                restoreMissingApprovals()
                kotlinx.coroutines.delay(5_000)
            }
        }
    }

    var notifyDone by mutableStateOf(prefs.notifyDone)
    var soundDone by mutableStateOf(prefs.soundDone)
    fun updateNotifyDone(on: Boolean) { notifyDone = on; prefs.notifyDone = on }
    fun updateSoundDone(on: Boolean) { soundDone = on; prefs.soundDone = on; if (on) playDoneSound() }

    /** Short "done" sound (the phone's notification sound). */
    fun playDoneSound() {
        runCatching {
            val ctx = getApplication<Application>()
            android.media.RingtoneManager.getRingtone(ctx,
                android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_NOTIFICATION))?.play()
        }
    }

    fun onAppBackground() {
        tasksJob?.cancel(); pcJob?.cancel(); notifyJob?.cancel(); backgroundAtMs = System.currentTimeMillis()
        val sid = currentSessionId
        if (streaming && notifyDone && sid != null)   // keep watching the reply and say when it is ready
            com.localai.bridge.ReplyWatchService.start(getApplication(), prefs.serverUrl, prefs.token, sid, currentTitle)
    }

    // ---------------------------------------------------------------- voice chat
    var voiceTurn = false                       // this reply answers a spoken question: read it aloud
    var pendingVoice by mutableStateOf(false)   // the widget's Voice button: start listening when the chat shows
    var focusInput by mutableStateOf(false)     // the widget's Ask button: put the cursor in the message box

    fun sendVoice(text: String) {
        if (text.isBlank()) return
        draft = if (draft.isBlank()) text else draft.trimEnd() + " " + text
        voiceTurn = true
        send()
    }

    // ---------------------------------------------------------------- share to the app, widget buttons, notifications
    fun handleIntent(intent: android.content.Intent?) {
        intent ?: return
        val open = intent.getStringExtra("open_session").orEmpty()
        if (open.isNotBlank() && paired) { screen = Screen.CHAT; openSession(open); intent.removeExtra("open_session") }
        when (intent.getStringExtra("widget_action")) {
            "ask" -> { newChat(); screen = Screen.CHAT; focusInput = true }
            "voice" -> { newChat(); screen = Screen.CHAT; pendingVoice = true }
            "models" -> screen = Screen.MODELS
        }
        intent.removeExtra("widget_action")
        val uris = when (intent.action) {
            android.content.Intent.ACTION_SEND -> listOfNotNull(
                if (android.os.Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(android.content.Intent.EXTRA_STREAM, Uri::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableExtra(android.content.Intent.EXTRA_STREAM))
            android.content.Intent.ACTION_SEND_MULTIPLE ->
                (if (android.os.Build.VERSION.SDK_INT >= 33) intent.getParcelableArrayListExtra(android.content.Intent.EXTRA_STREAM, Uri::class.java)
                 else @Suppress("DEPRECATION") intent.getParcelableArrayListExtra(android.content.Intent.EXTRA_STREAM)).orEmpty()
            else -> emptyList()
        }
        val text = if (intent.action == android.content.Intent.ACTION_SEND)
            intent.getStringExtra(android.content.Intent.EXTRA_TEXT).orEmpty() else ""
        if (uris.isEmpty() && text.isBlank()) return
        intent.action = null                     // handled: not again after a screen rotation
        if (!paired) { toast = "Pair with your PC first, then share again"; return }
        screen = Screen.CHAT
        if (text.isNotBlank()) draft = if (draft.isBlank()) text else draft.trimEnd() + "\n" + text
        if (uris.isNotEmpty()) { attach(uris); toast = "Shared ${uris.size} file(s) - add your question and send" }
        else focusInput = true
    }

    private var notifyJob: Job? = null
    /** While the app is open, show finished scheduled tasks and temperature alerts within 30 s. */
    private fun startNotifyPolling() {
        notifyJob?.cancel()
        notifyJob = viewModelScope.launch {
            while (true) {
                runCatching { com.localai.bridge.NotifyWorker.check(getApplication()) }
                kotlinx.coroutines.delay(30_000)
            }
        }
    }

    private fun startPcPolling() {
        pcJob?.cancel()
        pcJob = viewModelScope.launch {
            var wasReady = false
            while (true) {
                runCatching { api?.v100Status() }.getOrNull()?.let { s ->
                    pcStatus = s
                    val ready = s.health == "ready"
                    if (ready && !wasReady) refreshModels()   // chat model list follows the model loaded on the PC
                    wasReady = ready
                }
                kotlinx.coroutines.delay(3_000)
            }
        }
    }

    fun stopTask(sid: String) = viewModelScope.launch {
        try { api?.stopTask(sid); toast = "Stopping…" } catch (e: Exception) { toast = e.message }
        kotlinx.coroutines.delay(800); refreshTasks()
    }

    fun stopAgent(id: String) = viewModelScope.launch {
        try { api?.agentAbort(id); toast = "Stopping the agent…" }
        catch (e: Exception) { toast = e.message }
        kotlinx.coroutines.delay(800); refreshTasks()
    }

    fun killProcess(pid: Long) = viewModelScope.launch {
        try { api?.killProcess(pid); toast = "Process killed" } catch (e: Exception) { toast = e.message }
        kotlinx.coroutines.delay(500); refreshTasks()
    }

    fun abortLlm() = viewModelScope.launch {
        try { val r = api?.abortLlm(); toast = "LLM stopped (${r?.get("cancelled") ?: 0} generation(s) cancelled)" }
        catch (e: Exception) { toast = e.message }
        kotlinx.coroutines.delay(800); refreshTasks()
    }

    fun killAll() = viewModelScope.launch {
        try {
            val r = api?.killAll()
            toast = "Stopped ${r?.get("runs") ?: 0} chat(s), killed ${r?.get("processes") ?: 0} process(es)"
        } catch (e: Exception) { toast = e.message }
        kotlinx.coroutines.delay(800); refreshTasks()
    }

    /** Called when the app comes back to the foreground. */
    fun onAppForeground() {
        com.localai.bridge.ReplyWatchService.stop(getApplication())
        if (paired) { startTaskPolling(); startPcPolling(); startNotifyPolling() }
        val away = backgroundAtMs > 0 && System.currentTimeMillis() - backgroundAtMs > 3_000
        backgroundAtMs = 0L
        if (!paired || currentSessionId == null) return
        if (streaming) {
            // Android or the tunnel usually drops the connection while the app is in the background, without an error
            // until a long timeout: the reply looked stopped. The PC kept working, so reconnect now and catch up.
            if (away) viewModelScope.launch { streamJob?.cancelAndJoin(); reattach() }
            return
        }
        viewModelScope.launch { reattach() }
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectJob = viewModelScope.launch {
            var wait = 2_000L
            repeat(40) {
                kotlinx.coroutines.delay(wait)
                if (streaming || reattach()) return@launch
                wait = (wait * 2).coerceAtMost(30_000L)
            }
        }
    }

    /** Re-sync the open chat with the PC; re-attach to a reply that is still running. False if unreachable. */
    private suspend fun reattach(): Boolean {
        val a = api ?: return false
        val sid = currentSessionId ?: return false
        val s = try { a.session(sid) } catch (e: Exception) { return false }
        if (streaming || sid != currentSessionId) return true
        reconnectJob?.cancel()
        stats = s.stats ?: stats
        items.clear(); items.addAll(toItems(s.messages, s.summaryUpto))
        approvals.clear(); approvals.addAll(s.pendingApprovals)
        questions.clear(); questions.addAll(s.pendingQuestions)
        plan.clear(); plan.addAll(s.plan)
        if (s.running) {
            trimToLastUser()
            streamStartMs = System.currentTimeMillis(); phase = "resuming"
            streamJob = viewModelScope.launch { consume(a.resume(sid)) }
        }
        return true
    }

    /** Summarize the older part of this chat now (frees context; full history stays visible). */
    fun compressNow() {
        val a = api ?: return
        val sid = currentSessionId
        if (sid == null) { toast = "Nothing to compress yet"; return }
        if (streaming) return
        streaming = true
        streamStartMs = System.currentTimeMillis()
        phase = "compressing"
        streamJob = viewModelScope.launch {
            try { consume(a.compress(sid)) } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { items += ChatItem.Notice(nextKey(), e.message ?: e.toString(), error = true) }
            finally { streaming = false }
        }
    }

    fun updateAutoCompress(on: Boolean) { autoCompress = on; prefs.autoCompress = on }
    fun updateAutoRead(on: Boolean) { autoRead = on; prefs.autoRead = on; if (!on) speaker.stop() }
    fun updateSpeechRate(r: Float) { speechRate = r; prefs.speechRate = r; speaker.rate = r }
    /** Read one reply aloud, or stop if it is the one being read. */
    fun toggleSpeak(key: String, text: String) {
        if (speakingKey == key) { speaker.stop(); speakingKey = null; return }
        speakingKey = key; speaker.speak(text)
    }
    override fun onCleared() { speaker.shutdown(); super.onCleared() }
    fun updateCompressAt(pct: Int) { compressAt = pct; prefs.compressAt = pct }

    /** Reload the finished conversation so every message has its server id (needed for editing). */
    private suspend fun syncFromServer() {
        val sid = currentSessionId ?: return
        runCatching {
            val s = api!!.session(sid)
            stats = s.stats ?: stats
            if (!s.running && !streaming) { items.clear(); items.addAll(toItems(s.messages, s.summaryUpto)) }
        }
    }

    private fun str(ev: JsonObject, k: String) = ev[k]?.jsonPrimitive?.contentOrNull.orEmpty()

    private fun handle(ev: JsonObject) {
        lastEventMs = System.currentTimeMillis()
        when (str(ev, "type")) {
            "phase" -> {
                phase = str(ev, "phase"); phaseTool = str(ev, "name")
                if (phase == "prompt") { liveTokens = 0; liveTps = null }
            }
            "progress" -> {
                phase = str(ev, "phase")
                liveTokens = ev["tokens"]?.jsonPrimitive?.contentOrNull?.toIntOrNull() ?: liveTokens
                liveTps = ev["tps"]?.jsonPrimitive?.contentOrNull?.toDoubleOrNull() ?: liveTps
            }
            "stats" -> stats = runCatching { api!!.json.decodeFromJsonElement<SessionStats>(ev) }.getOrNull() ?: stats
            "delta", "reasoning" -> {
                val isReasoning = str(ev, "type") == "reasoning"
                if (phase == "prompt" || phase == "sending") phase = if (isReasoning) "thinking" else "writing"
                val last = items.lastOrNull()
                val cur = if (last is ChatItem.Assistant) last else ChatItem.Assistant(nextKey(), "", "").also { items += it }
                val upd = if (isReasoning) cur.copy(reasoning = cur.reasoning + str(ev, "text"))
                else cur.copy(text = cur.text + str(ev, "text"))
                items[items.lastIndex] = upd
            }
            "tool_call" -> items += ChatItem.Tool(
                str(ev, "id"), str(ev, "name"), ev["args"]?.jsonObject ?: JsonObject(emptyMap()), null, "running")
            "approval_required" -> {
                val id = str(ev, "id")
                updateTool(id) { it.copy(status = "awaiting") }
                if (approvals.none { it.id == id })
                    approvals += PendingApproval(id, str(ev, "name"), ev["args"]?.jsonObject ?: JsonObject(emptyMap()))
            }
            "question_required" -> {
                val id = str(ev, "id")
                updateTool(id) { it.copy(status = "awaiting") }
                if (questions.none { it.id == id }) runCatching {
                    api!!.json.decodeFromJsonElement<com.localai.bridge.data.PendingQuestion>(ev)
                }.getOrNull()?.let { questions += it }
            }
            "question_answered" -> questions.removeAll { it.id == str(ev, "id") }
            "tasks" -> runCatching {
                api!!.json.decodeFromJsonElement<List<com.localai.bridge.data.PlanStep>>(ev["tasks"]!!)
            }.getOrNull()?.let { plan.clear(); plan.addAll(it) }
            "tool_result" -> {
                val id = str(ev, "id")
                approvals.removeAll { it.id == id }
                questions.removeAll { it.id == id }
                val atts = runCatching {
                    api!!.json.decodeFromJsonElement<List<AttachmentRef>>(ev["attachments"]!!)
                }.getOrDefault(emptyList())
                updateTool(id) { it.copy(output = str(ev, "output"), status = "done", attachments = atts) }
            }
            "title" -> currentTitle = str(ev, "title")
            "done" -> {
                turnCompleted = true; turnEnded = true
                if (autoRead || voiceTurn) (items.lastOrNull { it is ChatItem.Assistant } as? ChatItem.Assistant)
                    ?.takeIf { it.text.isNotBlank() }?.let { speakingKey = it.key; speaker.speak(it.text) }
                voiceTurn = false
            }
            "compressed" -> items += ChatItem.Notice(nextKey(),
                "Compressed ${str(ev, "messages")} earlier messages into a summary - context freed.")
            "notice" -> items += ChatItem.Notice(nextKey(), str(ev, "text"))
            "error" -> { turnEnded = true; items += ChatItem.Notice(nextKey(), str(ev, "message"), error = true) }
        }
    }

    private fun updateTool(id: String, f: (ChatItem.Tool) -> ChatItem.Tool) {
        val i = items.indexOfFirst { it is ChatItem.Tool && it.key == id }
        if (i >= 0) items[i] = f(items[i] as ChatItem.Tool)
    }

    fun respondApproval(p: PendingApproval, ok: Boolean) = viewModelScope.launch {
        approvals.remove(p)
        if (ok) updateTool(p.id) { it.copy(status = "running") }
        try { api?.approve(p.id, ok) } catch (e: Exception) { toast = e.message }
    }

    /** Send the user's choice for an ask_user question; the reply on the PC continues with it. */
    fun answerQuestion(q: com.localai.bridge.data.PendingQuestion, answer: String) = viewModelScope.launch {
        if (answer.isBlank()) return@launch
        questions.remove(q)
        updateTool(q.id) { it.copy(status = "running") }
        try { api?.answerQuestion(q.id, answer) } catch (e: Exception) { toast = e.message }
    }

    /** Tap on an option the model listed in plain text: send it as the next message. */
    fun quickReply(text: String) { if (streaming) return; draft = text; send() }

    fun stop() = viewModelScope.launch {
        currentSessionId?.let { runCatching { api?.stop(it) } }
        approvals.clear(); questions.clear()
    }

    // ---------------------------------------------------------------- edit / regenerate / theme
    fun startEdit(item: ChatItem.User) {
        if (streaming) return
        if (item.messageId == null) { toast = "Wait a moment - message is still syncing"; return }
        editingMessageId = item.messageId
        draft = item.text
        pendingAttachments.clear(); pendingAttachments.addAll(item.attachments)
    }

    fun cancelEdit() {
        editingMessageId = null
        draft = ""
        pendingAttachments.clear()
    }

    /** Re-run the last user message to get a new answer. */
    fun regenerate() {
        val last = items.lastOrNull { it is ChatItem.User } as? ChatItem.User ?: return
        startEdit(last)
        if (editingMessageId != null) send()
    }

    fun toggleSandbox() {
        sandbox = !sandbox
        prefs.sandbox = sandbox
        toast = if (sandbox) "Sandbox ON: code runs without network and without access to your files (no approval needed)"
                else "Sandbox OFF: code runs normally on the PC"
    }

    fun updateOcr(mode: String) {
        ocr = mode
        prefs.ocr = mode
        toast = "OCR: " + (OCR_MODES.firstOrNull { it.first == mode }?.let { "${it.second} (${it.third})" } ?: mode)
    }

    fun updateThinking(mode: String) {
        thinking = mode
        prefs.thinking = mode
        toast = "Thinking: " + (THINKING_MODES.firstOrNull { it.first == mode }?.let { "${it.second} (${it.third})" } ?: mode)
    }

    fun toggleWebSearch() {
        webSearch = !webSearch
        prefs.webSearch = webSearch
        toast = if (webSearch) "Web search ON" else "Web search OFF"
    }

    fun updateAutoApprove(on: Boolean) {
        autoApprove = on
        prefs.autoApprove = on
    }

    fun setTheme(mode: String) {
        themeMode = mode
        prefs.themeMode = mode
    }

    /** Capture the PC screen and attach it to the next message. */
    fun attachScreenshot() = viewModelScope.launch {
        val a = api ?: return@launch
        uploading = true
        try { pendingAttachments += a.screenshot() } catch (e: Exception) { toast = "Screenshot failed: ${e.message}" }
        uploading = false
    }

    // ---------------------------------------------------------------- attachments
    fun attach(uris: List<Uri>, nameOverride: String? = null) = viewModelScope.launch {
        val a = api ?: return@launch
        uploading = true
        try {
            for (u in uris) pendingAttachments += a.upload(getApplication<Application>().contentResolver, u, nameOverride)
        } catch (e: Exception) {
            toast = "Upload failed: ${e.message}"
        } finally {
            uploading = false
        }
    }
}
