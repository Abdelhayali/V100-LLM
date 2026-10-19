package com.localai.bridge.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.localai.bridge.data.BenchState
import com.localai.bridge.data.benchStart
import com.localai.bridge.data.benchState
import com.localai.bridge.data.benchStop
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val BENCH_CATS = listOf("coding" to "Coding", "reasoning" to "Reasoning", "ifeval" to "Instructions",
    "search" to "Web search", "agent" to "Agent", "vision" to "Vision", "longctx" to "Long context")

/** Speed test + any categories of the V100-LLM hard suite, on the model that is loaded (it stays loaded). */
@Composable
fun BenchCard(vm: MainViewModel, modelReady: Boolean) {
    val scope = rememberCoroutineScope()
    var st by remember { mutableStateOf<BenchState?>(null) }
    var speed by remember { mutableStateOf(true) }
    val cats = remember { mutableStateListOf("coding") }
    LaunchedEffect(Unit) {
        while (true) {
            runCatching { vm.api?.benchState() }.getOrNull()?.let { st = it }
            delay(if (st?.running == true) 3_000 else 15_000)
        }
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Benchmark the loaded model", style = MaterialTheme.typography.titleSmall)
            val s = st
            if (s?.running == true) {
                Text("Running on ${s.modelName.ifBlank { s.model }} · ${s.elapsed / 60} min ${s.elapsed % 60} s",
                    style = MaterialTheme.typography.bodySmall)
                LinearProgressIndicator(Modifier.fillMaxWidth())
                OutlinedButton(onClick = { scope.launch { runCatching { vm.api?.benchStop() } } }) { Text("Stop") }
            } else {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    FilterChip(selected = speed, onClick = { speed = !speed }, label = { Text("Speed") })
                    BENCH_CATS.forEach { (id, label) ->
                        FilterChip(selected = id in cats, onClick = { if (id in cats) cats.remove(id) else cats.add(id) },
                            label = { Text(label) })
                    }
                }
                Text("Speed ~30 s. Coding and reasoning ~2 min each, the rest under a minute. Replies in chats are " +
                    "slower while it runs. Results stay on the PC (eval/results_phone), not on the public leaderboard.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button(enabled = modelReady && (speed || cats.isNotEmpty()), onClick = {
                    scope.launch {
                        try { vm.api?.benchStart(cats.toList(), speed); vm.toast = "Benchmark started"; delay(1000)
                              st = vm.api?.benchState() }
                        catch (e: Exception) { vm.toast = e.message }
                    }
                }) { Text(if (modelReady) "Run benchmark" else "Load a model first") }
            }
            if (s != null && (s.speed.isNotEmpty() || s.scores.isNotEmpty())) {
                s.speed["mean"]?.let { Text("Speed: %.1f tok/s (code %.1f, chat %.1f)".format(it, s.speed["code"] ?: 0.0, s.speed["chat"] ?: 0.0),
                    fontWeight = FontWeight.SemiBold) }
                s.scores.filterKeys { it != "mean" }.forEach { (k, v) ->
                    Text("${BENCH_CATS.firstOrNull { it.first == k }?.second ?: k}: %.1f".format(v)) }
                s.scores["mean"]?.let { Text("Mean: %.1f".format(it), fontWeight = FontWeight.SemiBold) }
            }
            if (s != null && s.error.isNotBlank()) Text(s.error, color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall)
            if (s != null && s.running && s.log.isNotEmpty()) Text(s.log.takeLast(5).joinToString("\n"),
                style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
