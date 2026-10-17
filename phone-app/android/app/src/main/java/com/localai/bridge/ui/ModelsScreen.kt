package com.localai.bridge.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.V100Model
import com.localai.bridge.data.V100Status
import com.localai.bridge.data.v100Load
import com.localai.bridge.data.v100Models
import com.localai.bridge.data.v100Status
import com.localai.bridge.data.v100Unload
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private fun gib(b: Long) = "%.1f".format(b / 1073741824.0)

/** Load / unload models on the PC through the V100-LLM launcher, with live GPU / CPU / RAM, like its GUI. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModelsScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf<V100Status?>(null) }
    var models by remember { mutableStateOf<List<V100Model>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val chosen = remember { mutableStateMapOf<String, String>() }   // model id -> preset id
    var wasReady by remember { mutableStateOf(false) }

    fun loadModels() = scope.launch {
        error = null
        try { models = vm.api?.v100Models() } catch (e: Exception) { error = e.message }
    }
    LaunchedEffect(Unit) { loadModels() }
    LaunchedEffect(Unit) {
        while (true) {
            try {
                val s = vm.api?.v100Status()
                status = s
                val ready = s?.health == "ready"
                if (ready && !wasReady) vm.refreshModels()     // the chat's model list follows the loaded model
                wasReady = ready
            } catch (_: Exception) { }
            delay(2000)
        }
    }

    fun load(m: V100Model) = scope.launch {
        busy = true
        try {
            val p = chosen[m.id] ?: m.presets.firstOrNull()?.id ?: ""
            vm.api?.v100Load(m.id, p)
            vm.toast = "Loading ${m.name}…"
        } catch (e: Exception) { vm.toast = e.message }
        busy = false
    }
    fun unload() = scope.launch {
        busy = true
        try { vm.api?.v100Unload(); vm.toast = "Model unloaded, GPU memory freed" } catch (e: Exception) { vm.toast = e.message }
        busy = false
    }

    Scaffold(topBar = {
        TopAppBar(
            title = { Text("Models (V100)") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { loadModels() }) { Icon(Icons.Default.Refresh, "Refresh") } },
        )
    }) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            StatusCard(status, busy, onUnload = { unload() })

            Text("Models", style = MaterialTheme.typography.titleMedium)
            error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = { loadModels() }) { Text("Try again (starts the launcher on the PC)") }
            }
            val list = models
            if (list == null && error == null) CircularProgressIndicator()
            list?.sortedByDescending { it.installed }?.forEach { m ->
                ModelCard(
                    m = m, status = status, busy = busy,
                    preset = chosen[m.id] ?: m.presets.firstOrNull()?.id ?: "",
                    onPreset = { chosen[m.id] = it },
                    onLoad = { load(m) }, onUnload = { unload() },
                )
            }
        }
    }
}

@Composable
private fun Meter(label: String, frac: Float, text: String) {
    Column(Modifier.fillMaxWidth()) {
        Row {
            Text(label, style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
            Text(text, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        val f = frac.coerceIn(0f, 1f)
        LinearProgressIndicator(
            progress = { f }, modifier = Modifier.fillMaxWidth().padding(top = 3.dp),
            color = when { f > 0.97f -> MaterialTheme.colorScheme.error; f > 0.85f -> Color(0xFFE3A33B); else -> MaterialTheme.colorScheme.primary },
        )
    }
}

@Composable
private fun StatusCard(s: V100Status?, busy: Boolean, onUnload: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (s == null) { CircularProgressIndicator(Modifier.size(20.dp)); return@Column }
            if (!s.launcher) {
                Text("V100-LLM launcher is not running on the PC", style = MaterialTheme.typography.titleSmall)
                Text("It starts automatically when the model list loads (tap refresh).", style = MaterialTheme.typography.bodySmall)
                return@Column
            }
            val loaded = s.health != "stopped"
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(if (loaded) s.modelName.ifBlank { s.model } else "No model loaded",
                        style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text(when (s.health) {
                        "ready" -> "Ready · ${s.presetName}"
                        "loading" -> "Loading… ${s.uptime}s · ${s.presetName}"
                        "stopped" -> "GPU memory is free"
                        else -> s.health
                    }, style = MaterialTheme.typography.bodySmall,
                        color = when (s.health) { "ready" -> Color(0xFF2E9D57); "loading" -> Color(0xFFC27C0E); else -> MaterialTheme.colorScheme.onSurfaceVariant })
                }
                if (loaded) OutlinedButton(onClick = onUnload, enabled = !busy,
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Unload") }
            }
            val gpu = s.gpuName.replace("Tesla ", "").ifBlank { "GPU" }
            if (s.vramTotalMb > 0) Meter("$gpu VRAM", s.vramUsedMb.toFloat() / s.vramTotalMb,
                "%.1f / %.1f GB".format(s.vramUsedMb / 1024.0, s.vramTotalMb / 1024.0))
            Meter("GPU load", s.gpuUtil / 100f, "${s.gpuUtil}%")
            Meter("CPU", (s.cpu / 100).toFloat(), "%.0f%% of %d threads".format(s.cpu, s.cpuThreads))
            if (s.ramTotal > 0) Meter("RAM", s.ramUsed.toFloat() / s.ramTotal,
                "${gib(s.ramUsed)} / ${gib(s.ramTotal)} GB" + if (s.modelRam > 0) " · model ${gib(s.modelRam)}" else "")
            if (s.health == "loading" && s.log.isNotEmpty())
                Text(s.log.last(), style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace,
                    maxLines = 2, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ModelCard(
    m: V100Model, status: V100Status?, busy: Boolean, preset: String,
    onPreset: (String) -> Unit, onLoad: () -> Unit, onUnload: () -> Unit,
) {
    val isThis = status?.model == m.id && status.health != "stopped"
    val other = status != null && status.health != "stopped" && !isThis
    Card(Modifier.fillMaxWidth(), colors = if (isThis) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
        else CardDefaults.cardColors()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(m.name, style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                if (m.sizeGb > 0) AssistChip(onClick = {}, label = { Text("${m.sizeGb} GB") })
                if (m.vision) AssistChip(onClick = {}, label = { Text("vision") })
                if (!m.installed) AssistChip(onClick = {}, label = { Text("not downloaded") })
            }
            if (m.desc.isNotBlank()) Text(m.desc, style = MaterialTheme.typography.bodySmall, maxLines = 3, overflow = TextOverflow.Ellipsis,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            val p = m.presets.firstOrNull { it.id == preset }
            if (m.presets.isNotEmpty()) {
                var open by remember { mutableStateOf(false) }
                Box {
                    TextButton(onClick = { open = true }) {
                        Text(p?.name ?: preset, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, false))
                        Icon(Icons.Default.ArrowDropDown, null)
                    }
                    DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                        m.presets.forEach { x ->
                            DropdownMenuItem(text = { Text(x.name) }, onClick = { onPreset(x.id); open = false })
                        }
                    }
                }
                p?.bench?.takeIf { it.isNotBlank() }?.let {
                    Text("Measured: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (!m.installed) Text("Download it first in the GUI on the PC", style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.weight(1f))
                else Spacer(Modifier.weight(1f))
                if (isThis) {
                    OutlinedButton(onClick = onUnload, enabled = !busy) { Text("Unload") }
                    Spacer(Modifier.width(8.dp))
                }
                Button(onClick = onLoad, enabled = !busy && m.installed && !(isThis && status?.health == "loading")) {
                    Text(when { isThis -> "Reload"; other -> "Switch to this"; else -> "Load" })
                }
            }
        }
    }
}


@Composable
private fun MiniMeter(label: String, frac: Float, text: String, modifier: Modifier) {
    Column(modifier) {
        Text("$label $text", style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        val f = frac.coerceIn(0f, 1f)
        LinearProgressIndicator(progress = { f }, modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
            color = when { f > 0.97f -> MaterialTheme.colorScheme.error; f > 0.85f -> Color(0xFFE3A33B); else -> MaterialTheme.colorScheme.primary })
    }
}

/** One-glance PC status (loaded model + VRAM / GPU / CPU / RAM), shown in the chat and the menu. Tap = Models screen. */
@Composable
fun PcStatusBar(s: V100Status?, onClick: () -> Unit, modifier: Modifier = Modifier) {
    if (s == null || !s.launcher) return
    androidx.compose.material3.Surface(color = MaterialTheme.colorScheme.surfaceContainerHigh,
        modifier = modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            val dot = when (s.health) { "ready" -> Color(0xFF2E9D57); "loading" -> Color(0xFFC27C0E); else -> MaterialTheme.colorScheme.outline }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("●", color = dot, style = MaterialTheme.typography.labelMedium)
                Text(when (s.health) {
                    "ready" -> "  ${s.modelName.ifBlank { s.model }}"
                    "loading" -> "  Loading ${s.modelName.ifBlank { s.model }}… ${s.uptime}s"
                    "stopped" -> "  No model loaded (tap to load one)"
                    else -> "  ${s.health}"
                }, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                val w = Modifier.weight(1f)
                if (s.vramTotalMb > 0) MiniMeter("VRAM", s.vramUsedMb.toFloat() / s.vramTotalMb, "%.1f/%.0fG".format(s.vramUsedMb / 1024.0, s.vramTotalMb / 1024.0), w)
                MiniMeter("GPU", s.gpuUtil / 100f, "${s.gpuUtil}%", w)
                MiniMeter("CPU", (s.cpu / 100).toFloat(), "%.0f%%".format(s.cpu), w)
                if (s.ramTotal > 0) MiniMeter("RAM", s.ramUsed.toFloat() / s.ramTotal, "${gib(s.ramUsed)}/${"%.0f".format(s.ramTotal / 1073741824.0)}G", w)
            }
        }
    }
}

