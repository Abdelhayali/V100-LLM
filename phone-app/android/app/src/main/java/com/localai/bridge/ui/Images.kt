package com.localai.bridge.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BrokenImage
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AssistChip
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.localai.bridge.data.AttachmentRef
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** Decoded images, shared across the chat so scrolling doesn't re-download. */
private val bitmapCache = android.util.LruCache<String, ImageBitmap>(24)

/** Download an attachment once into the cache dir (keeps its original file name for sharing). */
suspend fun attachmentFile(vm: MainViewModel, ctx: android.content.Context, a: AttachmentRef): File {
    val dir = File(ctx.cacheDir, "att/${a.id}").apply { mkdirs() }
    val f = File(dir, a.filename.ifBlank { a.id })
    if (!f.exists() || f.length() == 0L) vm.api!!.downloadAttachment(a.id, f)
    return f
}

private fun decodeSampled(f: File, maxSide: Int): ImageBitmap? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(f.path, bounds)
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / sample > maxSide) sample *= 2
    return BitmapFactory.decodeFile(f.path, BitmapFactory.Options().apply { inSampleSize = sample })?.asImageBitmap()
}

@Composable
private fun rememberAttachmentBitmap(vm: MainViewModel, a: AttachmentRef, maxSide: Int): Pair<ImageBitmap?, Boolean> {
    val ctx = LocalContext.current
    val key = "${a.id}@$maxSide"
    var bmp by remember(key) { mutableStateOf(bitmapCache.get(key)) }
    var failed by remember(key) { mutableStateOf(false) }
    LaunchedEffect(key) {
        if (bmp != null) return@LaunchedEffect
        try {
            val loaded = withContext(Dispatchers.IO) { decodeSampled(attachmentFile(vm, ctx, a), maxSide) }
            if (loaded != null) { bitmapCache.put(key, loaded); bmp = loaded } else failed = true
        } catch (e: Exception) { failed = true }
    }
    return bmp to failed
}

/** Images inline (tap = full screen), other files as chips (tap = open). */
@Composable
fun AttachmentsView(vm: MainViewModel, attachments: List<AttachmentRef>, alignEnd: Boolean = false) {
    if (attachments.isEmpty()) return
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var viewing by remember { mutableStateOf<AttachmentRef?>(null) }
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(6.dp, if (alignEnd) Alignment.End else Alignment.Start),
        verticalArrangement = Arrangement.spacedBy(6.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        for (a in attachments) {
            if (a.kind == "image") {
                val (bmp, failed) = rememberAttachmentBitmap(vm, a, 1024)
                Box(
                    Modifier.widthIn(max = 280.dp).heightIn(max = 280.dp).clip(RoundedCornerShape(10.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant).clickable { viewing = a },
                    contentAlignment = Alignment.Center,
                ) {
                    when {
                        bmp != null -> Image(bmp, a.filename, contentScale = ContentScale.Fit)
                        failed -> Icon(Icons.Default.BrokenImage, null, Modifier.padding(24.dp))
                        else -> CircularProgressIndicator(Modifier.padding(32.dp).size(24.dp), strokeWidth = 2.dp)
                    }
                }
            } else {
                AssistChip(
                    onClick = {
                        scope.launch {
                            runCatching { openLocal(ctx, attachmentFile(vm, ctx, a)) }
                                .onFailure { vm.toast = "Cannot open: ${it.message}" }
                        }
                    },
                    label = { Text(a.filename, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.widthIn(max = 200.dp)) },
                    leadingIcon = { Icon(kindIcon(a.kind), null, Modifier.size(16.dp)) },
                )
            }
        }
    }
    viewing?.let { ImageViewer(vm, it) { viewing = null } }
}

@Composable
fun ImageViewer(vm: MainViewModel, a: AttachmentRef, onClose: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val (bmp, _) = rememberAttachmentBitmap(vm, a, 3000)
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(Modifier.fillMaxSize().background(Color.Black)) {
            if (bmp != null) {
                Image(
                    bmp, a.filename, contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxSize()
                        .pointerInput(Unit) {
                            detectTransformGestures { _, pan, zoom, _ ->
                                scale = (scale * zoom).coerceIn(1f, 8f)
                                offset = if (scale == 1f) Offset.Zero else offset + pan
                            }
                        }
                        .graphicsLayer(scaleX = scale, scaleY = scale, translationX = offset.x, translationY = offset.y),
                )
            } else CircularProgressIndicator(Modifier.align(Alignment.Center))
            Surface(color = Color.Black.copy(alpha = 0.5f), modifier = Modifier.fillMaxWidth().safeDrawingPadding()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onClose) { Icon(Icons.Default.Close, "Close", tint = Color.White) }
                    Text(a.filename, color = Color.White, maxLines = 1, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f))
                    IconButton(onClick = {
                        scope.launch { runCatching { openLocal(ctx, attachmentFile(vm, ctx, a)) } }
                    }) { Icon(Icons.Default.OpenInNew, "Open", tint = Color.White) }
                    IconButton(onClick = {
                        scope.launch { runCatching { shareLocal(ctx, attachmentFile(vm, ctx, a)) } }
                    }) { Icon(Icons.Default.Share, "Share / save", tint = Color.White) }
                }
            }
        }
    }
}
