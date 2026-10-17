package com.localai.bridge.ui

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.MemoryDto
import com.localai.bridge.data.MemoryStatus
import com.localai.bridge.data.addMemoryIn
import com.localai.bridge.data.editMemory
import com.localai.bridge.data.memorySearch
import com.localai.bridge.data.memoryStatus
import com.localai.bridge.data.setAutoMemory
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val CATS = listOf("personal", "family", "work", "preferences", "health", "places", "plans", "other")
private val CAT_LABEL = mapOf("personal" to "Personal", "family" to "Family", "work" to "Work", "preferences" to "Likes",
    "health" to "Health", "places" to "Places", "plans" to "Plans", "other" to "Other")

/** What the assistant remembers about the user: search by meaning, filter, edit, turn auto-remember on / off. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryScreen2(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<List<MemoryDto>?>(null) }
    var st by remember { mutableStateOf<MemoryStatus?>(null) }
    var q by remember { mutableStateOf("") }
    var cat by remember { mutableStateOf("") }
    var newText by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf<MemoryDto?>(null) }
    fun load() = scope.launch {
        list = runCatching { vm.api?.memorySearch(q, cat) }.onFailure { vm.toast = it.message }.getOrNull()
        st = runCatching { vm.api?.memoryStatus() }.getOrNull()
    }
    LaunchedEffect(cat) { load() }
    LaunchedEffect(q) { delay(400); load() }          // search as you type (meaning, any language)

    Scaffold(topBar = {
        TopAppBar(title = { Text("Memory") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { load() }) { Icon(Icons.Default.Refresh, "Refresh") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().imePadding().padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            val s = st
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                Column(Modifier.padding(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Remember automatically", style = MaterialTheme.typography.titleSmall)
                            Text("After each reply the AI keeps lasting facts about you (family, work, likes, plans) and " +
                                "updates or removes ones that changed.", style = MaterialTheme.typography.bodySmall)
                        }
                        Switch(checked = s?.autoMemory ?: true, onCheckedChange = { on ->
                            scope.launch { st = runCatching { vm.api?.setAutoMemory(on) }.getOrNull() ?: st }
                        })
                    }
                    Text(when {
                        s == null -> ""
                        s.ready -> "${s.count} memories · smart recall by meaning (Arabic + English) is on"
                        s.loading -> "${s.count} memories · preparing smart recall on the PC (first time downloads ~2 GB)…"
                        s.error.isNotBlank() -> "${s.count} memories · smart recall unavailable, using word search (${s.error.take(80)})"
                        else -> "${s.count} memories"
                    }, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            OutlinedTextField(q, { q = it }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                label = { Text("Search memories (any language, by meaning)") },
                leadingIcon = { Icon(Icons.Default.Search, null) })
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                FilterChip(selected = cat == "", onClick = { cat = "" }, label = { Text("All") })
                CATS.forEach { c -> FilterChip(selected = cat == c, onClick = { cat = if (cat == c) "" else c }, label = { Text(CAT_LABEL[c] ?: c) }) }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(newText, { newText = it }, Modifier.weight(1f), singleLine = true,
                    placeholder = { Text("Add: e.g. I prefer answers in Arabic") })
                IconButton(enabled = newText.isNotBlank(), onClick = {
                    val t = newText; newText = ""
                    scope.launch { runCatching { vm.api?.addMemoryIn(t, cat.ifBlank { "other" }) }.onFailure { vm.toast = it.message }; load() }
                }) { Icon(Icons.Default.Add, "Add") }
            }
            val l = list
            if (l != null && l.isEmpty()) Text(if (q.isBlank()) "Nothing remembered yet. Just chat: the AI keeps what matters."
                                               else "Nothing matches.", style = MaterialTheme.typography.bodySmall)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(l.orEmpty(), key = { it.id }) { m ->
                    Card(Modifier.fillMaxWidth().clickable { editing = m }) {
                        Column(Modifier.padding(10.dp)) {
                            Text(m.content, style = MaterialTheme.typography.bodyMedium)
                            val date = java.text.SimpleDateFormat("d MMM yyyy", java.util.Locale.getDefault())
                                .format(java.util.Date(((m.updated ?: m.created) * 1000).toLong()))
                            Text("${CAT_LABEL[m.category] ?: m.category} · ${if (m.source == "manual") "added by you" else "remembered by AI"} · $date",
                                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }

    editing?.let { m ->
        var t by remember(m.id) { mutableStateOf(m.content) }
        var c by remember(m.id) { mutableStateOf(m.category ?: "other") }
        AlertDialog(onDismissRequest = { editing = null }, title = { Text("Memory") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(t, { t = it }, modifier = Modifier.fillMaxWidth().heightIn(min = 90.dp))
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        CATS.forEach { x -> FilterChip(selected = c == x, onClick = { c = x }, label = { Text(CAT_LABEL[x] ?: x) }) }
                    }
                }
            },
            confirmButton = { TextButton(enabled = t.isNotBlank(), onClick = {
                scope.launch { runCatching { vm.api?.editMemory(m.id, t, c) }.onFailure { vm.toast = it.message }; editing = null; load() }
            }) { Text("Save") } },
            dismissButton = {
                Row {
                    TextButton(onClick = {
                        scope.launch { runCatching { vm.api?.deleteMemory(m.id) }; editing = null; load() }
                    }) { Text("Forget", color = MaterialTheme.colorScheme.error) }
                    Spacer(Modifier.width(4.dp))
                    TextButton(onClick = { editing = null }) { Text("Cancel") }
                }
            })
    }
}
