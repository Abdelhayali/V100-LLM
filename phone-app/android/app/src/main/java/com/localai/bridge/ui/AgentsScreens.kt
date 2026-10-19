package com.localai.bridge.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.localai.bridge.RecordService
import com.localai.bridge.data.ProjectDto
import com.localai.bridge.data.ResearchRun
import com.localai.bridge.data.VoiceJob
import com.localai.bridge.data.projectDelete
import com.localai.bridge.data.projectNewChat
import com.localai.bridge.data.projectSave
import com.localai.bridge.data.projectSchedule
import com.localai.bridge.data.projects
import com.localai.bridge.data.research
import com.localai.bridge.data.researchStart
import com.localai.bridge.data.voiceJobs
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Screen(title: String, openDrawer: () -> Unit, actions: @Composable () -> Unit = {}, body: @Composable () -> Unit) {
    Scaffold(topBar = {
        TopAppBar(title = { Text(title) }, navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { actions() })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) { body() }
    }
}

@Composable
private fun Hint(text: String) = Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

// ------------------------------------------------------------------ deep research
@Composable
fun ResearchScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var q by remember { mutableStateOf("") }
    var depth by remember { mutableStateOf("normal") }
    var runs by remember { mutableStateOf<List<ResearchRun>>(emptyList()) }
    LaunchedEffect(Unit) {
        while (true) {
            runCatching { vm.api?.research() }.getOrNull()?.let { runs = it }
            delay(if (runs.any { it.status == "running" }) 4_000 else 20_000)
        }
    }
    Screen("Deep research", openDrawer) {
        Hint("The PC searches the web, reads the pages, cross-checks them and writes a report with numbered sources. " +
            "It runs in the background: you get a notification when it is ready.")
        OutlinedTextField(q, { q = it }, label = { Text("What should be researched?") }, modifier = Modifier.fillMaxWidth(), minLines = 3)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("quick" to "Quick (~3 min)", "normal" to "Normal (~8 min)", "deep" to "Deep (~20 min)").forEach { (k, l) ->
                FilterChip(selected = depth == k, onClick = { depth = k }, label = { Text(l) })
            }
        }
        Button(enabled = q.isNotBlank() && runs.none { it.status == "running" }, onClick = {
            scope.launch {
                runCatching { vm.api?.researchStart(q.trim(), depth) }
                    .onSuccess { vm.toast = "Research started - you'll get a notification"; q = ""; runs = vm.api?.research().orEmpty() }
                    .onFailure { vm.toast = it.message }
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("Start research") }
        runs.forEach { r ->
            Card(Modifier.fillMaxWidth().clickable(enabled = r.status != "running") { vm.screen = Screen.CHAT; vm.openSession(r.sessionId) },
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(r.question, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    when (r.status) {
                        "running" -> { LinearProgressIndicator(Modifier.fillMaxWidth()); Text(r.progress, style = MaterialTheme.typography.bodySmall) }
                        "done" -> Text("✓ Report ready · ${r.sources} sources · tap to read", style = MaterialTheme.typography.bodySmall)
                        else -> Text("✗ ${r.error}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------ meeting / voice notes
@Composable
fun NotesScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var recording by remember { mutableStateOf(RecordService.recording) }
    var elapsed by remember { mutableLongStateOf(0L) }
    var gpu by remember { mutableStateOf(false) }
    var addTasks by remember { mutableStateOf(true) }
    var uploading by remember { mutableStateOf(false) }
    var jobs by remember { mutableStateOf<List<VoiceJob>>(emptyList()) }
    val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) { RecordService.start(ctx); recording = true } else vm.toast = "Recording needs the microphone permission"
    }
    LaunchedEffect(Unit) {
        while (true) {
            recording = RecordService.recording
            elapsed = if (recording) (System.currentTimeMillis() - RecordService.startedAt) / 1000 else 0
            if ((System.currentTimeMillis() / 1000) % 5 == 0L || jobs.any { it.status == "running" })
                runCatching { vm.api?.voiceJobs() }.getOrNull()?.let { jobs = it }
            delay(1_000)
        }
    }
    Screen("Voice notes", openDrawer) {
        Hint("Record a meeting, lecture or idea. Your PC writes the transcript (Arabic or English), a summary, decisions and " +
            "action items. Keeps recording with the screen off.")
        Text(if (recording) "● Recording  %d:%02d".format(elapsed / 60, elapsed % 60) else "Ready",
            style = MaterialTheme.typography.headlineMedium,
            color = if (recording) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
        if (!recording) Button(onClick = {
            if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                RecordService.start(ctx); recording = true
            } else mic.launch(Manifest.permission.RECORD_AUDIO)
        }, modifier = Modifier.fillMaxWidth().height(72.dp)) { Text("🎙 Start recording", style = MaterialTheme.typography.titleMedium) }
        else Button(onClick = {
            val f = RecordService.stop(ctx); recording = false
            if (f != null && f.length() > 2000) {
                uploading = true
                scope.launch {
                    runCatching { vm.api?.uploadVoice(f, if (gpu) "gpu" else "cpu", addTasks) }
                        .onSuccess { vm.toast = "Uploaded - the notes will be ready soon"; f.delete() }
                        .onFailure { vm.toast = "Upload failed (kept on the phone): ${it.message}" }
                    uploading = false
                    jobs = runCatching { vm.api?.voiceJobs() }.getOrNull().orEmpty()
                }
            } else vm.toast = "The recording was too short"
        }, modifier = Modifier.fillMaxWidth().height(72.dp),
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
            Text("■ Stop and make notes", style = MaterialTheme.typography.titleMedium) }
        if (uploading) LinearProgressIndicator(Modifier.fillMaxWidth())
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Transcribe on the GPU (faster)")
                Hint("Off: on the CPU, the chat model stays loaded (≈ the length of the recording). On: the chat model is unloaded for a moment.")
            }
            Switch(checked = gpu, onCheckedChange = { gpu = it })
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Add action items to my tasks", Modifier.weight(1f))
            Switch(checked = addTasks, onCheckedChange = { addTasks = it })
        }
        jobs.forEach { j ->
            Card(Modifier.fillMaxWidth().clickable(enabled = j.status == "done") { vm.screen = Screen.CHAT; vm.openSession(j.sessionId) },
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(j.title.ifBlank { "Voice note" }, fontWeight = FontWeight.SemiBold)
                    when (j.status) {
                        "running" -> { LinearProgressIndicator(Modifier.fillMaxWidth()); Text(j.progress, style = MaterialTheme.typography.bodySmall) }
                        "done" -> Text("✓ Notes ready" + (if (j.tasksAdded > 0) " · ${j.tasksAdded} tasks added" else "") + " · tap to open",
                            style = MaterialTheme.typography.bodySmall)
                        else -> Text("✗ ${j.error}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------ long-term projects
@Composable
fun ProjectsScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<List<ProjectDto>?>(null) }
    var openId by remember { mutableStateOf<Int?>(null) }
    var editing by remember { mutableStateOf<ProjectDto?>(null) }
    var scheduling by remember { mutableStateOf<ProjectDto?>(null) }
    fun reload() = scope.launch { runCatching { vm.api?.projects() }.onSuccess { list = it }.onFailure { vm.toast = it.message } }
    LaunchedEffect(Unit) { reload() }

    editing?.let { p ->
        var name by remember(p.id) { mutableStateOf(p.name) }
        var goal by remember(p.id) { mutableStateOf(p.goal) }
        var notes by remember(p.id) { mutableStateOf(p.notes) }
        AlertDialog(onDismissRequest = { editing = null },
            title = { Text(if (p.id == 0) "New project" else "Edit project") },
            text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true)
                OutlinedTextField(goal, { goal = it }, label = { Text("Goal: what should be achieved?") }, minLines = 3)
                OutlinedTextField(notes, { notes = it }, label = { Text("Notes (the AI adds progress here)") }, minLines = 4)
            } },
            confirmButton = { TextButton(enabled = name.isNotBlank(), onClick = {
                editing = null
                scope.launch { runCatching { vm.api?.projectSave(p.copy(name = name, goal = goal, notes = notes)) }
                    .onSuccess { reload() }.onFailure { vm.toast = it.message } }
            }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { editing = null }) { Text("Cancel") } })
    }
    scheduling?.let { p ->
        var at by remember(p.id) { mutableStateOf("21:00") }
        var prompt by remember(p.id) { mutableStateOf("Continue working on this project: read the goal and the notes, " +
            "do the next useful step, save results in the project folder, and record progress and the next steps with project_note.") }
        AlertDialog(onDismissRequest = { scheduling = null },
            title = { Text("Work on \"${p.name}\" every day") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(at, { at = it.take(5) }, label = { Text("Time (HH:MM)") }, singleLine = true)
                OutlinedTextField(prompt, { prompt = it }, label = { Text("What to do each time") }, minLines = 4)
                Hint("Runs as a project chat with web search and tasks access; code runs in the sandbox; you get a notification.")
            } },
            confirmButton = { TextButton(onClick = {
                scheduling = null
                scope.launch { runCatching { vm.api?.projectSchedule(p, at, prompt) }
                    .onSuccess { vm.toast = "Scheduled daily at $at (Schedules & alerts)" }.onFailure { vm.toast = it.message } }
            }) { Text("Schedule") } },
            dismissButton = { TextButton(onClick = { scheduling = null }) { Text("Cancel") } })
    }

    Screen("Projects", openDrawer, actions = { IconButton(onClick = { editing = ProjectDto() }) { Icon(Icons.Default.Add, "New project") } }) {
        Hint("A project has a goal, notes and a folder that all its chats share; the AI records progress so every new chat " +
            "or scheduled run continues where the last one stopped.")
        val l = list
        if (l != null && l.isEmpty()) OutlinedButton(onClick = { editing = ProjectDto() }) { Text("Create your first project") }
        l?.forEach { p ->
            Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                Column(Modifier.padding(12.dp).clickable { openId = if (openId == p.id) null else p.id },
                    verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("📁 " + p.name, style = MaterialTheme.typography.titleMedium)
                    Text(p.goal.ifBlank { "(no goal yet)" }, style = MaterialTheme.typography.bodyMedium,
                        maxLines = if (openId == p.id) 20 else 2, overflow = TextOverflow.Ellipsis)
                    if (openId == p.id) {
                        Text("Notes", style = MaterialTheme.typography.titleSmall)
                        Text(p.notes.ifBlank { "(none yet)" }, style = MaterialTheme.typography.bodySmall)
                        if (p.files.isNotEmpty()) {
                            Text("Files (${p.files.size})", style = MaterialTheme.typography.titleSmall)
                            Text(p.files.take(12).joinToString("\n"), style = MaterialTheme.typography.bodySmall)
                        }
                        Text("Chats (${p.chats.size})", style = MaterialTheme.typography.titleSmall)
                        p.chats.take(10).forEach { c ->
                            Text("• " + c.title, color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.clickable { vm.screen = Screen.CHAT; vm.openSession(c.id) })
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Button(onClick = { scope.launch {
                                runCatching { vm.api?.projectNewChat(p.id) }.getOrNull()?.let { s -> vm.screen = Screen.CHAT; vm.openSession(s.id) }
                            } }) { Text("New chat") }
                            OutlinedButton(onClick = { scheduling = p }) { Text("Daily work") }
                            OutlinedButton(onClick = { editing = p }) { Text("Edit") }
                        }
                        TextButton(onClick = { scope.launch { runCatching { vm.api?.projectDelete(p.id) }; reload() } }) {
                            Text("Delete project (chats and files stay)", color = MaterialTheme.colorScheme.error) }
                    }
                }
            }
        }
    }
}
