package com.localai.bridge

import android.os.Bundle
import androidx.fragment.app.FragmentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.localai.bridge.ui.AppRoot
import com.localai.bridge.ui.BridgeTheme
import com.localai.bridge.ui.MainViewModel

class MainActivity : FragmentActivity() {   // FragmentActivity: needed for the fingerprint prompt (vault)
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ReplyWatchService.channels(this)
        if (android.os.Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
            != android.content.pm.PackageManager.PERMISSION_GRANTED)   // for "Reply ready"
            requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 7)
        setContent { BridgeTheme(vm.themeMode) { AppRoot(vm) } }
        NotifyWorker.schedule(this)          // scheduled-task results and temperature alerts, even when closed
        GpuWidget.refreshAll(this)
        vm.handleIntent(intent)
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        vm.handleIntent(intent)
    }
}
