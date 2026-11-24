package `in`.prahari.app

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileNotFoundException
import java.io.FileOutputStream
import java.security.MessageDigest
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.util.Locale

/**
 * Offline app-file (.apk) inspector. A shared (ACTION_SEND, EXTRA_STREAM) or picked
 * (ACTION_OPEN_DOCUMENT) file is copied to the app cache, its metadata is read with
 * [PackageManager.getPackageArchiveInfo], and the copy is deleted before the facts go to
 * android/python/apk_check.py, which decides the verdict.
 *
 * The app in the file is never installed, opened or run: no installer session, no install intent,
 * no class loader. getPackageArchiveInfo parses the manifest and signing block only, and the
 * label comes from the archive's resource table. No permission is needed: the content URI comes
 * with the sender's or the picker's read grant. Call [read] from the model worker only.
 */
internal object ApkInspector {
    const val PICK_REQUEST = 43
    const val APK_MIME = "application/vnd.android.package-archive"
    private const val MAX_BYTES = 200L * 1024 * 1024
    private const val DIR = "apk-inspect"
    private const val STALE_MS = 10 * 60 * 1000L

    /** A file Prahari could not read. [key] is the strings_hi.json "new" key for the message. */
    class Unreadable(val key: String) : Exception(key)

    /** The check was replaced or cancelled while the file was being copied. */
    class Stopped : Exception("app file check cancelled")

    class Facts(val json: JSONObject, val display: String)

    fun pickIntent(): Intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
        addCategory(Intent.CATEGORY_OPENABLE)
        type = "*/*"
        // Some file managers label an .apk as a generic binary or zip; the parse decides.
        putExtra(Intent.EXTRA_MIME_TYPES, arrayOf(APK_MIME, "application/octet-stream", "application/zip"))
    }

    /** True for a share of an app file, even one whose stream is missing (shown as an error). */
    fun isShare(intent: Intent?): Boolean =
        intent?.action == Intent.ACTION_SEND && intent.type?.lowercase(Locale.ROOT) == APK_MIME

    fun sharedUri(intent: Intent): Uri? {
        val stream = if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }
        return stream ?: intent.clipData?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.uri
    }

    fun read(ctx: Context, uri: Uri, still: () -> Boolean): Facts {
        // A file:// URI would need storage access; only granted content URIs are read.
        if (uri.scheme != "content") throw Unreadable("apk_fail")
        val dir = File(ctx.cacheDir, DIR)
        dir.mkdirs()
        sweep(dir)
        val name = displayName(ctx, uri)
        val file = File(dir, "check-${System.nanoTime()}.apk")
        try {
            val size = copy(ctx, uri, file, still)
            if (!still()) throw Stopped()
            return inspect(ctx.packageManager, file.path, name, size)
        } finally {
            file.delete()
        }
    }

    /** Copies left behind by a crash. The worker runs one check at a time, so none is in use. */
    private fun sweep(dir: File) {
        val now = System.currentTimeMillis()
        dir.listFiles()?.forEach { old ->
            if (now - old.lastModified() > STALE_MS) old.delete()
        }
    }

    private fun displayName(ctx: Context, uri: Uri): String = try {
        ctx.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst() && !c.isNull(0)) c.getString(0) else ""
        } ?: ""
    } catch (_: Throwable) {
        ""
    }

    /** The size cap is enforced while streaming: a provider's reported size is not trusted. */
    private fun copy(ctx: Context, uri: Uri, file: File, still: () -> Boolean): Long {
        val input = try {
            ctx.contentResolver.openInputStream(uri)
        } catch (_: SecurityException) {
            throw Unreadable("apk_denied")
        } catch (_: FileNotFoundException) {
            throw Unreadable("apk_fail")
        } ?: throw Unreadable("apk_fail")
        input.use { inp ->
            FileOutputStream(file).use { out ->
                val buf = ByteArray(64 * 1024)
                var total = 0L
                while (true) {
                    val n = inp.read(buf)
                    if (n < 0) break
                    total += n
                    if (total > MAX_BYTES) throw Unreadable("apk_big")
                    if (!still()) throw Stopped()
                    out.write(buf, 0, n)
                }
                return total
            }
        }
    }

    private fun archiveInfo(pm: PackageManager, path: String, flags: Int): PackageInfo? = try {
        if (Build.VERSION.SDK_INT >= 33) {
            pm.getPackageArchiveInfo(path, PackageManager.PackageInfoFlags.of(flags.toLong()))
        } else {
            @Suppress("DEPRECATION")
            pm.getPackageArchiveInfo(path, flags)
        }
    } catch (_: Throwable) {
        null
    }

    /**
     * Signer certificates, or empty when none could be read. Empty is reported as "unknown", not
     * "unsigned": a failed read is not proof that the file has no signature. The legacy
     * GET_SIGNATURES read is a fallback for platform versions where signingInfo comes back null
     * for archives. Nothing here verifies who the certificate belongs to.
     */
    private fun signers(pm: PackageManager, path: String): List<ByteArray> {
        val modern = archiveInfo(pm, path, PackageManager.GET_SIGNING_CERTIFICATES)?.signingInfo
        val current = try {
            modern?.apkContentsSigners?.mapNotNull { it?.toByteArray() }.orEmpty()
        } catch (_: Throwable) {
            emptyList()
        }
        if (current.isNotEmpty()) return current
        @Suppress("DEPRECATION")
        val legacy = archiveInfo(pm, path, PackageManager.GET_SIGNATURES)?.signatures
        return legacy?.mapNotNull { it?.toByteArray() }.orEmpty()
    }

    private fun inspect(pm: PackageManager, path: String, fileName: String, size: Long): Facts {
        val flags = PackageManager.GET_PERMISSIONS or PackageManager.GET_SERVICES or PackageManager.GET_RECEIVERS
        val info = archiveInfo(pm, path, flags) ?: throw Unreadable("apk_fail")
        // BIND_ACCESSIBILITY_SERVICE and BIND_DEVICE_ADMIN are the android:permission of a service
        // or receiver, not a uses-permission, so component permissions are included.
        val perms = sortedSetOf<String>()
        info.requestedPermissions?.forEach { p -> if (p != null) perms.add(p) }
        info.services?.forEach { s -> s.permission?.let { perms.add(it) } }
        info.receivers?.forEach { r -> r.permission?.let { perms.add(it) } }
        val label = try {
            info.applicationInfo?.let { ai ->
                ai.sourceDir = path
                ai.publicSourceDir = path
                pm.getApplicationLabel(ai).toString()
            }
        } catch (_: Throwable) {
            null
        }.orEmpty()
        val certs = signers(pm, path)
        var debug = false
        var fingerprint = ""
        certs.firstOrNull()?.let { der ->
            fingerprint = MessageDigest.getInstance("SHA-256").digest(der)
                .joinToString("") { "%02X".format(it) }
            debug = try {
                val cert = CertificateFactory.getInstance("X.509")
                    .generateCertificate(ByteArrayInputStream(der)) as X509Certificate
                cert.subjectX500Principal.name.contains("CN=Android Debug")
            } catch (_: Throwable) {
                false
            }
        }
        val pkg = info.packageName.orEmpty()
        val version = info.versionName.orEmpty()
        val json = JSONObject()
            .put("package", pkg)
            .put("label", label)
            .put("file_name", fileName)
            .put("version", version)
            .put("size_bytes", size)
            .put("permissions", JSONArray(perms.toList()))
            .put("signing", if (certs.isNotEmpty()) "present" else "unknown")
            .put("debug_cert", debug)
            .put("cert_sha256", fingerprint)
        return Facts(json, display(fileName, label, pkg, version, size, fingerprint))
    }

    /** The "You checked" text. Every part except the sizes comes from the file and is shown as data. */
    private fun display(fileName: String, label: String, pkg: String, version: String, size: Long, sha: String): String {
        fun one(s: String, limit: Int) = s.replace(Regex("[\\p{Cc}\\p{Cf}]"), " ").trim().take(limit)
        val lines = mutableListOf<String>()
        one(fileName, 120).takeIf { it.isNotEmpty() }?.let { lines.add(it) }
        one(label, 80).takeIf { it.isNotEmpty() }?.let { lines.add(it) }
        one(pkg, 200).takeIf { it.isNotEmpty() }?.let { lines.add(it) }
        val mb = String.format(Locale.US, "%.1f MB", size / (1024.0 * 1024.0))
        lines.add(listOfNotNull(one(version, 40).takeIf { it.isNotEmpty() }?.let { "v$it" }, mb).joinToString(" · "))
        if (sha.isNotEmpty()) lines.add("SHA-256 ${sha.take(16)}…")
        return lines.joinToString("\n")
    }
}
