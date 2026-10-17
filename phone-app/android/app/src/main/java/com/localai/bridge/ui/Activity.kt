package com.localai.bridge.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.HourglassEmpty
import androidx.compose.material.icons.filled.RadioButtonUnchecked
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** One row of the step list. state: pending | now | waiting | done | failed */
private data class Step(val title: String, val detail: String, val state: String)

private fun arg(a: JsonObject, k: String) = (a[k] as? JsonPrimitive)?.contentOrNull.orEmpty()

/** What exactly a tool call does, in one or two short lines (the first lines of code, the file, the query...). */
private fun toolDetail(name: String, a: JsonObject): String = when (name) {
    "run_code" -> arg(a, "code").lines().map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith("#") }.take(2).joinToString("  ⏎  ")
    "write_file" -> "${arg(a, "content").lines().size} lines"
    "ask_user" -> (a["options"]?.toString() ?: "").removePrefix("[").removeSuffix("]").replace("\"", "").replace(",", " · ")
    else -> ""
}

private fun stepsFromTools(tools: List<ChatItem.Tool>): List<Step> = tools
    .filter { it.name != "update_tasks" }
    .map { t ->
        val failed = t.status == "done" && (t.output.orEmpty().startsWith("The user denied") ||
            t.output.orEmpty().startsWith("The user did not answer") || t.output.orEmpty().startsWith("Error"))
        Step(toolSummary(t.name, t.args), toolDetail(t.name, t.args), when {
            t.status == "running" -> "now"
            t.status == "awaiting" -> "waiting"
            failed -> "failed"
            else -> "done"
        })
    }

/**
 * "What your PC is doing": the model's own plan when it sends one (update_tasks), otherwise every action it takes in
 * this reply (run code, read / write files, search, ask you...) with a live status. Expanded while the reply runs.
 */
@Composable
fun ActivityCard(vm: MainViewModel) {
    val lastUser = vm.items.indexOfLast { it is ChatItem.User }
    val tools = vm.items.drop(lastUser + 1).filterIsInstance<ChatItem.Tool>()
    val fromPlan = vm.plan.isNotEmpty()
    val steps = if (fromPlan) vm.plan.map {
        Step(it.title, "", when (it.status) { "in_progress" -> if (vm.streaming) "now" else "done"; "done" -> "done"; else -> "pending" })
    } else stepsFromTools(tools)
    if (steps.isEmpty()) return
    var open by remember(lastUser) { mutableStateOf<Boolean?>(null) }
    val expanded = open ?: vm.streaming                     // open while working, folded when finished
    val done = steps.count { it.state == "done" }
    Surface(color = MaterialTheme.colorScheme.surfaceContainer, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
            Row(Modifier.fillMaxWidth().clickable { open = !expanded }, verticalAlignment = Alignment.CenterVertically) {
                Text(if (fromPlan) "Plan" else "What your PC is doing", style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.weight(1f))
                Text(if (fromPlan) "$done/${steps.size} done" else "${steps.size} step(s)",
                    style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore, if (expanded) "Fold" else "Show steps")
            }
            if (expanded) Column(
                Modifier.heightIn(max = 220.dp).verticalScroll(rememberScrollState()).padding(top = 2.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                steps.forEachIndexed { i, s -> StepRow(i + 1, s) }
            }
        }
    }
}

@Composable
private fun StepRow(n: Int, s: Step) {
    Row(verticalAlignment = Alignment.Top) {
        val ok = Color(0xFF2E9D57)
        when (s.state) {
            "now" -> CircularProgressIndicator(Modifier.size(16.dp).padding(1.dp), strokeWidth = 2.dp)
            "waiting" -> Icon(Icons.Default.HourglassEmpty, "waiting for you", Modifier.size(16.dp), tint = MaterialTheme.colorScheme.tertiary)
            "done" -> Icon(Icons.Default.CheckCircle, "done", Modifier.size(16.dp), tint = ok)
            "failed" -> Icon(Icons.Default.Close, "not done", Modifier.size(16.dp), tint = MaterialTheme.colorScheme.error)
            else -> Icon(Icons.Default.RadioButtonUnchecked, "to do", Modifier.size(16.dp), tint = MaterialTheme.colorScheme.outline)
        }
        androidx.compose.foundation.layout.Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f)) {
            Text("$n. ${s.title}" + when (s.state) { "now" -> "  (now)"; "waiting" -> "  (waiting for you)"; else -> "" },
                style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis,
                color = if (s.state == "pending") MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
            if (s.detail.isNotBlank()) Text(s.detail, style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace,
                maxLines = 2, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
