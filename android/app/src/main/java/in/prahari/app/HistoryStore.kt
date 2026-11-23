package `in`.prahari.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Opt-in recent checks. Off until the user turns it on. The file stays in the app's
 * private files directory, numbers are redacted, and nothing is backed up (allowBackup is false).
 */
internal object HistoryStore {
    private const val PREFS = "prahari"
    private const val ON = "history_on"
    private const val FILE = "history.json"
    private const val MAX = 25
    private const val TTL_MS = 14L * 24 * 60 * 60 * 1000

    data class Entry(val at: Long, val mode: Int, val level: String, val snippet: String)

    private val lock = Any()

    fun enabled(ctx: Context): Boolean =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(ON, false)

    fun setEnabled(ctx: Context, on: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(ON, on).apply()
    }

    fun add(ctx: Context, mode: Int, level: String, text: String) {
        if (!enabled(ctx)) return
        val entry = Entry(System.currentTimeMillis(), mode, level, redact(text).take(96))
        synchronized(lock) {
            val next = (listOf(entry) + read(ctx)).take(MAX)
            write(ctx, next)
        }
    }

    fun list(ctx: Context): List<Entry> = synchronized(lock) { read(ctx) }

    fun clear(ctx: Context) {
        synchronized(lock) { file(ctx).delete() }
    }

    /** 10+ digit runs, then OTP-like 4–8 digit runs. The message text is not kept whole. */
    fun redact(text: String): String {
        var s = text.replace(Regex("""(?<!\d)\d{10,}(?!\d)"""), "••••••••••")
        s = s.replace(Regex("""(?<!\d)(\d{4,8})(?!\d)""")) { "•".repeat(it.value.length) }
        return s.replace(Regex("""\s+"""), " ").trim()
    }

    private fun file(ctx: Context) = File(ctx.filesDir, FILE)

    private fun read(ctx: Context): List<Entry> {
        val raw = try {
            val f = file(ctx)
            if (!f.isFile) return emptyList()
            f.readText(Charsets.UTF_8)
        } catch (_: Throwable) {
            return emptyList()
        }
        val cutoff = System.currentTimeMillis() - TTL_MS
        val out = ArrayList<Entry>()
        try {
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val item = arr.optJSONObject(i) ?: continue
                val at = item.optLong("at")
                if (at < cutoff) continue
                out.add(Entry(at, item.optInt("mode"), item.optString("level"), item.optString("snippet")))
            }
        } catch (_: Throwable) {
            return emptyList()
        }
        if (out.size > MAX) return out.take(MAX)
        return out
    }

    private fun write(ctx: Context, entries: List<Entry>) {
        val arr = JSONArray()
        for (entry in entries) {
            arr.put(JSONObject()
                .put("at", entry.at)
                .put("mode", entry.mode)
                .put("level", entry.level)
                .put("snippet", entry.snippet))
        }
        file(ctx).writeText(arr.toString(), Charsets.UTF_8)
    }
}
