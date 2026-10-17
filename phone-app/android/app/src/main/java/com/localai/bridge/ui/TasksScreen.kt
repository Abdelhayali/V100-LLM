package com.localai.bridge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dangerous
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.TaskRun

fun phaseLabel(phase: String, tool: String): String = when (phase) {
    "prompt" -> "Reading the conversation"
    "thinking" -> "Thinking"
    "writing" -> "Writing"
    "tool_args" -> "Preparing a tool call"
    "tool" -> "Running ${tool.replace('_', ' ')}"
    "approval" -> "Waiting for approval (${tool.replace('_', ' ')})"
    "compressing" -> "Compressing the conversation"
    else -> "Starting"
}

private fun mmss(sec: Long) = "%d:%02d".format(sec / 60, sec % 60)

/** Everything the PC is doing right now, with stop buttons. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    var confirmKill by remember { mutableStateOf(false) }
    val agentVm: AgentViewModel = androidx.lifecycle.viewmodel.compose.viewModel()
    LaunchedEffect(Unit) {
        while (true) { vm.refreshTasks(); kotlinx.coroutines.delay(2000) }  // fast refresh while visible
    }
    val t = vm.tasks
    Scaffold(topBar = {
        TopAppBar(
            title = { Text("Running tasks") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { vm.refreshTasks() }) { Icon(Icons.Default.Refresh, "Refresh") } },
        )
    }) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (t == null) {
                CircularProgressIndicator()
                return@Column
            }
            // ---- LLM server state
            val llm = when (t.llmBusy) { true -> "busy generating"; false -> "idle"; else -> "unknown" }
            Card(colors = CardDefaults.cardColors(
                containerColor = if (t.llmBusy == true && t.runs.isEmpty()) MaterialTheme.colorScheme.errorContainer
                else MaterialTheme.colorScheme.surfaceContainerHigh)) {
                Column(Modifier.fillMaxWidth().padding(12.dp)) {
                    Text("LLM server: $llm", style = MaterialTheme.typography.titleSmall)
                    if (t.llmBusy == true && t.runs.isEmpty()) {
                        Text("The model is generating, but no chat is waiting for it. An earlier request was cut off " +
                            "and the LLM server is finishing it anyway. New messages wait until it ends.",
                            style = MaterialTheme.typography.bodySmall)
                        OutlinedButton(onClick = { vm.abortLlm() }, modifier = Modifier.padding(top = 6.dp)) { Text("Stop it") }
                    }
                }
            }

            // ---- chats
            Text("Chats (${t.runs.size})", style = MaterialTheme.typography.titleMedium)
            if (t.runs.isEmpty()) Text("No chat is generating.", style = MaterialTheme.typography.bodySmall)
            t.runs.forEach { r -> RunCard(vm, r) }

            // ---- BETA: coding agents
            if (t.agents.isNotEmpty()) {
                Text("Code agents (${t.agents.size})", style = MaterialTheme.typography.titleMedium)
                t.agents.forEach { a ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(a.title, style = MaterialTheme.typography.titleSmall)
                                Text(a.directory, style = MaterialTheme.typography.bodySmall, maxLines = 1,
                                    overflow = TextOverflow.Ellipsis)
                            }
                            OutlinedButton(onClick = {
                                agentVm.api = vm.api
                                agentVm.open(a.id)
                                vm.screen = Screen.AGENT
                            }) { Text("Open") }
                            Spacer(Modifier.size(6.dp))
                            OutlinedButton(onClick = { vm.stopAgent(a.id) }) { Text("Stop") }
                        }
                    }
                }
            }

            // ---- code processes
            Text("Code running on the PC (${t.processes.size})", style = MaterialTheme.typography.titleMedium)
            if (t.processes.isEmpty()) Text("No code is running.", style = MaterialTheme.typography.bodySmall)
            t.processes.forEach { p ->
                Card(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("${p.language} · pid ${p.pid} · ${mmss(p.elapsed)}", style = MaterialTheme.typography.labelLarge)
                            Text(p.preview, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall,
                                maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                        OutlinedButton(onClick = { vm.killProcess(p.pid) }) { Text("Kill") }
                    }
                }
            }

            Spacer(Modifier.size(8.dp))
            Button(
                onClick = { confirmKill = true },
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                modifier = Modifier.fillMaxWidth(),
            ) { Icon(Icons.Default.Dangerous, null); Spacer(Modifier.size(8.dp)); Text("Kill all") }
            Text("Stops every chat, kills all code started from the app and denies pending approvals.",
                style = MaterialTheme.typography.bodySmall)
        }
    }
    if (confirmKill) AlertDialog(
        onDismissRequest = { confirmKill = false },
        title = { Text("Kill everything?") },
        text = { Text("All running chats stop and all code started from the app is killed. Partial answers are lost.") },
        confirmButton = { TextButton(onClick = { confirmKill = false; vm.killAll() }) { Text("Kill all") } },
        dismissButton = { TextButton(onClick = { confirmKill = false }) { Text("Cancel") } },
    )
}

@Composable
private fun RunCard(vm: MainViewModel, r: TaskRun) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text(r.title, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            val speed = r.tps?.let { " · %.1f t/s".format(it) } ?: ""
            Text("${phaseLabel(r.phase, r.tool)} · ${r.tokens} tokens$speed · ${mmss(r.elapsed)}",
                style = MaterialTheme.typography.bodySmall,
                color = if (r.waitingApproval) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                OutlinedButton(onClick = { vm.openSession(r.sessionId) }) { Text("Open") }
                OutlinedButton(onClick = { vm.stopTask(r.sessionId) }) { Text("Stop") }
            }
        }
    }
}
