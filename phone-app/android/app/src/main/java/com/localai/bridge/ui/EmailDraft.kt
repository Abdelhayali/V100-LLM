package com.localai.bridge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.saveDraft
import kotlinx.coroutines.launch

/** The email a chat is about ("...the email with id=1a2b..."), so a reply draft lands in the same Gmail thread. */
fun emailIdOfChat(items: List<ChatItem>): String =
    items.filterIsInstance<ChatItem.User>().firstNotNullOfOrNull {
        Regex("""email with id=([0-9a-fA-F]{8,})""").find(it.text)?.groupValues?.get(1)
    }.orEmpty()

/** Show the "Save as Gmail draft" action on a reply? Yes in email chats, or when the reply looks like an email. */
fun looksLikeEmail(text: String, emailId: String) =
    emailId.isNotBlank() || Regex("""(?im)^\s*\**subject\**\s*:""").containsMatchIn(text)

private data class DraftParts(val to: String, val subject: String, val body: String)

/** Pull To / Subject lines and the "Here is your draft:" preamble out of the AI's reply; the rest is the email. */
private fun splitDraft(text: String): DraftParts {
    var to = ""; var subject = ""
    val lines = Speaker.clean(text).lines().toMutableList()
    val keep = mutableListOf<String>()
    for (l in lines) {
        val m = Regex("""^\s*(to|subject)\s*:\s*(.*)$""", RegexOption.IGNORE_CASE).find(l)
        when {
            m != null && m.groupValues[1].equals("to", true) && to.isEmpty() -> to = m.groupValues[2].trim()
            m != null && m.groupValues[1].equals("subject", true) && subject.isEmpty() -> subject = m.groupValues[2].trim()
            else -> keep += l
        }
    }
    while (keep.isNotEmpty() && keep.first().isBlank()) keep.removeAt(0)
    // "Here's a draft reply:" / "Draft:" before the email itself
    if (keep.size > 2 && keep.first().trim().endsWith(":") && keep.first().length < 120) keep.removeAt(0)
    // trailing offer like "Would you like me to send it?"
    while (keep.isNotEmpty() && (keep.last().isBlank() || (keep.last().trim().endsWith("?") && keep.last().contains(Regex("(?i)send|change|edit|like me"))))) keep.removeAt(keep.lastIndex)
    return DraftParts(to, subject, keep.joinToString("\n").trim())
}

private typealias Speaker = com.localai.bridge.data.Speaker

/** Edit and save the AI's reply as a Gmail draft (a reply in the same thread when the chat is about an email). */
@Composable
fun SaveDraftDialog(vm: MainViewModel, text: String, emailId: String, onClose: () -> Unit) {
    val scope = rememberCoroutineScope()
    val parts = remember(text) { splitDraft(text) }
    var to by remember { mutableStateOf(parts.to) }
    var subject by remember { mutableStateOf(parts.subject) }
    var body by remember { mutableStateOf(parts.body) }
    var busy by remember { mutableStateOf(false) }
    AlertDialog(onDismissRequest = onClose, title = { Text("Save as Gmail draft") },
        text = {
            Column(Modifier.heightIn(max = 460.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (emailId.isNotBlank()) Text("Saved as a reply in the same email thread. Leave To and Subject empty to reply to the sender.",
                    style = MaterialTheme.typography.labelSmall)
                OutlinedTextField(to, { to = it }, label = { Text(if (emailId.isNotBlank()) "To (optional)" else "To") },
                    singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(subject, { subject = it }, label = { Text("Subject") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(body, { body = it }, label = { Text("Email text") }, modifier = Modifier.fillMaxWidth().heightIn(min = 160.dp))
                Text("It is only saved in Gmail Drafts, not sent. Send it from Gmail when you are ready.",
                    style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = { TextButton(enabled = !busy && body.isNotBlank() && (emailId.isNotBlank() || to.isNotBlank()), onClick = {
            busy = true
            scope.launch {
                runCatching { vm.api?.saveDraft(body, to, subject, emailId) }
                    .onSuccess { vm.toast = "Saved in Gmail Drafts"; onClose() }
                    .onFailure { vm.toast = it.message; busy = false }
            }
        }) { Text(if (busy) "Saving…" else "Save draft") } },
        dismissButton = { TextButton(onClick = onClose) { Text("Cancel") } })
}
