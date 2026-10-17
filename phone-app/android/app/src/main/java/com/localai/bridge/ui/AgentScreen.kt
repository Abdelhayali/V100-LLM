package com.localai.bridge.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.localai.bridge.data.AgentPart
import com.localai.bridge.data.AgentPermission
import com.localai.bridge.data.FsEntry
import com.localai.bridge.data.mkdir
import com.localai.bridge.data.renamePath
import androidx.compose.material.icons.filled.CreateNewFolder
import androidx.compose.material3.Switch
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** BETA: OpenCode coding agent working on a project folder of the PC. */
@Composable
fun AgentScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val avm: AgentViewModel = viewModel()
    avm.api = vm.api
    if (!avm.autoInitialized) { avm.autoApprove = vm.autoApprove; avm.autoInitialized = true }
    LaunchedEffect(Unit) { avm.refreshList() }
    avm.toast?.let { vm.toast = it; avm.toast = null }
    if (avm.current == null) AgentList(vm, avm, openDrawer) else AgentSessionView(avm)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AgentList(vm: MainViewModel, avm: AgentViewModel, openDrawer: () -> Unit) {
    var picking by remember { mutableStateOf(false) }
    Scaffold(topBar = {
        TopAppBar(title = { Text("Code agent (beta)") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { avm.refreshList() }) { Icon(Icons.Default.Refresh, "Refresh") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("OpenCode works on a folder of your PC using your local model: it reads code, edits files and runs " +
                "commands. Every edit and command asks for your approval (unless Auto-approve is on).",
                style = MaterialTheme.typography.bodySmall)
            if (avm.installed == false) Text("OpenCode is not installed on the PC (npm install -g opencode-ai).",
                color = MaterialTheme.colorScheme.error)
            avm.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(onClick = { picking = true }, enabled = !avm.loading, modifier = Modifier.fillMaxWidth()) {
                if (avm.loading) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                else { Icon(Icons.Default.Add, null); Spacer(Modifier.size(6.dp)); Text("New agent session - pick a project folder") }
            }
            Text("Sessions", style = MaterialTheme.typography.titleMedium)
            LazyColumn(Modifier.weight(1f)) {
                items(avm.sessions, key = { it.id }) { s ->
                    ListItem(
                        headlineContent = { Text(s.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        supportingContent = { Text(s.directory, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        leadingContent = { Icon(Icons.Default.Code, null) },
                        trailingContent = { IconButton(onClick = { avm.delete(s.id) }) { Icon(Icons.Default.Delete, "Delete") } },
                        modifier = Modifier.clickable { avm.open(s.id) })
                }
            }
        }
    }
    if (picking) FolderPicker(vm, onPick = { picking = false; avm.create(it) }, onDismiss = { picking = false })
}

/** Browse the PC's allowed folders and choose one. */
@Composable
private fun FolderPicker(vm: MainViewModel, onPick: (String) -> Unit, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var path by remember { mutableStateOf<String?>(null) }
    val entries = remember { mutableStateListOf<FsEntry>() }
    val roots = remember { mutableStateListOf<String>() }
    var parent by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableStateOf(0) }
    var nameDialog by remember { mutableStateOf<Pair<String, FsEntry?>?>(null) }  // (initial text, entry to rename or null = new)
    LaunchedEffect(path, reload) {
        val a = vm.api ?: return@LaunchedEffect
        try {
            if (path == null) { roots.clear(); roots.addAll(a.roots().roots); entries.clear() }
            else { val l = a.list(path!!); parent = l.parent; entries.clear(); entries.addAll(l.entries.filter { it.isDir }) }
        } catch (e: Exception) { vm.toast = e.message; path = null }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(path ?: "Choose a project folder", maxLines = 2, overflow = TextOverflow.Ellipsis) },
        text = {
            LazyColumn(Modifier.heightIn(max = 420.dp)) {
                if (path == null) items(roots) { r ->
                    ListItem(headlineContent = { Text(r) }, leadingContent = { Icon(Icons.Default.Folder, null) },
                        modifier = Modifier.clickable { path = r })
                } else {
                    item {
                        ListItem(headlineContent = { Text("..") },
                            leadingContent = { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) },
                            modifier = Modifier.clickable {
                                path = parent?.takeIf { p -> roots.any { p.startsWith(it.trimEnd('\\', '/')) } }
                            })
                    }
                    item {
                        ListItem(headlineContent = { Text("New folder…", color = MaterialTheme.colorScheme.primary) },
                            leadingContent = { Icon(Icons.Default.CreateNewFolder, null, tint = MaterialTheme.colorScheme.primary) },
                            modifier = Modifier.clickable { nameDialog = "" to null })
                    }
                    items(entries, key = { it.path }) { e ->
                        ListItem(headlineContent = { Text(e.name) }, leadingContent = { Icon(Icons.Default.Folder, null) },
                            trailingContent = {
                                IconButton(onClick = { nameDialog = e.name to e }) { Icon(Icons.Default.Edit, "Rename") }
                            },
                            modifier = Modifier.clickable { path = e.path })
                    }
                }
            }
        },
        confirmButton = { TextButton(enabled = path != null, onClick = { path?.let(onPick) }) { Text("Use this folder") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
    nameDialog?.let { (initial, entry) ->
        var name by remember(entry, initial) { mutableStateOf(initial) }
        AlertDialog(
            onDismissRequest = { nameDialog = null },
            title = { Text(if (entry == null) "New folder" else "Rename folder") },
            text = { OutlinedTextField(name, { name = it }, singleLine = true, label = { Text("Name") }) },
            confirmButton = {
                TextButton(enabled = name.isNotBlank(), onClick = {
                    val a = vm.api
                    val dir = path
                    nameDialog = null
                    scope.launch {
                        try {
                            if (entry == null && a != null && dir != null) {
                                a.mkdir(dir, name.trim()); vm.toast = "Folder created"
                            } else if (entry != null && a != null) {
                                a.renamePath(entry.path, name.trim()); vm.toast = "Renamed"
                            }
                        } catch (e: Exception) { vm.toast = e.message }
                        reload++
                    }
                }) { Text(if (entry == null) "Create" else "Rename") }
            },
            dismissButton = { TextButton(onClick = { nameDialog = null }) { Text("Cancel") } },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AgentSessionView(avm: AgentViewModel) {
    val d = avm.current!!
    var draft by remember { mutableStateOf("") }
    var confirmAuto by remember { mutableStateOf(false) }
    val list = rememberLazyListState()
    BackHandler { avm.close() }
    val lastLen = avm.messages.lastOrNull()?.parts?.sumOf { it.text.length + it.status.length } ?: 0
    LaunchedEffect(avm.messages.size, lastLen) { if (avm.messages.isNotEmpty()) list.scrollToItem(avm.messages.lastIndex, Int.MAX_VALUE / 2) }

    Scaffold(topBar = {
        TopAppBar(
            navigationIcon = { IconButton(onClick = { avm.close() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            actions = {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(end = 8.dp)) {
                    Switch(checked = avm.autoApprove, onCheckedChange = { on ->
                        if (on) confirmAuto = true else avm.updateAutoApprove(false)
                    })
                    Text("Auto-approve", style = MaterialTheme.typography.labelSmall,
                        color = if (avm.autoApprove) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            },
            title = {
                Column {
                    Text(d.title, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    val ctx = avm.contextUsed?.let { u -> d.contextSize?.let { "Context ${u / 1000}k / ${it / 1000}k · " } ?: "Context ${u / 1000}k · " } ?: ""
                    Text(ctx + d.directory, style = MaterialTheme.typography.labelSmall, maxLines = 1,
                        overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            },
        )
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().imePadding()) {
            if (!avm.connected) LinearProgressIndicator(Modifier.fillMaxWidth())
            Box(Modifier.weight(1f)) {
                if (avm.messages.isEmpty()) Text(
                    "Describe a coding task for this folder, e.g. \"add input validation to app.py and run the tests\".",
                    modifier = Modifier.padding(24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                LazyColumn(state = list, contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxSize()) {
                    items(avm.messages, key = { it.id }) { m ->
                        if (m.role == "user") {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                                Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(14.dp),
                                    modifier = Modifier.widthIn(max = 320.dp)) {
                                    Text(m.parts.filter { it.kind == "text" }.joinToString("\n") { it.text }, Modifier.padding(12.dp))
                                }
                            }
                        } else Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            m.parts.forEach { p -> AgentPartView(p) }
                        }
                    }
                }
            }
            if (avm.busy) AgentStatusBar(avm)
            Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(8.dp), verticalAlignment = Alignment.Bottom) {
                OutlinedTextField(draft, { draft = it }, placeholder = { Text("Task for the agent…") },
                    modifier = Modifier.weight(1f).heightIn(max = 160.dp), shape = RoundedCornerShape(24.dp))
                Spacer(Modifier.size(6.dp))
                if (avm.busy) FilledIconButton(onClick = { avm.abort() }) { Icon(Icons.Default.Stop, "Stop") }
                else FilledIconButton(enabled = draft.isNotBlank(), onClick = { avm.send(draft.trim()); draft = "" }) {
                    Icon(Icons.AutoMirrored.Filled.Send, "Send")
                }
            }
        }
    }
    avm.permissions.firstOrNull()?.let { PermissionDialog(avm, it) }
    if (confirmAuto) AlertDialog(
        onDismissRequest = { confirmAuto = false },
        title = { Text("Auto-approve this agent?") },
        text = { Text("The agent will edit files and run commands in ${d.directory} without asking you. " +
            "Only use this for projects you have a backup of (e.g. in git).") },
        confirmButton = { TextButton(onClick = { confirmAuto = false; avm.updateAutoApprove(true) }) { Text("Turn on") } },
        dismissButton = { TextButton(onClick = { confirmAuto = false }) { Text("Cancel") } },
    )
}

@Composable
private fun AgentStatusBar(avm: AgentViewModel) {
    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) { while (true) { now = System.currentTimeMillis(); delay(500) } }
    val sec = ((now - avm.busySinceMs) / 1000).coerceAtLeast(0)
    val running = avm.messages.lastOrNull()?.parts?.lastOrNull { it.kind == "tool" && it.status == "running" }
    val label = when {
        avm.permissions.isNotEmpty() -> "Waiting for your approval"
        running != null -> "Running ${running.tool}" + (running.title.takeIf { it.isNotBlank() }?.let { ": $it" } ?: "")
        else -> "Agent is working…"
    }
    Surface(color = MaterialTheme.colorScheme.surfaceContainerHigh, modifier = Modifier.fillMaxWidth()) {
        Column {
            LinearProgressIndicator(Modifier.fillMaxWidth().height(2.dp))
            Row(Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
                Text(label, style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f),
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text("%d:%02d".format(sec / 60, sec % 60), style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

private fun toolIcon(tool: String) = when (tool) {
    "edit", "write", "patch", "multiedit" -> Icons.Default.Edit
    "bash" -> Icons.Default.Terminal
    "read", "list" -> Icons.Default.Visibility
    "grep", "glob", "codesearch" -> Icons.Default.Search
    "webfetch", "websearch" -> Icons.Default.Public
    else -> Icons.Default.Code
}

@Composable
private fun AgentPartView(p: AgentPart) {
    when (p.kind) {
        "text" -> if (p.text.isNotBlank()) MarkdownText(p.text.trim())
        "reasoning" -> if (p.text.isNotBlank()) {
            var open by remember { mutableStateOf(false) }
            Column {
                AssistChip(onClick = { open = !open }, label = { Text(if (open) "Hide thinking" else "Thinking") },
                    leadingIcon = { Icon(Icons.Default.Psychology, null, Modifier.size(16.dp)) })
                if (open) Text(p.text.trim(), style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        "tool" -> {
            var open by remember { mutableStateOf(false) }
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh),
                modifier = Modifier.fillMaxWidth().clickable { open = !open }.animateContentSize()) {
                Column(Modifier.padding(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(toolIcon(p.tool), null, Modifier.size(16.dp))
                        val what = p.title.ifBlank { p.input["filePath"] ?: p.input["command"] ?: p.input["pattern"] ?: "" }
                        Text(" ${p.tool} ${what.substringAfterLast('\\')}", style = MaterialTheme.typography.labelLarge,
                            maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                        when (p.status) {
                            "running", "pending" -> CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp)
                            "error" -> Text("failed", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelSmall)
                            else -> Text(if (open) "hide" else "details", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                    if (p.diff.isNotBlank() && !open) DiffView(p.diff, maxLines = 12)
                    if (open) {
                        p.input["command"]?.let { CodeBlock(it, "command") }
                        if (p.diff.isNotBlank()) DiffView(p.diff)
                        if (p.output.isNotBlank()) CodeBlock(p.output.take(6000), "output")
                        if (p.error.isNotBlank()) Text(p.error, color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

/** Unified diff with added lines green and removed lines red. */
@Composable
private fun DiffView(diff: String, maxLines: Int = Int.MAX_VALUE) {
    val lines = diff.lines().filterNot { it.startsWith("Index:") || it.startsWith("====") }
    Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(6.dp),
        modifier = Modifier.fillMaxWidth().padding(top = 6.dp)) {
        Column(Modifier.padding(8.dp)) {
            lines.take(maxLines).forEach { l ->
                val color = when {
                    l.startsWith("+") && !l.startsWith("+++") -> androidx.compose.ui.graphics.Color(0xFF2E7D32)
                    l.startsWith("-") && !l.startsWith("---") -> MaterialTheme.colorScheme.error
                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                }
                Text(l, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = color, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
            }
            if (lines.size > maxLines) Text("… ${lines.size - maxLines} more lines (tap for all)",
                style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun PermissionDialog(avm: AgentViewModel, p: AgentPermission) {
    val title = when (p.permission) {
        "edit" -> "Allow this file edit?"
        "bash" -> "Allow this command?"
        "webfetch" -> "Allow fetching this web page?"
        else -> "Allow ${p.permission}?"
    }
    AlertDialog(
        onDismissRequest = {},
        title = { Text(title) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                val target = p.command.ifBlank { p.filepath.ifBlank { p.patterns.joinToString() } }
                Text(target, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
                if (p.diff.isNotBlank()) DiffView(p.diff)
            }
        },
        confirmButton = {
            Row {
                TextButton(onClick = { avm.reply(p, "always") }) { Text("Always") }
                TextButton(onClick = { avm.reply(p, "once") }) { Text("Allow") }
            }
        },
        dismissButton = { TextButton(onClick = { avm.reply(p, "reject") }) { Text("Reject") } },
    )
}
