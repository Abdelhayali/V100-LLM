package com.localai.bridge.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.ShopChoice
import com.localai.bridge.data.ShopFiles
import com.localai.bridge.data.ShopInstalled
import com.localai.bridge.data.ShopProgress
import com.localai.bridge.data.ShopRepo
import com.localai.bridge.data.shopFiles
import com.localai.bridge.data.shopInstall
import com.localai.bridge.data.shopInstalled
import com.localai.bridge.data.shopProgress
import com.localai.bridge.data.shopRemove
import com.localai.bridge.data.shopSearch
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private fun gb(b: Long) = "%.1f GB".format(b / 1e9)
private fun fitColor(f: String) = when (f) { "gpu" -> Color(0xFF2E9D57); "tight" -> Color(0xFFC27C0E); else -> Color(0xFFC0392B) }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShopScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var q by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<ShopRepo>>(emptyList()) }
    var open by remember { mutableStateOf<ShopFiles?>(null) }
    var mmproj by remember { mutableStateOf<String?>(null) }
    var confirm by remember { mutableStateOf<ShopChoice?>(null) }
    var removing by remember { mutableStateOf<ShopInstalled?>(null) }
    var installed by remember { mutableStateOf<List<ShopInstalled>>(emptyList()) }
    var progress by remember { mutableStateOf<ShopProgress?>(null) }
    fun reloadInstalled() = scope.launch { runCatching { vm.api?.shopInstalled() }.getOrNull()?.let { installed = it } }
    LaunchedEffect(Unit) {
        reloadInstalled()
        var was = false
        while (true) {
            runCatching { vm.api?.shopProgress() }.getOrNull()?.let { p ->
                progress = p
                if (was && !p.active) { reloadInstalled(); if (p.error.isNotBlank()) vm.toast = p.error else vm.toast = "Download finished: the model is in Models" }
                was = p.active
            }
            delay(2000)
        }
    }
    fun search() = scope.launch {
        if (q.isBlank()) return@launch
        busy = true; open = null
        runCatching { vm.api?.shopSearch(q.trim()) }.onSuccess { results = it.orEmpty() }.onFailure { vm.toast = it.message }
        busy = false
    }
    fun openRepo(repo: String) = scope.launch {
        busy = true
        runCatching { vm.api?.shopFiles(repo) }.onSuccess { open = it; mmproj = null }.onFailure { vm.toast = it.message }
        busy = false
    }

    confirm?.let { c ->
        val f = open ?: return@let
        val mm = f.mmproj.firstOrNull { it.name == mmproj }
        AlertDialog(onDismissRequest = { confirm = null }, title = { Text("Download this model?") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("From huggingface.co/${f.repo}")
                c.parts.forEach { Text("• ${it.name}  (${gb(it.size)})", style = MaterialTheme.typography.bodySmall) }
                mm?.let { Text("• ${it.name}  (${gb(it.size)}, vision)", style = MaterialTheme.typography.bodySmall) }
                Text("Total ${gb(c.size + (mm?.size ?: 0))} onto the PC (V100-LLM\\models). Each file is checked against " +
                     "its SHA-256 from Hugging Face.", style = MaterialTheme.typography.bodySmall)
                Text(c.fitText, color = fitColor(c.fit), style = MaterialTheme.typography.bodySmall)
                if (f.license.isNotBlank()) Text("Licence: ${f.license}", style = MaterialTheme.typography.bodySmall)
            } },
            confirmButton = { TextButton(onClick = {
                confirm = null
                scope.launch {
                    runCatching { vm.api?.shopInstall(f.repo, c.key, mm?.name) }
                        .onSuccess { vm.toast = "Downloading ${it?.name ?: "the model"}…" }.onFailure { vm.toast = it.message }
                }
            }) { Text("Download") } },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } })
    }
    removing?.let { m ->
        AlertDialog(onDismissRequest = { removing = null }, title = { Text("Remove ${m.name}?") },
            text = { Text("Deletes its files from the PC (${gb(m.size)}) and removes it from Models. If it is loaded, it is unloaded first.") },
            confirmButton = { TextButton(onClick = {
                removing = null
                scope.launch { runCatching { vm.api?.shopRemove(m.id) }.onSuccess { reloadInstalled(); vm.toast = "Removed" }.onFailure { vm.toast = it.message } }
            }) { Text("Remove", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { removing = null }) { Text("Cancel") } })
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text("Model shop") },
            navigationIcon = { IconButton(onClick = { if (open != null) open = null else vm.screen = Screen.MODELS }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            progress?.takeIf { it.active }?.let { p ->
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Downloading: ${p.item}", style = MaterialTheme.typography.bodyMedium)
                        if (p.total > 0) LinearProgressIndicator(progress = { (p.done.toFloat() / p.total).coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
                        else LinearProgressIndicator(Modifier.fillMaxWidth())
                        if (p.total > 0) Text("${gb(p.done)} of ${gb(p.total)}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            val f = open
            if (f == null) {
                Text("Find GGUF models on Hugging Face and install them on the PC. They run on the standard llama.cpp engine " +
                     "with automatic fit (what does not fit in 16 GB runs on the CPU), not tuned like the catalog models.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedTextField(q, { q = it }, label = { Text("Search, e.g. Qwen3 8B, Gemma 3, Llama") }, singleLine = true, modifier = Modifier.weight(1f))
                    Button(onClick = { search() }, enabled = !busy) { Text("Search") }
                }
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                results.forEach { r ->
                    Card(Modifier.fillMaxWidth().clickable { openRepo(r.repo) }, colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                        Column(Modifier.padding(12.dp)) {
                            Text(r.repo, fontWeight = FontWeight.SemiBold)
                            Text("⬇ %,d · ♥ %d".format(r.downloads, r.likes) + (if (r.license.isNotBlank()) " · ${r.license}" else "") +
                                 (if (r.gated) " · 🔒 gated (sign in on the PC)" else ""), style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                if (installed.isNotEmpty()) {
                    Text("Installed from the shop", style = MaterialTheme.typography.titleMedium)
                    installed.forEach { m ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(m.name); Text(gb(m.size) + if (m.installed) " · ready in Models" else " · not fully downloaded",
                                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            TextButton(onClick = { removing = m }) { Text("Remove", color = MaterialTheme.colorScheme.error) }
                        }
                    }
                }
            } else {
                Text(f.repo, style = MaterialTheme.typography.titleMedium)
                if (f.gated) Text("🔒 Gated: on the PC run `hf auth login` once and accept access on the model's Hugging Face page.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (f.mmproj.isNotEmpty()) {
                    Text("Vision (lets the model see images):", style = MaterialTheme.typography.bodyMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        FilterChip(selected = mmproj == null, onClick = { mmproj = null }, label = { Text("No vision") })
                        f.mmproj.take(3).forEach { m -> FilterChip(selected = mmproj == m.name, onClick = { mmproj = m.name }, label = { Text("${m.name.removeSuffix(".gguf")} ${gb(m.size)}") }) }
                    }
                }
                if (f.choices.isEmpty()) Text("No GGUF files in this repository.")
                f.choices.forEach { c ->
                    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text((c.quant.ifBlank { c.key.substringAfterLast('/') }) + "  ·  " + gb(c.size) + if (c.parts.size > 1) "  (${c.parts.size} parts)" else "",
                                    fontWeight = FontWeight.SemiBold)
                                Text(c.fitText, color = fitColor(c.fit), style = MaterialTheme.typography.bodySmall)
                            }
                            OutlinedButton(onClick = { confirm = c }, enabled = progress?.active != true) { Text("Get") }
                        }
                    }
                }
            }
        }
    }
}
