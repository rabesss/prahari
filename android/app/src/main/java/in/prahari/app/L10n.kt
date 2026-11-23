package `in`.prahari.app

import org.json.JSONObject

/**
 * One lookup for user-facing copy. English is the key. Hindi comes from
 * android/python/strings_hi.json when that mode is on, and a missing line stays English.
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
        templates = evidence.mapNotNull { (en, hi) -> compile(en, hi) }
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
        for (template in templates) {
            val match = template.regex.matchEntire(trimmed) ?: continue
            var out = template.hindi
            template.names.forEachIndexed { index, name ->
                out = out.replace("{$name}", match.groupValues[index + 1])
            }
            return out
        }
        return english
    }

    /** A string that did not exist in the English list, keyed under "new". */
    fun n(key: String): String {
        val pair = fresh[key] ?: return key
        return if (hindi) pair.second else pair.first
    }

    private fun dict(obj: org.json.JSONObject?): Map<String, String> {
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

    private fun compile(english: String, hindi: String): Template? {
        if (!english.contains('{')) return null
        val names = ArrayList<String>()
        val pattern = StringBuilder("^")
        var i = 0
        while (i < english.length) {
            if (english[i] == '{') {
                val end = english.indexOf('}', i + 1)
                if (end < 0) return null
                names.add(english.substring(i + 1, end))
                pattern.append("(.+?)")
                i = end + 1
            } else {
                pattern.append(Regex.escape(english[i].toString()))
                i++
            }
        }
        pattern.append("$")
        return Template(Regex(pattern.toString()), hindi, names)
    }
}
