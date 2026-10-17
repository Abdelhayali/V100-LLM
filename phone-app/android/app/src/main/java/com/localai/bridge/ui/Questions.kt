package com.localai.bridge.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.PendingQuestion

/** The model asked the user to choose (ask_user tool): the reply waits on the PC until one of these is tapped. */
@Composable
fun QuestionCard(q: PendingQuestion, vm: MainViewModel) {
    var other by remember(q.id) { mutableStateOf("") }
    val picked = remember(q.id) { mutableStateListOf<String>() }
    Surface(color = MaterialTheme.colorScheme.secondaryContainer, modifier = Modifier.fillMaxWidth()) {
        Column(
            Modifier.heightIn(max = 380.dp).verticalScroll(rememberScrollState()).padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.HelpOutline, null)
                Text("  " + q.question, style = MaterialTheme.typography.titleSmall)
            }
            Text(if (q.multiple) "Pick one or more, then Send. The reply continues on your PC."
                 else "Tap your choice. The reply continues on your PC.",
                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            q.options.forEachIndexed { i, opt ->
                if (q.multiple) {
                    Row(Modifier.fillMaxWidth().clickable { if (opt in picked) picked.remove(opt) else picked.add(opt) },
                        verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = opt in picked, onCheckedChange = { if (it) picked.add(opt) else picked.remove(opt) })
                        Text(opt, style = MaterialTheme.typography.bodyMedium)
                    }
                } else {
                    OutlinedButton(onClick = { vm.answerQuestion(q, opt) }, modifier = Modifier.fillMaxWidth()) {
                        Text("${i + 1}. $opt", modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            if (q.multiple) Button(onClick = { vm.answerQuestion(q, picked.joinToString("; ")) }, enabled = picked.isNotEmpty(),
                modifier = Modifier.fillMaxWidth()) { Text("Send ${picked.size} choice(s)") }
            if (q.allowOther) Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(other, { other = it }, placeholder = { Text("Or type your own answer…") },
                    singleLine = true, modifier = Modifier.weight(1f))
                IconButton(onClick = { vm.answerQuestion(q, other) }, enabled = other.isNotBlank()) {
                    Icon(Icons.AutoMirrored.Filled.Send, "Send answer")
                }
            }
        }
    }
}

private val optionLine = Regex("""^\s*(?:\(?(\d{1,2}|[A-Fa-f])[.):]|[-*•])\s+(.{1,160})$""")
private val askWords = Regex("""\?|\b(choose|select|pick|which|prefer|option|would you like|let me know)\b""", RegexOption.IGNORE_CASE)

/**
 * Options the model listed in plain text at the end of its reply ("1. ...", "A) ...", "- ..."), when the reply asks
 * the user to choose. Returns 2-6 short labels, or nothing.
 */
fun suggestedReplies(text: String): List<String> {
    val lines = text.trimEnd().lines().takeLast(14)
    if (lines.isEmpty() || !askWords.containsMatchIn(lines.joinToString("\n"))) return emptyList()
    // the last block of consecutive option lines (allowing blank lines and a closing question after it)
    val opts = mutableListOf<String>()
    var started = false
    for (l in lines.asReversed()) {
        val m = optionLine.matchEntire(l)
        if (m != null) { opts += m.groupValues[2]; started = true }
        else if (started && l.isNotBlank()) break
        else if (!started && l.isNotBlank() && opts.isEmpty() && !askWords.containsMatchIn(l)) return emptyList()
    }
    val clean = opts.asReversed().map {
        it.replace(Regex("""\*\*|__|`"""), "").substringBefore(" - ").substringBefore(": ").trim().trimEnd('.', ',', ';')
    }.filter { it.isNotBlank() && it.length <= 80 }.distinct()
    return if (clean.size in 2..6) clean else emptyList()
}

/** Tap-to-answer chips under the last reply when it ends with a list of options. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun QuickReplies(options: List<String>, vm: MainViewModel) {
    if (options.isEmpty()) return
    FlowRow(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        options.forEach { o ->
            SuggestionChip(onClick = { vm.quickReply(o) },
                label = { Text(o, maxLines = 2, overflow = TextOverflow.Ellipsis) })
        }
    }
}
