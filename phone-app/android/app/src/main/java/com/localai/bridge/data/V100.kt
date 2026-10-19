package com.localai.bridge.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

// ------------------------------------------------------------------ V100-LLM model control (load / unload / status)

@Serializable
data class V100Preset(val id: String, val name: String = "", val bench: String = "")

@Serializable
data class V100Model(
    val id: String,
    val name: String = "",
    val desc: String = "",
    val installed: Boolean = false,
    @SerialName("size_gb") val sizeGb: Double = 0.0,
    val vision: Boolean = false,
    val presets: List<V100Preset> = emptyList(),
)

@Serializable
data class V100Status(
    val launcher: Boolean = false,
    val health: String = "offline",           // offline | stopped | loading | ready | error
    val model: String = "",
    @SerialName("model_name") val modelName: String = "",
    val preset: String = "",
    @SerialName("preset_name") val presetName: String = "",
    val kernel: String = "",
    val port: Int = 0,
    val uptime: Long = 0,
    @SerialName("gpu_name") val gpuName: String = "",
    @SerialName("vram_used_mb") val vramUsedMb: Long = 0,
    @SerialName("vram_total_mb") val vramTotalMb: Long = 0,
    @SerialName("gpu_util") val gpuUtil: Int = 0,
    val cpu: Double = 0.0,
    @SerialName("cpu_threads") val cpuThreads: Int = 0,
    @SerialName("ram_used") val ramUsed: Long = 0,
    @SerialName("ram_total") val ramTotal: Long = 0,
    @SerialName("model_ram") val modelRam: Long = 0,
    val log: List<String> = emptyList(),
)

suspend fun Api.v100Status(): V100Status = getJson("/api/v100/status")
suspend fun Api.v100Models(): List<V100Model> = getJson("/api/v100/models")
suspend fun Api.v100Load(id: String, preset: String): JsonObject =
    sendJson("POST", "/api/v100/load", buildJsonObject { put("id", id); put("preset", preset) })
suspend fun Api.v100Unload(): JsonObject = sendJson("POST", "/api/v100/unload", JsonObject(emptyMap()))
/** Unload the model, stop a running OCR and end leftover V100-LLM / OCR processes that still hold GPU memory. */
suspend fun Api.v100FreeGpu(): JsonObject = sendJson("POST", "/api/v100/free_gpu", JsonObject(emptyMap()))
