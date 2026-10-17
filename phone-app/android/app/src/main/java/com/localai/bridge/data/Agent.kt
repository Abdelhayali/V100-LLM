package com.localai.bridge.data

import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

// ------------------------------------------------------------------ BETA: OpenCode coding agent

suspend inline fun <reified T> Api.getJson(path: String): T = json.decodeFromString(rawGet(path))
suspend inline fun <reified T> Api.sendJson(method: String, path: String, body: JsonObject?): T =
    json.decodeFromString(rawSend(method, path, body))

@Serializable
data class AgentStatus(val installed: Boolean = false, val running: Boolean = false, val model: String = "")

@Serializable
data class AgentSessionDto(
    val id: String,
    val directory: String = "",
    val title: String = "",
    val updated: Double = 0.0,
)

@Serializable
data class AgentPart(
    val id: String,
    val kind: String,                 // text | reasoning | tool
    val text: String = "",
    val tool: String = "",
    val status: String = "",          // pending | running | completed | error
    val title: String = "",
    val input: Map<String, String> = emptyMap(),
    val output: String = "",
    val diff: String = "",
    val error: String = "",
)

@Serializable
data class AgentMessageDto(val id: String? = null, val role: String? = null, val parts: List<AgentPart> = emptyList())

@Serializable
data class AgentPermission(
    val id: String,
    val permission: String = "",       // edit | bash | webfetch | ...
    val patterns: List<String> = emptyList(),
    val command: String = "",
    val filepath: String = "",
    val diff: String = "",
)

@Serializable
data class AgentDetail(
    val id: String,
    val directory: String = "",
    val title: String = "",
    val messages: List<AgentMessageDto> = emptyList(),
    val busy: Boolean = false,
    @SerialName("context_used") val contextUsed: Long? = null,
    @SerialName("context_size") val contextSize: Long? = null,
    val permissions: List<AgentPermission> = emptyList(),
)

@Serializable
data class BusyAgent(val id: String, val title: String = "", val directory: String = "")

suspend fun Api.agentStatus(): AgentStatus = getJson("/api/agent/status")
suspend fun Api.agentSessions(): List<AgentSessionDto> = getJson("/api/agent/sessions")
suspend fun Api.agentSession(id: String): AgentDetail = getJson("/api/agent/sessions/$id")
suspend fun Api.createAgentSession(directory: String): AgentSessionDto =
    sendJson("POST", "/api/agent/sessions", buildJsonObject { put("directory", directory) })
suspend fun Api.deleteAgentSession(id: String) { sendJson<JsonObject>("DELETE", "/api/agent/sessions/$id", null) }
suspend fun Api.agentPrompt(id: String, text: String) {
    sendJson<JsonObject>("POST", "/api/agent/sessions/$id/prompt", buildJsonObject { put("text", text) })
}
suspend fun Api.agentAbort(id: String) {
    sendJson<JsonObject>("POST", "/api/agent/sessions/$id/abort", JsonObject(emptyMap()))
}
suspend fun Api.agentReply(permissionId: String, reply: String, directory: String) {
    sendJson<JsonObject>("POST", "/api/agent/permissions/$permissionId",
        buildJsonObject { put("reply", reply); put("directory", directory) })
}
suspend fun Api.mkdir(parent: String, name: String): JsonObject =
    sendJson("POST", "/api/fs/mkdir", buildJsonObject { put("parent", parent); put("name", name) })
suspend fun Api.renamePath(path: String, newName: String): JsonObject =
    sendJson("POST", "/api/fs/rename", buildJsonObject { put("path", path); put("new_name", newName) })

fun Api.agentEvents(id: String, auto: Boolean): Flow<JsonObject> =
    sseGet("/api/agent/sessions/$id/events", mapOf("auto" to auto.toString()))
