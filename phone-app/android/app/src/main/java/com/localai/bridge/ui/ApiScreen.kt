package com.localai.bridge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.OpenAiInfo
import com.localai.bridge.data.openAiDisable
import com.localai.bridge.data.openAiInfo
import com.localai.bridge.data.openAiRegenerate
import kotlinx.coroutines.launch

/**
 * An OpenAI-compatible URL + API key for whatever model is loaded on the PC, to use in any app or script.
 * The key is made and refreshed here; the URL keeps working when another model is loaded.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Suppress("DEPRECATION")
@Composable
fun ApiScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    val clip = LocalClipboardManager.current
    var info by remember { mutableStateOf<OpenAiInfo?>(null) }
    var busy by remember { mutableStateOf(false) }
    var show by remember { mutableStateOf(false) }
    var confirm by remember { mutableStateOf<String?>(null) }   // "refresh" | "off"

    fun run(block: suspend () -> OpenAiInfo?) = scope.launch {
        busy = true
        try { block()?.let { info = it } } catch (e: Exception) { vm.toast = e.message }
        busy = false
    }
    LaunchedEffect(Unit) { run { vm.api?.openAiInfo() } }
    fun copy(label: String, text: String) { clip.setText(AnnotatedString(text)); vm.toast = "$label copied" }

    val i = info
    // the app knows the address it reaches the PC at, so the URL works even before the tunnel reports it
    val url = i?.baseUrl?.ifBlank { null } ?: (vm.prefs.serverUrl.trimEnd('/') + "/openai/v1")
    val model = vm.pcStatus?.modelName?.ifBlank { null } ?: i?.models?.firstOrNull()?.substringAfterLast('\\') ?: "no model loaded"

    Scaffold(topBar = {
        TopAppBar(
            title = { Text("API (OpenAI format)") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { run { vm.api?.openAiInfo() } }) { Icon(Icons.Default.Refresh, "Reload") } },
        )
    }) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Use the model running on your PC from any app, script or tool that speaks the OpenAI API. " +
                "Load or switch models from the Models screen: the same URL and key keep working.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (i == null) { CircularProgressIndicator(); return@Column }

            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Field("Base URL", url) { copy("URL", url) }
                    if (i.enabled) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("API key", style = MaterialTheme.typography.labelMedium)
                                SelectionContainer {
                                    Text(if (show) i.key else i.key.take(10) + "•".repeat(18), fontFamily = FontFamily.Monospace,
                                        style = MaterialTheme.typography.bodySmall)
                                }
                            }
                            IconButton(onClick = { show = !show }) {
                                Icon(if (show) Icons.Default.VisibilityOff else Icons.Default.Visibility, if (show) "Hide" else "Show")
                            }
                            IconButton(onClick = { copy("Key", i.key) }) { Icon(Icons.Default.ContentCopy, "Copy key") }
                        }
                    } else Text("API is off: no key yet. Generate one to turn it on.", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error)
                    Field("Model", model, copyable = false) {}
                    Text("Any model name works in requests: the PC answers with the loaded model.",
                        style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!i.enabled) Button(onClick = { run { vm.api?.openAiRegenerate() } }, enabled = !busy) { Text("Generate key") }
                else {
                    Button(onClick = { confirm = "refresh" }, enabled = !busy) {
                        Icon(Icons.Default.Refresh, null, Modifier.size(18.dp)); Text("  Refresh key")
                    }
                    OutlinedButton(onClick = { confirm = "off" }, enabled = !busy,
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Turn off") }
                }
            }

            if (i.enabled) {
                val curl = "curl $url/chat/completions \\\n  -H \"Authorization: Bearer ${i.key}\" \\\n" +
                    "  -H \"Content-Type: application/json\" \\\n  -d '{\"model\":\"local\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}]}'"
                val py = "from openai import OpenAI\nclient = OpenAI(base_url=\"$url\", api_key=\"${i.key}\")\n" +
                    "r = client.chat.completions.create(model=\"local\", messages=[{\"role\": \"user\", \"content\": \"Hi\"}])\n" +
                    "print(r.choices[0].message.content)"
                Example("curl", curl) { copy("curl example", curl) }
                Example("Python (openai package)", py) { copy("Python example", py) }
            }

            Text(
                (if (i.fixedUrl) "Your tunnel has a fixed address, so this URL stays the same."
                 else "Note: with the free quick tunnel the URL changes when the server on the PC restarts; open this " +
                    "screen again to get the new one (a named Cloudflare tunnel keeps it fixed).") +
                    " On the PC itself you can also use ${i.localUrl}. Refresh key makes the old key stop working at once.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }

    confirm?.let { what ->
        AlertDialog(onDismissRequest = { confirm = null },
            title = { Text(if (what == "refresh") "Refresh the API key?" else "Turn the API off?") },
            text = { Text(if (what == "refresh") "A new key is made. Apps using the old key stop working until you give them the new one."
                          else "The key is deleted and the URL stops answering until you generate a new key.") },
            confirmButton = { TextButton(onClick = {
                confirm = null
                run { if (what == "refresh") vm.api?.openAiRegenerate() else vm.api?.openAiDisable() }
            }) { Text(if (what == "refresh") "Refresh" else "Turn off") } },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } })
    }
}

@Composable
private fun Field(label: String, value: String, copyable: Boolean = true, onCopy: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.labelMedium)
            SelectionContainer { Text(value, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall) }
        }
        if (copyable) IconButton(onClick = onCopy) { Icon(Icons.Default.ContentCopy, "Copy $label") }
    }
}

@Composable
private fun Example(title: String, code: String, onCopy: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = MaterialTheme.typography.labelLarge, modifier = Modifier.weight(1f))
                IconButton(onClick = onCopy) { Icon(Icons.Default.ContentCopy, "Copy") }
            }
            SelectionContainer { Text(code, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall) }
        }
    }
}
