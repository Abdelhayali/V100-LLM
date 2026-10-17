package com.localai.bridge.ui

import androidx.compose.material3.Slider
import android.content.Context
import android.content.Intent
import android.webkit.MimeTypeMap
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.automirrored.filled.InsertDriveFile
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Upload
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Switch
import androidx.compose.material3.TextButton
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import com.localai.bridge.data.ExecResult
import com.localai.bridge.data.FsListing
import com.localai.bridge.data.MemoryDto
import kotlinx.coroutines.launch
import java.io.File
import java.text.DateFormat
import java.util.Date

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Bar(title: String, openDrawer: () -> Unit, actions: @Composable () -> Unit = {}) {
    TopAppBar(
        title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
        navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
        actions = { actions() },
    )
}

private fun humanSize(b: Long): String = when {
    b >= 1 shl 30 -> "%.1f GB".format(b / (1 shl 30).toDouble())
    b >= 1 shl 20 -> "%.1f MB".format(b / (1 shl 20).toDouble())
    b >= 1 shl 10 -> "%.0f KB".format(b / 1024.0)
    else -> "$b B"
}

fun openLocal(ctx: Context, f: File) {
    val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.files", f)
    val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(f.extension.lowercase()) ?: "*/*"
    val view = Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    ctx.startActivity(Intent.createChooser(view, f.name))
}

fun shareLocal(ctx: Context, f: File) {
    val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.files", f)
    val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(f.extension.lowercase()) ?: "*/*"
    val send = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri)
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    ctx.startActivity(Intent.createChooser(send, f.name))
}

// ------------------------------------------------------------------ files
@Composable
fun FilesScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var path by rememberSaveable { mutableStateOf<String?>(null) }
    var listing by remember { mutableStateOf<FsListing?>(null) }
    val roots = remember { mutableStateListOf<String>() }
    var loading by remember { mutableStateOf(false) }
    var menuFor by remember { mutableStateOf<String?>(null) }

    fun load() = scope.launch {
        val a = vm.api ?: return@launch
        loading = true
        try {
            if (path == null) { roots.clear(); roots.addAll(a.roots().roots); listing = null }
            else listing = a.list(path!!)
        } catch (e: Exception) { vm.toast = e.message; if (path != null) path = null }
        loading = false
    }
    LaunchedEffect(path) { load() }

    val uploader = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        val dir = path ?: return@rememberLauncherForActivityResult
        scope.launch {
            loading = true
            try {
                uris.forEach { vm.api?.uploadTo(dir, ctx.contentResolver, it) }
                vm.toast = "Uploaded ${uris.size} file(s)"
            } catch (e: Exception) { vm.toast = e.message }
            load()
        }
    }

    fun download(p: String, name: String, then: (File) -> Unit) = scope.launch {
        loading = true
        try {
            val dir = File(ctx.cacheDir, "downloads").apply { mkdirs() }
            then(vm.api!!.download(p, File(dir, name)))
        } catch (e: Exception) { vm.toast = e.message }
        loading = false
    }

    BackHandler(enabled = path != null) {
        val parent = listing?.parent
        path = if (parent != null && roots.any { parent.startsWith(it.trimEnd('\\', '/')) }) parent else null
    }

    Scaffold(
        topBar = { Bar(path ?: "Files on PC", openDrawer) { IconButton(onClick = { load() }) { Icon(Icons.Default.Refresh, "Refresh") } } },
        floatingActionButton = {
            if (path != null) ExtendedFloatingActionButton(onClick = { uploader.launch(arrayOf("*/*")) },
                icon = { Icon(Icons.Default.Upload, null) }, text = { Text("Upload here") })
        },
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            LazyColumn(Modifier.fillMaxSize()) {
                if (path == null) {
                    items(roots) { r ->
                        ListItem(headlineContent = { Text(r) }, leadingContent = { Icon(Icons.Default.Folder, null) },
                            modifier = Modifier.clickable { path = r })
                    }
                    item {
                        Text("Allowed folders are set in server/config.json → allowed_roots.",
                            style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(16.dp))
                    }
                } else {
                    item {
                        ListItem(headlineContent = { Text("..") }, leadingContent = { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) },
                            modifier = Modifier.clickable {
                                val parent = listing?.parent
                                path = if (parent != null && roots.any { parent.startsWith(it.trimEnd('\\', '/')) }) parent else null
                            })
                    }
                    items(listing?.entries.orEmpty(), key = { it.path }) { e ->
                        ListItem(
                            headlineContent = { Text(e.name, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                            supportingContent = {
                                if (!e.isDir) Text("${humanSize(e.size)} · ${DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date((e.modified * 1000).toLong()))}")
                            },
                            leadingContent = { Icon(if (e.isDir) Icons.Default.Folder else Icons.AutoMirrored.Filled.InsertDriveFile, null) },
                            trailingContent = {
                                DropdownMenu(menuFor == e.path, { menuFor = null }) {
                                    DropdownMenuItem(text = { Text("Open") }, onClick = {
                                        menuFor = null
                                        download(e.path, e.name) { f -> runCatching { openLocal(ctx, f) }.onFailure { vm.toast = "No app to open this file" } }
                                    })
                                    DropdownMenuItem(text = { Text("Share / save to phone") }, onClick = {
                                        menuFor = null; download(e.path, e.name) { f -> shareLocal(ctx, f) }
                                    })
                                    DropdownMenuItem(text = { Text("Ask AI about this file") }, onClick = {
                                        menuFor = null
                                        vm.newChat()
                                        vm.draft = "Read the file \"${e.path}\" and summarize it."
                                    })
                                }
                            },
                            modifier = Modifier.clickable { if (e.isDir) path = e.path else menuFor = e.path },
                        )
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------ terminal
private data class RunEntry(val lang: String, val code: String, val result: ExecResult?, val error: String?)

@Composable
fun TerminalScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var lang by rememberSaveable { mutableStateOf("powershell") }
    var code by rememberSaveable { mutableStateOf("") }
    var running by remember { mutableStateOf(false) }
    val history = remember { mutableStateListOf<RunEntry>() }

    Scaffold(topBar = { Bar("Terminal", openDrawer) }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().imePadding().padding(12.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("powershell", "python", "cmd").forEach {
                    FilterChip(selected = lang == it, onClick = { lang = it }, label = { Text(it) })
                }
            }
            OutlinedTextField(code, { code = it }, modifier = Modifier.fillMaxWidth().heightIn(min = 120.dp, max = 220.dp),
                textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                placeholder = { Text(if (lang == "python") "print('hello from my PC')" else "Get-ChildItem") })
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 6.dp)) {
                Button(enabled = code.isNotBlank() && !running, onClick = {
                    val c = code; val l = lang
                    running = true
                    scope.launch {
                        history.add(0, try { RunEntry(l, c, vm.api!!.exec(l, c), null) }
                        catch (e: Exception) { RunEntry(l, c, null, e.message) })
                        running = false
                    }
                }) { Icon(Icons.Default.PlayArrow, null); Text("Run") }
                Spacer(Modifier.size(8.dp))
                if (running) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                Spacer(Modifier.weight(1f))
                Text("cwd: workspace", style = MaterialTheme.typography.labelSmall)
            }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(history) { r ->
                    Card(Modifier.fillMaxWidth().clickable { code = r.code; lang = r.lang }) {
                        Column(Modifier.padding(10.dp)) {
                            Text("${r.lang} › ${r.code.lines().first().take(60)}", style = MaterialTheme.typography.labelMedium,
                                fontFamily = FontFamily.Monospace)
                            HorizontalDivider(Modifier.padding(vertical = 4.dp))
                            val res = r.result
                            val text = r.error ?: buildString {
                                append(res!!.stdout)
                                if (res.stderr.isNotBlank()) append("\n[stderr]\n").append(res.stderr)
                                append("\n[exit ${res.exitCode}${if (res.timedOut) ", timed out" else ""}]")
                            }
                            SelectionContainer {
                                Text(text.trim(), fontFamily = FontFamily.Monospace, fontSize = 12.sp,
                                    color = if (r.error != null || (res?.exitCode ?: 0) != 0) MaterialTheme.colorScheme.error
                                    else MaterialTheme.colorScheme.onSurface,
                                    modifier = Modifier.horizontalScroll(rememberScrollState()))
                            }
                        }
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------ memory
@Composable
fun MemoryScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    val mems = remember { mutableStateListOf<MemoryDto>() }
    var text by remember { mutableStateOf("") }
    fun load() = scope.launch {
        try { val l = vm.api!!.memories(); mems.clear(); mems.addAll(l) } catch (e: Exception) { vm.toast = e.message }
    }
    LaunchedEffect(Unit) { load() }

    Scaffold(topBar = { Bar("Memory", openDrawer) { IconButton(onClick = { load() }) { Icon(Icons.Default.Refresh, "Refresh") } } }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().imePadding().padding(12.dp)) {
            Text("Facts the assistant remembers across all sessions. It adds them itself, or you can add them here.",
                style = MaterialTheme.typography.bodySmall)
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 8.dp)) {
                OutlinedTextField(text, { text = it }, Modifier.weight(1f), placeholder = { Text("e.g. I prefer answers in Arabic") })
                IconButton(enabled = text.isNotBlank(), onClick = {
                    val t = text; text = ""
                    scope.launch { try { vm.api!!.addMemory(t) } catch (e: Exception) { vm.toast = e.message }; load() }
                }) { Icon(Icons.Default.Add, "Add") }
            }
            LazyColumn {
                items(mems, key = { it.id }) { m ->
                    ListItem(headlineContent = { Text(m.content) },
                        trailingContent = {
                            IconButton(onClick = {
                                scope.launch { runCatching { vm.api!!.deleteMemory(m.id) }; mems.remove(m) }
                            }) { Icon(Icons.Default.Delete, "Delete") }
                        })
                }
            }
        }
    }
}

// ------------------------------------------------------------------ settings
@Composable
fun SettingsScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    LaunchedEffect(Unit) { vm.refreshAll() }
    var confirmAuto by remember { mutableStateOf(false) }
    if (confirmAuto) AlertDialog(
        onDismissRequest = { confirmAuto = false },
        title = { Text("Turn on auto-approve?") },
        text = {
            Text("The AI will run code and write files on your PC without asking. A malicious web page, PDF or " +
                "file the AI reads could trick it into running harmful commands. Only use this with content you trust.")
        },
        confirmButton = { TextButton(onClick = { vm.updateAutoApprove(true); confirmAuto = false }) { Text("Turn on") } },
        dismissButton = { TextButton(onClick = { confirmAuto = false }) { Text("Cancel") } },
    )
    val i = vm.info
    Scaffold(topBar = { Bar("Settings", openDrawer) }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Server", style = MaterialTheme.typography.titleMedium)
            Text(vm.prefs.serverUrl, style = MaterialTheme.typography.bodyMedium)
            vm.connectionError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if (i != null) {
                Text("LLM: ${i.llmBaseUrl}  ${if (i.llmOk) "✓ online" else "✗ offline"}")
                Text("Models: ${i.models.joinToString().ifBlank { "none" }}")
                Text("Code execution: ${if (i.codeExec) "enabled" else "disabled"} · approval ${if (i.requireApproval) "required" else "not required"}")
                Text("Allowed folders:\n" + i.allowedRoots.joinToString("\n") { "  • $it" })
                Text("Workspace: ${i.workspace}")
            }
            HorizontalDivider()
            Text("Assistant", style = MaterialTheme.typography.titleMedium)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Web search")
                    Text("Let the AI search the internet and read web pages (also the 🌐 button in chat).",
                        style = MaterialTheme.typography.bodySmall)
                }
                Switch(checked = vm.webSearch, onCheckedChange = { vm.toggleWebSearch() })
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Auto-approve everything", color = if (vm.autoApprove) MaterialTheme.colorScheme.error
                        else MaterialTheme.colorScheme.onSurface)
                    Text("Run code and write files on the PC without asking you.",
                        style = MaterialTheme.typography.bodySmall)
                }
                Switch(checked = vm.autoApprove, onCheckedChange = { on ->
                    if (on) confirmAuto = true else vm.updateAutoApprove(false)
                })
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Auto-compress long chats")
                    Text("When the context fills up, older messages are summarized so the chat can go on. " +
                        "You still see the full history.", style = MaterialTheme.typography.bodySmall)
                }
                Switch(checked = vm.autoCompress, onCheckedChange = { vm.updateAutoCompress(it) })
            }
            if (vm.autoCompress) {
                var pct by remember { mutableStateOf(vm.compressAt.toFloat()) }
                Text("Compress at ${pct.toInt()}% of the context", style = MaterialTheme.typography.bodyMedium)
                Slider(value = pct, onValueChange = { pct = it }, valueRange = 50f..95f, steps = 8,
                    onValueChangeFinished = { vm.updateCompressAt(pct.toInt()) })
                Text("You can also compress any chat by hand: 📎 → Compress conversation now.",
                    style = MaterialTheme.typography.bodySmall)
            }
            HorizontalDivider()
            Text("Appearance", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("system" to "System", "light" to "Light", "dark" to "Dark").forEach { (k, label) ->
                    FilterChip(selected = vm.themeMode == k, onClick = { vm.setTheme(k) }, label = { Text(label) })
                }
            }
            HorizontalDivider()
            Text("Quick tunnel URLs change every time the server restarts. Re-scan the QR after a restart, " +
                "or configure a named Cloudflare tunnel for a fixed address.", style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = { vm.unpair() }, modifier = Modifier.fillMaxWidth()) { Text("Disconnect / re-pair") }
        }
    }
}
