package com.localai.bridge.ui

import androidx.compose.material.icons.filled.Compress
import androidx.compose.material.icons.filled.DocumentScanner
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.Shield
import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.automirrored.filled.InsertDriveFile
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.InputChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.RadioButton
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.EventNote
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Drafts
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Screenshot
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Switch
import androidx.compose.ui.Alignment
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.runtime.DisposableEffect
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.FilterChip
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.localai.bridge.data.AttachmentRef
import com.localai.bridge.data.PendingApproval
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    val ctx = LocalContext.current
    val listState = rememberLazyListState()
    var attachMenu by remember { mutableStateOf(false) }
    var thinkMenu by remember { mutableStateOf(false) }
    if (thinkMenu) AlertDialog(onDismissRequest = { thinkMenu = false },
        title = { Text("Thinking effort") },
        text = { Column { THINKING_MODES.forEach { (id, label, tip) ->
            Row(Modifier.fillMaxWidth().clickable { vm.updateThinking(id); thinkMenu = false }.padding(vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = vm.thinking == id, onClick = { vm.updateThinking(id); thinkMenu = false })
                Column { Text(label); Text(tip, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            } } } },
        confirmButton = { TextButton(onClick = { thinkMenu = false }) { Text("Close") } })
    var ocrMenu by remember { mutableStateOf(false) }
    if (ocrMenu) AlertDialog(onDismissRequest = { ocrMenu = false },
        title = { Text("OCR sub-model") },
        text = { Column {
            Text("Unlimited-OCR reads scanned PDFs, photos of pages and text in images (any language) for the chat model.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OCR_MODES.forEach { (id, label, tip) ->
            Row(Modifier.fillMaxWidth().clickable { vm.updateOcr(id); ocrMenu = false }.padding(vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = vm.ocr == id, onClick = { vm.updateOcr(id); ocrMenu = false })
                Column { Text(label); Text(tip, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            } } } },
        confirmButton = { TextButton(onClick = { ocrMenu = false }) { Text("Close") } })
    var confirmAuto by remember { mutableStateOf(false) }
    var modelMenu by remember { mutableStateOf(false) }
    var cameraUri by rememberSaveable { mutableStateOf<String?>(null) }

    val pickFiles = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        if (uris.isNotEmpty()) vm.attach(uris)
    }
    var photoVoice by rememberSaveable { mutableStateOf(false) }   // camera + voice: ask about the photo by speaking
    val takePhoto = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        cameraUri?.let {
            if (ok && photoVoice) vm.photoQuestion(Uri.parse(it))
            else if (ok) vm.attach(listOf(Uri.parse(it)), "photo_${System.currentTimeMillis()}.jpg")
        }
        photoVoice = false
    }
    fun launchCamera() {
        val f = File(ctx.cacheDir, "camera_${System.currentTimeMillis()}.jpg")
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.files", f)
        cameraUri = uri.toString()
        takePhoto.launch(uri)
    }
    val camPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) launchCamera() else vm.toast = "Camera permission denied"
    }
    // voice chat: the phone's speech recognizer (Arabic / English), then the reply is read aloud
    val listen = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        val text = r.data?.getStringArrayListExtra(android.speech.RecognizerIntent.EXTRA_RESULTS)?.firstOrNull().orEmpty()
        if (text.isNotBlank()) vm.sendVoice(text)
    }
    fun startListening() {
        val i = android.content.Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(android.speech.RecognizerIntent.EXTRA_PROMPT, "Ask your PC…")
        runCatching { listen.launch(i) }.onFailure { vm.toast = "No speech recognizer on this phone (install Google app)" }
    }
    LaunchedEffect(vm.pendingVoice) { if (vm.pendingVoice) { vm.pendingVoice = false; startListening() } }
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) vm.startDriving() else vm.toast = "Driving mode needs the microphone permission"
    }
    fun driveOn() {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) vm.startDriving()
        else micPermission.launch(Manifest.permission.RECORD_AUDIO)
    }
    if (vm.driving) { DrivingOverlay(vm); return }
    val inputFocus = remember { androidx.compose.ui.focus.FocusRequester() }
    LaunchedEffect(vm.focusInput) { if (vm.focusInput) { vm.focusInput = false; runCatching { inputFocus.requestFocus() } } }

    LaunchedEffect(vm.items.size, (vm.items.lastOrNull() as? ChatItem.Assistant)?.text?.length) {
        if (vm.items.isNotEmpty()) listState.scrollToItem(vm.items.lastIndex, Int.MAX_VALUE / 2)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
                title = {
                    Column {
                        Text(vm.currentTitle, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Box {
                            Row(Modifier.clickable { modelMenu = true; vm.refreshModels() }, verticalAlignment = Alignment.CenterVertically) {
                                Text(shortModel(vm.currentModel.ifBlank { "auto model" }), style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Icon(Icons.Default.ArrowDropDown, null, Modifier.size(16.dp))
                                if (vm.autoApprove) Text("  AUTO-APPROVE", style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.error)
                            }
                            DropdownMenu(modelMenu, { modelMenu = false }) {
                                val models = vm.info?.models.orEmpty()
                                if (models.isEmpty()) DropdownMenuItem(text = { Text("No models (is the LLM running?)") }, onClick = { modelMenu = false })
                                models.forEach { m ->
                                    DropdownMenuItem(text = { Text(shortModel(m)) }, onClick = { vm.selectModel(m); modelMenu = false })
                                }
                            }
                        }
                    }
                },
                actions = { IconButton(onClick = { driveOn() }) { Icon(Icons.Default.DirectionsCar, "Driving mode (hands-free)") } },
            )
        },
    ) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).imePadding()) {
            vm.connectionError?.let {
                Surface(color = MaterialTheme.colorScheme.errorContainer, modifier = Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(it, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = { vm.refreshAll() }) { Text("Retry") }
                    }
                }
            }
            PcStatusBar(vm.pcStatus, onClick = { vm.screen = Screen.MODELS })
            if (vm.loadingSession) LinearProgressIndicator(Modifier.fillMaxWidth())
            vm.stats?.let { Box(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 2.dp)) { StatsLine(it) } }
            if (vm.backgroundTaskCount > 0) {
                Surface(color = MaterialTheme.colorScheme.tertiaryContainer,
                    modifier = Modifier.fillMaxWidth().clickable { vm.screen = Screen.TASKS }) {
                    Row(Modifier.padding(horizontal = 16.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp)
                        val t = vm.tasks
                        val orphan = t?.llmBusy == true && t.runs.isEmpty()
                        Text(if (orphan) "  The LLM is busy with an earlier request - tap to see"
                             else "  ${vm.backgroundTaskCount} task(s) running on your PC - tap to see / stop",
                            style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
                    }
                }
            }

            Box(Modifier.weight(1f)) {
                if (vm.items.isEmpty() && !vm.loadingSession) EmptyChat()
                LazyColumn(state = listState, contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxSize()) {
                    items(vm.items, key = { it.key }) { item ->
                        when (item) {
                            is ChatItem.User -> UserBubble(vm, item)
                            is ChatItem.Assistant -> {
                                val last = item === vm.items.lastOrNull { it is ChatItem.Assistant } && vm.items.last() !is ChatItem.User
                                AssistantBubble(vm, item, isLast = last)
                                if (last && item === vm.items.last() && !vm.streaming && vm.questions.isEmpty())
                                    QuickReplies(remember(item.text) { suggestedReplies(item.text) }, vm)
                            }
                            is ChatItem.Tool -> ToolCard(vm, item)
                            is ChatItem.Notice -> Text(item.text, style = MaterialTheme.typography.bodySmall,
                                color = if (item.error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    if (vm.streaming && vm.items.lastOrNull() !is ChatItem.Assistant) item {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    }
                }
            }

            // ---- pending attachments
            if (vm.pendingAttachments.isNotEmpty() || vm.uploading) {
                LazyRow(Modifier.padding(horizontal = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(vm.pendingAttachments, key = { it.id }) { a ->
                        InputChip(selected = false, onClick = { vm.pendingAttachments.remove(a) },
                            label = { Text(a.filename, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.widthIn(max = 160.dp)) },
                            leadingIcon = { Icon(kindIcon(a.kind), null, Modifier.size(16.dp)) },
                            trailingIcon = { Icon(Icons.Default.Close, "Remove", Modifier.size(16.dp)) })
                    }
                    if (vm.uploading) item { CircularProgressIndicator(Modifier.size(24.dp).padding(4.dp), strokeWidth = 2.dp) }
                }
            }

            // ---- the model asks the user to choose (ask_user): reply paused until a choice is tapped
            vm.questions.firstOrNull()?.let { QuestionCard(it, vm) }

            // ---- step list: the model's plan, or the actions it is taking on the PC
            ActivityCard(vm)

            // ---- live status while the PC is working
            if (vm.streaming) LiveStatus(vm)

            // ---- editing banner
            if (vm.editingMessageId != null) {
                Surface(color = MaterialTheme.colorScheme.secondaryContainer, modifier = Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(start = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Edit, null, Modifier.size(16.dp))
                        Text("  Editing message - the chat continues from here", style = MaterialTheme.typography.labelMedium,
                            modifier = Modifier.weight(1f))
                        IconButton(onClick = { vm.cancelEdit() }) { Icon(Icons.Default.Close, "Cancel edit") }
                    }
                }
            }

            if (vm.speaking) Row(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.Center) {
                Button(onClick = { vm.speaker.stop() }, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
                    Icon(Icons.Default.VolumeOff, null, Modifier.size(18.dp)); Spacer(Modifier.size(6.dp)); Text("Stop reading")
                }
            }
            // ---- active modes (tap to turn off) - kept out of the input row so the text field stays wide
            if (vm.webSearch || vm.autoApprove || vm.emailAccess || vm.organizerAccess || vm.thinking != "auto" || vm.ocr != "off" || vm.sandbox || vm.pcActions) {
                // one line that scrolls sideways: several chips must never squeeze each other into tall columns
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(start = 12.dp, end = 12.dp, top = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (vm.thinking != "auto") InputChip(selected = vm.thinking != "off", onClick = { thinkMenu = true },
                        label = { Text("Thinking: " + (THINKING_MODES.firstOrNull { it.first == vm.thinking }?.second ?: vm.thinking), maxLines = 1, softWrap = false) },
                        leadingIcon = { Icon(Icons.Default.Psychology, null, Modifier.size(16.dp)) })
                    if (vm.pcActions) InputChip(selected = true, onClick = { vm.togglePcActions() },
                        label = { Text("PC actions", maxLines = 1, softWrap = false) },
                        leadingIcon = { Icon(Icons.Default.Computer, null, Modifier.size(16.dp)) },
                        trailingIcon = { Icon(Icons.Default.Close, "Turn off", Modifier.size(14.dp)) })
                    if (vm.sandbox) InputChip(selected = true, onClick = { vm.toggleSandbox() },
                        label = { Text("Sandbox", maxLines = 1, softWrap = false) },
                        leadingIcon = { Icon(Icons.Default.Shield, null, Modifier.size(16.dp)) },
                        trailingIcon = { Icon(Icons.Default.Close, "Turn off", Modifier.size(14.dp)) })
                    if (vm.ocr != "off") InputChip(selected = true, onClick = { ocrMenu = true },
                        label = { Text("OCR: " + (if (vm.ocr == "gpu") "GPU" else "CPU"), maxLines = 1, softWrap = false) },
                        leadingIcon = { Icon(Icons.Default.DocumentScanner, null, Modifier.size(16.dp)) })
                    if (vm.emailAccess) InputChip(selected = true, onClick = { vm.toggleEmailAccess() },
                        label = { Text("Email", maxLines = 1, softWrap = false) }, leadingIcon = { Icon(Icons.Default.Email, null, Modifier.size(16.dp)) },
                        trailingIcon = { Icon(Icons.Default.Close, "Turn off", Modifier.size(14.dp)) })
                    if (vm.organizerAccess) InputChip(selected = true, onClick = { vm.toggleOrganizerAccess() },
                        label = { Text("Tasks", maxLines = 1, softWrap = false) }, leadingIcon = { Icon(Icons.Default.EventNote, null, Modifier.size(16.dp)) },
                        trailingIcon = { Icon(Icons.Default.Close, "Turn off", Modifier.size(14.dp)) })
                    if (vm.webSearch) InputChip(selected = true, onClick = { vm.toggleWebSearch() },
                        label = { Text("Web search", maxLines = 1, softWrap = false) },
                        leadingIcon = { Icon(Icons.Default.Public, null, Modifier.size(16.dp)) },
                        trailingIcon = { Icon(Icons.Default.Close, "Turn off", Modifier.size(14.dp)) })
                    if (vm.autoApprove) InputChip(selected = true, onClick = { vm.updateAutoApprove(false) },
                        label = { Text("Auto-approve", color = MaterialTheme.colorScheme.error, maxLines = 1, softWrap = false) },
                        leadingIcon = { Icon(Icons.Default.Bolt, null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.error) },
                        trailingIcon = { Icon(Icons.Default.Close, "Turn off", Modifier.size(14.dp)) })
                }
            }

            // ---- input bar
            Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(8.dp), verticalAlignment = Alignment.Bottom) {
                Box {
                    IconButton(onClick = { attachMenu = true }) { Icon(Icons.Default.AttachFile, "Attach and options") }
                    DropdownMenu(attachMenu, { attachMenu = false }) {
                        DropdownMenuItem(text = { Text("Image") }, leadingIcon = { Icon(Icons.Default.Image, null) },
                            onClick = { attachMenu = false; pickFiles.launch(arrayOf("image/*")) })
                        DropdownMenuItem(text = { Text("PDF") }, leadingIcon = { Icon(Icons.Default.PictureAsPdf, null) },
                            onClick = { attachMenu = false; pickFiles.launch(arrayOf("application/pdf")) })
                        DropdownMenuItem(text = { Text("Any file") }, leadingIcon = { Icon(Icons.AutoMirrored.Filled.InsertDriveFile, null) },
                            onClick = { attachMenu = false; pickFiles.launch(arrayOf("*/*")) })
                        DropdownMenuItem(text = { Text("Screenshot of PC") }, leadingIcon = { Icon(Icons.Default.Screenshot, null) },
                            onClick = { attachMenu = false; vm.attachScreenshot() })
                        DropdownMenuItem(text = { Text("Camera") }, leadingIcon = { Icon(Icons.Default.CameraAlt, null) },
                            onClick = {
                                attachMenu = false
                                if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) launchCamera()
                                else camPermission.launch(Manifest.permission.CAMERA)
                            })
                        DropdownMenuItem(text = { Text("Compress conversation now") }, leadingIcon = { Icon(Icons.Default.Compress, null) },
                            enabled = !vm.streaming && vm.currentSessionId != null,
                            onClick = { attachMenu = false; vm.compressNow() })
                        HorizontalDivider()
                        DropdownMenuItem(text = { Text("Thinking: " + (THINKING_MODES.firstOrNull { it.first == vm.thinking }?.second ?: vm.thinking)) },
                            leadingIcon = { Icon(Icons.Default.Psychology, null) },
                            onClick = { attachMenu = false; thinkMenu = true })
                        DropdownMenuItem(text = { Text("OCR: " + (OCR_MODES.firstOrNull { it.first == vm.ocr }?.second ?: vm.ocr)) },
                            leadingIcon = { Icon(Icons.Default.DocumentScanner, null) },
                            onClick = { attachMenu = false; ocrMenu = true })
                        DropdownMenuItem(text = { Text("Ask about a photo (camera + voice)") }, leadingIcon = { Icon(Icons.Default.PhotoCamera, null) },
                            onClick = {
                                attachMenu = false; photoVoice = true
                                if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) launchCamera()
                                else camPermission.launch(Manifest.permission.CAMERA)
                            })
                        DropdownMenuItem(text = { Text("Driving mode (hands-free)") }, leadingIcon = { Icon(Icons.Default.DirectionsCar, null) },
                            onClick = { attachMenu = false; driveOn() })
                        DropdownMenuItem(text = { Text("PC actions (screen, open, files, scripts)") }, leadingIcon = { Icon(Icons.Default.Computer, null) },
                            trailingIcon = { Switch(checked = vm.pcActions, onCheckedChange = null) },
                            onClick = { vm.togglePcActions() })
                        DropdownMenuItem(text = { Text("Run code in sandbox") }, leadingIcon = { Icon(Icons.Default.Shield, null) },
                            trailingIcon = { Switch(checked = vm.sandbox, onCheckedChange = null) },
                            onClick = { vm.toggleSandbox() })
                        DropdownMenuItem(text = { Text("Web search") }, leadingIcon = { Icon(Icons.Default.Public, null) },
                            trailingIcon = { Switch(checked = vm.webSearch, onCheckedChange = null) },
                            onClick = { vm.toggleWebSearch() })
                        DropdownMenuItem(text = { Text("Email access") }, leadingIcon = { Icon(Icons.Default.Email, null) },
                            trailingIcon = { Switch(checked = vm.emailAccess, onCheckedChange = null) },
                            onClick = { vm.toggleEmailAccess() })
                        DropdownMenuItem(text = { Text("Tasks & calendar access") }, leadingIcon = { Icon(Icons.Default.EventNote, null) },
                            trailingIcon = { Switch(checked = vm.organizerAccess, onCheckedChange = null) },
                            onClick = { vm.toggleOrganizerAccess() })
                        DropdownMenuItem(text = { Text("Auto-approve") }, leadingIcon = { Icon(Icons.Default.Bolt, null) },
                            trailingIcon = { Switch(checked = vm.autoApprove, onCheckedChange = null) },
                            onClick = {
                                if (vm.autoApprove) vm.updateAutoApprove(false)
                                else { attachMenu = false; confirmAuto = true }
                            })
                    }
                }
                OutlinedTextField(
                    value = vm.draft, onValueChange = { vm.draft = it },
                    placeholder = { Text("Message…") },
                    modifier = Modifier.weight(1f).heightIn(max = 160.dp).focusRequester(inputFocus),
                    shape = RoundedCornerShape(24.dp),
                )
                Spacer(Modifier.size(6.dp))
                if (vm.streaming) {
                    FilledIconButton(onClick = { vm.stop() }) { Icon(Icons.Default.Stop, "Stop") }
                } else if (vm.draft.isBlank() && vm.pendingAttachments.isEmpty()) {
                    FilledIconButton(onClick = { vm.speaker.stop(); startListening() }) { Icon(Icons.Default.Mic, "Speak") }
                } else {
                    FilledIconButton(onClick = { vm.send() },
                        enabled = (vm.draft.isNotBlank() || vm.pendingAttachments.isNotEmpty()) && !vm.uploading) {
                        Icon(Icons.AutoMirrored.Filled.Send, "Send")
                    }
                }
            }
        }
    }

    vm.approvals.firstOrNull()?.let { ApprovalDialog(it, vm) }
    if (confirmAuto) AlertDialog(
        onDismissRequest = { confirmAuto = false },
        title = { Text("Turn on auto-approve?") },
        text = {
            Text("The AI will run code and write files on your PC without asking. A malicious web page, PDF or " +
                "file the AI reads could trick it into running harmful commands. Only use this with content you trust.")
        },
        confirmButton = { TextButton(onClick = { vm.updateAutoApprove(true); confirmAuto = false }) { Text("Turn on") } },
        dismissButton = { TextButton(onClick = { confirmAuto = false }) { Text("Cancel") } },
    )
}

private fun kfmt(n: Long): String = when {
    n >= 1_000_000 -> "%.1fM".format(n / 1e6)
    n >= 10_000 -> "%.0fk".format(n / 1e3)
    n >= 1_000 -> "%.1fk".format(n / 1e3)
    else -> n.toString()
}

/** "Context 2.4k / 131k (2%) · 36.1 t/s" under the chat title. */
@Composable
private fun StatsLine(s: com.localai.bridge.data.SessionStats?) {
    if (s == null) return
    val used = s.ctxUsed
    val size = s.ctxSize
    Row(verticalAlignment = Alignment.CenterVertically) {
        val parts = buildList {
            if (used != null) add(if (size != null) "Context ${kfmt(used)} / ${kfmt(size)} (${(used * 100 / size)}%)"
                                else "Context ${kfmt(used)} tokens")
            s.tps?.let { add("%.1f t/s".format(it)) }
            s.promptTps?.let { add("read %.0f t/s".format(it)) }
        }
        Text(parts.joinToString(" · "), style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
        if (used != null && size != null && size > 0) {
            Spacer(Modifier.size(6.dp))
            val frac = (used.toFloat() / size).coerceIn(0f, 1f)
            LinearProgressIndicator(progress = { frac }, modifier = Modifier.size(width = 40.dp, height = 4.dp),
                color = if (frac > 0.85f) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
        }
    }
}

/** Shows what the PC is doing right now, with elapsed time - so long tasks visibly keep progressing. */
@Composable
private fun LiveStatus(vm: MainViewModel) {
    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) { while (true) { now = System.currentTimeMillis(); kotlinx.coroutines.delay(500) } }
    val elapsed = ((now - vm.streamStartMs).coerceAtLeast(0) / 1000).toInt()
    val silent = ((now - vm.lastEventMs) / 1000).toInt()
    val speed = vm.liveTps?.let { " · %.1f t/s".format(it) } ?: ""
    val label = when (vm.phase) {
        "sending" -> "Sending to your PC…"
        "resuming" -> "Catching up with the PC…"
        "prompt" -> "Reading the conversation…"
        "thinking" -> "Thinking… ${vm.liveTokens} tokens$speed"
        "writing" -> "Writing… ${vm.liveTokens} tokens$speed"
        "tool_args" -> "Preparing a tool call… ${vm.liveTokens} tokens$speed"
        "tool" -> "Now: " + (vm.items.lastOrNull { it is ChatItem.Tool && it.status == "running" }
            ?.let { toolSummary((it as ChatItem.Tool).name, it.args) } ?: vm.phaseTool.replace('_', ' '))
        "approval" -> "Waiting for your approval"
        "question" -> "Waiting for your choice (see the options below)"
        "compressing" -> "Compressing the conversation…"
        else -> "Working…"
    }
    Surface(color = MaterialTheme.colorScheme.surfaceContainerHigh, modifier = Modifier.fillMaxWidth()) {
        Column {
            LinearProgressIndicator(Modifier.fillMaxWidth().height(2.dp))
            Row(Modifier.padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(label, style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f), maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
                Text("%d:%02d".format(elapsed / 60, elapsed % 60), style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (silent >= 30) Text(
                "No signal from the PC for ${silent}s - it may be busy or the connection dropped.",
                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(start = 12.dp, end = 12.dp, bottom = 6.dp))
        }
    }
}

/** llama.cpp reports models as full file paths; show just the file name. */
private fun shortModel(m: String) = m.substringAfterLast('\\').substringAfterLast('/')

@Composable
private fun EmptyChat() {
    Column(Modifier.fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(Icons.Default.Psychology, null, Modifier.size(56.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.size(12.dp))
        Text("Ask anything. Your PC's model can run code, read your folders, analyse PDFs and images, and remember things.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

fun kindIcon(kind: String) = when (kind) {
    "image" -> Icons.Default.Image
    "pdf" -> Icons.Default.PictureAsPdf
    "text" -> Icons.Default.Description
    else -> Icons.AutoMirrored.Filled.InsertDriveFile
}

@Composable
private fun MessageActions(content: @Composable () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) { content() }
}

@Composable
private fun SmallAction(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, onClick: () -> Unit) {
    IconButton(onClick = onClick, modifier = Modifier.size(34.dp)) {
        Icon(icon, label, Modifier.size(17.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun UserBubble(vm: MainViewModel, item: ChatItem.User) {
    val clip = LocalClipboardManager.current
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.End) {
        AttachmentsView(vm, item.attachments, alignEnd = true)
        if (item.text.isNotBlank()) {
            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(16.dp, 4.dp, 16.dp, 16.dp),
                modifier = Modifier.widthIn(max = 320.dp).padding(top = 4.dp)) {
                SelectionContainer { Text(item.text, Modifier.padding(12.dp)) }
            }
        }
        MessageActions {
            SmallAction(Icons.Default.ContentCopy, "Copy") {
                clip.setText(AnnotatedString(item.text)); vm.toast = "Copied"
            }
            if (!vm.streaming) SmallAction(Icons.Default.Edit, "Edit") { vm.startEdit(item) }
        }
    }
}

@Composable
private fun AssistantBubble(vm: MainViewModel, item: ChatItem.Assistant, isLast: Boolean) {
    val clip = LocalClipboardManager.current
    val (thinkInline, visible) = splitThink(item.text)
    val reasoning = (item.reasoning + thinkInline).trim()
    var showReasoning by remember { mutableStateOf(false) }
    var draftOpen by remember { mutableStateOf(false) }
    val emailId = remember(vm.items.size) { emailIdOfChat(vm.items) }
    if (draftOpen) SaveDraftDialog(vm, visible.trim(), emailId) { draftOpen = false }
    Column(Modifier.fillMaxWidth().animateContentSize()) {
        if (reasoning.isNotEmpty()) {
            AssistChip(onClick = { showReasoning = !showReasoning },
                label = { Text(if (showReasoning) "Hide thinking" else "Show thinking") },
                leadingIcon = { Icon(Icons.Default.Psychology, null, Modifier.size(16.dp)) })
            if (showReasoning) Text(reasoning, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 6.dp))
        }
        if (visible.isNotBlank()) {
            MarkdownText(visible.trim())
            val streamingThis = vm.streaming && isLast
            if (!streamingThis) MessageActions {
                SmallAction(Icons.Default.ContentCopy, "Copy") {
                    clip.setText(AnnotatedString(visible.trim())); vm.toast = "Copied"
                }
                if (looksLikeEmail(visible, emailId)) SmallAction(Icons.Default.Drafts, "Save as Gmail draft") { draftOpen = true }
                val reading = vm.speakingKey == item.key
                SmallAction(if (reading) Icons.Default.Stop else Icons.AutoMirrored.Filled.VolumeUp, if (reading) "Stop reading" else "Read aloud") {
                    vm.toggleSpeak(item.key, visible)
                }
                if (isLast && !vm.streaming) SmallAction(Icons.Default.Refresh, "Regenerate") { vm.regenerate() }
            }
        }
    }
}

private fun argText(args: JsonObject, k: String) = (args[k] as? JsonPrimitive)?.contentOrNull.orEmpty()

internal fun toolSummary(name: String, args: JsonObject): String = when (name) {
    "ask_user" -> "Ask you: ${argText(args, "question")}"
    "tasks_list" -> "Look at your tasks"
    "tasks_add" -> "Add task: ${argText(args, "title")}"
    "tasks_update" -> "Update task #${argText(args, "id")}"
    "notes_add" -> "Save note: ${argText(args, "title")}"
    "notes_search" -> "Search notes: ${argText(args, "query")}"
    "calendar_list" -> "Check calendar ${argText(args, "start")}"
    "calendar_add" -> "Add event: ${argText(args, "title")} ${argText(args, "start")}"
    "gmail_list" -> "Check email: ${argText(args, "query").ifBlank { "inbox" }}"
    "gmail_read" -> "Read an email"
    "gmail_draft" -> "Write a draft email"
    "gmail_send" -> "Send email to ${argText(args, "to").ifBlank { "the sender" }}"
    "gmail_send_draft" -> "Send the draft"
    "google_calendar_add" -> "Add to Google Calendar: ${argText(args, "title")}"
    "update_tasks" -> "Update the plan"
    "run_code" -> "Run ${argText(args, "language")}"
    "list_dir" -> "List ${argText(args, "path")}"
    "read_file" -> "Read ${argText(args, "path")}"
    "write_file" -> "Write ${argText(args, "path")}"
    "search_files" -> "Search ${argText(args, "pattern")} in ${argText(args, "root")}"
    "save_memory" -> "Remember: ${argText(args, "content")}"
    "search_memory" -> "Recall: ${argText(args, "query")}"
    "take_screenshot" -> "Screenshot of PC"
    "web_search" -> "Web search: ${argText(args, "query")}"
    "fetch_url" -> "Read ${argText(args, "url")}"
    "send_file_to_user" -> "Send ${shortModel(argText(args, "path"))}"
    else -> name
}

/** run_code returns JSON {exit_code, stdout, stderr}; show it as plain console text. */
private fun prettyOutput(raw: String): String = runCatching {
    val o = kotlinx.serialization.json.Json.parseToJsonElement(raw) as JsonObject
    buildString {
        append(argText(o, "stdout").trimEnd())
        argText(o, "stderr").takeIf { it.isNotBlank() }?.let { append("\n[stderr]\n").append(it.trimEnd()) }
        append("\n[exit ${argText(o, "exit_code")}${if (argText(o, "timed_out") == "true") ", timed out" else ""}]")
    }.trim()
}.getOrDefault(raw)

@Composable
private fun ToolCard(vm: MainViewModel, item: ChatItem.Tool) {
    var open by remember { mutableStateOf(false) }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh),
        modifier = Modifier.fillMaxWidth().clickable { open = !open }.animateContentSize()) {
        Column(Modifier.padding(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Build, null, Modifier.size(16.dp))
                Text(" " + toolSummary(item.name, item.args), style = MaterialTheme.typography.labelLarge,
                    maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                when (item.status) {
                    "running" -> CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp)
                    "awaiting" -> Text(if (item.name == "ask_user") "waiting for your choice" else "needs approval", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.tertiary)
                    else -> Text(if (open) "hide" else "details", style = MaterialTheme.typography.labelSmall)
                }
            }
            if (item.attachments.isNotEmpty()) {
                Spacer(Modifier.size(6.dp))
                AttachmentsView(vm, item.attachments)
            }
            if (open) {
                val code = argText(item.args, "code").ifBlank { argText(item.args, "content") }
                if (code.isNotBlank()) CodeBlock(code, argText(item.args, "language"))
                item.output?.let {
                    Text("Output", style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(top = 4.dp))
                    CodeBlock(prettyOutput(it).take(8000), "")
                }
            }
        }
    }
}

@Composable
private fun ApprovalDialog(p: PendingApproval, vm: MainViewModel) {
    val code = when (p.name) {
        "gmail_send" -> "To: ${argText(p.args, "to").ifBlank { "(reply to the original sender)" }}\n" +
            "Subject: ${argText(p.args, "subject").ifBlank { "(Re: original subject)" }}\n\n${argText(p.args, "body")}"
        "gmail_send_draft" -> "Draft id: ${argText(p.args, "draft_id")}\n(the draft the AI showed you in the chat)"
        "google_calendar_add" -> "${argText(p.args, "title")}\n${argText(p.args, "start")}" +
            argText(p.args, "end").let { if (it.isBlank()) "" else " → $it" } +
            argText(p.args, "location").let { if (it.isBlank()) "" else "\n@ $it" } +
            argText(p.args, "description").let { if (it.isBlank()) "" else "\n\n$it" }
        else -> argText(p.args, "code").ifBlank { argText(p.args, "content") }
    }
    AlertDialog(
        onDismissRequest = {},
        title = { Text(when (p.name) {
            "run_code" -> "Run code on your PC?"
            "gmail_send", "gmail_send_draft" -> "Send this email?"
            "google_calendar_add" -> "Add to Google Calendar?"
            else -> "Write file on your PC?"
        }) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(toolSummary(p.name, p.args), style = MaterialTheme.typography.labelLarge)
                Spacer(Modifier.size(8.dp))
                Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(6.dp)) {
                    Text(code, fontFamily = FontFamily.Monospace, fontSize = 12.sp, modifier = Modifier.padding(8.dp))
                }
            }
        },
        confirmButton = { TextButton(onClick = { vm.respondApproval(p, true) }) { Text("Approve") } },
        dismissButton = { TextButton(onClick = { vm.respondApproval(p, false) }) { Text("Deny") } },
    )
}


/** Full-screen, glanceable driving view: what the app is doing, what it heard, the answer, and big buttons. */
@Composable
private fun DrivingOverlay(vm: MainViewModel) {
    val view = androidx.compose.ui.platform.LocalView.current
    DisposableEffect(Unit) { view.keepScreenOn = true; onDispose { view.keepScreenOn = false } }
    androidx.activity.compose.BackHandler { vm.stopDriving() }
    val (label, color) = when {
        vm.streaming && vm.phase.isNotBlank() && vm.phase != "writing" -> "Thinking…" to Color(0xFFC27C0E)
        vm.driveState == "speaking" || vm.speaking -> "Speaking…" to Color(0xFF2E7DD7)
        vm.streaming -> "Writing the answer…" to Color(0xFFC27C0E)
        vm.driveState == "listening" -> "Listening… speak now" to Color(0xFF2E9D57)
        else -> "Getting ready…" to MaterialTheme.colorScheme.onSurfaceVariant
    }
    val answer = (vm.items.lastOrNull { it is ChatItem.Assistant } as? ChatItem.Assistant)?.text.orEmpty()
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxSize().systemBarsPadding().padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.DirectionsCar, null, Modifier.size(28.dp))
                Spacer(Modifier.size(8.dp))
                Text("Driving mode", style = MaterialTheme.typography.titleLarge)
            }
            Text(label, style = MaterialTheme.typography.displaySmall, color = color)
            if (vm.driveHeard.isNotBlank()) Text("“${vm.driveHeard}”", style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 3, overflow = TextOverflow.Ellipsis)
            Text(com.localai.bridge.data.Speaker.clean(answer).takeLast(600), style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.weight(1f), overflow = TextOverflow.Ellipsis)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("I listen in:", style = MaterialTheme.typography.titleMedium)
                FilterChip(selected = vm.driveLang.startsWith("ar"), onClick = { vm.updateDriveLang("ar-EG") },
                    label = { Text("العربية", style = MaterialTheme.typography.titleMedium) })
                FilterChip(selected = vm.driveLang.startsWith("en"), onClick = { vm.updateDriveLang("en-US") },
                    label = { Text("English", style = MaterialTheme.typography.titleMedium) })
            }
            Text("After the beep, ask. Say \"new chat\" or \"stop\".  بعد الصفارة اسأل. قل \"محادثة جديدة\" أو \"توقف\"",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = { vm.newChat(); vm.speaker.speak("New chat") }, Modifier.weight(1f).height(72.dp)) {
                    Text("New chat", style = MaterialTheme.typography.titleMedium) }
                if (vm.speaking) OutlinedButton(onClick = { vm.speaker.stop() }, Modifier.weight(1f).height(72.dp)) {
                    Text("Skip reading", style = MaterialTheme.typography.titleMedium) }
            }
            Button(onClick = { vm.stopDriving() }, Modifier.fillMaxWidth().height(96.dp),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
                Text("STOP", style = MaterialTheme.typography.headlineMedium)
            }
        }
    }
}
