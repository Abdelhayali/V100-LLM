package com.localai.bridge.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.AuditRow
import com.localai.bridge.data.audit
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Everything the AI did with tools: what, when, in which chat, approval, result. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuditScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val scope = rememberCoroutineScope()
    var rows by remember { mutableStateOf<List<AuditRow>?>(null) }
    var q by remember { mutableStateOf("") }
    var open by remember { mutableStateOf<Int?>(null) }
    fun load() = scope.launch { runCatching { vm.api?.audit(q) }.onSuccess { rows = it }.onFailure { vm.toast = it.message } }
    LaunchedEffect(q) { delay(300); load() }
    Scaffold(topBar = {
        TopAppBar(title = { Text("Audit log") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { load() }) { Icon(Icons.Default.Refresh, "Refresh") } })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().padding(horizontal = 12.dp)) {
            OutlinedTextField(q, { q = it }, label = { Text("Search (tool, file, command, result…)") },
                singleLine = true, modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp))
            val r = rows
            if (r != null && r.isEmpty()) Text("No actions yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(r.orEmpty(), key = { it.id }) { a ->
                    Card(Modifier.fillMaxWidth().clickable { open = if (open == a.id) null else a.id },
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(a.tool, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                                Text(SimpleDateFormat("dd MMM HH:mm:ss", Locale.getDefault()).format(Date((a.ts * 1000).toLong())),
                                    style = MaterialTheme.typography.labelSmall)
                            }
                            Text(a.summary, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace,
                                maxLines = if (open == a.id) 20 else 2, overflow = TextOverflow.Ellipsis)
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                Text(if (a.ok == 1) "✓ ok" else "✗ failed", style = MaterialTheme.typography.labelSmall,
                                    color = if (a.ok == 1) Color(0xFF2E9D57) else MaterialTheme.colorScheme.error)
                                Text(a.approval, style = MaterialTheme.typography.labelSmall, color = when (a.approval) {
                                    "approved" -> Color(0xFF2E7DD7); "denied", "blocked" -> MaterialTheme.colorScheme.error
                                    "auto" -> Color(0xFFC27C0E); else -> MaterialTheme.colorScheme.onSurfaceVariant })
                                Text(listOfNotNull(a.chat, a.source.takeIf { it != "chat" }).joinToString(" · "),
                                    style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                            if (open == a.id) {
                                Text(a.result, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
                                if (!a.sessionId.isNullOrBlank()) Text("Open chat", color = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.clickable { vm.screen = Screen.CHAT; vm.openSession(a.sessionId) })
                            }
                        }
                    }
                }
            }
        }
    }
}
