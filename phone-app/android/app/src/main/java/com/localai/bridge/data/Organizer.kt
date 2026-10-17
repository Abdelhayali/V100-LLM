package com.localai.bridge.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.put

// ------------------------------------------------------------------ notes, tasks, calendar, Google (stored on the PC)

@Serializable
data class NoteDto(val id: Long, val title: String? = "", val body: String? = "", val updated: Double = 0.0)

@Serializable
data class TaskDto(
    val id: Long, val title: String? = "", val notes: String? = "", val due: String? = "",
    val priority: String? = "normal", val done: Boolean = false,
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
suspend fun Api.addTask(title: String, due: String, priority: String): TaskDto =
    sendJson("POST", "/api/tasks_list", buildJsonObject { put("title", title); put("due", due); put("priority", priority) })
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
suspend fun Api.mail(q: String = "in:inbox", page: String = ""): MailPage =
    getJson("/api/google/mail?n=25&q=" + java.net.URLEncoder.encode(q, "UTF-8") + "&page=" + java.net.URLEncoder.encode(page, "UTF-8"))
suspend fun Api.mailOne(id: String): MailFull = getJson("/api/google/mail/$id")
