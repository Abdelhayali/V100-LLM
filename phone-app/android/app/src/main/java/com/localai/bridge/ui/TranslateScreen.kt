package com.localai.bridge.ui

import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.translate
import kotlinx.coroutines.launch

private data class Translation(val from: String, val to: String, val toLang: String)

/** Translator: speak or type Arabic -> English or English -> Arabic; the translation is read aloud. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TranslateScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    val history = remember { mutableStateListOf<Translation>() }
    var busy by remember { mutableStateOf(false) }
    var typed by remember { mutableStateOf("") }
    var pendingTo by remember { mutableStateOf("en") }

    fun run(text: String, to: String) {
        if (text.isBlank()) return
        busy = true
        scope.launch {
            try {
                val out = vm.api?.translate(text, to).orEmpty()
                history.add(0, Translation(text, out, to))
                if (out.isNotBlank()) vm.speaker.speak(out)
            } catch (e: Exception) { vm.toast = "Translation failed: ${e.message}" }
            busy = false
        }
    }
    val listen = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        val text = r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull().orEmpty()
        run(text, pendingTo)
    }
    fun speak(to: String) {
        pendingTo = to
        vm.speaker.stop()
        val from = if (to == "en") "ar-EG" else "en-US"     // listen in the language you speak, not the phone's
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, from)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, from)
            .putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true)
            .putExtra(RecognizerIntent.EXTRA_PROMPT, if (to == "en") "تكلم بالعربية" else "Speak English")
        runCatching { listen.launch(i) }.onFailure { vm.toast = "No speech recognizer on this phone (install the Google app)" }
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text("Translator") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = { speak("en") }, enabled = !busy, modifier = Modifier.weight(1f).height(84.dp)) {
                    Text("🎤 عربي → English", style = MaterialTheme.typography.titleMedium) }
                Button(onClick = { speak("ar") }, enabled = !busy, modifier = Modifier.weight(1f).height(84.dp)) {
                    Text("🎤 English → عربي", style = MaterialTheme.typography.titleMedium) }
            }
            OutlinedTextField(typed, { typed = it }, label = { Text("Or type text to translate") },
                modifier = Modifier.fillMaxWidth(), minLines = 2)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { run(typed, "en"); typed = "" }, enabled = !busy && typed.isNotBlank()) { Text("→ English") }
                OutlinedButton(onClick = { run(typed, "ar"); typed = "" }, enabled = !busy && typed.isNotBlank()) { Text("→ العربية") }
                if (busy) CircularProgressIndicator(Modifier.padding(start = 8.dp))
                if (vm.speaking) TextButton(onClick = { vm.speaker.stop() }) { Text("Stop reading") }
            }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(history) { h ->
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(h.from, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(h.to, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            Row {
                                TextButton(onClick = { vm.speaker.speak(h.to) }) { Text("▶ Read") }
                                TextButton(onClick = { run(h.to, if (h.toLang == "en") "ar" else "en") }) { Text("⇄ Back") }
                            }
                        }
                    }
                }
            }
        }
    }
}
