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
import android.text.TextUtils
import android.text.TextWatcher
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.*
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

private object T {
    val bg = Color.parseColor("#F4F5F9"); val white = Color.WHITE
    val surface2 = Color.parseColor("#EEF0F5"); val outline = Color.parseColor("#DCE0E8")
    val outline2 = Color.parseColor("#C3C9D5"); val ink = Color.parseColor("#121626")
    val ink2 = Color.parseColor("#4B5266"); val ink3 = Color.parseColor("#6B7186")
    val brand = Color.parseColor("#283593"); val brandC = Color.parseColor("#E8EAF6")
    val danger = Color.parseColor("#B3261E"); val dangerC = Color.parseColor("#FDECEA")
    val onDanger = Color.parseColor("#8C1D18"); val warnBanner = Color.parseColor("#F5B01A")
    val onWarn = Color.parseColor("#2B1B00"); val warn = Color.parseColor("#8A5300")
    val warnC = Color.parseColor("#FFF3D6"); val onWarnC = Color.parseColor("#5E3A00")
    val ok = Color.parseColor("#1E7B3C"); val okBanner = Color.parseColor("#E5F4EA")
    val okLine = Color.parseColor("#A9D6B6"); val onOk = Color.parseColor("#0D4F27")
}

class MainActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor()
    @Volatile private var module: LlmModule? = null
    private var loadError: String? = null // worker thread only
    @Volatile private var runId = 0
    private var screen = "home"
    private var selectedMode = 0
    private var inputValue = ""
    private lateinit var input: EditText
    private val modelFile = "Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte"
    private val tokenizerFile = "tokenizer.model"
    private val kinds = arrayOf("sms", "url", "flow")
    private val modeNames = arrayOf("SMS", "Link", "Network")
    private val modeHindi = arrayOf("संदेश", "लिंक", "नेटवर्क")
    private val modeIcons = intArrayOf(R.drawable.ic_message, R.drawable.ic_link, R.drawable.ic_activity)
    private val labels = arrayOf("Message you received", "Link you want to open", "Network event or flow JSON")
    private val hints = arrayOf("Paste or type the SMS or WhatsApp message", "Paste the full link, e.g. https://…", "Describe the traffic, or paste flow JSON")
    private data class Sample(val label: String, val mode: Int, val value: String)
    private val samples = listOf(
        Sample("KYC scam SMS", 0, "Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked"),
        Sample("Bill reminder", 0, "Your electricity bill of Rs 1,240 is due on 15 Nov. Pay through the mahadiscom app; no link is attached."),
        Sample("Lookalike link", 1, "http://amaz0n-refund-help.top/claim?id=8812"),
        Sample("Official link", 1, "https://www.irctc.co.in/nget/train-search"),
        Sample("Port scan", 2, "tcp connections to 200 different ports on 10.0.0.5 within 10 seconds, all rejected"),
        Sample("Hinglish electricity", 0, "Aapka bijli connection aaj raat 9:30 kat jayega. Turant 98XXXXXX12 par call karein ya http://uppcl-bill-pay.top kholein."),
        Sample("Bank OTP alert (genuine)", 0, "SBI: Rs 2,450 debited via UPI. OTP 482910 kisi se share mat karein. If not you, block card in YONO app.")
    )
    private val density get() = resources.displayMetrics.density
    private fun dp(n: Number) = (n.toFloat() * density + .5f).toInt()
    private fun shape(fill: Int, radius: Float, stroke: Int = 0, strokeColor: Int = T.outline) = GradientDrawable().apply {
        setColor(fill); cornerRadius = radius * density
        if (stroke > 0) setStroke(dp(stroke), strokeColor)
    }
    private fun ripple(bg: GradientDrawable) = RippleDrawable(ColorStateList.valueOf(0x33121626), bg, null)
    private fun txt(value: CharSequence, size: Float, color: Int = T.ink, weight: Int = 400, line: Int = 0) = TextView(this).apply {
        text = value; textSize = size; setTextColor(color); includeFontPadding = false
        typeface = Typeface.create(Typeface.DEFAULT, weight, false)
        if (line > 0) lineHeight = dp(line)
    }
    private fun icon(id: Int, size: Int, tint: Int) = ImageView(this).apply {
        setImageResource(id); setColorFilter(tint); layoutParams = LinearLayout.LayoutParams(dp(size), dp(size))
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
        background = shape(fill, 16f, if (border) 1 else 0); pad(this, 16, 14, 16, 14)
    }
    private fun heading(en: String, hi: String) = txt("${en.uppercase(Locale.ROOT)} · $hi", 11f, T.ink2, 700, 16).apply { letterSpacing = .04f }
    private fun iconText(id: Int, text: String, color: Int, size: Float = 14f, iconSize: Int = 18): LinearLayout = row().apply {
        add(this, icon(id, iconSize, color), iconSize, iconSize)
        add(this, txt(text, size, color, 600), -2, -2, left = 6)
    }
    private fun button(text: String, id: Int? = null, fill: Int = T.brand, textColor: Int = T.white, outlined: Boolean = false, action: () -> Unit): LinearLayout = row().apply {
        gravity = Gravity.CENTER; minimumHeight = dp(48)
        background = ripple(shape(if (outlined) T.white else fill, 16f, if (outlined) 1 else 0, T.outline2))
        if (id != null) add(this, icon(id, 20, textColor), 20, 20)
        add(this, txt(text, 16f, textColor, 600).apply { gravity = Gravity.CENTER }, -2, -2, left = if (id != null) 10 else 0)
        isClickable = true; isFocusable = true; setOnClickListener { action() }
    }
    private fun iconButton(id: Int, description: String, action: () -> Unit) = FrameLayout(this).apply {
        minimumWidth = dp(48); minimumHeight = dp(48); contentDescription = description
        isClickable = true; isFocusable = true; background = ripple(shape(T.bg, 24f))
        addView(icon(id, 24, T.ink), FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
        setOnClickListener { action() }
    }
    private fun logo(): FrameLayout = FrameLayout(this).apply {
        background = shape(T.brand, 11f)
        addView(icon(R.drawable.ic_shield, 22, T.white), FrameLayout.LayoutParams(dp(22), dp(22), Gravity.CENTER))
        addView(View(this@MainActivity).apply { background = shape(T.white, 3f) }, FrameLayout.LayoutParams(dp(4), dp(4), Gravity.CENTER))
    }
    private fun root(): LinearLayout = col().apply { setBackgroundColor(T.bg); fitsSystemWindows = true; isFocusableInTouchMode = true }
    private fun bar(title: String, offline: Boolean): LinearLayout = row().apply {
        pad(this, 4, 0, 8, 0); add(this, iconButton(R.drawable.ic_arrow_left, "Back") { goHome() }, 48, 48)
        add(this, txt(title, 20f, T.ink, 600), 0, -2, left = 4, weight = 1f)
        if (offline) add(this, iconText(R.drawable.ic_wifi_off, "Offline", T.brand, 12f, 14).apply {
            background = shape(T.brandC, 14f); pad(this, 10, 6, 10, 6)
        }, -2, -2)
    }
    private fun bottom(parent: LinearLayout, text: String, outlined: Boolean = false, id: Int? = null, action: () -> Unit) {
        val box = col().apply { setBackgroundColor(T.white) }; divider(box)
        val wrap = col().apply { pad(this, 16, 10, 16, 6) }
        add(wrap, button(text, id, textColor = if (outlined) T.ink else T.white, outlined = outlined, action = action), -1, 52)
        add(box, wrap); add(parent, box)
    }
    private fun scrollBody(parent: LinearLayout): LinearLayout {
        val body = col().apply { pad(this, 16, 0, 16, 16) }
        val scroll = ScrollView(this).apply { isFillViewport = false; clipToPadding = false; addView(body) }
        add(parent, scroll, -1, 0, weight = 1f)
        return body
    }
    private fun files(): Pair<File, File>? = getExternalFilesDir(null)?.let { Pair(File(it, modelFile), File(it, tokenizerFile)) }
    private fun missingMessage(): String? {
        val f = files()
        return if (f == null || !f.first.isFile || !f.second.isFile) "Model files are missing. Copy $modelFile and $tokenizerFile to ${f?.first?.parent ?: "the app external files directory"}. See README." else null
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = T.bg; window.navigationBarColor = T.bg
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        showHome()
        worker.execute { if (missingMessage() == null) try { ensureModel() } catch (e: Throwable) { loadError = errorText(e) } }
    }
    private fun ensureModel(): LlmModule {
        module?.let { return it }
        loadError?.let { throw IllegalStateException(it) }
        val f = files() ?: throw IllegalStateException(missingMessage() ?: "Model files missing")
        missingMessage()?.let { throw IllegalStateException(it) }
        val m = LlmModule(f.first.path, f.second.path, 0f)
        try { m.load(); module = m; return m } catch (e: Throwable) { try { m.close() } catch (_: Throwable) {}; throw e }
    }
    private fun errorText(e: Throwable) = "${e.javaClass.simpleName}: ${e.message}"
    private fun goHome(clear: Boolean = false) {
        runId++; module?.stop(); if (clear) inputValue = ""; showHome()
    }
    private fun showHome() {
        screen = "home"
        val root = root(); val scroller = ScrollView(this).apply { isFillViewport = true }
        val all = col(); scroller.addView(all); add(root, scroller, -1, 0, weight = 1f)
        val brand = row().apply { pad(this, 16, 4, 8, 4) }
        add(brand, logo(), 36, 36)
        val name = col(); add(name, txt("Prahari", 20f, T.ink, 700, 24)); add(name, txt("प्रहरी · scam & threat check", 12f, T.ink3, 500, 16))
        add(brand, name, 0, -2, left = 10, weight = 1f); add(brand, iconButton(R.drawable.ic_info, "About Prahari") { showAbout() }, 48, 48)
        add(all, brand, -1, 60)
        val body = col().apply { pad(this, 16, 0, 16, 8) }; add(all, body, -1, 0, weight = 1f)
        add(body, txt("Check before you tap", 24f, T.ink, 700, 30), top = 2)
        add(body, txt("टैप करने से पहले जाँचें · works with no internet", 14f, T.ink2, 400, 20), top = 2)
        val seg = row().apply { background = shape(T.surface2, 14f); pad(this, 4, 4, 4, 4) }
        val segments = mutableListOf<LinearLayout>()
        val inputCard = col().apply { pad(this, 16, 14, 16, 8) }
        val label = txt(labels[selectedMode], 12f, T.brand, 600, 16)
        input = EditText(this).apply {
            setText(inputValue); hint = hints[selectedMode]; setTextColor(T.ink); setHintTextColor(T.ink3)
            textSize = 16f; lineHeight = dp(24); includeFontPadding = false; background = null
            gravity = Gravity.TOP or Gravity.START; inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE or android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            setPadding(0, 0, 0, 0)
        }
        fun refreshSegments() {
            segments.forEachIndexed { i, v ->
                v.background = if (i == selectedMode) shape(T.white, 10f, 1, T.outline) else null
                val top = v.getChildAt(0) as LinearLayout
                (top.getChildAt(0) as ImageView).setColorFilter(if (i == selectedMode) T.brand else T.ink2)
                (top.getChildAt(1) as TextView).setTextColor(if (i == selectedMode) T.brand else T.ink2)
                (v.getChildAt(1) as TextView).setTextColor(if (i == selectedMode) T.brand else T.ink2)
            }
            label.text = labels[selectedMode]; input.hint = hints[selectedMode]
        }
        for (i in kinds.indices) {
            val s = col().apply { gravity = Gravity.CENTER; isClickable = true; isFocusable = true; contentDescription = "${modeNames[i]} · ${modeHindi[i]}" }
            add(s, iconText(modeIcons[i], modeNames[i], T.ink2, 14f, 16), -2, -2)
            add(s, txt(modeHindi[i], 11f, T.ink2, 500), -2, -2)
            s.setOnClickListener { selectedMode = i; refreshSegments() }; segments.add(s)
            add(seg, s, 0, -1, left = if (i == 0) 0 else 4, weight = 1f)
        }
        add(body, seg, -1, 60, top = 16)
        fun focusBorder() { inputCard.background = shape(T.white, 16f, if (input.hasFocus()) 2 else 1, if (input.hasFocus()) T.brand else T.outline2) }
        input.setOnFocusChangeListener { _, _ -> focusBorder() }
        add(inputCard, label); add(inputCard, input, -1, 0, top = 6, weight = 1f)
        val tools = row(); val paste = iconText(R.drawable.ic_clipboard, "Paste", T.brand)
        paste.minimumHeight = dp(48); paste.setOnClickListener {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val item = clipboard.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)
            if (item != null) input.setText(item)
        }
        val clear = iconText(R.drawable.ic_x, "Clear", T.ink2).apply { minimumHeight = dp(48); setOnClickListener { input.setText("") } }
        add(tools, paste, -2, -2); add(tools, View(this), 0, 1, weight = 1f); add(tools, clear, -2, -2)
        add(inputCard, tools); add(body, inputCard, -1, 228, top = 12); focusBorder(); refreshSegments()
        add(body, heading("Try a sample", "नमूना आज़माएँ"), top = 12)
        val chips = row(); samples.forEach { sample ->
            val chip = iconText(modeIcons[sample.mode], sample.label, T.ink2, 14f, 16).apply {
                (getChildAt(1) as TextView).setTextColor(T.ink); background = ripple(shape(T.white, 18f, 1, T.outline2)); pad(this, 10, 0, 14, 0)
                minimumHeight = dp(48); setOnClickListener { selectedMode = sample.mode; refreshSegments(); input.setText(sample.value) }
            }; add(chips, chip, -2, 48, left = if (chips.childCount == 0) 0 else 8)
        }
        add(body, HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; addView(chips) }, -1, 48, top = 4)
        val check = button("Check on this phone", R.drawable.ic_shield_check) { startCheck() }.apply { contentDescription = "Check on this phone · इस फ़ोन पर जाँचें" }
        add(body, check, -1, 56, top = 8)
        fun refreshInput() {
            inputValue = input.text.toString(); clear.visibility = if (inputValue.isEmpty()) View.INVISIBLE else View.VISIBLE
            val enabled = inputValue.isNotBlank(); check.isEnabled = enabled
            check.background = ripple(shape(if (enabled) T.brand else T.surface2, 16f))
            (check.getChildAt(0) as ImageView).setColorFilter(if (enabled) T.white else T.ink3)
            (check.getChildAt(1) as TextView).setTextColor(if (enabled) T.white else T.ink3)
        }
        input.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { refreshInput() }
            override fun afterTextChanged(s: Editable?) {}
        }); refreshInput()
        missingMessage()?.let { add(body, txt(it, 12f, T.onDanger, 400, 17), top = 8) }
        add(body, View(this), -1, 0, weight = 1f)
        val offline = row().apply { background = ripple(shape(T.white, 16f, 1)); pad(this, 14, 12, 12, 12); isClickable = true; setOnClickListener { showNetwork() } }
        val bubble = FrameLayout(this).apply { background = shape(T.brandC, 20f); addView(icon(R.drawable.ic_wifi_off, 20, T.brand), FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER)) }
        add(offline, bubble, 40, 40); val offlineText = col(); add(offlineText, txt("Prove it's offline", 15f, T.ink, 600, 20)); add(offlineText, txt("Try to reach the internet from this app", 13f, T.ink2, 400, 18))
        add(offline, offlineText, 0, -2, left = 12, weight = 1f); add(offline, icon(R.drawable.ic_chevron_right, 20, T.ink3), 20, 20)
        add(body, offline, top = 16)
        add(body, iconText(R.drawable.ic_lock, "Nothing you paste leaves this phone", T.ink3, 12f, 13).apply { gravity = Gravity.CENTER }, -1, -2, top = 12)
        setContentView(root)
    }
    private fun startCheck() {
        val value = input.text.toString()
        if (value.isBlank()) { Toast.makeText(this, "Paste a message, link or network event first.", Toast.LENGTH_SHORT).show(); return }
        inputValue = value
        (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).hideSoftInputFromWindow(input.windowToken, 0)
        val id = ++runId; val mode = selectedMode; val started = SystemClock.elapsedRealtime()
        showChecking(mode, value)
        worker.execute {
            try {
                val bridge = Python.getInstance().getModule("mobile")
                val verdict = JSONObject(bridge.callAttr("verdict", kinds[mode], value).toString())
                require(verdict.optString("level") in listOf("danger", "warn", "clear")) { "Invalid detector verdict" }
                if (id != runId) return@execute
                runOnUiThread { if (id == runId) showResult(verdict, mode, value, started) }
                if (id != runId) return@execute
                val explanation = try {
                    val f = files() ?: throw IllegalStateException(missingMessage() ?: "Model files missing")
                    ensureModel()
                    if (id != runId) throw IllegalStateException("Check cancelled")
                    JSONObject(bridge.callAttr("explain", Runner(f.first.path, f.second.path, id)).toString())
                } catch (e: Throwable) { JSONObject().put("error", errorText(e)) }
                val total = SystemClock.elapsedRealtime() - started
                val pss = Debug.getPss() / 1024.0
                runOnUiThread { if (id == runId && screen == "result") updateExplanation(explanation, verdict, total, pss) }
            } catch (e: Throwable) {
                val message = "Check failed: ${errorText(e)}. The model may not run on this device."
                runOnUiThread { if (id == runId) { showHome(); Toast.makeText(this, message, Toast.LENGTH_LONG).show() } }
            }
        }
    }
    private fun showChecking(mode: Int, value: String) {
        screen = "checking"; val root = root(); add(root, bar("Checking", true), -1, 56)
        val body = scrollBody(root)
        val what = card(); val summary = row(); add(summary, icon(modeIcons[mode], 18, T.ink2), 18, 18)
        add(summary, txt(value, 14f, T.ink2, 400, 20).apply { maxLines = 3; ellipsize = TextUtils.TruncateAt.END }, 0, -2, left = 12, weight = 1f)
        add(what, summary); add(body, what)
        val ring = FrameLayout(this); val progress = ProgressBar(this, null, android.R.attr.progressBarStyleLarge).apply { indeterminateTintList = ColorStateList.valueOf(T.brand) }
        ring.addView(progress, FrameLayout.LayoutParams(dp(132), dp(132), Gravity.CENTER))
        val center = FrameLayout(this).apply { background = shape(T.brandC, 42f); addView(icon(R.drawable.ic_shield, 40, T.brand), FrameLayout.LayoutParams(dp(40), dp(40), Gravity.CENTER)) }
        ring.addView(center, FrameLayout.LayoutParams(dp(84), dp(84), Gravity.CENTER)); add(body, ring, -1, 132, top = 24)
        add(body, txt("Checking on this phone…", 22f, T.ink, 700, 28).apply { gravity = Gravity.CENTER }, top = 18)
        add(body, txt("इस फ़ोन पर जाँच हो रही है", 14f, T.ink2, 400, 20).apply { gravity = Gravity.CENTER }, top = 4)
        val steps = card(); listOf(Triple("Checking scam signals", "Rules + detector", 0), Triple("Llama 3.2 is writing an explanation", "On-device · usually 2–4 s", 1), Triple("Safety steps", "From the vetted list", 2)).forEachIndexed { index, item ->
            if (index > 0) divider(steps)
            val r = row().apply { minimumHeight = dp(56); if (index > 0) alpha = .55f }
            if (index == 0) add(r, ProgressBar(this, null, android.R.attr.progressBarStyleSmall).apply { indeterminateTintList = ColorStateList.valueOf(T.brand) }, 24, 24)
            else add(r, View(this).apply { background = shape(T.white, 12f, 2, T.outline2) }, 24, 24)
            val labels = col(); add(labels, txt(item.first, 15f, T.ink, 500, 21)); add(labels, txt(item.second, 12f, T.ink3, 400, 16))
            add(r, labels, 0, -2, left = 12, weight = 1f); add(steps, r)
        }; add(body, steps, top = 18)
        add(body, iconText(R.drawable.ic_wifi_off, "No internet used. You can switch on airplane mode.", T.ink3, 12f, 13).apply { gravity = Gravity.CENTER }, top = 16)
        bottom(root, "Cancel", outlined = true) { goHome() }; setContentView(root)
    }
    private data class Palette(val fill: Int, val on: Int, val chip: Int, val chipText: Int, val number: Int, val glyph: Int, val iconFill: Int, val title: String, val hindi: String)
    private fun palette(level: String) = when (level) {
        "danger" -> Palette(T.danger, T.white, T.dangerC, T.onDanger, T.onDanger, R.drawable.ic_octagon_x, 0x2EFFFFFF, "DANGEROUS", "खतरनाक")
        "warn" -> Palette(T.warnBanner, T.onWarn, T.warnC, T.onWarnC, T.warn, R.drawable.ic_triangle_alert, 0x1F2B1B00, "SUSPICIOUS", "संदिग्ध")
        else -> Palette(T.okBanner, T.onOk, T.okBanner, T.onOk, T.onOk, R.drawable.ic_shield, T.white, "NO RISK FOUND", "कोई खतरा नहीं मिला")
    }
    private fun sentence(s: String): String = s.trim().replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
    private fun strings(a: JSONArray?): List<String> = if (a == null) emptyList() else (0 until a.length()).map { a.optString(it) }
    private fun banner(p: Palette, why: String, meta: String, metaIcon: Int, stillVerify: Boolean = false): LinearLayout {
        val box = col().apply { background = shape(p.fill, 20f, if (stillVerify) 1 else 0, T.okLine); pad(this, 18, 18, 18, 16) }
        val top = row(); val bubble = FrameLayout(this).apply {
            background = shape(p.iconFill, 26f)
            addView(icon(p.glyph, 30, if (stillVerify) T.ok else p.on), FrameLayout.LayoutParams(dp(30), dp(30), Gravity.CENTER))
        }
        add(top, bubble, 52, 52); val titles = col()
        add(titles, txt(p.hindi, 15f, p.on, 600, 20)); add(titles, txt(p.title, if (stillVerify) 25f else 28f, p.on, 800, 32).apply { letterSpacing = .02f })
        if (stillVerify) add(titles, iconText(R.drawable.ic_alert_circle, "Still verify · फिर भी जाँच लें", T.onOk, 13f, 14).apply { background = shape(T.white, 13f, 1, T.okLine); pad(this, 8, 5, 8, 5) }, -2, -2, top = 6)
        add(top, titles, 0, -2, left = 14, weight = 1f); add(box, top)
        add(box, txt(why, 16f, p.on, 500, 22), top = 12)
        add(box, iconText(metaIcon, meta, p.on, 12f, 14).apply { alpha = .9f }, -1, -2, top = 10)
        return box
    }
    private lateinit var explanationText: TextView
    private lateinit var statsDetails: LinearLayout
    private lateinit var statsSummary: TextView
    private lateinit var metaText: TextView
    private fun showResult(data: JSONObject, mode: Int, value: String, started: Long) {
        screen = "result"; val level = data.optString("level", "clear"); val p = palette(level); val clear = level == "clear"
        val evidence = strings(data.optJSONArray("evidence")); val actions = strings(data.optJSONArray("actions"))
        val fallback = when (level) { "danger" -> "Strong scam signals found."; "warn" -> "Some warning signs found."; else -> "No scam signals found." }
        val first = evidence.firstOrNull()?.let { sentence(it).trimEnd('.', '!', '?') + "." } ?: fallback
        val why = first + if (clear) " That is not a guarantee it is safe." else ""
        val root = root(); add(root, bar("Result", true), -1, 56); val body = scrollBody(root)
        val b = banner(p, why, "${modeNames[mode]} · checked on this phone in ${formatMs((SystemClock.elapsedRealtime() - started).toDouble())}", modeIcons[mode], clear)
        metaText = ((b.getChildAt(2) as LinearLayout).getChildAt(1) as TextView)
        data.optString("scam_type", "").takeIf { it.isNotBlank() }?.let { add(b, txt("Type: ${sentence(it)}", 12f, p.on, 500, 16), top = 8) }
        add(body, b); b.post { b.announceForAccessibility("${p.title}. $why") }
        val steps = card(); add(steps, heading(if (clear) "Before you act" else "Do this now", if (clear) "कार्य करने से पहले" else "अभी यह करें"))
        actions.forEachIndexed { i, action ->
            val r = row().apply { gravity = Gravity.TOP }; val number = txt("${i + 1}", 13f, p.number, 700).apply { gravity = Gravity.CENTER; background = shape(p.chip, 13f) }
            add(r, number, 26, 26); add(r, txt(action, 15f, T.ink, 400, 21), 0, -2, left = 12, weight = 1f); add(steps, r, top = if (i == 0) 10 else 12)
        }
        if (mode != 2 && level == "danger") {
            val buttons = row(); add(buttons, button("Call 1930", R.drawable.ic_phone, T.danger) { dial() }, 0, 48, weight = 1f)
            add(buttons, button("Report online", R.drawable.ic_external, textColor = T.ink, outlined = true) { launch(Intent(Intent.ACTION_VIEW, Uri.parse("https://cybercrime.gov.in"))) }, 0, 48, left = 8, weight = 1f)
            add(steps, buttons, top = 14)
        } else if (mode != 2 && level == "warn") {
            divider(steps, 12); add(steps, iconText(R.drawable.ic_phone, "Lost money or shared details? Call 1930 now.", T.ink2, 13f, 16).apply { minimumHeight = dp(48); setOnClickListener { dial() } })
        } else if (clear) {
            divider(steps, 12); add(steps, iconText(R.drawable.ic_alert_circle, "Scammers copy real messages. If it asks for money or a code, check in the official app first.", T.ink2, 13f, 16).apply { minimumHeight = dp(48) }, top = 8)
        }
        add(body, steps, top = 12)
        if (evidence.isNotEmpty()) {
            val ec = card(); val hr = row(); add(hr, heading(if (clear) "What we saw" else "Why it's flagged", "संकेत"), 0, -2, weight = 1f)
            add(hr, txt("${evidence.size} ${if (evidence.size == 1) "signal" else "signals"}", 11f, T.ink3, 600), -2, -2); add(ec, hr)
            evidence.forEach { item ->
                val chip = row().apply { gravity = Gravity.TOP; background = shape(p.chip, 12f); pad(this, 10, 8, 12, 8) }
                add(chip, icon(if (clear) R.drawable.ic_check_circle else R.drawable.ic_alert_circle, 16, p.chipText), 16, 16)
                val text = SpannableString(sentence(item)); Regex("[a-z0-9-]+(\\.[a-z0-9-]+)+").findAll(text).forEach { m ->
                    text.setSpan(TypefaceSpan("monospace"), m.range.first, m.range.last + 1, 0); text.setSpan(StyleSpan(Typeface.BOLD), m.range.first, m.range.last + 1, 0); text.setSpan(RelativeSizeSpan(13f / 14f), m.range.first, m.range.last + 1, 0)
                }
                add(chip, txt(text, 14f, p.chipText, 400, 20), 0, -2, left = 8, weight = 1f); add(ec, chip, -1, -2, top = 8)
            }; add(body, ec, top = 12)
        }
        val llama = card(T.surface2, false); add(llama, iconText(R.drawable.ic_cpu, "Explained on this phone by Llama 3.2", T.ink2, 13f, 18))
        val explainRow = row().apply { gravity = Gravity.TOP }; add(explainRow, View(this).apply { setBackgroundColor(T.brand) }, 3, 48)
        explanationText = txt("Writing an explanation on this phone…", 15f, T.ink2, 400, 22).apply { setTypeface(typeface, Typeface.ITALIC) }
        add(explainRow, explanationText, 0, -2, left = 12, weight = 1f); add(llama, explainRow, top = 12)
        add(llama, iconText(R.drawable.ic_info, "AI-written and can be wrong. Follow the steps above.", T.ink2, 12f, 14), top = 12)
        add(body, llama, top = 12)
        val stats = card(); val header = row().apply { minimumHeight = dp(48); isClickable = true; isFocusable = true; contentDescription = "Toggle on-device stats" }
        add(header, icon(R.drawable.ic_cpu, 18, T.ink2), 18, 18); add(header, txt("On-device stats", 14f, T.ink2, 600), 0, -2, left = 10, weight = 1f)
        statsSummary = txt("${formatMs(data.optDouble("detector_ms", Double.NaN))} · …", 12f, T.ink3, 500); add(header, statsSummary, -2, -2)
        val chev = icon(R.drawable.ic_chevron_down, 20, T.ink2); add(header, chev, 20, 20, left = 8)
        add(stats, header); statsDetails = col().apply { visibility = View.GONE }; add(stats, statsDetails)
        header.setOnClickListener { val expanded = statsDetails.visibility == View.VISIBLE; statsDetails.visibility = if (expanded) View.GONE else View.VISIBLE; chev.rotation = if (expanded) 0f else 180f }
        fillStats(data, null, null, null); add(body, stats, top = 12)
        val checked = card(); add(checked, heading("You checked", "आपने जाँचा")); add(checked, txt(value, 14f, T.ink2, 400, 20).apply { setTextIsSelectable(true); if (mode != 0) typeface = Typeface.MONOSPACE }, top = 10); add(body, checked, top = 12)
        bottom(root, "Check another · दूसरा जाँचें") { goHome(true) }; setContentView(root)
    }
    private fun formatMs(value: Double): String = if (!value.isFinite() || value < 0) "—" else if (value < 1000) "${value.toInt()} ms" else String.format(Locale.US, "%.2f s", value / 1000)
    private fun fillStats(data: JSONObject, llm: JSONObject?, total: Long?, pss: Double?) {
        statsDetails.removeAllViews(); val tiles = row()
        val values = listOf(formatMs(data.optDouble("detector_ms", Double.NaN)), formatMs(llm?.optDouble("first_token_ms", Double.NaN) ?: Double.NaN), llm?.optDouble("decode_tps", Double.NaN)?.takeIf { it.isFinite() }?.let { String.format(Locale.US, "%.1f t/s", it) } ?: "—")
        listOf("Detector", "First token", "Decode speed").forEachIndexed { i, label ->
            val tile = col().apply { background = shape(T.surface2, 12f); pad(this, 10, 10, 10, 10) }
            add(tile, txt(values[i], 17f, T.ink, 700)); add(tile, txt(label, 11f, T.ink2, 500), top = 4)
            add(tiles, tile, 0, -2, left = if (i == 0) 0 else 8, weight = 1f)
        }; add(statsDetails, tiles, top = 4)
        val abi = Build.SUPPORTED_ABIS.firstOrNull() ?: "—"
        val foot = "Total ${total?.let { formatMs(it.toDouble()) } ?: "—"} · Memory ${pss?.let { String.format(Locale.US, "%.1f MB", it) } ?: "—"}\nLlama 3.2 1B INT4 · ExecuTorch · XNNPACK\nCPU ABI: $abi" + if (abi.startsWith("x86")) "\nx86 emulator: not Arm timings" else ""
        add(statsDetails, txt(foot, 12f, T.ink3, 400, 18).apply { typeface = Typeface.MONOSPACE }, top = 12)
        statsSummary.text = "${values[0]} · ${values[1]}"
    }
    private fun updateExplanation(result: JSONObject, verdict: JSONObject, total: Long, pss: Double) {
        val error = result.optString("error", "")
        val explanation = result.optString("explanation", "").trim()
        if (error.isNotEmpty() || explanation.isEmpty()) {
            explanationText.text = "Explanation unavailable on this phone. The verdict and steps above are complete." + if (error.isNotEmpty()) "\n$error" else ""
            explanationText.setTextColor(T.ink2); explanationText.setTypeface(explanationText.typeface, Typeface.ITALIC)
        } else { explanationText.text = explanation; explanationText.setTextColor(T.ink); explanationText.typeface = Typeface.DEFAULT }
        fillStats(verdict, result.optJSONObject("llm"), total, pss)
        metaText.text = "${modeNames[selectedMode]} · checked on this phone in ${formatMs(total.toDouble())}"
    }
    private fun launch(intent: Intent) { try { startActivity(intent) } catch (e: Exception) { Toast.makeText(this, "Unable to open: ${errorText(e)}", Toast.LENGTH_LONG).show() } }
    private fun dial() = launch(Intent(Intent.ACTION_DIAL, Uri.parse("tel:1930")))
    private fun showNetwork() {
        screen = "network"; val id = ++runId
        val root = root(); add(root, bar("Network check", false), -1, 56); val body = scrollBody(root)
        add(body, txt("Testing HTTPS…", 16f, T.ink2), top = 16)
        bottom(root, "Run again", true, R.drawable.ic_refresh) { showNetwork() }; setContentView(root)
        worker.execute {
            val start = SystemClock.elapsedRealtime(); var error: Exception? = null
            try {
                val c = URL("https://example.com").openConnection(); c.connectTimeout = 4000; c.readTimeout = 4000
                c.getInputStream().use { it.read() }
            } catch (e: Exception) { error = e }
            val elapsed = SystemClock.elapsedRealtime() - start; val failure = error
            runOnUiThread { if (id == runId && screen == "network") renderNetwork(body, failure, elapsed) }
        }
    }
    private fun renderNetwork(body: LinearLayout, error: Exception?, elapsed: Long) {
        body.removeAllViews(); val connected = error == null
        val p = Palette(if (connected) T.danger else T.brand, T.white, T.brandC, T.brand, T.brand, if (connected) R.drawable.ic_octagon_x else R.drawable.ic_wifi_off, 0x2EFFFFFF, if (connected) "CONNECTED" else "NO INTERNET", if (connected) "कनेक्शन सफल" else "इंटरनेट नहीं")
        val why = if (connected) "This app reached the internet. The offline claim failed on this build." else if (error is SecurityException) "This app cannot connect. Android blocked the request because Prahari has no internet permission." else "This request could not connect. See the exception below."
        add(body, banner(p, why, "Tested just now · took $elapsed ms", R.drawable.ic_lock))
        val tried = card(); add(tried, heading("What we tried", "हमने क्या आज़माया"))
        fun pairRow(key: String, value: View) {
            val r = row().apply { minimumHeight = dp(42) }; add(r, txt(key, 13f, T.ink2), 0, -2, weight = 1f); add(r, value, -2, -2); add(tried, r)
        }
        pairRow("Request", txt("HTTPS GET example.com", 12f, T.ink).apply { typeface = Typeface.MONOSPACE }); divider(tried)
        pairRow("Result", txt(if (connected) "Connected" else "Blocked", 12f, if (connected) T.onDanger else T.onOk, 700).apply {
            background = shape(if (connected) T.dangerC else T.okBanner, 12f); pad(this, 10, 5, 10, 5)
        })
        if (error != null) {
            divider(tried); add(tried, txt(errorText(error), 12f, T.ink2, 400, 17).apply { typeface = Typeface.MONOSPACE; background = shape(T.surface2, 10f); pad(this, 12, 10, 12, 10); setTextIsSelectable(true) }, top = 8)
        }
        add(body, tried, top = 12)
        if (!connected) {
            val means = card(); add(means, heading("What this means", "इसका मतलब"))
            val abi = Build.SUPPORTED_ABIS.firstOrNull() ?: ""
            val cpu = if (abi.startsWith("x86")) "The detector and Llama 3.2 run on this emulator's CPU." else "The detector and Llama 3.2 run on this phone's Arm CPU."
            listOf("Messages and links you check never leave this phone.", cpu, "Calls to 1930 or opening cybercrime.gov.in use your phone's dialler and browser, not this app.").forEach {
                val r = row().apply { gravity = Gravity.TOP }; add(r, icon(R.drawable.ic_check_circle, 20, T.ok), 20, 20)
                add(r, txt(it, 14f, T.ink, 400, 20), 0, -2, left = 12, weight = 1f); add(means, r, top = 12)
            }; add(body, means, top = 12)
        }
    }
    private fun showAbout() {
        val dialog = Dialog(this); dialog.requestWindowFeature(Window.FEATURE_NO_TITLE)
        val sheet = col().apply {
            background = GradientDrawable().apply { setColor(T.white); val r = 28f * density; cornerRadii = floatArrayOf(r, r, r, r, 0f, 0f, 0f, 0f) }
            pad(this, 20, 8, 20, 12)
        }
        val handle = View(this).apply { background = shape(T.outline2, 2f) }
        sheet.addView(handle, LinearLayout.LayoutParams(dp(36), dp(4)).apply { gravity = Gravity.CENTER_HORIZONTAL })
        val head = row(); add(head, logo(), 36, 36); val title = col(); add(title, txt("How Prahari works", 20f, T.ink, 700, 26)); add(title, txt("प्रहरी कैसे काम करता है", 13f, T.ink3, 500, 18)); add(head, title, 0, -2, left = 12, weight = 1f); add(sheet, head, top = 14)
        val descriptions = listOf(
            Triple(R.drawable.ic_wifi_off, "Runs fully offline", "The app has no internet permission, so nothing you check can be sent anywhere. Airplane mode works."),
            Triple(R.drawable.ic_cpu, "Llama 3.2 1B on this phone", "Runs on the phone's CPU through ExecuTorch (INT4, XNNPACK). It only writes the explanation."),
            Triple(R.drawable.ic_shield_check, "A detector decides the verdict", "Scam signals are checked by the detector. The verdict never depends on the AI text."),
            Triple(R.drawable.ic_list, "Safety steps are fixed", "Steps come from a vetted list (1930, cybercrime.gov.in), never from the AI."),
            Triple(R.drawable.ic_alert_circle, "Best effort, not a guarantee", "No checker catches every scam. If in doubt, don't pay and call 1930.")
        )
        descriptions.forEachIndexed { i, item ->
            if (i > 0) divider(sheet)
            val r = row().apply { gravity = Gravity.TOP; pad(this, 0, 11, 0, 11) }
            val tile = FrameLayout(this).apply { background = shape(T.brandC, 12f); addView(icon(item.first, 20, T.brand), FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER)) }
            add(r, tile, 36, 36); val text = col(); add(text, txt(item.second, 15f, T.ink, 600, 20)); add(text, txt(item.third, 13f, T.ink2, 400, 18), top = 2)
            add(r, text, 0, -2, left = 14, weight = 1f); add(sheet, r)
        }
        add(sheet, button("Got it") { dialog.dismiss() }, -1, 56, top = 8)
        add(sheet, txt("Built for the Arm Bharat AI-SoC Challenge 2026", 12f, T.ink3, 400, 16).apply { gravity = Gravity.CENTER }, top = 12)
        val scroll = ScrollView(this).apply { isFillViewport = false; addView(sheet) }
        dialog.setContentView(scroll); dialog.window?.apply {
            setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT)); addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND); setDimAmount(.52f)
            setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT); setGravity(Gravity.BOTTOM)
        }; dialog.show(); dialog.window?.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    }
    // Called by Chaquopy on the worker. Never throw from a native callback.
    inner class Runner(private val pte: String, private val tokenizer: String, private val id: Int) {
        fun generate(prompt: String): String {
            if (id != runId) throw IllegalStateException("Check cancelled")
            val m = ensureModel()
            m.resetContext()
            if (id != runId) throw IllegalStateException("Check cancelled")
            val start = SystemClock.elapsedRealtime(); var first: Long? = null; var count = 0
            val out = StringBuilder(); var rawStats = "{}"
            val callbackError = java.util.concurrent.atomic.AtomicReference<String?>(null)
            val cb = object : LlmCallback {
                override fun onResult(result: String) {
                    if (first == null) first = SystemClock.elapsedRealtime()
                    out.append(result); count++
                    if (count >= 40 || id != runId) { try { m.stop() } catch (_: Throwable) {} }
                }
                override fun onStats(stats: String) { rawStats = stats }
                override fun onError(errorCode: Int, message: String) { callbackError.set("ExecuTorch $errorCode: $message") }
            }
            val seqLen = (prompt.toByteArray(Charsets.UTF_8).size * 3 / 4 + 32 + 40).coerceIn(256, 2048)
            val config = LlmGenerationConfig.create().echo(false).seqLen(seqLen).temperature(0f).maxNewTokens(40).build()
            var generationFailure: Throwable? = null
            try { m.generate(prompt, config, cb) } catch (e: Throwable) { generationFailure = e }
            if (id != runId) throw IllegalStateException("Check cancelled")
            callbackError.get()?.let { throw IllegalStateException(it, generationFailure) }
            generationFailure?.let { throw it }
            val nativeStats = JSONObject(rawStats)
            val stats = JSONObject().put("backend", "executorch").put("raw", nativeStats)
            if (nativeStats.has("generated_tokens")) stats.put("generated_tokens", nativeStats.getInt("generated_tokens"))
            if (nativeStats.has("decode_token_per_sec")) stats.put("decode_tps", nativeStats.getDouble("decode_token_per_sec"))
            first?.let { stats.put("first_token_ms", it - start) }
            return JSONObject().put("text", out.toString()).put("stats", stats).toString()
        }
    }
    @Deprecated("Deprecated in Android")
    override fun onBackPressed() { if (screen == "home") super.onBackPressed() else goHome() }
    override fun onDestroy() {
        runId++; module?.stop()
        worker.execute { try { module?.stop(); module?.close() } finally { module = null } }
        worker.shutdown(); super.onDestroy()
    }
}
