package com.localai.bridge.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private sealed interface Block {
    data class Text(val text: String) : Block
    data class Code(val lang: String, val code: String) : Block
}

private fun parseBlocks(src: String): List<Block> {
    val out = mutableListOf<Block>()
    val lines = src.lines()
    var i = 0
    val buf = StringBuilder()
    fun flush() { if (buf.isNotBlank()) out += Block.Text(buf.toString().trim('\n')); buf.clear() }
    while (i < lines.size) {
        val l = lines[i]
        if (l.trimStart().startsWith("```")) {
            flush()
            val lang = l.trimStart().removePrefix("```").trim()
            val code = StringBuilder()
            i++
            while (i < lines.size && !lines[i].trimStart().startsWith("```")) { code.appendLine(lines[i]); i++ }
            out += Block.Code(lang, code.toString().trimEnd())
        } else buf.appendLine(l)
        i++
    }
    flush()
    return out
}

/** Split `<think>...</think>` (Qwen/DeepSeek style) out of the visible answer. */
fun splitThink(text: String): Pair<String, String> {
    val start = text.indexOf("<think>")
    if (start < 0) return "" to text
    val end = text.indexOf("</think>", start)
    return if (end < 0) text.substring(start + 7) to text.substring(0, start)
    else text.substring(start + 7, end) to (text.substring(0, start) + text.substring(end + 8))
}

private fun inline(line: String, codeBg: androidx.compose.ui.graphics.Color): AnnotatedString = buildAnnotatedString {
    var i = 0
    while (i < line.length) {
        when {
            line.startsWith("**", i) && line.indexOf("**", i + 2) > i -> {
                val e = line.indexOf("**", i + 2)
                withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(line.substring(i + 2, e)) }
                i = e + 2
            }
            line[i] == '`' && line.indexOf('`', i + 1) > i -> {
                val e = line.indexOf('`', i + 1)
                withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = codeBg)) { append(line.substring(i + 1, e)) }
                i = e + 1
            }
            line[i] == '*' && i + 1 < line.length && line[i + 1] != ' ' && line.indexOf('*', i + 1) > i -> {
                val e = line.indexOf('*', i + 1)
                withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(line.substring(i + 1, e)) }
                i = e + 1
            }
            else -> { append(line[i]); i++ }
        }
    }
}

@Composable
fun MarkdownText(text: String, modifier: Modifier = Modifier) {
    val codeBg = MaterialTheme.colorScheme.surfaceVariant
    Column(modifier) {
        for (b in parseBlocks(text)) when (b) {
            is Block.Code -> CodeBlock(b.code, b.lang)
            is Block.Text -> SelectionContainer {
                Column {
                    for (raw in b.text.lines()) {
                        val l = raw.trimEnd()
                        when {
                            l.startsWith("### ") -> Text(inline(l.drop(4), codeBg), style = MaterialTheme.typography.titleSmall)
                            l.startsWith("## ") -> Text(inline(l.drop(3), codeBg), style = MaterialTheme.typography.titleMedium)
                            l.startsWith("# ") -> Text(inline(l.drop(2), codeBg), style = MaterialTheme.typography.titleLarge)
                            l.trimStart().startsWith("- ") || l.trimStart().startsWith("* ") -> Row {
                                Spacer(Modifier.width((8 + (l.length - l.trimStart().length) * 4).dp))
                                Text("•  ")
                                Text(inline(l.trimStart().drop(2), codeBg))
                            }
                            l.isBlank() -> Spacer(Modifier.size(6.dp))
                            else -> Text(inline(l, codeBg))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun CodeBlock(code: String, lang: String = "") {
    val clip = LocalClipboardManager.current
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(start = 10.dp)) {
                Text(lang.ifBlank { "code" }, style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(1f))
                IconButton(onClick = { clip.setText(AnnotatedString(code)) }, modifier = Modifier.size(32.dp)) {
                    Icon(Icons.Default.ContentCopy, "Copy", modifier = Modifier.size(16.dp))
                }
            }
            SelectionContainer {
                Text(
                    code, fontFamily = FontFamily.Monospace, fontSize = 12.sp, lineHeight = 16.sp,
                    modifier = Modifier.horizontalScroll(rememberScrollState()).padding(start = 10.dp, end = 10.dp, bottom = 10.dp),
                )
            }
        }
    }
}
