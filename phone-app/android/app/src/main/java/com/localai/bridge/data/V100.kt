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
    @SerialName("gpu_temp") val gpuTemp: Double? = null,
    @SerialName("gpu_power") val gpuPower: Double? = null,
    @SerialName("gpu_power_limit") val gpuPowerLimit: Double? = null,
    @SerialName("gpu_clock") val gpuClock: Double? = null,
    @SerialName("gpu_clock_max") val gpuClockMax: Double? = null,
    @SerialName("gpu_throttle") val gpuThrottle: List<String> = emptyList(),
    @SerialName("cpu_temp") val cpuTemp: Double? = null,
    @SerialName("cpu_temp_source") val cpuTempSource: String = "",
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
/** New access key for this bridge; the old one stops working at once. */
suspend fun Api.rotateToken(): String =
    sendJson<JsonObject>("POST", "/api/token/rotate", JsonObject(emptyMap()))["token"].toString().trim('"')
suspend fun Api.v100FreeGpu(): JsonObject = sendJson("POST", "/api/v100/free_gpu", JsonObject(emptyMap()))

// ------------------------------------------------------------------ benchmark the loaded model from the phone
@Serializable
data class BenchState(
    val running: Boolean = false,
    val model: String = "",
    @SerialName("model_name") val modelName: String = "",
    @SerialName("preset_name") val presetName: String = "",
    val log: List<String> = emptyList(),
    val scores: Map<String, Double> = emptyMap(),
    val speed: Map<String, Double> = emptyMap(),
    val error: String = "",
    val elapsed: Long = 0,
)

suspend fun Api.benchState(): BenchState = getJson("/api/v100/bench")
suspend fun Api.benchStart(categories: List<String>, speed: Boolean): JsonObject =
    sendJson("POST", "/api/v100/bench", buildJsonObject {
        put("speed", speed)
        put("categories", kotlinx.serialization.json.JsonArray(categories.map { kotlinx.serialization.json.JsonPrimitive(it) }))
    })
suspend fun Api.benchStop(): JsonObject = sendJson("POST", "/api/v100/bench/stop", JsonObject(emptyMap()))

// ------------------------------------------------------------------ model shop (Hugging Face GGUF models)
@Serializable
data class ShopRepo(val repo: String = "", val downloads: Long = 0, val likes: Int = 0, val gated: Boolean = false,
                    val license: String = "", val pipeline: String = "")

@Serializable
data class ShopFile(val name: String = "", val size: Long = 0, val sha256: String = "")

@Serializable
data class ShopChoice(val key: String = "", val quant: String = "", val size: Long = 0, val parts: List<ShopFile> = emptyList(),
                      val fit: String = "", @SerialName("fit_text") val fitText: String = "")

@Serializable
data class ShopFiles(val repo: String = "", val gated: Boolean = false, val license: String = "",
                     val choices: List<ShopChoice> = emptyList(), val mmproj: List<ShopFile> = emptyList())

@Serializable
data class ShopInstalled(val id: String = "", val name: String = "", val repo: String = "", val size: Long = 0,
                         val installed: Boolean = false)

@Serializable
data class ShopProgress(val active: Boolean = false, val item: String = "", val done: Long = 0, val total: Long = 0,
                        val error: String = "", val mid: String = "")

@Serializable
data class ShopStarted(val id: String = "", val name: String = "")

suspend fun Api.shopSearch(q: String): List<ShopRepo> = getJson("/api/v100/shop/search?q=" + java.net.URLEncoder.encode(q, "UTF-8"))
suspend fun Api.shopFiles(repo: String): ShopFiles = getJson("/api/v100/shop/files?repo=" + java.net.URLEncoder.encode(repo, "UTF-8"))
suspend fun Api.shopInstalled(): List<ShopInstalled> = getJson("/api/v100/shop/installed")
suspend fun Api.shopProgress(): ShopProgress = getJson("/api/v100/shop/progress")
suspend fun Api.shopInstall(repo: String, key: String, mmproj: String?): ShopStarted =
    sendJson("POST", "/api/v100/shop/install", buildJsonObject { put("repo", repo); put("key", key); if (mmproj != null) put("mmproj", mmproj) })
suspend fun Api.shopRemove(id: String): JsonObject = sendJson("POST", "/api/v100/shop/remove", buildJsonObject { put("id", id) })
