"""Mechanism-level analysis of a message: what it asks the reader to DO.

A scam is a *request that harms*: hand over a secret, pay to receive money, approve a
collect request, install a remote-access app, move funds to a "safe" account, or act on a
threat through a channel the real organisation does not use. A genuine alert may mention
amounts, codes, links and deadlines, so none of those alone is evidence: the decision needs
both the mechanism and the absence of the legitimate channel that would explain it.

Everything here is clause-scoped and negation-aware ("do not share", "share na karein",
"किसी को न बताएं"), so protection statements are read as protection, not as requests.
Reported speech counts too: "the agent is asking for the code" describes the same demand as
"send the code", which is how advisory corpora often phrase a scam attempt.
"""
import re
import unicodedata
from urllib.parse import urlparse

SPLIT = ".!?।;\n"
# Hindi perfective forms ("जमा किए गए हैं", "भुगतान हो गया", "ट्रांसफर की गई") report money that already
# moved; only the bare or imperative verb ("जमा करें", "भुगतान करें") asks the reader to pay.
_NOT_PERFECTIVE = (r"(?!\s*(?:हो\s*(?:गए|गई|गया|गये|चुके|चुकी|चुका)|हुए|हुई|हुआ|हुये|"
                   r"(?:किए|किये|की|किया|कर\s*दिए|कर\s*दी|कर\s*दिया)\s*(?:गए|गई|गया|गये|जा\s*चुके)))")
NEG = re.compile(
    r"\b(no|not|never|without|n't|dont|don't|doesn't|does not|will not|won't|avoid|"
    r"nahi|nahin|mat|bina|na)\b"
    r"|(?:^|[\s,;:])(न|मत|बिना|नहीं|कोई नहीं)(?:[\s,;:]|$)", re.I)
# Only a negator attached to the request vetoes it. "bina call kiye ... transfer kar" negates
# the call, not the transfer; "agar payment nahi hua to message jayega" is a threat, not advice.
NEG_VERB = re.compile(r"(?:\b(?:do not|don't|does not|doesn't|did not|not|never|will not|won't|"
                      r"should not|shouldn't|must not|no need to|not to|avoid|no)\b|"
                      r"(?:^|[\s,;:])(?:न|मत))\s+(?:\w+\s+){0,4}$|"
                      # "you never need to enter your PIN or scan a QR code": the negated auxiliary
                      # reaches the second verb of the same clause
                      r"\b(?:never|not|no)\s+(?:need|needed)\s+to\s+(?:\w+\s+){0,9}$", re.I)
NEG_AFTER = re.compile(r"^\s*(?:is|are|was|were|को|की|का|to)?[^\n]{0,20}?"
                       r"(?:\b(?:not|never|no)\b|नहीं(?![\u0900-\u097F])|(?:na|mat|nahi)\b|"
                       r"(?:न|मत)(?=[\s,;:।]|$))", re.I)
NEG_INSIDE = re.compile(r"(?:^|[\s,;:])(?:न|मत|नहीं)(?:[\s,;:]|$)|"
                        r"(?:^|\s)(?:nahi|nahin|mat|na|not|no|never)(?:\s|$)|"
                        # "penalty se bachne ke liye ...": the matched harm is what to avoid
                        r"(?:^|\s)(?:se|से)\s*bach\w*", re.I)

# Credentials and identity material a scammer asks a victim to hand over. Bare "kyc" and
# generic words like "details" are deliberately absent: routine notices mention them.
CREDS = (r"(otp|one[- ]?time (password|code|pin)|verification code|login code|security code|"
         r"\bpin\b|mpin|upi pin|debit card (pin|cvv)|credit card (pin|cvv)|cvv|password|passcode|"
         r"net ?banking (password|login|details|id)|internet banking (password|login|details)|"
         r"bank login|login (details|credentials|id)|username and password|card (details|number)|"
         r"gift card (code|number)|\b(4|6)[- ]?digit (code|number|pin)\b|last (four|4) digits|"
         r"bank screen|screen(shot)? of (your|the) (bank|payment|upi) app|"
         r"पिन|ओटीपी|गुप्त कोड|पासवर्ड|सीवीवी|बैंक लॉगिन|लॉगिन|बैंक स्क्रीन|"
         r"बैंक ऐप का स्क्रीन|एटीएम पिन|गिफ्ट कार्ड)")
CRED = (r"(otp|one[- ]?time (password|code|pin)|verification code|login code|security code|"
        r"\bpin\b|mpin|upi pin|debit card (pin|number|cvv|details)|credit card (number|cvv|pin|details)|"
        r"card (number|details|no)|cvv|password|passcode|net ?banking (password|login|details|id)|"
        r"internet banking (password|login|details)|bank login|login (details|credentials|id)|"
        r"username and password|account (number|details)|card (details|number)|gift card (code|number)|"
        r"\b(4|6)[- ]?digit (code|number|pin)\b|last (four|4) digits|"
        r"aadhaar|आधार|\bpan\b|date of birth|\bdob\b|selfie|"
        r"bank screen|screen(shot)? of (your|the) (bank|payment|upi) app|"
        r"पिन|ओटीपी|गुप्त कोड|कोड|पासवर्ड|सीवीवी|कार्ड|खाता संख्या|पैन|जन्मतिथि|"
        r"बैंक लॉगिन|लॉगिन|बैंक स्क्रीन|बैंक ऐप का स्क्रीन|एटीएम पिन|गिफ्ट कार्ड)")
# A secret that is only ever safe to *enter* yourself. An official app or portal can explain
# these verbs; it can never explain "share/send/tell", which banks never ask for.
SHARE = (r"(shar(e|ing)|send(ing)?|reply|telling|tell|giv(e|ing)|forward(ing)?|read out|dictat(e|ing)|"
         r"bhejein|bhejo|bhej\w*|batao|bataen|bataein|bata do|saza\w*|"
         r"भेजें|भेजो|बताएं|बताओ|साझा|दें|दो|भरो)")
ENTER = (r"(enter(ing)?|typ(e|ing)|fill(ing)?|provid(e|ing)|submit(ting)?|confirm(ing)?|"
         r"verif(y|ying)|updat(e|ing)|upload(ing)?|डाल\w*|दर्ज\w*|पुष्टि|स्वीकार|भर\w*|अपडेट|करें|कराएं|कराएँ|करवाएं)")
DEMAND = (r"(\b(ask|asks|asked|asking|demand|demands|demanded|demanding|want|wants|wanted|"
          r"request|requests|requested|requesting|require|requires|required|requiring)\b|मांग\w*|कहता है|कहती है|कह रह\w*|"
          r"bolta hai|bol rah\w*|keh rah\w*|कहा है|कहते हैं|maang\w*|maang rah\w*)")
PAY = (r"\b(pay|paid|paying|send|sends|sending|transfer|transfers|deposit|deposits|remit|fund|"
       r"approve|approves|authori[sz]e|scan|buy|purchase|top[- ]?up|recharge|bhar\w*)\b"
       r"|(bhej\w*|jama\w*|daal\w*)|भुगतान|भेजें|भेजो|भेजने|जमा" + _NOT_PERFECTIVE + r"|भरें|भरो|स्वीकार|टॉप ?अप|"
       r"ट्रांसफर\s*(करें|करो|कर दें|कीजिए|करना)")
AMOUNT = (r"(rs\.?|inr|₹|rupees|रुपये|राशि|amount|money|balance|bill|invoice|dues|शुल्क|फीस|"
          r"पैसा|पैसे|पेमेंट|भुगतान)")
MONEY = (r"\b(money|payment|amount|cash|funds|deposit|fee|charge|balance|rupees|rs\.?|inr|"
         r"paise|paisa)\b|₹|रुपये|राशि|रकम|पैसे|पैसा|फीस|शुल्क|भुगतान")
DEST_OFFICIAL = (r"\b(in|via|through|using|on|at)\s+(the\s+)?(official\s+)?(bank\s+|payment\s+|"
                 r"provider\s+|insurer\s+|company\s+|merchant\s+|utility\s+|telecom\s+|"
                 r"electricity\s+|solar\s+|courier\s+)?(app|application|portal|website|site|"
                 r"account settings|ATM|branch)\b|"
                 r"\bofficial\s+(?:[a-z]+\s+){0,2}(app|portal|website|site|channel|desk|helpline|"
                 r"helpdesk|support|care|number|branch)\b|"
                 r"आधिकारिक (ऐप|पोर्टल|वेबसाइट|चैनल)|"
                 r"(ऐप|पोर्टल|वेबसाइट|थाने|शाखा)\s*(में|पर|से|द्वारा)\s*"
                 r"(भुगतान|देख\w*|जांच\w*|करें|कर सकते)|"
                 r"\bat the (ATM|branch)\b|\bat the bank branch\b|"
                 r"\bback of your card\b|\bsigned[- ]in\b|"
                 r"\bnumber on (the )?(back of )?your card\b|"
                 r"\b(in|via|on) your (banking |payment )?app\b|"
                 r"\b(via|in|on|through) the [a-z0-9]{2,}\s+(app|portal)\b|"
                 r"(अधिकृत|आधिकारिक)\s*(ऐप|पोर्टल|वेबसाइट)")
# A payee that is a private person, not a merchant or an institution.
DEST_PERSONAL = (
    r"(to|into|at|on)\s+(this|that|the following|my|another|unknown|new|private|personal|"
    r"alag|naye|nijee)\s+(?:\w+\s+){0,2}(account|number|wallet|upi|vpa|khata|खाते|वॉलेट)|"
    r"(to|for|को)\s+(this|that|my|मेरे|अपने|उस)?\s*(cashier|lawyer|advocate|वकील|agent|cousin|uncle|aunty)|"
    r"\b(personal|private|unknown|another|audit|alag|nijee)\s+(account|wallet|khate|खाते|वॉलेट|"
    r"upi|vpa|number)|"
    r"(nijee|niji|private|personal|निजी)\s+(khate|खाते)|"
    r"\b(is|us|uss|iss|this)\s+number\s+(par|pe)\b|"
    r"(temporary|safe|secure)\s+(account|खाते)|"
    r"(lawyer|advocate|वकील)[^.;!?।\n]{0,15}(account|khate|खाते|account mein)|"
    r"\b[6-9]\d{9}\b|\+91|"
    r"\b[a-z0-9._%+-]+@[a-z]{2,}\b|"
    r"(इस|नीचे दिए|दिए गए)\s+(लिंक|अकाउंट|खाते|वॉलेट)|"
    r"\b(phone|mobile|whatsapp|telegram)\b\s*(number|par|pe|se)\b|"
    r"crypto|bitcoin|usdt|wallet address")
# A payee that is *suspicious on its own*: a private account, an unknown wallet, a personal
# mobile number or a relative's "lawyer". Used to decide a payment demand without relying on
# a chat-model score.
DEST_STRONG = (
    r"(personal|private|unknown|another|audit|alag|nijee|niji)\s+(account|wallet|khate|खाते|वॉलेट|"
    r"upi|vpa|number)|"
    r"(nijee|niji|private|personal|निजी)\s+(khate|खाते)|"
    r"(to|into|at|on)\s+(this|that|the following|my|another|unknown)\s+(?:\w+\s+){0,2}"
    r"(account|number|wallet|upi|vpa|खाते|वॉलेट)|"
    r"(to|for|को)\s+(this|that|my|मेरे|अपने|उस)?\s*(cashier|lawyer|advocate|वकील)|"
    r"(lawyer|advocate|वकील)\s*(को|ke|के)|"
    r"(lawyer|advocate|वकील)[^.;!?।\n]{0,15}(account|khate|खाते)|"
    r"(temporary|safe|secure)\s+(account|खाते)|"
    r"\b[a-z0-9._%+-]+@[a-z]{2,}\b|"
    r"\b(a/c|acct|account)\s{0,3}(no\.?|number|#)?\s{0,3}[:.\-]?\s{0,3}\d{9,18}\b|"
    r"(pay|send|transfer|deposit|bhej\w*|jama\w*|bhar\w*|भेजें|जमा|भरें)[^.;!?।\n]{0,25}"
    r"\b(is|us|uss|this|iss) number\b|"
    r"(agent|officer|advisor|representative|staff)[’']?s?\s+(number|account|upi|vpa)|"
    r"crypto|bitcoin|usdt|wallet address")
PAY_TO_RECEIVE = (
    # pay, deposit or authorise now, so that money or goods are released afterwards
    r"(pay|paid|send|transfer|deposit|remit|top[- ]?up|buy|purchase|authori[sz]e|approve|"
    r"bhej\w*|jama\w*|bhar\w*|भेजें|जमा|भरें|स्वीकार)"
    r"[^.;!?।\n]{0,60}"
    r"(to (get|receive|claim|unlock|release|withdraw|secure|activate|accept)|"
    r"before (you can |we |they |i )?(credit|release|withdraw|send|deliver|process|refund|pay)|"
    r"so (that )?(you|we|i) can (receive|withdraw|get)|in order to (receive|withdraw|claim)|"
    r"(and|then) (we|i) will (refund|credit|release|pay|send)|"
    r"tabhi|तभी|तभी तो|के बदले|release hoga|release hogi|mil jayega|मिल जाएगा|प्राप्त होगा)"
    r"|"
    # a refund, prize or withdrawal that needs a fee or deposit first
    r"(refund|prize|award|lottery|withdrawal|payout|delivery|parcel|इनाम|रिफंड|वापसी|"
    r"पार्सल|डिलीवरी|निकासी)"
    r"[^.;!?।\n]{0,50}"
    r"(se pehle|से पहले|before|ke liye|के लिए|tabhi|तभी|पहले)"
    r"[^.;!?।\n]{0,40}"
    r"(pay|send|transfer|deposit|fee|charge|jama|bhej\w*|bhar\w*|शुल्क|भेज|जमा|भर)")
FEE = (r"(processing|registration|verification|activation|shipping|customs|clearance|delivery|"
       r"release|reset|late|penalty|unlock|reactivation|redemption|starter|security|training|"
       r"service|stamp|documentation|convenience|file|legal|insurance|maintenance|joining|"
       r"kyc|pan|aadhaar)\s*"
       r"(fee|charge|amount|cost|deposit|duty)"
       r"|(refundable|security)\s+(bond|deposit)"
       r"|(शुल्क|फीस|चार्ज|जमानत|ड्यूटी)")
COLLECT = (r"(collect request|payment request|कलेक्ट अनुरोध|भुगतान अनुरोध|"
           r"upi (mandate|debit|autopay)|mandate required)")
COLLECT_ACTION = (r"(approve|accept|authori[sz]e|स्वीकार|अनुमोदन|मंजूर)")
QR = (r"(scan (this|the|our|below) qr|this qr|qr code|scan kar\w*|स्कैन)")
REMOTE = (r"\b(anydesk|teamviewer|quicksupport|rustdesk|screen[- ]shar\w*|remote[- ]access "
          r"(software|app|tool)|remote app|remote support)\b|"
          r"\b(install|download)\b[^.;!?।\n]{0,30}\b(app|application|apk|software|tool)\b|"
          r"grant (contacts|sms|access|permissions)|"
          r"ऐप (लगाकर|इंस्टॉल)|ऐप डाउनलोड|रिमोट (ऐप|सॉफ्टवेयर)|स्क्रीन (साझा|शेयर)")
THREAT_BLOCK = (
    # Hindi: "खाता बंद हो जाएगा / ब्लॉक हो रहा है" (the account will be closed or is being blocked)
    r"\b(account|sim|card|connection|number|service|upi|banking|खाता|सिम|कार्ड|सेवा|नंबर|यूपीआई)\b"
    r"[^.;!?।\n]{0,50}\b(बंद|ब्लॉक|निलंबित|फ्रीज|काट|डिएक्टिवेट)\s+हो\s*"
    r"(?:जाएगा|जाएगी|रहा है|रही है|गया है|गई है|सकता है|जा सकता है)|"
    r"\b(block|blocked|suspend|suspended|deactivat\w*|disconnect\w*|cut[- ]?off|freeze|frozen|"
    r"expire\w*|penalty|arrest|warrant|legal action|fir|closure|forfeit\w*|dhamki|blackmail\w*|"
    r"धमकी|डरा\w*)\b"
    r"[^.;!?।\n]{0,60}"
    r"\b(account|sim|card|service|connection|number|access|electricity|power|water|gas|bill|itr|"
    r"deposit|subsidy|rebate|pension|earnings|payout|balance|खाता|सिम|सेवा|बिजली|कार्ड|जमा)"
    r"|\b(account|sim|card|connection|number|electricity|power|bill|deposit|subsidy|payout|खाता|सिम|बिजली|कार्ड)\b"
    r"[^.;!?।\n]{0,60}\b(will be|ho gaya|ho jayega|हो जाएगा|हो गया|हो सकता|हो गई|कर दिया|काट दिया|बंद|निलंबित|फ्रीज)"
    r"[^.;!?।\n]{0,40}\b(block|blocked|cut|suspend|deactiv\w*|disconnect\w*|closed|reject\w*|forfeit\w*|बंद|निलंबित|फ्रीज)"
    r"|\b(block|blocked|band|बंद|ब्लॉक|निलंबित|फ्रीज)\b[^.;!?।\n]{0,40}\b(account|card|sim|number|खाता|कार्ड|सिम)"
)
# A threat to expose the reader to their contacts or family ("sab contacts ko bhej dunga").
THREAT_EXPOSE = (
    r"(contacts?|family|friends|photos?|videos?)\s*(ko|to)?\s*(message|post|publish|share|leak|bhej\w*)|"
    r"(message|post|publish|share|leak)\b[^.;!?।\n]{0,30}(contacts?|family|friends)|"
    r"(कॉन्टैक्ट|संपर्क|परिवार)[^।;!?\n]{0,30}(संदेश|भेज|वायरल|पोस्ट)")
THREAT = THREAT_BLOCK + "|" + THREAT_EXPOSE
EXPOSE_DESC = "threatens to send or post something about you to your contacts or family"
AUTHORITY = (r"\b(police|cbi|ncb|dri|ed|enforcement directorate|customs|court|magistrate|narcotics|"
             r"cyber ?cell|cyber crime|crime branch|inspector|sub[- ]inspector|\btrai\b|\brbi\b|"
             r"income tax|investigation officer|compliance (desk|officer)|vigilance|digital arrest)\b"
             r"|(पुलिस|सीबीआई|कस्टम|अदालत|नारकोटिक्स|आयकर|प्रवर्तन|साइबर सेल|साइबर पुलिस|"
             r"साइबर अपराध|ट्राई|मजिस्ट्रेट|जांच अधिकारी|कथित अधिकारी|डिजिटल अरेस्ट|डिजिटल गिरफ्तारी)")
AUTHORITY_ACT = (r"\b(case|warrant|arrest|legal action|fir|penalty|parcel|summons|notice|inquiry|"
                 r"investigation|probe|detain\w*|complaint|seized|contraband|drugs|money laundering|illegal)\b|"
                 r"(जांच|मामला|वारंट|गिरफ्तारी|कार्रवाई|नोटिस|पूछताछ|हिरासत|शिकायत|अपराध|आदेश|"
                 r"पार्सल|ड्रग्स|नशीला|तस्करी|धनशोधन|फर्जी)")
JOB = (r"(work from home|work-from-home|part[- ]time job|part time job|paid batch|work batch|"
       r"daily income|earn (rs\.?|₹|inr)?\s?\d+|data entry|घर से काम|कमाई|नौकरी|"
       r"\binterview\b|shortlisted|vacancy|recruitment|hiring|appointment letter|joining letter|"
       r"review earnings|review job|product review|prepaid order|\bjob\b|\btask\b|\bpayout\b|"
       r"नियुक्ति पत्र|भर्ती|चयन सूची|समीक्षा कार्य|टास्क)")
LOAN = (r"(instant loan|loan approval|loan approved|pre[- ]approved|personal loan|"
        r"बिना दस्तावेज|without documents|लोन|ऋण|आसान कमाई|disbursal|loan desk)")
UPFRONT = (r"(starter kit|buy training|training fee|processing fee|registration fee|security deposit|"
           r"(काम|task|batch|job|work|नौकरी)[^.;!?।\n]{0,35}(जमा राशि|deposit|फीस|fee|शुल्क)|"
           r"(pay|send|transfer|deposit|bhej\w*|jama\w*|भेजें|जमा|भरें)[^.;!?।\n]{0,45}"
           r"(registration|booking|seat|confirmation|interview|fee|charge|duty|deposit|amount|bond|"
           r"appointment letter|joining letter|offer letter)"
           r"[^.;!?।\n]{0,30}(rs\.?|inr|₹|rupees|रुपये)?\s*\d{2,6}|"
           r"(pay|send|transfer|deposit|bhej\w*|jama\w*|भेजें|जमा|भरें)\s+"
           r"(rs\.?|inr|₹|rupees)?\s*[\d,]{2,7}[^.;!?।\n]{0,40}"
           r"(appointment letter|joining letter|offer letter)|"
           r"(pay|send|transfer|deposit|bhej\w*|jama\w*|भेजें|जमा|भरें)\s+"
           r"(rs\.?|inr|₹|rupees)?\s*[\d,]{2,7}[^.;!?।\n]{0,30}"
           r"(registration|booking|seat|confirmation|interview|fee|charge|deposit|bond|security)|"
           r"(pay|send|transfer|deposit|bhej\w*|jama\w*|भेजें|जमा|भरें)[^.;!?।\n]{0,40}"
           r"(fee|charge|duty|deposit|bond|amount)[^.;!?।\n]{0,40}"
           r"(account|before|to (send|release|start|join|process)|so (that|i)|tabhi|तभी)|"
           r"(buy|purchase)[^.;!?।\n]{0,40}(order|package|task|bundle|batch)[^.;!?।\n]{0,40}"
           r"(withdraw|release|payout|earning|balance)|"
           r"(नियुक्ति पत्र|appointment letter)[^।;!?\n]{0,50}(जमा राशि|deposit|fee|शुल्क|पैसे)|"
           r"(paise|paisa|money|रकम|पैसे)[^.;!?।\n]{0,25}(daal|jama|deposit|bhej\w*|भेज|जमा)"
           r"[^.;!?।\n]{0,40}(balance|clear|withdraw|payout|release|निकाल)|"
           r"pay (a )?(small )?(fee|charge|deposit|duty)|fee (bhejein|jama)|"
           r"(शुल्क|फीस|जमा राशि)\s*(भरें|भेजें|करें|दें)|"
           r"pay to (unlock|activate|start|join)|(जमा राशि|अग्रिम)[^।;!?\n]{0,25}(भरें|जमा|दें)|"
           r"(फीस|शुल्क)[^।;!?\n]{0,25}(जमा|भरें|दें)|"
           # amount first, verb after: "Rs 700 bhejo", "700 रुपये जमा करें"
           r"((?<![\d,])(rs\.?|inr|₹|rupees)\s*\d{2,6}|(?<![\d,])\d{2,6}\s*(rupaye|रुपये))"
           r"[^.;!?।\n]{0,25}"
           r"(bhej\w*|bhejo|bhejein|jama\w*|transfer|pay|deposit|भेजें|भेजो|जमा|भरें|दें)"
           r"[^.;!?।\n]{0,40}(verification|फीस|fee|charge|processing|approval|loan|लोन|registration|"
           r"unlock|disbursal|अनुमोदन|सत्यापन)|"
           r"verification (ke naam par|के नाम पर)|"
           # recharge first, task later: "recharge bhejo, task unlock hoga"
           r"(recharge|top[- ]?up|रिचार्ज)[^.;!?।\n]{0,40}"
           r"(task|batch|group|work|job|unlock|start|join|काम|बैच|ग्रुप|टास्क)|"
           r"(task|batch|group|work|job|काम|बैच|टास्क)[^.;!?।\n]{0,40}"
           r"(recharge|top[- ]?up|रिचार्ज))")
PRIZE = (r"\b(won|winner|lottery|lucky draw|jackpot|prize|इनाम|लॉटरी|जीत|पुरस्कार|लकी ड्रॉ|"
         r"ipo allotment|allotment guaranteed)\b"
         r"|(guaranteed (profit|return|allotment)|fixed weekly return|निश्चित साप्ताहिक|"
         r"गारंटीड|निश्चित लाभ)")
PRIZE_ACT = (r"(pay|send|fee|charge|details|claim|deposit|tax|bhar\w*|शुल्क|भरें|भरो|भेजें|जमा|"
             r"विवरण|जानकारी|प्राप्त)")
INVEST = (r"(guaranteed|assured|fixed)\s+[^.;!?।\n]{0,30}(return|profit|income|gain)"
          r"|(double|triple)\s+your\s+(money|investment|capital)"
          r"|(\d{1,3}\s*(%|percent)\s*(monthly|per month|weekly|per week|daily|per day))")
INVEST_ACT = (r"(deposit|add|fund|invest|top[- ]?up|join|pay|transfer|bhej\w*|jama\w*|भेजें|जमा|निवेश)"
              r"[^.;!?।\n]{0,40}(fund|money|amount|rs\.?|inr|₹|wallet|group|plan)"
              r"|(fund|money|amount|rs\.?|inr|₹|wallet|group|plan)[^.;!?।\n]{0,40}"
              r"(deposit|add|invest|join|transfer|bhej\w*|jama\w*|भेजें|जमा)")
SAFE_ACCOUNT = (r"(temporary|safe|secure|audit|सेफ|अस्थायी|सुरक्षित)\s+"
                r"(account|wallet|खाते|अकाउंट|खाता|account me)"
                r"|(verification|government|settlement|escrow|सरकारी|सत्यापन)\s+"
                r"(account|wallet|खाते|अकाउंट|खाता)"
                r"|(rbi|reserve bank|आरबीआई|भारतीय रिज़र्व बैंक)\s+(verification\s+)?"
                r"(account|wallet|अकाउंट|खाता)"
                r"|(transfer|send|move|bhej\w*|भेजें|ट्रांसफर|deposit)[^.;!?।\n]{0,45}"
                r"(whole|entire|full|all the|savings|balance|पूरी राशि|सारा पैसा)"
                r"|(account|खाता)[^.;!?।\n]{0,20}(khali|khaali|empty|zero|खाली)")
CRYPTO = r"(crypto|bitcoin|usdt|binance|wallet address|क्रिप्टो|बिटकॉइन)"
NEW_CONTACT = (r"(new (number|phone|sim|mobile)|naya (number|phone|sim)|naye number|"
               r"number badal|अज्ञात नंबर|unknown number|नया नंबर|नंबर बदल|"
               r"phone ghar par reh gaya|phone (is )?(off|switched off)|cannot talk|"
               r"can't talk|बात नहीं कर सकत\w*|फोन बंद)")
SECRECY = (r"(keep (this|it|the call) (a )?secret|secret from|"
           r"(do not|don't|never) (tell|inform)[^.;!?।\n]{0,30}"
           r"(anyone|anybody|family|spouse|wife|husband|parents|police|lawyer|advocate|"
           r"किसी को|परिवार|पत्नी|पति|वकील|पुलिस)|"
           r"(kisi ko|kisi ko bhi)?\s*(na|mat)\s*(bata|batana|batayein)|"
           r"किसी को (न|मत) बत\w*|घर में किसी को न बत\w*|chupke|चुपचाप|"
           r"without telling|बिना बताए)")
ISOLATION = (r"\b(alone|akele|akela)\b[^.;!?।\n]{0,25}(call|video|room|stay|reh\w*)|"
             r"(stay|remain|keep)[^.;!?।\n]{0,20}(on|in)[^.;!?।\n]{0,15}(video|call|room)|"
             r"(video call|video par|कैमरे पर|वीडियो कॉल)[^.;!?।\n]{0,30}"
             r"(alone|akele|अकेले|stay|रह\w*)|"
             r"(कमरे में अकेले|कमरे में रहें|कैमरा (चालू|on)|कैमरा चालू रख\w*)|"
             r"(room alone|camera on|keep the camera on|stay in the room|door (band|closed))|"
             r"(कमरे का दरवाजा बंद|दरवाजा बंद रख)|"
             r"(वकील से संपर्क न करें|परिवार से संपर्क न करें|पुलिस को न बताएं|"
             r"lawyer se sampark na karein)"
             r"|(do not|don't|never)\s+(disconnect|cut|leave|end|close)\s+(the\s+|this\s+)?"
             r"(video\s+|phone\s+)?(call|line)"
             r"|keep (the|this) (call|line) (connected|on|open)")
MONEY_MOVE = (r"(break|close|withdraw|empty|khali|khaali|निकाल|तोड़)[^.;!?।\n]{0,30}"
              r"(fixed deposit|fd|deposit|account|savings|balance|खाते|जमा)")
VIDEO = (r"(video call|on video|video par|कैमरे पर|वीडियो कॉल|वीडियो पर)")
# Identity documents a KYC, loan or "verification" scam asks the reader to send into a chat or to
# an unknown link. Aadhaar/PAN photocopies are the material an Indian loan or KYC scam collects.
IDENT = (r"(aadhaar|aadhar|आधार|\bpan\b|पैन|passport|पासपोर्ट|voter id|मतदाता|driving licen[cs]e|"
         r"date of birth|\bdob\b|जन्म ?तिथि|selfie|सेल्फी)")
IDENT_ACT = (r"(send|share|upload|enter|provide|photo|copy|update|bhej\w*|भेजें|भेजो|साझा|डालें|दर्ज|अपलोड|अपडेट)")
KYC_CONTEXT = (r"(kyc|केवाईसी|bank|बैंक|account|खाता|loan|लोन|verif\w*|update|blocked|बंद)")
PRIVATE_CHANNEL = (r"(whatsapp|telegram|व्हाट्सएप|टेलीग्राम|this chat|isi chat|इसी चैट|"
                   r"this number|isi number|इसी नंबर|\bdm\b|\binbox\b)")
UTILITY = (r"(electricity|power|meter|बिजली|मीटर|discom|mahadiscom|bses|torrent|"
           r"water bill|gas connection|bill|बिल)")
# A staff member of "ours" is not a bank or merchant payee: utilities and telecoms never ask you to
# send money to an individual officer. The determiner keeps "the delivery agent" out.
DEST_STAFF = (r"\b(our|their|company|senior|bank'?s?)\s+(agent|officer|executive|representative|"
              r"lineman|technician|operator|supervisor|staff)\b")
# Review-task scams ask the reader to buy the item first and promise a refund plus commission.
BUY_REFUND = (r"(buy|purchase|order|book)\b[^.;!?।\n]{0,50}"
              r"(refund|reimburse|commission|cashback|full amount back|paise wapas|पैसे वापस)")

RISKY_BRANDS = ("sbi", "hdfc", "icici", "axis", "kotak", "pnb", "paytm", "phonepe", "gpay", "bhim",
                "npci", "amazon", "flipkart", "irctc", "uidai", "aadhaar", "incometax", "epfo", "airtel",
                "jio", "indiapost", "netflix", "paypal", "google", "apple", "microsoft", "kbc", "rbi",
                "trai", "mahadiscom", "lic", "bsnl", "vodafone", "tata", "baroda", "canara", "union",
                "idbi", "indusind", "bandhan", "yesbank", "bescom", "cesc", "uppcl", "adani", "reliance",
                "indane", "bharatgas", "iocl", "hpcl", "bpcl", "swiggy", "zomato", "myntra", "mobikwik",
                "freecharge", "sancharsaathi", "cybercrime", "chakshu", "sebi", "nsdl", "groww", "zerodha")
RISKY_TLDS = {"top", "xyz", "club", "online", "site", "live", "icu", "buzz", "info", "click", "link",
              "work", "rest", "fit", "tk", "ml", "ga", "cf", "gq", "shop", "vip", "cc", "win", "loan",
              "example"}
RESERVED_TLDS = {"example", "test", "invalid", "localhost"}
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".bank.in", ".ac.in", ".edu.in")
OFFICIAL_DOMAINS = {"sbi.co.in", "onlinesbi.sbi", "hdfcbank.com", "icicibank.com", "axisbank.com",
                    "kotak.com", "pnbindia.in", "paytm.com", "phonepe.com", "npci.org.in",
                    "bhimupi.org.in", "amazon.in", "amazon.com", "flipkart.com", "myntra.com",
                    "irctc.co.in", "uidai.gov.in", "incometax.gov.in", "epfindia.gov.in",
                    "indiapost.gov.in", "pib.gov.in", "cybercrime.gov.in", "sancharsaathi.gov.in",
                    "airtel.in", "jio.com", "bsnl.co.in", "mahadiscom.in", "google.com", "apple.com",
                    "microsoft.com", "netflix.com", "paypal.com",
                    # public sites of other Indian banks, billers and couriers
                    "bankofbaroda.in", "canarabank.com", "unionbankofindia.co.in", "idbibank.in",
                    "indusind.com", "yesbank.in", "bandhanbank.com", "federalbank.co.in",
                    "southindianbank.com", "centralbankofindia.co.in", "punjabandsindbank.co.in",
                    "indianbank.in", "bankofindia.com", "ucobank.in",
                    "tatapower.com", "cesc.co.in", "bescom.org", "uppcl.org",
                    "bluedart.com", "dhl.com", "fedex.com", "delhivery.com", "licindia.in", "licindia.com"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "shorturl.at",
              "tiny.cc", "ow.ly"}
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+|"
                    r"\b(?:[a-z0-9-]+\.)+(?:com|in|net|org|top|xyz|info|co|ly|me|io|site|online|link|"
                    r"click|live|vip|cc|shop|club|app|biz|pro|icu|buzz|work|rest|fit|tk|ml|ga|cf|gq|"
                    r"dev|net|org|example)(?:/[^\s<>\"']*)?", re.I)
# A mobile number: ten digits starting 6-9, optionally prefixed by +91 or 0, which may be split by
# spaces or punctuation ("98,76543210"), or written masked in a sample ("98XXXXXX66"). Reference,
# consumer and card numbers, amounts, short codes and toll-free lines do not have this shape.
PHONE = (r"(?:(?<!\w)(?:\+?91[\s-]?|0[\s-]?)?[6-9]\d(?:[\s.,/()\u2013\u2014-]{0,2}\d){8}(?!\w)"
         r"|(?<!\w)[6-9]\d?[xX×*]{4,6}\d{2,3}(?!\w))")
# A chat the reader is sent to, as distinct from a chat a warning merely names ("WhatsApp groups
# ... are scams", "never asks for details on WhatsApp").
CHAT_CONTACT = (r"\b(whatsapp|telegram)\s+(?:us|me|kar\w*|karein|karo|kijiye|pe|par|on|at)\b|"
                r"\b(?:on|via|through|by|over)\s+(?:whatsapp|telegram)\b[^.;!?।\n]{0,40}"
                r"\b(?:call|chat|message|video|contact|send|share|upload|report|submit|apply|"
                r"register|verify|confirm|talk|speak|join|connect|reach)\b|"
                r"\b(?:call|contact|chat|message|reach|join)\b[^.;!?।\n]{0,30}\b(?:whatsapp|telegram)\b|"
                r"(?:व्हाट्सऐप|व्हाट्सएप|टेलीग्राम)\s*(?:पर|कर\w*|से)")
URGENCY = (r"\b(?:immediately|urgent|urgently|right away|at once|asap|right now|today itself|"
           r"within \d+[- ]?(?:hours?|hrs?|minutes?|mins?)|turant|abhi|जल्दी|तुरंत|अभी)\b")
# An alert that tells the reader what to do if they did not make the request or transaction.
SELF_CHECK = re.compile(
    r"\bif (?:it |this )?(?:was |is )?(?:not |never )(?:you|done by you|done|initiated|requested|"
    r"authori[sz]ed|made|attempted)\b|\bif (?:it |this )?(?:was |is )?unauthori[sz]ed\b|"
    r"\bif (?:you|u) (?:did|do) not\b|\bif you didn'?t\b|in case you did not|"
    r"agar aapne (?:ye |yeh |यह )?nahi|अगर आपने नहीं|यदि आपने नहीं|"
    r"\b(?:was|is) (?:not |never )(?:done|initiated|requested|authori[sz]ed|attempted|made)(?: by you)?\b|"
    r"\bnot (?:done|initiated|requested|attempted|authori[sz]ed) by you\b|"
    r"\bdid not (?:request|initiate|authori[sz]e|make|attempt) (?:this|it|the)\b", re.I)
# A delivery code handed over in person to the delivery staff at the door.
DOORSTEP_HANDOVER = re.compile(
    r"\b(delivery|courier)\b[^.;!?।\n]{0,80}\b(associate|agent|partner|executive|boy|person|staff|"
    r"driver|representative)\b[^.;!?।\n]{0,50}\b(at (?:your|the) (?:door|doorstep|address|home)|"
    r"in person|at the time of delivery|when (?:he|she|they) (?:arrives?|comes?|reaches?)|"
    r"on delivery|at delivery)\b", re.I)
# A named app, portal or store ("Axis Mobile app", "bob World app", "Jio Store") is the
# organisation's own channel when the name is a proper noun or a known brand. Generic wording
# ("your application", "the approved portal") names no organisation and stays unverified.
_APP_WORDS = r"(?:[Aa]pp|[Aa]pplication|[Pp]ortal|[Ss]tore|[Ww]ebsite|[Ss]ite)"
_NOT_A_NAME = ("This|That|The|Our|Your|My|Their|Any|All|Official|New|Approved|Linked|Below|Above|"
               "Following|Same|Other|Another|Fake|Unknown|Bank|Payment|Net|Online|Digital|Android|"
               "IPhone|IPad|Phone|Free|Safe|Secure|Trusted|Verified|Instant|Latest|Updated|Original|"
               "Genuine|Registered|Real|Important|Please|Now|Kindly|Download|Install|Open|Update|Pay|"
               "Send|Share|Enter|Verify|Click|Today|Immediately|Also|Then|And|Or|For|To|Of|In|On|At|By|"
               "With|From|Use|Using|Via|Recharge|Bill|KYC|OTP|SIM|UPI|Card|Account")
NAMED_APP = re.compile(
    r"\b(?:in|on|via|at|from|through|using|open|visit|se|par|mein)\s+(?:the\s+|your\s+|apne\s+)?"
    r"(?:[a-z0-9&]+\s+){0,2}(?!(?:" + _NOT_A_NAME + r")\s)(?:[A-Z][\w-]*\s+){1,3}" + _APP_WORDS + r"\b"
    r"|\b(?:in|on|via|at|from|through|using|open|visit|se|par|mein)\s+(?:the\s+|your\s+|apne\s+)?"
    r"(?:(?:" + "|".join(RISKY_BRANDS) + r")[\w]*\s+){1,3}(?:app|application|portal|store)\b"
    r"|(?!(?:" + _NOT_A_NAME + r")\s)(?:[A-Z][\w-]*\s+){1,3}[Aa]pp\s+(?:par|mein|se|in|on)\b")
# A payment request between acquaintances that says there is no hurry; a scam pressures.
NO_HURRY = (r"\b(?:no (?:hurry|rush|urgency)|koi jaldi nahi|jab (?:fursat|furusat) (?:mile|ho)|"
            r"when (?:you )?(?:have|get) (?:the |some )?time|at (?:your )?convenience|"
            r"apni (?:suvidha|aaram) se|jab bhi (?:aap )?(?:chahein|chaho|chaaho))|"
            r"जब फ़ुर्सत मिले|जब फुर्सत मिले|कोई जल्दी नहीं|जब चाहें")
# The sender's own record: an order status in Hinglish, or a transfer the sender has already made.
OWN_RECORD = (
    r"\b(?:order|booking|payment|refund|recharge|delivery|ticket)[^.;!?।\n]{0,40}\b(?:ho chuk|pack ho|dispatch ho)\w*|"
    r"\b(?:just|already|maine|humne|मैंने|हमने)\s+[^.;!?।\n]{0,60}"
    r"(?:transferred|sent|paid|deposited|bhej\s*di\w*|bhej chuk\w*|de diye|कर दिया|दे दिया|भेज\s*द(?:िया|ी|े)|जमा कर दिया)\b|"
    r"भेज द(?:िए|िया|ी) ह(?:ैं|ै)|bhej d(?:i|e|ye)\s*h(?:ai|ain)\b")
# What fraudsters do to other people, as an advisory or report describes it. Such a clause makes
# no payment request of the reader, so it names no payee.
REPORTED = re.compile(
    r"\b(?:fraudster\w*|scammer\w*|gang|cheat\w*|caller|impersonator\w*|miscreant\w*|thug\w*|they|"
    r"people|customers|consumers|citizens|victims?|users?|लोग|गिरोह|ठग\w*)\b[^.;!?।\n]{0,40}"
    r"\b(?:is|are|was|were|have|has|had)\s+(?:calling|asking|telling|sending|cheating|duping|running|"
    r"operating|targeting|using|demanding|threatening|posing|pretending|impersonating|instructing|"
    r"directing|forcing|making)\b", re.I)

SAFE = [
    ("official_channel", DEST_OFFICIAL),
    ("transaction_receipt",
     r"(debited|credited|withdrawn|paid to|received from|has (been )?(delivered|shipped|booked|processed|"
     r"credited|debited|renewed|received|cancelled)|order (id|#|no)|a/c\s{0,3}(no\.?)?\s{0,3}x*\d|"
     r"account\s*xx|salary[^.;!?।\n]{0,25}(credited|received|paid)|refund[^.;!?।\n]{0,30}processed|"
     r"(refund|payment|credit)[^.;!?।\n]{0,30}(has been |was |is )?(initiated|processed|completed)|"
     r"\breceipt\b|रसीद|acknowledgement|reference (number|no)|"
     r"(initiated|processed|completed)[^.;!?।\n]{0,30}(refund|credit)|will (credit|refund)|"
     r"ticket[^.;!?।\n]{0,25}confirmed|\bpnr\b|booking (is )?confirmed|"
     r"recharge[^.;!?।\n]{0,25}(successful|active|done)|is now active|(successfully|successful)[^.;!?।\n]{0,20}(done|active|completed)|"
     r"(टिकट|बुकिंग|ऑर्डर|रिचार्ज|रिफंड|वेतन)[^।;!?\n]{0,25}"
     r"(कन्फर्म|सफल|सक्रिय|आ गया|आ गई|जमा|प्राप्त|पहुंच)|पीएनआर|"
     r"(recharge|ticket|booking|order|refund|salary|payment)[^.;!?।\n]{0,30}"
     r"(ho gaya|ho gayi|aa gaya|aa gayi|jama hua|successful|credited)|"
     r"जमा हुआ|प्राप्त हुआ|नवीनीकरण|डिलीवर हो गया|डिलीवर हुआ|पहुंच गया|सफलतापूर्वक|स्वीकार कर लिया|वेतन|रिटर्न)"),
    ("otp_notification",
     r"((your|aapka|आपका)?\s*(otp|code|pin|password|कोड|ओटीपी|पिन)(\s+for[^.;!?।\n]{0,20})?\s{0,3}(is|है)?\s{0,3}[:#-]?\s{0,3}\d{4,8})"
     r"|(code\s{0,3}(is)?\s{0,3}\d{4,8})|(\d{4,8}\s*(is your|aapka)\s*(otp|code))|"
     r"(\d{4,8}\s*(is|है)\s*(your|aapka|आपका)?\s*(one[- ]?time (password|code)|otp|verification code))|"
     # "One Time Password (OTP) for SBI Internet Banking login is 840219"
     r"(\b(one[- ]?time (password|code)|otp|password|verification code|login code)\b[^.;!?।\n]{0,50}?"
     r"\b(?:is|:)\s*\d{4,8}\b)"),
    ("protective",
     r"(never|will not|won't|does not|doesn't|do not|don't)\s+(ask|asks|share|send|reply|call|"
     r"pay|transfer|deposit)\b|"
     r"no (payment|fee|charge|otp|pin|cvv|code|link|reply|deposit|action|shortlink|secret-code)"
     r"[^.;!?।\n]{0,40}(required|needed|due|asked|attached|necessary|is needed|request|collected)|"
     r"do not share|don't share|never share|share na karein|share mat karein|mat (bat|bhej)|"
     r"na (bhejein|bataen|karein)|न भेजें|न बताएं|मत बताएं|साझा न करें|नहीं मांगा|नहीं मांगेगा|"
     r"(needs|requires) no (code|payment|link|fee|otp|reply|pin)|"
     r"koi (secret )?code kisi ko mat|"
     r"works only at the keypad|"
     r"(कोई\s+)?(शुल्क|भुगतान|पिन|कोड|राशि|लिंक|फीस)[^।;!?\n]{0,45}"
     r"(नहीं चाहिए|नहीं लगेगा|नहीं लगती|की जरूरत नहीं|नहीं मांगा|नहीं है|नहीं)|"
     r"(fraud|scam|alert)[^.;!?।\n]{0,40}(never|do not|don't)\s+(ask|share|send)|"
     r"(agencies|banks|police|officials?)\s+(do not|don't|never)\s+ask"),
    ("opt_out", r"reply stop|opt out|unsubscribe"),
    ("notice",
     r"\b(appointment|scheduled|rescheduled|meeting|notice|reminder|admit card|result|interview|"
     r"application|shortlisted|portal|office|campus|school|college|policy|renewal|statement)\b|"
     r"(raffle|lucky draw|draw|contest|competition|fair)[^.;!?।\n]{0,60}"
     r"(community|school|college|hall|venue|neighbourhood|office|club)\b|"
     r"(सूचना|सूचि|बैठक|नोटिस|रिमाइंडर|पोर्टल|कार्यालय|विद्यालय|पॉलिसी|नवीनीकरण|बातचीत|"
     r"मुलाकात|सत्र|सभा|कार्यक्रम|समय तय)"),
    ("appointment_notice",
     r"\b(appointment|appointments|scheduled|rescheduled|consultation|follow[- ]?up|check[- ]?up|"
     r"delayed|running late|platform (changed|change)|gate (changed|change)|diversion|"
     r"out for delivery|ready for (pickup|collection)|delivery (attempt|update)|"
     r"cash on delivery|pay on delivery|pay (?:by|via|using) (?:cash|upi)|"
     r"collection|technician|sample|\blab\b|(?:book|confirm|schedule)\s+(?:hai|hain|ho (?:gaya|gayi|chuka|chuki)))\b|"
     r"(अपॉइंटमेंट|परामर्श|जांच|विलंब)"),
    # Consumer advice: read or ask for published charges before acting. A request that also pays
    # or hands over a secret sets a harmful mechanism first, so this only clears text with no ask.
    ("consumer_advice",
     r"(read|check|verify|compare|ask|confirm|understand|पढ़|जांच|पूछ|समझ)[^.;!?।\n]{0,40}"
     r"(terms|charges|fee|interest|credentials|registration|policy|premium|शुल्क|ब्याज|नियम|"
     r"शर्तें|पंजीकरण|पॉलिसी)[^.;!?।\n]{0,30}(before|first|in writing|लिखित|पहले|कर लें|करें)"
     r"|(terms|charges|fee|interest|शुल्क|ब्याज|शर्तें)[^.;!?।\n]{0,40}"
     r"(read|check|verify|ask|confirm|पढ़|जांच|पूछ|समझ)"),
    # A collect or payment request that is only *pending* and tells the reader to review it is an
    # app notification. Approving, accepting or authorising it is the harmful mechanism instead.
    ("collect_review",
     r"(collect|payment) request[^.;!?।\n]{0,50}(pending|received|waiting|review|check|verify)"
     r"[^.;!?।\n]{0,80}(app|bank|upi)"),
    # Warning or news framing: a regulator, police or awareness notice that names a scam technique.
    # A real demand sets a decisive mechanism first, so this clears only text with no ask.
    ("awareness",
     r"(warns?|warning|beware|caution|advisory|awareness)[^.;!?।\n]{0,80}"
     r"(scam|fraud|fake|fraudster|otp|pin|processing fee|payment|loan|kyc|safe account|video call)"
     # "Alert:" and "Notice:" count only next to a fraud word: a bank's own alert also says "KYC".
     r"|\b(alert|notice|bulletin)[^.;!?।\n]{0,60}"
     r"(scam|fraud\w*|fake|phishing|cheat\w*|duping|thug\w*|ठग\w*|धोखाधड़ी|साइबर सुरक्षा)"
     r"|\b(is|are|was|were)\s+(?:a\s+|an\s+)?(scam|scams|fraud|frauds|fake|fraudulent|phishing)\b"
     r"|(scam|fraud|fake|fraudster)[^.;!?।\n]{0,60}"
     r"(warns?|warning|beware|arrest\w*|bust\w*|detain\w*|advisory)"
     r"|(arrest\w*|bust\w*|detain\w*|convict\w*)[^.;!?।\n]{0,60}(scam|fraud|racket)"
     # A tip about what to do when a caller demands a secret or a fee.
     r"|(if|when|a caller|someone|fraudster|scammer)[^.;!?।\n]{0,60}"
     r"(asks?|demands?|requests?)[^.;!?।\n]{0,50}(otp|pin|password|code|money|fee)"
     r"[^.;!?।\n]{0,60}(hang up|report|do not|never|ignore)"),
    ("bill_notice",
     r"(bill|बिल)[^.;!?।\n]{0,40}(is )?(ready|due|generated|issued|reminder)|"
     r"amount due|due date|(देय तिथि|देय राशि|बिल तैयार)|bill (for|of)\b|"
     r"(प्रीमियम|बीमा|पॉलिसी|policy|premium)[^।.;!?\n]{0,25}(देय|due|renew)|"
     # a loan EMI or auto-debit reminder
     r"\b(?:emi|sip|installment|auto-?debit|standing instruction)\b|ऑटो-?डेबिट|अनुस्मारक"),
    ("promo",
     r"\b(sale|discount|% ?off|cashback|deal|coupon|offer|win up to|save up to|free trial)\b|"
     r"(छूट|ऑफर|कैशबैक)"),
    ("personal",
     r"(family note|good night|see you|call me|reach(ed)? home|lunch|dinner|ghar pahunch|khana)"),
]


def clean(text):
    """Undo cheap obfuscations a scam may use: zero-width joiners, full-width forms, spaced capitals."""
    s = unicodedata.normalize("NFKC", text)
    s = re.sub(r"[\u200b-\u200f\u2060\ufeff\u00ad]", "", s)
    s = re.sub(r"\b(?:[A-Z]\s){2,}[A-Z]\b", lambda m: m.group(0).replace(" ", ""), s)
    return re.sub(r"[^\S\r\n]+", " ", s)


def clauses(t):
    """Split on sentence punctuation; keep the text lowercased."""
    out, start = [], 0
    for m in re.finditer(r"(?<!\brs)(?<!\bno)(?<!\bref)(?<!\binr)(?<!\bmr)(?<!\bmrs)(?<!\bdr)(?<!\bmt)"
                        r"(?<!\bapprox)(?<!\bupto)(?<!\bacs)(?<!\bamt)[.!?।;](?=\s|$)|\n", t):
        if m.start() > start:
            out.append((start, t[start:m.start()]))
        start = m.end()
    if start < len(t):
        out.append((start, t[start:]))
    return out


def _negated(clause):
    return bool(NEG.search(clause))


def _matched(m, clause):
    """False when the matched request is itself negated ("do not share", "PIN mat bhejein")."""
    before, after = clause[:m.start()], clause[m.end():]
    if NEG_INSIDE.search(m.group()):
        return False
    if NEG_VERB.search(before[-80:]):
        return False
    m_after = NEG_AFTER.match(after.split(',', 1)[0])
    if m_after:
        tail = after[m_after.start():]
        conditional = re.search(r"\b(if|agar|unless|warna|otherwise)\b|नहीं\s*तो|nahi\s+toh", tail[:35], re.I) or \
            re.search(r"\b(if|agar|unless|warna|otherwise)\b|नहीं\s*तो|nahi\s+toh", clause[:m.end()][-70:], re.I)
        if not conditional:
            return False
    return True


def _clause_hit(pattern, t):
    """True when pattern matches a clause at a point that is not negated."""
    for _, c in clauses(t):
        # A negated greedy match can span a later, separate request. Retry from
        # the next character so the later request is still examined.
        pos = 0
        compiled = re.compile(pattern, re.I)
        while pos < len(c):
            m = compiled.search(c, pos)
            if not m:
                break
            if _matched(m, c):
                return True
            pos = m.start() + 1
    return False


# The text asks the reader to do something: an instruction to the reader, a demand for their
# details or an immediate payment. Scopes that must respect a negation are clause-scoped.
DIRECT_RAW = (
    r"\b(you|your|aap|aapka|आप|आपका)\b[^.;!?।\n]{0,40}"
    r"\b(must|need to|should|pay|send|transfer|share|click|install|download|call|verify|"
    r"update|deposit|invest)\b",
    r"(?:कृपया|ज़रा|जरा)\s+[^.;!?।\n]{0,40}(भेजें|भेजो|बताएं|बताओ|साझा|दें|भरें|करें)",
    r"\b(pay|send|transfer|share|deposit|invest)\s+(now|today|immediately|at once|"
    r"right away|turant|abhi)\b",
    r"\b(citizens|customers|people|all)\s+(must|should|need to)\s+"
    r"(pay|transfer|share|deposit|invest|click|install|download)\b")
DIRECT_SCOPED = (
    r"(?:^\s*|[,;:]\s*)(?:(?:now|then|please|kindly|pls|request you to|कृपया|ज़रा|जरा)\s*,?\s*)*"
    r"(?:pay|send|transfer|share|tell|give|provide|reply|forward|enter|type|submit|upload|dictate|click|install|download|verify|update|deposit|invest|call)\b",
    r"\b(?:please|kindly|pls)\s+(?:pay|send|transfer|share|tell|give|provide|reply|forward|enter|type|submit|upload|dictate|click|install|download|verify|update|deposit|invest|call)\b",
    DEMAND + r"[^.;!?।\n]{0,40}\b(?:your|aapka|आपका)\b[^.;!?।\n]{0,25}" + CREDS)


def _directs(t):
    """True when the text asks the reader to do something. Also used clause by clause, to bind a
    contact to the request that names it."""
    return (any(_any(pattern, t) for pattern in DIRECT_RAW)
            or any(_clause_hit(pattern, t) for pattern in DIRECT_SCOPED))


def _clause_find(pattern, t):
    for off, c in clauses(t):
        for m in re.finditer(pattern, c, re.I):
            if _matched(m, c):
                return c.strip(), off + m.start(), off + m.end()
    return None


def _any(pattern, t):
    return bool(re.search(pattern, t, re.I))


def hosts(t):
    out = []
    for m in URL_RE.finditer(t):
        raw = m.group(0).rstrip(".,;:)!?")
        u = raw if "://" in raw else "http://" + raw
        h = (urlparse(u).hostname or "").lower().strip(".")
        if h and h not in out:
            out.append(h)
    return out


def is_official(h):
    return h in OFFICIAL_DOMAINS or h.endswith(OFFICIAL_SUFFIXES) or any(
        h.endswith("." + d) for d in OFFICIAL_DOMAINS)


def host_risk(h):
    parts = h.split(".")
    if len(parts) < 2:
        return ""
    tld, label = parts[-1], parts[-2]
    if is_official(h):
        return ""
    if any(h == s or h.endswith("." + s) for s in SHORTENERS):
        return f"the domain {h} is a URL shortener that hides its destination"
    brand = next((b for b in RISKY_BRANDS if b in h), None)
    if brand and tld in RISKY_TLDS:
        return f"the domain {h} imitates '{brand}' on .{tld}"
    if brand and any("-" in p and brand in p for p in parts):
        return f"the domain {h} is a hyphenated lookalike of '{brand}'"
    if tld in RESERVED_TLDS:
        # RFC 2606 reserves these names: no real site, scam or genuine, uses them, so "common for
        # throwaway scam sites" would be a false claim. The link is still unverified.
        return f"the domain {h} is not an official site"
    if tld in RISKY_TLDS:
        return f"the domain {h} uses .{tld}, common for throwaway scam sites"
    if re.search(r"\d", label) and any(b in label.replace("0", "o") for b in RISKY_BRANDS):
        return f"the domain {h} swaps letters for digits to imitate a brand"
    if h.count("-") >= 2 or h.count(".") >= 4:
        return f"the domain {h} is unusually long or hyphenated"
    return ""


def analyze(text):
    """Return a dict of mechanism findings used by the decision layer."""
    t = clean(text).lower()
    orig = clean(text)
    a = {"text": t, "harm": [], "safe": [], "hosts": [], "risky": [], "official_host": False,
         "secret": False, "secret_share": False, "pay_to_receive": False, "pay_unverified": False,
         "collect": False, "remote": False, "crypto": False, "authority": False, "threat": False,
         "job_upfront": False, "prize_claim": False, "safe_account": False, "fee": False,
         "official_channel": False, "receipt": False, "otp_note": False, "protective": False,
         "notice": False, "promo": False, "bill": False, "appointment": False,
         "isolation": False, "secrecy": False, "new_contact": False, "dest_strong": False}

    hs = hosts(t)
    a["hosts"] = hs
    for h in hs:
        r = host_risk(h)
        if r:
            a["risky"].append(r)
        elif is_official(h):
            a["official_host"] = True
    for m in URL_RE.finditer(t):
        if re.match(r"-\w", t[m.end():m.end() + 2]):
            # "sanchar-verify.in-verify": letters run on past the domain ending and hide the address
            a["risky"].append("a link runs on past its domain ending, hiding where it really goes")

    for name, pat in SAFE:
        if _any(pat, t):
            a["safe"].append(name)
    if NAMED_APP.search(orig):
        a["safe"].append("official_channel")
    if _any(OWN_RECORD, t) and not _any(r"\b(wapas|return|refund|वापस|by mistake|galti se)\b", t):
        a["safe"].append("transaction_receipt")
    if _any(NO_HURRY, t):
        a["safe"].append("no_hurry")
    a["official_host"] = a["official_host"] and not a["risky"]
    a["official_channel"] = "official_channel" in a["safe"] or a["official_host"]
    a["receipt"] = "transaction_receipt" in a["safe"]
    a["otp_note"] = "otp_notification" in a["safe"]
    a["protective"] = "protective" in a["safe"]
    a["notice"] = "notice" in a["safe"]
    a["bill"] = "bill_notice" in a["safe"]
    a["appointment"] = "appointment_notice" in a["safe"]
    a["promo"] = "promo" in a["safe"]
    a["advice"] = "consumer_advice" in a["safe"]
    a["collect_review"] = "collect_review" in a["safe"]
    a["awareness"] = "awareness" in a["safe"]
    a["no_hurry"] = "no_hurry" in a["safe"]
    # A warning or news report names the criminals and what they do to third parties ("a gang is
    # calling people and asking them to transfer"). When the reader is not addressed and no
    # imperative asks them to act, the harmful wording is a description, not a demand.
    report_src = _any(r"\b(police|cyber ?cell|rbi|sebi|trai|cbi|court|bank|authority|authorities|"
                      r"advisory|warning|beware|awareness|news|fir|case|report|arrest\w*|bust\w*|detain\w*|"
                      r"पुलिस|साइबर|आरबीआई|अदालत|गिरफ्तार\w*)\b", t)
    third_actor = _any(r"\b(gang|fraudster\w*|scammer\w*|accused|cheat\w*|officer|agent|caller|"
                       r"man|woman|broker|advisor|they|them|people|"
                       r"citizens|customers|public|victims?|लोग|गिरोह|ठग\w*)\b", t)
    report_verb = _any(r"\b(is|are|was|were|has|have|had)\s+(calling|asking|telling|sending|cheating|"
                       r"duping|running|operating|targeting|using|demanding|threatening|posing|"
                       r"pretending|impersonating)\b", t) or _any(
        r"\b(arrested|busted|detained|convicted|booked|filed|asked|requested|demanded|told)\b", t)
    # A bank or police agent asking for a code is not, by itself, a news report.
    # Require an actual report frame or an explicitly named third-party audience.
    report_frame = _any(r"\b(warn\w*|beware|advisory|awareness|news|report\w*|"
                        r"arrest\w*|bust\w*|detain\w*|convict\w*|booked)\b|गिरफ्तार\w*", t)
    third_audience = _any(r"\b(victims?|customers|citizens|people|public)\b|लोग", t)
    a["report"] = bool(report_src and third_actor and report_verb and (report_frame or third_audience))
    a["reader_direct"] = _directs(t)
    a["isolation"] = _any(ISOLATION, t)
    a["secrecy"] = _any(SECRECY, t)
    a["new_contact"] = _any(NEW_CONTACT, t)

    sep = r"[^.;!?।\n]{0,60}?"
    risky_any = bool(a["risky"])
    phish_page = _clause_hit(r"(click|enter|login|log in|sign in|submit|verify|confirm|update|pay|share|scan)"
                             r"[^.;!?।\n]{0,40}(link|page|site|portal|here|below|unlock|account|kyc|otp|"
                             r"pin|reactivate|blocked|qr)", t) or \
        bool(re.search(r"(click|enter|login|log in|sign in|submit|verify|confirm|update|pay|share|scan)"
                       r"[^\n]{0,60}(https?://|www\.)", t, re.I))

    # A secret handed over by sharing/sending/telling is never legitimate, even when the message
    # claims an official app. Entering a code in the bank's own app can be; an official channel
    # explains that case only.
    # A delivery code shown in the sender's app and handed over in person to the delivery staff at
    # the door is how couriers confirm a drop. The scam pattern hands a bank code to a caller, a
    # chat or a number, so an in-person handover is the only share that is not a request.
    doorstep = (_any(r"\b(shown|displayed|visible|available)\b[^.;!?।\n]{0,50}\b(app|application)\b", t)
                and not _any(PHONE, t) and not _clause_hit(PRIVATE_CHANNEL, t))
    share_hit = any(not (doorstep and DOORSTEP_HANDOVER.search(clause)) and
                    (_clause_hit(SHARE + sep + CRED, clause) or _clause_hit(CRED + sep + SHARE, clause))
                    for _, clause in clauses(t))
    # An official channel explains entry only in the same clause; a separate
    # reassurance about the official app cannot clear an unrelated request.
    enter_hit = any(
        (_clause_hit(ENTER + sep + CREDS, clause) or _clause_hit(CREDS + sep + ENTER, clause))
        and not _any(DEST_OFFICIAL, clause)
        and not any(is_official(host) for host in hosts(clause))
        for _, clause in clauses(t)
    )
    if not share_hit and re.search(CREDS, t, re.I) and _clause_hit(
            SHARE + r"\s+(it|this|that|the (code|number|pin))", t):
        # "Your OTP is 123456. Share it with our agent." names the secret in one clause and
        # requests it by pronoun in the next; a bank never asks for either.
        share_hit = True
    read_code = bool(re.search(
        r"\b(read|speak|repeat|dictate)\b[^.;!?।\n]{0,40}\b(otp|code|pin|6[- ]?digit)\b"
        r"[^.;!?।\n]{0,40}\b(screen|phone|message|sms|app)\b", t, re.I))
    direct_share = share_hit
    share_hit = share_hit or (_clause_hit(DEMAND + r"[^.;!?।\n]{0,40}" + CREDS, t) or
                              _clause_hit(CREDS + r"[^.;!?।\n]{0,40}" + DEMAND, t))
    # "If a caller asks for an OTP, hang up and report it" and "callers pose as bank staff and ask
    # for OTP" describe the demand; neither asks the reader to hand a secret over. A direct
    # share/send request still fires. Only criminals are named here: "our officer asks for the
    # code" is a demand.
    hypothetical = bool(re.search(
        r"\b(if|when|a caller|callers|someone|fraudster|fraudsters|scammer|scammers|"
        r"cheats|conmen|thugs|miscreants)\b[^.;!?।\n]{0,60}"
        r"\b(asks?|demands?|requests?)\b[^.;!?।\n]{0,50}"
        r"(otp|pin|password|code)\b", t, re.I))
    # Report framing never clears a credential demand: scammers wrap requests in news-style text,
    # so a warning that quotes a demand is flagged rather than risk clearing a real one.
    if hypothetical and not direct_share and not read_code:
        # A third-party report can contain both a demand and its quoted action.
        share_hit = False
        enter_hit = False
        read_code = False
        direct_share = False
    a["secret_share"] = direct_share
    if share_hit or read_code or enter_hit:
        a["secret"] = True
        if a["isolation"] or a["secrecy"] or a["authority"]:
            a["harm"].append(("secret_request", "demands a PIN, OTP, password or account login and isolates the reader"))
        else:
            a["harm"].append(("secret_request", "asks you to share a PIN, OTP, card or account detail"))
    if risky_any and phish_page and (re.search(CRED, t, re.I) or
                                     _clause_hit(r"(account|kyc|otp|pin|unlock|verify|blocked|reactivate)", t)):
        a["harm"].append(("phish_link", "sends you to a lookalike page and asks you to act there"))
    # Identity papers sent into a personal chat or to an unknown link are what a KYC or loan scam
    # collects. Aadhaar/PAN are never needed inside WhatsApp or on a non-official page.
    ident_ask = _clause_hit(IDENT_ACT + r"[^.;!?।\n]{0,40}" + IDENT, t) or \
        _clause_hit(IDENT + r"[^.;!?।\n]{0,40}" + IDENT_ACT, t)
    # Bind the destination to the document request, not to a different sentence.
    id_channel = any(
        (_clause_hit(IDENT_ACT + r"[^.;!?।\n]{0,40}" + IDENT, clause) or
         _clause_hit(IDENT + r"[^.;!?।\n]{0,40}" + IDENT_ACT, clause))
        and (_clause_hit(PRIVATE_CHANNEL, clause) or
             ((hosts(clause) or _clause_hit(r"\b(link|लिंक|url)\b", clause)) and
              not (_any(DEST_OFFICIAL, clause) or
                   any(is_official(host) for host in hosts(clause)))))
        for _, clause in clauses(t)
    )
    # A private channel elsewhere in the message still receives the document unless the request
    # itself names an official channel ("upload in the official app").
    ident_official = any(
        (_clause_hit(IDENT_ACT + r"[^.;!?।\n]{0,40}" + IDENT, clause) or
         _clause_hit(IDENT + r"[^.;!?।\n]{0,40}" + IDENT_ACT, clause))
        and (_any(DEST_OFFICIAL, clause) or any(is_official(host) for host in hosts(clause)))
        for _, clause in clauses(t))
    id_channel = id_channel or (_clause_hit(PRIVATE_CHANNEL, t) and not ident_official)
    if ident_ask and _clause_hit(KYC_CONTEXT, t) and id_channel:
        a["harm"].append(("id_request", "asks you to send identity documents to a chat or link"))

    # Payment demands: price of receiving something, a named fee, or an explicit private payee.
    unmoney = _clause_hit(r"(?:" + PAY + r")[^.;!?।\n]{0,50}(?:" + MONEY + r")", t) or \
        _clause_hit(r"(?:" + MONEY + r")[^.;!?।\n]{0,50}(?:" + PAY + r")", t)
    fee = _clause_hit(FEE, t)
    pay = _clause_hit(PAY, t)
    a["fee"] = fee
    phone = PHONE
    phone_destination = any(
        (_clause_hit(r"\b(?:pay|send|transfer)\b", clause) and _any(phone, clause)) or
        _any(r"\b(?:to|on)\s+" + phone, clause)
        for _, clause in clauses(t)
    )
    # A threat followed by "call <mobile number>" sends the reader to a private number.
    threat_call = _clause_hit(THREAT, t) and _any(r"\b(?:call|contact|whatsapp|dial)\b[^.;!?।\n]{0,20}" + phone, t)
    a["dest_strong"] = _clause_hit(DEST_STRONG, t) or phone_destination or threat_call
    # An unrelated official-channel sentence cannot authorize a payment elsewhere, but a link or
    # number given in the very next sentence ("Use this link: ...") belongs to the payment.
    all_clauses = [clause for _, clause in clauses(t)]
    pay_idx = [i for i, clause in enumerate(all_clauses)
               if not REPORTED.search(clause) and
               (_clause_hit(PAY, clause) or (_clause_hit(DEMAND, clause) and _any(MONEY, clause)))]
    cont_idx = [i + 1 for i in pay_idx if i + 1 < len(all_clauses) and i + 1 not in pay_idx and
                (hosts(all_clauses[i + 1]) or _clause_hit(r"\blink\b", all_clauses[i + 1]) or
                 (_any(phone, all_clauses[i + 1]) and
                  _clause_hit(r"\b(send|pay|transfer|upi|gpay|phonepe|paytm)\b", all_clauses[i + 1])))]
    payment_clauses = [all_clauses[i] for i in sorted(set(pay_idx) | set(cont_idx))]
    payment_official = bool(payment_clauses) and all(
        _any(DEST_OFFICIAL, clause) or any(is_official(host) for host in hosts(clause))
        for clause in payment_clauses
    )
    payment_dest_strong = any(
        _any(DEST_STRONG, clause) or _any(phone, clause)
        for clause in payment_clauses
    ) or _any(r"\b(?:to|on)\s+" + phone, t)
    payment_personal = any(_clause_hit(DEST_PERSONAL, clause) for clause in payment_clauses)
    payment_risky = any(host_risk(host) for clause in payment_clauses for host in hosts(clause))
    payment_links = any(hosts(clause) or _clause_hit(r"\blink\b", clause)
                        for clause in payment_clauses)
    dest_staff = any(_clause_hit(DEST_STAFF, clause) for clause in payment_clauses)
    agent_pay = any(_clause_hit(r"(agent|officer|advisor|representative|staff)[’']?s?\s+"
                                r"(number|account|upi|vpa)", clause) for clause in payment_clauses)
    # A bill reminder that takes payment on the biller's own app or site ("pay on the Tata Power
    # app or tatapower.com") names a destination that is not a private payee, a bare "link" or a
    # lookalike host: a routine bill payment, not an unverified one.
    bill_own_site = a["bill"] and not payment_risky and \
        not any(_clause_hit(r"\blink\b", c) for c in payment_clauses) and \
        any(_any(r"\bapp\b", c) or any(not host_risk(h) for h in hosts(c)) for c in payment_clauses)
    if _clause_hit(PAY_TO_RECEIVE, t):
        a["pay_to_receive"] = True
        a["harm"].append(("pay_to_receive", "asks for a payment before a refund, prize or delivery is released"))
    elif pay and (fee or _clause_hit(AMOUNT, t) or agent_pay or (unmoney and payment_dest_strong)) and \
            (payment_dest_strong or payment_risky or not payment_official) and \
            (payment_personal or payment_risky or dest_staff or agent_pay
             or (fee and payment_links)
             or (payment_links and _clause_hit(UTILITY, t) and not bill_own_site)):
        a["pay_unverified"] = True
        a["harm"].append(("pay_unverified", "asks for a payment to a personal number, account or unverified link"))
    private_negated = _any(
        r"(do not|don't|never|no)\s+(transfer|send|pay|deposit)[^.;!?।\n]{0,30}"
        r"(personal|private|any)\s+(upi|account|number|wallet)", t)
    dept_pay = (_clause_hit(AUTHORITY, t) and pay and a["dest_strong"] and
                not a["official_channel"] and not private_negated and
                _clause_hit(r"\b(tax|duty|penalty|fine|arrears|outstanding)\b", t))
    if dept_pay and not a["pay_unverified"]:
        # A tax or penalty demand routed to a private UPI or account is not the department's portal.
        a["pay_unverified"] = True
        a["harm"].append(("pay_unverified", "asks for a payment to a personal number, account or unverified link"))
    collect_conditional = _clause_hit(
        r"(only after|after you|once you|before you|wait until|after the)[^.;!?।\n]{0,50}"
        r"(receive|deliver|check|verify|arrive|read|approv)", t)
    if _clause_hit(COLLECT, t) and _clause_hit(COLLECT_ACTION, t) and not collect_conditional:
        # "Approve the collect request only after the order arrives" is advice, not a push.
        a["collect"] = True
        a["harm"].append(("collect_request", "pushes you to approve a UPI collect or payment request"))
    if _clause_hit(QR, t) and unmoney and not payment_official:
        a["collect"] = True
        a["harm"].append(("qr_payment", "asks you to scan a QR code and approve a payment"))
    # Commas separate negated and affirmative instructions, while sentence splitting
    # preserves dots inside filenames and URLs. APK delivery may be described elsewhere.
    remote_parts = [part for _, sentence in clauses(t) for part in sentence.split(',')]
    install = any(_clause_hit(r"\b(install|download)\b", part) for part in remote_parts)
    apk_private = (_clause_hit(r"\b(apk|sideload|unknown sources?)\b", t) and
                   _clause_hit(PRIVATE_CHANNEL, t))
    for remote_clause in remote_parts:
        remote_negated = _any(
            r"(never|do not|don't|does not|doesn'?t|no)\s+(ask|asks|tell|tells|require|requires|request|"
            r"requests)\b[^.;!?।\n]{0,40}(install|download|remote|screen[- ]shar)", remote_clause) or _any(
            r"(anydesk|teamviewer|remote[- ]access|screen[- ]shar\w*)[^\n]{0,50}"
            r"(never|do not|don't)\s+(install|download|use|do that|allow|share)", remote_clause) or _any(
            r"(never|do not|don't)\s+(install|download|use)\b[^.;!?।\n]{0,40}"
            r"(anydesk|teamviewer|remote[- ]access|screen[- ]shar)", remote_clause)
        apk_install = (_clause_hit(r"\b(install|download)\b", remote_clause) and
                       _clause_hit(r"\b(apk|sideload|unknown sources?)\b", remote_clause))
        if (_clause_hit(REMOTE, remote_clause) or apk_install) and not remote_negated:
            generic_install = _clause_hit(r"\b(install|download)\b", remote_clause) and not _clause_hit(
                r"\b(anydesk|teamviewer|quicksupport|rustdesk|screen[- ]shar\w*|remote[- ]access "
                r"(software|app|tool)|remote app|remote support)\b", remote_clause)
            if not generic_install or hosts(remote_clause) or _clause_hit(
                PRIVATE_CHANNEL, remote_clause) or _clause_hit(r"\b(apk|sideload|unknown sources?)\b", remote_clause) or apk_private:
                a["remote"] = True
                break
    if install and apk_private:
        a["remote"] = True
    # An .apk file the reader is told to install is a side-loaded app in any language.
    if _any(r"\b[\w-]+\.apk\b", t) and _clause_hit(r"\b(install|download|इंस्टॉल|डाउनलोड|लगाएं|लगाओ)\b", t):
        a["remote"] = True
    if a["remote"]:
        a["harm"].append(("remote_access", "asks you to install an app or share your screen"))
    if _clause_hit(CRYPTO, t) and (pay or _clause_hit(r"(send|transfer|deposit|bhej\w*|भेजें)", t)):
        a["crypto"] = True
        a["harm"].append(("crypto_transfer", "asks you to move money into crypto"))
    # A warning that names a fake officer and tells the reader not to pay is describing the scam,
    # not making the demand. A scam keeps the payment instruction and omits the negation.
    fake_warning = (_any(r"\b(fake|fraudster|scammer|fraudulent|claiming to be|frauds?|scams?|beware|"
                         r"cheats?|duping|duped)\b", t) and
                    _any(r"\b(do not|don't|never)\s+(pay|send|transfer|share)\b|"
                         r"\b(report|hang up|ignore)\b", t))
    # "No agency ever asks citizens to transfer funds into a safe verification account": the negated
    # demand describes the scam; it does not make it. The negation itself is what must be found, so
    # raw search rather than the negation-aware clause hit.
    safe_account_negated = _any(
        r"(never|do not|don't|will not|won't)\s+(ask|tell|request|instruct|advise)?[^.;!?।\n]{0,30}"
        r"(transfer|move|send|deposit)[^.;!?।\n]{0,30}(safe|secure|temporary|audit)\s+(account|wallet)", t) or \
        _any(r"banks?\s+(never|do not|will not)\s+(ask|tell)[^.;!?।\n]{0,40}(transfer|move|send|deposit)", t) or \
        _any(r"\b(no|not|never|does not|do not|will not|won't|ever)\b[^.;!?।\n]{0,90}"
             r"\b(ask|asks|tell|tells|demand|demands|request|requests|instruct|instructs)\b"
             r"[^.;!?।\n]{0,60}\b(transfer|move|send|deposit)\b[^.;!?।\n]{0,50}"
             r"(safe|secure|temporary|audit|verification|government|rbi)\s+(account|wallet)", t)
    if _clause_hit(SAFE_ACCOUNT, t) and not safe_account_negated:
        named_safe = _clause_hit(r"(temporary|safe|secure|audit|verification|government|settlement|"
                                 r"escrow|सेफ|सरकारी|सत्यापन)\s+"
                                 r"(account|wallet|खाते|अकाउंट|खाता|account me)", t)
        if named_safe or a["authority"] or a["threat"] or a["isolation"] or a["secrecy"] or \
                a["dest_strong"] or a["new_contact"]:
            a["safe_account"] = True
            a["harm"].append(("safe_account", "asks you to move funds to a 'safe' account"))
    if _clause_hit(AUTHORITY, t) and _clause_hit(AUTHORITY_ACT, t) and not fake_warning and \
            (pay or a["secret"] or _clause_hit(VIDEO, t) or a["isolation"] or a["secrecy"] or
             _clause_hit(MONEY_MOVE, t) or
             _clause_hit(r"(join the call|call now|transfer|तुरंत|भुगतान|ट्रांसफर|वीडियो कॉल)", t)):
        a["authority"] = True
        a["harm"].append(("authority_threat", "poses as police, customs or a regulator and demands action"))
    elif _clause_hit(AUTHORITY, t) and (a["isolation"] or a["secrecy"]) and unmoney and not fake_warning:
        # Reported "digital arrest": an officer on a video call isolates the reader and asks for money.
        a["authority"] = True
        a["harm"].append(("authority_threat", "poses as police, customs or a regulator and demands action"))
    if _clause_hit(THREAT, t):
        a["threat"] = True
        # The harm name stays block_threat (the decision rules are unchanged); only the reader-facing
        # line says which threat it is, so a blackmail message is not described as account blocking.
        a["harm"].append(("block_threat", "threatens to block, cut or freeze an account, SIM or connection"
                          if _clause_hit(THREAT_BLOCK, t) else EXPOSE_DESC))
    the_job = _clause_hit(JOB, t) or _clause_hit(LOAN, t)
    # A notice, alert or advisory that hands the reader a contact of its own is the spoofed-advisory
    # pattern: a mobile number, a chat, or a link that imitates or hides its destination. A genuine
    # one points at an official app or site, a short code or a toll-free line instead. Words about
    # the "official app" excuse a plain link in a routine notice; an advisory that also sends the
    # reader to a site of its own is a spoof whatever it calls that site.
    advisory = a["awareness"] or a.get("report")
    foreign = any(not is_official(h) for h in hs)
    directs = [clause for _, clause in clauses(t) if _directs(clause)]
    # A chat or a plain link is the sender's own contact only where a clause that asks the reader
    # to act names it: "over WhatsApp" inside a warning describes the fraud, and a link placed after
    # the advice ("Advisory: cert-in.org.in") is a citation. A lookalike link or a mobile number is
    # a contact wherever it stands: a genuine advisory never prints a mobile number.
    a["own_contact"] = bool(
        a["risky"] or _any(PHONE, t)
        or any(_clause_hit(CHAT_CONTACT, clause) or any(not is_official(h) for h in hosts(clause))
               for clause in directs)
        or (foreign and a["reader_direct"] and _any(URGENCY, t)))
    a["self_check"] = bool(SELF_CHECK.search(t))
    if (a["notice"] or advisory or a["advice"]) and a["own_contact"] and \
            not (a["official_channel"] and not advisory):
        a["harm"].append(("notice_contact", "is a notice or advisory that gives its own number, chat or link to act on"))
    if (the_job and (_clause_hit(UPFRONT, t) or _clause_hit(BUY_REFUND, t) or
                     (pay and fee and not a["official_channel"])) and not fake_warning):
        a["job_upfront"] = True
        a["harm"].append(("job_upfront", "offers a job or loan that needs an upfront fee or deposit"))
    elif (the_job and _clause_hit(r"(daily|per day|roz|रोज|turant|immediately|whatsapp|telegram)", t)
          and not (a["awareness"] and not (pay or fee)) and not fake_warning):
        # "Beware of fake job offers on Telegram" names a chat channel without offering anything.
        a["job_upfront"] = True
        a["harm"].append(("job_offer", "offers easy daily income through a personal chat channel"))
    if _clause_hit(r"(private (recording|video|photo)|intimate|morphed|nude)", t) and \
            _clause_hit(r"(post|publish|leak|share|send to|viral|bhej\w*|भेज|वायरल)", t):
        a["sextortion"] = True
        a["harm"].append(("sextortion", "threatens to publish private material unless you pay"))
    if _clause_hit(r"(gift (card|voucher)|voucher|google play|amazon (pay )?card)", t) and \
            _clause_hit(r"\b(buy|purchase|get)\b", t) and \
            _clause_hit(r"\b(send|share|forward|read|code)\b", t) and (a["secrecy"] or a["new_contact"] or
                 _clause_hit(r"\b(urgent|urgently|immediately|right away|asap|turant|jaldi|impersonat\w*|kyc|bank|manager|agent)\b|\b(?:unknown|new|stranger)\s+(?:contact|number|person)\b|तुरंत|जल्दी", t)):
        a["harm"].append(("gift_card", "asks you to buy gift vouchers and hand over the codes"))
    extort = (_clause_hit(r"(we have|we'?ve got|kidnap\w*|abduct\w*)[^.;!?।\n]{0,30}"
                          r"(your |the )?(family|child|son|daughter|wife|husband|kid)\b", t)
              or _clause_hit(r"\b(pay|transfer|send|bhej\w*)[^.;!?।\n]{0,20}or\b"
                             r"[^.;!?।\n]{0,30}(harm|hurt|kill|leak)\b", t))
    if extort and (pay or _clause_hit(DEMAND, t)):
        a["harm"].append(("extortion", "threatens the reader or family to force a payment"))
    descriptive_past = bool(
        not a["reader_direct"] and
        not _clause_hit(r"\b(pay|send|transfer|deposit)\b[^.;!?।\n]{0,40}"
                        r"\b(fee|tax|amount|account|wallet|upi|number|link)\b", t) and
        _any(r"\b(fraudsters?|scammers?|gang|company|firm|broker|advisor|agent|accused|"
             r"victims?|investors?|people)\b[^.;!?।\n]{0,70}"
             r"\b(promised|collected|duped|cheated|defrauded|invested|paid|lost)\b", t))
    invest_negated = _any(r"\b(no|not|never)\s+[^.;!?।\n]{0,25}(guaranteed|assured|fixed)\b|"
                          r"\b(guarantee\w*|assured|fixed returns?)\s+(is|are)\s+not\b|\bnot\s+guaranteed\b", t)
    if _clause_hit(INVEST, t) and _clause_hit(INVEST_ACT, t) and not a["official_channel"] and \
            not invest_negated and not descriptive_past and \
            not (a["awareness"] and not a["reader_direct"]):
        # An advisory that mentions guaranteed returns is naming the scam, not offering one.
        a["harm"].append(("investment", "promises guaranteed or doubled returns and asks you to deposit funds"))
    prize_negated = (_any(r"\b(no|not|never|without)\b[^.;!?।\n]{0,30}"
                          r"(fee|payment|charge|deposit|voucher|code|tax)[^.;!?।\n]{0,25}"
                          r"(needed|required|charged|necessary|asked)", t) or
                     _any(r"\b(never|do not|don't)\s+(pay|buy|send)[^.;!?।\n]{0,30}"
                          r"(fee|voucher|code|deposit|charge)", t))
    prize_ask = _clause_hit(r"\b(send|share|give|provide|buy|purchase|pay|transfer|deposit)\b", t)
    # A genuine prize announcement can say "claim it at the office". Only a fee, an unknown
    # payee, a personal-detail request, a link or a voucher/tax ask turns it into a claim scam.
    prize_risk = (a["fee"] or a["dest_strong"] or risky_any or ident_ask or
                  _clause_hit(r"\b(send|share|give|buy|purchase|pay|transfer|deposit)\b", t) or
                  _any(r"\b(tax|duty|processing|registration|voucher|gift card|code)\b", t))
    if _clause_hit(PRIZE, t) and _clause_hit(PRIZE_ACT, t) and prize_risk and \
            not descriptive_past and not (prize_negated and not prize_ask):
        # A real IPO or prize notice can ask for a payment on the bank's own app; only a
        # private payee, an unknown link or an identity request turns it into a claim scam.
        reward_notice = a["official_channel"] and not (risky_any or a["dest_strong"] or
                                                       ident_ask or _clause_hit(PRIVATE_CHANNEL, t))
        if not reward_notice:
            a["prize_claim"] = True
            a["harm"].append(("prize_claim", "promises a prize that needs a fee or personal details to claim"))
    # A relative or colleague on a new number, unavailable by voice, asking for money to a third
    # party while the family stays uninformed.
    if unmoney and a["dest_strong"] and (a["new_contact"] or a["secrecy"]):
        a["impersonation"] = True
        a["harm"].append(("impersonation", "poses as a relative or colleague and wants money sent to a third party"))
    # Group MONEY here: as a bare alternation it binds the suffix to its last branch only, so a
    # lone amount word counted as a demand pair and forced a private-payee alarm.
    demand_money = _clause_hit(DEMAND + r"[^.;!?।\n]{0,30}(?:" + MONEY + r")", t) or \
        _clause_hit(r"(?:" + MONEY + r")[^.;!?।\n]{0,30}" + DEMAND, t)
    if payment_dest_strong and (demand_money or (unmoney and (fee or a["threat"])) or (pay and a["pay_unverified"])):
        a["pay_unverified"] = True
        if ("payment_request_private", "asks for money to a private account or personal number") not in a["harm"]:
            a["harm"].append(("payment_request_private", "asks for money to a private account or personal number"))

    a["request_cues"] = bool(
        _clause_hit(r"\b(install|download|sideload)\b", t) or
        ((_clause_hit(r"\b(buy|purchase|send|share|forward|provide)\b", t) or
          _clause_hit(DEMAND + r"|\b(?:require|requires|need|needs)\b", t)) and
         _any(r"\b(gift cards?|vouchers?|codes?)\b", t)) or
        _clause_hit(r"\b(pay|transfer|deposit|remit|recharge)\b|(?:भुगतान|जमा|ट्रांसफर)" + _NOT_PERFECTIVE, t) or
        (pay and (_any(MONEY, t) or _any(AMOUNT, t))) or
        a["secret"] or share_hit or enter_hit or
        _clause_hit(ENTER + sep + CRED, t) or _clause_hit(CRED + sep + ENTER, t) or
        _clause_hit(DEMAND + sep + CRED, t)
    )
    # Evidence texts are deduplicated in order.
    return a


DECISIVE = {"secret_request", "pay_to_receive", "collect_request", "qr_payment", "remote_access",
            "crypto_transfer", "safe_account", "authority_threat", "job_upfront", "prize_claim",
            "investment", "id_request",
            "sextortion", "phish_link", "impersonation", "payment_request_private", "notice_contact",
            "gift_card", "extortion"}


SELF_BLOCK = re.compile(
    r"\b(?:if (?:it |this )?(?:was |is )?(?:not |never )(?:you|done by you|done|initiated by you|"
    r"requested by you|attempted by you|authori[sz]ed)|if (?:it |this )?(?:was |is )?unauthori[sz]ed|"
    r"if you did not|if you didn'?t|not done by you|agar aapne nahi kiya|यदि आपने नहीं)\b"
    r"[^.;!?।\n]{0,30}\b(?:block|freeze|disable|lock|hotlist|turn off)\b[^.;!?।\n]{0,20}"
    r"\b(?:card|upi|account|access)\b"
    r"(?:[^.;!?।\n]{0,40}\b(?:in|via|from|using|on|at)\b[^.;!?।\n]{0,40}"
    r"\b(?:app|yono|imobile|net ?banking|website)\b)?", re.I)
PASSIVE_THREAT = re.compile(r"\b(?:will be|would be|is being|ho jayega|ho jaega|हो जाएगा)\b[^.;!?।\n]{0,20}"
                                r"\b(?:blocked|suspended|frozen|closed|band|बंद)", re.I)
# A mobile number: ten digits starting 6-9 (with an optional +91 or 0) that may be split by spaces or
# punctuation ("98,76543210"), or written masked ("98XXXXXX66"). A bank's own alert never needs the
# reader to call a mobile; reference numbers, amounts, short codes and toll-free lines do not
# have this shape.
CONTACT_NUMBER = re.compile(
    r"(?<!\w)(?:\+?91[\s-]?|0[\s-]?)?[6-9]\d(?:[\s.,/()\u2013\u2014-]{0,2}\d){8}(?!\w)"
    r"|(?<!\w)[6-9]\d?[xX×*]{4,6}\d{2,3}(?!\w)")


OTHER_CONTACT = re.compile(r"whatsapp|telegram|wa\.me|\bt\.me\b|@\w|\(at\)|\[\.\]|\bupi\b|\bvpa\b", re.I)


def _other_contact(a):
    """A contact besides the official channel: a link to a site that is not the organisation's
    own, a mobile number, a chat handle or a UPI ID."""
    text = a.get("text", "")
    return bool(any(not is_official(h) for h in a["hosts"]) or CONTACT_NUMBER.search(text)
                or OTHER_CONTACT.search(text))


def _self_block(text):
    """A bank alert's own 'if not you, block your card in the app', with no threat or contact number."""
    return bool(SELF_BLOCK.search(text)) and not PASSIVE_THREAT.search(text) and not CONTACT_NUMBER.search(text)


# A warning segment states what the sender will never do or what the reader must never do: a negated
# mention of a secret, payment, app or link ("RBI never asks for your OTP", "kabhi AnyDesk install na
# karein", "OTP kisi se share mat karein"). A negated order with no such object ("do not tell your
# family", "vakil se sampark na karein") is a scam's isolation cue and stays, and so does a
# conditional threat ("agar payment nahi hua toh..."). A segment that orders the reader, threatens
# them or makes an exception ("except our executive") is never a warning. Segments are clauses split
# at ", ", dashes, contrast words and connectors before an order, so a negation reaches only its own
# segment ("don't panic, just share the OTP" keeps "just share the OTP"). Self-check lead-ins and
# doorstep handovers were tried and dropped: they added little and each opened ways to hide a demand
# (PR #48 review). Hypothetical callers came back later in a narrow form (_hypothetical_warning). A report that quotes what fraudsters asked for is not
# a warning segment: by controller decision a quoted credential demand stays flagged.
SEG_SPLIT = re.compile(r",\s|:\s|[–—]|\s-\s|\b(?:but|instead|just|however|lekin|balki|bas|sirf)\b|"
                       r"(?:^|\s)(?:लेकिन|बल्कि|बस|सिर्फ़|सिर्फ)(?=\s|$)", re.I)
_SEG_NEG = re.compile(r"\b(?:never|not|no|no one|nobody|don'?t|doesn'?t|won'?t|cannot|can'?t|kabhi|kabhee|"
                      r"nahi|nahin|mat|na)\b|n't\b|(?:^|[\s,;:])(?:कभी|नहीं|न|ना|मत)(?=[\s,;:।]|$)", re.I)
_SEG_PROTECTED = re.compile(
    r"\b(?:otp|pin|cvv|password|passcode|card|bank details|account details|upi|link|links|url|app|apps|"
    r"apk|anydesk|teamviewer|quicksupport|screen[- ]?shar\w*|remote|qr|collect|payment|pay|money|paise|"
    r"paisa|fee|fees|charges?|transfer|kyc|aadhaar|aadhar|details|code)\b|"
    r"ओटीपी|पिन|पासवर्ड|कार्ड|लिंक|ऐप|पैसे|पैसा|भुगतान|शुल्क|यूपीआई|क्यूआर|केवाईसी|आधार|विवरण|कोड", re.I)
_SEG_CONDITION = re.compile(r"\b(?:if|agar|unless|warna|otherwise|toh|varna)\b|(?:^|\s)(?:तो|वरना|अगर|यदि)(?=\s|$)", re.I)
# A short segment with an order in it ("pay now", "turant paise bhejein") is a request of its own.
_SEG_COMMAND = re.compile(r"\b(?:pay|send|share|transfer|tell|give|click|call|install|download|enter|type|"
                          r"forward|deposit|scan|approve|reply|bhej\w*|kar[oe]\w*|de\s?d[oe]|bata\w*|daal\w*)\b|"
                          r"करें|करो|भेजें|भेजो|दें|दो|बताएं|बताओ|डालें", re.I)
# An order to hand over, pay, send or install. Outside a warning segment it blocks clearing.
_RISKY_COMMAND = re.compile(
    r"\b(?:share|sharing|send|sending|tell|telling|give|giving|forward|transfer|move|pay|deposit|install|download|"
    r"approve|accept|authori[sz]e|scan|enter|type|reply|upload|dictate|read|provide|fill|buy|purchase|"
    r"hand(?:ing)? over|bhej\w*|bata\w*|de\s?d[oe]|de\s+(?:dijiye|dein|dena|do)|dijiye|dijiyega|dena hoga|dena hai|daal\w*|"
    r"bhar(?:o|ein|en|iye|dein|do)|jama)\b|भेजें|भेजो|भेजिए|भेजिये|भेज दें|बताएं|बताओ|बता दें|बता देना|बताइए|"
    r"दें|दो|दीजिए|दीजिये|दे दें|दे देना|देना होगा|देना|डालें|भरें|भरिए|जमा" + _NOT_PERFECTIVE + r"|रिचार्ज|इंस्टॉल", re.I)
# A verb in its oblique infinitive ("scan karne ki zaroorat nahi", "bhejne se pehle") names an action;
# it does not order one.
_INFINITIVE_AFTER = re.compile(r"^\s*(?:kar(?:ne|na)|करने|करना)\b|^(?:ne|na)\b", re.I)
_NEG_NEAR_BEFORE = re.compile(r"(?:\b(?:never|not|no|don'?t|do not|does not|doesn'?t|won'?t|cannot|can'?t|"
                              r"no need to|na|mat|nahi|nahin)|n't|(?:^|\s)(?:न|मत|नहीं|ना))\s+(?:\S+\s+){0,2}$|"
                              # "will not ask you to forward it", "never asks customers to share"
                              r"\b(?:never|not|n't|no)\s+(?:\S+\s+)?(?:ask|asks|request|requests|tell|tells|require|"
                              r"requires|want|wants)\s+(?:\S+\s+){0,2}to\s+$", re.I)
_NEG_NEAR_AFTER = re.compile(r"^\s*(?:\S+\s+){0,2}?(?:na|mat|nahi|nahin|not|never)\b|"
                             r"^\s*(?:\S+\s+){0,2}?(?:न|मत|नहीं|ना)(?=[\s,;:।]|$)", re.I)
_ATTENTION = re.compile(r"ध्यान दें|dhyan d\w+", re.I)
_LIST_TAIL = re.compile(r"^\s*(?:or|and|nor|ya|aur|या|और|एवं|तथा)(?=\s|$)", re.I)


# A new order joined by a connector ("and send", "please share", "then dictate") is a segment of its own.
_AND_ORDER = re.compile(r"\s(?:and|aur|और|then|please|kindly|pls|now|so|phir|abhi|turant|instead|simply|just)\s+"
                        r"(?:then\s+|please\s+|kindly\s+|just\s+|simply\s+)?(?=(?:share|send|tell|give|forward|"
                        r"transfer|move|pay|deposit|install|download|approve|accept|authori[sz]e|scan|enter|type|"
                        r"reply|upload|dictate|read|provide|buy|hand)\b)", re.I)


# A negation that encourages ("don't hesitate to share", "why not share") is an order.
_AFFIRM = re.compile(r"\b(?:don'?t|do not|never|dont)\s+hesitate\s+to\b|\bwhy not\b|\bno harm in\b|"
                     r"\bfeel free to\b|\bno problem (?:in|to)\b", re.I)


def _ordered(seg, threat=True):
    """The segment itself orders the reader to hand over, pay, send or install, or threatens them:
    "share the OTP with our officer", "koi bhi OTP humein bhejein". An order counts unless a negation
    sits within two words of the verb ("never share", "share mat karein", "install na karein"), it
    continues a negated list ("never share your OTP or install AnyDesk"), or the verb is an oblique
    infinitive ("scan karne ki zaroorat nahi")."""
    if threat and _threatens(seg):
        return True
    text = _AFFIRM.sub(" ", _ATTENTION.sub(" ", seg))
    negated_before = False
    for m in _RISKY_COMMAND.finditer(text):
        before, after = text[:m.start()], text[m.end():]
        if _INFINITIVE_AFTER.match(after) or re.search(r"[a-z]ne$", m.group(), re.I):
            continue
        if _NEG_NEAR_BEFORE.search(before) or _NEG_NEAR_AFTER.match(after) or \
                (negated_before and re.search(r"(?:\b(?:or|nor|ya)|या)\s+(?:\S+\s+)?$", before, re.I)):
            negated_before = True
            continue
        return True
    return False


def _threatens(seg, imperative=True):
    """A threat to the reader. With imperative=False the bare "block the card" wording of THREAT is not
    counted: in a self-check it is the reader's own remedy, while "will be blocked", "band ho jayega",
    a penalty or an FIR still are threats."""
    return bool((imperative and _clause_hit(THREAT, seg)) or _clause_hit(BLOCK_FUTURE, seg)
                or PASSIVE_THREAT.search(seg) or _clause_hit(_OTHER_THREAT, seg) or re.search(r"\bFIR\b", seg))


_OTHER_THREAT = (r"\b(?:penalty|fine of|jurmana|arrest\w*|legal action|forfeit\w*|seiz\w*|warrant)\b|"
                 r"जुर्माना|गिरफ्तार|कानूनी कार्रवाई|एफआईआर")


# "Never share your OTP with anyone except our executive" turns the warning into a request.
_EXCEPT = re.compile(r"\b(?:except|other than|apart from|siwa|sivay|siway|ke alawa|ke alava)\b|सिवाय|के अलावा|को छोड़कर", re.I)


def _warning_segment(seg):
    if _EXCEPT.search(seg) or _AFFIRM.search(seg) or _ordered(seg):
        return False
    return bool(_SEG_NEG.search(seg) and _SEG_PROTECTED.search(seg) and not _SEG_CONDITION.search(seg))


def _segments(clause):
    """(start, end) spans of a clause's segments. A short list item ("card CVV", "or OTP") stays with
    the segment before it, so a negation covers the whole list it heads. A tail with an order or a
    negation of its own ("and share your OTP", "not your family") is a segment of its own."""
    cuts = [0] + [m.end() for m in SEG_SPLIT.finditer(clause)]
    cuts += [m.end() for m in re.finditer(r"\s(?:और|aur)\s", clause)]
    cuts += [m.start() + 1 for m in _AND_ORDER.finditer(clause)]
    cuts = sorted(set(cuts)) + [len(clause)]
    spans = []
    for a, b in zip(cuts, cuts[1:]):
        if not clause[a:b].strip():
            continue
        if spans and not _SEG_COMMAND.search(clause[a:b]) and not _SEG_NEG.search(clause[a:b]) and \
                (_LIST_TAIL.match(clause[a:b]) or len(clause[a:b].split()) <= 3):
            spans[-1] = (spans[-1][0], b)
        else:
            spans.append((a, b))
    return spans


# A family or friend warning about a hypothetical caller: "if anyone calls asking for an OTP, hang up",
# "agar koi OTP maange to phone kaat dena", "अगर कोई ओटीपी मांगे तो फोन काट देना". PR #48 dropped a
# broad version of this because a demand could hide behind the condition. This one is narrow: the
# condition names an unknown third party (anyone, someone, koi, कोई), and the same clause tells the
# reader to protect themselves (hang up, disconnect, ignore, block or report the caller, or not to
# share). The clause is never a warning if, once the protective words are removed, it still orders the
# reader to hand over, pay, send or install, names a channel to contact, threatens after the
# condition, or makes an exception. A contact anywhere in the message still blocks clearing
# (_warning_only), so "hang up and call me on 98..." stays flagged.
_HYPO_CALLER = re.compile(
    r"\b(?:if|in case|whenever|when)\s+(?:any(?:one|body)|some(?:one|body)|a (?:stranger|caller)|"
    r"any (?:caller|person|stranger|unknown (?:caller|number|person)))\b|"
    r"\b(?:agar|jab|yadi)\s+(?:koi|kisi)\b|(?:^|\s)(?:अगर|यदि|जब)\s+(?:कोई|किसी)(?=\s|$)", re.I)
_HYPO_PROTECT = re.compile(
    r"\b(?:hang up|disconnect\w*|cut the call|end the call|put the phone down|ignore (?:it|them|the call|"
    r"the message|such calls)|block (?:the|that) (?:number|caller)|report (?:it|them|the number)|"
    r"(?:do not|don't|never) (?:share|give|tell|say|reply|answer|send)\b[^.;!?।\n]{0,30}|"
    r"phone (?:kaat|rakh) (?:do|dena|dein|dijiye)|call (?:kaat|cut) (?:do|dena|kar do|kar dena)|"
    r"kuch (?:bhi )?mat (?:batana|bolna|dena)|mat (?:batana|dena|bolna|bhejna)|ignore kar\w*|block kar\w*)\b|"
    r"(?:फोन|फ़ोन|कॉल)\s*(?:तुरंत\s*)?(?:काट|रख)\s*(?:देना|दें|दीजिए|दो)|कुछ\s*(?:भी\s*)?मत\s*(?:बताना|बोलना|देना)|"
    r"मत\s*(?:बताना|देना|भेजना)|(?:न|ना)\s*(?:बताएं|बताना|दें|देना|भेजें)|मना\s*कर\s*(?:देना|दें|दो)|"
    r"नंबर\s*ब्लॉक", re.I)
_HYPO_CONTACT = re.compile(r"\b(?:call|contact|visit|click|open|message|whatsapp|reach|dial|tap|go to)\b|"
                           r"संपर्क|कॉल\s*कर|फोन\s*कर|क्लिक", re.I)


# Hindi and Hinglish put the verb last, so one negated ask-verb at the end covers the whole list before
# it: "एसबीआई कभी भी कॉल, एसएमएस या लिंक के जरिए केवाईसी, ओटीपी, सीवीवी या यूपीआई पिन नहीं मांगता",
# "bank kabhi OTP, PIN ya CVV nahi maangta". Splitting at the commas would leave the list items outside
# the negation. Such a clause is one warning segment when it also passes _warning_segment's tests.
_VERB_FINAL_NEG = re.compile(
    r"(?:नहीं|कभी\s+नहीं|न)\s*(?:मांग|माँग|पूछ)(?:ता|ती|ते|ेगा|ेगी|ेंगे|े)\s*(?:है|हैं|था|थे)?\s*$|"
    r"\b(?:nahi|nahin|kabhi nahi|na)\s+(?:maang|mang|pooch|puchh?)(?:ta|ti|te|ega|egi|enge|e)\s*(?:hai|hain)?\s*$",
    re.I)


def _verb_final_warning(clause):
    c = clause.strip().rstrip("।.!")
    return bool(_VERB_FINAL_NEG.search(c) and _SEG_PROTECTED.search(c) and not _EXCEPT.search(c)
                and not _AFFIRM.search(c) and not _SEG_CONDITION.search(c) and not _ordered(c))


def _hypothetical_warning(clause):
    m = _HYPO_CALLER.search(clause)
    if not m or _EXCEPT.search(clause) or _AFFIRM.search(clause):
        return False
    after = clause[m.end():]
    prot = list(_HYPO_PROTECT.finditer(after))
    if not prot:
        return False
    # "don't disconnect, give them the code" negates the protection itself: never a warning. An earlier
    # protective phrase ("kuch mat batana, phone kaat dena") is not a negation of the next one.
    if any(_NEG_NEAR_BEFORE.search(_HYPO_PROTECT.sub(" ", after[:p.start()])) for p in prot):
        return False
    # Words after the first protective phrase are the reader's instruction: nothing there may name a
    # channel or threaten, and nothing may order the reader to hand over, pay, send or install. The
    # condition describes the caller ("asking for", "sending a link"), so its -ing forms are not
    # orders, but a bare order there ("if anyone calls, share the OTP") still counts.
    tail = _HYPO_PROTECT.sub(" ", after[prot[0].start():])
    if _HYPO_CONTACT.search(tail) or _threatens(tail):
        return False
    parts = re.split(r"(,\s|[–—]|\s-\s)", after[:prot[0].start()], maxsplit=1)
    condition = re.sub(r"\b[a-z]+ing\b", " ", parts[0], flags=re.I) + "".join(parts[1:])
    return not _ordered(" ".join((clause[:m.start()], condition, tail)), threat=False)


def request_text(text):
    """The text with warning segments blanked out in place: what the message actually asks of the
    reader. Everything else keeps its original wording and punctuation."""
    drop = []
    for off, clause in clauses(text):
        if _hypothetical_warning(clause) or _verb_final_warning(clause):
            drop.append((off, off + len(clause)))
            continue
        for a, b in _segments(clause):
            if _warning_segment(clause[a:b]):
                drop.append((off + a, off + b))
    out, last = [], 0
    for a, b in drop:
        out.append(text[last:a])
        last = b
    out.append(text[last:])
    return " ".join("".join(out).split())


# Only these mechanisms can be explained away by warning context: they are what genuine OTP messages
# and advisories mention. A payment, transfer, prize, job, investment or authority
# demand is never cleared by surrounding warnings.
CLEARABLE = {"secret_request", "remote_access", "qr_payment", "collect_request"}


def _warning_only(a):
    """True when every harmful mechanism sits in a warning segment and the message gives no
    contact of its own: a genuine advisory, self-check alert or doorstep OTP. A spoofed advisory
    always hands the reader a number, chat handle or link somewhere, so it is never cleared here."""
    if not a["harm"] or a["own_contact"] or a["risky"] or _contact_anywhere(a):
        return False
    if not {n for n, _ in a["harm"]} <= CLEARABLE:
        return False
    rest = request_text(a.get("text", ""))
    if _ordered(rest):
        # Something outside the warnings still tells the reader to hand over, pay, send or install
        # ("Never share your PIN. Share it with our officer"): never cleared, whatever re-analysis says.
        return False
    if not rest.strip():
        return True
    b = analyze(rest)
    return not (b["harm"] or b["threat"] or b["request_cues"])



# A direct order to pay, recharge or deposit ("pehle 500 rupaye recharge karein", "pay Rs 99 now").
PAY_COMMAND = (r"\b(?:pay|recharge|deposit|transfer|top[- ]?up)\b[^.;!?।\n]{0,40}"
               r"(?:rs\.?|inr|₹|rupees|\d)|(?:₹|rs\.?|inr)\s?[\d,]+[^.;!?।\n]{0,30}\b(?:pay|recharge|deposit|"
               r"transfer|bhej\w*|jama)\b|(?:रिचार्ज|भुगतान|जमा|भेज)\S*\s*(?:करें|करो|कीजिए|कीजिये|दें|दो)|"
               r"\b(?:recharge|payment|pay|jama|bhej)\w*\s+(?:karo|karein|karen|kare|kijiye|do|dein|dijiye)\b")
# A threat in any word order: "account band ho jayega", "will be blocked", "बंद हो जाएगा".
BLOCK_FUTURE = (r"\b(?:band|block\w*|suspend\w*|freeze|frozen|deactivat\w*|kat|cut|disconnect\w*)\s+"
                r"(?:ho|kar|kar di|kar diya|kar diye)?\s*(?:jayega|jaega|jayegi|jaegi|jaayega|denge|dega|di jayegi)\b|"
                r"\bwill be (?:blocked|suspended|frozen|deactivated|closed|disconnected|cut|barred)\b|"
                r"(?:बंद|ब्लॉक|निलंबित)\s*(?:हो|कर)\s*(?:जाएगा|जाएगी|दिया जाएगा|दी जाएगी)")


def _actionable(a):
    """A text-model score alone flags a message only when the reader is given something to act on:
    a contact of the sender's own (a mobile number, a chat, a lookalike or unknown link) or a direct
    request. Genuine bank, OTP, bill and notice messages often score high on vocabulary alone, but
    with no destination and no request a scam has no way to reach its victim."""
    text = a.get("text", "")
    # Warning segments and hypothetical-caller warnings are blanked first: "phone kaat dena" protects
    # the reader, and a request cue inside "कृपया ओटीपी किसी से साझा न करें" asks nothing.
    rest = request_text(text)
    if (a["own_contact"] or _clause_hit(BLOCK_FUTURE, text) or _contact_anywhere(a) or
            _clause_hit(PAY_COMMAND, text) or _ordered(rest, threat=False) or _EXCEPT.search(text)):
        return True
    if not (a["request_cues"] or a["reader_direct"]):
        return False
    if rest == " ".join(text.split()):
        return True
    if not rest.strip():
        return False
    b = analyze(rest)
    return bool(b["request_cues"] or b["reader_direct"])


_HANDLE = re.compile(r"@\w|wa\.me|\bt\.me\b|\(at\)|\[\.\]", re.I)
# A host written without a scheme on a TLD the main URL pattern does not list ("sbi-netbanking.pw/verify",
# "forms.gle/abc"): a dotted name with a path, or a hyphenated name, ending in letters.
_LOOSE_HOST = re.compile(r"\b((?:[a-z0-9-]+\.)+[a-z]{2,10})(?=/[^\s]*|\b)(/\S*)?", re.I)


# Real TLDs the main URL pattern does not list, so a bare "sbihelp.pw" still counts as a link.
_EXTRA_TLDS = {"pw", "us", "cn", "ru", "uk", "ws", "su", "gl", "gd", "do", "be", "ai", "gg", "store", "website",
               "support", "help", "tech", "space", "fun", "digital", "today", "world", "email", "services",
               "center", "network", "bond", "cyou", "cfd", "sbs", "lat", "mobi", "asia", "page", "net", "org"}


def _loose_hosts(text):
    out = []
    for m in _LOOSE_HOST.finditer(text):
        h = m.group(1).lower()
        label = h.split(".")[0]
        if m.group(2) or "-" in label or h in SHORTENERS or h in ("forms.gle", "bit.do", "youtu.be", "t.ly") \
                or h.rsplit(".", 1)[-1] in _EXTRA_TLDS:
            if not re.fullmatch(r"(?:rs|inr|no|ac|ref|txn)", label):
                out.append(h)
    return out


def _contact_anywhere(a):
    """Any contact a reader could use that is not the organisation's own, wherever it stands: a link
    to a site that is not official, a mobile number in any spelling, a chat handle or an obfuscated
    link. Unlike own_contact this does not need a clause that asks the reader to act."""
    text = a.get("text", "")
    return bool(any(not is_official(h) for h in a["hosts"] + _loose_hosts(text)) or CONTACT_NUMBER.search(text)
                or _HANDLE.search(text) or _any(CHAT_CONTACT, text))

def decide(p_model, a, gate=0.85):
    """Turn the mechanism analysis plus the text-model probability into a label and score.

    Order matters: a decisive harmful mechanism wins over a receipt or protection clause, because
    scammers write "no OTP needed, just pay the fee". A benign explanation (official channel, a
    completed-transaction record, an OTP notification, a protection statement) only clears a message
    when no harmful mechanism is present. The model probability is a tie-breaker for novel wording.
    """
    harm = [n for n, _ in a["harm"]]
    if harm and _warning_only(a):
        # Every harmful mechanism is described, negated or conditional, and there is nowhere of the
        # sender's own to act on: the message warns the reader instead of asking anything.
        cleared = dict(a, harm=[], safe=list(a["safe"]) + ["warning_only"])
        return 0, min(p_model, 0.40), cleared
    if a.get("report") and not a.get("reader_direct") and not harm:
        # A report describes the scam to a third party; it makes no request of the reader.
        return 0, min(p_model, 0.40), a
    if (a["official_channel"] and set(harm) == {"authority_threat"} and
            not (a["dest_strong"] or a["risky"] or a["threat"] or a["isolation"] or
                 a["secrecy"] or a["secret"])):
        # A genuine customs or utility notice points at its own portal and asks for the duty;
        # it does not isolate the reader or name a private payee.
        return 0, min(p_model, 0.45), a
    strong = [h for h in harm if h in DECISIVE]
    if strong:
        return 1, max(p_model, 0.85), a
    if (a["awareness"] or a.get("report")) and not a["own_contact"] and \
            set(harm) <= {"block_threat", "job_offer"}:
        # The threat or offer words describe what fraudsters do to other people; the advisory asks
        # nothing of the reader and gives no number, chat or link of its own.
        return 0, min(p_model, 0.40), a
    if a["threat"] and (a["risky"] or a["pay_unverified"] or a["secret"] or a["fee"] or a["remote"]):
        return 1, max(p_model, 0.75), a
    # A block warning that routes the reader to a personal mobile number or an unknown link is the
    # electricity, SIM and KYC scam pattern; genuine notices name a short code, a toll-free line or
    # their own app.
    if a["threat"] and (a["dest_strong"] or a["risky"]) and not a["official_channel"]:
        return 1, max(p_model, 0.75), a
    if (a["pay_unverified"] or a["secret"]) and (a["risky"] or a["dest_strong"]):
        return 1, max(p_model, 0.80), a
    if not harm:
        if a["awareness"] or a.get("report"):
            # A warning or news report makes no request of the reader. With no contact of its own
            # (analyze records that as a harm) it is cleared whatever the model says.
            return 0, min(p_model, 0.40), a
        if (a["bill"] or a["appointment"]) and not a["own_contact"]:
            # A bill or appointment reminder that names no mobile number, chat or lookalike link of
            # its own is a routine notice: the payment goes to the biller's own app or site.
            return 0, min(p_model, 0.40), a
        if a["no_hurry"] and not a["own_contact"]:
            # A payment chat that says there is no hurry and names nowhere to send money is a
            # favour between acquaintances; a scam pressures and always gives a destination.
            return 0, min(p_model, 0.40), a
        if (a["receipt"] or a["otp_note"]) and a["risky"]:
            # A copied debit or OTP alert that sends the reader to a lookalike or throwaway domain
            # ("Not you? Visit sbi-refund-help.dev") is not a record; genuine alerts name the
            # bank's own app, site or toll-free line. The reader is told to check, not that it is safe.
            return "uncertain", max(min(p_model, 0.6), 0.5), a
        if a["protective"] and not ((a["otp_note"] or a["self_check"]) and not a["own_contact"]) and \
                (a["request_cues"] or p_model >= gate):
            # An OTP delivered to the reader with "do not share it", or an alert that says what to
            # do "if you did not request this", is the sender's own protection, not a demand.
            return (1 if p_model >= gate and _actionable(a) else 0), p_model, a
        if a["receipt"] or a["otp_note"]:
            # A completed transaction or an OTP notification is a record, not a request.
            return 0, min(p_model, 0.35), a
        if (a["protective"] or a["promo"] or a["official_channel"] or a["notice"] or a["bill"]
                or a["appointment"]):
            return 0, min(p_model, 0.40), a
        # No harmful mechanism fired, so advice and warning frames are not demands even when
        # they cite a helpline or a report link. A pending collect still needs no hit link.
        if a["advice"]:
            return 0, min(p_model, 0.40), a
        if a["collect_review"] and not a["risky"]:
            return 0, min(p_model, 0.40), a
        if a["awareness"]:
            return 0, min(p_model, 0.40), a
        if p_model >= gate and _actionable(a):
            return 1, p_model, a
        return 0, (min(p_model, 0.55) if p_model >= gate else p_model), a
    # A warning carried on the service's own app or portal is a notice, not a demand: only a
    # secret request or a payment to an unverified payee survives the official-channel test.
    if a["official_channel"] and set(harm) <= {"block_threat", "job_offer"} and \
            not ("block_threat" in harm and CONTACT_NUMBER.search(a.get("text", ""))):
        # A block or disconnection threat that also points to the official app may still carry a
        # scammer's contact in any spelling (split numbers, handles, obfuscated links), so it is
        # never cleared outright: it is SUSPICIOUS and the reader checks in the official app.
        if p_model >= 0.5 and _other_contact(a):
            return "uncertain", min(p_model, 0.6), a
        return 0, min(p_model, 0.45), a
    if set(harm) == {"block_threat"} and (a["bill"] or a["notice"] or a["appointment"]) and \
            not (a["dest_strong"] or a["risky"] or a["secret"] or a["pay_unverified"]):
        # A routine bill or appointment reminder may say service stops after the due date; with
        # no private payee, link or secret request it is a deadline, not a threat.
        # A spoof can copy a reminder and hide its contact in any spelling, so when the model
        # leans scam the reader is told to check, not that there is no risk.
        if p_model >= 0.5 and _other_contact(a):
            return "uncertain", min(p_model, 0.6), a
        return 0, min(p_model, 0.45), a
    if set(harm) == {"block_threat"} and (a["receipt"] or a["otp_note"]) and _self_block(a.get("text", "")) and \
            not (a["hosts"] or a.get("reader_direct") or a["dest_strong"] or a["risky"] or a["secret"] or
                 a["pay_unverified"]):
        # A bank debit or OTP alert that says "if not you, block your card in the app" may be the
        # bank's own protective advice, but a spoof can copy it, so it is never cleared outright:
        # it is SUSPICIOUS, and the reader checks the payment in the bank app.
        return ("uncertain", min(p_model, 0.6), a) if p_model >= 0.5 else (0, min(p_model, 0.45), a)
    # The proxy scores abstention as a miss on both sides, so a binary call at the posterior
    # midpoint is never worse than "uncertain" and is right more often than always-benign.
    return (1 if p_model >= 0.5 else 0), p_model, a


DEVANAGARI = re.compile(r"[\u0900-\u097F]")
HINGLISH = re.compile(
    r"\b(hai|hain|aap|aapka|aapki|aapke|karein|karo|kijiye|karna|nahi|nahin|bhejein|bhejo|"
    r"turant|jaldi|paisa|paise|khata|namaste|milega|zaroorat|chahiye|sakte|hoga|gaya|gayi|"
    r"raha|rahi|bhai|didi|kripya|dhanyavad|swagat|wala|wali|abhi|mera|tera|hum|tum|bhej|"
    r"kare|karen|kar|jaye|jayega|hoga|hogi)\b", re.I)
INDIA = re.compile(
    r"\b(upi|kyc|aadhaar|pan|inr|lakh|crore|npci|irctc|uidai|epfo|trai|rbi|sbi|hdfc|icici|"
    r"axis|kotak|pnb|paytm|phonepe|gpay|bhim|indiapost|mahadiscom|bsnl|jio|airtel|lic|"
    r"collect request|digital arrest|cyber cell|electricity|disconnection|meter|courier|"
    r"customs|parcel|otp|rupees|शुल्क)\b|[₹]|\brs\.?\s?\d|\+91|\b[6-9]\d{9}\b|\.in\b", re.I)


def indic_context(text):
    """True for Indian-language or Indian-context messages; routes them to the Indic detector.

    Obfuscated text is cleaned first so zero-width characters cannot hide an Indian marker.

    The generic English SMS model is trained on a British SMS corpus and must keep serving that
    distribution unchanged. Indian messages carry at least one marker the corpus does not use:
    Devanagari script, Hinglish function words, an Indian entity, rupee amounts or a +91 number.
    """
    text = clean(text)
    return bool(DEVANAGARI.search(text) or HINGLISH.search(text) or INDIA.search(text))


SAFE_DESC = {
    "official_channel": "points to the official app or channel",
    "transaction_receipt": "reads like a normal payment receipt, order or delivery record",
    "otp_notification": "reads like a normal OTP notification",
    "protective": "includes a protective statement",
    "opt_out": "includes an opt-out option",
    "notice": "reads like a routine notice or appointment",
    "bill_notice": "reads like a routine bill reminder with a payment due",
    "appointment_notice": "reads like a routine appointment or schedule change",
    "promo": "reads like a promotional offer with a discount or cashback",
    "personal": "reads like a personal conversation",
    "consumer_advice": "reads like consumer advice to check the published charges first",
    "collect_review": "reads like a pending collect-request notice to review",
    "awareness": "reads like a warning or news report about a scam",
    "no_hurry": "says there is no hurry",
    "warning_only": "its risky words are only safety warnings or checks, with no contact to act on",
}


def safe_description(name, text):
    if name == 'transaction_receipt':
        if re.search(r"refund|रिफंड|वापसी", text, re.I):
            return 'reads like a normal refund receipt'
        if re.search(r"order|ऑर्डर|delivery|डिलीवरी", text, re.I):
            return 'reads like a normal order or delivery record'
        if re.search(r"track|ट्रैक", text, re.I):
            return 'reads like a normal tracking update'
    if name == 'protective':
        m = re.search(r"(never|do not|don't|does not|doesn't)\s+ask[^.;!?।\n]{0,30}\b(otp|pin|cvv|password|code)\b", text, re.I)
        if m:
            return 'says it never asks for ' + m.group(2).upper()
        m = re.search(r'no (fee|charge|payment)|koi (charge|fee|payment) nahi', text, re.I)
        if m:
            return 'says no ' + (m.group(1) or m.group(2)).lower() + ' is needed'
        m = re.search(r'no (otp|pin)|koi (otp|pin) nahi', text, re.I)
        if m:
            return 'says no ' + (m.group(1) or m.group(2)).upper() + ' is needed'
    if name == 'official_channel' and re.search(r'\bat the branch\b', text, re.I):
        other = [m.group() for m in re.finditer(DEST_OFFICIAL, text, re.I)
                 if not re.fullmatch(r'at the branch', m.group(), re.I)]
        if other:
            return 'mentions ' + ', '.join(other) + ' and the branch'
        return 'mentions the branch'
    return SAFE_DESC[name]


def evidence(a):
    """Human-readable evidence lines for the API (harm first, then the benign explanation)."""
    out = [d for _, d in a["harm"]]
    for r in a["risky"]:
        if r not in out:
            out.append(r)
    if not a["harm"]:
        for s in ("official_channel", "transaction_receipt", "otp_notification", "protective", "opt_out", "notice",
                  "promo", "consumer_advice", "collect_review", "awareness", "no_hurry", "warning_only"):
            if s in a["safe"]:
                out.append(safe_description(s, a['text']))
    return out[:5]
