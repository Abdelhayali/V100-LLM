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
