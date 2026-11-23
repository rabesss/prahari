# Prahari demo shot list — target 3:40

This is a production plan, not evidence of a recording or physical-phone operation. The Android detector and Llama have run end to end on an Android 14 x86_64 emulator; no physical-phone Llama run has been done. Rehearse and verify actual results before recording. Never show hidden data or per-item hidden predictions. Do not click a suspicious link. Llama results can vary; show the actual verdict and timing, even if wrong.

| Time | Shot and narration |
|:--|:--|
| 0:00–0:20 | Identify Prahari and target hardware. Show aarch64 CPU identity. State the workflow is advisory. Establish the conditional Linux offline proof below before Linux inference, or label it pending. |
| 0:20–0:45 | Enter an invented Hinglish electricity scam, e.g. “Bijli ka bill abhi pay karo warna connection cut hoga. OTP share karo.” Show verdict, evidence, on-screen Llama explanation, safe actions and displayed generation time. Do not claim an expected verdict without rehearsal. |
| 0:45–1:05 | Show the app's lookalike phishing URL preset. Show evidence, explanation and timing without opening it. |
| 1:05–1:25 | **Dataset replay:** prepare one licensed, visible real NSL-KDD feature record locally in the `bin/predict --task flow` JSONL schema (`id` and 41 named `features`); run `candidates/BEST/bin/predict --task flow --in <visible-record.jsonl> --out <result.jsonl>` with `HC_PY` configured. Show the resulting model verdict and evidence. Do not commit or display private data. This is not live capture. Choose the visible record in rehearsal; licence and permission must allow this use. If `data/dev/flow.jsonl` is provisioned, extract its first record locally with the snippet below; the dataset is not committed. |
| 1:25–1:45 | **Separate text-rule path:** select Network event in the UI and use the port-scan description preset. Show its rule verdict and Llama explanation with on-screen timing. Explain that it independently reclassifies text and does not explain the replay model's verdict; the two can disagree. |
| 1:45–2:05 | Show the hard benign bank-debit preset and its evidence and explanation. The benign label reads “NO RISK FOUND — still verify”; it is not a safety guarantee. |
| 2:05–2:25 | Enter `connections rejected` as a network description: this exercises the rule path's uncertain case. Show the actual result and cautious action. If the actual result differs, disclose it and investigate rather than staging success. |
| 2:25–2:50 | Summarise: VM benchmark about 3.8 s/item and 2.05 GB peak cgroup memory (systemd scope memory.peak, including page cache); no phone benchmark yet. State limitations: no live capture, synthetic tests, possible wrong advice. |
| 2:50–3:05 | **Android 14 emulator (x86_64):** select “KYC scam SMS”, then “Check on this phone”. Show the actual “खतरनाक” / “DANGEROUS” verdict and “Do this now · अभी यह करें” steps appearing before the Llama text. |
| 3:05–3:15 | Show “Call 1930” and “Report online”; tap “Call 1930” to show the dialler, without placing a call. Explain that the report button opens cybercrime.gov.in in the browser. |
| 3:15–3:28 | Return to the result and scroll to “Explained on this phone by Llama 3.2” and “AI-written and can be wrong. Follow the steps above.” Expand “On-device stats”; show “x86 emulator: not Arm timings”. |
| 3:28–3:40 | Return home and select “Prove it's offline”. Show “NO INTERNET” and the actual “SecurityException: Permission denied (missing INTERNET permission?)”. Explain that the app has no INTERNET permission; model files were staged beforehand. |

Linux inference runs locally and inputs reach the local app over loopback; normal Linux startup does not block outbound traffic. Model acquisition requires network access. The Android app declares no INTERNET permission; its dialler and browser actions use separate apps. Offline claims cover only what was tested.

## Offline proof variants

**A. Android emulator — demonstrated; physical phone planned.** Identify Android 14 and x86_64, stage model and assets beforehand, and show the app's permission test. The missing INTERNET permission and observed SecurityException concern this app; the separate dialler and browser can use their own connectivity. Do not present emulator timings as Arm timings. For a later physical-phone run, record the phone model, OS, ABI, memory, model version and actual timing; that run has not yet been done.

**B. Arm Linux server — conditional on an owner-provided egress block.** Show `uname -m` and `lscpu`; identify the environment as a cloud VM, not a physical edge device. An administrator must arrange a verified external egress block while preserving the SSH/loopback control path; do not disable an existing remote connection. Show a controlled outbound request failing under the same restriction, then run the application and show a result. The evaluator's import guard is a separate test, not proof normal app startup enforces a block. If the block cannot be established and verified, label offline proof pending. Organizer acceptance of a cloud VM is unconfirmed.

## Prepare the replay on the demo host

From the repository root, with the visible data already provisioned, create an input outside the repository. This selects only `id` and `features`, not the gold label. Review the applicable NSL-KDD terms before showing it.

```sh
D=$(mktemp -d)
python - "$D" <<'PY'
import sys
import json
from pathlib import Path
r = json.loads(Path('data/dev/flow.jsonl').open().readline())
Path(sys.argv[1], 'flow.jsonl').write_text(json.dumps({'id': 'replay', 'features': r['features']}) + '\n')
PY
candidates/BEST/bin/predict --task flow --in "$D/flow.jsonl" --out "$D/result.jsonl"
cat "$D/result.jsonl"
```

The replay command outputs a numeric label (1 malicious, 0 benign), score and evidence. Model acquisition and the data-preparation pipeline are prerequisites; do not use hidden records.
