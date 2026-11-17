package `in`.prahari.app

import android.app.Activity
import android.os.Bundle
import android.os.Debug
import android.os.SystemClock
import android.view.ViewGroup
import android.widget.*
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import org.pytorch.executorch.extension.llm.LlmCallback
import org.pytorch.executorch.extension.llm.LlmGenerationConfig
import org.pytorch.executorch.extension.llm.LlmModule
import java.io.File
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor()
    private var module: LlmModule? = null
    private lateinit var output: TextView
    private lateinit var input: EditText
    private lateinit var mode: Spinner
    private lateinit var check: Button
    private val modelFile = "Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte"
    private val tokenizerFile = "tokenizer.model"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 24, 24, 24) }
        val scroll = ScrollView(this); scroll.addView(layout); setContentView(scroll)
        layout.addView(TextView(this).apply { text = "Prahari\nOffline scam and threat check • Built with Llama"; textSize = 22f })
        mode = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("SMS", "URL", "Network flow")) }
        layout.addView(mode)
        input = EditText(this).apply { hint = "Enter a message, link, flow description, or flow JSON"; minLines = 4 }
        layout.addView(input)
        val samples = listOf(
            Triple("SMS: KYC scam", 0, "Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked"),
            Triple("SMS: bill", 0, "Your electricity bill of Rs 1,240 is due on 15 Nov. Pay through the mahadiscom app; no link is attached."),
            Triple("URL: lookalike", 1, "http://amaz0n-refund-help.top/claim?id=8812"),
            Triple("URL: official", 1, "https://www.irctc.co.in/nget/train-search"),
            Triple("Flow: port scan", 2, "tcp connections to 200 different ports on 10.0.0.5 within 10 seconds, all rejected")
        )
        val presets = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("Choose a sample") + samples.map { it.first }) }
        presets.onItemSelectedListener = object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: android.widget.AdapterView<*>?) {}
            override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: android.view.View?, position: Int, id: Long) {
                if (position > 0) { val s = samples[position - 1]; mode.setSelection(s.second); input.setText(s.third) }
            }
        }
        layout.addView(presets)
        check = Button(this).apply { text = "Check"; setOnClickListener { runCheck() } }; layout.addView(check)
        layout.addView(Button(this).apply { text = "Network check"; setOnClickListener { networkCheck() } })
        output = TextView(this).apply { textSize = 16f; setTextIsSelectable(true) }; layout.addView(output, ViewGroup.LayoutParams(-1, -2))
        showMissing()
    }
    private fun files(): Pair<File, File>? {
        val dir = getExternalFilesDir(null) ?: return null
        return Pair(File(dir, modelFile), File(dir, tokenizerFile))
    }
    private fun showMissing() {
        val pair = files()
        if (pair == null || !pair.first.isFile || !pair.second.isFile) {
            output.text = "Model files missing. Push $modelFile and $tokenizerFile to ${pair?.first?.parent ?: "the app external files directory"}. See README."
        }
    }
    private fun runCheck() {
        val pair = files()
        if (pair == null || !pair.first.isFile || !pair.second.isFile) { showMissing(); return }
        val text = input.text.toString(); if (text.isBlank()) { output.text = "Enter an item to check."; return }
        val kind = listOf("sms", "url", "flow")[mode.selectedItemPosition]
        check.isEnabled = false; output.text = "Checking on this device…"
        worker.execute {
            val start = SystemClock.elapsedRealtime()
            try {
                val runner = Runner(pair.first.path, pair.second.path)
                val result = JSONObject(Python.getInstance().getModule("mobile").callAttr("check", kind, text, runner).toString())
                val pss = Debug.getPss() / 1024.0
                val stats = result.getJSONObject("llm")
                val message = "${result.getString("verdict")} (score ${"%.4f".format(result.getDouble("score"))})\n\nEvidence: ${result.getJSONArray("evidence")}\n\nExplanation: ${result.getString("explanation")}\n\nRecommended action: ${result.getJSONArray("actions")}\n\nDetector: ${"%.1f".format(result.getDouble("detector_ms"))} ms • TTFT: ${stats.optString("first_token_ms", "unavailable")} ms • Decode: ${stats.optString("decode_tps", "unavailable")} tok/s\nTotal: ${SystemClock.elapsedRealtime()-start} ms • PSS: ${"%.1f".format(pss)} MB"
                runOnUiThread { output.text = message }
            } catch (e: Throwable) { runOnUiThread { output.text = "Check failed: ${e.javaClass.simpleName}: ${e.message}\nThe model may be incompatible with this runtime. See README." } }
            finally { runOnUiThread { check.isEnabled = true } }
        }
    }
    // Public Java method callable by Chaquopy. JNI may combine token bytes into one UTF-8 callback.
    inner class Runner(private val pte: String, private val tokenizer: String) {
        fun generate(prompt: String): String {
            val m = module ?: LlmModule(pte, tokenizer, 0f).also { module = it }
            m.resetContext()
            val start = SystemClock.elapsedRealtime(); var first: Long? = null; var count = 0
            val out = StringBuilder(); var rawStats = "{}"
            val cb = object : LlmCallback {
                override fun onResult(result: String) {
                    if (first == null) first = SystemClock.elapsedRealtime()
                    out.append(result); count++
                    if (count >= 40) m.stop()
                }
                override fun onStats(stats: String) { rawStats = stats }
                override fun onError(errorCode: Int, message: String) { throw IllegalStateException("ExecuTorch $errorCode: $message") }
            }
            val config = LlmGenerationConfig.create().echo(false).seqLen(2048).temperature(0f).maxNewTokens(40).build()
            m.generate(prompt, config, cb)
            val nativeStats = JSONObject(rawStats)
            val stats = JSONObject().put("backend", "executorch").put("raw", nativeStats)
            if (nativeStats.has("generated_tokens")) stats.put("generated_tokens", nativeStats.getInt("generated_tokens"))
            if (nativeStats.has("decode_token_per_sec")) stats.put("decode_tps", nativeStats.getDouble("decode_token_per_sec"))
            first?.let { stats.put("first_token_ms", it - start) }
            return JSONObject().put("text", out.toString()).put("stats", stats).toString()
        }
    }
    private fun networkCheck() {
        output.text = "Testing HTTPS…"
        worker.execute {
            val result = try {
                val c = URL("https://example.com/").openConnection(); c.connectTimeout = 4000; c.readTimeout = 4000
                c.getInputStream().use { it.read() }; "HTTPS connection succeeded — offline check failed."
            } catch (e: Exception) { "HTTPS connection failed: ${e.javaClass.simpleName}: ${e.message}" }
            runOnUiThread { output.text = result }
        }
    }
    override fun onDestroy() { worker.execute { module?.close(); module = null }; worker.shutdown(); super.onDestroy() }
}
