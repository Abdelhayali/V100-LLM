package com.localai.bridge.ui

import androidx.compose.foundation.clickable
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.TimePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DatePicker
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.EventDto
import com.localai.bridge.data.GoogleStatus
import com.localai.bridge.data.MailDto
import com.localai.bridge.data.MailFull
import com.localai.bridge.data.NoteDto
import com.localai.bridge.data.TaskDto
import com.localai.bridge.data.addEvent
import com.localai.bridge.data.addTask
import com.localai.bridge.data.deleteOrganizer
import com.localai.bridge.data.events
import com.localai.bridge.data.googleClient
import com.localai.bridge.data.googleConnect
import com.localai.bridge.data.googleDisconnect
import com.localai.bridge.data.googleStatus
import com.localai.bridge.data.mail
import com.localai.bridge.data.mailOne
import com.localai.bridge.data.sendDraft
import com.localai.bridge.data.updateDraft
import com.localai.bridge.data.draftOf
import com.localai.bridge.data.notes
import com.localai.bridge.data.organizerTasks
import com.localai.bridge.data.saveNote
import com.localai.bridge.data.setTaskDone
import kotlinx.coroutines.launch
import kotlinx.serialization.json.jsonPrimitive

/** Ask the model in a NEW chat (so it does not mix with the conversation that was open), and send at once. */
private fun askAi(vm: MainViewModel, text: String) {
    vm.newChat(); vm.draft = text; vm.send()
}

/** Notes, tasks, calendar and Gmail, kept on the PC and shared with the model (it can read and change them too). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrganizerScreen(vm: MainViewModel, openDrawer: () -> Unit) {
    var tab by remember { mutableIntStateOf(0) }
    var reload by remember { mutableIntStateOf(0) }
    Scaffold(topBar = {
        TopAppBar(
            title = { Text("Notes, tasks & calendar") },
            navigationIcon = { IconButton(onClick = openDrawer) { Icon(Icons.Default.Menu, "Menu") } },
            actions = { IconButton(onClick = { reload++ }) { Icon(Icons.Default.Refresh, "Reload") } },
        )
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            TabRow(selectedTabIndex = tab) {
                listOf("Tasks", "Notes", "Calendar", "Email").forEachIndexed { i, t ->
                    Tab(selected = tab == i, onClick = { tab = i }, text = { Text(t) })
                }
            }
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)) {
                when (tab) {
                    0 -> TasksTab(vm, reload)
                    1 -> NotesTab(vm, reload)
                    2 -> CalendarTab(vm, reload)
                    else -> EmailTab(vm, reload)
                }
            }
        }
    }
}

// ---------------------------------------------------------------- tasks
@Composable
private fun TasksTab(vm: MainViewModel, reload: Int) {
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<List<TaskDto>?>(null) }
    var showDone by remember { mutableStateOf(false) }
    var title by remember { mutableStateOf("") }
    var due by remember { mutableStateOf("") }
    var desc by remember { mutableStateOf("") }
    var high by remember { mutableStateOf(false) }
    fun load() = scope.launch { list = runCatching { vm.api?.organizerTasks("all") }.onFailure { vm.toast = it.message }.getOrNull() }
    LaunchedEffect(reload) { load() }

    OutlinedButton(onClick = { askAi(vm, "What tasks do I have? Sort them by due date and tell me what is most urgent.") }) {
        Text("Ask the AI: what tasks do I have?")
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            OutlinedTextField(title, { title = it }, label = { Text("New task") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(desc, { desc = it }, label = { Text("Description (optional)") }, modifier = Modifier.fillMaxWidth(),
                minLines = 1, maxLines = 4)
            Row(verticalAlignment = Alignment.CenterVertically) {
                DateTimeField("Due (optional)", due, { due = it }, modifier = Modifier.weight(1f))
                Spacer(Modifier.width(6.dp))
                FilterChip(selected = high, onClick = { high = !high }, label = { Text("High") })
            }
            Button(onClick = {
                scope.launch {
                    runCatching { vm.api?.addTask(title.trim(), due.trim(), if (high) "high" else "normal", desc.trim()) }
                        .onSuccess { title = ""; due = ""; desc = ""; high = false; load() }.onFailure { vm.toast = it.message }
                }
            }, enabled = title.isNotBlank()) { Icon(Icons.Default.Add, null); Text(" Add task") }
        }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Tasks", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
        FilterChip(selected = showDone, onClick = { showDone = !showDone }, label = { Text("Show done") })
    }
    val l = list ?: run { CircularProgressIndicator(); return }
    val shown = l.filter { showDone || !it.done }
    if (shown.isEmpty()) Text("No tasks. Add one above, or tell the AI \"remind me to …\".", style = MaterialTheme.typography.bodySmall)
    shown.forEach { t ->
        Card(Modifier.fillMaxWidth()) {
            Row(Modifier.padding(start = 4.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = t.done, onCheckedChange = { d ->
                    scope.launch { runCatching { vm.api?.setTaskDone(t.id, d) }.onFailure { vm.toast = it.message }; load() }
                })
                Column(Modifier.weight(1f).padding(vertical = 8.dp)) {
                    Text(t.title.orEmpty(), style = MaterialTheme.typography.bodyMedium,
                        textDecoration = if (t.done) TextDecoration.LineThrough else null,
                        fontWeight = if (t.priority == "high" && !t.done) FontWeight.SemiBold else null)
                    val meta = listOfNotNull(t.due?.takeIf { it.isNotBlank() }?.let { "due $it" },
                        t.priority?.takeIf { it != "normal" && it.isNotBlank() }, t.notes?.takeIf { it.isNotBlank() })
                    if (meta.isNotEmpty()) Text(meta.joinToString(" · "), style = MaterialTheme.typography.labelSmall,
                        color = if (t.priority == "high" && !t.done) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = { scope.launch { runCatching { vm.api?.deleteOrganizer("tasks", t.id.toString()) }; load() } }) {
                    Icon(Icons.Default.Delete, "Delete", Modifier.size(18.dp))
                }
            }
        }
    }
}

// ---------------------------------------------------------------- notes
@Composable
private fun NotesTab(vm: MainViewModel, reload: Int) {
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<List<NoteDto>?>(null) }
    var q by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf<NoteDto?>(null) }      // id 0 = new note
    fun load() = scope.launch { list = runCatching { vm.api?.notes(q) }.onFailure { vm.toast = it.message }.getOrNull() }
    LaunchedEffect(reload) { load() }

    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(q, { q = it; load() }, label = { Text("Search notes") }, singleLine = true, modifier = Modifier.weight(1f))
        Spacer(Modifier.width(6.dp))
        Button(onClick = { editing = NoteDto(0) }) { Icon(Icons.Default.Add, "New note") }
    }
    val l = list ?: run { CircularProgressIndicator(); return }
    if (l.isEmpty()) Text("No notes yet. Add one, or tell the AI \"save a note …\".", style = MaterialTheme.typography.bodySmall)
    l.forEach { n ->
        Card(Modifier.fillMaxWidth().clickable { editing = n }) {
            Row(Modifier.padding(10.dp), verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f)) {
                    Text(n.title.orEmpty(), style = MaterialTheme.typography.titleSmall)
                    if (!n.body.isNullOrBlank()) Text(n.body, style = MaterialTheme.typography.bodySmall, maxLines = 4,
                        overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = { scope.launch { runCatching { vm.api?.deleteOrganizer("notes", n.id.toString()) }; load() } }) {
                    Icon(Icons.Default.Delete, "Delete", Modifier.size(18.dp))
                }
            }
        }
    }
    editing?.let { n ->
        var t by remember(n.id) { mutableStateOf(n.title.orEmpty()) }
        var b by remember(n.id) { mutableStateOf(n.body.orEmpty()) }
        AlertDialog(onDismissRequest = { editing = null }, title = { Text(if (n.id == 0L) "New note" else "Edit note") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(t, { t = it }, label = { Text("Title") }, singleLine = true)
                    OutlinedTextField(b, { b = it }, label = { Text("Text") }, modifier = Modifier.heightIn(min = 140.dp))
                }
            },
            confirmButton = { TextButton(onClick = {
                scope.launch {
                    runCatching { vm.api?.saveNote(t.ifBlank { "Note" }, b, n.id.takeIf { it != 0L }) }.onFailure { vm.toast = it.message }
                    editing = null; load()
                }
            }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { editing = null }) { Text("Cancel") } })
    }
}

// ---------------------------------------------------------------- calendar
@Composable
private fun CalendarTab(vm: MainViewModel, reload: Int) {
    val scope = rememberCoroutineScope()
    var list by remember { mutableStateOf<List<EventDto>?>(null) }
    var adding by remember { mutableStateOf(false) }
    fun load() = scope.launch { list = runCatching { vm.api?.events() }.onFailure { vm.toast = it.message }.getOrNull() }
    LaunchedEffect(reload) { load() }

    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { adding = true }) { Icon(Icons.Default.Add, null); Text(" Add event") }
        OutlinedButton(onClick = { askAi(vm, "What do I have on my calendar this week?") }) { Text("Ask the AI") }
    }
    Text("Next 30 days: your calendar on the PC, plus Google Calendar when connected (Email tab).",
        style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    val l = list ?: run { CircularProgressIndicator(); return }
    if (l.isEmpty()) Text("Nothing planned.", style = MaterialTheme.typography.bodySmall)
    l.groupBy { (it.start ?: "").take(10) }.forEach { (day, evs) ->
        Text(day.ifBlank { "No date" }, style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 4.dp))
        evs.forEach { e ->
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        val time = (e.start ?: "").drop(11).take(5)
                        Text((if (time.isNotBlank()) "$time  " else "") + e.title.orEmpty(), style = MaterialTheme.typography.bodyMedium)
                        val meta = listOfNotNull(e.location?.takeIf { it.isNotBlank() }, if (e.source == "google") "Google" else null)
                        if (meta.isNotEmpty()) Text(meta.joinToString(" · "), style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (e.source == "local") IconButton(onClick = {
                        scope.launch { runCatching { vm.api?.deleteOrganizer("events", e.idText) }; load() }
                    }) { Icon(Icons.Default.Delete, "Delete", Modifier.size(18.dp)) }
                }
            }
        }
    }
    if (adding) {
        var t by remember { mutableStateOf("") }
        var start by remember { mutableStateOf(java.time.LocalDate.now().toString() + " 09:00") }
        var end by remember { mutableStateOf("") }
        var loc by remember { mutableStateOf("") }
        AlertDialog(onDismissRequest = { adding = false }, title = { Text("New event") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(t, { t = it }, label = { Text("Title") }, singleLine = true)
                    DateTimeField("Starts (No time = all day)", start, { start = it })
                    DateTimeField("Ends (optional)", end, { end = it })
                    OutlinedTextField(loc, { loc = it }, label = { Text("Location (optional)") }, singleLine = true)
                }
            },
            confirmButton = { TextButton(onClick = {
                scope.launch {
                    runCatching { vm.api?.addEvent(t.ifBlank { "Event" }, start.trim(), end.trim(), loc.trim()) }
                        .onSuccess { adding = false; load() }.onFailure { vm.toast = it.message }
                }
            }, enabled = t.isNotBlank() && start.isNotBlank()) { Text("Add") } },
            dismissButton = { TextButton(onClick = { adding = false }) { Text("Cancel") } })
    }
}

// ---------------------------------------------------------------- email (Gmail) + Google setup
/** Loaded mail per folder/search, kept while the app runs: reopening the tab shows it at once, then refreshes. */
private object MailCache {
    val pages = mutableMapOf<String, Pair<List<MailDto>, String>>()   // query -> (messages, next page token)
    val full = mutableMapOf<String, MailFull>()
}

@Composable
private fun EmailTab(vm: MainViewModel, reload: Int) {
    val scope = rememberCoroutineScope()
    var st by remember { mutableStateOf<GoogleStatus?>(null) }
    var q by remember { mutableStateOf("in:inbox") }
    var search by remember { mutableStateOf("") }
    var mails by remember { mutableStateOf(MailCache.pages[q]?.first) }
    var next by remember { mutableStateOf(MailCache.pages[q]?.second ?: "") }
    var loading by remember { mutableStateOf(false) }
    var open by remember { mutableStateOf<MailFull?>(null) }

    fun loadMail(more: Boolean = false) = scope.launch {
        if (loading) return@launch
        loading = true
        val query = q
        runCatching { vm.api?.mail(query, if (more) next else "") }.onSuccess { p ->
            if (p != null && query == q) {
                val list = if (more) (mails.orEmpty() + p.messages).distinctBy { it.id } else p.messages
                mails = list; next = p.next
                MailCache.pages[query] = list to p.next
            }
        }.onFailure { vm.toast = it.message }
        loading = false
    }
    fun show(query: String) {
        q = query; mails = MailCache.pages[query]?.first; next = MailCache.pages[query]?.second ?: ""
        loadMail()
    }
    LaunchedEffect(reload) {
        st = runCatching { vm.api?.googleStatus() }.onFailure { vm.toast = it.message }.getOrNull()
        if (st?.connected == true) loadMail()
    }
    val s = st ?: run { if (mails == null) CircularProgressIndicator(); null }
    if (s != null && !s.connected) {
        GoogleSetup(vm, s, onChange = { st = it }, onRecheck = { scope.launch { st = runCatching { vm.api?.googleStatus() }.getOrNull() ?: st } })
        return
    }

    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Gmail" + (s?.email?.let { ": $it" } ?: ""), style = MaterialTheme.typography.labelLarge, modifier = Modifier.weight(1f))
        if (s != null) TextButton(onClick = { scope.launch { st = runCatching { vm.api?.googleDisconnect() }.getOrNull() ?: st } }) { Text("Disconnect") }
    }
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        listOf("in:inbox" to "Inbox", "is:unread" to "Unread", "in:sent" to "Sent", "in:drafts" to "Drafts",
            "is:starred" to "Starred", "-in:spam -in:trash" to "All mail").forEach { (k, label) ->
            FilterChip(selected = q == k, onClick = { search = ""; show(k) }, label = { Text(label) })
        }
    }
    OutlinedTextField(search, { search = it }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        label = { Text("Search mail (e.g. from:sara invoice)") },
        trailingIcon = { IconButton(onClick = { if (search.isNotBlank()) show(search.trim()) }) { Icon(Icons.Default.Search, "Search") } },
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
        keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { if (search.isNotBlank()) show(search.trim()) }))
    OutlinedButton(onClick = { askAi(vm, "Check my unread emails and summarize what needs a reply.") }) {
        Text("Ask the AI to summarize my unread email")
    }
    if (loading) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
    val m = mails ?: return
    if (m.isEmpty() && !loading) Text("No emails here.", style = MaterialTheme.typography.bodySmall)
    val sent = q == "in:sent" || q == "in:drafts"
    m.forEach { e ->
        Card(Modifier.fillMaxWidth().clickable {
            MailCache.full[e.id]?.let { open = it } ?: scope.launch {
                runCatching { vm.api?.mailOne(e.id) }.onSuccess { it?.let { f -> MailCache.full[e.id] = f; open = f } }.onFailure { vm.toast = it.message }
            }
        }) {
            Column(Modifier.padding(10.dp)) {
                Row {
                    val who = if (sent) "To: " + e.to.substringBefore('<').trim().ifBlank { e.to } else e.from.substringBefore('<').trim().ifBlank { e.from }
                    Text(who, style = MaterialTheme.typography.labelMedium, fontWeight = if (e.unread) FontWeight.Bold else null,
                        maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    Text(shortDate(e.date), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(e.subject.ifBlank { "(no subject)" }, style = MaterialTheme.typography.bodyMedium,
                    fontWeight = if (e.unread) FontWeight.Bold else null, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(e.snippet, style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    if (next.isNotBlank()) OutlinedButton(onClick = { loadMail(more = true) }, enabled = !loading, modifier = Modifier.fillMaxWidth()) {
        Text(if (loading) "Loading…" else "Load more (${m.size} shown)")
    } else if (m.isNotEmpty()) Text("${m.size} email(s), that's all.", style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant)

    open?.takeIf { q == "in:drafts" }?.let { mf ->
        DraftDialog(vm, mf, onClose = { open = null }, onChanged = {
            MailCache.full.remove(mf.id); MailCache.pages.remove("in:drafts"); MailCache.pages.remove("in:sent"); loadMail()
        })
    }
    open?.takeIf { q != "in:drafts" }?.let { mf ->
        AlertDialog(onDismissRequest = { open = null }, title = { Text(mf.subject, maxLines = 2, overflow = TextOverflow.Ellipsis) },
            text = {
                Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                    Text("From: ${mf.from}\nTo: ${mf.to}\n${mf.date}", style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.size(8.dp))
                    SelectionContainer { Text(mf.body, style = MaterialTheme.typography.bodySmall) }
                }
            },
            confirmButton = {
                Column(horizontalAlignment = Alignment.End) {
                    TextButton(onClick = {
                        open = null
                        askAi(vm, "Read the email with id=${mf.id} (\"${mf.subject}\") and explain it to me simply: who sent it, " +
                            "what they want or tell me, any dates, deadlines or amounts, and whether I need to do or reply anything.")
                    }) { Text("Explain this email") }
                    TextButton(onClick = {
                        open = null
                        askAi(vm, "Read the email with id=${mf.id} (\"${mf.subject}\") and draft a reply for me. Save it as a draft, " +
                            "show it to me, and don't send it until I approve.")
                    }) { Text("Draft a reply with AI") }
                    TextButton(onClick = { open = null }) { Text("Close") }
                }
            })
    }
}

/** "Fri, 17 Oct 2026 14:03:11 +0300" -> "17 Oct 14:03" (or the date only if it is not from today). */
private fun shortDate(d: String): String {
    val m = Regex("""(\d{1,2}) (\w{3}) (\d{4}) (\d{2}):(\d{2})""").find(d) ?: return d.take(16)
    val (day, mon, _, hh, mm) = m.destructured
    return "$day $mon $hh:$mm"
}

@Composable
private fun GoogleSetup(vm: MainViewModel, s: GoogleStatus, onChange: (GoogleStatus) -> Unit, onRecheck: () -> Unit) {
    val scope = rememberCoroutineScope()
    var cid by remember { mutableStateOf("") }
    var secret by remember { mutableStateOf("") }
    var waiting by remember { mutableStateOf(false) }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Connect Google (Gmail + Calendar)", style = MaterialTheme.typography.titleSmall)
            Text("The AI can then read your email, write draft replies, list and add Google Calendar events. " +
                "Sending an email or adding a Google event always asks you first. Your login stays on your PC.",
                style = MaterialTheme.typography.bodySmall)
            if (!s.configured) {
                Text("One-time setup (5 minutes, free):\n" +
                    "1. On a computer open console.cloud.google.com and create a project.\n" +
                    "2. APIs & Services → Library: enable \"Gmail API\" and \"Google Calendar API\".\n" +
                    "3. OAuth consent screen: External, add your own Gmail address as a test user.\n" +
                    "4. Credentials → Create credentials → OAuth client ID → type \"Desktop app\".\n" +
                    "5. Copy the client ID and client secret here:", style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(cid, { cid = it }, label = { Text("Client ID (…apps.googleusercontent.com)") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                OutlinedTextField(secret, { secret = it }, label = { Text("Client secret") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Button(onClick = {
                    scope.launch { runCatching { vm.api?.googleClient(cid, secret) }.onSuccess { it?.let(onChange) }.onFailure { vm.toast = it.message } }
                }, enabled = cid.isNotBlank() && secret.isNotBlank()) { Text("Save") }
            } else {
                Text("Tap Connect: Google's sign-in page opens in the browser ON YOUR PC (it has to finish there). " +
                    "Sign in, allow access, then come back and tap \"I signed in\".", style = MaterialTheme.typography.bodySmall)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        scope.launch {
                            runCatching { vm.api?.googleConnect() }.onSuccess { r ->
                                waiting = true
                                vm.toast = if (r?.get("opened_on_pc")?.jsonPrimitive?.content == "true") "Sign-in page opened on your PC"
                                           else "Open the Google sign-in page on your PC (see the server window)"
                            }.onFailure { vm.toast = it.message }
                        }
                    }) { Text("Connect") }
                    if (waiting) OutlinedButton(onClick = onRecheck) { Text("I signed in") }
                }
                AssistChip(onClick = {}, label = { Text("Redirect: ${s.redirectUri}", style = MaterialTheme.typography.labelSmall) })
            }
        }
    }
}

// ---------------------------------------------------------------- date + time pickers
/**
 * A date (and optionally time) field: tapping it opens a small calendar, then a clock. Value: "YYYY-MM-DD" or
 * "YYYY-MM-DD HH:MM" (what the PC server stores). timeOptional adds a "No time" button on the clock.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DateTimeField(label: String, value: String, onValue: (String) -> Unit, withTime: Boolean = true,
                          timeOptional: Boolean = true, modifier: Modifier = Modifier) {
    var pickDate by remember { mutableStateOf(false) }
    var pickTime by remember { mutableStateOf<String?>(null) }      // the chosen date while the clock is open
    Box(modifier) {
        OutlinedTextField(value, {}, readOnly = true, singleLine = true, label = { Text(label) }, modifier = Modifier.fillMaxWidth(),
            trailingIcon = {
                if (value.isNotBlank()) IconButton(onClick = { onValue("") }) { Icon(Icons.Default.Close, "Clear") }
                else Icon(Icons.Default.CalendarMonth, null)
            })
        // the read-only field swallows taps, so a transparent layer on top opens the calendar
        Box(Modifier.matchParentSize().padding(end = 48.dp).clickable { pickDate = true })
    }
    if (pickDate) {
        val initial = runCatching {
            java.time.LocalDate.parse(value.take(10)).atStartOfDay(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
        }.getOrNull() ?: System.currentTimeMillis()
        val state = rememberDatePickerState(initialSelectedDateMillis = initial)
        DatePickerDialog(onDismissRequest = { pickDate = false },
            confirmButton = { TextButton(onClick = {
                pickDate = false
                state.selectedDateMillis?.let { ms ->
                    val d = java.time.Instant.ofEpochMilli(ms).atZone(java.time.ZoneOffset.UTC).toLocalDate().toString()
                    if (withTime) pickTime = d else onValue(d)
                }
            }) { Text(if (withTime) "Next: time" else "OK") } },
            dismissButton = { TextButton(onClick = { pickDate = false }) { Text("Cancel") } }) {
            DatePicker(state = state)
        }
    }
    pickTime?.let { d ->
        val old = value.drop(11).split(":")
        val state = rememberTimePickerState(initialHour = old.getOrNull(0)?.toIntOrNull() ?: 9,
            initialMinute = old.getOrNull(1)?.toIntOrNull() ?: 0, is24Hour = true)
        AlertDialog(onDismissRequest = { pickTime = null }, title = { Text("Time on $d") },
            text = { TimePicker(state = state) },
            confirmButton = { TextButton(onClick = {
                onValue("%s %02d:%02d".format(d, state.hour, state.minute)); pickTime = null
            }) { Text("OK") } },
            dismissButton = { TextButton(onClick = { if (timeOptional) onValue(d); pickTime = null }) {
                Text(if (timeOptional) "No time" else "Cancel")
            } })
    }
}

// ---------------------------------------------------------------- an opened Gmail draft: edit, ask AI to edit, send
@Composable
private fun DraftDialog(vm: MainViewModel, mf: MailFull, onClose: () -> Unit, onChanged: () -> Unit) {
    val scope = rememberCoroutineScope()
    var draftId by remember(mf.id) { mutableStateOf("") }
    var mode by remember(mf.id) { mutableStateOf("view") }       // view | edit | ask | send
    var to by remember(mf.id) { mutableStateOf(mf.to) }
    var subject by remember(mf.id) { mutableStateOf(mf.subject) }
    var body by remember(mf.id) { mutableStateOf(mf.body) }
    var ask by remember(mf.id) { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    LaunchedEffect(mf.id) {
        runCatching { vm.api?.draftOf(mf.id) }.onSuccess { draftId = it.orEmpty() }.onFailure { vm.toast = it.message }
    }
    fun act(block: suspend () -> Unit) = scope.launch { busy = true; runCatching { block() }.onFailure { vm.toast = it.message }; busy = false }

    when (mode) {
        "edit" -> AlertDialog(onDismissRequest = { mode = "view" }, title = { Text("Edit draft") },
            text = {
                Column(Modifier.heightIn(max = 460.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(to, { to = it }, label = { Text("To") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(subject, { subject = it }, label = { Text("Subject") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(body, { body = it }, label = { Text("Email text") }, modifier = Modifier.fillMaxWidth().heightIn(min = 180.dp))
                }
            },
            confirmButton = { TextButton(enabled = !busy && draftId.isNotBlank() && body.isNotBlank(), onClick = {
                act { vm.api?.updateDraft(draftId, body, subject, to); vm.toast = "Draft saved"; onChanged(); onClose() }
            }) { Text(if (busy) "Saving…" else "Save") } },
            dismissButton = { TextButton(onClick = { mode = "view" }) { Text("Back") } })

        "ask" -> AlertDialog(onDismissRequest = { mode = "view" }, title = { Text("Ask AI to edit") },
            text = {
                OutlinedTextField(ask, { ask = it }, label = { Text("What should change? (e.g. shorter, more formal, add the date)") },
                    modifier = Modifier.fillMaxWidth().heightIn(min = 100.dp))
            },
            confirmButton = { TextButton(enabled = draftId.isNotBlank() && ask.isNotBlank(), onClick = {
                onClose()
                askAi(vm, "Edit my Gmail draft (draft_id=$draftId, message id=${mf.id}, subject \"${mf.subject}\"). " +
                    "Read it with gmail_read id=${mf.id}, then rewrite it: ${ask.trim()}. Save the new version with " +
                    "gmail_update_draft (draft_id=$draftId) and show me the new text. Do not send it.")
            }) { Text("Ask") } },
            dismissButton = { TextButton(onClick = { mode = "view" }) { Text("Back") } })

        "send" -> AlertDialog(onDismissRequest = { mode = "view" }, title = { Text("Send this email?") },
            text = { Text("To: ${to.ifBlank { mf.to }}\nSubject: ${subject.ifBlank { mf.subject }}\n\nIt is sent from your Gmail right away.") },
            confirmButton = { TextButton(enabled = !busy && draftId.isNotBlank(), onClick = {
                act { vm.api?.sendDraft(draftId); vm.toast = "Email sent"; onChanged(); onClose() }
            }) { Text(if (busy) "Sending…" else "Send") } },
            dismissButton = { TextButton(onClick = { mode = "view" }) { Text("Cancel") } })

        else -> AlertDialog(onDismissRequest = onClose, title = { Text("Draft: " + mf.subject.ifBlank { "(no subject)" }, maxLines = 2, overflow = TextOverflow.Ellipsis) },
            text = {
                Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                    Text("To: ${mf.to.ifBlank { "(nobody yet)" }}", style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.size(8.dp))
                    SelectionContainer { Text(mf.body, style = MaterialTheme.typography.bodySmall) }
                    if (draftId.isBlank()) Text("Finding the draft in Gmail…", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            },
            confirmButton = {
                Column(horizontalAlignment = Alignment.End) {
                    TextButton(enabled = draftId.isNotBlank(), onClick = { mode = "edit" }) { Text("Edit") }
                    TextButton(enabled = draftId.isNotBlank(), onClick = { mode = "ask" }) { Text("Ask AI to edit") }
                    TextButton(enabled = draftId.isNotBlank() && mf.to.isNotBlank(), onClick = { mode = "send" }) { Text("Send") }
                    TextButton(onClick = onClose) { Text("Close") }
                }
            })
    }
}
