package `in`.prahari.app

import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.util.Log
import com.chaquo.python.Python
import org.json.JSONArray
import org.pytorch.executorch.EValue
import org.pytorch.executorch.Module
import org.pytorch.executorch.Tensor
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Call Guard (Preview) for Prahari Android.
 *
 * Isolated behind [FEATURE_FLAG_ENABLED] so the core SMS / Link / Network flows stay untouched.
 * Android cannot tap live phone call audio directly; this preview checks shared WhatsApp voice
 * notes / local audio files (or pasted/sample call transcripts) completely offline using:
 *   1. Android MediaExtractor + MediaCodec (offline PCM decode for .opus/.ogg/.m4a/.mp3/.wav)
 *   2. Chaquopy pure-NumPy 80-bin log-mel spectrogram
 *   3. ExecuTorch [Module] running Arm's Whisper Tiny INT8 XNNPACK `.pte` (when pushed locally)
 *   4. Existing Prahari detectors + Indian 'digital arrest' call-script rules + Llama 3.2 1B STOP
 *      warning + existing offline Android TextToSpeech read-aloud.
 *
 * Note: ASR latency/RAM has been measured on Arm Linux (Neoverse-N1); physical Galaxy S23 phone
 * testing remains pending a Remote Test Lab session.
 */
internal object CallGuardPreview {
    /** Feature flag: set false to hide Call Guard Preview without affecting SMS/Link/Network. */
    const val FEATURE_FLAG_ENABLED = false
    const val AUDIO_PICK_REQUEST = 42

    private const val TAG = "PrahariCallGuard"
    private const val WHISPER_DIR = "whisper-tiny"
    private const val WHISPER_PTE = "whisper_tiny_vivo_executorch_optimized.pte"
    private const val WHISPER_TOK = "tokenizer.json"
    private const val MAX_AUDIO_SECONDS = 30
    private const val MAX_DECODE_TOKENS = 128
    private const val MAX_DECODE_WALL_MS = 20_000L

    private const val SOT_TOKEN = 50258L
    private const val EN_TOKEN = 50259L
    private const val TRANSCRIBE_TOKEN = 50359L
    private const val NOTIMESTAMPS_TOKEN = 50363L
    private const val EOS_TOKEN = 50257

    private val SUPPRESS_TOKENS = intArrayOf(
        1, 2, 7, 8, 9, 10, 14, 25, 26, 27, 28, 29, 31, 58, 59, 60, 61, 62, 63,
        90, 91, 92, 93, 357, 366, 438, 532, 685, 705, 796, 930, 1058, 1220, 1267,
        1279, 1303, 1343, 1377, 1391, 1635, 1782, 1875, 2162, 2361, 2488, 3467,
        4008, 4211, 4600, 4808, 5299, 5855, 6329, 7203, 9609, 9959, 10563, 10786,
        11420, 11709, 11907, 13163, 13697, 13700, 14808, 15306, 16410, 16791,
        17992, 19203, 19510, 20724, 22305, 22935, 27007, 30109, 30420, 33409,
        34949, 40283, 40493, 40549, 47282, 49146, 50359, 50360, 50361
    )

    data class DecodedAudio(val pcm16Mono: ByteArray, val sampleRate: Int, val seconds: Double, val truncated: Boolean)
    /** [truncated]: only the first [MAX_AUDIO_SECONDS] were checked; the caller must say so and not clear the call. */
    data class AsrOutcome(val transcript: String?, val error: String?, val elapsedMs: Long, val truncated: Boolean = false)

    val sampleCalls = listOf(
        "Digital arrest (CBI/parcel)" to
            "This is Inspector Rajesh Sharma from Mumbai Cyber Crime and CBI. An arrest warrant has been issued in your name because a parcel with illegal drugs was seized by customs. Do not disconnect this call and stay on video call alone. Transfer 50,000 rupees to the RBI safe verification account immediately or police will arrest you.",
        "TRAI + customs scam" to
            "Alert from TRAI telecom department. Your mobile number will be disconnected within two hours due to an illegal narcotics parcel linked to your Aadhaar card. Stay on the line and do not tell your family. Press 9 to speak to the cyber officer and verify your bank account.",
        "Legitimate bank reminder" to
            "Hello, this is a routine security reminder from State Bank of India. Never share your OTP, UPI PIN, or password on any phone call. If you did not authorize a card transaction, block your card directly inside the official YONO app or visit your home branch."
    )

    fun readSharedAudio(intent: Intent?): Uri? {
        if (!FEATURE_FLAG_ENABLED || intent == null) return null
        if (intent.action != Intent.ACTION_SEND) return null
        val mime = intent.type ?: return null
        if (!mime.startsWith("audio/")) return null
        return if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }
    }

    fun whisperFiles(context: Context): Pair<File, File>? {
        val base = context.getExternalFilesDir(null) ?: return null
        val dir = File(base, WHISPER_DIR)
        return File(dir, WHISPER_PTE) to File(dir, WHISPER_TOK)
    }

    fun missingWhisperMessage(context: Context): String? {
        val pair = whisperFiles(context)
        if (pair != null && pair.first.isFile && pair.second.isFile) return null
        val dir = pair?.first?.parent ?: "/sdcard/Android/data/in.prahari.app/files/$WHISPER_DIR"
        return "Whisper ASR files not installed ($WHISPER_PTE and $WHISPER_TOK in $dir). " +
            "Push Arm/whisper-tiny-int8-xnnpack-executorch files via adb, or test a sample call transcript."
    }

    fun showDialog(activity: MainActivity, onPickAudio: () -> Unit, onCheckTranscript: (String) -> Unit) {
        val missing = missingWhisperMessage(activity)
        val status = if (missing == null) {
            "Offline Whisper Tiny INT8 model found on this device."
        } else {
            "Preview note: Whisper model files not pushed yet (transcript samples still work offline)."
        }
        val items = arrayOf(
            "Pick WhatsApp voice note / audio file",
            "Sample: Digital arrest (CBI / parcel)",
            "Sample: TRAI + customs scam call",
            "Sample: Legitimate SBI security reminder"
        )
        AlertDialog.Builder(activity)
            .setTitle("Call Guard · Preview")
            .setMessage(
                "Android cannot tap live phone calls directly. Share a WhatsApp voice note or pick a local audio file, " +
                    "or test a call transcript offline.\n\n$status"
            )
            .setItems(items) { _, which ->
                when (which) {
                    0 -> onPickAudio()
                    in 1..sampleCalls.size -> onCheckTranscript(sampleCalls[which - 1].second)
                }
            }
            .setNegativeButton("Close", null)
            .show()
    }

    /** Decode a shared audio URI (.opus/.ogg/.m4a/.mp3/.wav) to mono 16-bit PCM offline. */
    fun decodeAudioToPcm(context: Context, uri: Uri): DecodedAudio {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            val afd = context.contentResolver.openAssetFileDescriptor(uri, "r")
                ?: throw IllegalStateException("Cannot open audio file")
            afd.use { extractor.setDataSource(it.fileDescriptor, it.startOffset, it.length) }
            var trackIndex = -1
            var format: MediaFormat? = null
            for (i in 0 until extractor.trackCount) {
                val f = extractor.getTrackFormat(i)
                val mime = f.getString(MediaFormat.KEY_MIME) ?: ""
                if (mime.startsWith("audio/")) {
                    trackIndex = i
                    format = f
                    break
                }
            }
            if (trackIndex < 0 || format == null) {
                throw IllegalStateException("No audio track found in the shared file")
            }
            extractor.selectTrack(trackIndex)
            val mime = format.getString(MediaFormat.KEY_MIME)!!
            var sampleRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT).coerceAtLeast(1)

            codec = MediaCodec.createDecoderByType(mime)
            codec.configure(format, null, null, 0)
            codec.start()

            val out = ByteArrayOutputStream()
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false

            var truncated = false
            val decodeStart = SystemClock.elapsedRealtime()
            while (!outputDone) {
                // A stalled codec must not spin forever; what was decoded so far is checked as truncated.
                if (SystemClock.elapsedRealtime() - decodeStart > MAX_DECODE_WALL_MS) {
                    truncated = true
                    break
                }
                // Recomputed each pass: the decoder may report a different output rate than the container.
                if (out.size() >= sampleRate * 2 * MAX_AUDIO_SECONDS) {
                    truncated = true
                    break
                }
                if (!inputDone) {
                    val inIdx = codec.dequeueInputBuffer(10_000)
                    if (inIdx >= 0) {
                        val buf = codec.getInputBuffer(inIdx)!!
                        val read = extractor.readSampleData(buf, 0)
                        if (read < 0) {
                            codec.queueInputBuffer(inIdx, 0, 0, 0L, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(inIdx, 0, read, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val outIdx = codec.dequeueOutputBuffer(info, 10_000)
                when {
                    outIdx >= 0 -> {
                        val buf = codec.getOutputBuffer(outIdx)!!
                        if (info.size > 0) {
                            val chunk = ByteArray(info.size)
                            buf.position(info.offset)
                            buf.get(chunk)
                            if (channels == 1) {
                                out.write(chunk)
                            } else {
                                out.write(downmixToMono16(chunk, channels))
                            }
                        }
                        codec.releaseOutputBuffer(outIdx, false)
                        if ((info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                            outputDone = true
                        }
                    }
                    outIdx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val nf = codec.outputFormat
                        if (nf.containsKey(MediaFormat.KEY_SAMPLE_RATE)) {
                            sampleRate = nf.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        }
                        if (nf.containsKey(MediaFormat.KEY_CHANNEL_COUNT)) {
                            channels = nf.getInteger(MediaFormat.KEY_CHANNEL_COUNT).coerceAtLeast(1)
                        }
                    }
                }
            }
            val pcm = out.toByteArray()
            val sec = pcm.size.toDouble() / (sampleRate * 2.0)
            return DecodedAudio(pcm, sampleRate, sec, truncated)
        } finally {
            try { codec?.stop() } catch (_: Throwable) {}
            try { codec?.release() } catch (_: Throwable) {}
            try { extractor.release() } catch (_: Throwable) {}
        }
    }

    private fun downmixToMono16(pcm: ByteArray, channels: Int): ByteArray {
        val shorts = ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        val frames = shorts.remaining() / channels
        val mono = ByteArray(frames * 2)
        val out = ByteBuffer.wrap(mono).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        for (i in 0 until frames) {
            var sum = 0
            for (c in 0 until channels) sum += shorts.get(i * channels + c).toInt()
            out.put((sum / channels).toShort())
        }
        return mono
    }

    /** Run ExecuTorch Whisper Tiny INT8 on decoded PCM. Closes the Whisper module before returning. */
    fun transcribeUri(context: Context, uri: Uri): AsrOutcome {
        val start = SystemClock.elapsedRealtime()
        if (!FEATURE_FLAG_ENABLED) return AsrOutcome(null, "Call Guard is disabled", 0L)
        val missing = missingWhisperMessage(context)
        if (missing != null) {
            return AsrOutcome(null, missing, SystemClock.elapsedRealtime() - start)
        }
        val files = whisperFiles(context)!!
        var module: Module? = null
        return try {
            if (!Python.isStarted()) throw IllegalStateException("Python runtime is not running")
            val audio = decodeAudioToPcm(context, uri)
            val pyMod = Python.getInstance().getModule("callguard_mobile")
            val melBytes = pyMod.callAttr("mel_spectrogram_flat", audio.pcm16Mono, audio.sampleRate).toJava(ByteArray::class.java)
            val melFloats = FloatArray(melBytes.size / 4)
            ByteBuffer.wrap(melBytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(melFloats)

            module = Module.load(files.first.path, Module.LOAD_MODE_MMAP)
            val melTensor = Tensor.fromBlob(melFloats, longArrayOf(1L, 80L, 3000L))
            val encOut = module.execute("encoder", EValue.from(melTensor))
            val hidden = encOut[0].toTensor()

            val prefix = longArrayOf(EN_TOKEN, TRANSCRIBE_TOKEN, NOTIMESTAMPS_TOKEN)
            val tokens = ArrayList<Int>(MAX_DECODE_TOKENS + 4)
            tokens.add(SOT_TOKEN.toInt())
            var freeCount = 0

            for (step in 0 until (MAX_DECODE_TOKENS + prefix.size)) {
                val tokTensor = Tensor.fromBlob(longArrayOf(tokens.last().toLong()), longArrayOf(1L, 1L))
                val posTensor = Tensor.fromBlob(longArrayOf(step.toLong()), longArrayOf(1L))
                val decOut = module.execute(
                    "text_decoder",
                    EValue.from(tokTensor),
                    EValue.from(hidden),
                    EValue.from(posTensor)
                )
                val nextToken = if (step < prefix.size) {
                    prefix[step].toInt()
                } else {
                    val logits = decOut[0].toTensor().dataAsFloatArray
                    for (sup in SUPPRESS_TOKENS) {
                        if (sup in logits.indices && sup != EOS_TOKEN) logits[sup] = Float.NEGATIVE_INFINITY
                    }
                    if (freeCount == 0) {
                        if (220 in logits.indices) logits[220] = Float.NEGATIVE_INFINITY
                        if (EOS_TOKEN in logits.indices) logits[EOS_TOKEN] = Float.NEGATIVE_INFINITY
                    }
                    var bestIdx = 0
                    var bestVal = Float.NEGATIVE_INFINITY
                    for (i in logits.indices) {
                        if (logits[i] > bestVal) {
                            bestVal = logits[i]
                            bestIdx = i
                        }
                    }
                    freeCount++
                    if (bestIdx == EOS_TOKEN) break
                    bestIdx
                }
                tokens.add(nextToken)
            }
            val arr = JSONArray()
            tokens.forEach { arr.put(it) }
            val text = pyMod.callAttr("decode_whisper_tokens", files.second.path, arr.toString()).toString()
            AsrOutcome(text, null, SystemClock.elapsedRealtime() - start, audio.truncated)
        } catch (t: Throwable) {
            Log.e(TAG, "offline Whisper transcription failed", t)
            AsrOutcome(null, "${t.javaClass.simpleName}: ${t.message ?: "ASR error"}", SystemClock.elapsedRealtime() - start)
        } finally {
            try { module?.destroy() } catch (_: Throwable) {}
        }
    }
}
