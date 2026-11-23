"""Indian 'digital arrest' and voice-call scam script rules (pure Python, offline).

Designed for transcripts produced from WhatsApp voice notes, shared audio files, or
consented speakerphone recordings. Runs alongside Prahari's existing SMS/Indic detector
without altering core text-message behaviour unless Call Guard is invoked.

All rules are clause-scoped and check for protective/awareness framing so genuine bank
security reminders ("real police never do digital arrest", "never share your OTP on a call")
do not trigger false alarms.
"""
import re
import unicodedata

SPLIT_RE = re.compile(r"[.!?।;\n]+")

# Caller impersonates Indian law enforcement, customs, judiciary, telecom regulator or central bank.
FAKE_AUTHORITY_RE = re.compile(
    r"\b(?:c\.?\s*b\.?\s*i\.?|central bureau of investigation|cyber\s*(?:crime|cell|police)|"
    r"crime branch|mumbai police|delhi police|bangalore police|bengaluru police|"
    r"narcotics(?:\s+control\s+bureau)?|\bn\.?\s*c\.?\s*b\.?|"
    r"enforcement directorate|\be\.?\s*d\.?\s+officer|\bd\.?\s*r\.?\s*i\.?|"
    r"customs\s+(?:department|officer|office|authority)|airport customs|"
    r"\bt\.?\s*r\.?\s*a\.?\s*i\.?|telecom\s+(?:department|regulatory|authority)|"
    r"department of telecom(?:munications)?|"
    r"supreme court|high court|cbi court|magistrate|investigation officer|"
    r"inspector\s+[a-z]+|sub[- ]?inspector|cyber\s+officer|police\s+(?:headquarters|station|officer|commissioner)|"
    r"vigilance\s+(?:department|officer)|"
    r"(?:r\.?\s*b\.?\s*i\.?|reserve bank)\s+(?:officer|compliance|verification|vigilance|department|safe))\b"
    r"|(?<!\w)(?:सीबीआई|साइबर\s*(?:पुलिस|क्राइम|सेल)|मुंबई\s*पुलिस|दिल्ली\s*पुलिस|"
    r"क्राइम\s*ब्रांच|नारकोटिक्स|प्रवर्तन\s*निदेशालय|कस्टम(?:\s*(?:विभाग|अधिकारी))?|"
    r"ट्राई|दूरसंचार\s*विभाग|सुप्रीम\s*कोर्ट|मजिस्ट्रेट|जांच\s*अधिकारी|इंस्पेक्टर|"
    r"पुलिस\s*अधिकारी|आरबीआई\s*(?:अधिकारी|वेरिफिकेशन))",
    re.I,
)

# Demands that the victim stay connected and not hang up.
NO_DISCONNECT_RE = re.compile(
    r"\b(?:do not|don't|dont|must not|cannot|can't|never)\s+(?:disconnect|hang\s*up)\b"
    r"|\b(?:do not|don't|dont|must not|cannot|can't|never)\s+(?:cut|end|drop|leave|close)\s+"
    r"(?:the\s+|this\s+|your\s+)?(?:phone\s+|video\s+)?(?:call|line|phone)\b"
    r"|\b(?:keep|stay|remain)\s+(?:the\s+|this\s+)?(?:call|line)\s+(?:open|connected|active|on)\b"
    r"|\bstay\s+on\s+(?:the|this)\s+(?:line|call|phone)\b"
    r"|\bif\s+you\s+(?:disconnect|hang\s*up|cut\s+(?:the|this)\s+call)\b"
    r"|\b(?:phone|call|line)\s+(?:mat|na)\s+(?:kat\w*|kaat\w*|band\s+kar\w*)\b"
    r"|\bline\s+par\s+rah\w*\b"
    r"|(?:फोन|फ़ोन|कॉल|लाइन)\s*(?:मत|न)\s*(?:काट\w*|बंद\s*कर\w*)"
    r"|(?:फोन|फ़ोन|कॉल|लाइन)\s*(?:चालू|पर)\s*रह\w*",
    re.I,
)

# Coerced video surveillance, room isolation, or secrecy from family/lawyers.
VIDEO_ISOLATION_RE = re.compile(
    r"\b(?:stay|remain|keep|come|join|connect)\b[^.!?\n]{0,30}\b(?:on\s+)?(?:video\s*call|skype|whatsapp\s*video|camera\s*on)\b"
    r"|\b(?:video\s*call|camera)\b[^.!?\n]{0,25}\b(?:alone|on|open|active|24\s*hours?)\b"
    r"|\b(?:stay|sit|remain|be)\s+(?:alone\s+)?in\s+(?:a|your|the)\s+room(?:\s+alone)?\b"
    r"|\block\s+(?:the\s+|your\s+)?(?:room\s+)?door\b"
    r"|\b(?:close|shut)\s+(?:the\s+|your\s+)?(?:room\s+)?door\s+and\s+(?:stay|sit|remain)\b"
    r"|\b(?:never|do not|don't|dont|must not)\s+(?:tell|inform)\s+(?:anyone|anybody|your\s+family|family|"
    r"friends|police)\s+(?:about|regarding)\s+(?:this|the)\s+(?:call|case|investigation|matter|inquiry)\b"
    r"|\b(?:do not|don't|dont|must not|cannot)\s+(?:tell|inform|call|contact|speak\s+to|talk\s+to)\s+"
    r"(?:anyone|anybody|your\s+family|family|spouse|wife|husband|parents|children|friends|lawyer|advocate|police)\b"
    r"(?!\s+(?:your\s+|the\s+)?(?:otp|pin|password|cvv|upi|card|account\s+details))"
    r"|\b(?:keep\s+(?:this|it|the\s+call|the\s+case)\s+(?:strictly\s+)?(?:secret|confidential)|"
    r"under\s+(?:virtual|digital|online|camera)\s+(?:custody|surveillance|monitoring))\b"
    r"|\b(?:kamre\s+mein\s+akele|kisi\s+ko\s+(?:mat|na)\s+bata\w*|video\s+call\s+par\s+rah\w*)\b"
    r"|(?:कमरे\s*में\s*अकेले|वीडियो\s*कॉल\s*पर\s*(?:रह\w*|बने\s*रह\w*)|कैमरा\s*(?:चालू|ऑन)\s*रख\w*|"
    r"(?:किसी\s*को|परिवार\s*को|घर\s*में)\s*(?:मत|न)\s*बता\w*|दरवाजा\s*बंद\s*कर)",
    re.I,
)

# "Transfer money to RBI/government/police safe or verification account".
SAFE_ACCOUNT_VERIFY_RE = re.compile(
    r"\b(?:r\.?\s*b\.?\s*i\.?|reserve\s+bank|government|govt|supreme\s+court|police|c\.?\s*b\.?\s*i\.?|official|central)\s+"
    r"(?:safe|secure|verification|audit|escrow|monitoring|settlement|custody|temporary)\s+"
    r"(?:verification\s+)?(?:bank\s+)?(?:account|wallet|a/c)\b"
    r"|\b(?:safe|verification|escrow|custody)\s+(?:verification\s+)?(?:bank\s+)?(?:account|wallet|a/c)\b"
    r"|\b(?:transfer|send|move|deposit|wire|remit|shift)\b(?!\s+(?:the|this|your)\s+(?:call|line))"
    r"[^.!?\n]{0,30}\b(?:money|funds|amount|savings|balance|rupees|rs|lakhs?|thousand|\d[\d,]*)\b[^.!?\n]{0,40}\b"
    r"(?:to\s+verify|for\s+(?:rbi\s+|police\s+|court\s+|fund\s+|account\s+)?verification|"
    r"rbi\s+account|government\s+account|clear\s+your\s+(?:funds|money|account))\b"
    r"|\b(?:refunded|returned|credited\s+back)\s+(?:immediately\s+)?after\s+(?:the\s+)?(?:verification|audit|inquiry|investigation)\b"
    r"|\b(?:break|liquidate|close|empty)\s+(?:your\s+)?(?:fixed\s+deposit|fd|savings|bank\s+account)\b"
    r"|(?:आरबीआई|सरकारी|पुलिस|सुरक्षित|सेफ|वेरिफिकेशन|सत्यापन)\s*(?:वेरिफिकेशन\s*)?(?:खाते|अकाउंट|खाता)"
    r"|(?:खाते|अकाउंट)\s*में\s*(?:पैसे|राशि|रकम)\s*(?:ट्रांसफर|जमा|भेज)",
    re.I,
)

# Contraband parcel (drugs/MDMA/passports/SIMs) allegedly seized by customs or linked to Aadhaar.
CONTRABAND_PARCEL_RE = re.compile(
    r"\b(?:parcel|package|courier|consignment|shipment)\b[^.!?\n]{0,55}"
    r"\b(?:drugs?|narcotics?|mdma|cocaine|heroin|contraband|illegal|fake\s+passports?)\b"
    r"|\b(?:illegal\s+drugs?|narcotics?\s+parcel|drugs?\s+(?:were\s+)?(?:found|seized))\b"
    r"|\b(?:parcel|package|courier|consignment)\b[^.!?\n]{0,45}"
    r"\blink(?:ed)?\s+to\s+your\s+(?:aadhaa?r|ad[- ]?har|pan)\b"
    r"|\b(?:illegal\s+sim|drugs?|narcotics?|contraband)\b[^.!?\n]{0,45}"
    r"\b(?:link(?:ed)?\s+to\s+your\s+(?:aadhaa?r|ad[- ]?har|pan|id|mobile|number)|in\s+your\s+name)\b"
    r"|(?:पार्सल|कूरियर)\s*(?:में|से)\s*(?:ड्रग्स|नशीले\s*पदार्थ|अवैध|पासपोर्ट|सिम)"
    r"|(?:ड्रग्स|नशीले\s*पदार्थ)[^।.!?\n]{0,30}(?:पार्सल|कस्टम|आधार|पकड़)",
    re.I,
)

# Digital arrest / arrest warrant / immediate police arrest / money-laundering case threat.
ARREST_WARRANT_RE = re.compile(
    r"\b(?:digital\s+arrest|virtual\s+arrest|arrest\s+warrant|non[- ]?bailable\s+warrant|"
    r"warrant\s+(?:is\s+|was\s+|has\s+been\s+)?issued(?:\s+in\s+your\s+name)?|"
    r"(?:police|officers?|we)\s+(?:will|are\s+coming\s+to)\s+(?:come\s+(?:to\s+)?)?arrest\s+you|"
    r"you\s+(?:will\s+be|are|are\s+under)\s+(?:arrested|arrest|digital\s+arrest)|"
    r"(?:money\s+laundering|hawala|pmla|terror\s+funding|narcotics)\s+(?:case|investigation|charges?)|"
    r"f\.?\s*i\.?\s*r\.?\s+(?:has\s+been\s+)?(?:registered|filed)\s+against\s+you)\b"
    r"|(?:डिजिटल\s*(?:अरेस्ट|गिरफ्तारी)|गिरफ्तारी\s*(?:वारंट|का\s*वारंट)|वारंट\s*जारी|"
    r"पुलिस\s*(?:गिरफ्तार|अरेस्ट)\s*कर|मनी\s*लॉन्ड्रिंग\s*(?:केस|मामला)|एफआईआर\s*दर्ज)",
    re.I,
)

# TRAI / telecom disconnection threat + IVR press-9 / transfer-to-officer script.
TELECOM_IVR_RE = re.compile(
    r"\b(?:mobile\s+number|phone\s+number|sim(?:\s+card)?|all\s+your\s+numbers?|telecom\s+services?)\b"
    r"[^.!?\n]{0,45}\b(?:disconnected|blocked|suspended|deactivated|terminated)\b"
    r"|\bpress\s+(?:nine|9|one|1|zero|0)\b[^.!?\n]{0,45}\b(?:officer|police|cyber|customer\s+care|department|verify|speak|talk)\b"
    r"|\b(?:mobile|sim|number)\b[^.!?\n]{0,35}\b(?:band\s+ho\s+jayega|kat\s+jayega)\b"
    r"|(?:मोबाइल\s*नंबर|सिम|नंबर)\s*(?:बंद|ब्लॉक|डिएक्टिवेट)\s*हो\s*(?:जाएगा|रहा)",
    re.I,
)

# Caller demands reading out OTP/PIN/CVV/account verification or installing remote screen-share app.
CALL_SECRET_REMOTE_RE = re.compile(
    r"\b(?:share|tell|read\s+out|dictate|give|provide|enter|confirm)\b[^.!?\n]{0,35}"
    r"\b(?:otp|one[- ]?time\s+password|upi\s+pin|mpin|cvv|atm\s+pin|bank\s+password|verification\s+code)\b"
    r"|\b(?:verify\s+your\s+bank\s+account|confirm\s+your\s+bank\s+balance)\b"
    r"|\b(?:install|download|open)\b[^.!?\n]{0,30}\b(?:anydesk|teamviewer|quicksupport|rustdesk|screen[- ]?shar\w*)\b"
    r"|(?:ओटीपी|पिन|सीवीवी|पासवर्ड)[^।.!?\n]{0,25}(?:बता\w*|भेज\w*|दीजिए|दो)"
    r"|(?:एनीडेस्क|टीमव्यूअर|स्क्रीन\s*शेयर)",
    re.I,
)

# Framing that describes a scam as a warning/advisory rather than making a scammer's demand.
# Third-person narrative about scams ("real police never ...", "fraudsters pose as CBI"): the clause
# describes a scam instead of running one, up to a contrast word ("..., but I am CBI").
AWARENESS_NARRATIVE_RE = re.compile(
    r"\b(?:no\s+such\s+thing\s+as(?:\s+a)?\s+digital\s+arrest|"
    r"(?:real|genuine)\s+(?:police|cbi|customs|rbi|banks?|officials?|ed|trai)"
    r"(?:\s*,\s*|\s+and\s+|\s+or\s+|,\s*and\s+)?(?:(?:police|cbi|customs|rbi|banks?|officials?|ed|trai)"
    r"(?:\s*,\s*|\s+and\s+|\s+or\s+|,\s*and\s+)?)*\s*(?:never|do\s+not|don't|will\s+not|won't)|"
    r"(?:fraudsters?|scammers?|fake\s+(?:police|cbi|officers?))\s+(?:are|may|often|try|pose|claim|call|threaten))\b"
    r"|(?:डिजिटल\s*अरेस्ट\s*जैसी\s*कोई\s*(?:चीज़|चीज)\s*नहीं|ठग\s*(?:नकली|फर्जी))",
    re.I,
)
# Labels a genuine reminder uses. They mark the call as protective but never hide a rule match,
# because a scammer can say them too ("security reminder from CBI: you are under digital arrest").
AWARENESS_LABEL_RE = re.compile(
    r"\b(?:routine\s+security\s+reminder|security\s+reminder|fraud\s+awareness|scam\s+alert)\b"
    r"|सुरक्षा\s*चेतावनी",
    re.I,
)
# Negated advice ("never transfer to a safe account", "do not share your OTP").
AWARENESS_NEGATED_RE = re.compile(
    r"\b(?:never\s+(?:conduct|do|ask|share|transfer|move|stay|pay|give)|"
    r"do\s+not\s+(?:share|transfer|move|stay\s+on\s+a\s+video\s+call|pay|believe|fall\s+for)|"
    r"don't\s+(?:share|transfer|move|pay|believe|fall\s+for))\b"
    r"|कभी\s*(?:न|मत|नहीं)\s*(?:बताएं|साझा|ट्रांसफर|भेजें|करें)",
    re.I,
)
REPORTED_RE = re.compile(
    r"\b(?:if|did|has|have|whether|when)\s+(?:anyone|anybody|someone|the\s+caller|a\s+caller|they|he|she)\s+"
    r"(?:ever\s+)?(?:ask|asks|asked|tell|tells|told|request\w*|want\w*)\b",
    re.I,
)
CONTRAST_RE = re.compile(r"\b(?:but|however|yet|although|though|lekin|par)\b|लेकिन|पर\s", re.I)
_STRONG_NEGATOR_RE = re.compile(r"\b(?:never|not|don't|dont|avoid|कभी|मत|नहीं)\b", re.I)
_WEAK_NEGATOR_RE = re.compile(r"\b(?:no|without|nor|न)\b", re.I)
_BREAK_RE = re.compile(r"\b(?:and|but|then|so|or|aur|lekin|just|now|immediately|instead|rather|only)\b"
                       r"|[,:;—-]|और|लेकिन", re.I)

# Routine benign cues on everyday calls/voice notes.
BENIGN_CALL_RE = re.compile(
    r"\b(?:no\s+(?:fee|payment|charge|otp|pin)\s+(?:is\s+)?(?:required|needed|due)|"
    r"official\s+(?:[a-z]+\s+)?(?:app|portal|website)|visit\s+your\s+(?:home\s+)?branch|"
    r"confirm\s+your\s+appointment|whenever\s+it\s+is\s+convenient|"
    r"at\s+your\s+convenience|reception\s+desk|no\s+hurry|no\s+rush)\b",
    re.I,
)

DIGITAL_ARREST_RE = re.compile(r"\bdigital\s+arrest\b|डिजिटल\s*(?:अरेस्ट|गिरफ्तारी)", re.I)

RULE_SPECS = [
    ("fake_authority_call", FAKE_AUTHORITY_RE,
     "caller impersonates police, CBI, customs, TRAI, court or RBI"),
    ("arrest_warrant", ARREST_WARRANT_RE,
     "threatens a 'digital arrest', arrest warrant or criminal case"),
    ("contraband_parcel", CONTRABAND_PARCEL_RE,
     "claims a parcel with illegal drugs or contraband is linked to your name or Aadhaar"),
    ("no_disconnect", NO_DISCONNECT_RE,
     "orders you not to disconnect or hang up the call"),
    ("video_isolation", VIDEO_ISOLATION_RE,
     "pressures you to stay alone on video call or hide the call from family"),
    ("safe_account_verify", SAFE_ACCOUNT_VERIFY_RE,
     "asks you to transfer money to a 'safe' or RBI verification account"),
    ("telecom_ivr_scam", TELECOM_IVR_RE,
     "threatens imminent mobile/SIM disconnection or uses a press-9 cyber-officer script"),
    ("call_secret_or_remote", CALL_SECRET_REMOTE_RE,
     "asks for OTP/PIN/bank verification or a remote screen-sharing app during the call"),
]

# Rules strong enough to mark a call dangerous on their own or in combination.
DIGITAL_ARREST_SIGNALS = frozenset({
    "fake_authority_call",
    "arrest_warrant",
    "contraband_parcel",
    "no_disconnect",
    "video_isolation",
    "safe_account_verify",
    "telecom_ivr_scam",
})

SOLO_DECISIVE = frozenset({
    "safe_account_verify",
    "call_secret_or_remote",
})


def normalize_transcript(text: str) -> str:
    """Clean ASR output lightly (NFKC, collapse whitespace) without stripping Indic script."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = re.sub(r"[\u200b-\u200f\u2060\ufeff\u00ad]", "", s)
    # Whisper writes "C. B. I." / "R. B. I."; join them so sentence splitting keeps the name whole.
    s = re.sub(r"\b(?:[A-Za-z]\.\s?){2,}",
               lambda m: re.sub(r"[.\s]", "", m.group(0)) + " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _split_clauses(text: str) -> list[str]:
    return [c.strip() for c in SPLIT_RE.split(text) if c.strip()]


def _clause_is_protective(clause: str) -> bool:
    return bool(AWARENESS_NARRATIVE_RE.search(clause) or AWARENESS_LABEL_RE.search(clause)
                or AWARENESS_NEGATED_RE.search(clause))


def _active_segments(clauses: list[str]) -> list[str]:
    """Text a call script can be matched in. A narrative clause about scams is skipped up to its
    first contrast word; everything else stays active."""
    out = []
    for c in clauses:
        m = AWARENESS_NARRATIVE_RE.search(c) or REPORTED_RE.search(c)
        if m:
            cut = CONTRAST_RE.search(c, m.end())
            if cut:
                out.append(c[cut.end():])
            continue
        out.append(c)
    return [seg.strip() for seg in out if seg.strip()]


def _negated(segment: str, start: int) -> bool:
    """True when the words just before a match negate it ("never transfer money to a safe account",
    "do not stay ..."): a strong negator up to six words back, "no"/"without" up to two, stopping at
    "and", "but", "just", a comma and similar breaks ("don't panic, just transfer" is a demand)."""
    before = segment[max(0, start - 80):start]
    parts = _BREAK_RE.split(before)
    words = (parts[-1] if parts else before).split()
    return bool(_STRONG_NEGATOR_RE.search(" ".join(words[-6:])) or _WEAK_NEGATOR_RE.search(" ".join(words[-2:])))


def _rule_hit(rx: re.Pattern, segment: str) -> bool:
    return any(not _negated(segment, m.start()) for m in rx.finditer(segment))


def analyze_call(transcript: str) -> dict:
    """Analyze a call or voice-note transcript for Indian digital-arrest and voice-scam scripts.

    Returns a dict with:
      - label: 1 (dangerous), "uncertain" (suspicious), or 0 (no call-script hit)
      - score: float in [0, 1]
      - signals: list of matched rule names
      - evidence: list of human-readable evidence strings
      - protective: bool (True if genuine security reminder / benign call phrasing dominates)
      - is_digital_arrest: bool
      - scam_type: str (empty when benign)
    """
    text = normalize_transcript(transcript)
    if not text:
        return {
            "label": 0,
            "score": 0.0,
            "signals": [],
            "evidence": [],
            "protective": False,
            "is_digital_arrest": False,
            "scam_type": "",
            "active_text": "",
            "set_aside": False,
        }

    clauses = _split_clauses(text)
    protective_clauses = [c for c in clauses if _clause_is_protective(c)]
    benign_cues = bool(BENIGN_CALL_RE.search(text))

    # Match each rule in the active text. A match governed by a negation ("never transfer to a
    # safe account") is advice, not a demand, and does not count. Labels such as "security
    # reminder" hide nothing, so a scammer cannot borrow them to clear a script.
    hits: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    active = _active_segments(clauses)
    joined = " ".join(active)

    for name, rx, desc in RULE_SPECS:
        if any(_rule_hit(rx, seg) for seg in active) or _rule_hit(rx, joined):
            hits.append((name, desc))
            seen_names.add(name)

    # Determine if an explicit "digital arrest" / coercive authority script is present.
    da_hits = seen_names & DIGITAL_ARREST_SIGNALS
    has_authority = "fake_authority_call" in seen_names
    has_coercion = bool(seen_names & {
        "arrest_warrant", "contraband_parcel", "no_disconnect",
        "video_isolation", "safe_account_verify", "telecom_ivr_scam",
    })
    explicit_digital_arrest = any(
        _rule_hit(DIGITAL_ARREST_RE, seg) for seg in active
    )

    # Scoring & verdict:
    # - 2+ digital-arrest signals, OR solo decisive demand, OR explicit digital arrest -> DANGEROUS (1)
    # - 1 strong coercion/authority signal alone -> SUSPICIOUS ("uncertain")
    # - 0 hits -> 0 (caller defers to existing detector, or stays benign)
    if (
        len(seen_names) >= 2
        or bool(seen_names & SOLO_DECISIVE)
        or explicit_digital_arrest
        or (has_authority and has_coercion)
    ):
        label: int | str = 1
        score = min(0.99, 0.84 + 0.03 * len(seen_names))
    elif len(seen_names) == 1:
        label = "uncertain"
        score = 0.55
    else:
        label = 0
        score = 0.05 if (protective_clauses or benign_cues) else 0.10

    is_da = bool(label == 1 and (explicit_digital_arrest or len(da_hits) >= 2 or (
        "safe_account_verify" in seen_names and (has_authority or "arrest_warrant" in seen_names or "video_isolation" in seen_names)
    )))

    if label == 0:
        scam_type = ""
    elif is_da:
        scam_type = "a digital arrest scam call"
    elif "safe_account_verify" in seen_names:
        scam_type = "a safe-account transfer scam call"
    elif "telecom_ivr_scam" in seen_names and (has_authority or "contraband_parcel" in seen_names):
        scam_type = "a fake TRAI or customs scam call"
    elif "call_secret_or_remote" in seen_names:
        scam_type = "an OTP, bank-verification or remote-app scam call"
    elif has_authority or "arrest_warrant" in seen_names:
        scam_type = "a fake police, CBI or customs threat call"
    else:
        scam_type = "a suspicious call script"

    evidence = [desc for _, desc in hits]
    if not evidence and (protective_clauses or benign_cues):
        if protective_clauses:
            evidence.append("reads like a security reminder advising you not to share secrets or pay")
        elif benign_cues:
            evidence.append("reads like a routine appointment, delivery or official-app notice with no payment demand")

    return {
        "label": label,
        "score": round(score, 4),
        "signals": [n for n, _ in hits],
        "evidence": evidence[:6],
        "protective": bool((protective_clauses or benign_cues) and not hits),
        "is_digital_arrest": is_da,
        "scam_type": scam_type,
        # The text left after narrative and reported-speech clauses are set aside.
        "active_text": joined,
        "set_aside": any(AWARENESS_NARRATIVE_RE.search(c) or REPORTED_RE.search(c) for c in clauses),
    }
