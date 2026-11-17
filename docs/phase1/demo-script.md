# Prahari demo shot list — target 2:50

This is a production plan, not evidence a recording, Android APK, real phone, or egress block exists. Rehearse and verify actual results before recording. Never show hidden data or per-item hidden predictions. Do not click a suspicious link. Llama results can vary; show the actual verdict and timing, even if wrong.

| Time | Shot and narration |
|:--|:--|
| 0:00–0:20 | Identify Prahari and target hardware. Show aarch64 CPU identity. State the workflow is advisory. Establish the offline proof using one variant below before inference. |
| 0:20–0:45 | Enter an invented Hinglish electricity scam, e.g. “Bijli ka bill abhi pay karo warna connection cut hoga. OTP share karo.” Show verdict, evidence, on-screen Llama explanation, safe actions and displayed generation time. Do not claim an expected verdict without rehearsal. |
| 0:45–1:05 | Show the app's lookalike phishing URL preset. Show evidence, explanation and timing without opening it. |
| 1:05–1:25 | **Dataset replay:** prepare one licensed, visible real NSL-KDD feature record locally in the `bin/predict --task flow` JSONL schema (`id` and 41 named `features`); run `candidates/BEST/bin/predict --task flow --in <visible-record.jsonl> --out <result.jsonl>` with `HC_PY` configured. Show the resulting model verdict and evidence. Do not commit or display private data. This is not live capture. Choose the visible record in rehearsal; licence and permission must allow this use. If `data/dev/flow.jsonl` is provisioned, extract its first record locally with the snippet below; the dataset is not committed. |
| 1:25–1:45 | **Separate text-rule path:** select Network event in the UI and use the port-scan description preset. Show its rule verdict and Llama explanation with on-screen timing. Explain that it independently reclassifies text and does not explain the replay model's verdict; the two can disagree. |
| 1:45–2:05 | Show the hard benign bank-debit preset and its evidence and explanation. A benign label is not a safety guarantee. |
| 2:05–2:25 | Enter `connections rejected` as a network description: this exercises the rule path's uncertain case. Show the actual result and cautious action. If the actual result differs, disclose it and investigate rather than staging success. |
| 2:25–2:50 | Summarise: VM benchmark 3.67 s/item, 2.256 GB peak RSS, measured under the cited evaluation; no phone benchmark yet. State limitations: no live capture, synthetic tests, possible wrong advice. |

## Offline proof variants

**A. Remote real Android phone — planned, currently blocked on an APK.** Show the real phone identity and app build. Inspect the installed APK manifest/permissions and show that it declares no `android.permission.INTERNET`; stage model and assets beforehand. Run the same local inference with the remote-control connection retained. No INTERNET permission is evidence about that APK, not proof of every device network condition. Record phone model, OS, ABI, memory, model version and actual timing. Do not present this variant as implemented until it works.

**B. Arm Linux server — conditional on an owner-provided egress block.** Show `uname -m` and `lscpu`; identify the environment as a cloud VM, not a physical edge device. An administrator must arrange a verified external egress block while preserving the SSH/loopback control path; do not disable an existing remote connection. Show a controlled outbound request failing under the same restriction, then run the application and show a result. The evaluator's import guard is a separate test, not proof normal app startup enforces a block. If the block cannot be established and verified, label offline proof pending. Organizer acceptance of a cloud VM is unconfirmed.

## Prepare the replay on the demo host

From the repository root, with the visible data already provisioned, create an input outside the repository. This selects only `id` and `features`, not the gold label. Review the applicable NSL-KDD terms before showing it.

```sh
python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('data/dev/flow.jsonl').open().readline())
Path('/var/tmp/prahari-visible-flow.jsonl').write_text(json.dumps({'id': 'replay', 'features': r['features']}) + '\n')
PY
candidates/BEST/bin/predict --task flow --in /var/tmp/prahari-visible-flow.jsonl --out /var/tmp/prahari-visible-result.jsonl
cat /var/tmp/prahari-visible-result.jsonl
```

The replay command outputs a numeric label (1 malicious, 0 benign), score and evidence. Model acquisition and the data-preparation pipeline are prerequisites; do not use hidden records.
