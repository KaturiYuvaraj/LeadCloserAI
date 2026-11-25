"""
Shreya 2.0 evaluation set: 100 conversations in the 8 groups we agreed (25 Nov):
20 normal, 15 Telugu-English mixed, 15 difficult or angry, 10 price objections, 10 topic changes,
10 interruptions and broken sentences, 10 appointments and callbacks, 10 unclear speech.

Each scenario: the customer's turns (what STT would give us), the call language, and what must hold.
Expectations are checked automatically by eval/run_eval.py on every reply:
  always: numbers in words, at most one question, short, call language, no budget question,
          no price unless asked, no AI talk unless asked, no familiar goodbye
  "ends": the call must be ended (goodbye + hang-up) by the last reply
  "no_end": the call must still be open after the last reply
  "switch_to": the reply after the request must be in that language
  "hold": the reply must be a very short "take your time"
"""

from typing import Any, Dict, List

Scenario = Dict[str, Any]


def _s(group: str, lang: str, turns: List[str], **expect) -> Scenario:
    return {"group": group, "lang": lang, "turns": turns, **expect}


NORMAL = [
    _s("normal", "te-IN", ["అవునండి, చెప్పండి.", "మాకు ఒక website కావాలి.", "మాది textile shop అండి.", "ఇంకా నెల లోపు start చేయాలి."]),
    _s("normal", "te-IN", ["హా చెప్పండి.", "ఒక mobile app కావాలి మా restaurant కోసం.", "Android, iPhone రెండూ.", "Free consultation పెట్టండి, రేపు ఉదయం పదకొండు గంటలకి."]),
    _s("normal", "te-IN", ["అవును, నేనే enquiry పెట్టాను.", "మా clinic కి online booking కావాలి.", "Patients ఎక్కువగా phone లోనే చూస్తారు.", "సరే, details WhatsApp లో పంపండి."]),
    _s("normal", "te-IN", ["చెప్పండి అండి.", "Instagram, Facebook marketing చేయాలి.", "మాది కొత్త bakery.", "ఎలా help చేస్తారు?"]),
    _s("normal", "te-IN", ["ఆ చెప్పండి.", "మాకు billing software కావాలి.", "మూడు branches ఉన్నాయి.", "Team తో మాట్లాడతాను, రేపు call చేయండి."]),
    _s("normal", "hi-IN", ["हाँ बोलिए।", "हमें एक वेबसाइट चाहिए।", "हमारा कपड़ों का बिज़नेस है।", "अगले महीने तक चाहिए।"]),
    _s("normal", "hi-IN", ["जी बताइए।", "मोबाइल ऐप बनवाना है।", "Android और iPhone दोनों के लिए।", "ठीक है, कल शाम चार बजे कॉल कीजिए।"]),
    _s("normal", "hi-IN", ["हाँ जी।", "हमें CRM software चाहिए।", "हमारी sales team बीस लोगों की है।", "Details WhatsApp पर भेज दीजिए।"]),
    _s("normal", "en-IN", ["Yes, tell me.", "We need a website for our real estate company.", "We want property listings and enquiries.", "Can your team call me tomorrow at three?"]),
    _s("normal", "en-IN", ["Hello, yes.", "I'm looking for an e-commerce app.", "Both Android and iPhone.", "What is the next step?"]),
    _s("normal", "en-IN", ["Speaking.", "We run a school and need an app for parents.", "Attendance, fees and notices.", "Sounds good, send details on WhatsApp."]),
    _s("normal", "te-IN", ["చెప్పండి.", "Google lo మా shop రావాలి.", "మాది hardware shop.", "ఎంత time పడుతుంది?"]),
    _s("normal", "te-IN", ["అవునండి.", "ERP software గురించి enquiry చేశాను.", "Manufacturing company మాది.", "ఎప్పుడు మాట్లాడొచ్చు మీ team తో?"]),
    _s("normal", "te-IN", ["హలో, చెప్పండి.", "మా gym కి app కావాలి.", "Members attendance, payments.", "సరే, Saturday కలుద్దాం."]),
    _s("normal", "hi-IN", ["बोलिए।", "मेरा restaurant है, online orders चाहिए।", "Zomato से अलग अपना app चाहिए।", "ठीक है, team से बात करवा दीजिए।"]),
    _s("normal", "en-IN", ["Yes please.", "I need digital marketing for my salon.", "Mostly Instagram.", "Okay, call me on Monday."]),
    _s("normal", "te-IN", ["చెప్పండి అండి.", "మాకు already website ఉంది.", "కానీ customers రావట్లేదు.", "ఏం చేయొచ్చు?"]),
    _s("normal", "en-IN", ["Yes.", "We have an app but it's slow.", "Built five years back.", "Can you rebuild it?"]),
    _s("normal", "te-IN", ["అవునండి.", "మా coaching centre కి website, app రెండూ కావాలి.", "Students online classes చూడాలి.", "Free consultation book చేయండి, రేపు సాయంత్రం ఐదు."]),
    _s("normal", "hi-IN", ["हाँ जी बोलिए।", "मुझे जानना है आप क्या-क्या करते हो।", "मेरा medical store है।", "ठीक है, सोचकर बताता हूँ।"]),
]

TENGLISH = [
    _s("tenglish", "te-IN", ["Haa cheppandi.", "Maaku oka app kavali for delivery.", "Multiple restaurants untayi.", "Ok next steps enti?"]),
    _s("tenglish", "te-IN", ["చెప్పండి, but quick గా.", "Website already undi but update cheyali.", "Mobile friendly ga ledu.", "Ok team ni call cheyamanandi."]),
    _s("tenglish", "te-IN", ["అవును sir.", "Social media ads run cheyali, budget limited.", "Small business andi.", "Start chesthe results eppudu vastayi?"]),
    _s("tenglish", "te-IN", ["Yes andi.", "Naaku CRM kavali for my sales team.", "Twenty members unnaru.", "Demo chupistara?"]),
    _s("tenglish", "te-IN", ["Cheppandi.", "Ma shop ki online store kavali.", "Sarees ammutham.", "WhatsApp lo details pampandi."]),
    _s("tenglish", "te-IN", ["హలో.", "App development cost entha?", "Android only chalu.", "Startup andi maadi."]),
    _s("tenglish", "te-IN", ["చెప్పండి.", "Website, app rendu kavali, kani first website.", "Real estate business.", "Next week start cheddam."]),
    _s("tenglish", "te-IN", ["Yes cheppandi.", "Google lo top lo raavali ma business.", "Interior design company.", "Ela chestaru adi?"]),
    _s("tenglish", "te-IN", ["Haa.", "Maa hospital ki appointment app kavali.", "Doctors schedule kuda.", "Tomorrow evening call cheyandi."]),
    _s("tenglish", "te-IN", ["ఓకే చెప్పండి.", "Meeru Madhapur lo ekkada?", "Office ki ravacha?", "Saturday morning vastanu."]),
    _s("tenglish", "te-IN", ["Cheppandi andi.", "Billing software kavali GST tho.", "Retail shop.", "Ok think chesi cheptha."]),
    _s("tenglish", "hi-IN", ["Haan bolo.", "Mujhe ek website chahiye apne business ke liye.", "Travel agency hai.", "Kal call karna."]),
    _s("tenglish", "hi-IN", ["Ji boliye.", "App banwana hai, kitna time lagega?", "Dono platform pe.", "Theek hai, details bhej do."]),
    _s("tenglish", "en-IN", ["Yes tell me.", "Basically ma business ki online presence kavali.", "Photography studio.", "Ok, book a consultation."]),
    _s("tenglish", "te-IN", ["అవును.", "Marketing chesthe leads vastaya?", "Last time try chesam, waste ayyindi.", "Meeru ela different?"]),
]

ANGRY = [
    _s("angry", "te-IN", ["ఎవరు మీరు?", "మళ్ళీ మళ్ళీ call చేస్తున్నారు, చిరాకుగా ఉంది."], ends=True),
    _s("angry", "te-IN", ["చెప్పండి.", "మీ బిహేవియర్ ఏం బాలేదు, రూడ్ గా call కట్ చేశారు."], ends=True),
    _s("angry", "te-IN", ["నా number ఎక్కడ దొరికింది మీకు?", "Disturb చేయకండి, time waste."], ends=True),
    _s("angry", "hi-IN", ["कौन बोल रहा है?", "बार बार कॉल क्यों कर रहे हो, परेशान कर दिया।"], ends=True),
    _s("angry", "hi-IN", ["हाँ?", "बकवास बंद करो, मुझे कुछ नहीं चाहिए।"], ends=True),
    _s("angry", "en-IN", ["Who is this?", "Stop calling me again and again, it's annoying."], ends=True),
    _s("angry", "en-IN", ["Yes?", "This is a scam, I know these calls."], ends=True),
    _s("angry", "te-IN", ["హా.", "నాకు అవసరం లేదు, మళ్ళీ call చేయొద్దు."], ends=True),
    _s("angry", "en-IN", ["Hello.", "Don't call me again, remove my number."], ends=True),
    _s("angry", "te-IN", ["చెప్పండి.", "మీరు చాలా చీదరించుకుంటున్నారు, ఎటకారంగా మాట్లాడుతున్నారు."], ends=True),
    _s("angry", "hi-IN", ["बोलो।", "तुम लोग धोखा देते हो, फ्रॉड हो।"], ends=True),
    _s("angry", "en-IN", ["Yes.", "I'm busy and you keep disturbing me, it's irritating."], ends=True),
    _s("angry", "te-IN", ["ఎవరండి?", "ఇప్పటికే మూడు సార్లు చేశారు, విసిగిస్తున్నారు."], ends=True),
    _s("angry", "en-IN", ["Hello?", "Your people were rude last time."], ends=True),
    _s("angry", "te-IN", ["ఏంటి?", "Time వేస్ట్ చేయకండి, బుద్ధి లేదా?"], ends=True),
]

PRICING = [
    _s("pricing", "te-IN", ["చెప్పండి.", "App కి ఎంత అవుతుంది?", "Android, iPhone రెండూ.", "చాలా ఎక్కువ అండి."], no_end=True),
    _s("pricing", "te-IN", ["అవును.", "Website ఎంత?", "Simple ఐదు pages చాలు.", "GST తో total ఎంత?"], no_end=True),
    _s("pricing", "hi-IN", ["बोलिए।", "मोबाइल ऐप की कीमत क्या है?", "बहुत महंगा है।", "हम नया startup हैं।"], no_end=True),
    _s("pricing", "en-IN", ["Yes.", "How much for a website and social media?", "That's too costly.", "Can you reduce it?"], no_end=True),
    _s("pricing", "en-IN", ["Tell me.", "What's the price of your CRM?", "How long does it take?", "Okay, send the quotation."]),
    _s("pricing", "te-IN", ["హా.", "Marketing package rates చెప్పండి.", "మాది small business.", "Discount ఏమైనా ఉందా?"], no_end=True),
    _s("pricing", "hi-IN", ["हाँ।", "Android ऐप कितने में बनेगा?", "पचास हज़ार में बन जाएगा?", "ठीक है, team से बात करवाइए।"]),
    _s("pricing", "en-IN", ["Hello.", "Why is the Standard app plan so expensive?", "What's included?", "Okay."]),
    _s("pricing", "te-IN", ["చెప్పండి.", "ERP software ధర ఎంత?", "Payment terms ఏంటి?", "సరే."]),
    _s("pricing", "en-IN", ["Yes.", "Other companies quoted much less.", "Why should I choose you?", "Let me think."], no_end=True),
]

TOPIC_CHANGE = [
    _s("topic_change", "te-IN", ["చెప్పండి.", "మాకు website కావాలి.", "అసలు మీ office ఎక్కడ?", "సరే, website గురించి చెప్పండి."]),
    _s("topic_change", "en-IN", ["Yes.", "I need an app.", "Wait, do you also do Google ads?", "Okay, back to the app, both platforms."]),
    _s("topic_change", "te-IN", ["హా.", "App కావాలి.", "మీరు ఎన్ని years నుండి ఉన్నారు?", "ఓకే, app ఎంత time?"]),
    _s("topic_change", "hi-IN", ["बोलिए।", "वेबसाइट चाहिए।", "आपके founder कौन हैं?", "ठीक है, वेबसाइट की बात करते हैं।"]),
    _s("topic_change", "en-IN", ["Yes.", "We want a CRM.", "Actually first, can you make a website?", "Then CRM later."]),
    _s("topic_change", "te-IN", ["చెప్పండి.", "Marketing కావాలి.", "మీరు భోజనం చేశారా?", "సరే, marketing గురించి చెప్పండి."]),
    _s("topic_change", "en-IN", ["Yes.", "Website please.", "Are you a robot?", "Okay, continue."]),
    _s("topic_change", "te-IN", ["అవును.", "Billing software.", "మీరు ఎక్కడ ఉంటారు?", "సరే, billing గురించి."]),
    _s("topic_change", "hi-IN", ["हाँ।", "ऐप चाहिए।", "Office का time क्या है?", "ठीक है, ऐप के बारे में बताइए।"]),
    _s("topic_change", "en-IN", ["Hi.", "Do you build apps?", "What's your phone number?", "Great, I need an iPhone app."]),
]

INTERRUPTIONS = [
    _s("interruptions", "te-IN", ["చెప్పండి.", "మాకు ఒక... అదే...", "app కావాలి కానీ ముందు website.", "అవును."]),
    _s("interruptions", "te-IN", ["హా.", "ఒక్క నిమిషం.", "హా ఇప్పుడు చెప్పండి.", "Website కావాలి."], hold_turn=1),
    _s("interruptions", "en-IN", ["Yes.", "Hold on.", "Sorry, go ahead.", "We need an app."], hold_turn=1),
    _s("interruptions", "hi-IN", ["बोलिए।", "एक मिनट रुकिए।", "हाँ बताइए।", "वेबसाइट चाहिए।"], hold_turn=1),
    _s("interruptions", "te-IN", ["చెప్పండి.", "App కావాలి Android... no no, iPhone కూడా.", "రెండూ.", "Next?"]),
    _s("interruptions", "en-IN", ["Yes.", "I want a website, actually no, an app first.", "For my bakery.", "Okay."]),
    _s("interruptions", "te-IN", ["అవును.", "మా business... అంటే మాది...", "furniture shop.", "Website చాలు."]),
    _s("interruptions", "hi-IN", ["हाँ।", "मुझे चाहिए... रुको...", "हाँ, मोबाइल ऐप।", "दोनों के लिए।"]),
    _s("interruptions", "en-IN", ["Yeah.", "Let me finish first.", "We need a delivery app for many shops.", "Yes."]),
    _s("interruptions", "te-IN", ["హలో.", "హలో?", "వినిపిస్తోందా?", "ఆ, website కావాలి."]),
]

APPOINTMENTS = [
    _s("appointments", "te-IN", ["చెప్పండి.", "Website కావాలి.", "Free consultation పెట్టండి.", "రేపు మధ్యాహ్నం మూడు గంటలకి."]),
    _s("appointments", "en-IN", ["Yes.", "Busy now, driving.", "Call me after six today."], ends=True),
    _s("appointments", "hi-IN", ["हाँ।", "अभी meeting में हूँ।", "कल सुबह दस बजे कॉल करना।"], ends=True),
    _s("appointments", "te-IN", ["చెప్పండి.", "ఇప్పుడు busy, Sunday call చేయండి."]),
    _s("appointments", "en-IN", ["Yes.", "I want to visit your office.", "Saturday at eleven."]),
    _s("appointments", "te-IN", ["హా.", "App కావాలి.", "Consultation ok.", "ఏ time అయినా పర్లేదు."]),
    _s("appointments", "en-IN", ["Yes.", "Book a consultation.", "Ok.", "Three PM tomorrow."]),
    _s("appointments", "hi-IN", ["बोलिए।", "वेबसाइट चाहिए।", "Consultation रख लीजिए।", "परसों शाम पाँच बजे।"]),
    _s("appointments", "te-IN", ["చెప్పండి.", "రాత్రి పది గంటలకి call చేయండి."]),
    _s("appointments", "en-IN", ["Yes.", "Website needed.", "Can we talk at 8 PM tonight?"]),
]

UNCLEAR = [
    _s("unclear", "te-IN", ["అ...", "హ్మ్.", "ఏంటి?", "Website."]),
    _s("unclear", "te-IN", ["చెప్పండి.", "పహిలీచ్ ఫోన్ భేటతే.", "ఆ.", "App కావాలి."]),
    _s("unclear", "en-IN", ["Yes.", "Am I hard to look?", "Sorry, network.", "I need a website."]),
    _s("unclear", "hi-IN", ["हाँ।", "सैलरी में बात करो।", "हम्म।", "वेबसाइट।"]),
    _s("unclear", "te-IN", ["హలో.", "ఫోన్ బచ్చే సే.", "హా.", "మాకు marketing కావాలి."]),
    _s("unclear", "en-IN", ["Yes.", "Oral charges, I'm asking.", "Total charges.", "Okay."]),
    _s("unclear", "te-IN", ["చెప్పండి.", "అది ఇది అంతే.", "ఆ.", "సరే."]),
    _s("unclear", "en-IN", ["Hmm.", "Uh.", "What?", "Okay tell me."]),
    _s("unclear", "hi-IN", ["हाँ।", "उनका प्रश्न है।", "हाँ।", "ऐप।"]),
    _s("unclear", "te-IN", ["హా.", "మీరు మీరు.", "ఏమైంది?", "Website గురించి చెప్పండి."]),
]

SCENARIOS: List[Scenario] = NORMAL + TENGLISH + ANGRY + PRICING + TOPIC_CHANGE + INTERRUPTIONS + APPOINTMENTS + UNCLEAR
for i, sc in enumerate(SCENARIOS, 1):
    sc["id"] = i

assert len(SCENARIOS) == 100, len(SCENARIOS)
