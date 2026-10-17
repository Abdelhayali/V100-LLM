package com.localai.bridge.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// ------------------------------------------------------------------ OpenAI-compatible API of the loaded model

@Serializable
data class OpenAiInfo(
    val enabled: Boolean = false,
    val key: String = "",
    @SerialName("base_url") val baseUrl: String = "",
    @SerialName("local_url") val localUrl: String = "",
    val tunnel: Boolean = false,
    @SerialName("fixed_url") val fixedUrl: Boolean = false,
    val models: List<String> = emptyList(),
)

suspend fun Api.openAiInfo(): OpenAiInfo = getJson("/api/openai")
suspend fun Api.openAiRegenerate(): OpenAiInfo = sendJson("POST", "/api/openai/regenerate", JsonObject(emptyMap()))
suspend fun Api.openAiDisable(): OpenAiInfo = sendJson("POST", "/api/openai/disable", JsonObject(emptyMap()))
