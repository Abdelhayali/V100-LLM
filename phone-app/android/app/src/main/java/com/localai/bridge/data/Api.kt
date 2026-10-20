package com.localai.bridge.data

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.add
import okhttp3.Call
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.Response
import okio.BufferedSink
import okio.source
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

class ApiException(val code: Int, message: String) : IOException(message)

class Api(private val baseUrl: String, private val token: String) {
    companion object {
        /** The private vault's key while it is unlocked (base64); sent with every request, never stored on the PC. */
        @Volatile var vaultKey: String? = null
    }

    val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true }

    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)     // server sends keep-alive pings every 15 s while streaming
        .writeTimeout(5, TimeUnit.MINUTES)
        .build()

    private val jsonType = "application/json".toMediaType()

    private fun url(path: String, query: Map<String, String> = emptyMap()) =
        (baseUrl.trimEnd('/') + path).toHttpUrl().newBuilder().apply {
            query.forEach { (k, v) -> addQueryParameter(k, v) }
        }.build()

    private fun req(path: String, query: Map<String, String> = emptyMap()) =
        Request.Builder().url(url(path, query)).header("Authorization", "Bearer $token")
            .apply { vaultKey?.let { header("X-Vault-Key", it) } }

    private suspend fun exec(r: Request): String = withContext(Dispatchers.IO) {
        client.newCall(r).execute().use { resp -> checked(resp).body!!.string() }
    }

    private fun checked(resp: Response): Response {
        if (!resp.isSuccessful) {
            val body = resp.body?.string().orEmpty()
            val detail = runCatching { json.parseToJsonElement(body).jsonObject["detail"].toString().trim('"') }
                .getOrNull() ?: body.take(300)
            throw ApiException(resp.code, when (resp.code) {
                401 -> "Invalid token - re-pair with the server"
                429 -> "Too many failed attempts - wait 10 minutes"
                530, 502, 1033 -> "Server/tunnel offline (HTTP ${resp.code})"
                else -> "HTTP ${resp.code}: $detail"
            })
        }
        return resp
    }

    private suspend inline fun <reified T> get(path: String, query: Map<String, String> = emptyMap()): T =
        json.decodeFromString(exec(req(path, query).get().build()))

    private suspend inline fun <reified T> send(method: String, path: String, body: JsonObject): T =
        json.decodeFromString(exec(req(path).method(method, body.toString().toRequestBody(jsonType)).build()))

    // ---- basic
    suspend fun info(): ServerInfo = get("/api/info")
    suspend fun sessions(): List<SessionDto> = get("/api/sessions")
    suspend fun createSession(model: String = ""): SessionDto =
        send("POST", "/api/sessions", buildJsonObject { put("model", model) })
    suspend fun session(id: String): SessionDetail = get("/api/sessions/$id")
    suspend fun renameSession(id: String, title: String): SessionDto =
        send("PATCH", "/api/sessions/$id", buildJsonObject { put("title", title) })
    suspend fun setSessionModel(id: String, model: String): SessionDto =
        send("PATCH", "/api/sessions/$id", buildJsonObject { put("model", model) })
    suspend fun deleteSession(id: String) { exec(req("/api/sessions/$id").delete().build()) }
    suspend fun deletePath(path: String) { exec(req(path).delete().build()) }
    suspend fun truncate(id: String, messageId: Long) {
        send<JsonObject>("POST", "/api/sessions/$id/truncate", buildJsonObject { put("message_id", messageId) })
    }
    suspend fun screenshot(): AttachmentRef = send("POST", "/api/screenshot", JsonObject(emptyMap()))
    suspend fun stop(id: String) { send<JsonObject>("POST", "/api/sessions/$id/stop", JsonObject(emptyMap())) }
    suspend fun approve(callId: String, ok: Boolean) {
        send<JsonObject>("POST", "/api/approvals/$callId", buildJsonObject { put("approve", ok) })
    }

    suspend fun answerQuestion(callId: String, answer: String) {
        send<JsonObject>("POST", "/api/questions/$callId", buildJsonObject { put("answer", answer) })
    }

    // ---- raw helpers (used by feature extensions such as the beta agent API)
    suspend fun rawGet(path: String, query: Map<String, String> = emptyMap()): String = exec(req(path, query).get().build())
    suspend fun rawSend(method: String, path: String, body: JsonObject?): String =
        exec(req(path).method(method, body?.toString()?.toRequestBody(jsonType)).build())
    fun sseGet(path: String, query: Map<String, String> = emptyMap()): Flow<JsonObject> = sse(req(path, query).get().build())

    // ---- streaming chat (Server-Sent Events)
    fun chat(
        sessionId: String, content: String, attachments: List<String>, model: String?,
        web: Boolean = false, autoApprove: Boolean = false, compressAt: Double = 0.0,
        email: Boolean = false, organizer: Boolean = false, thinking: String = "auto", ocr: String = "off", sandbox: Boolean = false, voice: Boolean = false, translate: Boolean = false, pc: Boolean = false, drive: Boolean = false,
    ): Flow<JsonObject> {
        val body = buildJsonObject {
            put("content", content)
            put("compress_at", compressAt)
            put("web", web)
            put("auto_approve", autoApprove)
            put("email", email)
            put("organizer", organizer)
            put("thinking", thinking)
            put("ocr", ocr)
            put("sandbox", sandbox)
            put("voice", voice)
            put("translate", translate)
            put("pc", pc)
            put("drive", drive)
            putJsonArray("attachments") { attachments.forEach { add(it) } }
            if (!model.isNullOrBlank()) put("model", model)
        }
        return sse(req("/api/sessions/$sessionId/chat").post(body.toString().toRequestBody(jsonType)).build())
    }

    /** Summarize the older part of the conversation (runs on the PC, progress streamed like a reply). */
    fun compress(sessionId: String): Flow<JsonObject> =
        sse(req("/api/sessions/$sessionId/compress").post("{}".toRequestBody(jsonType)).build())

    fun resume(sessionId: String): Flow<JsonObject> = sse(req("/api/sessions/$sessionId/stream").get().build())

    private fun sse(request: Request): Flow<JsonObject> = flow {
        val call: Call = client.newCall(request)
        try {
            call.execute().use { resp ->
                checked(resp)
                val src = resp.body!!.source()
                while (true) {
                    currentCoroutineContext().ensureActive()
                    val line = src.readUtf8Line() ?: break
                    if (line.startsWith("data:")) {
                        emit(json.parseToJsonElement(line.substring(5).trim()).jsonObject)
                    }
                }
            }
        } finally {
            call.cancel()
        }
    }.flowOn(Dispatchers.IO)

    // ---- uploads
    private fun uriBody(cr: ContentResolver, uri: Uri, mime: String): RequestBody = object : RequestBody() {
        override fun contentType() = mime.toMediaType()
        override fun writeTo(sink: BufferedSink) {
            cr.openInputStream(uri)!!.source().use { sink.writeAll(it) }
        }
    }

    fun displayName(cr: ContentResolver, uri: Uri): String =
        cr.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) c.getString(0) else null
        } ?: uri.lastPathSegment ?: "file"

    private fun multipart(cr: ContentResolver, uri: Uri, nameOverride: String? = null): MultipartBody {
        val mime = cr.getType(uri) ?: "application/octet-stream"
        val name = nameOverride ?: displayName(cr, uri)
        return MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", name, uriBody(cr, uri, mime)).build()
    }

    suspend fun upload(cr: ContentResolver, uri: Uri, nameOverride: String? = null): AttachmentRef =
        json.decodeFromString(exec(req("/api/uploads").post(multipart(cr, uri, nameOverride)).build()))

    /** Voice note: the recording is transcribed and summarized on the PC (cpu = chat model stays loaded, gpu = faster). */
    suspend fun uploadVoice(file: File, device: String, addTasks: Boolean): String {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", file.name, file.asRequestBody("audio/mp4".toMediaType()))
            .addFormDataPart("device", device).addFormDataPart("add_tasks", addTasks.toString()).build()
        return exec(req("/api/notes/voice").post(body).build())
    }

    /** One 20-second piece of a live meeting (blocking: called from the recorder's thread). */
    fun uploadLiveChunkBlocking(id: String, wav: File, idx: Int, offsetSec: Double): Boolean {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", wav.name, wav.asRequestBody("audio/wav".toMediaType()))
            .addFormDataPart("idx", idx.toString()).addFormDataPart("offset", offsetSec.toString()).build()
        return client.newCall(req("/api/live/$id/chunk").post(body).build()).execute().use { it.isSuccessful }
    }

    /** WAV audio of [text] spoken by a PC voice (Piper on the PC). Blocking call: use from a background thread. */
    fun ttsAudioBlocking(text: String, voice: String): ByteArray? {
        val body = buildJsonObject { put("text", text); put("voice", voice) }.toString().toRequestBody(jsonType)
        return client.newCall(req("/api/tts").post(body).build()).execute().use { r -> if (r.isSuccessful) r.body?.bytes() else null }
    }

    // ---- filesystem
    suspend fun roots(): FsRoots = get("/api/fs/roots")
    suspend fun list(path: String): FsListing = get("/api/fs/list", mapOf("path" to path))
    suspend fun uploadTo(dir: String, cr: ContentResolver, uri: Uri) {
        exec(req("/api/fs/upload", mapOf("dir" to dir)).post(multipart(cr, uri)).build())
    }

    suspend fun download(path: String, dest: File) = withContext(Dispatchers.IO) {
        client.newCall(req("/api/fs/download", mapOf("path" to path)).get().build()).execute().use { resp ->
            checked(resp)
            dest.outputStream().use { out -> resp.body!!.byteStream().copyTo(out) }
        }
        dest
    }

    suspend fun downloadAttachment(id: String, dest: File) = withContext(Dispatchers.IO) {
        client.newCall(req("/api/uploads/$id").get().build()).execute().use { resp ->
            checked(resp)
            dest.outputStream().use { out -> resp.body!!.byteStream().copyTo(out) }
        }
        dest
    }

    // ---- running tasks
    suspend fun tasks(): TasksDto = get("/api/tasks")
    suspend fun stopTask(sessionId: String) { send<JsonObject>("POST", "/api/tasks/$sessionId/stop", JsonObject(emptyMap())) }
    suspend fun killProcess(pid: Long) { send<JsonObject>("POST", "/api/processes/$pid/kill", JsonObject(emptyMap())) }
    suspend fun abortLlm(): JsonObject = send("POST", "/api/llm/abort", JsonObject(emptyMap()))
    suspend fun killAll(): JsonObject = send("POST", "/api/tasks/kill_all", JsonObject(emptyMap()))

    // ---- exec & memory
    suspend fun exec(language: String, code: String): ExecResult =
        send("POST", "/api/exec", buildJsonObject { put("language", language); put("code", code) })

    suspend fun memories(): List<MemoryDto> = get("/api/memory")
    suspend fun addMemory(text: String) { send<JsonObject>("POST", "/api/memory", buildJsonObject { put("content", text) }) }
    suspend fun deleteMemory(id: Long) { exec(req("/api/memory/$id").delete().build()) }
}
