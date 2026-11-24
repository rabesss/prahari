# Typosquat check for Indian official domains

`candidates/BEST/triage/typosquat.py` flags links on near copies of the domains Indian scam messages
imitate most. It is a transparent rule with no model behind it, and it adds evidence the URL, SMS and
Indian-text rules already know how to weigh.

## What it flags
- **Typos of an official name**, compared on the registrable domain. The repo has no public-suffix
  list, so a small bundled one knows the `.in` second levels, `com.br`-style country endings and free
  hosting platforms such as `github.io` and `vercel.app`, whose tenants are separate sites.
  - Seven to nine letters: one dropped, added or swapped letter (`hdfcbnk.com`, `icicibnak.com`,
    `delhivry.com`).
  - Ten letters or more: two such edits (`unionbankofindla.co.in`).
  - Five or six letters: only two neighbouring letters swapped, after the first two (`patym.com`).
  - The first letter must match. A changed letter counts as two edits, except `l` for `i`
    (`lcicibank.com`, `epfindla.com`). `rn` is also read as `m` (`paytrn.com`).
- **An official stem plus filler words**, joined or hyphenated: `sbionline.com`, `sbi-online-in.com`,
  `irctc-refund.in`, `incometax-gov.in`, `hdfcbank-kyc.com`. The filler words are things like online,
  netbanking, login, kyc, update, refund, reward and claim. Words brands use for their own domains are
  not fillers: bank, card, life, pay, my, app, support and india (`sbicard.com`, `hdfclife.com`,
  `mypaytm.com`, `dtdcindia.com`).
- **Direct `.apk` links**: a URL whose path ends in `.apk` on a host that is not official in either
  list and not a reserved name (`apk_download`). APK links inside a message were already handled by
  the SMS rules.

## What it never flags
- Any official domain in the list and its subdomains.
- Hosts under `.gov.in`, `.nic.in`, `.bank.in`, `.ac.in`, `.edu.in`, `.mil.in` and `.res.in`, where only
  verified owners can register.
- The real name on another ending (`paytm.me`, `airtel.com`, `onlinesbi.com`). In the top-1M check
  these were mostly the brand's own.
- Reserved placeholder names (`.example`, `.test`).
- IP hosts and punycode or non-Latin hosts, which other rules cover.

## Official list and sources
56 registrable domains: major banks and RBI (RBI list of scheduled commercial banks), NPCI,
BHIM and UPI apps (NPCI's list of UPI apps), India Post, IRCTC, income tax, EPFO, UIDAI, DigiLocker,
LIC, Airtel, Jio, Vi, BSNL and the main couriers.

On 24 Nov 2026 each domain was fetched. Most served the organisation's page or redirected to its
`.bank.in` site. A few did not serve a page to the automated check:
- UCO, Union, Central, South Indian, Bank of India and NPCI returned a bot block or timed out.
- `iob.in` returned 404.
- `bankofmaharashtra.in` has only an IPv6 address.

All of these are the domains those organisations publish. Domains that no longer resolve or have
changed hands were left out (`psbindia.com` now serves a gambling page), because a lapsed domain on
an allow list would clear a scam link. The list should be re-checked periodically.

## Where the list counts as official
- **URL route.** A pasted link has no message around it that could claim another organisation, so
  the 56 domains and their subdomains also count as official there. Registry suffixes are not added.
- **SMS and Indian-text rules.** These keep their existing official list unchanged. Widening it let
  an OTP message that pointed at a listed courier's subdomain pass as an official channel.
- **The typosquat check itself** never flags any subdomain of a listed domain.

## False-positive check
The thresholds were set against the Tranco top-1M list (24 Nov 2026). The first draft matched 52
domains, mostly the brands' own sister domains and other banks one letter away (ecobank, rbcbank,
axosbank, idfcbank). The rules above match two (`fecharge.ir`, `pnbonline.com.br`). Brand-owned domains
outside the top 1M are not covered by this check. The URL evaluation set (F1 0.994, FPR 0) is
unchanged: neither signal fires on it.

## Wiring
- **URL route** (`rules.url_indicators`):
  - `typosquat` is added only when the brand-name and digit-swap rules did not already catch the
    host, so one host never gets two lookalike scores.
  - `typosquat` and `apk_download` are strong indicators (+0.1 each to the URL model score).
  - A listed domain on a risky ending (`cred.club`) gets no risky-ending line.
- **SMS and Indian-text routes** (`mech.host_risk`, `indicrules.host_risk`): the check runs after the
  existing host checks, so their evidence and its order are unchanged for every host they already
  flagged.
- The app shows the new lines in English and Hindi; the Hindi summary uses the same strings.

## Known gaps (follow-ups)
- **Not caught:** a lookalike in a subdomain of another domain (`hfdcbank.secure-login.com`) and digit
  swaps that leave no brand substring (`ic1cibank.com`).
- **APK advice:** an APK-only link gets the generic phishing-link advice rather than "do not install
  the file".
- **App:** the app's Kotlin bank-alert list (`MainActivity.kt`) was not widened.
