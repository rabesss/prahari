package `in`.prahari.app

import org.json.JSONArray
import org.json.JSONObject

/**
 * One lookup for user-facing copy. English is the key. Hindi comes from
 * android/python/strings_hi.json when that mode is on, and a missing line stays English.
 *
 * Evidence lines that contain a host, brand or count live under "templates"
 * ({host}, {brand}, {n}, or an explicit regex). Exact lines stay under "ui" and "evidence".
 */
internal object L10n {
    @Volatile var hindi: Boolean = false

    private var ui: Map<String, String> = emptyMap()
    private var evidence: Map<String, String> = emptyMap()
    private var skip: Set<String> = emptySet()
    private var fresh: Map<String, Pair<String, String>> = emptyMap()
    private var templates: List<Template> = emptyList()

    private class Template(val regex: Regex, val hindi: String, val names: List<String>)

    fun load(json: String) {
        val root = JSONObject(json)
        ui = dict(root.optJSONObject("ui"))
        evidence = dict(root.optJSONObject("evidence"))
        val skipArr = root.optJSONArray("skip")
        skip = if (skipArr == null) emptySet() else (0 until skipArr.length()).map { skipArr.optString(it) }.toSet()
        val created = root.optJSONObject("new")
        val next = HashMap<String, Pair<String, String>>()
        if (created != null) {
            val keys = created.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val item = created.optJSONObject(key) ?: continue
                val en = item.optString("en")
                val hi = item.optString("hi")
                if (en.isNotEmpty()) next[key] = en to hi.ifEmpty { en }
            }
        }
        fresh = next
        val compiled = ArrayList<Template>()
        val seen = HashSet<String>()
        fun add(template: Template?) {
            if (template == null) return
            if (seen.add(template.regex.pattern)) compiled.add(template)
        }
        val tmpl = root.optJSONArray("templates")
        if (tmpl != null) {
            for (i in 0 until tmpl.length()) add(fromJson(tmpl.optJSONObject(i)))
        }
        for ((en, hi) in evidence) {
            if (en.contains('{')) add(compile(en, hi))
        }
        compiled.sortByDescending { it.regex.pattern.length }
        templates = compiled
    }

    /** English source sentence. In Hindi mode, the bundled line, otherwise [english]. */
    fun t(english: String): String {
        if (!hindi || english.isEmpty() || english in skip) return english
        ui[english]?.let { return it }
        evidence[english]?.let { return it }
        val trimmed = english.trim()
        if (trimmed != english) {
            ui[trimmed]?.let { return it }
            evidence[trimmed]?.let { return it }
        }
        apply(trimmed)?.let { return it }
        return english
    }

    /** A string that did not exist in the English list, keyed under "new". */
    fun n(key: String): String {
        val pair = fresh[key] ?: return key
        return if (hindi) pair.second else pair.first
    }

    /** True when Hindi mode has a line for this exact English sentence or template. */
    fun translated(english: String): Boolean {
        if (english.isEmpty() || english in skip) return true
        if (ui.containsKey(english) || evidence.containsKey(english)) return true
        return apply(english.trim()) != null
    }

    private fun apply(trimmed: String): String? {
        for (template in templates) {
            val match = template.regex.matchEntire(trimmed) ?: continue
            var out = template.hindi
            for (index in template.names.indices) {
                val name = template.names[index]
                val value = match.groupValues.getOrNull(index + 1) ?: continue
                out = out.replace("{$name}", value)
                out = out.replace("{${index + 1}}", value)
            }
            return out
        }
        return null
    }

    private fun dict(obj: JSONObject?): Map<String, String> {
        if (obj == null) return emptyMap()
        val out = HashMap<String, String>()
        val keys = obj.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val value = obj.optString(key)
            if (key.isNotEmpty() && value.isNotEmpty()) out[key] = value
        }
        return out
    }

    private fun fromJson(item: JSONObject?): Template? {
        if (item == null) return null
        val hi = item.optString("hi")
        if (hi.isEmpty()) return null
        val regex = item.optString("regex")
        if (regex.isNotEmpty()) {
            val slots = item.optJSONArray("slots") ?: JSONArray()
            val names = (0 until slots.length()).map { slots.optString(it) }
            return try {
                Template(Regex(regex), hi, names)
            } catch (_: Throwable) {
                null
            }
        }
        val match = item.optString("en").ifEmpty { item.optString("match") }
        if (match.isEmpty()) return null
        return compile(match, hi)
    }

    private fun compile(english: String, hindi: String): Template? {
        if (!english.contains('{')) return null
        val names = ArrayList<String>()
        val pattern = StringBuilder("^")
        var i = 0
        while (i < english.length) {
            if (english[i] == '{') {
                val end = english.indexOf('}', i + 1)
                if (end < 0) return null
                val name = english.substring(i + 1, end)
                names.add(name)
                pattern.append(groupFor(name))
                i = end + 1
            } else {
                pattern.append(Regex.escape(english[i].toString()))
                i++
            }
        }
        pattern.append("$")
        return Template(Regex(pattern.toString()), hindi, names)
    }

    /** {n} is a count. {host} is a domain. {brand} stays inside the quotes the English line uses. */
    private fun groupFor(name: String): String = when (name) {
        "n", "count" -> "(\\d+)"
        "tld" -> "([A-Za-z0-9]+)"
        "host", "reg", "ip" -> "([^\\s']+)"
        "brand", "b" -> "([^']+)"
        "what" -> "(link|text|message)"
        else -> "(.+?)"
    }
}
