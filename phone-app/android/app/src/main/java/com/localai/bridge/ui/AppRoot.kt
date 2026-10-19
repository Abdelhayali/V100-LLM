package com.localai.bridge.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Workspaces
import androidx.compose.material.icons.filled.KeyboardVoice
import androidx.compose.material.icons.filled.TravelExplore
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.EventNote
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Snackbar
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun AppRoot(vm: MainViewModel) {
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { Box(Modifier.fillMaxSize()) {
        if (!vm.paired) PairScreen(vm) else MainShell(vm)
        vm.toast?.let { msg ->
            LaunchedEffect(msg) { delay(3500); vm.toast = null }
            Snackbar(Modifier.align(Alignment.BottomCenter).safeDrawingPadding().padding(16.dp)) { Text(msg) }
        }
    } }
}

// ------------------------------------------------------------------ pairing
@Composable
fun PairScreen(vm: MainViewModel) {
    var url by remember { mutableStateOf(vm.prefs.serverUrl) }
    var token by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun connect() {
        busy = true; error = null
        scope.launch { error = vm.pair(url, token); busy = false }
    }

    val ctx = androidx.compose.ui.platform.LocalContext.current
    val pickQr = rememberLauncherForActivityResult(androidx.activity.result.contract.ActivityResultContracts.GetContent()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val text = com.localai.bridge.data.decodeQrImage(ctx, uri)
            val p = text?.let { vm.parsePairQr(it) }
            when {
                p != null -> { url = p.url; token = p.token; connect() }
                text == null -> error = "No QR code found in that image"
                else -> error = "That QR code is not a LocalAI Bridge pairing code"
            }
        }
    }

    val scanner = rememberLauncherForActivityResult(ScanContract()) { r ->
        val p = r.contents?.let { vm.parsePairQr(it) }
        if (p != null) { url = p.url; token = p.token; connect() }
        else if (r.contents != null) error = "That QR code is not a LocalAI Bridge pairing code"
    }

    Column(
        Modifier.fillMaxSize().safeDrawingPadding().imePadding().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp, Alignment.CenterVertically),
    ) {
        Text("LocalAI Bridge", style = MaterialTheme.typography.headlineMedium)
        Text("Connect to the server running on your Windows PC. Start it, then scan the QR code it shows.",
            style = MaterialTheme.typography.bodyMedium)
        Button(
            onClick = {
                scanner.launch(ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                    .setPrompt("Scan the QR shown by LocalAI Bridge Server").setBeepEnabled(false).setOrientationLocked(false))
            },
            modifier = Modifier.fillMaxWidth(), enabled = !busy,
        ) {
            Icon(Icons.Default.QrCodeScanner, null); Spacer(Modifier.size(8.dp)); Text("Scan QR code with camera")
        }
        OutlinedButton(onClick = { pickQr.launch("image/*") }, modifier = Modifier.fillMaxWidth(), enabled = !busy) {
            Icon(Icons.Default.Image, null); Spacer(Modifier.size(8.dp)); Text("Load QR from image / screenshot")
        }
        Text("or enter manually", style = MaterialTheme.typography.labelMedium, modifier = Modifier.align(Alignment.CenterHorizontally))
        OutlinedTextField(url, { url = it }, label = { Text("Server URL (https://....trycloudflare.com)") },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
        OutlinedTextField(token, { token = it }, label = { Text("Access token") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        OutlinedButton(onClick = ::connect, enabled = !busy && url.isNotBlank() && token.isNotBlank(),
            modifier = Modifier.fillMaxWidth()) {
            if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp) else Text("Connect")
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
}

// ------------------------------------------------------------------ main shell with drawer
@Composable
fun MainShell(vm: MainViewModel) {
    val drawer = rememberDrawerState(DrawerValue.Closed)
    // phone woke up / app reopened: pick up replies the PC kept working on meanwhile
    androidx.lifecycle.compose.LifecycleEventEffect(androidx.lifecycle.Lifecycle.Event.ON_START) { vm.onAppForeground() }
    androidx.lifecycle.compose.LifecycleEventEffect(androidx.lifecycle.Lifecycle.Event.ON_STOP) { vm.onAppBackground() }
    val scope = rememberCoroutineScope()
    var renaming by remember { mutableStateOf<Pair<String, String>?>(null) }
    var confirmDelete by remember { mutableStateOf<String?>(null) }

    BackHandler(enabled = drawer.isOpen || vm.screen != Screen.CHAT) {
        if (drawer.isOpen) scope.launch { drawer.close() } else vm.screen = Screen.CHAT
    }
    fun go(s: Screen) { vm.screen = s; scope.launch { drawer.close() } }

    ModalNavigationDrawer(drawerState = drawer, drawerContent = {
        ModalDrawerSheet {
            Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                Spacer(Modifier.height(16.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("LocalAI Bridge", style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.padding(8.dp).weight(1f))
                    val dark = when (vm.themeMode) { "dark" -> true; "light" -> false; else -> isSystemInDarkTheme() }
                    IconButton(onClick = { vm.setTheme(if (dark) "light" else "dark") }) {
                        Icon(if (dark) Icons.Default.LightMode else Icons.Default.DarkMode,
                            if (dark) "Light mode" else "Dark mode")
                    }
                }
                PcStatusBar(vm.pcStatus, onClick = { go(Screen.MODELS) }, modifier = Modifier.padding(bottom = 8.dp))
                Button(onClick = { vm.newChat(); scope.launch { drawer.close() } }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.Add, null); Spacer(Modifier.size(6.dp)); Text("New chat")
                }
                Spacer(Modifier.height(8.dp))
                // compact 3-row grid instead of 9 full-width rows, so the session list below has room
                val tiles = listOf(
                    Triple(Screen.ORGANIZER, "Notes &\ntasks", Icons.Default.EventNote),
                    Triple(Screen.MODELS, "Models", Icons.Default.Storage),
                    Triple(Screen.SCHEDULES, "Schedules\n& alerts", Icons.Default.Schedule),
                    Triple(Screen.TRANSLATE, "Translator", Icons.Default.Translate),
                    Triple(Screen.RESEARCH, "Deep\nresearch", Icons.Default.TravelExplore),
                    Triple(Screen.NOTES, "Voice\nnotes", Icons.Default.KeyboardVoice),
                    Triple(Screen.PROJECTS, "Projects", Icons.Default.Workspaces),
                    Triple(Screen.AUDIT, "Audit\nlog", Icons.Default.History),
                    Triple(Screen.TASKS, "Running" + if (vm.backgroundTaskCount > 0) " (${vm.backgroundTaskCount})" else "", Icons.Default.Memory),
                    Triple(Screen.API, "API key", Icons.Default.Key),
                    Triple(Screen.AGENT, "Code\nagent", Icons.Default.Code),
                    Triple(Screen.FILES, "Files", Icons.Default.Folder),
                    Triple(Screen.TERMINAL, "Terminal", Icons.Default.Terminal),
                    Triple(Screen.MEMORY, "Memory", Icons.Default.Psychology),
                    Triple(Screen.SETTINGS, "Settings", Icons.Default.Settings),
                )
                tiles.chunked(5).forEach { row ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                        row.forEach { (s, label, icon) -> DrawerTile(label, icon, vm.screen == s, Modifier.weight(1f)) { go(s) } }
                        repeat(5 - row.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
                HorizontalDivider(Modifier.padding(vertical = 6.dp))
                Text("Sessions (${vm.sessions.size})", style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp))
                LazyColumn(Modifier.weight(1f)) {
                    items(vm.sessions, key = { it.id }) { s ->
                        Row(
                            Modifier.fillMaxWidth().clickable {
                                vm.openSession(s.id); scope.launch { drawer.close() }
                            }.padding(start = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(Icons.AutoMirrored.Filled.Chat, null, Modifier.size(18.dp),
                                tint = if (s.id == vm.currentSessionId) MaterialTheme.colorScheme.primary
                                else MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(s.title + if (s.running) "  •" else "", maxLines = 1, overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f).padding(horizontal = 10.dp))
                            IconButton(onClick = { renaming = s.id to s.title }) { Icon(Icons.Default.Edit, "Rename", Modifier.size(18.dp)) }
                            IconButton(onClick = { confirmDelete = s.id }) { Icon(Icons.Default.Delete, "Delete", Modifier.size(18.dp)) }
                        }
                    }
                }
            }
        }
    }) {
        val openDrawer = { scope.launch { drawer.open() }; Unit }
        when (vm.screen) {
            Screen.CHAT -> ChatScreen(vm, openDrawer)
            Screen.FILES -> FilesScreen(vm, openDrawer)
            Screen.TERMINAL -> TerminalScreen(vm, openDrawer)
            Screen.MEMORY -> MemoryScreen2(vm, openDrawer)
            Screen.SETTINGS -> SettingsScreen(vm, openDrawer)
            Screen.TASKS -> TasksScreen(vm, openDrawer)
            Screen.AGENT -> AgentScreen(vm, openDrawer)
            Screen.MODELS -> ModelsScreen(vm, openDrawer)
            Screen.API -> ApiScreen(vm, openDrawer)
            Screen.ORGANIZER -> OrganizerScreen(vm, openDrawer)
            Screen.SCHEDULES -> SchedulesScreen(vm, openDrawer)
            Screen.TRANSLATE -> TranslateScreen(vm, openDrawer)
            Screen.RESEARCH -> ResearchScreen(vm, openDrawer)
            Screen.NOTES -> NotesScreen(vm, openDrawer)
            Screen.PROJECTS -> ProjectsScreen(vm, openDrawer)
            Screen.AUDIT -> AuditScreen(vm, openDrawer)
        }
    }

    renaming?.let { (id, old) ->
        var t by remember(id) { mutableStateOf(old) }
        AlertDialog(onDismissRequest = { renaming = null }, title = { Text("Rename session") },
            text = { OutlinedTextField(t, { t = it }, singleLine = true) },
            confirmButton = { TextButton(onClick = { vm.renameSession(id, t); renaming = null }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { renaming = null }) { Text("Cancel") } })
    }
    confirmDelete?.let { id ->
        AlertDialog(onDismissRequest = { confirmDelete = null }, title = { Text("Delete session?") },
            text = { Text("This removes the conversation from the PC.") },
            confirmButton = { TextButton(onClick = { vm.deleteSession(id); confirmDelete = null }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { confirmDelete = null }) { Text("Cancel") } })
    }
}

/** One square menu entry: icon over a short label, highlighted when its screen is open. */
@Composable
private fun DrawerTile(label: String, icon: androidx.compose.ui.graphics.vector.ImageVector, selected: Boolean,
                       modifier: Modifier = Modifier, onClick: () -> Unit) {
    Surface(onClick = onClick, shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp), modifier = modifier,
        color = if (selected) MaterialTheme.colorScheme.secondaryContainer else androidx.compose.ui.graphics.Color.Transparent) {
        Column(Modifier.padding(vertical = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(icon, null, Modifier.size(22.dp))
            Text(label, style = MaterialTheme.typography.labelSmall, maxLines = 2, textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                lineHeight = androidx.compose.ui.unit.TextUnit(12f, androidx.compose.ui.unit.TextUnitType.Sp))
        }
    }
}
