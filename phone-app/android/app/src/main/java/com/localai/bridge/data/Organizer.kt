package com.localai.bridge.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.put

// ------------------------------------------------------------------ notes, tasks, calendar, Google (stored on the PC)

@Serializable
data class NoteDto(val id: Long, val title: String? = "", val body: String? = "", val updated: Double = 0.0)

@Serializable
data class TaskDto(
    val id: Long, val title: String? = "", val notes: String? = "", val due: String? = "",
    val priority: String? = "normal", val done: Boolean = false,
    @SerialName("email_id") val emailId: String? = "",          // set when the task came from an email
)

@Serializable
data class EventDto(
    val id: JsonElement? = null, val title: String? = "", val start: String? = "", val end: String? = "",
    val location: String? = "", val notes: String? = "", val source: String = "local",
) { val idText get() = (id as? JsonPrimitive)?.contentOrNull.orEmpty() }

@Serializable
data class GoogleStatus(
    val configured: Boolean = false, val connected: Boolean = false, val email: String = "",
    @SerialName("redirect_uri") val redirectUri: String = "",
)

@Serializable
data class MailDto(
    val id: String, val from: String = "", val to: String = "", val subject: String = "", val date: String = "",
    val snippet: String = "", val unread: Boolean = false,
)

@Serializable
data class MailPage(val messages: List<MailDto> = emptyList(), val next: String = "", val total: Int = 0)

@Serializable
data class MailFull(
    val id: String, val from: String = "", val to: String = "", val subject: String = "", val date: String = "",
    val body: String = "",
)

suspend fun Api.notes(q: String = ""): List<NoteDto> = getJson("/api/notes" + if (q.isBlank()) "" else "?q=" + java.net.URLEncoder.encode(q, "UTF-8"))
suspend fun Api.saveNote(title: String, body: String, id: Long? = null): NoteDto =
    sendJson(if (id == null) "POST" else "PUT", "/api/notes" + (id?.let { "/$it" } ?: ""),
        buildJsonObject { put("title", title); put("body", body) })

suspend fun Api.organizerTasks(status: String = "all"): List<TaskDto> = getJson("/api/tasks_list?status=$status")
suspend fun Api.addTask(title: String, due: String, priority: String, notes: String = ""): TaskDto =
    sendJson("POST", "/api/tasks_list", buildJsonObject { put("title", title); put("due", due); put("priority", priority); put("notes", notes) })
suspend fun Api.setTaskDone(id: Long, done: Boolean): TaskDto =
    sendJson("PATCH", "/api/tasks_list/$id", buildJsonObject { put("done", done) })

suspend fun Api.events(start: String = "", end: String = ""): List<EventDto> = getJson("/api/events?start=$start&end=$end")
suspend fun Api.addEvent(title: String, start: String, end: String, location: String): EventDto =
    sendJson("POST", "/api/events", buildJsonObject { put("title", title); put("start", start); put("end", end); put("location", location) })

suspend fun Api.deleteOrganizer(kind: String, id: String) { rawSend("DELETE", "/api/organizer/$kind/$id", null) }

suspend fun Api.googleStatus(): GoogleStatus = getJson("/api/google/status")
suspend fun Api.googleClient(id: String, secret: String): GoogleStatus =
    sendJson("POST", "/api/google/client", buildJsonObject { put("client_id", id); put("client_secret", secret) })
suspend fun Api.googleConnect(): JsonObject = sendJson("POST", "/api/google/connect", JsonObject(emptyMap()))
suspend fun Api.googleDisconnect(): GoogleStatus = sendJson("POST", "/api/google/disconnect", JsonObject(emptyMap()))
/** A page of mail. Also accepts an older PC server, which sends a plain list (no paging). */
suspend fun Api.mail(q: String = "in:inbox", page: String = ""): MailPage {
    val raw = rawGet("/api/google/mail?n=25&q=" + java.net.URLEncoder.encode(q, "UTF-8") + "&page=" + java.net.URLEncoder.encode(page, "UTF-8"))
    val el = json.parseToJsonElement(raw)
    return if (el is kotlinx.serialization.json.JsonArray) MailPage(json.decodeFromJsonElement(el))
           else json.decodeFromJsonElement(el)
}
suspend fun Api.mailOne(id: String): MailFull = getJson("/api/google/mail/$id")

suspend fun Api.saveDraft(body: String, to: String, subject: String, replyToId: String): JsonObject =
    sendJson("POST", "/api/google/draft", buildJsonObject {
        put("body", body); put("to", to); put("subject", subject); put("reply_to_id", replyToId)
    })

suspend fun Api.draftOf(messageId: String): String =
    getJson<JsonObject>("/api/google/draft_of/$messageId")["draft_id"]?.let { (it as? JsonPrimitive)?.contentOrNull }.orEmpty()
suspend fun Api.updateDraft(draftId: String, body: String, subject: String, to: String): JsonObject =
    sendJson("PUT", "/api/google/draft/$draftId", buildJsonObject { put("body", body); put("subject", subject); put("to", to) })
suspend fun Api.sendDraft(draftId: String): JsonObject = sendJson("POST", "/api/google/draft/$draftId/send", JsonObject(emptyMap()))

// ---- tasks suggested from email (the AI reads Gmail; the user accepts or dismisses each one)
@Serializable
data class EmailTaskDto(
    val id: Long, val title: String? = "", val notes: String? = "", val due: String? = "", val priority: String? = "normal",
    @SerialName("email_id") val emailId: String? = "", @SerialName("email_subject") val emailSubject: String? = "",
    @SerialName("email_from") val emailFrom: String? = "",
    val kind: String? = "task",                                  // task | reply (someone waits for your answer)
)

@Serializable
data class ScanStatus(val running: Boolean = false, val done: Int = 0, val total: Int = 0, val found: Int = 0, val error: String = "")

suspend fun Api.emailTasks(): List<EmailTaskDto> = getJson("/api/email_tasks")
suspend fun Api.scanEmailTasks(query: String, n: Int): ScanStatus =
    sendJson("POST", "/api/email_tasks/scan", buildJsonObject { put("query", query); put("n", n) })
suspend fun Api.scanStatus(): ScanStatus = getJson("/api/email_tasks/status")
suspend fun Api.acceptEmailTask(id: Long): JsonObject = sendJson("POST", "/api/email_tasks/$id/accept", JsonObject(emptyMap()))
suspend fun Api.dismissEmailTask(id: Long): JsonObject = sendJson("POST", "/api/email_tasks/$id/dismiss", JsonObject(emptyMap()))
suspend fun Api.forgetEmailScan(): JsonObject = sendJson("POST", "/api/email_tasks/forget", JsonObject(emptyMap()))

// ---- long-term memory (meaning search, categories, auto-remember)
suspend fun Api.memorySearch(q: String = "", category: String = ""): List<MemoryDto> =
    getJson("/api/memory?q=" + java.net.URLEncoder.encode(q, "UTF-8") + "&category=" + category)
suspend fun Api.memoryStatus(): MemoryStatus = getJson("/api/memory/status")
suspend fun Api.setAutoMemory(on: Boolean): MemoryStatus = sendJson("POST", "/api/memory/settings", buildJsonObject { put("auto_memory", on) })
suspend fun Api.addMemoryIn(content: String, category: String): MemoryDto =
    sendJson("POST", "/api/memory", buildJsonObject { put("content", content); put("category", category) })
suspend fun Api.editMemory(id: Long, content: String, category: String): MemoryDto =
    sendJson("PUT", "/api/memory/$id", buildJsonObject { put("content", content); put("category", category) })
