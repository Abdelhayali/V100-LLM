package com.localai.bridge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.ScheduleDto
import com.localai.bridge.data.alerts
import com.localai.bridge.data.alertsSet
import com.localai.bridge.data.scheduleDelete
import com.localai.bridge.data.scheduleRunNow
import com.localai.bridge.data.scheduleSave
import com.localai.bridge.data.schedules
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Scheduled prompts that run on the PC by themselves, and GPU / CPU temperature alerts (notifications on the phone). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SchedulesScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<List<ScheduleDto>?>(null) }
    var editing by remember { mutableStateOf<ScheduleDto?>(null) }
    var gpuC by remember { mutableStateOf("") }
    var cpuC by remember { mutableStateOf("") }
    fun reload() = scope.launch {
        runCatching { vm.api?.schedules() }.onSuccess { list = it }.onFailure { vm.toast = it.message }
    }
    LaunchedEffect(Unit) {
        reload()
        runCatching { vm.api?.alerts() }.getOrNull()?.let {
            gpuC = if (it.gpuC > 0) "%.0f".format(it.gpuC) else ""; cpuC = if (it.cpuC > 0) "%.0f".format(it.cpuC) else ""
        }
    }
    editing?.let { s -> ScheduleDialog(s, onDismiss = { editing = null }) { saved ->
        editing = null
        scope.launch {
            runCatching { vm.api?.scheduleSave(saved) }.onSuccess { vm.toast = "Saved: ${saved.name}"; reload() }
                .onFailure { vm.toast = it.message }
        }
    } }
    Scaffold(topBar = {
        TopAppBar(title = { Text("Schedules & alerts") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { editing = ScheduleDto() }) { Icon(Icons.Default.Add, "New schedule") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Scheduled tasks", style = MaterialTheme.typography.titleMedium)
            Text("A prompt your PC runs by itself, e.g. \"Summarize my unread email\" every morning at 8:00. The answer " +
                "goes to its own chat and you get a notification (checked every 15 min in the background).",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            val l = list
            if (l != null && l.isEmpty()) OutlinedButton(onClick = { editing = ScheduleDto() }) { Text("Add your first schedule") }
            l?.forEach { s ->
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                    Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(s.name, style = MaterialTheme.typography.titleSmall)
                                Text((if (s.kind == "daily") "Every day at ${s.at}" else "Every ${s.everyMin} min") +
                                    (s.nextRun?.let { " · next " + SimpleDateFormat("EEE HH:mm", Locale.getDefault()).format(Date((it * 1000).toLong())) } ?: "") +
                                    (s.lastStatus?.takeIf { it.isNotBlank() }?.let { " · last: $it" } ?: ""),
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            Switch(checked = s.enabled, onCheckedChange = { on ->
                                scope.launch { runCatching { vm.api?.scheduleSave(s.copy(enabled = on)) }; reload() }
                            })
                        }
                        Text(s.prompt, style = MaterialTheme.typography.bodyMedium, maxLines = 3)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { scope.launch {
                                runCatching { vm.api?.scheduleRunNow(s.id) }; vm.toast = "Running ${s.name} now - you'll get a notification"
                            } }) { Text("Run now") }
                            OutlinedButton(onClick = { editing = s }) { Text("Edit") }
                            if (!s.sessionId.isNullOrBlank()) TextButton(onClick = { vm.screen = Screen.CHAT; vm.openSession(s.sessionId) }) { Text("Chat") }
                            TextButton(onClick = { scope.launch { runCatching { vm.api?.scheduleDelete(s.id) }; reload() } }) {
                                Text("Delete", color = MaterialTheme.colorScheme.error) }
                        }
                    }
                }
            }

            Text("Temperature alerts", style = MaterialTheme.typography.titleMedium)
            Text("A notification when the GPU or CPU gets hotter than your limit (checked every 30 s on the PC, at most " +
                "one alert per 15 min). Leave empty for no alert. CPU needs LibreHardwareMonitor running on the PC.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(gpuC, { gpuC = it.filter(Char::isDigit).take(3) }, label = { Text("GPU °C") },
                    modifier = Modifier.weight(1f), singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                OutlinedTextField(cpuC, { cpuC = it.filter(Char::isDigit).take(3) }, label = { Text("CPU °C") },
                    modifier = Modifier.weight(1f), singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                Button(onClick = { scope.launch {
                    runCatching { vm.api?.alertsSet(gpuC.toDoubleOrNull() ?: 0.0, cpuC.toDoubleOrNull() ?: 0.0) }
                        .onSuccess { vm.toast = "Alerts: GPU ${gpuC.ifBlank { "off" }} · CPU ${cpuC.ifBlank { "off" }}" }
                        .onFailure { vm.toast = it.message }
                } }) { Text("Save") }
            }
            Text("Typical: GPU 85 °C (the V100 slows itself down from ~83 °C), CPU 85 °C.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ScheduleDialog(s: ScheduleDto, onDismiss: () -> Unit, onSave: (ScheduleDto) -> Unit) {
    var name by remember { mutableStateOf(s.name) }
    var prompt by remember { mutableStateOf(s.prompt) }
    var daily by remember { mutableStateOf(s.kind != "every") }
    var at by remember { mutableStateOf(s.at) }
    var every by remember { mutableStateOf(s.everyMin.toString()) }
    var web by remember { mutableStateOf(s.web) }
    var email by remember { mutableStateOf(s.email) }
    var organizer by remember { mutableStateOf(s.organizer) }
    val atOk = Regex("^([01]?\\d|2[0-3]):[0-5]\\d$").matches(at)
    AlertDialog(onDismissRequest = onDismiss,
        title = { Text(if (s.id == 0) "New schedule" else "Edit schedule") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true)
                OutlinedTextField(prompt, { prompt = it }, label = { Text("What should the AI do?") }, minLines = 3)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    FilterChip(selected = daily, onClick = { daily = true }, label = { Text("Daily") })
                    FilterChip(selected = !daily, onClick = { daily = false }, label = { Text("Every N min") })
                }
                if (daily) OutlinedTextField(at, { at = it.take(5) }, label = { Text("Time (HH:MM)") }, singleLine = true,
                    isError = !atOk)
                else OutlinedTextField(every, { every = it.filter(Char::isDigit).take(5) }, label = { Text("Every … minutes (min 5)") },
                    singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                AccessRow("Email (read, draft; sending asks you)", email) { email = it }
                AccessRow("Tasks & calendar", organizer) { organizer = it }
                AccessRow("Web search", web) { web = it }
                Text("Code always runs in the sandbox for scheduled tasks.", style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = {
            TextButton(enabled = name.isNotBlank() && prompt.isNotBlank() && (!daily || atOk), onClick = {
                onSave(s.copy(name = name.trim(), prompt = prompt.trim(), kind = if (daily) "daily" else "every", at = at,
                    everyMin = (every.toIntOrNull() ?: 60).coerceAtLeast(5), web = web, email = email, organizer = organizer))
            }) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
private fun AccessRow(label: String, on: Boolean, set: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Switch(checked = on, onCheckedChange = set)
    }
}
