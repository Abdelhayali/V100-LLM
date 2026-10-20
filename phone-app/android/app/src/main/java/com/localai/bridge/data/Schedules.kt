package com.localai.bridge.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

// ------------------------------------------------------------------ scheduled prompts, temperature alerts, notifications
@Serializable
data class ScheduleDto(
    val id: Int = 0,
    val name: String = "",
    val prompt: String = "",
    val kind: String = "daily",                 // daily | every
    val at: String = "08:00",
    @SerialName("every_min") val everyMin: Int = 60,
    val web: Boolean = false,
    val email: Boolean = false,
    val organizer: Boolean = false,
    val enabled: Boolean = true,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("last_run") val lastRun: Double? = null,
    @SerialName("next_run") val nextRun: Double? = null,
    @SerialName("last_status") val lastStatus: String? = null,
)

@Serializable
data class NotifyEvent(
    val id: Int = 0,
    val kind: String = "",
    val title: String = "",
    val body: String = "",
    @SerialName("session_id") val sessionId: String? = null,
)

@Serializable
data class NotifyFeed(val events: List<NotifyEvent> = emptyList(), @SerialName("last_id") val lastId: Int = 0)

@Serializable
data class AlertsDto(@SerialName("gpu_c") val gpuC: Double = 0.0, @SerialName("cpu_c") val cpuC: Double = 0.0)

private fun ScheduleDto.body() = buildJsonObject {
    put("name", name); put("prompt", prompt); put("kind", kind); put("at", at); put("every_min", everyMin)
    put("web", web); put("email", email); put("organizer", organizer); put("enabled", enabled)
}

suspend fun Api.schedules(): List<ScheduleDto> = getJson("/api/schedules")
suspend fun Api.scheduleSave(s: ScheduleDto): ScheduleDto =
    if (s.id == 0) sendJson("POST", "/api/schedules", s.body()) else sendJson("PUT", "/api/schedules/${s.id}", s.body())
suspend fun Api.scheduleDelete(id: Int): JsonObject = sendJson("DELETE", "/api/schedules/$id", null)
suspend fun Api.scheduleRunNow(id: Int): JsonObject = sendJson("POST", "/api/schedules/$id/run", JsonObject(emptyMap()))
suspend fun Api.notifyFeed(since: Int): NotifyFeed = getJson("/api/notify?since=$since")
suspend fun Api.alerts(): AlertsDto = getJson("/api/alerts")
suspend fun Api.alertsSet(gpuC: Double, cpuC: Double): AlertsDto =
    sendJson("POST", "/api/alerts", buildJsonObject { put("gpu_c", gpuC); put("cpu_c", cpuC) })

@Serializable
data class TranslateDto(val text: String = "", val to: String = "")

/** Translator screen: one direct translation by the PC's model (no chat history). */
suspend fun Api.translate(text: String, to: String): String =
    sendJson<TranslateDto>("POST", "/api/translate", buildJsonObject { put("text", text); put("to", to) }).text

// ------------------------------------------------------------------ audit log (every tool action of the AI)
@Serializable
data class AuditRow(
    val id: Int = 0,
    val ts: Double = 0.0,
    @SerialName("session_id") val sessionId: String? = null,
    val tool: String = "",
    val summary: String = "",
    val approval: String = "",
    val ok: Int = 1,
    val result: String = "",
    val source: String = "",
    val chat: String? = null,
)

suspend fun Api.audit(q: String = ""): List<AuditRow> =
    getJson("/api/audit?limit=300" + if (q.isNotBlank()) "&q=" + java.net.URLEncoder.encode(q, "UTF-8") else "")

// ------------------------------------------------------------------ deep research
@Serializable
data class ResearchRun(
    val id: String = "",
    @SerialName("session_id") val sessionId: String = "",
    val question: String = "",
    val depth: String = "",
    val status: String = "",
    val progress: String = "",
    val log: List<String> = emptyList(),
    val started: Double = 0.0,
    val sources: Int = 0,
    val error: String = "",
)

suspend fun Api.research(): List<ResearchRun> = getJson("/api/research")
suspend fun Api.researchStart(question: String, depth: String): ResearchRun =
    sendJson("POST", "/api/research", buildJsonObject { put("question", question); put("depth", depth) })

// ------------------------------------------------------------------ voice notes
@Serializable
data class VoiceJob(
    val id: String = "",
    val status: String = "",
    val progress: String = "",
    val started: Double = 0.0,
    @SerialName("session_id") val sessionId: String = "",
    val title: String = "",
    val error: String = "",
    val duration: Double = 0.0,
    @SerialName("tasks_added") val tasksAdded: Int = 0,
)

suspend fun Api.voiceJobs(): List<VoiceJob> = getJson("/api/notes/voice")

// ------------------------------------------------------------------ long-term projects
@Serializable
data class ProjectChat(val id: String = "", val title: String = "", val updated: Double = 0.0)

@Serializable
data class ProjectDto(
    val id: Int = 0,
    val name: String = "",
    val goal: String = "",
    val notes: String = "",
    val folder: String = "",
    val chats: List<ProjectChat> = emptyList(),
    val files: List<String> = emptyList(),
)

suspend fun Api.projects(): List<ProjectDto> = getJson("/api/projects")
suspend fun Api.projectSave(p: ProjectDto): ProjectDto {
    val b = buildJsonObject { put("name", p.name); put("goal", p.goal); put("notes", p.notes) }
    return if (p.id == 0) sendJson("POST", "/api/projects", b) else sendJson("PUT", "/api/projects/${p.id}", b)
}
suspend fun Api.projectDelete(id: Int): JsonObject = sendJson("DELETE", "/api/projects/$id", null)
suspend fun Api.projectNewChat(id: Int): SessionDto = sendJson("POST", "/api/projects/$id/chat", JsonObject(emptyMap()))
suspend fun Api.projectSchedule(p: ProjectDto, at: String, prompt: String): ScheduleDto =
    sendJson("POST", "/api/schedules", buildJsonObject {
        put("name", "Project: ${p.name}"); put("prompt", prompt); put("kind", "daily"); put("at", at)
        put("every_min", 60); put("web", true); put("email", false); put("organizer", true); put("enabled", true)
        put("project_id", p.id)
    })

// ------------------------------------------------------------------ PC voices (Piper on the PC)
@Serializable
data class PcVoice(val id: String = "", val lang: String = "", val name: String = "", val quality: String = "")

suspend fun Api.pcVoices(): List<PcVoice> = getJson("/api/tts/voices")
