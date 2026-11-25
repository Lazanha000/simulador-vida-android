package com.lazanha.simulador

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

/** Sobe o servidor Python do jogo em 127.0.0.1 e o mostra num WebView. O código do jogo não é alterado. */
class MainActivity : Activity() {
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#0f172a"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            webViewClient = WebViewClient()
        }
        setContentView(web)

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState)
        }
        Thread {
            try {
                val webDir = copyAssets()
                if (!Python.isStarted()) Python.start(AndroidPlatform(this))
                val saves = File(filesDir, "saves").absolutePath
                val port = Python.getInstance().getModule("android_launcher")
                    .callAttr("start", saves, webDir.absolutePath, 8765).toInt()
                runOnUiThread {
                    if (savedInstanceState == null) web.loadUrl("http://127.0.0.1:$port/")
                }
            } catch (e: Throwable) {
                runOnUiThread { web.loadData("<pre>Erro ao iniciar: ${e}</pre>", "text/html", "utf-8") }
            }
        }.start()
    }

    /** Copia assets/web para uma pasta real (o servidor Python lê arquivos do disco). Refaz a cópia a cada versão. */
    private fun copyAssets(): File {
        val dest = File(filesDir, "web")
        val marker = File(filesDir, "web.version")
        val ver = packageManager.getPackageInfo(packageName, 0).versionCode.toString()
        if (marker.exists() && marker.readText() == ver && dest.isDirectory) return dest
        dest.deleteRecursively()
        copyDir("web", dest)
        marker.writeText(ver)
        return dest
    }

    private fun copyDir(assetPath: String, out: File) {
        val list = assets.list(assetPath) ?: emptyArray()
        if (list.isEmpty()) {
            out.parentFile?.mkdirs()
            assets.open(assetPath).use { i -> out.outputStream().use { o -> i.copyTo(o) } }
        } else {
            out.mkdirs()
            for (n in list) copyDir("$assetPath/$n", File(out, n))
        }
    }

    private fun flushSave() {
        if (Python.isStarted()) {
            try { Python.getInstance().getModule("android_launcher").callAttr("flush") } catch (_: Throwable) {}
        }
    }

    override fun onPause() { flushSave(); super.onPause() }
    override fun onStop() { flushSave(); super.onStop() }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    /** O jogo é uma página só (sem histórico do WebView): pergunta ao JavaScript se há uma tela para voltar
     *  (fecha diálogo/painel, volta do menu Ações...). Só fecha o app se não houver nada a voltar. */
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        web.evaluateJavascript("(window.__simVoltar ? window.__simVoltar() : false)") { r ->
            if (r != "true") finish()
        }
    }
}
