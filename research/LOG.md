# Eval log

One line per `bin/eval` run (appended automatically). Add a short note after a line when useful.

- 20261109-183806 `baseline` score=69.33 D=0.672 E=0.7511 P=0.5195 C=0.8 fail=0 quick=False
- 20261109-191230 `indic1-quick` score=71.19 D=0.7804 E=0.7213 P=0.4872 C=0.8 fail=0 quick=True
- 20261109-191540 `indic2-quick` score=74.12 D=0.8391 E=0.7612 P=0.4959 C=0.8 fail=0 quick=True
- 20261109-191819 `indic3-quick` score=73.55 D=0.8147 E=0.7612 P=0.504 C=0.8 fail=0 quick=True
- 20261109-192044 `indic4-quick` score=74.7 D=0.8537 E=0.7612 P=0.5031 C=0.8 fail=0 quick=True
- 20261109-192343 `indic5-quick` score=75.64 D=0.8537 E=0.7988 P=0.503 C=0.8 fail=0 quick=True
- 20261109-192910 `indic6-quick` score=78.61 D=0.8537 E=0.7737 P=0.6826 C=0.8 fail=0 quick=True
- 20261109-193740 `indic7-full` score=79.36 D=0.8537 E=0.8129 P=0.6713 C=0.8 fail=0 quick=False
- 20261109-194227 `indic8-quick` score=77.25 D=0.8537 E=0.7738 P=0.6145 C=0.8 fail=0 quick=True
- 20261109-194518 `indic9-thr066` score=82.52 D=0.8534 E=0.7738 P=0.6287 C=1.0 fail=0 quick=True
- 20261109-194815 `indic10-receipts` score=82.64 D=0.8537 E=0.7738 P=0.634 C=1.0 fail=0 quick=True
- 20261109-194946 `indic11-clear` score=81.73 D=0.8539 E=0.7738 P=0.5885 C=1.0 fail=0 quick=True
- 20261109-195205 `indic12-final` score=84.36 D=0.8537 E=0.8129 P=0.6711 C=1.0 fail=0 quick=False
  best submission candidate: docs rewrite lifted C 0.80 -> 1.00; prompt and rule changes below.
- 20261109-195553 `indic13-type-first` score=84.15 D=0.8537 E=0.8129 P=0.6608 C=1.0 fail=0 quick=False
  type-first prompt left E unchanged and cost latency; reverted, indic12 is the shipped state.
- 20261109-200431 `indic14-recall` score=82.9 D=0.8563 E=0.7738 P=0.6434 C=1.0 fail=0 quick=True
- 20261109-200613 `indic15-hinglish` score=82.23 D=0.8563 E=0.7738 P=0.6096 C=1.0 fail=0 quick=True
- 20261109-200745 `indic16-full` score=84.36 D=0.8563 E=0.8129 P=0.6673 C=1.0 fail=0 quick=False
- 20261109-201032 `indic17-flow040` score=82.82 D=0.8573 E=0.7738 P=0.6378 C=1.0 fail=0 quick=True
- 20261109-201148 `indic18-flow030` score=82.22 D=0.8585 E=0.7738 P=0.6059 C=1.0 fail=0 quick=True
- 20261109-201305 `indic19-flow015` score=82.33 D=0.8595 E=0.7738 P=0.6098 C=1.0 fail=0 quick=True
- 20261109-201423 `indic20-flow005` score=79.31 D=0.8206 E=0.7738 P=0.5174 C=1.0 fail=0 quick=True
- 20261109-201603 `indic21-flow010` score=82.34 D=0.8598 E=0.7738 P=0.6098 C=1.0 fail=0 quick=True
- 20261109-202308 `indic22-billveto` score=82.4 D=0.8598 E=0.7738 P=0.6132 C=1.0 fail=0 quick=True
- 20261109-202452 `indic23-billveto2` score=82.25 D=0.8598 E=0.7738 P=0.6056 C=1.0 fail=0 quick=True
- 20261109-202629 `indic24-linkweight` score=81.84 D=0.8593 E=0.7362 P=0.6329 C=1.0 fail=0 quick=True
- 20261109-202804 `indic25-utility-nolink` score=82.22 D=0.8598 E=0.7738 P=0.604 C=1.0 fail=0 quick=True
- 20261109-202932 `indic26-utility-plainlink` score=84.55 D=0.9144 E=0.7738 P=0.6388 C=1.0 fail=0 quick=True
- 20261109-203323 `indic27-utility-billnotice` score=82.62 D=0.8598 E=0.7738 P=0.6241 C=1.0 fail=0 quick=True
- 20261109-203446 `indic28-utility-framing` score=82.87 D=0.8598 E=0.7738 P=0.6365 C=1.0 fail=0 quick=True
- 20261109-203609 `indic29-utility-txn` score=81.34 D=0.858 E=0.7362 P=0.6095 C=1.0 fail=0 quick=True
- 20261109-203756 `indic30-utility-routine` score=83.98 D=0.9144 E=0.7738 P=0.61 C=1.0 fail=0 quick=True
- 20261109-203912 `indic31-full-utility` score=86.23 D=0.9144 E=0.8129 P=0.6736 C=1.0 fail=0 quick=False
- 20261109-204514 `indic32-full-verdictpin` score=86.06 D=0.9144 E=0.8057 P=0.6741 C=1.0 fail=0 quick=False
- Final recommendation: `candidates/indic1`, full run `20261109-203912-indic31-full-utility` score=86.23. The 86.06 verdict-pin run was reverted; prompt and candidate are back to the 86.23 configuration. See research/REPORT.md.
