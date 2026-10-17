package com.localai.bridge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.localai.bridge.ui.AppRoot
import com.localai.bridge.ui.BridgeTheme
import com.localai.bridge.ui.MainViewModel

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { BridgeTheme(vm.themeMode) { AppRoot(vm) } }
    }
}
