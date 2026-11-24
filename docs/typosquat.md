# Typosquat check for Indian official domains

`candidates/BEST/triage/typosquat.py` flags links on near copies of the domains Indian scam messages
imitate most. It is a transparent rule with no model behind it, and it adds evidence the URL, SMS and
Indian-text rules already know how to weigh.

## What it flags
- **Typos of an official name**, compared on the registrable domain (a small bundled suffix list, since
  the repo has no public-suffix list; it knows the `.in` second levels, `com.br`-style country endings
  and free hosting platforms such as `github.io` and `vercel.app`, whose tenants are separate sites): one dropped, doubled or swapped letter for names of seven to nine
  letters (`hdfcbnk.com`, `icicibnak.com`, `delhivry.com`), two such edits for ten letters or more
  (`unionbankofindla.co.in`), and only two neighbouring letters swapped for five- or six-letter names
  (`patym.com`). The first letter must match. A changed letter counts as two edits, except `l` for `i`
  (`lcicibank.com`, `epfindla.com`). `rn` is also read as `m` (`paytrn.com`).
- **An official stem plus filler words**, joined or hyphenated: `sbionline.com`, `sbi-online-in.com`,
  `irctc-refund.in`, `incometax-gov.in`, `hdfcbank-kyc.com`. The filler words are things like online,
  netbanking, login, kyc, update, refund, reward and claim. Words brands use for their own domains are
  not fillers: bank, card, life, pay, my, app and support (`sbicard.com`, `hdfclife.com`, `mypaytm.com`).
- **Direct `.apk` links**: a URL whose path ends in `.apk` on a non-official host (`apk_download`).
  APK links inside a message were already handled by the SMS rules.

## What it never flags
Any official domain in the list, its subdomains, hosts under `.gov.in`, `.nic.in`, `.bank.in`,
`.ac.in` and `.edu.in` (only verified owners can register there), the real name on another ending
(`paytm.me`, `airtel.com`, `onlinesbi.com` are usually the brand's own), reserved placeholder names
(`.example`, `.test`), IP hosts and punycode or non-Latin hosts (other rules cover those).

## Official list and sources
56 registrable domains: major banks and RBI (RBI list of scheduled commercial banks), NPCI,
BHIM and UPI apps (NPCI's list of UPI apps), India Post, IRCTC, income tax, EPFO, UIDAI, DigiLocker,
LIC, Airtel, Jio, Vi, BSNL and the main couriers. On 24 Nov 2026 each domain was fetched: most served
the organisation's page or redirected to its `.bank.in` site; a few bank sites (UCO, Union, Central,
Bank of Maharashtra, South Indian, Bank of India, NPCI) answered with a bot block or timed out, but their
names resolved and they are the domains those organisations publish. Domains that no longer resolve or
have changed hands were left out (`psbindia.com` now serves a gambling page), because a lapsed domain on
an allow list would clear a scam link. In the existing URL, SMS and Indian-text rules the new list
counts as official only for the bare domain and its `www.` host: a deeper subdomain of an unrelated
organisation (`sbi-login.ecomexpress.in`) must not clear a message that imitates a bank. The typosquat
check itself never flags any subdomain of a listed domain.

## False-positive check
The thresholds were set against the Tranco top-1M list (24 Nov 2026). The first draft matched 52
domains, mostly the brands' own sister domains and other banks one letter away (ecobank, rbcbank,
axosbank, idfcbank). The rules above match two (`fecharge.ir`, `pnbonline.com.br`). The URL evaluation set (F1 0.994,
FPR 0) is unchanged: neither signal fires on it.

## Wiring
- URL route (`rules.url_indicators`): `typosquat` is added only when the brand-name and digit-swap
  rules did not already catch the host, so one host never gets two lookalike scores. `typosquat` and
  `apk_download` are strong indicators (+0.1 each to the URL model score).
- SMS and Indian-text routes (`mech.host_risk`, `indicrules.host_risk`): checked after the existing
  host checks, so their evidence and its order are unchanged.
- The app shows the new lines in English and Hindi; the Hindi summary uses the same strings.
