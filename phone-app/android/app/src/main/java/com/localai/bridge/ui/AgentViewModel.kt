package com.localai.bridge.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.localai.bridge.data.AgentDetail
import com.localai.bridge.data.AgentPart
import com.localai.bridge.data.AgentPermission
import com.localai.bridge.data.AgentSessionDto
import com.localai.bridge.data.Api
import com.localai.bridge.data.agentAbort
import com.localai.bridge.data.agentEvents
import com.localai.bridge.data.agentPrompt
import com.localai.bridge.data.agentReply
import com.localai.bridge.data.agentSession
import com.localai.bridge.data.agentSessions
import com.localai.bridge.data.agentStatus
import com.localai.bridge.data.createAgentSession
import com.localai.bridge.data.deleteAgentSession
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** One message of an agent session; parts are updated live while the agent works. */
class AgentMsg(val id: String, role: String) {
    var role by mutableStateOf(role)
    val parts = mutableStateListOf<AgentPart>()
}

/** BETA: state of the OpenCode "Code agent" screen. */
class AgentViewModel(app: Application) : AndroidViewModel(app) {
    var api: Api? = null
    var autoApprove by mutableStateOf(false)   // approve edits/commands of this agent without asking
    var autoInitialized = false

    val sessions = mutableStateListOf<AgentSessionDto>()
    var installed by mutableStateOf<Boolean?>(null)
    var current by mutableStateOf<AgentDetail?>(null)
    val messages = mutableStateListOf<AgentMsg>()
    val permissions = mutableStateListOf<AgentPermission>()
    var busy by mutableStateOf(false)
    var busySinceMs by mutableStateOf(0L)
    var lastEventMs by mutableStateOf(0L)
    var contextUsed by mutableStateOf<Long?>(null)
    var connected by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var loading by mutableStateOf(false)
    var toast by mutableStateOf<String?>(null)

    private var streamJob: Job? = null

    fun refreshList() = viewModelScope.launch {
        val a = api ?: return@launch
        try {
            installed = a.agentStatus().installed
            val l = a.agentSessions(); sessions.clear(); sessions.addAll(l)
            error = null
        } catch (e: Exception) { error = e.message }
    }

    fun create(directory: String) = viewModelScope.launch {
        val a = api ?: return@launch
        loading = true
        try { open(a.createAgentSession(directory).id) } catch (e: Exception) { toast = e.message }
        loading = false
    }

    fun delete(id: String) = viewModelScope.launch {
        try { api?.deleteAgentSession(id); sessions.removeAll { it.id == id } } catch (e: Exception) { toast = e.message }
    }

    fun close() {
        streamJob?.cancel(); streamJob = null
        current = null; messages.clear(); permissions.clear(); busy = false
        refreshList()
    }

    fun open(id: String) {
        streamJob?.cancel()
        streamJob = viewModelScope.launch {
            loading = true
            if (!load(id)) { loading = false; return@launch }
            loading = false
            // keep a live connection while the session is open; reconnect if it drops (phone sleep, network)
            var wait = 1_000L
            while (true) {
                try {
                    connected = true
                    api!!.agentEvents(id, autoApprove).collect { handle(it); wait = 1_000L }
                } catch (e: CancellationException) { throw e } catch (_: Exception) { }
                connected = false
                delay(wait); wait = (wait * 2).coerceAtMost(15_000L)
                load(id)  // catch up on whatever happened while disconnected
            }
        }
    }

    private suspend fun load(id: String): Boolean {
        val a = api ?: return false
        return try {
            val d = a.agentSession(id)
            current = d
            messages.clear()
            d.messages.forEach { m ->
                messages += AgentMsg(m.id ?: "", m.role ?: "assistant").also { it.parts.addAll(m.parts) }
            }
            permissions.clear(); permissions.addAll(d.permissions)
            markBusy(d.busy)
            contextUsed = d.contextUsed
            error = null
            true
        } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.message; false }
    }

    private fun markBusy(b: Boolean) {
        if (b && !busy) busySinceMs = System.currentTimeMillis()
        busy = b
    }

    private fun str(ev: JsonObject, k: String) = ev[k]?.jsonPrimitive?.contentOrNull.orEmpty()

    private fun msg(id: String, role: String = "assistant"): AgentMsg =
        messages.firstOrNull { it.id == id } ?: AgentMsg(id, role).also { messages += it }

    private fun handle(ev: JsonObject) {
        lastEventMs = System.currentTimeMillis()
        val json = api!!.json
        when (str(ev, "type")) {
            "part" -> {
                val part = json.decodeFromJsonElement<AgentPart>(ev["part"]!!.jsonObject)
                val m = msg(str(ev, "message_id"))
                val i = m.parts.indexOfFirst { it.id == part.id }
                if (i >= 0) m.parts[i] = part else m.parts += part
            }
            "delta" -> {
                val m = msg(str(ev, "message_id"))
                val pid = str(ev, "part_id")
                val i = m.parts.indexOfFirst { it.id == pid }
                if (i >= 0) m.parts[i] = m.parts[i].copy(text = m.parts[i].text + str(ev, "text"))
                else m.parts += AgentPart(pid, str(ev, "kind"), text = str(ev, "text"))
                markBusy(true)
            }
            "message" -> {
                val id = str(ev, "id")
                val role = str(ev, "role").ifEmpty { "assistant" }
                if (id.isNotEmpty()) {
                    val existing = messages.firstOrNull { it.id == id }
                    if (existing != null) existing.role = role else messages += AgentMsg(id, role)
                    if (role == "user") messages.removeAll { it.id.startsWith("local-") }  // real task arrived
                }
                ev["context_used"]?.jsonPrimitive?.contentOrNull?.toLongOrNull()?.let { if (it > 0) contextUsed = it }
            }
            "permission" -> {
                val p = json.decodeFromJsonElement<AgentPermission>(ev)
                if (permissions.none { it.id == p.id }) permissions += p
            }
            "permission_replied" -> permissions.removeAll { it.id == str(ev, "id") }
            "status" -> markBusy(ev["busy"]?.jsonPrimitive?.contentOrNull == "true")
            "idle" -> markBusy(false)
            "error" -> { toast = str(ev, "message"); markBusy(false) }
            "notice" -> toast = str(ev, "text")
        }
    }

    fun send(text: String) = viewModelScope.launch {
        val a = api ?: return@launch
        val id = current?.id ?: return@launch
        // show the task immediately; the real message replaces it when the agent picks it up
        messages += AgentMsg("local-${System.currentTimeMillis()}", "user").also {
            it.parts += AgentPart("local", "text", text = text)
        }
        markBusy(true)
        try { a.agentPrompt(id, text) } catch (e: Exception) { toast = e.message; markBusy(false) }
    }

    fun abort() = viewModelScope.launch {
        val id = current?.id ?: return@launch
        try { api?.agentAbort(id); toast = "Stopping the agent…" } catch (e: Exception) { toast = e.message }
    }

    /** Turn auto-approve on/off; pending requests are approved right away and the live stream restarts. */
    fun updateAutoApprove(on: Boolean) {
        autoApprove = on
        if (on) permissions.toList().forEach { reply(it, "once") }
        current?.id?.let { open(it) }
    }

    fun reply(p: AgentPermission, reply: String) = viewModelScope.launch {
        permissions.remove(p)
        try { api?.agentReply(p.id, reply, current?.directory ?: "") } catch (e: Exception) { toast = e.message }
    }
}
