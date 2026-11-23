package `in`.prahari.app

import android.app.Activity
import android.app.Dialog
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.SystemClock
import android.text.Editable
import android.text.SpannableString
import android.text.TextPaint
import android.text.TextUtils
import android.text.TextWatcher
import android.text.style.MetricAffectingSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.WindowManager
import android.view.accessibility.AccessibilityNodeInfo
import android.view.inputmethod.InputMethodManager
import android.widget.*
import android.window.OnBackInvokedCallback
import android.window.OnBackInvokedDispatcher
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import org.pytorch.executorch.extension.llm.LlmCallback
import org.pytorch.executorch.extension.llm.LlmGenerationConfig
import org.pytorch.executorch.extension.llm.LlmModule
import java.io.File
import java.net.URL
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.locks.ReentrantLock

private object T {
    val bg = Color.parseColor("#F4F5F9"); val white = Color.WHITE
    val surface2 = Color.parseColor("#EEF0F5"); val outline = Color.parseColor("#DCE0E8")
    // Borders that identify a control need 3:1 against white. Dividers stay outline.
    val outline2 = Color.parseColor("#868C96"); val ink = Color.parseColor("#121626")
    val ink2 = Color.parseColor("#4B5266")
    // Secondary text has to clear 4.5:1 on the page background, not only on white.
    val ink3 = Color.parseColor("#62687C")
    val brand = Color.parseColor("#283593"); val brandC = Color.parseColor("#E8EAF6")
    val danger = Color.parseColor("#B3261E"); val dangerC = Color.parseColor("#FDECEA")
    val onDanger = Color.parseColor("#8C1D18"); val warnBanner = Color.parseColor("#F5B01A")
    val onWarn = Color.parseColor("#2B1B00"); val warn = Color.parseColor("#8A5300")
    val warnC = Color.parseColor("#FFF3D6"); val onWarnC = Color.parseColor("#5E3A00")
    val ok = Color.parseColor("#1E7B3C"); val okBanner = Color.parseColor("#E5F4EA")
    val okLine = Color.parseColor("#A9D6B6"); val onOk = Color.parseColor("#0D4F27")
}

private const val MODEL_FILE = "Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte"
private const val TOKENIZER_FILE = "tokenizer.model"
private val KINDS = arrayOf("sms", "url", "flow")
private const val TAG = "Prahari"

private class Cancelled : RuntimeException("Check cancelled")

/** Letter-spacing for the Latin half of a heading. Devanagari must not be spaced: matras separate. */
private class Tracking(private val em: Float) : MetricAffectingSpan() {
    override fun updateDrawState(tp: TextPaint) { tp.letterSpacing = em }
    override fun updateMeasureState(tp: TextPaint) { tp.letterSpacing = em }
}

private fun errorText(t: Throwable): String {
    val msg = (t.message ?: "no details").replace('\n', ' ').take(300)
    return "${t.javaClass.simpleName}: $msg"
}

/** True when Android refused the socket because this app has no INTERNET permission. */
private fun internetBlocked(t: Throwable): Boolean {
    val seen = HashSet<Throwable>()
    var cur: Throwable? = t
    while (cur != null && seen.add(cur)) {
        if (cur is SecurityException) return true
        if (cur.message?.contains("INTERNET permission", ignoreCase = true) == true) return true
        cur = cur.cause
    }
    return false
}

private fun containsIndic(value: CharSequence): Boolean {
    for (i in value.indices) if (value[i] in '\u0900'..'\u097F') return true
    return false
}

private fun modelFiles(): Pair<File, File>? {
    val dir = Bridge.app?.getExternalFilesDir(null) ?: return null
    return File(dir, MODEL_FILE) to File(dir, TOKENIZER_FILE)
}

private fun missingMessage(): String? {
    val files = modelFiles()
    return if (files == null || !files.first.isFile || !files.second.isFile) {
        "Model files are missing. Copy $MODEL_FILE and $TOKENIZER_FILE to ${files?.first?.parent ?: "the app external files directory"}. See README."
    } else null
}

/** Load the single process-wide module. Call only from [Bridge.worker]. */
private fun ensureLoaded(): LlmModule {
    Bridge.module?.let { return it }
    val missing = missingMessage()
    Bridge.missing = missing
    if (missing != null) throw IllegalStateException(missing)
    Bridge.loadError?.let { throw IllegalStateException(it) }
    val files = modelFiles() ?: throw IllegalStateException(missingMessage() ?: "Model files missing")
    val created = LlmModule(files.first.path, files.second.path, 0f)
    try {
        created.load()
    } catch (t: Throwable) {
        try { created.close() } catch (_: Throwable) {}
        Bridge.loadError = errorText(t)
        throw IllegalStateException(Bridge.loadError, t)
    }
    Bridge.module = created
    Bridge.loadError = null
    Bridge.missing = null
    return created
}

/**
 * One worker thread owns Chaquopy (`mobile._last`) and [LlmModule]. [LlmModule.generate]
 * holds its own lock and forbids re-entering load, reset, or close from a callback.
 * [LlmModule.stop] is the only call that is safe from the UI thread, and only while
 * generate is inside the native call. The module outlives rotation; it is closed when
 * the user leaves the activity.
 */
internal object Bridge {
    class Job(
        val id: Int,
        val mode: Int,
        val value: String,
        val started: Long,
        val verdict: JSONObject
    ) {
        @Volatile var explanation: JSONObject? = null
        @Volatile var totalMs: Long = -1L
        @Volatile var pssMb: Double = Double.NaN
    }

    class Net(val id: Int, val code: String, val message: String, val elapsed: Long, val done: Boolean)

    val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "prahari-model").apply { isDaemon = true }
    }
    val netWorker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "prahari-net").apply { isDaemon = true }
    }
    val genLock = ReentrantLock()
    @Volatile var app: Context? = null
    @Volatile var host: MainActivity? = null
    @Volatile var module: LlmModule? = null
    @Volatile var loadError: String? = null
    @Volatile var missing: String? = null
    @Volatile var pythonError: String? = null
    @Volatile var generation = 0
    @Volatile var generating = false
    @Volatile var phase = "idle"
    @Volatile var job: Job? = null
    @Volatile var netId = 0
    @Volatile var net: Net? = null
    /** 0 verdict still running, 1 verdict back (Llama writing), 2 explanation back. */
    @Volatile var checkStage = 0

    fun still(id: Int) = id == generation

    fun ui(block: (MainActivity) -> Unit) {
        val activity = host ?: return
        if (activity.isDestroyed) return
        activity.runOnUiThread {
            val current = host
            if (current == null || current !== activity || current.isDestroyed) return@runOnUiThread
            block(current)
        }
    }

    fun begin(): Int {
        val stopNow: LlmModule?
        val id: Int
        genLock.lock()
        try {
            generation += 1
            id = generation
            job = null
            phase = "checking"
            checkStage = 0
            stopNow = if (generating) module else null
        } finally {
            genLock.unlock()
        }
        if (stopNow != null) try { stopNow.stop() } catch (_: Throwable) {}
        return id
    }

    fun cancel() {
        val stopNow: LlmModule?
        genLock.lock()
        try {
            generation += 1
            phase = "idle"
            job = null
            stopNow = if (generating) module else null
        } finally {
            genLock.unlock()
        }
        if (stopNow != null) try { stopNow.stop() } catch (_: Throwable) {}
    }

    fun publish(id: Int, next: Job): Boolean {
        genLock.lock()
        try {
            if (id != generation || phase != "checking") return false
            job = next
            phase = "result"
            return true
        } finally {
            genLock.unlock()
        }
    }

    fun mark(id: Int, next: String): Boolean {
        genLock.lock()
        try {
            if (id != generation) return false
            phase = next
            return true
        } finally {
            genLock.unlock()
        }
    }

    fun enterNetwork(cancelWork: Boolean) {
        val stopNow: LlmModule?
        genLock.lock()
        try {
            if (cancelWork) {
                generation += 1
                job = null
            }
            phase = "network"
            stopNow = if (cancelWork && generating) module else null
        } finally {
            genLock.unlock()
        }
        if (stopNow != null) try { stopNow.stop() } catch (_: Throwable) {}
    }

    fun fail(id: Int) {
        genLock.lock()
        try {
            if (id != generation) return
            phase = "idle"
            job = null
        } finally {
            genLock.unlock()
        }
    }

    /** Stop a running generate, then close. Queued on [worker], so it runs after generate returns. */
    fun closeModel() {
        val stopNow: LlmModule?
        genLock.lock()
        try {
            generation += 1
            phase = "idle"
            job = null
            stopNow = if (generating) module else null
        } finally {
            genLock.unlock()
        }
        if (stopNow != null) try { stopNow.stop() } catch (_: Throwable) {}
        worker.execute {
            val open = module
            module = null
            if (open != null) {
                try { open.stop() } catch (_: Throwable) {}
                try { open.close() } catch (_: Throwable) {}
            }
        }
    }
}

private fun requestModel(force: Boolean) {
    Bridge.worker.execute {
        try {
            Bridge.missing = missingMessage()
            val shouldLoad = Bridge.missing == null && Bridge.pythonError == null &&
                Bridge.module == null && (force || Bridge.loadError == null)
            if (shouldLoad) {
                if (force) Bridge.loadError = null
                try {
                    ensureLoaded()
                    Bridge.loadError = null
                } catch (t: Throwable) {
                    Bridge.loadError = errorText(t)
                    Log.e(TAG, "model load failed", t)
                }
            }
        } catch (t: Throwable) {
            Bridge.loadError = errorText(t)
            Log.e(TAG, "model probe failed", t)
        }
        Bridge.ui { if (it.screen == "home") it.bindModelStatus() }
    }
}

private fun enqueueCheck(id: Int, mode: Int, value: String, started: Long) {
    Bridge.worker.execute {
        try {
            runCheck(id, mode, value, started)
        } catch (t: Throwable) {
            Log.e(TAG, "check escaped", t)
        }
    }
}

private fun runCheck(id: Int, mode: Int, value: String, started: Long) {
    try {
        if (!Bridge.still(id)) return
        if (Bridge.pythonError != null || !Python.isStarted()) {
            throw IllegalStateException(Bridge.pythonError ?: "Python is not running")
        }
        val bridge = Python.getInstance().getModule("mobile")
        val verdict = JSONObject(bridge.callAttr("verdict", KINDS[mode], value).toString())
        val level = verdict.optString("level")
        if (level != "danger" && level != "warn" && level != "clear") {
            throw IllegalStateException("Invalid detector verdict")
        }
        if (!Bridge.still(id)) return
        val job = Bridge.Job(id, mode, value, started, verdict)
        if (!Bridge.publish(id, job)) return
        // Step 1 and the safety steps are both done once verdict() returns. Step 2 keeps spinning.
        Bridge.checkStage = 1
        Bridge.ui { act ->
            if (!Bridge.still(id)) return@ui
            if (act.screen == "checking") act.advanceChecking(1)
            if (act.screen != "result" || act.shownId != id) act.presentResult(job)
        }
        if (!Bridge.still(id)) return
        val explanation = try {
            val missing = missingMessage()
            Bridge.missing = missing
            when {
                missing != null -> JSONObject().put("error", missing)
                Bridge.pythonError != null -> JSONObject().put("error", Bridge.pythonError)
                else -> JSONObject(bridge.callAttr("explain", Runner(id)).toString())
            }
        } catch (t: Throwable) {
            if (!Bridge.still(id)) return
            Log.e(TAG, "explanation failed", t)
            JSONObject().put("error", errorText(t))
        }
        if (!Bridge.still(id)) return
        job.explanation = explanation
        job.totalMs = SystemClock.elapsedRealtime() - started
        job.pssMb = try { Debug.getPss() / 1024.0 } catch (_: Throwable) { Double.NaN }
        Bridge.checkStage = 2
        Bridge.ui { act ->
            if (!Bridge.still(id)) return@ui
            if (act.screen == "checking") act.advanceChecking(2)
            if (act.screen != "result" || act.shownId != id) act.presentResult(job)
            else act.applyExplanation(job)
        }
    } catch (t: Throwable) {
        if (!Bridge.still(id)) return
        Log.e(TAG, "check failed", t)
        Bridge.fail(id)
        if (!Bridge.still(id)) return
        val message = "Check failed: ${errorText(t)}. The model may not run on this device."
        Bridge.ui { act ->
            if (!Bridge.still(id)) return@ui
            act.inputValue = value
            act.selectedMode = mode
            act.showHome()
            act.toast(message)
        }
    }
}

private fun enqueueNet(id: Int) {
    Bridge.netWorker.execute {
        val start = SystemClock.elapsedRealtime()
        var code = "other"
        var message = ""
        try {
            val connection = URL("https://example.com").openConnection()
            connection.connectTimeout = 4000
            connection.readTimeout = 4000
            connection.getInputStream().use { it.read() }
            code = "ok"
        } catch (e: Exception) {
            // SecurityException, or any failure whose text names the missing INTERNET permission,
            // is Android blocking the app. Timeouts, DNS and other IO are a different state.
            code = if (internetBlocked(e)) "blocked" else "other"
            message = errorText(e)
        }
        val elapsed = SystemClock.elapsedRealtime() - start
        if (id != Bridge.netId) return@execute
        val net = Bridge.Net(id, code, message, elapsed, true)
        Bridge.net = net
        Bridge.ui { act ->
            if (id != Bridge.netId || act.screen != "network") return@ui
            val body = act.networkBody ?: return@ui
            act.renderNetwork(body, net)
        }
    }
}

/**
 * Chaquopy calls [generate] on the model worker. Do not touch views from here, and do not
 * call load, reset, or close from [LlmCallback] — the native generate holds the module lock.
 */
class Runner(private val id: Int) {
    fun generate(prompt: String): String {
        if (!Bridge.still(id)) throw Cancelled()
        val module = ensureLoaded()
        if (!Bridge.still(id)) throw Cancelled()
        module.resetContext()
        if (!Bridge.still(id)) throw Cancelled()
        val start = SystemClock.elapsedRealtime()
        var first: Long? = null
        var count = 0
        val out = StringBuilder()
        var rawStats = "{}"
        val callbackError = AtomicReference<String?>(null)
        val callback = object : LlmCallback {
            override fun onResult(result: String) {
                try {
                    if (first == null) first = SystemClock.elapsedRealtime()
                    out.append(result)
                    count++
                    // maxNewTokens is not forwarded by this AAR. Stop from the callback, which is supported.
                    if (count >= 40 || !Bridge.still(id)) {
                        try { module.stop() } catch (_: Throwable) {}
                    }
                } catch (_: Throwable) {}
            }
            override fun onStats(stats: String) {
                try { rawStats = stats } catch (_: Throwable) {}
            }
            override fun onError(errorCode: Int, message: String) {
                try { callbackError.set("ExecuTorch $errorCode: $message") } catch (_: Throwable) {}
            }
        }
        val seqLen = (prompt.toByteArray(Charsets.UTF_8).size * 3 / 4 + 32 + 40).coerceIn(256, 2048)
        val config = LlmGenerationConfig.create().echo(false).seqLen(seqLen).temperature(0f).maxNewTokens(40).build()
        var armed = false
        var generationFailure: Throwable? = null
        try {
            Bridge.genLock.lock()
            try {
                if (!Bridge.still(id)) throw Cancelled()
                Bridge.generating = true
                armed = true
            } finally {
                Bridge.genLock.unlock()
            }
            try {
                module.generate(prompt, config, callback)
            } catch (t: Throwable) {
                generationFailure = t
            }
        } finally {
            if (armed) {
                Bridge.genLock.lock()
                try { Bridge.generating = false } finally { Bridge.genLock.unlock() }
            }
        }
        if (!Bridge.still(id)) throw Cancelled()
        callbackError.get()?.let { throw IllegalStateException(it, generationFailure) }
        generationFailure?.let { throw it }
        val stats = JSONObject().put("backend", "executorch")
        try {
            val nativeStats = JSONObject(if (rawStats.isBlank()) "{}" else rawStats)
            stats.put("raw", nativeStats)
            if (nativeStats.has("generated_tokens")) stats.put("generated_tokens", nativeStats.optInt("generated_tokens"))
            if (nativeStats.has("decode_token_per_sec")) stats.put("decode_tps", nativeStats.optDouble("decode_token_per_sec"))
        } catch (_: Throwable) {}
        first?.let { stats.put("first_token_ms", it - start) }
        return JSONObject().put("text", out.toString()).put("stats", stats).toString()
    }
}

class MainActivity : Activity() {
    internal var screen = "home"
    internal var selectedMode = 0
    internal var inputValue = ""
    internal var shownId = Int.MIN_VALUE
    private var visibleJob: Bridge.Job? = null
    private lateinit var input: EditText
    private var explanationText: TextView? = null
    private var statsDetails: LinearLayout? = null
    private var statsSummary: TextView? = null
    private var statsHeader: View? = null
    private var metaText: TextView? = null
    private var modelStatusSlot: LinearLayout? = null
    internal var networkBody: LinearLayout? = null
    private val checkSlots = mutableListOf<FrameLayout>()
    private val checkTitles = mutableListOf<TextView>()
    private val checkSubs = mutableListOf<TextView>()
    private var aboutDialog: Dialog? = null
    private var backCallback: OnBackInvokedCallback? = null
    private var ignoreBackUntil = 0L

    private val modeNames = arrayOf("SMS", "Link", "Network")
    private val modeHindi = arrayOf("संदेश", "लिंक", "नेटवर्क")
    private val modeIcons = intArrayOf(R.drawable.ic_message, R.drawable.ic_link, R.drawable.ic_activity)
    private val labels = arrayOf("Message you received", "Link you want to open", "Network event or flow JSON")
    private val hints = arrayOf(
        "Paste or type the SMS or WhatsApp message",
        "Paste the full link, e.g. https://…",
        "Describe the traffic, or paste flow JSON"
    )
    private data class Sample(val label: String, val mode: Int, val value: String)
    private val samples = listOf(
        Sample("KYC scam SMS", 0, "Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked"),
        Sample("Bill reminder", 0, "Your electricity bill of Rs 1,240 is due on 15 Dec. Pay through the mahadiscom app; no link is attached."),
        Sample("Lookalike link", 1, "http://amaz0n-refund-help.top/claim?id=8812"),
        Sample("Official link", 1, "https://www.irctc.co.in/nget/train-search"),
        Sample("Port scan", 2, "tcp connections to 200 different ports on 10.0.0.5 within 10 seconds, all rejected"),
        Sample("Hinglish electricity", 0, "Aapka bijli connection aaj raat 9:30 kat jayega. Turant 98XXXXXX12 par call karein ya http://uppcl-bill-pay.top kholein."),
        Sample("Bank debit alert", 0, "SBI: Rs 2,450 debited via UPI. OTP 482910 kisi se share mat karein. If not you, block card in YONO app.")
    )

    private val density get() = resources.displayMetrics.density
    private fun dp(n: Number) = (n.toFloat() * density + .5f).toInt()
    private fun shape(fill: Int, radius: Float, stroke: Int = 0, strokeColor: Int = T.outline) = GradientDrawable().apply {
        setColor(fill); cornerRadius = radius * density
        if (stroke > 0) setStroke(dp(stroke), strokeColor)
    }
    private fun ripple(bg: GradientDrawable) = RippleDrawable(ColorStateList.valueOf(0x33121626), bg, null)

    /** User-facing English goes through [t]. Pass raw for the message itself, a quote, or Llama text. */
    private fun t(english: String): String = L10n.t(english)

    private fun txt(value: CharSequence, size: Float, color: Int = T.ink, weight: Int = 400, line: Int = 0, raw: Boolean = false) = TextView(this).apply {
        val shown: CharSequence = if (!raw && value is String) t(value) else value
        text = shown
        setTextSize(TypedValue.COMPLEX_UNIT_SP, size)
        setTextColor(color)
        // includeFontPadding plus a line box in sp keeps Devanagari matras and descenders
        // inside a wrapped Hindi step at 100% and 200% font scale. textSize already includes
        // fontScale, so the line box doubles at 200% instead of clipping the lower stroke.
        includeFontPadding = true
        isFallbackLineSpacing = true
        typeface = Typeface.create(Typeface.DEFAULT, weight, false)
        val indic = containsIndic(shown)
        if (line > 0 || indic) {
            val designed = if (line > 0) {
                TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, line.toFloat(), resources.displayMetrics)
            } else 0f
            val room = textSize * if (indic) 1.8f else 1.15f
            lineHeight = maxOf(designed, room).toInt().coerceAtLeast(1)
        }
        if (indic) {
            val cushion = (textSize * 0.12f).toInt()
            setPadding(paddingLeft, paddingTop, paddingRight, paddingBottom + cushion)
        }
    }

    private fun icon(id: Int, size: Int, tint: Int) = ImageView(this).apply {
        setImageResource(id)
        setColorFilter(tint)
        layoutParams = LinearLayout.LayoutParams(dp(size), dp(size))
        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
    }
    private fun col() = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
    private fun row() = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
    private fun pad(v: View, l: Int, t: Int, r: Int, b: Int) = v.setPadding(dp(l), dp(t), dp(r), dp(b))
    private fun add(parent: LinearLayout, child: View, w: Int = -1, h: Int = -2, top: Int = 0, left: Int = 0, weight: Float = 0f) {
        parent.addView(child, LinearLayout.LayoutParams(if (w < 0) w else dp(w), if (h < 0) h else dp(h), weight).apply {
            topMargin = dp(top); leftMargin = dp(left)
        })
    }
    private fun divider(parent: LinearLayout, top: Int = 0) = add(parent, View(this).apply { setBackgroundColor(T.outline) }, -1, 1, top)
    private fun card(fill: Int = T.white, border: Boolean = true) = col().apply {
        background = shape(fill, 16f, if (border) 1 else 0, T.outline2)
        pad(this, 16, 14, 16, 14)
    }
    private fun heading(en: String, hi: String): TextView {
        if (L10n.hindi) {
            val label = t(en).let { if (it != en) it else hi.ifBlank { en } }
            return txt(label, 11f, T.ink2, 700, 16, raw = true).apply { isAccessibilityHeading = true }
        }
        val label = en.uppercase(Locale.ROOT)
        val full = "$label · $hi"
        return txt(full, 11f, T.ink2, 700, 16, raw = true).apply {
            isAccessibilityHeading = true
            val spaced = SpannableString(full)
            spaced.setSpan(Tracking(0.04f), 0, label.length, 0)
            text = spaced
        }
    }
    private fun iconText(id: Int, text: String, color: Int, size: Float = 14f, iconSize: Int = 18, flex: Boolean = false): LinearLayout = row().apply {
        add(this, icon(id, iconSize, color), iconSize, iconSize)
        val label = txt(text, size, color, 600)
        if (flex) {
            label.maxLines = 8
            label.ellipsize = TextUtils.TruncateAt.END
        }
        add(this, label, if (flex) 0 else -2, -2, left = 6, weight = if (flex) 1f else 0f)
    }
    private fun cap(label: TextView, limit: View, slackDp: Int) {
        limit.addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
            if (limit.width <= 0) return@addOnLayoutChangeListener
            val max = (limit.width - dp(slackDp)).coerceAtLeast(dp(32))
            if (label.maxWidth != max) label.maxWidth = max
        }
    }
    private fun asButton(v: ViewGroup, description: String) {
        v.contentDescription = t(description)
        v.isClickable = true
        v.isFocusable = true
        if (v.minimumHeight < dp(48)) v.minimumHeight = dp(48)
        v.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        v.accessibilityDelegate = object : View.AccessibilityDelegate() {
            override fun onInitializeAccessibilityNodeInfo(host: View, info: AccessibilityNodeInfo) {
                super.onInitializeAccessibilityNodeInfo(host, info)
                info.className = Button::class.java.name
            }
        }
        for (i in 0 until v.childCount) {
            v.getChildAt(i).importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        }
    }
    private fun a11yText(v: ViewGroup, description: String) {
        v.contentDescription = t(description)
        v.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        for (i in 0 until v.childCount) {
            v.getChildAt(i).importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        }
    }
    private fun button(text: String, id: Int? = null, fill: Int = T.brand, textColor: Int = T.white, outlined: Boolean = false, action: () -> Unit): LinearLayout = row().apply {
        gravity = Gravity.CENTER
        minimumHeight = dp(48)
        setPadding(dp(12), dp(4), dp(12), dp(4))
        background = ripple(shape(if (outlined) T.white else fill, 16f, if (outlined) 1 else 0, T.outline2))
        val label = txt(text, 16f, textColor, 600).apply {
            gravity = Gravity.CENTER
            textAlignment = View.TEXT_ALIGNMENT_CENTER
            maxLines = 3
            ellipsize = TextUtils.TruncateAt.END
        }
        if (id != null) add(this, icon(id, 20, textColor), 20, 20)
        add(this, label, -2, -2, left = if (id != null) 10 else 0)
        setOnClickListener { action() }
        asButton(this, text)
        addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
            if (width <= 0) return@addOnLayoutChangeListener
            val iconW = if (id != null) dp(30) else 0
            val max = (width - paddingLeft - paddingRight - iconW).coerceAtLeast(dp(48))
            if (label.maxWidth != max) label.maxWidth = max
        }
    }
    private fun iconButton(id: Int, description: String, action: () -> Unit) = FrameLayout(this).apply {
        minimumWidth = dp(48)
        minimumHeight = dp(48)
        isClickable = true
        isFocusable = true
        background = ripple(shape(T.bg, 24f))
        addView(icon(id, 24, T.ink), FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
        setOnClickListener { action() }
        asButton(this, description)
    }
    private fun logo(): FrameLayout = FrameLayout(this).apply {
        background = shape(T.brand, 11f)
        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        addView(icon(R.drawable.ic_shield, 22, T.white), FrameLayout.LayoutParams(dp(22), dp(22), Gravity.CENTER))
        addView(View(this@MainActivity).apply {
            background = shape(T.white, 3f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }, FrameLayout.LayoutParams(dp(4), dp(4), Gravity.CENTER))
    }
    private fun root(pane: String): LinearLayout = col().apply {
        setBackgroundColor(T.bg)
        fitsSystemWindows = true
        isFocusableInTouchMode = true
        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        accessibilityPaneTitle = t(pane)
    }
    private fun bar(title: String, offline: Boolean, lang: Boolean = false): LinearLayout = row().apply {
        minimumHeight = dp(56)
        pad(this, 4, 0, 8, 0)
        add(this, iconButton(R.drawable.ic_arrow_left, "Back") { goHome() }, 48, 48)
        add(this, txt(title, 20f, T.ink, 600).apply { maxLines = 2; ellipsize = TextUtils.TruncateAt.END }, 0, -2, left = 4, weight = 1f)
        if (lang) add(this, langToggle {
            val job = visibleJob
            if (job != null && screen == "result") presentResult(job) else showHome()
        }, -2, -2)
        if (offline) {
            val chip = iconText(R.drawable.ic_wifi_off, "Offline", T.brand, 12f, 14).apply {
                background = shape(T.brandC, 14f)
                pad(this, 10, 6, 10, 6)
            }
            a11yText(chip, "Offline. This app has no internet permission.")
            add(this, chip, -2, -2)
        }
    }
    private fun bottom(parent: LinearLayout, text: String, outlined: Boolean = false, id: Int? = null, action: () -> Unit) {
        val box = col().apply { setBackgroundColor(T.white) }
        divider(box)
        val wrap = col().apply { pad(this, 16, 10, 16, 6) }
        val actionButton = button(text, id, textColor = if (outlined) T.ink else T.white, outlined = outlined, action = action)
        actionButton.minimumHeight = dp(52)
        add(wrap, actionButton, -1, -2)
        add(box, wrap)
        add(parent, box)
    }
    private fun scrollBody(parent: LinearLayout): LinearLayout {
        val body = col().apply { pad(this, 16, 0, 16, 16) }
        val scroll = ScrollView(this).apply {
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            isFillViewport = false
            clipToPadding = false
            addView(body)
        }
        add(parent, scroll, -1, 0, weight = 1f)
        return body
    }
    private fun centeredNote(parent: LinearLayout, child: LinearLayout, top: Int) {
        val label = child.getChildAt(1) as TextView
        label.gravity = Gravity.CENTER
        label.textAlignment = View.TEXT_ALIGNMENT_CENTER
        val holder = row().apply { gravity = Gravity.CENTER }
        holder.addView(child)
        add(parent, holder, -1, -2, top = top)
        cap(label, holder, 28)
    }
    private fun loadStrings() {
        val prefs = getSharedPreferences("prahari", MODE_PRIVATE)
        L10n.hindi = prefs.getString("lang", "en") == "hi"
        if (!Python.isStarted()) return
        try {
            val raw = Python.getInstance().getModule("intake").callAttr("strings_json").toString()
            L10n.load(raw)
        } catch (t: Throwable) {
            Log.e(TAG, "strings load failed", t)
        }
    }

    private fun rememberLanguage() {
        getSharedPreferences("prahari", MODE_PRIVATE).edit()
            .putString("lang", if (L10n.hindi) "hi" else "en").apply()
    }

    /** EN | हिंदी. [rebuild] draws the current screen again in the chosen language. */
    private fun langToggle(rebuild: () -> Unit): LinearLayout {
        val wrap = row().apply {
            background = shape(T.surface2, 14f)
            pad(this, 2, 2, 2, 2)
            minimumHeight = dp(48)
        }
        fun seg(label: String, on: Boolean, hi: Boolean) = row().apply {
            gravity = Gravity.CENTER
            minimumWidth = dp(48)
            minimumHeight = dp(44)
            setPadding(dp(8), dp(4), dp(8), dp(4))
            background = if (on) shape(T.white, 12f, 1, T.outline) else null
            add(this, txt(label, 12f, if (on) T.brand else T.ink2, 700, raw = true), -2, -2)
            setOnClickListener {
                if (L10n.hindi == hi) return@setOnClickListener
                L10n.hindi = hi
                rememberLanguage()
                rebuild()
            }
            asButton(this, label)
        }
        add(wrap, seg("EN", !L10n.hindi, false), -2, -2)
        add(wrap, seg("हिंदी", L10n.hindi, true), -2, -2, left = 2)
        return wrap
    }

    internal fun toast(message: String) {
        if (isDestroyed) return
        Toast.makeText(this, t(message).take(400), Toast.LENGTH_LONG).show()
    }
    private fun hideKeyboard() {
        if (!::input.isInitialized) return
        val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager ?: return
        input.windowToken?.let { imm.hideSoftInputFromWindow(it, 0) }
    }
    private fun modelProblem(): String? {
        Bridge.pythonError?.let { return "The on-device checker could not start. $it" }
        Bridge.missing?.let { return it }
        Bridge.loadError?.let { return "Couldn't load the on-device model. $it" }
        return null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Bridge.app = applicationContext
        Bridge.host = this
        window.statusBarColor = T.bg
        window.navigationBarColor = T.bg
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        savedInstanceState?.let {
            selectedMode = it.getInt("mode", 0).coerceIn(0, KINDS.lastIndex)
            inputValue = it.getString("input") ?: ""
        }
        try {
            if (!Python.isStarted()) Python.start(AndroidPlatform(applicationContext))
            Bridge.pythonError = null
        } catch (t: Throwable) {
            Bridge.pythonError = errorText(t)
            Log.e(TAG, "Python start failed", t)
        }
        loadStrings()
        installBack()
        // A share intent stays on the activity across rotation. Only the first create auto-checks.
        val shared = if (savedInstanceState == null) readShare(intent) else null
        if (shared != null) {
            openShared(shared)
            requestModel(false)
            return
        }
        val restored = if (Bridge.phase == "idle") savedJob(savedInstanceState) else null
        when (Bridge.phase) {
            "checking" -> {
                val job = Bridge.job
                showChecking(job?.mode ?: selectedMode, job?.value ?: inputValue)
            }
            "result" -> {
                val job = Bridge.job
                if (job != null) presentResult(job) else showHome()
            }
            "network" -> showNetwork(false)
            else -> if (restored != null) presentResult(restored) else showHome()
        }
        requestModel(false)
    }

    override fun onSaveInstanceState(out: Bundle) {
        super.onSaveInstanceState(out)
        if (screen == "home" && ::input.isInitialized) inputValue = input.text?.toString() ?: inputValue
        out.putInt("mode", selectedMode)
        out.putString("input", inputValue)
        out.putString("screen", screen)
        val job = if (screen == "result") visibleJob else null
        if (job != null) {
            out.putString("verdict", job.verdict.toString())
            out.putString("value", job.value)
            out.putInt("jobMode", job.mode)
            out.putLong("started", job.started)
            job.explanation?.let { out.putString("explanation", it.toString()) }
            out.putLong("total", job.totalMs)
            if (job.pssMb.isFinite()) out.putDouble("pss", job.pssMb)
        }
    }

    private fun savedJob(state: Bundle?): Bridge.Job? {
        if (state == null) return null
        val raw = state.getString("verdict") ?: return null
        return try {
            val job = Bridge.Job(
                id = -1,
                mode = state.getInt("jobMode", selectedMode),
                value = state.getString("value") ?: inputValue,
                started = state.getLong("started", SystemClock.elapsedRealtime()),
                verdict = JSONObject(raw)
            )
            val explanation = state.getString("explanation")
            job.explanation = if (explanation != null) JSONObject(explanation)
            else JSONObject().put("error", "The check was interrupted when the app closed. The verdict above was restored.")
            job.totalMs = state.getLong("total", -1L)
            if (state.containsKey("pss")) job.pssMb = state.getDouble("pss")
            job
        } catch (t: Throwable) {
            Log.e(TAG, "could not restore result", t)
            null
        }
    }

    private fun installBack() {
        if (Build.VERSION.SDK_INT < 33) return
        val callback = OnBackInvokedCallback { handleBack() }
        onBackInvokedDispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, callback)
        backCallback = callback
    }

    private fun handleBack() {
        val now = SystemClock.uptimeMillis()
        if (now < ignoreBackUntil) return
        ignoreBackUntil = now + 200
        val dialog = aboutDialog
        if (dialog != null) {
            aboutDialog = null
            if (dialog.isShowing) dialog.dismiss()
            return
        }
        if (screen == "home") {
            if (!isFinishing) finish()
        } else {
            goHome()
        }
    }

    @Deprecated("Deprecated in Java")
    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        handleBack()
    }

    private fun goHome(clear: Boolean = false) {
        Bridge.cancel()
        if (clear) inputValue = ""
        showHome()
    }

    internal fun showHome() {
        screen = "home"
        visibleJob = null
        networkBody = null
        val root = root("Prahari")
        val scroller = ScrollView(this).apply {
            isFillViewport = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        val all = col()
        scroller.addView(all)
        add(root, scroller, -1, 0, weight = 1f)
        val brand = row().apply { minimumHeight = dp(60); pad(this, 16, 4, 8, 4) }
        add(brand, logo(), 36, 36)
        val name = col()
        add(name, txt("Prahari", 20f, T.ink, 700, 24))
        add(name, txt("प्रहरी · scam & threat check", 12f, T.ink3, 500, 16))
        add(brand, name, 0, -2, left = 10, weight = 1f)
        add(brand, langToggle { showHome() }, -2, -2)
        add(brand, iconButton(R.drawable.ic_info, "About Prahari") { showAbout() }, 48, 48)
        add(all, brand, -1, -2)
        val body = col().apply { pad(this, 16, 0, 16, 8) }
        add(all, body, -1, 0, weight = 1f)
        add(body, txt("Check before you tap", 24f, T.ink, 700, 30).apply { isAccessibilityHeading = true }, top = 2)
        add(body, txt("टैप करने से पहले जाँचें · works with no internet", 14f, T.ink2, 400, 20), top = 2)
        val seg = row().apply { minimumHeight = dp(52); background = shape(T.surface2, 14f); pad(this, 4, 4, 4, 4) }
        val segments = mutableListOf<LinearLayout>()
        val inputCard = col().apply { pad(this, 16, 14, 16, 8) }
        val label = txt(labels[selectedMode], 12f, T.brand, 600, 16)
        input = EditText(this).apply {
            setText(inputValue)
            setSelection(text?.length ?: 0)
            hint = t(hints[selectedMode])
            setTextColor(T.ink)
            setHintTextColor(T.ink3)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            includeFontPadding = true
            isFallbackLineSpacing = true
            val designed = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, 24f, resources.displayMetrics)
            lineHeight = maxOf(designed, textSize * 1.6f).toInt()
            minLines = 5
            maxLines = 8
            background = null
            gravity = Gravity.TOP or Gravity.START
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE or
                android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            setPadding(0, dp(2), 0, dp(2))
            id = View.generateViewId()
        }
        label.id = View.generateViewId()
        label.labelFor = input.id
        fun refreshSegments() {
            segments.forEachIndexed { i, v ->
                val selected = i == selectedMode
                v.isSelected = selected
                v.background = if (selected) shape(T.white, 10f, 1, T.outline) else null
                val top = v.getChildAt(0) as LinearLayout
                (top.getChildAt(0) as ImageView).setColorFilter(if (selected) T.brand else T.ink2)
                (top.getChildAt(1) as TextView).setTextColor(if (selected) T.brand else T.ink2)
                if (v.childCount > 1) (v.getChildAt(1) as TextView).setTextColor(if (selected) T.brand else T.ink2)
            }
            label.text = t(labels[selectedMode])
            input.hint = t(hints[selectedMode])
        }
        for (i in KINDS.indices) {
            val segment = col().apply {
                gravity = Gravity.CENTER
                minimumHeight = dp(48)
                setPadding(dp(2), dp(8), dp(2), dp(8))
            }
            val face = iconText(modeIcons[i], modeNames[i], T.ink2, 14f, 16)
            val faceLabel = face.getChildAt(1) as TextView
            faceLabel.gravity = Gravity.CENTER
            faceLabel.textAlignment = View.TEXT_ALIGNMENT_CENTER
            faceLabel.maxLines = 2
            faceLabel.ellipsize = TextUtils.TruncateAt.END
            val hindi = txt(modeHindi[i], 11f, T.ink2, 500).apply {
                gravity = Gravity.CENTER
                textAlignment = View.TEXT_ALIGNMENT_CENTER
                maxLines = 2
                ellipsize = TextUtils.TruncateAt.END
            }
            add(segment, face, -2, -2)
            if (!L10n.hindi) add(segment, hindi, -1, -2)
            cap(faceLabel, segment, 24)
            cap(hindi, segment, 8)
            segment.setOnClickListener { selectedMode = i; refreshSegments() }
            asButton(segment, "${modeNames[i]}, ${modeHindi[i]}")
            segments.add(segment)
            add(seg, segment, 0, -2, left = if (i == 0) 0 else 4, weight = 1f)
        }
        add(body, seg, -1, -2, top = 16)
        fun focusBorder() {
            inputCard.background = shape(T.white, 16f, if (input.hasFocus()) 2 else 1, if (input.hasFocus()) T.brand else T.outline2)
        }
        input.setOnFocusChangeListener { _, _ -> focusBorder() }
        add(inputCard, label)
        add(inputCard, input, -1, -2, top = 6)
        val tools = row()
        val paste = iconText(R.drawable.ic_clipboard, "Paste", T.brand).apply {
            minimumWidth = dp(48)
            minimumHeight = dp(48)
            setPadding(dp(4), 0, dp(4), 0)
            setOnClickListener { pasteClipboard() }
        }
        asButton(paste, "Paste from clipboard")
        val clear = iconText(R.drawable.ic_x, "Clear", T.ink2).apply {
            minimumWidth = dp(48)
            minimumHeight = dp(48)
            setPadding(dp(4), 0, dp(4), 0)
            setOnClickListener { input.setText("") }
        }
        asButton(clear, "Clear text")
        add(tools, paste, -2, -2)
        add(tools, View(this), 0, 1, weight = 1f)
        add(tools, clear, -2, -2)
        add(inputCard, tools)
        add(body, inputCard, -1, -2, top = 12)
        focusBorder()
        refreshSegments()
        add(body, heading("Try a sample", "नमूना आज़माएँ"), top = 12)
        val chips = row()
        samples.forEach { sample ->
            val chip = iconText(modeIcons[sample.mode], sample.label, T.ink2, 14f, 16).apply {
                (getChildAt(1) as TextView).setTextColor(T.ink)
                background = ripple(shape(T.white, 18f, 1, T.outline2))
                setPadding(dp(10), dp(8), dp(14), dp(8))
                minimumHeight = dp(48)
                setOnClickListener {
                    selectedMode = sample.mode
                    refreshSegments()
                    input.setText(sample.value)
                    input.setSelection(input.text.length)
                }
            }
            asButton(chip, "${sample.label}, ${modeNames[sample.mode]} sample")
            add(chips, chip, -2, -2, left = if (chips.childCount == 0) 0 else 8)
        }
        add(body, HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(chips)
        }, -1, -2, top = 4)
        val check = button("Check on this phone", R.drawable.ic_shield_check) { startCheck() }.apply {
            contentDescription = "Check on this phone. इस फ़ोन पर जाँचें"
            minimumHeight = dp(56)
        }
        modelStatusSlot = col().apply { accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE }
        add(body, modelStatusSlot!!, -1, -2, top = 8)
        bindModelStatus()
        add(body, check, -1, -2, top = 8)
        fun refreshInput() {
            inputValue = input.text.toString()
            val empty = inputValue.isEmpty()
            clear.visibility = if (empty) View.INVISIBLE else View.VISIBLE
            clear.importantForAccessibility = if (empty) View.IMPORTANT_FOR_ACCESSIBILITY_NO else View.IMPORTANT_FOR_ACCESSIBILITY_YES
            val enabled = inputValue.isNotBlank()
            check.isEnabled = enabled
            check.background = ripple(shape(if (enabled) T.brand else T.surface2, 16f))
            (check.getChildAt(0) as ImageView).setColorFilter(if (enabled) T.white else T.ink3)
            (check.getChildAt(1) as TextView).setTextColor(if (enabled) T.white else T.ink3)
        }
        input.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { refreshInput() }
            override fun afterTextChanged(s: Editable?) {}
        })
        refreshInput()
        add(body, View(this), -1, 0, weight = 1f)
        val offline = row().apply {
            background = ripple(shape(T.white, 16f, 1, T.outline2))
            pad(this, 14, 12, 12, 12)
            minimumHeight = dp(48)
            setOnClickListener { showNetwork(true) }
        }
        val bubble = FrameLayout(this).apply {
            background = shape(T.brandC, 20f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(icon(R.drawable.ic_wifi_off, 20, T.brand), FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER))
        }
        add(offline, bubble, 40, 40)
        val offlineText = col()
        add(offlineText, txt("Prove it's offline", 15f, T.ink, 600, 20))
        add(offlineText, txt("Try to reach the internet from this app", 13f, T.ink2, 400, 18))
        add(offline, offlineText, 0, -2, left = 12, weight = 1f)
        add(offline, icon(R.drawable.ic_chevron_right, 20, T.ink3), 20, 20)
        asButton(offline, "Prove it's offline. Try to reach the internet from this app.")
        add(body, offline, top = 16)
        centeredNote(body, iconText(R.drawable.ic_lock, "Nothing you paste leaves this phone", T.ink3, 12f, 13), 12)
        setContentView(root)
    }

    internal fun bindModelStatus() {
        val slot = modelStatusSlot ?: return
        slot.removeAllViews()
        val problem = modelProblem() ?: return
        val box = card(T.dangerC)
        add(box, txt(problem, 14f, T.onDanger, 400, 20).apply { setTextIsSelectable(true) })
        val retry = when {
            Bridge.pythonError != null -> "Try starting again"
            Bridge.loadError != null && Bridge.missing == null -> "Try loading again"
            Bridge.missing != null -> "Check for the model files"
            else -> null
        }
        if (retry != null) {
            val action = button(retry, outlined = true, textColor = T.onDanger) {
                if (Bridge.pythonError != null) {
                    try {
                        if (!Python.isStarted()) Python.start(AndroidPlatform(applicationContext))
                        Bridge.pythonError = null
                    } catch (t: Throwable) {
                        Bridge.pythonError = errorText(t)
                    }
                    bindModelStatus()
                    if (Bridge.pythonError == null) requestModel(true)
                } else {
                    requestModel(true)
                }
            }
            add(box, action, -1, -2, top = 10)
        }
        add(slot, box)
    }

    private fun pasteClipboard() {
        try {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val item = clipboard.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)
            when {
                item.isNullOrEmpty() -> toast("The clipboard is empty.")
                item.length > 100_000 -> toast("That text is too long to paste.")
                else -> {
                    input.setText(item)
                    input.setSelection(input.text.length)
                }
            }
        } catch (t: Throwable) {
            Log.e(TAG, "clipboard read failed", t)
            toast("Couldn't read the clipboard.")
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val shared = readShare(intent) ?: return
        openShared(shared)
    }

    /** ACTION_SEND uses EXTRA_TEXT. ACTION_PROCESS_TEXT uses EXTRA_PROCESS_TEXT. Never log the text. */
    private fun readShare(source: Intent?): String? {
        if (source == null) return null
        val key = when (source.action) {
            Intent.ACTION_SEND -> {
                val type = source.type ?: return null
                if (!type.startsWith("text/plain")) return null
                Intent.EXTRA_TEXT
            }
            Intent.ACTION_PROCESS_TEXT -> Intent.EXTRA_PROCESS_TEXT
            else -> return null
        }
        val text = source.getCharSequenceExtra(key) ?: source.getStringExtra(key) ?: return null
        return text.toString()
    }

    private fun openShared(raw: String) {
        val text = raw.trim()
        when {
            text.isEmpty() -> {
                toast("Nothing to check.")
                showHome()
            }
            text.length > 100_000 -> {
                toast("That text is too long to check.")
                showHome()
            }
            else -> beginCheck(detectMode(text), text)
        }
    }

    private fun detectMode(text: String): Int {
        return try {
            if (!Python.isStarted()) 0
            else Python.getInstance().getModule("intake").callAttr("detect_mode", text).toInt().coerceIn(0, 2)
        } catch (t: Throwable) {
            Log.e(TAG, "mode detection failed", t)
            0
        }
    }

    /** SMS / Link / Network. The selected chip is the auto-detected mode; another tap re-checks. */
    private fun modeSwitcher(selected: Int, value: String): LinearLayout {
        val seg = row().apply {
            minimumHeight = dp(48)
            background = shape(T.surface2, 14f)
            pad(this, 4, 4, 4, 4)
        }
        for (i in KINDS.indices) {
            val on = i == selected
            val chip = row().apply {
                gravity = Gravity.CENTER
                minimumHeight = dp(48)
                setPadding(dp(4), dp(4), dp(4), dp(4))
                background = if (on) shape(T.white, 10f, 1, T.outline) else null
            }
            val color = if (on) T.brand else T.ink2
            add(chip, icon(modeIcons[i], 16, color), 16, 16)
            val label = txt(modeNames[i], 13f, color, 700).apply {
                maxLines = 1
                ellipsize = TextUtils.TruncateAt.END
                gravity = Gravity.CENTER
            }
            add(chip, label, 0, -2, left = 4, weight = 1f)
            chip.setOnClickListener { if (i != selected) beginCheck(i, value) }
            asButton(chip, if (on) "${modeNames[i]}, ${modeHindi[i]}, selected" else "Change to ${modeNames[i]}, ${modeHindi[i]}")
            add(seg, chip, 0, -2, left = if (i == 0) 0 else 4, weight = 1f)
        }
        return seg
    }

    private fun startCheck() {
        if (!::input.isInitialized) return
        beginCheck(selectedMode, input.text?.toString() ?: "")
    }

    private fun beginCheck(mode: Int, value: String) {
        if (value.isBlank()) {
            toast("Paste a message, link or network event first.")
            return
        }
        if (value.length > 100_000) {
            toast("That text is too long to check.")
            return
        }
        inputValue = value
        selectedMode = mode.coerceIn(0, KINDS.lastIndex)
        hideKeyboard()
        val id = Bridge.begin()
        val started = SystemClock.elapsedRealtime()
        showChecking(selectedMode, value)
        enqueueCheck(id, selectedMode, value, started)
    }

    private fun showChecking(mode: Int, value: String) {
        screen = "checking"
        selectedMode = mode
        inputValue = value
        visibleJob = null
        networkBody = null
        val root = root("Checking")
        add(root, bar("Checking", true), -1, -2)
        val body = scrollBody(root)
        val what = card()
        val summary = row()
        add(summary, icon(modeIcons[mode], 18, T.ink2), 18, 18)
        add(summary, txt(value, 14f, T.ink2, 400, 20, raw = true).apply { maxLines = 3; ellipsize = TextUtils.TruncateAt.END }, 0, -2, left = 12, weight = 1f)
        add(what, summary)
        add(body, what)
        add(body, modeSwitcher(mode, value), -1, -2, top = 12)
        val ring = FrameLayout(this)
        val progress = ProgressBar(this, null, android.R.attr.progressBarStyleLarge).apply {
            indeterminateTintList = ColorStateList.valueOf(T.brand)
            contentDescription = "Checking on this phone"
        }
        ring.addView(progress, FrameLayout.LayoutParams(dp(132), dp(132), Gravity.CENTER))
        val center = FrameLayout(this).apply {
            background = shape(T.brandC, 42f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(icon(R.drawable.ic_shield, 40, T.brand), FrameLayout.LayoutParams(dp(40), dp(40), Gravity.CENTER))
        }
        ring.addView(center, FrameLayout.LayoutParams(dp(84), dp(84), Gravity.CENTER))
        add(body, ring, -1, 132, top = 24)
        add(body, txt("Checking on this phone…", 22f, T.ink, 700, 28).apply {
            gravity = Gravity.CENTER
            isAccessibilityHeading = true
            accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
        }, top = 18)
        add(body, txt("इस फ़ोन पर जाँच हो रही है", 14f, T.ink2, 400, 20).apply { gravity = Gravity.CENTER }, top = 4)
        modelProblem()?.let { problem ->
            add(body, txt(problem, 13f, T.onDanger, 400, 18).apply { gravity = Gravity.CENTER }, top = 8)
        }
        val problem = modelProblem()
        val llama = when {
            problem != null -> "On-device explanation unavailable" to "The verdict will still be ready"
            Bridge.module == null -> "Loading Llama 3.2 on this phone" to "The first load can take a while"
            else -> "Llama 3.2 is writing an explanation" to "On-device · usually 2–4 s"
        }
        val steps = card()
        checkSlots.clear()
        checkTitles.clear()
        checkSubs.clear()
        listOf(
            "Checking scam signals" to "Rules + detector",
            llama.first to llama.second,
            "Safety steps" to "From the vetted list"
        ).forEachIndexed { index, item ->
            if (index > 0) divider(steps)
            val line = row().apply { minimumHeight = dp(56) }
            val slot = FrameLayout(this)
            add(line, slot, 24, 24)
            val labels = col()
            // Pending steps stay in ink3, which clears 4.5:1. A 55% fade does not.
            val title = txt(item.first, 15f, T.ink3, 500, 21)
            val sub = txt(item.second, 12f, T.ink3, 400, 16)
            add(labels, title)
            add(labels, sub)
            add(line, labels, 0, -2, left = 12, weight = 1f)
            add(steps, line)
            checkSlots.add(slot)
            checkTitles.add(title)
            checkSubs.add(sub)
        }
        add(body, steps, top = 18)
        advanceChecking(Bridge.checkStage)
        centeredNote(body, iconText(R.drawable.ic_wifi_off, "No internet used. You can switch on airplane mode.", T.ink3, 12f, 13), 16)
        bottom(root, "Cancel", outlined = true) { goHome() }
        setContentView(root)
    }

    /** Step 1 and step 3 finish together when verdict() returns. Step 2 spins until explain() returns. */
    internal fun advanceChecking(stage: Int) {
        if (screen != "checking" || checkTitles.size < 3) return
        if (stage <= 0) {
            paintCheck(0, "run")
            paintCheck(1, "wait")
            paintCheck(2, "wait")
            return
        }
        paintCheck(0, "done")
        paintCheck(2, "done")
        // A known model failure will not write anything, so that step is finished with the verdict.
        if (stage >= 2 || modelProblem() != null) {
            paintCheck(1, "done")
            return
        }
        checkTitles[1].text = t("Llama 3.2 is writing an explanation")
        checkSubs[1].text = t("On-device · usually 2–4 s")
        paintCheck(1, "run")
    }

    private fun paintCheck(index: Int, state: String) {
        val slot = checkSlots.getOrNull(index) ?: return
        val title = checkTitles.getOrNull(index) ?: return
        slot.removeAllViews()
        when (state) {
            "run" -> {
                val spin = ProgressBar(this, null, android.R.attr.progressBarStyleSmall).apply {
                    indeterminateTintList = ColorStateList.valueOf(T.brand)
                    contentDescription = title.text
                }
                slot.addView(spin, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
            }
            "done" -> {
                val mark = ImageView(this).apply {
                    setImageResource(R.drawable.ic_check_circle)
                    setColorFilter(T.ok)
                    importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
                }
                slot.addView(mark, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
            }
            else -> {
                val dot = View(this).apply { background = shape(T.white, 12f, 2, T.outline2) }
                slot.addView(dot, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
            }
        }
        title.setTextColor(if (state == "wait") T.ink3 else T.ink)
    }

    private data class Palette(
        val fill: Int, val on: Int, val chip: Int, val chipText: Int, val number: Int,
        val glyph: Int, val iconFill: Int, val title: String, val hindi: String
    )
    private fun palette(level: String) = when (level) {
        "danger" -> Palette(T.danger, T.white, T.dangerC, T.onDanger, T.onDanger, R.drawable.ic_octagon_x, 0x2EFFFFFF, "DANGEROUS", "खतरनाक")
        "warn" -> Palette(T.warnBanner, T.onWarn, T.warnC, T.onWarnC, T.warn, R.drawable.ic_triangle_alert, 0x1F2B1B00, "SUSPICIOUS", "संदिग्ध")
        else -> Palette(T.okBanner, T.onOk, T.okBanner, T.onOk, T.onOk, R.drawable.ic_shield, T.white, "NO RISK FOUND", "कोई खतरा नहीं मिला")
    }
    private fun sentence(s: String): String = s.trim().replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
    private fun strings(a: JSONArray?): List<String> = if (a == null) emptyList() else (0 until a.length()).map { a.optString(it) }

    private fun verdictLine(evidence: List<String>, fallback: String, clear: Boolean): String {
        val raw = evidence.firstOrNull()
        val line = when {
            raw == null -> t(fallback)
            L10n.hindi -> {
                val translated = t(raw)
                if (translated != raw) {
                    val body = translated.trim()
                    if (body.endsWith("।") || body.endsWith(".") || body.endsWith("!") || body.endsWith("?")) body
                    else "$body।"
                } else sentence(raw).trimEnd('.', '!', '?') + "."
            }
            else -> sentence(raw).trimEnd('.', '!', '?') + "."
        }
        return if (clear) "$line ${t("That is not a guarantee it is safe.")}" else line
    }

    /** English keeps the existing "checked on this phone in …" line. Hindi uses the lookup. */
    private fun checkedMeta(mode: Int, elapsedMs: Double): String {
        val tail = formatMs(elapsedMs)
        val name = modeNames[mode.coerceIn(0, modeNames.lastIndex)]
        return if (L10n.hindi) "${t(name)} · ${t("checked on this phone")} · $tail"
        else "$name · checked on this phone in $tail"
    }

    private fun banner(p: Palette, why: String, meta: String, metaIcon: Int, stillVerify: Boolean = false): LinearLayout {
        val box = col().apply { background = shape(p.fill, 20f, if (stillVerify) 1 else 0, T.okLine); pad(this, 18, 18, 18, 16) }
        val top = row()
        val bubble = FrameLayout(this).apply {
            background = shape(p.iconFill, 26f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(icon(p.glyph, 30, if (stillVerify) T.ok else p.on), FrameLayout.LayoutParams(dp(30), dp(30), Gravity.CENTER))
        }
        add(top, bubble, 52, 52)
        val titles = col()
        val big = if (L10n.hindi) t(p.title).let { if (it != p.title) it else p.hindi } else p.title
        if (!L10n.hindi) add(titles, txt(p.hindi, 15f, p.on, 600, 20, raw = true))
        add(titles, txt(big, if (stillVerify) 25f else 28f, p.on, 800, 32, raw = true).apply {
            if (!containsIndic(big)) letterSpacing = .02f
            isAccessibilityHeading = true
        })
        if (stillVerify) {
            val verify = iconText(R.drawable.ic_alert_circle, "Still verify · फिर भी जाँच लें", T.onOk, 13f, 14).apply {
                background = shape(T.white, 13f, 1, T.okLine)
                pad(this, 8, 5, 8, 5)
            }
            val verifyLabel = verify.getChildAt(1) as TextView
            verifyLabel.maxLines = 3
            add(titles, verify, -2, -2, top = 6)
            cap(verifyLabel, titles, 40)
        }
        add(top, titles, 0, -2, left = 14, weight = 1f)
        add(box, top)
        add(box, txt(why, 16f, p.on, 500, 22), top = 12)
        val metaRow = iconText(metaIcon, meta, p.on, 12f, 14, flex = true).apply { alpha = .9f }
        (metaRow.getChildAt(1) as TextView).tag = "prahari-meta"
        add(box, metaRow, -1, -2, top = 10)
        return box
    }

    internal fun presentResult(job: Bridge.Job) {
        if (job.id >= 0 && !Bridge.mark(job.id, "result")) return
        shownId = job.id
        visibleJob = job
        selectedMode = job.mode.coerceIn(0, KINDS.lastIndex)
        inputValue = job.value
        screen = "result"
        networkBody = null
        val data = job.verdict
        val level = data.optString("level", "clear")
        val p = palette(level)
        val clear = level == "clear"
        val evidence = strings(data.optJSONArray("evidence"))
        val actions = strings(data.optJSONArray("actions"))
        val fallback = when (level) {
            "danger" -> "Strong scam signals found."
            "warn" -> "Some warning signs found."
            else -> "No scam signals found."
        }
        // The one-line "why" is the first evidence line (benign reading when the verdict is clear).
        val why = verdictLine(evidence, fallback, clear)
        val elapsed = if (job.totalMs >= 0) job.totalMs else SystemClock.elapsedRealtime() - job.started
        val root = root("${p.title}. ${p.hindi}")
        add(root, bar("Result", true, lang = true), -1, -2)
        val body = scrollBody(root)
        add(body, modeSwitcher(selectedMode, job.value), -1, -2)
        val b = banner(p, why, checkedMeta(selectedMode, elapsed.toDouble()), modeIcons[selectedMode], clear)
        metaText = b.findViewWithTag<TextView>("prahari-meta")
        data.optString("scam_type", "").takeIf { it.isNotBlank() }?.let { scam ->
            val kind = if (L10n.hindi) t(scam) else sentence(scam)
            add(b, txt(t("Type") + ": " + kind, 12f, p.on, 500, 16, raw = true), top = 8)
        }
        add(body, b, top = 12)
        b.post { if (!isDestroyed) b.announceForAccessibility("${p.title}. ${p.hindi}. $why") }
        val steps = card()
        add(steps, heading(if (clear) "Before you act" else "Do this now", if (clear) "कार्य करने से पहले" else "अभी यह करें"))
        val actionsHi = strings(data.optJSONArray("actions_hi"))
        actions.forEachIndexed { i, action ->
            val line = row().apply { gravity = Gravity.TOP }
            val number = txt("${i + 1}", 13f, p.number, 700).apply {
                gravity = Gravity.CENTER
                background = shape(p.chip, 13f)
                minWidth = dp(26)
                minHeight = dp(26)
                setPadding(dp(6), dp(2), dp(6), dp(2))
            }
            add(line, number, -2, -2)
            val textCol = col()
            val hi = actionsHi.getOrNull(i).orEmpty()
            if (L10n.hindi) {
                add(textCol, txt(hi.ifBlank { t(action) }, 15f, T.ink, 400, 21, raw = true))
            } else {
                add(textCol, txt(action, 15f, T.ink, 400, 21))
                if (hi.isNotBlank()) add(textCol, txt(hi, 13f, T.ink2, 400, 18, raw = true), top = 2)
            }
            add(line, textCol, 0, -2, left = 12, weight = 1f)
            add(steps, line, top = if (i == 0) 10 else 12)
        }
        val mode = job.mode
        val report = data.optJSONObject("report_buttons")
        if (mode != 2 && level == "warn") {
            val (en, hi) = buttonCopy(data, "lost_money_1930", "Lost money? Call 1930")
            divider(steps, 12)
            val lost = row().apply {
                gravity = Gravity.CENTER_VERTICAL
                minimumHeight = dp(48)
                setPadding(0, dp(8), 0, dp(8))
                setOnClickListener { dial() }
            }
            add(lost, icon(R.drawable.ic_phone, 16, T.ink2), 16, 16)
            val labels = col()
            val main = if (L10n.hindi) hi.ifBlank { t(en) } else en
            add(labels, txt(main, 13f, T.ink2, 600, 18, raw = L10n.hindi))
            if (!L10n.hindi && hi.isNotBlank()) add(labels, txt(hi, 12f, T.ink3, 400, 16, raw = true), top = 1)
            add(lost, labels, 0, -2, left = 6, weight = 1f)
            asButton(lost, reportDescription("lost_money_1930", en, hi))
            add(steps, lost)
        } else if (mode != 2 && report != null) {
            val primary = report.optJSONObject("primary")
            val secondary = report.optJSONObject("secondary")
            if (primary != null && secondary != null) {
                val buttons = row().apply { gravity = Gravity.TOP }
                fun place(which: JSONObject, outlined: Boolean, left: Int) {
                    val id = which.optString("id")
                    val en = which.optString("en")
                    val hi = which.optString("hi")
                    val dial = id == "lost_money_1930"
                    val main = if (L10n.hindi) hi.ifBlank { en } else en
                    val sub = if (L10n.hindi) "" else hi
                    val view = reportButton(
                        main, sub,
                        if (dial) R.drawable.ic_phone else R.drawable.ic_external,
                        if (dial || level == "danger") T.danger else T.brand,
                        if (outlined) T.ink else T.white,
                        if (outlined) T.ink2 else Color.argb(230, 255, 255, 255),
                        outlined,
                        reportDescription(id, en, hi)
                    ) { openReport(id) }
                    add(buttons, view, 0, -2, left = left, weight = 1f)
                }
                place(primary, false, 0)
                place(secondary, true, 8)
                add(steps, buttons, top = 14)
            }
        }
        if (clear) {
            divider(steps, 12)
            add(steps, iconText(R.drawable.ic_alert_circle, "Scammers copy real messages. If it asks for money or a code, check in the official app first.", T.ink2, 13f, 16, flex = true).apply {
                minimumHeight = dp(48)
                setPadding(0, dp(8), 0, dp(8))
            }, top = 8)
        }
        add(body, steps, top = 12)
        if (evidence.isNotEmpty()) {
            val evidenceCard = card()
            val header = row()
            add(header, heading(if (clear) "What we saw" else "Why it's flagged", "संकेत"), 0, -2, weight = 1f)
            val countWord = t(if (evidence.size == 1) "signal" else "signals")
            add(header, txt("${evidence.size} $countWord", 11f, T.ink3, 600, raw = true), -2, -2)
            add(evidenceCard, header)
            evidence.forEach { item ->
                val chip = row().apply { gravity = Gravity.TOP; background = shape(p.chip, 12f); pad(this, 10, 8, 12, 8) }
                add(chip, icon(if (clear) R.drawable.ic_check_circle else R.drawable.ic_alert_circle, 16, p.chipText), 16, 16)
                val translated = if (L10n.hindi) t(item) else item
                val shown = if (L10n.hindi && translated != item) translated else sentence(item)
                val text = SpannableString(shown)
                Regex("[a-z0-9-]+(\\.[a-z0-9-]+)+").findAll(text).forEach { match ->
                    text.setSpan(TypefaceSpan("monospace"), match.range.first, match.range.last + 1, 0)
                    text.setSpan(StyleSpan(Typeface.BOLD), match.range.first, match.range.last + 1, 0)
                    text.setSpan(RelativeSizeSpan(13f / 14f), match.range.first, match.range.last + 1, 0)
                }
                add(chip, txt(text, 14f, p.chipText, 400, 20), 0, -2, left = 8, weight = 1f)
                add(evidenceCard, chip, -1, -2, top = 8)
            }
            add(body, evidenceCard, top = 12)
        }
        val llama = card(T.surface2, false)
        add(llama, iconText(R.drawable.ic_cpu, "Explained on this phone by Llama 3.2", T.ink2, 13f, 18, flex = true))
        val explainRow = row().apply { gravity = Gravity.TOP; isBaselineAligned = false }
        val accent = View(this).apply {
            setBackgroundColor(T.brand)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        add(explainRow, accent, 3, -1)
        val known = modelProblem()
        val placeholder = if (known == null) "Writing an explanation on this phone…"
        else "Explanation unavailable on this phone. The verdict and the steps above are complete.\n$known"
        explanationText = txt(placeholder, 15f, T.ink2, 400, 22).apply {
            if (known == null) setTypeface(typeface, Typeface.ITALIC)
            includeFontPadding = true
            isFallbackLineSpacing = true
            lineHeight = maxOf(lineHeight, (textSize * 1.6f).toInt())
            accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
        }
        add(explainRow, explanationText!!, 0, -2, left = 12, weight = 1f)
        // The accent matches the explanation text, including after Llama replaces the placeholder.
        explanationText!!.addOnLayoutChangeListener { v, _, _, _, _, _, _, _, _ ->
            val h = v.height
            if (h > 0 && accent.layoutParams.height != h) {
                v.post {
                    if (!isDestroyed && accent.layoutParams.height != h) {
                        accent.layoutParams.height = h
                        accent.requestLayout()
                    }
                }
            }
        }
        add(llama, explainRow, top = 12)
        add(llama, iconText(R.drawable.ic_info, "AI-written and can be wrong. Follow the steps above.", T.ink2, 12f, 14, flex = true), top = 12)
        if (L10n.hindi) add(llama, txt(L10n.n("ai_english"), 12f, T.ink3, 600, 16, raw = true), top = 6)
        add(body, llama, top = 12)
        val stats = card()
        val header = row().apply { minimumHeight = dp(48) }
        statsHeader = header
        add(header, icon(R.drawable.ic_cpu, 18, T.ink2), 18, 18)
        add(header, txt("On-device stats", 14f, T.ink2, 600), 0, -2, left = 10, weight = 1f)
        statsSummary = txt("— · …", 12f, T.ink3, 500)
        add(header, statsSummary!!, -2, -2)
        val chevron = icon(R.drawable.ic_chevron_down, 20, T.ink2)
        add(header, chevron, 20, 20, left = 8)
        asButton(header, "On-device stats, collapsed")
        add(stats, header)
        statsDetails = col().apply { visibility = View.GONE }
        add(stats, statsDetails!!)
        header.setOnClickListener {
            val details = statsDetails ?: return@setOnClickListener
            val open = details.visibility != View.VISIBLE
            details.visibility = if (open) View.VISIBLE else View.GONE
            chevron.rotation = if (open) 180f else 0f
            describeStats(open)
        }
        fillStats(data, null, null, null)
        add(body, stats, top = 12)
        val checked = card()
        add(checked, heading("You checked", "आपने जाँचा"))
        add(checked, txt(job.value, 14f, T.ink2, 400, 20, raw = true).apply {
            setTextIsSelectable(true)
            if (mode != 0) typeface = Typeface.MONOSPACE
        }, top = 10)
        add(body, checked, top = 12)
        bottom(root, "Check another · दूसरा जाँचें") { goHome(true) }
        setContentView(root)
        if (job.explanation != null) applyExplanation(job)
    }

    private fun formatMs(value: Double): String {
        if (!value.isFinite() || value < 0) return "—"
        return if (value < 1000) "${value.toInt()} ms" else String.format(Locale.US, "%.2f s", value / 1000)
    }

    private fun describeStats(expanded: Boolean) {
        val header = statsHeader ?: return
        val summary = statsSummary?.text ?: ""
        header.contentDescription = "On-device stats, ${if (expanded) "expanded" else "collapsed"}. $summary"
        if (Build.VERSION.SDK_INT >= 30) header.stateDescription = if (expanded) "Expanded" else "Collapsed"
    }

    private fun fillStats(data: JSONObject, llm: JSONObject?, total: Long?, pss: Double?) {
        val details = statsDetails ?: return
        val summary = statsSummary ?: return
        details.removeAllViews()
        val tiles = row()
        val values = listOf(
            formatMs(data.optDouble("detector_ms", Double.NaN)),
            formatMs(llm?.optDouble("first_token_ms", Double.NaN) ?: Double.NaN),
            llm?.optDouble("decode_tps", Double.NaN)?.takeIf { it.isFinite() }?.let { String.format(Locale.US, "%.1f t/s", it) } ?: "—"
        )
        listOf("Detector", "First token", "Decode speed").forEachIndexed { i, label ->
            val tile = col().apply { background = shape(T.surface2, 12f); pad(this, 10, 10, 10, 10) }
            add(tile, txt(values[i], 17f, T.ink, 700).apply { maxLines = 2 })
            add(tile, txt(label, 11f, T.ink2, 500).apply { maxLines = 2 }, top = 4)
            add(tiles, tile, 0, -2, left = if (i == 0) 0 else 8, weight = 1f)
        }
        add(details, tiles, top = 4)
        val abi = Build.SUPPORTED_ABIS.firstOrNull() ?: "—"
        val foot = "Total ${total?.let { formatMs(it.toDouble()) } ?: "—"} · Memory ${pss?.let { String.format(Locale.US, "%.1f MB", it) } ?: "—"}\nLlama 3.2 1B INT4 · ExecuTorch · XNNPACK\nCPU ABI: $abi" +
            if (abi.startsWith("x86")) "\nx86 emulator: not Arm timings" else ""
        add(details, txt(foot, 12f, T.ink3, 400, 18).apply { typeface = Typeface.MONOSPACE }, top = 12)
        summary.text = "${values[0]} · ${values[1]}"
        describeStats(details.visibility == View.VISIBLE)
    }

    internal fun applyExplanation(job: Bridge.Job) {
        if (shownId != job.id) return
        val view = explanationText ?: return
        val result = job.explanation ?: return
        val error = result.optString("error", "")
        val explanation = result.optString("explanation", "").trim()
        if (error.isNotEmpty() || explanation.isEmpty()) {
            val lead = when {
                error.contains("Model files are missing", ignoreCase = true) ->
                    "The model files are not on this phone, so Llama did not write an explanation. The verdict and the steps above are complete."
                error.contains("Failed to load", ignoreCase = true) || error.contains("Couldn't load", ignoreCase = true) ->
                    "Llama could not be loaded on this phone. The verdict and the steps above are complete."
                else -> "Explanation unavailable on this phone. The verdict and the steps above are complete."
            }
            val shown = t(lead)
            view.text = if (error.isNotEmpty()) "$shown\n$error" else shown
            view.setTextColor(T.ink2)
            view.setTypeface(view.typeface, Typeface.ITALIC)
        } else {
            view.text = explanation
            view.setTextColor(T.ink)
            view.typeface = Typeface.DEFAULT
            view.includeFontPadding = true
            view.isFallbackLineSpacing = true
            view.lineHeight = maxOf(view.lineHeight, (view.textSize * 1.6f).toInt())
        }
        val total = job.totalMs.takeIf { it >= 0 }
        val pss = job.pssMb.takeIf { it.isFinite() }
        fillStats(job.verdict, result.optJSONObject("llm"), total, pss)
        metaText?.text = checkedMeta(job.mode, (total ?: -1L).toDouble())
    }

    private fun launch(intent: Intent) {
        try {
            startActivity(intent)
        } catch (e: Exception) {
            toast("Unable to open: ${errorText(e)}")
        }
    }
    private fun dial() = launch(Intent(Intent.ACTION_DIAL, Uri.parse("tel:1930")))

    private fun openReport(id: String) {
        when (id) {
            "lost_money_1930" -> dial()
            "report_chakshu" -> launch(Intent(Intent.ACTION_VIEW, Uri.parse("https://sancharsaathi.gov.in")))
            else -> launch(Intent(Intent.ACTION_VIEW, Uri.parse("https://cybercrime.gov.in")))
        }
    }

    private fun buttonCopy(data: JSONObject, id: String, fallback: String): Pair<String, String> {
        val item = data.optJSONObject("buttons")?.optJSONObject(id)
        val en = item?.optString("en")?.takeIf { it.isNotBlank() } ?: fallback
        val hi = item?.optString("hi").orEmpty()
        return en to hi
    }

    private fun reportDescription(id: String, en: String, hi: String): String {
        val where = when (id) {
            "lost_money_1930" -> t("Opens the phone dialler.")
            "report_chakshu" -> t("Opens sancharsaathi.gov.in in the browser.")
            else -> t("Opens cybercrime.gov.in in the browser.")
        }
        return listOf(en, hi).filter { it.isNotBlank() }.joinToString(". ") + ". " + where
    }

    private fun reportButton(
        en: String, hi: String, iconId: Int, fill: Int, textColor: Int, hiColor: Int,
        outlined: Boolean, description: String, action: () -> Unit
    ): LinearLayout = row().apply {
        gravity = Gravity.CENTER_VERTICAL
        minimumHeight = dp(48)
        setPadding(dp(10), dp(8), dp(10), dp(8))
        background = ripple(shape(if (outlined) T.white else fill, 16f, if (outlined) 1 else 0, T.outline2))
        add(this, icon(iconId, 20, textColor), 20, 20)
        val labels = col()
        val enView = txt(en, 14f, textColor, 600, 18).apply {
            maxLines = 4
            ellipsize = TextUtils.TruncateAt.END
        }
        add(labels, enView)
        val hiView = if (hi.isNotBlank()) txt(hi, 12f, hiColor, 400, 16).apply {
            maxLines = 4
            ellipsize = TextUtils.TruncateAt.END
        } else null
        if (hiView != null) add(labels, hiView, top = 1)
        add(this, labels, 0, -2, left = 8, weight = 1f)
        setOnClickListener { action() }
        asButton(this, description)
        addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
            if (width <= 0) return@addOnLayoutChangeListener
            val max = (width - paddingLeft - paddingRight - dp(28)).coerceAtLeast(dp(48))
            if (enView.maxWidth != max) enView.maxWidth = max
            if (hiView != null && hiView.maxWidth != max) hiView.maxWidth = max
        }
    }

    private fun showNetwork(rerun: Boolean) {
        Bridge.enterNetwork(rerun)
        screen = "network"
        visibleJob = null
        val root = root("Network check")
        add(root, bar("Network check", false), -1, -2)
        val body = scrollBody(root)
        networkBody = body
        bottom(root, "Run again", true, R.drawable.ic_refresh) { showNetwork(true) }
        setContentView(root)
        val existing = Bridge.net
        if (!rerun && existing != null && existing.id == Bridge.netId && existing.done) {
            renderNetwork(body, existing)
        } else if (!rerun && existing != null && existing.id == Bridge.netId && !existing.done) {
            add(body, txt("Testing HTTPS…", 16f, T.ink2).apply {
                accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
            }, top = 16)
        } else {
            val id = ++Bridge.netId
            Bridge.net = Bridge.Net(id, "pending", "", 0L, false)
            add(body, txt("Testing HTTPS…", 16f, T.ink2).apply {
                contentDescription = "Testing whether this app can open a connection"
                accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
            }, top = 16)
            enqueueNet(id)
        }
    }

    internal fun renderNetwork(body: LinearLayout, net: Bridge.Net) {
        if (isDestroyed || screen != "network") return
        body.removeAllViews()
        val connected = net.code == "ok"
        val blocked = net.code == "blocked" || net.code == "security"
        val p = when {
            connected -> Palette(T.danger, T.white, T.dangerC, T.onDanger, T.onDanger, R.drawable.ic_octagon_x, 0x2EFFFFFF, "CONNECTED", "कनेक्शन सफल")
            blocked -> Palette(T.brand, T.white, T.brandC, T.brand, T.brand, R.drawable.ic_wifi_off, 0x2EFFFFFF, "NO INTERNET / blocked by Android", "इंटरनेट नहीं")
            else -> Palette(T.warnBanner, T.onWarn, T.warnC, T.onWarnC, T.warn, R.drawable.ic_triangle_alert, 0x1F2B1B00, "Could not connect", "कनेक्ट नहीं हो सका")
        }
        val why = when {
            connected -> "This app reached the internet. The offline claim failed on this build."
            blocked -> "This app cannot connect. Android blocked the request because Prahari has no internet permission."
            else -> "This alone does not prove the app is offline."
        }
        val banner = banner(p, why, "Tested just now · took ${net.elapsed} ms", R.drawable.ic_lock)
        add(body, banner)
        banner.post { if (!isDestroyed) banner.announceForAccessibility("${p.title}. ${p.hindi}. $why") }
        val tried = card()
        add(tried, heading("What we tried", "हमने क्या आज़माया"))
        fun pairRow(key: String, value: View) {
            val line = row().apply { minimumHeight = dp(48) }
            add(line, txt(key, 13f, T.ink2), 0, -2, weight = 1f)
            add(line, value, -2, -2)
            add(tried, line)
        }
        pairRow("Request", txt("HTTPS GET example.com", 12f, T.ink).apply { typeface = Typeface.MONOSPACE })
        divider(tried)
        val resultLabel = when {
            connected -> "Connected"
            blocked -> "Blocked"
            else -> "Could not connect"
        }
        val resultColor = when {
            connected -> T.onDanger
            blocked -> T.onOk
            else -> T.onWarnC
        }
        val resultFill = when {
            connected -> T.dangerC
            blocked -> T.okBanner
            else -> T.warnC
        }
        pairRow("Result", txt(resultLabel, 12f, resultColor, 700).apply {
            background = shape(resultFill, 12f)
            pad(this, 10, 5, 10, 5)
        })
        if (net.message.isNotEmpty()) {
            divider(tried)
            add(tried, txt(net.message, 12f, T.ink2, 400, 17).apply {
                typeface = Typeface.MONOSPACE
                background = shape(T.surface2, 10f)
                pad(this, 12, 10, 12, 10)
                setTextIsSelectable(true)
            }, top = 8)
        }
        add(body, tried, top = 12)
        if (blocked) {
            val means = card()
            add(means, heading("What this means", "इसका मतलब"))
            val abi = Build.SUPPORTED_ABIS.firstOrNull() ?: ""
            val cpu = if (abi.startsWith("x86")) "The detector and Llama 3.2 run on this emulator's CPU."
            else "The detector and Llama 3.2 run on this phone's Arm CPU."
            listOf(
                "Messages and links you check never leave this phone.",
                cpu,
                "Calls to 1930, Sanchar Saathi Chakshu or cybercrime.gov.in use your phone's dialler and browser, not this app."
            ).forEach {
                val line = row().apply { gravity = Gravity.TOP }
                add(line, icon(R.drawable.ic_check_circle, 20, T.ok), 20, 20)
                add(line, txt(it, 14f, T.ink, 400, 20), 0, -2, left = 12, weight = 1f)
                add(means, line, top = 12)
            }
            add(body, means, top = 12)
        }
    }

    private fun showAbout() {
        val dialog = Dialog(this)
        aboutDialog = dialog
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE)
        dialog.setOnDismissListener {
            if (aboutDialog === dialog) aboutDialog = null
            ignoreBackUntil = SystemClock.uptimeMillis() + 350
        }
        val sheet = col().apply {
            background = GradientDrawable().apply {
                setColor(T.white)
                val radius = 28f * density
                cornerRadii = floatArrayOf(radius, radius, radius, radius, 0f, 0f, 0f, 0f)
            }
            pad(this, 20, 8, 20, 12)
        }
        val handle = View(this).apply {
            background = shape(T.outline2, 2f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        sheet.addView(handle, LinearLayout.LayoutParams(dp(36), dp(4)).apply { gravity = Gravity.CENTER_HORIZONTAL })
        val head = row()
        add(head, logo(), 36, 36)
        val title = col()
        add(title, txt("How Prahari works", 20f, T.ink, 700, 26).apply { isAccessibilityHeading = true })
        add(title, txt("प्रहरी कैसे काम करता है", 13f, T.ink3, 500, 18))
        add(head, title, 0, -2, left = 12, weight = 1f)
        add(sheet, head, top = 14)
        val descriptions = listOf(
            Triple(R.drawable.ic_wifi_off, "Runs fully offline", "The app has no internet permission, so nothing you check can be sent anywhere. Airplane mode works."),
            Triple(R.drawable.ic_cpu, "Llama 3.2 1B on this phone", "Runs on the phone's CPU through ExecuTorch (INT4, XNNPACK). It only writes the explanation."),
            Triple(R.drawable.ic_shield_check, "A detector decides the verdict", "Scam signals are checked by the detector. The verdict never depends on the AI text."),
            Triple(R.drawable.ic_list, "Safety steps are fixed", "Steps come from a vetted list (Sanchar Saathi Chakshu, 1930, cybercrime.gov.in), never from the AI."),
            Triple(R.drawable.ic_alert_circle, "Best effort, not a guarantee", "No checker catches every scam. If in doubt, don't pay; report on Sanchar Saathi Chakshu, or call 1930 if money was lost.")
        )
        descriptions.forEachIndexed { i, item ->
            if (i > 0) divider(sheet)
            val line = row().apply { gravity = Gravity.TOP; pad(this, 0, 11, 0, 11) }
            val tile = FrameLayout(this).apply {
                background = shape(T.brandC, 12f)
                importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
                addView(icon(item.first, 20, T.brand), FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER))
            }
            add(line, tile, 36, 36)
            val text = col()
            add(text, txt(item.second, 15f, T.ink, 600, 20))
            add(text, txt(item.third, 13f, T.ink2, 400, 18), top = 2)
            add(line, text, 0, -2, left = 14, weight = 1f)
            add(sheet, line)
        }
        add(sheet, button("Got it") { dialog.dismiss() }.apply { minimumHeight = dp(56) }, -1, -2, top = 8)
        add(sheet, txt("Built for the Arm Bharat AI-SoC Challenge 2026", 12f, T.ink3, 400, 16).apply { gravity = Gravity.CENTER }, top = 12)
        val column = col()
        val spacer = View(this).apply {
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            setOnClickListener { dialog.dismiss() }
        }
        column.addView(spacer, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        column.addView(sheet)
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            fitsSystemWindows = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(column, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        }
        dialog.setContentView(scroll)
        dialog.window?.apply {
            setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
            addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND)
            setDimAmount(.52f)
            setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            setGravity(Gravity.BOTTOM)
            setTitle(t("How Prahari works"))
        }
        dialog.show()
        dialog.window?.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
    }

    override fun onDestroy() {
        aboutDialog?.setOnDismissListener(null)
        aboutDialog?.dismiss()
        aboutDialog = null
        if (Build.VERSION.SDK_INT >= 33) {
            backCallback?.let { callback ->
                try { onBackInvokedDispatcher.unregisterOnBackInvokedCallback(callback) } catch (_: Throwable) {}
            }
        }
        backCallback = null
        if (Bridge.host === this) Bridge.host = null
        // Rotation keeps the loaded module. Leaving the app closes it after generate returns.
        if (isFinishing) Bridge.closeModel()
        super.onDestroy()
    }
}
