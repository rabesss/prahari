package `in`.prahari.app

import android.app.Activity
import android.app.Dialog
import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.ImageDecoder
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.SystemClock
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.text.Editable
import android.text.SpannableString
import android.text.TextPaint
import android.text.TextUtils
import android.text.TextWatcher
import android.text.style.MetricAffectingSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import android.text.format.DateUtils
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.WindowInsets
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
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
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
    // NO RISK is slate, not green: a clear result must not look like a promise of safety.
    val slateBg = Color.parseColor("#ECEFF1"); val slateInk = Color.parseColor("#263238")
    val slateLine = Color.parseColor("#B0BEC5")
}

private const val MODEL_FILE = "Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte"
private const val TOKENIZER_FILE = "tokenizer.model"
private val KINDS = arrayOf("sms", "url", "flow")
/**
 * An app file (.apk) check. Not in [KINDS]: the home screen's SMS / Link / Network choice stays
 * 0..2, and only a job's own mode is ever [APK_MODE]. See ApkInspector and apk_check.py.
 */
internal const val APK_MODE = 3
private fun kindName(mode: Int) = if (mode == APK_MODE) "apk" else KINDS.getOrElse(mode) { "?" }
private const val DEBIT_STEP = "Didn't make this payment? Call 1930 and block the card or UPI in your bank app."
private const val CHECK_STEP = "Check the payment in your bank app, not through any link or number in the message."
// Hosts in any script (internationalised domains such as a Devanagari .भारत name count too).
private val OWN_HOST = Regex("(?i)(?<![\\p{L}\\p{M}\\p{N}_-])((?:[\\p{L}\\p{N}][\\p{L}\\p{M}\\p{N}-]*\\.)+\\p{L}[\\p{L}\\p{M}]{1,23})(?![\\p{L}\\p{M}\\p{N}_-])")
private val OWN_URL = Regex("(?i)(?:https?://|www\\.)([^\\s/?#<>\"']+)")
private val OWN_IP = Regex("\\b\\d{1,3}(?:\\.\\d{1,3}){3}\\b")
private val OWN_MOBILE = Regex("(?<![0-9])(?:\\+?91[ -]?)?[6-9][0-9]{4}[ -]?[0-9]{5}(?![0-9])")
private val OWN_OTHER = Regex("(?i)\\.apk\\b|\\*\\d{2,3}\\*")
// Sites a genuine bank alert may name. Any other host, an IP, an APK, a USSD forwarding code or a
// private mobile number is a contact of the sender's own.
private val OFFICIAL_HOSTS = listOf(
    "sbi.co.in", "onlinesbi.sbi", "sbicard.com", "hdfcbank.com", "icicibank.com", "axisbank.com", "kotak.com",
    "bankofbaroda.in", "bankofbaroda.co.in", "bobcard.co.in", "pnbindia.in", "idfcfirstbank.com", "indusind.com",
    "federalbank.co.in", "yesbank.in", "canarabank.com", "unionbankofindia.co.in", "aubank.in", "rblbank.com",
    "iob.in", "bankofindia.co.in", "centralbankofindia.co.in", "indianbank.in", "paytm.com", "phonepe.com", "npci.org.in",
)
private val OFFICIAL_SUFFIXES = listOf(".gov.in", ".nic.in", ".bank.in")

private fun officialHost(host: String): Boolean {
    val h = host.lowercase()
    return OFFICIAL_HOSTS.any { h == it || h.endsWith(".$it") } || OFFICIAL_SUFFIXES.any { h.endsWith(it) }
}

/** True when the text offers a contact of its own: an unofficial link, IP, APK, USSD code or private mobile. */
private fun hasOwnContact(text: String): Boolean =
    OWN_MOBILE.containsMatchIn(text) || OWN_IP.containsMatchIn(text) || OWN_OTHER.containsMatchIn(text) ||
        OWN_HOST.findAll(text).any { !officialHost(it.groupValues[1]) } ||
        OWN_URL.findAll(text).any { !officialHost(it.groupValues[1].substringBefore(':').trimEnd('.', ',', ')', ']')) }

/**
 * How a result that carries the vetted bank debit or check step is shown, or null for no change.
 * "alert": the amber CHECK THIS ALERT banner (no contact of the sender's own). "warn": SUSPICIOUS,
 * because a copied alert that sends the reader to its own link or number is never NO RISK. A
 * DANGEROUS verdict is never changed. The result screen and History both use this.
 */
private fun bankAlertLevel(verdict: JSONObject, value: String): String? {
    val level = verdict.optString("level", "clear")
    if (level != "clear" && level != "warn") return null
    // A personal-mobile sender already raised this result to SUSPICIOUS with its own evidence line;
    // the amber CHECK THIS ALERT banner would hide that line, so the level is left as it is.
    if (verdict.has("sender_raised")) return null
    val actions = verdict.optJSONArray("actions") ?: return null
    val vetted = (0 until actions.length()).any { val a = actions.optString(it); a == DEBIT_STEP || a == CHECK_STEP }
    if (!vetted) return null
    return if (hasOwnContact(value)) "warn" else "alert"
}

private const val OWN_CONTACT_LINE = "Sends you to its own link or number; real bank alerts point to the bank app or a toll-free line"
private const val RAISED_NOTE = "This alert names its own link or number, so it is marked suspicious. The AI note was written for the first reading, so it is not shown."
private const val ALERT_LINE = "Looks like a bank alert. Scammers copy these, so check it in your bank app."
private const val TAG = "Prahari"
/**
 * Wall-clock budget for the whole Llama stage of one check (every retry included), from the moment
 * the verdict is on screen. Past it, generation is stopped and the reader gets the detector's fixed
 * text. A warm check takes about 1.2 s on a cool Galaxy S23 and about 3 s when it is hot.
 */
internal const val LLAMA_BUDGET_MS = 15_000L
/** One JSON line per finished check, numbers only (no checked text, no explanation). adb_bench.py reads it. */
private const val PERF_TAG = "PrahariPerf"
/** Debug builds only: "all" or "flagged-only", so the adb harness can set the gating mode at launch. */
internal const val GATING_EXTRA = "in.prahari.app.extra.GATING"
internal const val PREF_EXPLAIN_CLEARED = "explain_cleared"
private const val QR_REQUEST = 41

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

/**
 * Load the single process-wide module. A second [LlmModule] is never constructed
 * while one is alive. Call only from [Bridge.worker].
 */
private fun ensureLoaded(): LlmModule {
    Bridge.module?.let { return it }
    synchronized(Bridge.moduleLock) {
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
        val raced = Bridge.module
        if (raced != null) {
            try { created.close() } catch (_: Throwable) {}
            return raced
        }
        Bridge.module = created
        Bridge.loadError = null
        Bridge.missing = null
        return created
    }
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
        val verdict: JSONObject,
        /** Where the text came from ('qr', 'whatsapp', 'sms' or ''): a hint for the report only. */
        val source: String = "",
        /** Optional sender typed for this check (message mode only); never stored in History. */
        val sender: String = ""
    ) {
        @Volatile var explanation: JSONObject? = null
        @Volatile var totalMs: Long = -1L
        @Volatile var pssMb: Double = Double.NaN
        @Volatile var verdictCallMs: Double = Double.NaN
    }

    class Net(val id: Int, val code: String, val message: String, val elapsed: Long, val done: Boolean)

    val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "prahari-model").apply { isDaemon = true }
    }
    val netWorker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "prahari-net").apply { isDaemon = true }
    }
    val genLock = ReentrantLock()
    val moduleLock = Any()
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
    /** Mode and text of the check in flight, for a rotation before its verdict is published. */
    @Volatile var pendingMode = 0
    @Volatile var pendingValue = ""
    @Volatile var netId = 0
    @Volatile var net: Net? = null
    /** 0 verdict still running, 1 verdict back (Llama writing), 2 explanation back. */
    @Volatile var checkStage = 0
    /**
     * False (the default) is flagged-only gating: a result shown as NO RISK gets the detector's
     * fixed text and no Llama call. DANGEROUS and SUSPICIOUS results always get Llama.
     */
    @Volatile var explainCleared = false
    val perfSeq = AtomicInteger(0)
    /** Distinguishes this process's PrahariPerf lines from an earlier run's still in logcat. */
    val perfSession: String = java.lang.Long.toHexString(System.nanoTime() xor System.currentTimeMillis())

    fun gatingName() = if (explainCleared) "all" else "flagged-only"

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
            val open: LlmModule?
            synchronized(moduleLock) {
                open = module
                module = null
            }
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
                val loadStart = SystemClock.elapsedRealtime()
                try {
                    ensureLoaded()
                    Bridge.loadError = null
                } catch (t: Throwable) {
                    Bridge.loadError = errorText(t)
                    Log.e(TAG, "model load failed", t)
                }
                logModel(SystemClock.elapsedRealtime() - loadStart)
            } else {
                logModel(null)
            }
        } catch (t: Throwable) {
            Bridge.loadError = errorText(t)
            Log.e(TAG, "model probe failed", t)
        }
        Bridge.ui { if (it.screen == "home") it.bindModelStatus() }
    }
}

private fun enqueueCheck(id: Int, mode: Int, value: String, started: Long, source: String, sender: String, payload: String = "") {
    Bridge.worker.execute {
        try {
            runCheck(id, mode, value, started, source, sender, payload)
        } catch (t: Throwable) {
            Log.e(TAG, "check escaped", t)
        }
    }
}

/**
 * [payload] is the app file's facts JSON for [APK_MODE] (read by [readApk]) and empty for text checks.
 */
private fun runCheck(id: Int, mode: Int, value: String, started: Long, source: String, sender: String, payload: String = "") {
    try {
        if (!Bridge.still(id)) return
        if (Bridge.pythonError != null || !Python.isStarted()) {
            throw IllegalStateException(Bridge.pythonError ?: "Python is not running")
        }
        val apk = mode == APK_MODE
        // apk_check has the same verdict / explain / vetted_explanation calls as mobile.
        val bridge = Python.getInstance().getModule(if (apk) "apk_check" else "mobile")
        val callStart = SystemClock.elapsedRealtimeNanos()
        val verdict = JSONObject(
            if (apk) bridge.callAttr("verdict", payload).toString()
            else bridge.callAttr("verdict", KINDS[mode], value, source, sender).toString()
        )
        val verdictCallMs = (SystemClock.elapsedRealtimeNanos() - callStart) / 1e6
        val level = verdict.optString("level")
        if (level != "danger" && level != "warn" && level != "clear") {
            throw IllegalStateException("Invalid detector verdict")
        }
        if (!Bridge.still(id)) return
        val job = Bridge.Job(id, mode, value, started, verdict, source, sender)
        job.verdictCallMs = verdictCallMs
        // Flagged-only gating: only a result the screen shows as NO RISK skips Llama. A bank alert
        // the app relabels (CHECK THIS ALERT or SUSPICIOUS) is not NO RISK, so it keeps Llama.
        val gating = Bridge.gatingName()
        val skipLlama = !Bridge.explainCleared && level == "clear" && bankAlertLevel(verdict, value) == null
        if (!Bridge.publish(id, job)) return
        Bridge.app?.let { ctx ->
            try {
                HistoryStore.add(ctx, mode, bankAlertLevel(verdict, value) ?: level, value)
            } catch (t: Throwable) {
                Log.e(TAG, "history save failed", t)
            }
        }
        // Step 1 and the safety steps are both done once verdict() returns. Step 2 keeps spinning.
        Bridge.checkStage = 1
        Bridge.ui { act ->
            if (!Bridge.still(id)) return@ui
            if (act.screen == "checking") act.advanceChecking(1)
            if (act.screen != "result" || act.shownId != id) act.presentResult(job)
        }
        if (!Bridge.still(id)) return
        val explanation = try {
            val missing = if (skipLlama) null else missingMessage()
            if (!skipLlama) Bridge.missing = missing
            when {
                skipLlama -> JSONObject(bridge.callAttr("vetted_explanation").toString())
                missing != null -> JSONObject().put("error", missing)
                Bridge.pythonError != null -> JSONObject().put("error", Bridge.pythonError)
                else -> JSONObject(bridge.callAttr("explain", Runner(id, SystemClock.elapsedRealtime() + LLAMA_BUDGET_MS)).toString())
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
        logPerf(job, gating)
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
        val detail = errorText(t)
        Bridge.ui { act ->
            if (!Bridge.still(id)) return@ui
            if (mode in KINDS.indices) {
                act.inputValue = value
                act.senderValue = sender
                act.selectedMode = mode
            }
            act.showHome()
            act.failureToast(detail)
        }
    }
}

/**
 * Read an app file on its own thread, under check [id], then queue the verdict on the model worker.
 * A content provider that stalls holds only this thread: Cancel or a newer check moves on, and
 * the model worker stays free for the next check.
 */
private fun readApk(id: Int, uri: Uri, started: Long) {
    Thread({
        fun failed(key: String) {
            if (!Bridge.still(id)) return
            Bridge.fail(id)
            Bridge.ui { act -> if (Bridge.still(id)) act.apkFailed(key) }
        }
        try {
            val ctx = Bridge.app ?: throw IllegalStateException("App context is not ready")
            val facts = ApkInspector.read(ctx, uri) { Bridge.still(id) }
            if (!Bridge.still(id)) return@Thread
            Bridge.pendingValue = facts.display
            enqueueCheck(id, APK_MODE, facts.display, started, "", "", facts.json.toString())
        } catch (e: ApkInspector.Unreadable) {
            failed(e.key)
        } catch (_: ApkInspector.Stopped) {
        } catch (t: Throwable) {
            Log.e(TAG, "app file read failed", t)
            failed("apk_fail")
        }
    }, "prahari-apk").apply { isDaemon = true }.start()
}

private fun putNum(rec: JSONObject, key: String, value: Double?) {
    rec.put(key, if (value != null && value.isFinite() && value >= 0) value else JSONObject.NULL)
}

/** The preload finished (or was not needed). The harness waits for this before its first check. */
private fun logModel(loadMs: Long?) {
    try {
        val state = when {
            Bridge.module != null -> "ready"
            Bridge.missing != null -> "missing"
            else -> "error"
        }
        val rec = JSONObject().put("event", "model").put("session", Bridge.perfSession)
            .put("seq", Bridge.perfSeq.incrementAndGet()).put("state", state).put("gating", Bridge.gatingName())
        putNum(rec, "load_ms", loadMs?.toDouble())
        Log.i(PERF_TAG, rec.toString())
    } catch (_: Throwable) {}
}

/** One line per finished check for the adb harness. Numbers and labels only; never the checked text. */
private fun logPerf(job: Bridge.Job, gating: String) {
    try {
        val ex = job.explanation
        val llm = ex?.optJSONObject("llm")
        fun num(key: String) = llm?.optDouble(key, Double.NaN)
        val rec = JSONObject()
            .put("event", "result")
            .put("session", Bridge.perfSession)
            .put("seq", Bridge.perfSeq.incrementAndGet())
            .put("id", job.id)
            .put("kind", kindName(job.mode))
            .put("level", job.verdict.optString("level"))
            .put("gating", gating)
            .put("llama_skipped", ex?.optBoolean("llama_skipped") == true)
            .put("fallback", ex?.optString("fallback")?.takeIf { it.isNotEmpty() } ?: JSONObject.NULL)
            .put("error", ex == null || ex.has("error"))
        putNum(rec, "detector_ms", job.verdict.optDouble("detector_ms", Double.NaN))
        putNum(rec, "verdict_call_ms", job.verdictCallMs)
        putNum(rec, "prompt_tokens", num("prompt_tokens"))
        putNum(rec, "prefill_ms", num("prefill_ms"))
        putNum(rec, "prefill_tps", num("prefill_tps"))
        putNum(rec, "first_token_ms", num("first_token_ms"))
        putNum(rec, "decode_tps", num("decode_tps"))
        putNum(rec, "generated_tokens", num("generated_tokens"))
        putNum(rec, "gen_wall_ms", num("gen_wall_ms"))
        putNum(rec, "total_ms", job.totalMs.toDouble())
        putNum(rec, "pss_mb", job.pssMb)
        rec.put("retried", llm?.optBoolean("retried") == true)
        Log.i(PERF_TAG, rec.toString())
    } catch (t: Throwable) {
        Log.e(TAG, "perf log failed", t)
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
class Runner(private val id: Int, private val deadline: Long = Long.MAX_VALUE) {
    private fun timedOut(stats: JSONObject = JSONObject()): String =
        JSONObject().put("text", "").put("stats", stats.put("timed_out", true)).put("timed_out", true).toString()

    fun generate(prompt: String): String {
        if (!Bridge.still(id)) throw Cancelled()
        val module = ensureLoaded()
        if (!Bridge.still(id)) throw Cancelled()
        module.resetContext()
        if (!Bridge.still(id)) throw Cancelled()
        // A retry that would start after the budget is not started at all.
        if (SystemClock.elapsedRealtime() >= deadline) return timedOut()
        val start = SystemClock.elapsedRealtime()
        val overBudget = AtomicBoolean(false)
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
                    // The budget is enforced here too: a callback runs inside the native generate, the
                    // only place stop() is safe. Prefill emits no callback, so a run can overshoot the
                    // budget by at most one prefill and one token.
                    if (SystemClock.elapsedRealtime() >= deadline) overBudget.set(true)
                    if (count >= 40 || !Bridge.still(id) || overBudget.get()) {
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
            try { module.resetContext() } catch (_: Throwable) {}
        }
        val end = SystemClock.elapsedRealtime()
        if (!Bridge.still(id)) throw Cancelled()
        val stats = JSONObject().put("backend", "executorch")
        first?.let { stats.put("first_token_ms", it - start) }
        // Over budget: report a timeout (mobile.explain then shows the detector's fixed text), not the
        // partial reply, and not an error from the stopped native call.
        if (overBudget.get()) return timedOut(stats)
        callbackError.get()?.let { throw IllegalStateException(it, generationFailure) }
        generationFailure?.let { throw it }
        try {
            val nativeStats = JSONObject(if (rawStats.isBlank()) "{}" else rawStats)
            stats.put("raw", nativeStats)
            if (nativeStats.has("generated_tokens")) stats.put("generated_tokens", nativeStats.optInt("generated_tokens"))
            if (nativeStats.has("decode_token_per_sec")) stats.put("decode_tps", nativeStats.optDouble("decode_token_per_sec"))
            prefillStats(nativeStats, stats)
        } catch (_: Throwable) {}
        stats.put("gen_wall_ms", end - start)
        return JSONObject().put("text", out.toString()).put("stats", stats).toString()
    }
}

/**
 * Prompt tokens and prefill from ExecuTorch's native Stats JSON. Prefill time runs from
 * inference_start_ms to prompt_eval_end_ms, so it includes tokenizing the prompt. A missing, zero
 * or non-finite value is left out, and the UI and harness show it as unavailable.
 */
internal fun prefillStats(native: JSONObject, stats: JSONObject) {
    fun pos(key: String): Double? = native.optDouble(key, Double.NaN).takeIf { it.isFinite() && it > 0 }
    val tokens = pos("prompt_tokens")
    val start = pos("inference_start_ms")
    val end = pos("prompt_eval_end_ms")
    val ms = if (start != null && end != null && end > start) end - start else null
    val tps = pos("prefill_token_per_sec") ?: if (tokens != null && ms != null) tokens * 1000.0 / ms else null
    tokens?.let { stats.put("prompt_tokens", it.toInt()) }
    (ms ?: if (tokens != null && tps != null) tokens * 1000.0 / tps else null)?.let { stats.put("prefill_ms", it) }
    tps?.let { stats.put("prefill_tps", it) }
}

class MainActivity : Activity() {
    internal var screen = "home"
    internal var selectedMode = 0
    internal var inputValue = ""
    /** Optional sender for the current message check. Cleared for shared, QR and sample text. */
    internal var senderValue = ""
    private var senderInput: EditText? = null
    private var sharedBanner = false
    /** The shared text and its source hint, used only if that exact text is then checked. */
    private var sharedText = ""
    private var sharedSource = ""
    /** Source of the check in flight, so a mode switch on the checking screen keeps it. */
    private var checkSource = ""
    private var advancedOpen = false
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
    private var speech: TextToSpeech? = null
    private var announcedJob = Int.MIN_VALUE
    private var speaking = false
    // Bumped by stopSpeech(); a TTS engine that finishes starting after the user left the result
    // (Back, pause, stop) sees a stale request and stays silent.
    private var speechRequest = 0
    // Id of the utterance now playing; callbacks for a flushed, older one are ignored.
    private var currentUtterance = ""
    private var utteranceSeq = 0
    private var listenLabel: TextView? = null
    private var replacedSlot: LinearLayout? = null
    private var aiFootSlot: View? = null
    private var llamaHeadSlot: LinearLayout? = null
    private var aiEnglishSlot: TextView? = null
    private var backCallback: OnBackInvokedCallback? = null
    private var ignoreBackUntil = 0L

    private val modeNames = arrayOf("SMS", "Link", "Network", "App file")
    private val modeIcons = intArrayOf(R.drawable.ic_message, R.drawable.ic_link, R.drawable.ic_activity, R.drawable.ic_package)
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
        Sample("UPI refund QR scam", 1, "upi://pay?pa=cashback.refund99@ybl&pn=Amazon%20Refund%20Desk&am=4999&cu=INR&tn=Scan%20and%20enter%20UPI%20PIN%20to%20receive%20refund"),
        Sample("Legit kirana QR", 1, "upi://pay?pa=sharma.kirana@okicici&pn=Sharma%20Kirana%20Store&mc=5411&cu=INR&tn=Grocery%20bill"),
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
    private fun emulator() = (Build.SUPPORTED_ABIS.firstOrNull() ?: "").startsWith("x86")

    /**
     * Lookup first, then swap the device word. Replacing "this phone" before the lookup
     * missed every Hindi line, so the emulator showed English chrome.
     * On x86 the visible text never says "this phone" or "इस फ़ोन". arm64 keeps both.
     */
    private fun onDevice(text: String): String {
        if (!emulator() || text.isEmpty()) return text
        return text
            .replace("this phone's", "this emulator's")
            .replace("this phone", "this emulator")
            .replace("इसी फ़ोन", "इसी एम्युलेटर")
            .replace("इस फ़ोन", "इस एम्युलेटर")
            .replace("फ़ोन पर", "एम्युलेटर पर")
    }

    private fun t(english: String): String = onDevice(L10n.t(english))

    private fun n(key: String): String = onDevice(L10n.n(key))

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
    /** English mode is English only. Hindi mode is the bundled line, with [hi] if the table has no entry. */
    private fun heading(en: String, hi: String): TextView {
        val looked = L10n.t(en)
        val label = if (L10n.hindi) {
            val chosen = if (looked != en) looked else hi.ifBlank { en }
            onDevice(chosen)
        } else en.uppercase(Locale.ROOT)
        return txt(label, 11f, T.ink2, 700, 16, raw = true).apply {
            isAccessibilityHeading = true
            if (!L10n.hindi) {
                val spaced = SpannableString(label)
                spaced.setSpan(Tracking(0.04f), 0, label.length, 0)
                text = spaced
            }
        }
    }
    private fun iconText(id: Int, text: String, color: Int, size: Float = 14f, iconSize: Int = 18, flex: Boolean = false): LinearLayout = row().apply {
        add(this, icon(id, iconSize, color), iconSize, iconSize)
        val label = txt(text, size, color, 600)
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
        if (v.minimumWidth < dp(48)) v.minimumWidth = dp(48)
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
        fitsSystemWindows = false
        isFocusableInTouchMode = true
        importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        accessibilityPaneTitle = t(pane)
    }

    /** Draw under the system bars and pad them ourselves. API 35 does not keep the footer clear of the nav bar on its own. */
    private fun edgeToEdge() {
        if (Build.VERSION.SDK_INT >= 30) window.setDecorFitsSystemWindows(false)
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            )
    }

    /**
     * Top inset on [root]. Bottom inset plus 8 dp on the scroll content, or on [bottomBar]
     * when the last control sits outside the scroll. The last card then clears the nav bar.
     */
    private fun pinInsets(root: View, scroll: View, bottomBar: View?) {
        root.setOnApplyWindowInsetsListener { _, insets ->
            val top: Int
            val left: Int
            val right: Int
            val bottom: Int
            if (Build.VERSION.SDK_INT >= 30) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
                val ime = insets.getInsets(WindowInsets.Type.ime())
                top = bars.top
                left = bars.left
                right = bars.right
                bottom = maxOf(bars.bottom, ime.bottom)
            } else {
                @Suppress("DEPRECATION")
                top = insets.systemWindowInsetTop
                @Suppress("DEPRECATION")
                left = insets.systemWindowInsetLeft
                @Suppress("DEPRECATION")
                right = insets.systemWindowInsetRight
                @Suppress("DEPRECATION")
                bottom = insets.systemWindowInsetBottom
            }
            root.setPadding(left, top, right, 0)
            val clear = bottom + dp(8)
            if (bottomBar != null) {
                if (bottomBar.paddingBottom != clear) {
                    bottomBar.setPadding(bottomBar.paddingLeft, bottomBar.paddingTop, bottomBar.paddingRight, clear)
                }
            } else if (scroll.paddingBottom != clear) {
                scroll.setPadding(scroll.paddingLeft, scroll.paddingTop, scroll.paddingRight, clear)
            }
            if (Build.VERSION.SDK_INT >= 30) WindowInsets.CONSUMED else {
                @Suppress("DEPRECATION")
                insets.consumeSystemWindowInsets()
            }
        }
        root.requestApplyInsets()
    }

    /** Side-by-side controls become a vertical stack when their text no longer fits. */
    private fun stackWhenTight(row: LinearLayout, gapDp: Int = 8) {
        row.addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
            if (row.width <= 0 || row.orientation == LinearLayout.VERTICAL) return@addOnLayoutChangeListener
            val children = (0 until row.childCount).map { row.getChildAt(it) }.filter { it.visibility != View.GONE }
            if (children.size < 2) return@addOnLayoutChangeListener
            var needed = row.paddingLeft + row.paddingRight
            for (child in children) {
                child.measure(
                    View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED),
                    View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
                )
                needed += child.measuredWidth
            }
            needed += dp(gapDp) * (children.size - 1)
            if (needed <= row.width) return@addOnLayoutChangeListener
            row.orientation = LinearLayout.VERTICAL
            children.forEachIndexed { index, child ->
                val lp = (child.layoutParams as? LinearLayout.LayoutParams) ?: return@forEachIndexed
                lp.width = ViewGroup.LayoutParams.MATCH_PARENT
                lp.height = ViewGroup.LayoutParams.WRAP_CONTENT
                lp.weight = 0f
                lp.leftMargin = 0
                lp.topMargin = if (index == 0) 0 else dp(gapDp)
                child.layoutParams = lp
            }
        }
    }
    private fun bar(title: String, offline: Boolean, lang: Boolean = false): LinearLayout = row().apply {
        minimumHeight = dp(56)
        pad(this, 4, 0, 8, 0)
        add(this, iconButton(R.drawable.ic_arrow_left, "Back") { goHome() }, 48, 48)
        add(this, txt(title, 20f, T.ink, 600), 0, -2, left = 4, weight = 1f)
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
    private var screenScroll: ScrollView? = null
    private var screenBottom: View? = null

    private fun bottom(parent: LinearLayout, text: String, outlined: Boolean = false, id: Int? = null, action: () -> Unit) {
        val box = col().apply { setBackgroundColor(T.white) }
        divider(box)
        val wrap = col().apply { pad(this, 16, 10, 16, 6) }
        val actionButton = button(text, id, textColor = if (outlined) T.ink else T.white, outlined = outlined, action = action)
        actionButton.minimumHeight = dp(52)
        add(wrap, actionButton, -1, -2)
        add(box, wrap)
        screenBottom = box
        add(parent, box)
    }
    private fun scrollBody(parent: LinearLayout): LinearLayout {
        val body = col().apply { pad(this, 16, 0, 16, 16) }
        val scroll = ScrollView(this).apply {
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            isFillViewport = true
            clipToPadding = false
            addView(body, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        }
        screenScroll = scroll
        screenBottom = null
        add(parent, scroll, -1, 0, weight = 1f)
        return body
    }
    private fun showScreen(root: LinearLayout) {
        val scroll = screenScroll
        if (scroll != null) pinInsets(root, scroll, screenBottom)
        setContentView(root)
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
        Bridge.explainCleared = prefs.getBoolean(PREF_EXPLAIN_CLEARED, false)
        if (!Python.isStarted()) return
        try {
            val raw = Python.getInstance().getModule("intake").callAttr("strings_json").toString()
            L10n.load(raw)
        } catch (t: Throwable) {
            Log.e(TAG, "strings load failed", t)
        }
    }

    private fun setExplainCleared(on: Boolean) {
        Bridge.explainCleared = on
        getSharedPreferences("prahari", MODE_PRIVATE).edit().putBoolean(PREF_EXPLAIN_CLEARED, on).apply()
    }

    /**
     * Debug builds only: the adb harness launches with GATING_EXTRA set to "all" or "flagged-only".
     * Read on a fresh launch and on a new intent, never on recreation, so a later switch change wins.
     */
    private fun applyGatingExtra(source: Intent?) {
        if ((applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) == 0) return
        when (source?.getStringExtra(GATING_EXTRA)) {
            "all" -> setExplainCleared(true)
            "flagged-only" -> setExplainCleared(false)
            else -> return
        }
        source?.removeExtra(GATING_EXTRA)
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
        fun seg(label: String, on: Boolean, hi: Boolean, description: String) = row().apply {
            gravity = Gravity.CENTER
            minimumWidth = dp(48)
            minimumHeight = dp(48)
            setPadding(dp(8), dp(4), dp(8), dp(4))
            background = if (on) shape(T.white, 12f, 1, T.outline) else null
            add(this, txt(label, 12f, if (on) T.brand else T.ink2, 700, raw = true), -2, -2)
            setOnClickListener {
                if (L10n.hindi == hi) return@setOnClickListener
                L10n.hindi = hi
                rememberLanguage()
                rebuild()
            }
            asButton(this, description)
            contentDescription = n("language_name") + ", " + t(description)
        }
        add(wrap, seg("EN", !L10n.hindi, false, "English"), -2, -2)
        add(wrap, seg("हिंदी", L10n.hindi, true, "Hindi"), -2, -2, left = 2)
        return wrap
    }

    internal fun toast(message: String) {
        if (isDestroyed) return
        Toast.makeText(this, t(message).take(400), Toast.LENGTH_LONG).show()
    }

    internal fun failureToast(detail: String) {
        toast(t("Check failed") + ": " + detail + " " + t("The model may not run on this device."))
    }
    private fun hideKeyboard() {
        if (!::input.isInitialized) return
        val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager ?: return
        input.windowToken?.let { imm.hideSoftInputFromWindow(it, 0) }
    }
    private fun modelProblem(): String? {
        Bridge.pythonError?.let { return t("The on-device checker could not start.") + " " + it }
        Bridge.missing?.let { return t("Model files missing") + " " + it }
        Bridge.loadError?.let { return t("Couldn't load the on-device model.") + " " + it }
        return null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Bridge.app = applicationContext
        Bridge.host = this
        window.statusBarColor = T.bg
        window.navigationBarColor = T.bg
        edgeToEdge()
        savedInstanceState?.let {
            selectedMode = it.getInt("mode", 0).coerceIn(0, KINDS.lastIndex)
            inputValue = it.getString("input") ?: ""
            senderValue = it.getString("sender") ?: ""
            sharedBanner = it.getBoolean("shared")
            sharedText = it.getString("sharedText") ?: ""
            sharedSource = it.getString("sharedSource") ?: ""
            checkSource = it.getString("checkSource") ?: ""
            advancedOpen = it.getBoolean("advanced")
        }
        try {
            if (!Python.isStarted()) Python.start(AndroidPlatform(applicationContext))
            Bridge.pythonError = null
        } catch (t: Throwable) {
            Bridge.pythonError = errorText(t)
            Log.e(TAG, "Python start failed", t)
        }
        loadStrings()
        if (savedInstanceState == null) applyGatingExtra(intent)
        installBack()
        // An app file share is read at once: reading its details runs nothing from it. Only the
        // first create handles it, so a rotation does not read it again.
        if (savedInstanceState == null && takeApkShare(intent)) {
            requestModel(false)
            return
        }
        // A share intent stays on the activity across rotation. Only the first create fills the box.
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
                if (job != null) showChecking(job.mode, job.value)
                else showChecking(Bridge.pendingMode, Bridge.pendingValue)
            }
            "result" -> {
                val job = Bridge.job
                if (job != null) presentResult(job) else showHome()
            }
            "network" -> showNetwork(false)
            else -> when {
                restored != null -> presentResult(restored)
                savedInstanceState?.getString("screen") == "history" -> showHistory()
                else -> showHome()
            }
        }
        requestModel(false)
    }

    override fun onSaveInstanceState(out: Bundle) {
        super.onSaveInstanceState(out)
        if (screen == "home" && ::input.isInitialized) inputValue = input.text?.toString() ?: inputValue
        if (screen == "home") senderInput?.let { senderValue = it.text?.toString() ?: senderValue }
        out.putInt("mode", selectedMode)
        out.putString("input", inputValue)
        out.putString("sender", senderValue)
        out.putString("screen", screen)
        out.putBoolean("shared", sharedBanner)
        out.putString("sharedText", sharedText)
        out.putString("sharedSource", sharedSource)
        out.putString("checkSource", checkSource)
        out.putBoolean("advanced", advancedOpen)
        val job = if (screen == "result") visibleJob else null
        if (job != null) {
            out.putString("verdict", job.verdict.toString())
            out.putString("value", job.value)
            out.putString("source", job.source)
            out.putString("jobSender", job.sender)
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
                verdict = JSONObject(raw),
                source = state.getString("source") ?: "",
                sender = state.getString("jobSender") ?: ""
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
        stopSpeech()
        Bridge.cancel()
        if (clear) { inputValue = ""; senderValue = "" }
        showHome()
    }

    internal fun showHome() {
        screen = "home"
        visibleJob = null
        networkBody = null
        val root = root("Prahari")
        val scroller = ScrollView(this).apply {
            isFillViewport = true
            clipToPadding = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        val all = col()
        scroller.addView(all, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        add(root, scroller, -1, 0, weight = 1f)
        val brand = row().apply { minimumHeight = dp(60); pad(this, 16, 4, 8, 4) }
        add(brand, logo(), 36, 36)
        val name = col()
        add(name, txt("Prahari", 20f, T.ink, 700, 24, raw = true))
        add(name, txt(n("app_subtitle"), 12f, T.ink3, 500, 16, raw = true))
        add(brand, name, 0, -2, left = 10, weight = 1f)
        add(brand, langToggle { showHome() }, -2, -2)
        add(brand, iconButton(R.drawable.ic_info, "About Prahari") { showAbout() }, 48, 48)
        add(all, brand, -1, -2)
        val body = col().apply { pad(this, 16, 0, 16, 8) }
        add(all, body)
        add(body, txt("Check before you tap", 24f, T.ink, 700, 30).apply { isAccessibilityHeading = true }, top = 2)
        add(body, txt(n("works_offline"), 14f, T.ink2, 400, 20, raw = true), top = 2)
        if (sharedBanner) {
            val note = col().apply {
                background = shape(T.warnC, 14f)
                pad(this, 14, 12, 14, 12)
            }
            add(note, txt(n("shared_banner"), 14f, T.onWarnC, 600, 20, raw = true))
            add(body, note, top = 12)
        }
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
        // Optional sender (message mode only). It can only raise a result: a personal mobile number
        // on a bank-style message is marked suspicious; a sender ID never makes a message safe.
        val senderCard = col().apply {
            background = shape(T.white, 16f, 1, T.outline2)
            pad(this, 16, 12, 16, 10)
        }
        val senderLabel = txt(n("sender_label"), 12f, T.brand, 600, 16, raw = true)
        val senderField = EditText(this).apply {
            setText(senderValue)
            hint = n("sender_hint")
            setTextColor(T.ink)
            setHintTextColor(T.ink3)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            includeFontPadding = true
            filters = arrayOf(android.text.InputFilter.LengthFilter(32))
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS or
                android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            // Wraps instead of scrolling sideways, so the hint stays readable at font scale 2.0.
            setHorizontallyScrolling(false)
            maxLines = 2
            minHeight = dp(48)
            background = null
            importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
            setPadding(0, dp(4), 0, dp(4))
            id = View.generateViewId()
        }
        senderLabel.id = View.generateViewId()
        senderLabel.labelFor = senderField.id
        senderField.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { senderValue = s?.toString().orEmpty() }
            override fun afterTextChanged(s: Editable?) {}
        })
        add(senderCard, senderLabel)
        add(senderCard, senderField, -1, -2, top = 4)
        add(senderCard, txt(n("sender_note"), 12f, T.ink2, 400, 17, raw = true), top = 2)
        senderInput = senderField
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
            senderCard.visibility = if (selectedMode == 0) View.VISIBLE else View.GONE
        }
        fun modeChip(i: Int): LinearLayout {
            val segment = col().apply {
                gravity = Gravity.CENTER
                minimumHeight = dp(48)
                setPadding(dp(2), dp(8), dp(2), dp(8))
            }
            val face = iconText(modeIcons[i], modeNames[i], T.ink2, 14f, 16)
            val faceLabel = face.getChildAt(1) as TextView
            faceLabel.gravity = Gravity.CENTER
            faceLabel.textAlignment = View.TEXT_ALIGNMENT_CENTER
            add(segment, face, -2, -2)
            cap(faceLabel, segment, 24)
            segment.setOnClickListener {
                selectedMode = i
                if (i != 0) senderField.setText("")  // the sender belongs to a message check only
                refreshSegments()
            }
            asButton(segment, modeNames[i])
            segments.add(segment)
            return segment
        }
        add(seg, modeChip(0), 0, -2, weight = 1f)
        add(seg, modeChip(1), 0, -2, left = 4, weight = 1f)
        stackWhenTight(seg, 4)
        add(body, seg, -1, -2, top = 16)
        if (selectedMode == 2) advancedOpen = true
        val advanced = col().apply {
            background = shape(T.surface2, 14f)
            pad(this, 4, 4, 4, 4)
        }
        val advHead = row().apply {
            minimumHeight = dp(48)
            setPadding(dp(10), dp(4), dp(8), dp(4))
        }
        add(advHead, txt(n("advanced_mode"), 15f, T.ink, 700, raw = true), 0, -2, weight = 1f)
        val chevron = icon(R.drawable.ic_chevron_down, 20, T.ink2)
        add(advHead, chevron, 20, 20)
        val netWrap = col()
        add(netWrap, modeChip(2), -1, -2)
        add(advanced, advHead)
        add(advanced, netWrap)
        fun applyAdvanced() {
            netWrap.visibility = if (advancedOpen) View.VISIBLE else View.GONE
            chevron.rotation = if (advancedOpen) 180f else 0f
            advHead.contentDescription = n("advanced_mode") + ", " + t(if (advancedOpen) "Expanded" else "Collapsed")
        }
        advHead.setOnClickListener {
            advancedOpen = !advancedOpen
            // Hiding Network must not leave it selected: a message typed next would be checked as
            // a network event and could come back NO RISK.
            if (!advancedOpen && selectedMode == 2) {
                selectedMode = 0
                refreshSegments()
            }
            applyAdvanced()
        }
        asButton(advHead, n("advanced_mode"))
        applyAdvanced()
        add(body, advanced, -1, -2, top = 8)
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
            setOnClickListener { input.setText(""); senderField.setText("") }
        }
        asButton(clear, "Clear text")
        add(tools, paste, -2, -2)
        add(tools, View(this), 0, 1, weight = 1f)
        add(tools, clear, -2, -2)
        add(inputCard, tools)
        add(body, inputCard, -1, -2, top = 12)
        add(body, senderCard, -1, -2, top = 8)
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
                    if (sample.mode == 2 && !advancedOpen) {
                        advancedOpen = true
                        applyAdvanced()
                    }
                    refreshSegments()
                    senderField.setText("")
                    input.setText(sample.value)
                    input.setSelection(input.text.length)
                }
            }
            asButton(chip, t(sample.label) + ", " + t(modeNames[sample.mode]))
            add(chips, chip, -2, -2, left = if (chips.childCount == 0) 0 else 8)
        }
        add(body, HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(chips)
        }, -1, -2, top = 4)
        val check = button("Check on this phone", R.drawable.ic_shield_check) { startCheck() }.apply {
            minimumHeight = dp(56)
        }
        modelStatusSlot = col().apply { accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE }
        add(body, modelStatusSlot!!, -1, -2, top = 8)
        bindModelStatus()
        add(body, check, -1, -2, top = 8)
        fun refreshInput() {
            inputValue = input.text.toString()
            val empty = inputValue.isEmpty()
            if (empty && senderField.text.isNotEmpty()) senderField.setText("")
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
        add(body, historyHomeRow(), top = 16)
        add(body, navRow(R.drawable.ic_link, n("qr_check"), "") { pickQr() }, top = 8)
        add(body, navRow(R.drawable.ic_package, n("apk_check"), n("apk_check_sub")) { pickApk() }, top = 8)
        add(body, offline, top = 8)
        add(all, View(this), -1, 0, weight = 1f)
        centeredNote(all, iconText(R.drawable.ic_lock, "Nothing you paste leaves this phone", T.ink3, 12f, 13), 12)
        pinInsets(root, scroller, null)
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
                    senderInput?.setText("")  // a pasted message is a new message: its sender is unknown
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
        applyGatingExtra(intent)
        if (takeApkShare(intent)) return
        val shared = readShare(intent) ?: return
        // getReferrer() still names the app that first launched this singleTop activity, so a
        // later share gets no medium hint rather than a stale one.
        openShared(shared, trustReferrer = false)
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

    /** Drop control characters. Newlines and tabs stay so a pasted message keeps its lines. */
    private fun cleanShare(raw: String): String {
        return try {
            if (!Python.isStarted()) cleanShareLocal(raw)
            else Python.getInstance().getModule("intake").callAttr("clean_share", raw).toString()
        } catch (t: Throwable) {
            Log.e(TAG, "share clean failed", t)
            cleanShareLocal(raw)
        }
    }

    private fun cleanShareLocal(raw: String): String {
        val sb = StringBuilder(raw.length)
        var i = 0
        while (i < raw.length) {
            val ch = raw[i]
            when {
                ch == '\r' -> {
                    sb.append('\n')
                    if (i + 1 < raw.length && raw[i + 1] == '\n') i++
                }
                ch == '\n' || ch == '\t' -> sb.append(ch)
                ch.isISOControl() -> {}
                else -> sb.append(ch)
            }
            i++
        }
        return sb.toString().trim()
    }

    /** Share opens Home with the text filled in. Nothing is checked, and no link is opened, until Check. */
    private fun openShared(raw: String, trustReferrer: Boolean = true) {
        stopSpeech()
        Bridge.cancel()
        val text = cleanShare(raw)
        when {
            text.isEmpty() -> {
                sharedBanner = false
                toast("Nothing to check.")
                showHome()
            }
            text.length > 100_000 -> {
                sharedBanner = false
                toast("That text is too long to check.")
                showHome()
            }
            else -> {
                sharedBanner = true
                sharedText = text
                sharedSource = if (trustReferrer) shareSource() else ""
                inputValue = text
                senderValue = ""  // shared text carries no sender
                selectedMode = detectMode(text)
                showHome()
            }
        }
    }

    /**
     * The sharing app as a hint for the report's medium line. The referrer is optional and set by
     * the caller, so it is never trusted for anything else; unknown apps give "".
     */
    private fun shareSource(): String {
        val pkg = try {
            referrer?.takeIf { it.scheme == "android-app" }?.host.orEmpty()
        } catch (_: Throwable) {
            ""
        }
        return when (pkg) {
            "com.whatsapp", "com.whatsapp.w4b" -> "whatsapp"
            "com.google.android.apps.messaging", "com.samsung.android.messaging", "com.android.mms" -> "sms"
            else -> ""
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
                gravity = Gravity.CENTER
                textAlignment = View.TEXT_ALIGNMENT_CENTER
            }
            add(chip, label, 0, -2, left = 4, weight = 1f)
            chip.setOnClickListener { if (i != selected) beginCheck(i, value, visibleJob?.source ?: checkSource) }
            val modeLabel = t(modeNames[i])
            asButton(chip, if (on) "$modeLabel, ${t("selected")}" else "${t("Change to")} $modeLabel")
            add(seg, chip, 0, -2, left = if (i == 0) 0 else 4, weight = 1f)
        }
        stackWhenTight(seg, 4)
        return seg
    }

    private fun startCheck() {
        if (!::input.isInitialized) return
        val text = input.text?.toString() ?: ""
        val sender = if (selectedMode == 0) senderInput?.text?.toString()?.trim().orEmpty() else ""
        beginCheck(selectedMode, text, if (text == sharedText) sharedSource else "", sender)
    }

    /** [sender] defaults to the current check's sender, so a mode switch re-check keeps it. */
    private fun beginCheck(mode: Int, value: String, source: String = "", sender: String = senderValue) {
        if (value.isBlank()) {
            toast("Paste a message, link or network event first.")
            return
        }
        if (value.length > 100_000) {
            toast("That text is too long to check.")
            return
        }
        inputValue = value
        senderValue = sender.take(32)
        selectedMode = mode.coerceIn(0, KINDS.lastIndex)
        sharedBanner = false
        checkSource = source
        stopSpeech()
        hideKeyboard()
        val id = Bridge.begin()
        val started = SystemClock.elapsedRealtime()
        Bridge.pendingMode = selectedMode
        Bridge.pendingValue = value
        showChecking(selectedMode, value)
        enqueueCheck(id, selectedMode, value, started, source, senderValue)
    }

    /** An app file share: start the check, or say why the file cannot be read. */
    private fun takeApkShare(source: Intent?): Boolean {
        if (!ApkInspector.isShare(source)) return false
        val uri = ApkInspector.sharedUri(source!!)
        if (uri == null) {
            stopSpeech()
            Bridge.cancel()
            showHome()
            toast(n("apk_fail"))
        } else {
            beginApkCheck(uri)
        }
        return true
    }

    private fun pickApk() {
        try {
            @Suppress("DEPRECATION")
            startActivityForResult(ApkInspector.pickIntent(), ApkInspector.PICK_REQUEST)
        } catch (t: Throwable) {
            Log.e(TAG, "file picker failed", t)
            toast(n("apk_fail"))
        }
    }

    /**
     * The file is read on its own thread under this check's id ([readApk]), so a newer check or
     * Cancel stops it and the copy never outlives the check. Home's text and mode are left alone.
     */
    private fun beginApkCheck(uri: Uri) {
        sharedBanner = false
        checkSource = ""
        stopSpeech()
        hideKeyboard()
        val id = Bridge.begin()
        val started = SystemClock.elapsedRealtime()
        val shown = n("apk_reading")
        Bridge.pendingMode = APK_MODE
        Bridge.pendingValue = shown
        showChecking(APK_MODE, shown)
        readApk(id, uri, started)
    }

    /** The app file could not be read: back to Home with the reason. */
    internal fun apkFailed(key: String) {
        showHome()
        toast(n(key))
    }

    private fun showChecking(mode: Int, value: String) {
        screen = "checking"
        // An app file check keeps Home's own mode and text.
        if (mode in KINDS.indices) {
            selectedMode = mode
            inputValue = value
        }
        visibleJob = null
        networkBody = null
        val root = root("Checking")
        add(root, bar("Checking", true), -1, -2)
        val body = scrollBody(root)
        val what = card()
        val summary = row()
        add(summary, icon(modeIcons[mode], 18, T.ink2), 18, 18)
        add(summary, txt(value, 14f, T.ink2, 400, 20, raw = true).apply {
            maxLines = 3
            ellipsize = android.text.TextUtils.TruncateAt.END
        }, 0, -2, left = 12, weight = 1f)
        add(what, summary)
        add(body, what)
        if (mode in KINDS.indices) add(body, modeSwitcher(mode, value), -1, -2, top = 12)
        val ring = FrameLayout(this)
        val progress = ProgressBar(this, null, android.R.attr.progressBarStyleLarge).apply {
            indeterminateTintList = ColorStateList.valueOf(T.brand)
            contentDescription = t("Checking on this phone")
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
        showScreen(root)
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
        else -> Palette(T.slateBg, T.slateInk, T.slateBg, T.slateInk, T.slateInk, R.drawable.ic_shield, T.white, "NO RISK FOUND", "कोई खतरा नहीं मिला")
    }
    private fun sentence(s: String): String = s.trim().replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
    private fun strings(a: JSONArray?): List<String> = if (a == null) emptyList() else (0 until a.length()).map { a.optString(it) }

    /** [firstHi]: the result's own Hindi for the first evidence line (app file results), or "". */
    private fun verdictLine(evidence: List<String>, fallback: String, clear: Boolean, firstHi: String = ""): String {
        val raw = evidence.firstOrNull()
        val line = when {
            raw == null -> t(fallback)
            L10n.hindi -> {
                val translated = firstHi.ifBlank { t(raw) }
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

    /** "SMS · checked on this phone in 1.2 s", with the Hindi line when that mode is on. */
    private fun checkedMeta(mode: Int, elapsedMs: Double, isUpi: Boolean = false): String {
        val tail = formatMs(elapsedMs)
        val name = if (isUpi) "UPI QR" else modeNames[mode.coerceIn(0, modeNames.lastIndex)]
        val where = t("checked on this phone")
        val shownName = t(name)
        return if (L10n.hindi) "$shownName · $where · $tail" else "$shownName · $where in $tail"
    }

    private fun upiCard(upi: JSONObject): LinearLayout {
        val box = card()
        add(box, heading("UPI QR details", "UPI QR विवरण"))
        val direction = upi.optString("direction", "sends_money")
        val intentLabel = upi.optString("intent_label", "Sends money from your account")
        val badgeFill = if (direction == "sends_money") T.warnC else T.dangerC
        val badgeInk = if (direction == "sends_money") T.onWarnC else T.onDanger
        val badge = iconText(R.drawable.ic_alert_circle, intentLabel, badgeInk, 13f, 16, flex = true).apply {
            background = shape(badgeFill, 12f)
            pad(this, 10, 7, 12, 7)
        }
        add(box, badge, -1, -2, top = 8)
        fun fieldRow(label: String, value: String, mono: Boolean = false, first: Boolean = false) {
            if (!first) divider(box, 6)
            val line = row().apply { gravity = Gravity.TOP; pad(this, 0, 6, 0, 2) }
            add(line, txt(label, 12f, T.ink3, 600, 18), 88, -2)
            val v = txt(value, 14f, T.ink, 500, 20, raw = true).apply {
                if (mono) typeface = Typeface.MONOSPACE
            }
            add(line, v, 0, -2, left = 8, weight = 1f)
            add(box, line, -1, -2)
        }
        val rows = ArrayList<Triple<String, String, Boolean>>()
        val pn = upi.optString("payee_name", "")
        val pa = upi.optString("payee_vpa", "")
        val amt = upi.optString("amount", "")
        val cu = upi.optString("currency", "INR")
        val mc = upi.optString("merchant_code", "")
        val isMerchant = upi.optBoolean("is_merchant", false)
        val note = upi.optString("note", "")
        if (pn.isNotBlank()) rows.add(Triple("Payee", pn, false))
        if (pa.isNotBlank()) rows.add(Triple("UPI ID", pa, true))
        rows.add(Triple("Amount", if (amt.isNotBlank()) "$cu $amt" else t("Entered by you"), amt.isNotBlank()))
        val cat = when {
            mc.isNotBlank() -> "MCC $mc"
            isMerchant -> t("Merchant")
            else -> t("Personal / P2P")
        }
        rows.add(Triple("Category", cat, isMerchant))
        if (note.isNotBlank()) rows.add(Triple("Note", note, false))
        rows.forEachIndexed { idx, item -> fieldRow(item.first, item.second, item.third, idx == 0) }
        divider(box, 8)
        add(box, iconText(R.drawable.ic_lock, "Checked safely — no UPI app was opened", T.ink3, 12f, 14, flex = true), -1, -2, top = 8)
        return box
    }

    private fun banner(p: Palette, why: String, meta: String, metaIcon: Int, stillVerify: Boolean = false): LinearLayout {
        val box = col().apply { background = shape(p.fill, 20f, if (stillVerify) 1 else 0, T.slateLine); pad(this, 18, 18, 18, 16) }
        val top = row()
        val bubble = FrameLayout(this).apply {
            background = shape(p.iconFill, 26f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(icon(p.glyph, 30, p.on), FrameLayout.LayoutParams(dp(30), dp(30), Gravity.CENTER))
        }
        add(top, bubble, 52, 52)
        val titles = col()
        val looked = L10n.t(p.title)
        val big = onDevice(if (L10n.hindi && looked != p.title) looked else if (L10n.hindi) p.hindi else p.title)
        add(titles, txt(big, if (stillVerify) 25f else 28f, p.on, 800, 32, raw = true).apply {
            if (!containsIndic(big)) letterSpacing = .02f
            isAccessibilityHeading = true
        })
        if (stillVerify) {
            val verify = iconText(R.drawable.ic_alert_circle, n("still_verify"), p.on, 13f, 14).apply {
                background = shape(T.white, 13f, 1, T.slateLine)
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

    /** Verdict title and vetted steps only. The message, the evidence line and the Llama text stay silent. */
    private fun speechScript(p: Palette, actions: List<String>, actionsHi: List<String>, hindi: Boolean): String {
        val looked = if (hindi) L10n.t(p.title) else p.title
        val title = if (hindi && looked == p.title) p.hindi else looked
        val steps = actions.mapIndexed { i, action ->
            if (hindi) actionsHi.getOrNull(i).orEmpty().ifBlank { L10n.t(action) } else action
        }
        return onDevice((listOf(title) + steps).filter { it.isNotBlank() }.joinToString("\n"))
    }

    private fun listenButton(p: Palette, hindiScript: String, englishScript: String): LinearLayout {
        val box = row().apply {
            gravity = Gravity.CENTER
            minimumHeight = dp(48)
            setPadding(dp(12), dp(8), dp(12), dp(8))
            background = ripple(shape(Color.TRANSPARENT, 14f, 1, p.on))
        }
        val label = txt(n("listen"), 15f, p.on, 700, raw = true)
        listenLabel = label
        add(box, label, -2, -2)
        box.setOnClickListener { toggleSpeech(hindiScript, englishScript) }
        asButton(box, n("listen"))
        return box
    }

    private fun refreshListen() {
        val label = listenLabel ?: return
        val word = if (speaking) n("stop") else n("listen")
        label.text = word
        (label.parent as? View)?.contentDescription = word
    }

    private fun stopSpeech() {
        speechRequest++
        speaking = false
        try { speech?.stop() } catch (_: Throwable) {}
        refreshListen()
    }

    private fun toggleSpeech(hindiScript: String, englishScript: String) {
        val script = if (L10n.hindi) hindiScript else englishScript
        if (script.isBlank()) return
        if (speaking) {
            stopSpeech()
            return
        }
        val ready = speech
        if (ready == null) {
            val request = ++speechRequest
            speech = TextToSpeech(applicationContext) { status ->
                runOnUiThread {
                    if (isDestroyed || isFinishing || request != speechRequest || screen != "result") return@runOnUiThread
                    if (status != TextToSpeech.SUCCESS || speech == null) {
                        toast(n("voice_missing"))
                        return@runOnUiThread
                    }
                    speakNow(hindiScript, englishScript)
                }
            }
            return
        }
        speakNow(hindiScript, englishScript)
    }

    private fun speakNow(hindiScript: String, englishScript: String) {
        val engine = speech ?: return
        val chosen = chooseVoice(engine, hindiScript, englishScript) ?: return
        try {
            // setVoice reports failure by return code, not only by throwing.
            if (engine.setVoice(chosen.first) != TextToSpeech.SUCCESS) {
                toast(n("voice_missing"))
                return
            }
        } catch (t: Throwable) {
            Log.e(TAG, "voice select failed", t)
            toast(n("voice_missing"))
            return
        }
        val script = chosen.second
        val utterance = "prahari-${++utteranceSeq}"
        currentUtterance = utterance
        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) {
                runOnUiThread { if (!isDestroyed && utteranceId == currentUtterance) { speaking = false; refreshListen() } }
            }
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                runOnUiThread { if (!isDestroyed && utteranceId == currentUtterance) { speaking = false; refreshListen() } }
            }
        })
        val code = engine.speak(script, TextToSpeech.QUEUE_FLUSH, Bundle(), utterance)
        if (code == TextToSpeech.ERROR) {
            toast(n("voice_missing"))
            return
        }
        speaking = true
        refreshListen()
    }

    /**
     * Offline voices only. A network voice is never selected.
     * Hindi needs an installed hi-IN voice; otherwise read the English script, or say no voice is installed.
     */
    private fun chooseVoice(engine: TextToSpeech, hindiScript: String, englishScript: String): Pair<Voice, String>? {
        fun offline(language: String, country: String?): Voice? {
            val voices = try { engine.voices } catch (t: Throwable) {
                Log.e(TAG, "voice list failed", t)
                null
            } ?: return null
            val ready = voices.filter { voice ->
                if (voice.isNetworkConnectionRequired) return@filter false
                if (!voice.locale.language.equals(language, ignoreCase = true)) return@filter false
                if (country != null && !voice.locale.country.equals(country, ignoreCase = true)) return@filter false
                val features = voice.features ?: emptySet()
                if (features.any { it.equals("notInstalled", ignoreCase = true) || it.contains("network", ignoreCase = true) }) return@filter false
                true
            }
            return ready.firstOrNull()
        }
        if (L10n.hindi) {
            offline("hi", "IN")?.let { return it to hindiScript }
            val english = offline("en", "IN") ?: offline("en", null)
            if (english == null) {
                toast(n("voice_missing"))
                return null
            }
            toast(n("hindi_voice_english"))
            return english to englishScript
        }
        val english = offline("en", "IN") ?: offline("en", null)
        if (english == null) {
            toast(n("voice_missing"))
            return null
        }
        return english to englishScript
    }

    internal fun presentResult(job: Bridge.Job) {
        stopSpeech()
        if (job.id >= 0 && !Bridge.mark(job.id, "result")) return
        shownId = job.id
        visibleJob = job
        val apk = job.mode == APK_MODE
        if (!apk) {
            selectedMode = job.mode.coerceIn(0, KINDS.lastIndex)
            inputValue = job.value
            senderValue = job.sender
        }
        screen = "result"
        networkBody = null
        val data = job.verdict
        // A bank debit or OTP alert is never relabelled when the verdict is DANGEROUS. Without a
        // contact of its own it shows the amber CHECK THIS ALERT banner; with an unofficial link
        // or a private number it is shown as SUSPICIOUS, even when the detector cleared it.
        val alertLevel = bankAlertLevel(data, job.value)
        val rawLevel = data.optString("level", "clear")
        val level = if (alertLevel == "warn") "warn" else rawLevel
        // A raised alert must not show the detector's benign reading ("reads like a normal receipt").
        val evidence = if (alertLevel == "warn" && rawLevel == "clear") listOf(OWN_CONTACT_LINE)
            else strings(data.optJSONArray("evidence"))
        val actions = strings(data.optJSONArray("actions"))
        val clear = level == "clear"
        val bankAlert = alertLevel == "alert"
        val p = if (bankAlert) palette("warn").copy(title = "CHECK THIS ALERT", hindi = "अलर्ट जांचें") else palette(level)
        val calm = clear && !bankAlert
        val fallback = when {
            level == "danger" -> "Strong scam signals found."
            level == "warn" -> "Some warning signs found."
            else -> "No scam signals found."
        }
        // The alert banner replaces the suspicious line. Other results use the first evidence line.
        val firstHi = strings(data.optJSONArray("evidence_hi")).firstOrNull().orEmpty()
        val why = if (bankAlert) t(ALERT_LINE) else verdictLine(evidence, fallback, calm, firstHi)
        val elapsed = if (job.totalMs >= 0) job.totalMs else SystemClock.elapsedRealtime() - job.started
        val root = root(p.title)
        add(root, bar("Result", true, lang = true), -1, -2)
        val body = scrollBody(root)
        val modeRow = if (apk) null else modeSwitcher(selectedMode, job.value)
        modeRow?.let { add(body, it, -1, -2) }
        val upi = data.optJSONObject("upi")
        val shownMode = if (apk) APK_MODE else selectedMode
        val b = banner(p, why, checkedMeta(shownMode, elapsed.toDouble(), upi != null), modeIcons[shownMode], calm)
        b.accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
        if (job.mode == 2) add(b, txt(n("replay_label"), 13f, p.on, 600, 18, raw = true), top = 8)
        metaText = b.findViewWithTag<TextView>("prahari-meta")
        data.optString("scam_type", "").takeIf { it.isNotBlank() }?.let { scam ->
            val scamHi = data.optString("scam_type_hi", "")
            val kind = if (L10n.hindi) scamHi.ifBlank { t(scam) } else sentence(scam)
            add(b, txt(t("Type") + ": " + kind, 12f, p.on, 500, 16, raw = true), top = 8)
        }
        val actionsHi = strings(data.optJSONArray("actions_hi"))
        add(b, listenButton(p, speechScript(p, actions, actionsHi, true), speechScript(p, actions, actionsHi, false)), -1, -2, top = 12)
        add(body, b, top = 12)
        if (job.mode != 2 && data.optBoolean("remote_app_check")) {
            val apps = try { RemoteApps.installed(packageManager) } catch (_: Throwable) { emptyList() }
            if (apps.isNotEmpty()) add(body, remoteAppBanner(apps), top = 12)
        }
        if (announcedJob != job.id) {
            announcedJob = job.id
            val announcement = "${t(p.title)}. $why"
            b.post { if (!isDestroyed && announcedJob == job.id) b.announceForAccessibility(announcement) }
        }
        val steps = card()
        add(steps, heading(if (clear) "Before you act" else "Do this now", if (clear) "कार्य करने से पहले" else "अभी यह करें"))
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
                stackWhenTight(buttons, 8)
                add(steps, buttons, top = 14)
            }
        }
        // Copy report and Send to family: SCAM or SUSPICIOUS message and link results only.
        val reportCard = if (mode == 2 || level == "clear") null
            else data.optJSONObject("report_card")
                ?: if (alertLevel == "warn") data.optJSONObject("report_card_raised") else null
        if (reportCard != null) add(steps, shareRow(reportCard), top = 10)
        if (apk) {
            divider(steps, 12)
            add(steps, iconText(R.drawable.ic_info, n("apk_note"), T.ink2, 13f, 16, flex = true).apply {
                minimumHeight = dp(48)
                setPadding(0, dp(8), 0, dp(8))
            }, top = 8)
        } else if (clear && mode == 0) {
            divider(steps, 12)
            add(steps, iconText(R.drawable.ic_alert_circle, "Scammers copy real messages. If it asks for money or a code, check in the official app first.", T.ink2, 13f, 16, flex = true).apply {
                minimumHeight = dp(48)
                setPadding(0, dp(8), 0, dp(8))
            }, top = 8)
        } else if (clear && mode == 1) {
            divider(steps, 12)
            val caveat = if (upi != null) n("upi_caveat") else n("link_caveat")
            add(steps, iconText(R.drawable.ic_alert_circle, caveat, T.ink2, 13f, 16, flex = true).apply {
                minimumHeight = dp(48)
                setPadding(0, dp(8), 0, dp(8))
            }, top = 8)
        }
        add(body, steps, top = 12)
        if (upi != null) add(body, upiCard(upi), top = 12)
        var whyCard: View? = null
        val shownEvidence = evidence.filter { it.isNotBlank() }
        if (shownEvidence.isEmpty() && (level == "danger" || level == "warn") && !bankAlert && job.mode != 2) {
            val evidenceCard = card()
            add(evidenceCard, heading("Why it's flagged", "संकेत"))
            add(evidenceCard, txt(n("model_only_evidence"), 14f, T.ink, 400, 20, raw = true), top = 8)
            whyCard = evidenceCard
            add(body, evidenceCard, top = 12)
        } else if (shownEvidence.isNotEmpty()) {
            val evidenceCard = card()
            val header = row()
            add(header, heading(if (clear) "What we saw" else "Why it's flagged", "संकेत"), 0, -2, weight = 1f)
            val countWord = t(if (shownEvidence.size == 1) "signal" else "signals")
            add(header, txt("${shownEvidence.size} $countWord", 11f, T.ink3, 600, raw = true), -2, -2)
            add(evidenceCard, header)
            val quotes = strings(data.optJSONArray("evidence_quotes"))
            // App file results carry their own Hindi evidence (apk_check.py), written beside the English.
            val evidenceHi = strings(data.optJSONArray("evidence_hi"))
            evidence.forEachIndexed { index, item ->
                if (item.isBlank()) return@forEachIndexed
                val chip = row().apply { gravity = Gravity.TOP; background = shape(p.chip, 12f); pad(this, 10, 8, 12, 8) }
                add(chip, icon(if (calm) R.drawable.ic_check_circle else R.drawable.ic_alert_circle, 16, p.chipText), 16, 16)
                val column = col()
                val translated = if (L10n.hindi) evidenceHi.getOrNull(index)?.takeIf { it.isNotBlank() } ?: t(item) else item
                val shown = if (L10n.hindi && translated != item) translated else sentence(item)
                val text = SpannableString(shown)
                Regex("[a-z0-9-]+(\\.[a-z0-9-]+)+").findAll(text).forEach { match ->
                    text.setSpan(TypefaceSpan("monospace"), match.range.first, match.range.last + 1, 0)
                    text.setSpan(StyleSpan(Typeface.BOLD), match.range.first, match.range.last + 1, 0)
                    text.setSpan(RelativeSizeSpan(13f / 14f), match.range.first, match.range.last + 1, 0)
                }
                add(column, txt(text, 14f, p.chipText, 400, 20))
                val quote = quotes.getOrNull(index).orEmpty()
                if (quote.isNotEmpty()) {
                    val quoteView = txt("“$quote”", 12f, T.ink2, 400, 16, raw = true).apply {
                        isClickable = false
                        linksClickable = false
                        setTextIsSelectable(false)
                    }
                    add(column, quoteView, top = 2)
                }
                add(chip, column, 0, -2, left = 8, weight = 1f)
                chip.isClickable = false
                add(evidenceCard, chip, -1, -2, top = 8)
            }
            whyCard = evidenceCard
            add(body, evidenceCard, top = 12)
        }
        // Hindi mode: the detector's fixed-text Hindi summary leads, labelled as not AI-written.
        // Llama 3.2 1B cannot write reliable Hindi, so its explanation below stays in English.
        val summaryHi = data.optString("summary_hi", "")
        if (L10n.hindi && summaryHi.isNotEmpty()) {
            val hiCard = card()
            add(hiCard, txt(data.optString("summary_hi_label", ""), 12f, T.ink3, 600, 16, raw = true))
            add(hiCard, txt(summaryHi, 15f, T.ink, 400, 24, raw = true).apply {
                includeFontPadding = true
                isFallbackLineSpacing = true
            }, top = 6)
            add(body, hiCard, top = 12)
        }
        val llama = card(T.surface2, false)
        val llamaHead = iconText(R.drawable.ic_cpu, "Explained on this phone by Llama 3.2", T.ink2, 13f, 18, flex = true)
        llamaHeadSlot = llamaHead
        add(llama, llamaHead)
        val replaced = row().apply {
            visibility = View.GONE
            background = shape(T.brandC, 12f)
            pad(this, 8, 4, 10, 4)
        }
        add(replaced, txt(n("replaced_chip"), 12f, T.brand, 600, 16, raw = true))
        replacedSlot = replaced
        add(llama, replaced, -2, -2, top = 8)
        val explainRow = row().apply { gravity = Gravity.TOP; isBaselineAligned = false }
        val accent = View(this).apply {
            setBackgroundColor(T.brand)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        add(explainRow, accent, 3, -1)
        val known = modelProblem()
        val placeholder = if (known == null) t("Writing an explanation on this phone…")
        else t("Explanation unavailable on this phone. The verdict and the steps above are complete.") + "\n" + known
        explanationText = txt(placeholder, 15f, T.ink2, 400, 22, raw = true).apply {
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
        val aiFoot = iconText(R.drawable.ic_info, "AI-written and can be wrong. Follow the steps above.", T.ink2, 12f, 14, flex = true)
        add(llama, aiFoot, top = 12)
        aiFootSlot = aiFoot
        aiEnglishSlot = null
        if (L10n.hindi) {
            val note = txt(n("ai_english"), 12f, T.ink3, 600, 16, raw = true)
            aiEnglishSlot = note
            add(llama, note, top = 6)
        }
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
        fillStats(data, null, null, null, false, false)
        add(body, stats, top = 12)
        val checked = card()
        add(checked, heading("You checked", "आपने जांचा"))
        add(checked, txt(job.value, 14f, T.ink2, 400, 20, raw = true).apply {
            setTextIsSelectable(true)
            if (mode != 0) typeface = Typeface.MONOSPACE
        }, top = 10)
        add(body, checked, top = 12)
        bottom(root, n("check_another")) { goHome(true) }
        fun after(next: View, prev: View) {
            if (next.id == View.NO_ID) next.id = View.generateViewId()
            if (prev.id == View.NO_ID) prev.id = View.generateViewId()
            next.accessibilityTraversalAfter = prev.id
        }
        if (b.id == View.NO_ID) b.id = View.generateViewId()
        after(steps, b)
        var cursor: View = steps
        whyCard?.let { after(it, cursor); cursor = it }
        explanationText?.let { after(it, cursor); cursor = it }
        statsHeader?.let { after(it, cursor); cursor = it }
        modeRow?.let { after(it, cursor) }
        showScreen(root)
        if (job.explanation != null) applyExplanation(job)
    }

    private fun formatMs(value: Double): String {
        if (!value.isFinite() || value < 0) return "—"
        return if (value < 1000) "${value.toInt()} ms" else String.format(Locale.US, "%.2f s", value / 1000)
    }

    private fun describeStats(expanded: Boolean) {
        val header = statsHeader ?: return
        val summary = statsSummary?.text ?: ""
        header.contentDescription = t(if (expanded) "On-device stats, expanded" else "On-device stats, collapsed") + ". $summary"
        if (Build.VERSION.SDK_INT >= 30) header.stateDescription = t(if (expanded) "Expanded" else "Collapsed")
    }

    private fun tileRow(labels: List<String>, values: List<String>): LinearLayout {
        val tiles = row()
        labels.forEachIndexed { i, label ->
            val tile = col().apply { background = shape(T.surface2, 12f); pad(this, 10, 10, 10, 10) }
            add(tile, txt(values[i], 17f, T.ink, 700))
            add(tile, txt(label, 11f, T.ink2, 500), top = 4)
            add(tiles, tile, 0, -2, left = if (i == 0) 0 else 8, weight = 1f)
        }
        stackWhenTight(tiles, 8)
        return tiles
    }

    private fun tps(value: Double?): String =
        value?.takeIf { it.isFinite() && it > 0 }?.let { String.format(Locale.US, "%.1f t/s", it) } ?: "—"

    /** [done]: the explanation stage has finished, whatever its outcome, so the header never stays "—". */
    private fun fillStats(data: JSONObject, llm: JSONObject?, total: Long?, pss: Double?, skipped: Boolean, done: Boolean, fallback: Boolean = false) {
        val details = statsDetails ?: return
        val summary = statsSummary ?: return
        details.removeAllViews()
        fun d(key: String) = llm?.optDouble(key, Double.NaN) ?: Double.NaN
        val detector = formatMs(data.optDouble("detector_ms", Double.NaN))
        val firstToken = formatMs(d("first_token_ms"))
        add(details, tileRow(listOf("Detector", "First token", "Decode speed"),
            listOf(detector, firstToken, tps(d("decode_tps")))), top = 4)
        val tokens = d("prompt_tokens").takeIf { it.isFinite() && it > 0 }?.let { "${it.toInt()}" } ?: "—"
        add(details, tileRow(listOf("Prompt tokens", "Prefill", "Prefill speed"),
            listOf(tokens, formatMs(d("prefill_ms")), tps(d("prefill_tps")))), top = 8)
        val abi = Build.SUPPORTED_ABIS.firstOrNull() ?: "—"
        val skippedLine = if (skipped) t("Llama skipped: verdict and text from the detector") + "\n" else ""
        val foot = skippedLine + t("Total") + " ${total?.let { formatMs(it.toDouble()) } ?: "—"} · " +
            t("Memory") + " ${pss?.let { String.format(Locale.US, "%.1f MB", it) } ?: "—"}\n" +
            "Llama 3.2 1B INT4 · ExecuTorch · XNNPACK\nCPU ABI: $abi" +
            if (abi.startsWith("x86")) "\n" + t("x86 emulator: not Arm timings") else ""
        add(details, txt(foot, 12f, T.ink3, 400, 18, raw = true).apply { typeface = Typeface.MONOSPACE }, top = 12)
        // adb_bench.py reads this summary from the header's label: "<detector> · <first token>" when
        // Llama ran; "Llama skipped" when gating skipped it; "Detector text" when Llama's replies were
        // replaced by the detector's fixed text; "No AI text" when there is no explanation at all
        // (missing model, an error); "—" only while Llama is still writing.
        val second = when {
            skipped -> t("Llama skipped")
            done && fallback -> t("Detector text")
            done && firstToken == "—" -> t("No AI text")
            else -> firstToken
        }
        summary.text = "$detector · $second"
        describeStats(details.visibility == View.VISIBLE)
    }

    internal fun applyExplanation(job: Bridge.Job) {
        if (shownId != job.id) return
        val view = explanationText ?: return
        val result = job.explanation ?: return
        val error = result.optString("error", "")
        val explanation = result.optString("explanation", "").trim()
        val skipped = result.optBoolean("llama_skipped")
        replacedSlot?.visibility = if (result.optBoolean("replaced")) View.VISIBLE else View.GONE
        if (skipped) markDetectorText("gated")
        // The app raised a cleared bank alert to SUSPICIOUS because it names its own link or number.
        // Llama wrote for the detector's NO RISK reading, so its text would contradict the banner.
        if (bankAlertLevel(job.verdict, job.value) == "warn" && job.verdict.optString("level") == "clear") {
            replacedSlot?.visibility = View.GONE
            aiFootSlot?.visibility = View.GONE  // the note is the app's text, not the AI's
            view.text = t(RAISED_NOTE)
            view.setTextColor(T.ink2)
            view.setTypeface(view.typeface, Typeface.ITALIC)
            // Stats still finish, so the header (and adb_bench.py) sees the check as done.
            fillStats(job.verdict, result.optJSONObject("llm"), job.totalMs.takeIf { it >= 0 }, job.pssMb.takeIf { it.isFinite() }, skipped, true, result.has("fallback"))
            return
        }
        if (result.has("fallback")) markDetectorText(result.optString("fallback"))
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
        // A detector-text fallback reads "No AI text" even when a refused reply had a first token.
        fillStats(job.verdict, result.optJSONObject("llm"), total, pss, skipped, true, result.has("fallback"))
        metaText?.text = checkedMeta(job.mode, (total ?: -1L).toDouble(), job.verdict.has("upi"))
    }

    /**
     * The text shown is the detector's fixed text, not Llama's: gating skipped Llama ("gated"), every
     * reply failed the explanation checks ("checks_failed"), or the time budget ran out ("timeout").
     * The card says so instead of claiming it is AI-written.
     */
    private fun markDetectorText(reason: String) {
        llamaHeadSlot?.let { head ->
            (head.getChildAt(0) as? ImageView)?.setImageResource(R.drawable.ic_shield_check)
            (head.getChildAt(1) as? TextView)?.text = when (reason) {
                "gated" -> t("Fixed text from the detector. Llama was not used.")
                "timeout" -> t("Llama took too long, so this is the detector's fixed text.")
                else -> t("Llama's reply did not pass the checks, so this is the detector's fixed text.")
            }
        }
        (aiFootSlot as? LinearLayout)?.let { foot ->
            (foot.getChildAt(1) as? TextView)?.text =
                if (reason == "gated") t("Llama is skipped for NO RISK results so they finish faster. Turn it on in About.")
                else t("Fixed text from the detector, not written by AI.")
        }
        aiEnglishSlot?.text = n("detector_english")
    }

    private fun launch(intent: Intent) {
        try {
            startActivity(intent)
        } catch (e: Exception) {
            toast(t("Unable to open") + ": " + errorText(e))
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

    /** Amber note naming installed screen-sharing apps. Read by TalkBack as one block. */
    private fun remoteAppBanner(apps: List<String>): LinearLayout {
        val message = n("remote_app_banner").replace("{apps}", apps.joinToString(", "))
        return row().apply {
            gravity = Gravity.TOP
            background = shape(T.warnC, 14f, 1, T.warn)
            pad(this, 14, 12, 14, 12)
            add(this, icon(R.drawable.ic_triangle_alert, 18, T.warn), 18, 18)
            add(this, txt(message, 14f, T.onWarnC, 600, 20, raw = true), 0, -2, left = 10, weight = 1f)
            isFocusable = true
            a11yText(this, message)  // one TalkBack stop: the children are hidden
        }
    }

    /** Two outlined buttons. Nothing is sent: one copies text, the other opens the share sheet. */
    private fun shareRow(card: JSONObject): LinearLayout {
        val buttons = row().apply { gravity = Gravity.TOP }
        fun place(key: String, descKey: String, iconId: Int, left: Int, action: () -> Unit) {
            val en = L10n.en(key)
            val hi = L10n.hi(key)
            val main = if (L10n.hindi) hi else en
            val sub = if (L10n.hindi) "" else hi
            val view = reportButton(
                main, sub, iconId, T.brand, T.ink, T.ink2, true, n(key) + ". " + n(descKey), action
            )
            add(buttons, view, 0, -2, left = left, weight = 1f)
        }
        val lang = if (L10n.hindi) "hi" else "en"
        place("report_copy", "report_copy_desc", R.drawable.ic_clipboard, 0) {
            copyReport(card.optString("report_$lang").ifBlank { card.optString("report_en") })
        }
        place("family_send", "family_send_desc", R.drawable.ic_message, 8) {
            sendToFamily(card.optString("family_$lang").ifBlank { card.optString("family_en") })
        }
        stackWhenTight(buttons, 8)
        return buttons
    }

    private fun copyReport(text: String) {
        if (text.isBlank()) return
        try {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val clip = ClipData.newPlainText(n("report_copy"), text)
            if (Build.VERSION.SDK_INT >= 33) {
                // Codes are masked, but the report can quote the message: keep it out of the preview.
                clip.description.extras = android.os.PersistableBundle().apply {
                    putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true)
                }
            }
            clipboard.setPrimaryClip(clip)
            toast(n("report_copied"))
        } catch (t: Throwable) {
            Log.e(TAG, "report copy failed", t)
            toast(n("report_copy_fail"))
        }
    }

    /** ACTION_SEND through the chooser. The user picks the app and the person; Prahari is left out. */
    private fun sendToFamily(text: String) {
        if (text.isBlank()) return
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        val chooser = Intent.createChooser(send, n("family_chooser")).apply {
            putExtra(Intent.EXTRA_EXCLUDE_COMPONENTS, arrayOf(ComponentName(this@MainActivity, MainActivity::class.java)))
        }
        launch(chooser)
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
            textAlignment = View.TEXT_ALIGNMENT_VIEW_START
        }
        add(labels, enView)
        val hiView = if (hi.isNotBlank()) txt(hi, 12f, hiColor, 400, 16).apply {
            textAlignment = View.TEXT_ALIGNMENT_VIEW_START
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
        showScreen(root)
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
                contentDescription = t("Testing whether this app can open a connection")
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
        val banner = banner(p, why, t("Tested just now") + " · ${net.elapsed} ms", R.drawable.ic_lock)
        add(body, banner)
        banner.post { if (!isDestroyed) banner.announceForAccessibility("${t(p.title)}. ${t(why)}") }
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

    /** Same SharedPreferences key as the History screen switch. */
    private fun historyHomeRow(): LinearLayout {
        val on = HistoryStore.enabled(this)
        val line = row().apply {
            background = ripple(shape(T.white, 16f, 1, T.outline2))
            pad(this, 14, 8, 8, 8)
            minimumHeight = dp(48)
        }
        val bubble = FrameLayout(this).apply {
            background = shape(T.brandC, 20f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(icon(R.drawable.ic_list, 20, T.brand), FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER))
        }
        add(line, bubble, 40, 40)
        val text = col().apply {
            minimumHeight = dp(48)
            setOnClickListener { showHistory() }
        }
        add(text, txt(n("recent"), 15f, T.ink, 600, 20, raw = true))
        add(text, txt(if (on) n("history_local_only") else n("history_off"), 13f, T.ink2, 400, 18, raw = true))
        add(line, text, 0, -2, left = 12, weight = 1f)
        val sw = Switch(this).apply {
            isChecked = on
            minimumWidth = dp(48)
            minimumHeight = dp(48)
            contentDescription = n("history_toggle")
            setOnCheckedChangeListener { _, checked ->
                HistoryStore.setEnabled(this@MainActivity, checked)
                showHome()
            }
        }
        add(line, sw, -2, -2)
        text.contentDescription = n("recent")
        return line
    }

    private fun navRow(iconId: Int, title: String, subtitle: String, action: () -> Unit): LinearLayout {
        val line = row().apply {
            background = ripple(shape(T.white, 16f, 1, T.outline2))
            pad(this, 14, 12, 12, 12)
            minimumHeight = dp(48)
            setOnClickListener { action() }
        }
        val bubble = FrameLayout(this).apply {
            background = shape(T.brandC, 20f)
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(icon(iconId, 20, T.brand), FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER))
        }
        add(line, bubble, 40, 40)
        val text = col()
        add(text, txt(title, 15f, T.ink, 600, 20, raw = true))
        if (subtitle.isNotBlank()) add(text, txt(subtitle, 13f, T.ink2, 400, 18, raw = true))
        add(line, text, 0, -2, left = 12, weight = 1f)
        add(line, icon(R.drawable.ic_chevron_right, 20, T.ink3), 20, 20)
        asButton(line, if (subtitle.isBlank()) title else "$title. $subtitle")
        return line
    }

    private fun showHistory() {
        screen = "history"
        visibleJob = null
        networkBody = null
        val root = root(n("recent"))
        add(root, bar(n("recent"), true), -1, -2)
        val body = scrollBody(root)
        val enabled = HistoryStore.enabled(this)
        val toggle = row().apply {
            background = shape(T.white, 16f, 1, T.outline2)
            pad(this, 14, 8, 14, 8)
            minimumHeight = dp(48)
        }
        add(toggle, txt(n("history_toggle"), 15f, T.ink, 600, 20, raw = true), 0, -2, weight = 1f)
        val sw = Switch(this).apply {
            isChecked = enabled
            minimumWidth = dp(48)
            minimumHeight = dp(48)
            contentDescription = n("history_toggle")
            setOnCheckedChangeListener { _, on ->
                HistoryStore.setEnabled(this@MainActivity, on)
                post { showHistory() }
            }
        }
        add(toggle, sw, -2, -2)
        add(body, toggle)
        val items = HistoryStore.list(this)
        if (!enabled) add(body, txt(n("history_off"), 13f, T.ink2, 400, 18, raw = true), top = 12)
        if (items.isEmpty()) {
            add(body, txt(n("history_empty"), 15f, T.ink2, 400, 22, raw = true), top = 16)
        }
        items.forEach { entry ->
            val card = card()
            val title = when (entry.level) {
                "danger" -> t("DANGEROUS")
                "warn" -> t("SUSPICIOUS")
                "alert" -> t("CHECK THIS ALERT")
                else -> t("NO RISK FOUND")
            }
            val whenText = DateUtils.getRelativeTimeSpanString(entry.at, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS)
            add(card, txt("$title · ${t(modeNames[entry.mode.coerceIn(0, modeNames.lastIndex)])}", 15f, T.ink, 700, 20, raw = true))
            add(card, txt(whenText.toString(), 12f, T.ink3, 400, 16, raw = true), top = 2)
            if (entry.snippet.isNotBlank()) add(card, txt(entry.snippet, 14f, T.ink2, 400, 20, raw = true), top = 6)
            add(body, card, top = 10)
        }
        bottom(root, n("clear_history"), outlined = true) {
            HistoryStore.clear(this)
            showHistory()
        }
        showScreen(root)
    }

    private fun pickQr() {
        val intent = if (Build.VERSION.SDK_INT >= 33) {
            Intent(android.provider.MediaStore.ACTION_PICK_IMAGES).apply { type = "image/*" }
        } else {
            Intent(Intent.ACTION_GET_CONTENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "image/*"
            }
        }
        try {
            @Suppress("DEPRECATION")
            startActivityForResult(intent, QR_REQUEST)
        } catch (t: Throwable) {
            Log.e(TAG, "photo picker failed", t)
            toast(n("qr_fail"))
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == ApkInspector.PICK_REQUEST) {
            if (resultCode == RESULT_OK) data?.data?.let { beginApkCheck(it) }
            return
        }
        if (requestCode != QR_REQUEST || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        Thread({
            val text = try {
                val bitmap = loadQrBitmap(uri)
                try {
                    bitmap?.let { decodeQr(it) }
                } finally {
                    if (bitmap != null && !bitmap.isRecycled) bitmap.recycle()
                }
            } catch (t: Throwable) {
                Log.e(TAG, "qr decode failed", t)
                null
            }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                if (text.isNullOrBlank()) {
                    toast(n("qr_fail"))
                    return@runOnUiThread
                }
                // The decoded text is checked here. It is never opened as a link or a UPI intent.
                inputValue = text
                // Back to Home and Check again on the same text keeps the QR medium.
                sharedText = text
                sharedSource = "qr"
                beginCheck(detectMode(text), text, "qr", "")
            }
        }, "prahari-qr").start()
    }

    private fun loadQrBitmap(uri: Uri): Bitmap? {
        return try {
            if (Build.VERSION.SDK_INT >= 28) {
                val source = ImageDecoder.createSource(contentResolver, uri)
                ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                    decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                    val big = maxOf(info.size.width, info.size.height)
                    if (big > 1024) {
                        val scale = 1024.0 / big
                        decoder.setTargetSize(
                            (info.size.width * scale).toInt().coerceAtLeast(1),
                            (info.size.height * scale).toInt().coerceAtLeast(1)
                        )
                    }
                }
            } else {
                contentResolver.openInputStream(uri)?.use { stream ->
                    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                    BitmapFactory.decodeStream(stream, null, bounds)
                    val sample = run {
                        var value = 1
                        val big = maxOf(bounds.outWidth, bounds.outHeight)
                        while (big / value > 1024) value *= 2
                        value
                    }
                    contentResolver.openInputStream(uri)?.use { again ->
                        BitmapFactory.decodeStream(again, null, BitmapFactory.Options().apply { inSampleSize = sample })
                    }
                }
            }
        } catch (t: Throwable) {
            Log.e(TAG, "image read failed", t)
            null
        }
    }

    /** Local decoder only. Versions above 10 and micro QR come back empty. The bitmap is recycled. */
    private fun decodeQr(bitmap: Bitmap): String? {
        var scaled: Bitmap? = null
        return try {
            val big = maxOf(bitmap.width, bitmap.height)
            val sample = if (big > 1024) {
                val scale = 1024f / big
                Bitmap.createScaledBitmap(
                    bitmap,
                    (bitmap.width * scale).toInt().coerceAtLeast(21),
                    (bitmap.height * scale).toInt().coerceAtLeast(21),
                    true
                ).also { scaled = it }
            } else bitmap
            val w = sample.width
            val h = sample.height
            val pixels = IntArray(w * h)
            sample.getPixels(pixels, 0, w, 0, 0, w, h)
            val gray = ByteArray(w * h)
            for (i in pixels.indices) {
                val color = pixels[i]
                val y = (Color.red(color) * 30 + Color.green(color) * 59 + Color.blue(color) * 11) / 100
                gray[i] = y.toByte()
            }
            if (!Python.isStarted()) null
            else {
                val raw = Python.getInstance().getModule("qrdec").callAttr("decode_gray", gray, w, h)
                val text = raw?.toString().orEmpty()
                if (text.isBlank() || text == "None") null else text
            }
        } finally {
            scaled?.let { if (!it.isRecycled) it.recycle() }
            if (!bitmap.isRecycled) bitmap.recycle()
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
        add(head, title, 0, -2, left = 12, weight = 1f)
        add(sheet, head, top = 14)
        val descriptions = listOf(
            Triple(R.drawable.ic_wifi_off, "Runs fully offline", "The app has no internet permission, so nothing you check can be sent anywhere. Airplane mode works."),
            Triple(R.drawable.ic_cpu, "Llama 3.2 1B on this phone",
                "Runs on this phone's CPU through ExecuTorch (INT4, XNNPACK). It only writes the explanation."),
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
        divider(sheet)
        val gateRow = row().apply { pad(this, 0, 11, 0, 11); minimumHeight = dp(48) }
        val gateText = col()
        add(gateText, txt("Explain NO RISK results with Llama", 15f, T.ink, 600, 20))
        add(gateText, txt("Off: NO RISK results show the detector's fixed text and skip Llama, so they finish faster. DANGEROUS, SUSPICIOUS and CHECK THIS ALERT results always use Llama.", 13f, T.ink2, 400, 18), top = 2)
        add(gateRow, gateText, 0, -2, weight = 1f)
        val gateSwitch = Switch(this).apply {
            isChecked = Bridge.explainCleared
            minimumHeight = dp(48)
            minimumWidth = dp(48)
            contentDescription = t("Explain NO RISK results with Llama")
            setOnCheckedChangeListener { _, on -> setExplainCleared(on) }
        }
        add(gateRow, gateSwitch, -2, -2, left = 12)
        // The whole row toggles, so the target is not only the small switch.
        gateRow.setOnClickListener { gateSwitch.toggle() }
        add(sheet, gateRow)
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
            clipToPadding = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            addView(column, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        }
        val sheetBottom = sheet.paddingBottom
        scroll.setOnApplyWindowInsetsListener { _, insets ->
            val nav = if (Build.VERSION.SDK_INT >= 30) {
                insets.getInsets(WindowInsets.Type.navigationBars()).bottom
            } else {
                @Suppress("DEPRECATION")
                insets.systemWindowInsetBottom
            }
            val clear = sheetBottom + nav + dp(8)
            if (sheet.paddingBottom != clear) {
                sheet.setPadding(sheet.paddingLeft, sheet.paddingTop, sheet.paddingRight, clear)
            }
            insets
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
        scroll.requestApplyInsets()
    }

    override fun onPause() {
        stopSpeech()
        super.onPause()
    }

    override fun onStop() {
        stopSpeech()
        super.onStop()
    }

    override fun onDestroy() {
        stopSpeech()
        try { speech?.shutdown() } catch (_: Throwable) {}
        speech = null
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
