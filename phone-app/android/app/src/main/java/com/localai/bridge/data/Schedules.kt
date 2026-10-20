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
    val knowledge: List<KnowledgeDto> = emptyList(),
)

@Serializable
data class KnowledgeDto(val name: String = "", val size: Long = 0, val chars: Long = 0, val kind: String = "",
                        val description: String = "")

suspend fun Api.projects(): List<ProjectDto> = getJson("/api/projects")
suspend fun Api.projectSave(p: ProjectDto): ProjectDto {
    val b = buildJsonObject { put("name", p.name); put("goal", p.goal); put("notes", p.notes) }
    return if (p.id == 0) sendJson("POST", "/api/projects", b) else sendJson("PUT", "/api/projects/${p.id}", b)
}
suspend fun Api.projectDelete(id: Int): JsonObject = sendJson("DELETE", "/api/projects/$id", null)
suspend fun Api.projectNewChat(id: Int, title: String = ""): SessionDto =
    sendJson("POST", "/api/projects/$id/chat", buildJsonObject { put("title", title) })
suspend fun Api.knowledgeDelete(id: Int, name: String): JsonObject =
    sendJson("DELETE", "/api/projects/$id/knowledge/" + java.net.URLEncoder.encode(name, "UTF-8").replace("+", "%20"), null)
suspend fun Api.knowledgeDescribe(id: Int, name: String, description: String): JsonObject =
    sendJson("PUT", "/api/projects/$id/knowledge/" + java.net.URLEncoder.encode(name, "UTF-8").replace("+", "%20"),
        buildJsonObject { put("title", description) })
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

// ------------------------------------------------------------------ temporary chats, private vault, profile
suspend fun Api.tempSession(): SessionDto = sendJson("POST", "/api/sessions/temp", JsonObject(emptyMap()))
suspend fun Api.vaultUnlock(): JsonObject = sendJson("POST", "/api/vault/unlock", JsonObject(emptyMap()))
suspend fun Api.vaultSessions(): List<SessionDto> = getJson("/api/vault/sessions")
suspend fun Api.vaultNew(): SessionDto = sendJson("POST", "/api/vault/sessions", JsonObject(emptyMap()))

@Serializable
data class ProfileDto(val text: String = "", val enabled: Int = 1, val updated: Double = 0.0, val building: Int = 0)

suspend fun Api.profile(): ProfileDto = getJson("/api/profile")
suspend fun Api.profileSave(enabled: Boolean, text: String?): ProfileDto =
    sendJson("PUT", "/api/profile", buildJsonObject { put("enabled", enabled); if (text != null) put("text", text) })
suspend fun Api.profileRebuild(): ProfileDto = sendJson("POST", "/api/profile/rebuild", JsonObject(emptyMap()))

// ------------------------------------------------------------------ language tutor
@Serializable
data class Correction(val wrong: String = "", val right: String = "", val why: String = "")

@Serializable
data class TutorTurn(val reply: String = "", val corrections: List<Correction> = emptyList(), val better: String = "",
                     val score: Double? = null)

@Serializable
data class WordMark(val word: String = "", val ok: Boolean = true)

@Serializable
data class PronounceResult(val score: Int = 0, val words: List<WordMark> = emptyList(), val missed: List<String> = emptyList(),
                           val tips: String = "")

@Serializable
data class SentenceDto(val sentence: String = "")

suspend fun Api.tutorTurn(lang: String, level: String, text: String, history: List<Pair<String, String>>): TutorTurn =
    sendJson("POST", "/api/tutor/turn", buildJsonObject {
        put("lang", lang); put("level", level); put("text", text)
        put("history", kotlinx.serialization.json.JsonArray(history.map { (r, c) -> buildJsonObject { put("role", r); put("content", c) } }))
    })
suspend fun Api.tutorSentence(lang: String, level: String): String =
    sendJson<SentenceDto>("POST", "/api/tutor/sentence", buildJsonObject { put("lang", lang); put("level", level) }).sentence
suspend fun Api.tutorPronounce(lang: String, target: String, heard: String): PronounceResult =
    sendJson("POST", "/api/tutor/pronounce", buildJsonObject { put("lang", lang); put("target", target); put("heard", heard) })

// ------------------------------------------------------------------ live meeting
@Serializable
data class LiveLine(val t: Double = 0.0, val text: String = "")

@Serializable
data class LiveResult(@SerialName("session_id") val sessionId: String = "", val title: String = "", val error: String = "",
                      @SerialName("tasks_added") val tasksAdded: Int = 0)

@Serializable
data class LiveState(val id: String = "", val status: String = "", val lines: List<LiveLine> = emptyList(), val total: Int = 0,
                     val behind: Int = 0, val elapsed: Int = 0, val result: LiveResult? = null)

@Serializable
data class LiveStart(val id: String = "")

@Serializable
data class AnswerDto(val answer: String = "")

suspend fun Api.liveStart(lang: String): String = sendJson<LiveStart>("POST", "/api/live/start", buildJsonObject { put("lang", lang) }).id
suspend fun Api.liveState(id: String, after: Int): LiveState = getJson("/api/live/$id?after=$after")
suspend fun Api.liveAsk(id: String, q: String): String = sendJson<AnswerDto>("POST", "/api/live/$id/ask", buildJsonObject { put("question", q) }).answer
suspend fun Api.liveStop(id: String, addTasks: Boolean): JsonObject = sendJson("POST", "/api/live/$id/stop", buildJsonObject { put("add_tasks", addTasks) })
