# Data and model provenance

| Asset | Use | Licence | Source |
|---|---|---|---|
| UCI SMS Spam Collection | train/test (SMS) | CC BY 4.0 | https://archive.ics.uci.edu/dataset/228/sms+spam+collection |
| Mendeley SMS Phishing Dataset (5,971 msgs) | train/test (SMS) | CC BY 4.0 | https://data.mendeley.com/datasets/f45bkkt8pr |
| PhiUSIIL Phishing URL Dataset | train/test (URLs) | CC BY 4.0 | https://archive.ics.uci.edu/dataset/967 |
| NSL-KDD | train/test (flows) | research use (UNB); not redistributed | https://www.unb.ca/cic/datasets/nsl.html |
| HF Indian Multilingual Scam Message Dataset (karanverma19) | seed rows in `train/indic_seed.jsonl` | Apache-2.0 | https://huggingface.co/datasets/karanverma19/Indian_Multilingual_Scam_Message_Dataset |
| HF Hinglish & English Financial Scam/Fraud Text Dataset (bolewara) | seed rows in `train/indic_seed.jsonl` | CC BY 4.0 | https://huggingface.co/datasets/bolewara/hinglish-scam-text-dataset |
| Indian-context synthetic messages | Project-generated Indian-context messages used in training/development and a separate synthetic generator run for evaluation; see split and generator documentation | original work (this project) | generated for this project |
| Llama 3.2 1B Instruct QLoRA INT4 .pte | explanations | Llama 3.2 Community License | https://huggingface.co/executorch-community |

| Hindi summary strings (`triage/explain_hi.json`) | fixed-text Hindi summary in Hindi mode | original work (this project) | evidence phrases reuse the app's Hindi table (`android/python/strings_hi.json`) where the English matches; the remaining phrases, key facts and verdict lines were written for this project; no machine-translation service output is used |

Datasets and model weights are not committed to the repository.
