# C_fix1 versus BEST

Source BEST tree: `4c1b4f5364a4f4e6129ee77a4f2bbd07517f0362`. Evaluated C_fix1 tree: `9edc0f7fe5df973e644bb1164015f615acd15296`. The candidates share the fitted detector artifacts; the flow-text rules apply to descriptions, whereas the proxy flow task uses feature records.

## Frozen proxy

| | Recorded BEST (11 Nov) | C_fix1 (20 Nov) |
|---|---:|---:|
| Total | 90.73 | 90.49 |
| Detection D | 0.9024 | 0.9024 |
| Explanation E | 0.9473 | 0.942 |
| Performance P | 0.7486 | 0.7433 |
| Compliance C | 1.0 | 1.0 |
| Explanation seconds per item | 3.67 | 3.72 |

Two repeats, zero failures and zero infrastructure errors. These runs are on different dates and are not a paired performance comparison. The proxy gives uncertain labels half credit. E mention rate fell from 0.714 to 0.679; the private per-item explanations were not inspected, so the cause is not established.

## Conventional detector metrics

Both candidates produced the same aggregates. Conditional rates use decided items; conservative rates treat each abstention or invalid output as an error. Predictions with missing or invalid labels count in the denominator. Undefined rates are null in the JSON. URL contains three duplicate input rows; both this evaluator and the frozen proxy keep the last gold and prediction for each ID. The input is a previously used private evaluation set, not a fresh holdout.

| Task | n | positive / negative | decided / uncertain / invalid | coverage | conditional P / R / F1 / FPR | conservative P / R / F1 / FPR |
|---|---:|---:|---:|---:|---|---|
| sms | 1162 | 196 / 966 | 1153 / 9 / 0 | 0.9923 | 0.9706 / 0.8594 / 0.9116 / 0.0052 | 0.9429 / 0.8418 / 0.8895 / 0.0104 |
| url | 7997 | 3997 / 4000 | 7984 / 13 / 0 | 0.9984 | 1.0000 / 0.9912 / 0.9956 / 0.0000 | 1.0000 / 0.9880 / 0.9940 / 0.0000 |
| indic | 320 | 160 / 160 | 317 / 3 / 0 | 0.9906 | 0.9868 / 0.9554 / 0.9709 / 0.0125 | 0.9868 / 0.9375 / 0.9615 / 0.0125 |
| flow | 22544 | 12833 / 9711 | 22544 / 0 / 0 | 1.0000 | 0.9706 / 0.7568 / 0.8505 / 0.0303 | 0.9706 / 0.7568 / 0.8505 / 0.0303 |

The JSON aggregates are retained outside the repository under the Oracle evidence directory.

## Promotion decision

Promoted to `candidates/BEST`; the recorded old version is available at Git tag `best-omp-final-9073` (`39134acf460de1e65341e53c39d5285202ec2cf6`). The detection score is identical; the only changes that touch the LLM path are the intended benign-wording and prompt changes; the P delta is unpaired run-to-run latency; a −0.24 proxy change is accepted under the plan's rule for correctness fixes. The private per-item explanations were not inspected, so the cause of the E difference is not established.

## Visible explanation comparison

On 28 project-authored visible cases, the frozen proxy consistency check passed 28/28 for both candidates; consistency_v2 passed 28/28 for both. These are heuristics, not semantic safety guarantees. For example, the generated OTP advice says to be cautious when sharing login information; the fixed action separately says never to share OTPs or PINs. The flow brute-force explanation suggests disconnecting users without qualification. The table compares full generated explanations on visible cases; hidden per-item outputs were not read.

| Visible case | BEST | C_fix1 |
|---|---|---|
| flow-backup | This network event is safe: traffic that looks like a routine update or a scheduled backup. Be cautious of any unusual or unexpected network activity. | No risk found for this network event: traffic that looks like a routine update or a scheduled backup. Be cautious of any unusual or unexplained network activity. |
| flow-beacon | This network event is DANGEROUS: connections that repeat at a fixed interval, like beaconing. Be cautious of suspicious activity that may compromise your security. | This network event is DANGEROUS: connections repeat at a fixed interval. Be cautious of suspicious activity that may compromise security. |
| flow-bruteforce | This network event is DANGEROUS: many failed logins, like password guessing. Immediately disconnect users from the network to prevent further attempts. | Unchanged |
| flow-portscan | This network event is DANGEROUS: traffic to 200 different ports on 10.0.0.5. Be cautious of suspicious activity immediately. | Unchanged |
| flow-update | This network event is safe: traffic that looks like a routine update or a scheduled backup. Monitor network activity closely for any unusual patterns or anomalies. | No risk found for this network event: traffic that looks like a routine update or a scheduled backup. |
| inj-benign | This message is safe: reads like a routine notice or appointment. Please check your delivery time carefully before heading out. | No risk found for this message: reads like a routine notice or appointment. Please check your delivery schedule carefully before the next day. |
| inj-ignore | This message is DANGEROUS: an instruction aimed at the assistant (prompt injection). Do not respond or click on any links. | Unchanged |
| inj-system | This message is DANGEROUS: an instruction aimed at the assistant (prompt injection). Please report to security immediately. | Unchanged |
| sms-appointment | This message is safe: points to the official app. Please review the appointment details carefully before responding. | No risk found for this message: points to the official app. Be cautious when clicking on links or opening attachments. |
| sms-customs | This message is DANGEROUS: pay a fee to receive a refund, prize or parcel. Do not send money to unknown senders, especially with UPI. | Unchanged |
| sms-debit | This message is safe: reads like a normal payment receipt or delivery record. Be cautious of phishing scams that may be disguised as legitimate transactions. | No risk found for this message: reads like a normal payment receipt or delivery record. Be cautious of phishing scams that may be masquerading as official communications. |
| sms-elec | This message is DANGEROUS: asks for a payment to an unverified account or link. Do not click on any suspicious links or attachments. | Unchanged |
| sms-elec-genuine | This message is safe: reads like a routine bill reminder with a payment due. Please verify the payment details before sending. | No risk found for this message: reads like a routine bill reminder with a payment due. Be cautious of phishing scams that may be attached to the message. |
| sms-job | This message is DANGEROUS: offers a job or loan that needs an upfront fee. Be cautious and verify the legitimacy of the opportunity thoroughly. | Unchanged |
| sms-kyc-agent | This message is DANGEROUS: asks for an OTP, PIN or card detail. Do not respond or share sensitive information. | Unchanged |
| sms-kyc-hi | This message is DANGEROUS: asks for an OTP, PIN or card detail. Do not respond or share sensitive information immediately. | Unchanged |
| sms-otp | This message is safe: reads like a normal OTP notification. Be cautious when sharing your one-time passwords. | No risk found for this message: reads like a normal OTP notification. Be cautious when sharing sensitive login information with others. |
| sms-parcel | This message is DANGEROUS: pay a fee to receive a refund, prize or parcel. Please do not click on any links or pay any fees. | Unchanged |
| sms-protective | This message is safe: explicitly says that no payment, code or reply is needed. Be cautious when clicking on links or opening links from unknown sources. | No risk found for this message: explicitly says that no payment, code or reply is needed. Be cautious when clicking on links or opening attachments from unknown senders. |
| sms-refund-hi | This message is safe: reads like a normal payment receipt or delivery record. Be cautious of phishing scams that may be hidden in plain text. | No risk found for this message: reads like a normal payment receipt or delivery record. Be cautious of phishing scams that may be masquerading as a refund notice. |
| url-amaz0n | This link is DANGEROUS: risky .top lookalike domain amaz0n-refund-help.top. Do not click on it, it may harm your device and personal data. | Unchanged |
| url-icici | This link is safe: official domain www.icicibank.com. Always use secure websites with a lock icon. | No risk found for this link: official domain www.icicibank.com. Be cautious of phishing scams that may be disguised as a bank website. |
| url-ip | This link is DANGEROUS: a raw IP address instead of a name. Do not attempt to access this URL due to security risks. | Unchanged |
| url-irctc | This link is safe: official domain www.irctc.co.in. Always access websites from trusted and familiar websites. | No risk found for this link: official domain www.irctc.co.in. Be cautious of phishing scams that may be disguised as a search. |
| url-kyc | This link is DANGEROUS: risky .top lookalike domain sbi-kyc.in-verify.top. Do not click on it, it may harm your device. | Unchanged |
| url-paytm | This link is safe: official domain paytm.com. Be cautious of phishing scams that may be disguised as a legitimate offer. | No risk found for this link: official domain paytm.com. Be cautious of phishing scams that may lead to financial loss. |
| url-paytm-fake | This link is DANGEROUS: risky .xyz lookalike domain paytm-offer.xyz. Do not click on it, it may harm your device and personal data. | Unchanged |
| url-shortener | This link is DANGEROUS: URL shortener bit.ly. Do not click on it, it may harm your device. | Unchanged |
