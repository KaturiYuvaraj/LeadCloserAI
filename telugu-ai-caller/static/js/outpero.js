/**
 * Outpero.com Complete Interactive Frontend Engine
 * Replicates all client-side interactive widgets, animations, 7-language simulators,
 * 56 industry call audio players, channel tab switchers, employee stage builder,
 * pricing calculators, and pointer effects.
 */
(function () {
  "use strict";

  // =========================================================================
  // 1. DATA: GREETINGS, BRIEF PROMPTS, HOW-IT-WORKS, CALL CLIPS, CHANNELS
  // =========================================================================
  const GREETING_WORDS = [
    { text: "नमस्ते", lang: "hi" },
    { text: "నమస్కారం", lang: "te" },
    { text: "வணக்கம்", lang: "ta" },
    { text: "ನಮಸ್ಕಾರ", lang: "kn" },
    { text: "നമസ്കാരം", lang: "ml" },
    { text: "नमस्कार", lang: "mr" },
    { text: "Hello", lang: "en" }
  ];

  const BRIEF_PLACEHOLDERS = [
    "Call every new Facebook lead within 30 seconds in Hindi, ask budget and timeline, and book a site visit for this weekend...",
    "Call policies expiring next week in Telugu, explain the renewal amount, and send the payment link on WhatsApp...",
    "Answer incoming calls to our clinic in Tamil, check doctor availability, and book an appointment slot...",
    "Call 2,000 past enquiries in Marathi about our festive offer and pass interested ones to the sales team...",
    "Call car enquiry leads in Kannada, ask which model they liked, and book a home test drive for Saturday..."
  ];

  const BRIEF_CHIPS = {
    "Remind about renewals": "Call customers whose policy renewals are due this week in Hindi and English, confirm if they want to renew, and send the payment link on WhatsApp.",
    "Call new property leads": "Call new 2BHK and 3BHK Facebook ad enquiries within 30 seconds, ask if they're buying to live in or invest, check their budget, and book a Saturday site visit.",
    "Remind patients": "Call patients with tomorrow's clinic appointments in Telugu or English, confirm if they're coming, or reschedule to the next open slot.",
    "Wake up an old list": "Call our list of past enquiries from the last 6 months, tell them about our festive offer, and mark anyone interested for a callback from our senior closer.",
    "Book test drives": "Call website enquiries for our new SUV in Hindi, ask whether they want a showroom visit or home test drive, and book a slot for this weekend."
  };

  const HOW_IT_WORKS_DATA = [
    {
      label: "हिन्दी",
      english: "Hindi",
      langAttr: "hi",
      caller: "Nest Realty",
      initials: "NR",
      duration: "1:08",
      leadName: "Aman Verma",
      leadInitials: "AV",
      leadPhone: "+91 98••• ••210",
      leadCity: "Noida",
      languagePill: "Hindi + English",
      turns: [
        { from: "ai", text: "नमस्ते अमन जी! मैं Meera, Nest Realty से। आपने Sector 150 के 2BHK के लिए enquiry की थी। दो मिनट बात कर सकते हैं?" },
        { from: "lead", text: "हाँ जी, बोलिए।" },
        { from: "ai", text: "रहने के लिए देख रहे हैं, या investment के लिए?" },
        { from: "lead", text: "रहने के लिए। Budget लगभग 90 लाख है।" },
        { from: "ai", text: "बढ़िया। इस Saturday 11 बजे site visit रख दूँ? Location मैं WhatsApp कर देती हूँ।" },
        { from: "lead", text: "हाँ, कर दीजिए।" }
      ],
      fields: [
        { k: "Looking for", v: "2BHK, Sector 150", revealAt: 1 },
        { k: "Purpose", v: "To live in", revealAt: 4 },
        { k: "Budget", v: "~₹90L", revealAt: 4 },
        { k: "Site visit", v: "Sat, 11:00 AM", revealAt: 6 }
      ],
      summary: "Wants a 2BHK in Sector 150, Noida to live in, around ₹90L. Site visit booked for Saturday 11 AM; location sent on WhatsApp."
    },
    {
      label: "తెలుగు",
      english: "Telugu",
      langAttr: "te",
      caller: "Nest Realty",
      initials: "NR",
      duration: "1:12",
      leadName: "Srinivas Rao",
      leadInitials: "SR",
      leadPhone: "+91 90••• ••418",
      leadCity: "Hyderabad",
      languagePill: "Telugu + English",
      turns: [
        { from: "ai", text: "నమస్కారం శ్రీనివాస్ గారు! నేను Meera, Nest Realty నుండి. మీరు Kondapur 2BHK గురించి enquiry చేశారు కదా. రెండు నిమిషాలు మాట్లాడవచ్చా?" },
        { from: "lead", text: "ఆ చెప్పండి." },
        { from: "ai", text: "మీరు ఉండటానికి చూస్తున్నారా, లేక investment కోసమా?" },
        { from: "lead", text: "ఉండటానికేనండి. Budget దాదాపు 90 లక్షలు." },
        { from: "ai", text: "చాలా మంచిది. ఈ Saturday ఉదయం 11 గంటలకు site visit పెట్టమంటారా? Location నేను WhatsApp లో పంపిస్తాను." },
        { from: "lead", text: "సరేనండి, పెట్టండి." }
      ],
      fields: [
        { k: "Looking for", v: "2BHK, Kondapur", revealAt: 1 },
        { k: "Purpose", v: "To live in", revealAt: 4 },
        { k: "Budget", v: "~₹90L", revealAt: 4 },
        { k: "Site visit", v: "Sat, 11:00 AM", revealAt: 6 }
      ],
      summary: "Wants a 2BHK in Kondapur, Hyderabad to live in, around ₹90L. Site visit booked for Saturday 11 AM; location sent on WhatsApp."
    },
    {
      label: "தமிழ்",
      english: "Tamil",
      langAttr: "ta",
      caller: "Nest Realty",
      initials: "NR",
      duration: "1:10",
      leadName: "Karthik Raman",
      leadInitials: "KR",
      leadPhone: "+91 94••• ••602",
      leadCity: "Chennai",
      languagePill: "Tamil + English",
      turns: [
        { from: "ai", text: "வணக்கம் கார்த்திக் சார்! நான் Meera, Nest Realty-ல இருந்து பேசுறேன். நீங்க Velachery 2BHK பத்தி கேட்டிருந்தீங்க. ரெண்டு நிமிஷம் பேசலாமா?" },
        { from: "lead", text: "ஆமா சொல்லுங்க." },
        { from: "ai", text: "நீங்க குடியிருக்க பாக்குறீங்களா, இல்ல investment-ஆ?" },
        { from: "lead", text: "குடியிருக்கத்தான். Budget சுமார் 90 லட்சம்." },
        { from: "ai", text: "சூப்பர் சார். இந்த Saturday காலைல 11 மணிக்கு site visit வச்சிடலாமா? Location-அ நான் WhatsApp பண்ணிடுறேன்." },
        { from: "lead", text: "சரிங்க, வச்சிடுங்க." }
      ],
      fields: [
        { k: "Looking for", v: "2BHK, Velachery", revealAt: 1 },
        { k: "Purpose", v: "To live in", revealAt: 4 },
        { k: "Budget", v: "~₹90L", revealAt: 4 },
        { k: "Site visit", v: "Sat, 11:00 AM", revealAt: 6 }
      ],
      summary: "Wants a 2BHK in Velachery, Chennai to live in, around ₹90L. Site visit booked for Saturday 11 AM; location sent on WhatsApp."
    },
    {
      label: "ಕನ್ನಡ",
      english: "Kannada",
      langAttr: "kn",
      caller: "Nest Realty",
      initials: "NR",
      duration: "1:09",
      leadName: "Prakash Gowda",
      leadInitials: "PG",
      leadPhone: "+91 99••• ••115",
      leadCity: "Bengaluru",
      languagePill: "Kannada + English",
      turns: [
        { from: "ai", text: "ನಮಸ್ಕಾರ ಪ್ರಕಾಶ್ ಸರ್! ನಾನು Meera, Nest Realty ಇಂದ. ನೀವು Whitefield 2BHK ಬಗ್ಗೆ ವಿಚಾರಿಸಿದ್ರಿ. ಎರಡು ನಿಮಿಷ ಮಾತಾಡಬಹುದಾ?" },
        { from: "lead", text: "ಹೌದು ಹೇಳಿ." },
        { from: "ai", text: "ನೀವು ವಾಸಕ್ಕೆ ನೋಡ್ತಿದ್ದೀರಾ, ಇಲ್ಲ investment ಗಾ?" },
        { from: "lead", text: "ವಾಸಕ್ಕೆ ನೋಡ್ತಿದ್ದೀವಿ. Budget ಸುಮಾರು 90 ಲಕ್ಷ." },
        { from: "ai", text: "ತುಂಬಾ ಒಳ್ಳೇದು. ಈ Saturday ಬೆಳಗ್ಗೆ 11 ಗಂಟೆಗೆ site visit ಇಡಲಾ? Location ನಾನು WhatsApp ಮಾಡ್ತೀನಿ." },
        { from: "lead", text: "ಸರಿ, ಇಡಿ." }
      ],
      fields: [
        { k: "Looking for", v: "2BHK, Whitefield", revealAt: 1 },
        { k: "Purpose", v: "To live in", revealAt: 4 },
        { k: "Budget", v: "~₹90L", revealAt: 4 },
        { k: "Site visit", v: "Sat, 11:00 AM", revealAt: 6 }
      ],
      summary: "Wants a 2BHK in Whitefield, Bengaluru to live in, around ₹90L. Site visit booked for Saturday 11 AM; location sent on WhatsApp."
    },
    {
      label: "മലയാളം",
      english: "Malayalam",
      langAttr: "ml",
      caller: "Nest Realty",
      initials: "NR",
      duration: "1:11",
      leadName: "Anjali Nair",
      leadInitials: "AN",
      leadPhone: "+91 94••• ••874",
      leadCity: "Kochi",
      languagePill: "Malayalam + English",
      turns: [
        { from: "ai", text: "നമസ്കാരം അഞ്ജലി ചേച്ചി! ഞാൻ Meera, Nest Realty-ൽ നിന്നാണ്. Kakkanad 2BHK-യെ കുറിച്ച് ചോദിച്ചിരുന്നല്ലോ. രണ്ട് മിനിറ്റ് സംസാരിക്കാമോ?" },
        { from: "lead", text: "ആ പറയ്." },
        { from: "ai", text: "താമസിക്കാൻ വേണ്ടിയാണോ നോക്കുന്നത്, അതോ investment ആണോ?" },
        { from: "lead", text: "താമസിക്കാൻ തന്നെയാണ്. Budget ഏകദേശം 90 ലക്ഷം." },
        { from: "ai", text: "നല്ലത്. ഈ Saturday രാവിലെ 11 മണിക്ക് site visit വെക്കട്ടെ? Location ഞാൻ WhatsApp ചെയ്യാം." },
        { from: "lead", text: "ശരി, വെച്ചോളൂ." }
      ],
      fields: [
        { k: "Looking for", v: "2BHK, Kakkanad", revealAt: 1 },
        { k: "Purpose", v: "To live in", revealAt: 4 },
        { k: "Budget", v: "~₹90L", revealAt: 4 },
        { k: "Site visit", v: "Sat, 11:00 AM", revealAt: 6 }
      ],
      summary: "Wants a 2BHK in Kakkanad, Kochi to live in, around ₹90L. Site visit booked for Saturday 11 AM; location sent on WhatsApp."
    },
    {
      label: "मराठी",
      english: "Marathi",
      langAttr: "mr",
      caller: "Nest Realty",
      initials: "NR",
      duration: "1:08",
      leadName: "Sagar Patil",
      leadInitials: "SP",
      leadPhone: "+91 98••• ••539",
      leadCity: "Pune",
      languagePill: "Marathi + English",
      turns: [
        { from: "ai", text: "नमस्कार सागर सर! मी Meera, Nest Realty मधून बोलतेय. तुम्ही Baner च्या 2BHK साठी चौकशी केली होती. दोन मिनिटं बोलू शकतो का?" },
        { from: "lead", text: "हो, बोला ना." },
        { from: "ai", text: "तुम्ही राहण्यासाठी बघताय की investment साठी?" },
        { from: "lead", text: "राहण्यासाठीच. Budget साधारण 90 लाख आहे." },
        { from: "ai", text: "छान. या Saturday सकाळी 11 वाजता site visit ठेवू का? Location मी WhatsApp करते." },
        { from: "lead", text: "हो, चालेल." }
      ],
      fields: [
        { k: "Looking for", v: "2BHK, Baner", revealAt: 1 },
        { k: "Purpose", v: "To live in", revealAt: 4 },
        { k: "Budget", v: "~₹90L", revealAt: 4 },
        { k: "Site visit", v: "Sat, 11:00 AM", revealAt: 6 }
      ],
      summary: "Wants a 2BHK in Baner, Pune to live in, around ₹90L. Site visit booked for Saturday 11 AM; location sent on WhatsApp."
    },
    {
      label: "English",
      english: "English",
      langAttr: "en",
      caller: "Nest Realty",
      initials: "NR",
      duration: "1:04",
      leadName: "Neha Kapoor",
      leadInitials: "NK",
      leadPhone: "+91 98••• ••304",
      leadCity: "Mumbai",
      languagePill: "Indian English",
      turns: [
        { from: "ai", text: "Hi Neha, this is Meera calling from Nest Realty. You'd asked about the 2BHK in Powai. Do you have two minutes?" },
        { from: "lead", text: "Sure, go ahead." },
        { from: "ai", text: "Are you looking at this to move into yourself, or as an investment?" },
        { from: "lead", text: "To move into. Budget is around 90 lakhs." },
        { from: "ai", text: "Got it. Shall I book a site visit for this Saturday at 11 AM? I'll send the location on WhatsApp." },
        { from: "lead", text: "Yes, Saturday works." }
      ],
      fields: [
        { k: "Looking for", v: "2BHK, Powai", revealAt: 1 },
        { k: "Purpose", v: "To live in", revealAt: 4 },
        { k: "Budget", v: "~₹90L", revealAt: 4 },
        { k: "Site visit", v: "Sat, 11:00 AM", revealAt: 6 }
      ],
      summary: "Wants a 2BHK in Powai, Mumbai to live in, around ₹90L. Site visit booked for Saturday 11 AM; location sent on WhatsApp."
    }
  ];

  const CALL_INDUSTRIES = [
    { key: "finance", tag: "Loans & insurance", summary: "Screens eligibility and chases documents", mode: "Outbound" },
    { key: "realestate", tag: "Real estate", summary: "Qualifies a property lead and books a site visit", mode: "Outbound" },
    { key: "education", tag: "Coaching", summary: "Explains batches and fees, books a demo class", mode: "Outbound" },
    { key: "healthcare", tag: "Hospitals", summary: "Answers a patient and books a doctor slot", mode: "Inbound" },
    { key: "automotive", tag: "Car dealership", summary: "Follows up an enquiry and books a test drive", mode: "Outbound" },
    { key: "ecommerce", tag: "E-commerce", summary: "Confirms a cash-on-delivery order before shipping", mode: "Outbound" },
    { key: "restaurant", tag: "Restaurants", summary: "Takes a table or party booking over the phone", mode: "Inbound" },
    { key: "recruitment", tag: "Recruitment", summary: "Screens a candidate's notice period and CTC", mode: "Outbound" }
  ];

  const CALL_CLIPS = {
    hindi: {
      finance: { person: "Sneha", voice: "P02", duration: "1:10", src: "https://outpero.com/site/calls/hindi/finance-sneha-p2.mp3" },
      realestate: { person: "Arjun", voice: "P04", duration: "1:10", src: "https://outpero.com/site/calls/hindi/realestate-arjun-p4.mp3" },
      education: { person: "Kavya", voice: "P03", duration: "1:12", src: "https://outpero.com/site/calls/hindi/education-kavya-p3.mp3" },
      healthcare: { person: "Ananya", voice: "P01", duration: "1:12", src: "https://outpero.com/site/calls/hindi/healthcare-ananya-p1.mp3" },
      automotive: { person: "Vikram", voice: "P05", duration: "1:09", src: "https://outpero.com/site/calls/hindi/automotive-vikram-p5.mp3" },
      ecommerce: { person: "Rohan", voice: "P06", duration: "1:07", src: "https://outpero.com/site/calls/hindi/ecommerce-rohan-p6.mp3" },
      restaurant: { person: "Ananya", voice: "P01", duration: "1:11", src: "https://outpero.com/site/calls/hindi/restaurant-ananya-p1.mp3" },
      recruitment: { person: "Sneha", voice: "P02", duration: "1:00", src: "https://outpero.com/site/calls/hindi/recruitment-sneha-p2.mp3" }
    },
    telugu: {
      finance: { person: "Sneha", voice: "P02", duration: "1:20", src: "https://outpero.com/site/calls/telugu/finance-sneha-p2.mp3" },
      realestate: { person: "Arjun", voice: "P04", duration: "1:12", src: "https://outpero.com/site/calls/telugu/realestate-arjun-p4.mp3" },
      education: { person: "Kavya", voice: "P03", duration: "1:18", src: "https://outpero.com/site/calls/telugu/education-kavya-p3.mp3" },
      healthcare: { person: "Ananya", voice: "P01", duration: "1:12", src: "https://outpero.com/site/calls/telugu/healthcare-ananya-p1.mp3" },
      automotive: { person: "Vikram", voice: "P05", duration: "1:15", src: "https://outpero.com/site/calls/telugu/automotive-vikram-p5.mp3" },
      ecommerce: { person: "Rohan", voice: "P06", duration: "1:23", src: "https://outpero.com/site/calls/telugu/ecommerce-rohan-p6.mp3" },
      restaurant: { person: "Ananya", voice: "P01", duration: "1:07", src: "https://outpero.com/site/calls/telugu/restaurant-ananya-p1.mp3" },
      recruitment: { person: "Sneha", voice: "P02", duration: "1:10", src: "https://outpero.com/site/calls/telugu/recruitment-sneha-p2.mp3" }
    },
    tamil: {
      finance: { person: "Sneha", voice: "P02", duration: "1:17", src: "https://outpero.com/site/calls/tamil/finance-sneha-p2.mp3" },
      realestate: { person: "Arjun", voice: "P04", duration: "1:16", src: "https://outpero.com/site/calls/tamil/realestate-arjun-p4.mp3" },
      education: { person: "Kavya", voice: "P03", duration: "1:24", src: "https://outpero.com/site/calls/tamil/education-kavya-p3.mp3" },
      healthcare: { person: "Ananya", voice: "P01", duration: "1:15", src: "https://outpero.com/site/calls/tamil/healthcare-ananya-p1.mp3" },
      automotive: { person: "Vikram", voice: "P05", duration: "1:20", src: "https://outpero.com/site/calls/tamil/automotive-vikram-p5.mp3" },
      ecommerce: { person: "Rohan", voice: "P06", duration: "1:23", src: "https://outpero.com/site/calls/tamil/ecommerce-rohan-p6.mp3" },
      restaurant: { person: "Ananya", voice: "P01", duration: "1:16", src: "https://outpero.com/site/calls/tamil/restaurant-ananya-p1.mp3" },
      recruitment: { person: "Sneha", voice: "P02", duration: "1:12", src: "https://outpero.com/site/calls/tamil/recruitment-sneha-p2.mp3" }
    },
    kannada: {
      finance: { person: "Sneha", voice: "P02", duration: "1:25", src: "https://outpero.com/site/calls/kannada/finance-sneha-p2.mp3" },
      realestate: { person: "Arjun", voice: "P04", duration: "1:13", src: "https://outpero.com/site/calls/kannada/realestate-arjun-p4.mp3" },
      education: { person: "Kavya", voice: "P03", duration: "1:17", src: "https://outpero.com/site/calls/kannada/education-kavya-p3.mp3" },
      healthcare: { person: "Ananya", voice: "P01", duration: "1:14", src: "https://outpero.com/site/calls/kannada/healthcare-ananya-p1.mp3" },
      automotive: { person: "Vikram", voice: "P05", duration: "1:19", src: "https://outpero.com/site/calls/kannada/automotive-vikram-p5.mp3" },
      ecommerce: { person: "Rohan", voice: "P06", duration: "1:24", src: "https://outpero.com/site/calls/kannada/ecommerce-rohan-p6.mp3" },
      restaurant: { person: "Ananya", voice: "P01", duration: "1:16", src: "https://outpero.com/site/calls/kannada/restaurant-ananya-p1.mp3" },
      recruitment: { person: "Sneha", voice: "P02", duration: "1:13", src: "https://outpero.com/site/calls/kannada/recruitment-sneha-p2.mp3" }
    },
    malayalam: {
      finance: { person: "Sneha", voice: "P02", duration: "1:18", src: "https://outpero.com/site/calls/malayalam/finance-sneha-p2.mp3" },
      realestate: { person: "Arjun", voice: "P04", duration: "1:12", src: "https://outpero.com/site/calls/malayalam/realestate-arjun-p4.mp3" },
      education: { person: "Kavya", voice: "P03", duration: "1:22", src: "https://outpero.com/site/calls/malayalam/education-kavya-p3.mp3" },
      healthcare: { person: "Ananya", voice: "P01", duration: "1:08", src: "https://outpero.com/site/calls/malayalam/healthcare-ananya-p1.mp3" },
      automotive: { person: "Vikram", voice: "P05", duration: "1:14", src: "https://outpero.com/site/calls/malayalam/automotive-vikram-p5.mp3" },
      ecommerce: { person: "Rohan", voice: "P06", duration: "1:25", src: "https://outpero.com/site/calls/malayalam/ecommerce-rohan-p6.mp3" },
      restaurant: { person: "Ananya", voice: "P01", duration: "1:17", src: "https://outpero.com/site/calls/malayalam/restaurant-ananya-p1.mp3" },
      recruitment: { person: "Sneha", voice: "P02", duration: "1:04", src: "https://outpero.com/site/calls/malayalam/recruitment-sneha-p2.mp3" }
    },
    marathi: {
      finance: { person: "Sneha", voice: "P02", duration: "1:18", src: "https://outpero.com/site/calls/marathi/finance-sneha-p2.mp3" },
      realestate: { person: "Arjun", voice: "P04", duration: "1:08", src: "https://outpero.com/site/calls/marathi/realestate-arjun-p4.mp3" },
      education: { person: "Kavya", voice: "P03", duration: "1:07", src: "https://outpero.com/site/calls/marathi/education-kavya-p3.mp3" },
      healthcare: { person: "Ananya", voice: "P01", duration: "1:09", src: "https://outpero.com/site/calls/marathi/healthcare-ananya-p1.mp3" },
      automotive: { person: "Vikram", voice: "P05", duration: "1:04", src: "https://outpero.com/site/calls/marathi/automotive-vikram-p5.mp3" },
      ecommerce: { person: "Rohan", voice: "P06", duration: "1:11", src: "https://outpero.com/site/calls/marathi/ecommerce-rohan-p6.mp3" },
      restaurant: { person: "Ananya", voice: "P01", duration: "1:13", src: "https://outpero.com/site/calls/marathi/restaurant-ananya-p1.mp3" },
      recruitment: { person: "Sneha", voice: "P02", duration: "1:06", src: "https://outpero.com/site/calls/marathi/recruitment-sneha-p2.mp3" }
    },
    english: {
      finance: { person: "Sneha", voice: "P02", duration: "1:07", src: "https://outpero.com/site/calls/english/finance-sneha-p2.mp3" },
      realestate: { person: "Arjun", voice: "P04", duration: "1:02", src: "https://outpero.com/site/calls/english/realestate-arjun-p4.mp3" },
      education: { person: "Kavya", voice: "P03", duration: "1:07", src: "https://outpero.com/site/calls/english/education-kavya-p3.mp3" },
      healthcare: { person: "Ananya", voice: "P01", duration: "1:04", src: "https://outpero.com/site/calls/english/healthcare-ananya-p1.mp3" },
      automotive: { person: "Vikram", voice: "P05", duration: "1:02", src: "https://outpero.com/site/calls/english/automotive-vikram-p5.mp3" },
      ecommerce: { person: "Rohan", voice: "P06", duration: "1:07", src: "https://outpero.com/site/calls/english/ecommerce-rohan-p6.mp3" },
      restaurant: { person: "Ananya", voice: "P01", duration: "1:10", src: "https://outpero.com/site/calls/english/restaurant-ananya-p1.mp3" },
      recruitment: { person: "Sneha", voice: "P02", duration: "0:57", src: "https://outpero.com/site/calls/english/recruitment-sneha-p2.mp3" }
    }
  };

  const CHANNEL_TABS_DATA = [
    {
      id: "instant",
      label: "Instant leads",
      href: "/product/instant-leads",
      title: "Call every new enquiry while they still have their phone in hand.",
      points: [
        "Fires from Meta Ads, Google Sheets, website forms or webhooks",
        "Asks your qualifying questions and books the next step",
        "Sends a WhatsApp message mid-call or right after"
      ],
      frameTitle: "Conversations",
      frameRight: `<span class="flex items-center gap-2 text-[12px] text-muted"><span class="relative inline-flex w-2 h-2"><span class="absolute inset-0 rounded-full animate-pulse-dot bg-ok"></span></span> Calling in 22s</span>`,
      frameBody: `<div class="p-5 sm:p-6">
        <div class="flex items-center justify-between text-[12.5px] text-muted pb-3 border-b border-line">
          <span>New enquiries · Meta Lead Ads</span>
          <span class="font-mono">Last 10 mins</span>
        </div>
        <div class="divide-y divide-line">
          <div class="py-3.5 flex items-center gap-3">
            <span class="grid place-items-center w-8 h-8 rounded-full bg-brand-50 text-brand-700 text-[12px] font-semibold">AM</span>
            <div class="min-w-0 flex-1">
              <div class="text-[14px] font-medium text-ink">Arjun Mehta <span class="text-muted font-normal">· 3BHK Whitefield</span></div>
              <div class="text-[12px] text-muted font-mono">Called in 19s · Hindi</div>
            </div>
            <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-ok-soft text-ok border-[#C7EBD9]">Site visit Sat 11 AM</span>
          </div>
          <div class="py-3.5 flex items-center gap-3">
            <span class="grid place-items-center w-8 h-8 rounded-full bg-brand-50 text-brand-700 text-[12px] font-semibold">PR</span>
            <div class="min-w-0 flex-1">
              <div class="text-[14px] font-medium text-ink">Priya Reddy <span class="text-muted font-normal">· 2BHK Gachibowli</span></div>
              <div class="text-[12px] text-muted font-mono">Called in 24s · Telugu</div>
            </div>
            <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-brand-50 text-brand-700 border-brand-100">On the call · 0:48</span>
          </div>
          <div class="py-3.5 flex items-center gap-3">
            <span class="grid place-items-center w-8 h-8 rounded-full bg-brand-50 text-brand-700 text-[12px] font-semibold">KS</span>
            <div class="min-w-0 flex-1">
              <div class="text-[14px] font-medium text-ink">Karthik S <span class="text-muted font-normal">· Villa Sarjapur</span></div>
              <div class="text-[12px] text-muted font-mono">Called in 21s · Kannada</div>
            </div>
            <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-ok-soft text-ok border-[#C7EBD9]">Brochure on WhatsApp</span>
          </div>
          <div class="py-3.5 flex items-center gap-3">
            <span class="grid place-items-center w-8 h-8 rounded-full bg-brand-50 text-brand-700 text-[12px] font-semibold">NK</span>
            <div class="min-w-0 flex-1">
              <div class="text-[14px] font-medium text-ink">Neha Kulkarni <span class="text-muted font-normal">· 2BHK Baner</span></div>
              <div class="text-[12px] text-muted font-mono">Called in 27s · Marathi</div>
            </div>
            <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-canvas text-ink-2 border-line">Call back 6 PM</span>
          </div>
        </div>
      </div>`
    },
    {
      id: "campaigns",
      label: "Bulk campaigns",
      href: "/product/campaigns",
      title: "Hand over the list. Get back the interested ones.",
      points: [
        "As many calls at once as you have channels",
        "Calling hours, pacing and auto-retry",
        "Edit settings while it's running"
      ],
      frameTitle: "Campaigns",
      frameRight: `<span class="flex items-center gap-2 text-[12px] text-muted"><span class="relative inline-flex w-2 h-2"><span class="absolute inset-0 rounded-full animate-pulse-dot bg-ok"></span></span> Running</span>`,
      frameBody: `<div class="p-5 sm:p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-[17px] font-semibold tracking-tight">Festive offer · past enquiries</div>
            <div class="text-[13px] text-muted mt-0.5">1,240 contacts · 10:00–19:00 · Hindi + English</div>
          </div>
          <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-brand-50 text-brand-700 border-brand-100 shrink-0">12 calls at a time</span>
        </div>
        <div class="mt-6">
          <div class="flex items-baseline justify-between text-[13px]">
            <span class="text-ink-2"><span class="font-mono font-semibold text-ink">768</span> of 1,240 called</span>
            <span class="text-muted font-mono">~43 min left</span>
          </div>
          <div class="mt-2 h-2 rounded-full bg-canvas overflow-hidden flex">
            <span class="bg-ok" style="width:7.74%"></span>
            <span class="bg-info" style="width:11.37%"></span>
            <span class="bg-line-2" style="width:17.10%"></span>
            <span class="bg-[#E9D9BB]" style="width:25.73%"></span>
          </div>
        </div>
        <div class="mt-6 grid grid-cols-2 gap-3">
          <div class="rounded-xl border border-line p-3.5">
            <div class="flex items-center gap-2 text-[12.5px] text-muted"><span class="w-2 h-2 rounded-full bg-ok"></span>Interested</div>
            <div class="flex items-baseline gap-2 mt-1"><span class="text-[22px] font-semibold font-mono tracking-tight">96</span><span class="text-[12px] text-faint font-mono">13%</span></div>
          </div>
          <div class="rounded-xl border border-line p-3.5">
            <div class="flex items-center gap-2 text-[12.5px] text-muted"><span class="w-2 h-2 rounded-full bg-info"></span>Call back</div>
            <div class="flex items-baseline gap-2 mt-1"><span class="text-[22px] font-semibold font-mono tracking-tight">141</span><span class="text-[12px] text-faint font-mono">18%</span></div>
          </div>
          <div class="rounded-xl border border-line p-3.5">
            <div class="flex items-center gap-2 text-[12.5px] text-muted"><span class="w-2 h-2 rounded-full bg-line-2"></span>Not interested</div>
            <div class="flex items-baseline gap-2 mt-1"><span class="text-[22px] font-semibold font-mono tracking-tight">212</span><span class="text-[12px] text-faint font-mono">28%</span></div>
          </div>
          <div class="rounded-xl border border-line p-3.5">
            <div class="flex items-center gap-2 text-[12.5px] text-muted"><span class="w-2 h-2 rounded-full bg-[#E9D9BB]"></span>No answer · retrying</div>
            <div class="flex items-baseline gap-2 mt-1"><span class="text-[22px] font-semibold font-mono tracking-tight">319</span><span class="text-[12px] text-faint font-mono">42%</span></div>
          </div>
        </div>
      </div>`
    },
    {
      id: "inbound",
      label: "Inbound",
      href: "/product/inbound",
      title: "Every call to your business number, answered on the first ring.",
      points: [
        "Dedicated +91 business number in one click",
        "Answers FAQs from the documents you upload",
        "Books appointments or hands off to your team"
      ],
      frameTitle: "Inbound · +91 80 4680 ••12",
      frameRight: `<span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-ok-soft text-ok border-[#C7EBD9]">24/7 active</span>`,
      frameBody: `<div class="p-5 sm:p-6">
        <div class="rounded-2xl border border-brand-200 bg-brand-50/60 p-4 flex items-center gap-3.5">
          <span class="grid place-items-center w-10 h-10 rounded-xl bg-brand-600 text-white shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 2v6h6"/><path d="m22 2-6 6"/><path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"/></svg>
          </span>
          <div class="min-w-0 flex-1">
            <div class="text-[14px] font-semibold text-ink">Incoming · +91 97••• ••812</div>
            <div class="text-[12.5px] text-muted">Answered on ring 1 · speaking Tamil</div>
          </div>
          <span class="font-mono text-[12.5px] text-brand-700">0:38</span>
        </div>
        <div class="mt-4 grid gap-2">
          <div class="flex items-center justify-between rounded-xl border border-line px-3.5 py-2.5 text-[13.5px]">
            <span class="text-ink-2">Looked up order <span class="font-mono text-ink">#48219</span></span>
            <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-ok-soft text-ok border-[#C7EBD9]">Found</span>
          </div>
          <div class="flex items-center justify-between rounded-xl border border-line px-3.5 py-2.5 text-[13.5px]">
            <span class="text-ink-2">Answered delivery status from knowledge base</span>
            <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-ok-soft text-ok border-[#C7EBD9]">Done</span>
          </div>
          <div class="flex items-center justify-between rounded-xl border border-line px-3.5 py-2.5 text-[13.5px]">
            <span class="text-ink-2">Sent tracking link on WhatsApp</span>
            <span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-ok-soft text-ok border-[#C7EBD9]">Sent</span>
          </div>
        </div>
      </div>`
    }
  ];

  // =========================================================================
  // 2. HEADER, NAV PILL, PRODUCT DROPDOWN & MOBILE MENU
  // =========================================================================
  function initHeader() {
    const header = document.querySelector("header");
    if (!header) return;
    const bar = header.firstElementChild;
    const nav = header.querySelector("nav[aria-label='Main']");
    const pill = nav ? nav.querySelector(".nav-pill") : null;
    const productWrap = nav ? nav.querySelector("div.relative") : null;
    const productBtn = productWrap ? productWrap.querySelector("button") : null;
    const mobileBtn = header.querySelector("button[aria-label='Open menu'], button[aria-label='Close menu']");

    // Scroll state
    function onScroll() {
      if (!bar) return;
      if (window.scrollY > 8) {
        bar.classList.remove("h-[60px]", "bg-paper/90", "sm:bg-paper/60", "sm:backdrop-blur-md", "border-line/70", "shadow-[0_4px_18px_-10px_rgba(30,20,60,0.18)]", "max-lg:border-b-transparent");
        bar.classList.add("h-[54px]", "bg-paper/95", "sm:bg-paper/80", "sm:backdrop-blur-xl", "border-line", "shadow-[0_10px_30px_-12px_rgba(30,20,60,0.25)]");
      } else {
        bar.classList.add("h-[60px]", "bg-paper/90", "sm:bg-paper/60", "sm:backdrop-blur-md", "border-line/70", "shadow-[0_4px_18px_-10px_rgba(30,20,60,0.18)]", "max-lg:border-b-transparent");
        bar.classList.remove("h-[54px]", "bg-paper/95", "sm:bg-paper/80", "sm:backdrop-blur-xl", "border-line", "shadow-[0_10px_30px_-12px_rgba(30,20,60,0.25)]");
      }
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    // Nav pill hover indicator
    if (nav && pill) {
      const items = Array.from(nav.children).filter(el => el !== pill);
      items.forEach(item => {
        item.addEventListener("pointerenter", () => {
          pill.style.left = item.offsetLeft + "px";
          pill.style.width = item.offsetWidth + "px";
          pill.style.opacity = "1";
        });
      });
      nav.addEventListener("pointerleave", () => {
        pill.style.opacity = "0";
      });
    }

    // Product dropdown
    if (productWrap && productBtn) {
      const dropdown = document.createElement("div");
      dropdown.className = "absolute left-0 top-full pt-2.5 hidden z-50";
      dropdown.innerHTML = `
        <div class="menu-in w-[620px] rounded-2xl border border-line bg-paper shadow-lift p-2 grid grid-cols-[1fr_200px] gap-2">
          <div class="grid gap-0.5">
            <a href="/product/instant-leads" class="group flex items-start gap-3.5 rounded-xl p-3 hover:bg-canvas transition-colors">
              <span class="grid place-items-center w-9 h-9 rounded-lg bg-brand-50 text-brand-600 group-hover:bg-brand-600 group-hover:text-white transition-colors shrink-0 mt-0.5">
                <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>
              </span>
              <span class="min-w-0">
                <span class="flex items-center gap-1.5 text-[14px] font-semibold text-ink">Instant leads</span>
                <span class="block text-[12.5px] text-muted leading-snug mt-0.5">Call every new ad or form lead within 30 seconds.</span>
              </span>
            </a>
            <a href="/product/campaigns" class="group flex items-start gap-3.5 rounded-xl p-3 hover:bg-canvas transition-colors">
              <span class="grid place-items-center w-9 h-9 rounded-lg bg-brand-50 text-brand-600 group-hover:bg-brand-600 group-hover:text-white transition-colors shrink-0 mt-0.5">
                <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 6a13 13 0 0 0 8.4-2.8A1 1 0 0 1 21 4v12a1 1 0 0 1-1.6.8A13 13 0 0 0 11 14H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"/><path d="M6 14a12 12 0 0 0 2.4 7.2 2 2 0 0 0 3.2-2.4A8 8 0 0 1 10 14"/><path d="M8 6v8"/></svg>
              </span>
              <span class="min-w-0">
                <span class="flex items-center gap-1.5 text-[14px] font-semibold text-ink">Bulk campaigns</span>
                <span class="block text-[12.5px] text-muted leading-snug mt-0.5">Upload a CSV or Google Sheet and call thousands at once.</span>
              </span>
            </a>
            <a href="/product/inbound" class="group flex items-start gap-3.5 rounded-xl p-3 hover:bg-canvas transition-colors">
              <span class="grid place-items-center w-9 h-9 rounded-lg bg-brand-50 text-brand-600 group-hover:bg-brand-600 group-hover:text-white transition-colors shrink-0 mt-0.5">
                <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 2v6h6"/><path d="m22 2-6 6"/><path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"/></svg>
              </span>
              <span class="min-w-0">
                <span class="flex items-center gap-1.5 text-[14px] font-semibold text-ink">Inbound</span>
                <span class="block text-[12.5px] text-muted leading-snug mt-0.5">A +91 business number that answers every caller 24/7.</span>
              </span>
            </a>
          </div>
          <a href="/#hear" class="rounded-xl p-4 flex flex-col justify-between text-white relative overflow-hidden group" style="background:radial-gradient(120% 120% at 100% 0%, #3E2672 0%, #1B1031 60%, #130B24 100%)">
            <div class="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-brand-300">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/></svg>
              Hear a real call
            </div>
            <div>
              <div class="text-[14px] font-semibold leading-snug">Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, English.</div>
              <div class="mt-2 inline-flex items-center gap-1 text-[12px] text-brand-200 group-hover:translate-x-0.5 transition-transform">
                Eight industries
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
              </div>
            </div>
          </a>
        </div>
      `;
      productWrap.appendChild(dropdown);
      const chevron = productBtn.querySelector("svg");

      function showProductMenu() {
        dropdown.classList.remove("hidden");
        productBtn.setAttribute("aria-expanded", "true");
        if (chevron) chevron.classList.add("rotate-180");
      }
      function hideProductMenu() {
        dropdown.classList.add("hidden");
        productBtn.setAttribute("aria-expanded", "false");
        if (chevron) chevron.classList.remove("rotate-180");
      }
      productWrap.addEventListener("pointerenter", showProductMenu);
      productWrap.addEventListener("pointerleave", hideProductMenu);
      productBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (dropdown.classList.contains("hidden")) showProductMenu();
        else hideProductMenu();
      });
      document.addEventListener("click", (e) => {
        if (!productWrap.contains(e.target)) hideProductMenu();
      });
    }

    // Mobile drawer
    if (mobileBtn) {
      const drawer = document.createElement("div");
      drawer.className = "lg:hidden fixed inset-x-0 top-14 bottom-0 z-40 bg-paper border-t border-line overflow-y-auto px-5 py-5 hidden flex-col gap-6 pointer-events-auto";
      drawer.innerHTML = `
        <div class="grid gap-1">
          <div class="t-eyebrow text-faint px-3 pb-1">Product</div>
          <a href="/product/instant-leads" class="flex items-start gap-3 rounded-xl px-3 py-2.5 hover:bg-canvas">
            <span class="grid place-items-center w-9 h-9 rounded-lg bg-brand-50 text-brand-600 shrink-0 mt-0.5">⚡</span>
            <span class="min-w-0">
              <span class="block text-[15px] font-semibold text-ink">Instant leads</span>
              <span class="block text-[13px] text-muted leading-snug">Call every new ad or form lead within 30 seconds.</span>
            </span>
          </a>
          <a href="/product/campaigns" class="flex items-start gap-3 rounded-xl px-3 py-2.5 hover:bg-canvas">
            <span class="grid place-items-center w-9 h-9 rounded-lg bg-brand-50 text-brand-600 shrink-0 mt-0.5">📣</span>
            <span class="min-w-0">
              <span class="block text-[15px] font-semibold text-ink">Bulk campaigns</span>
              <span class="block text-[13px] text-muted leading-snug">Upload a CSV or Google Sheet and call thousands at once.</span>
            </span>
          </a>
          <a href="/product/inbound" class="flex items-start gap-3 rounded-xl px-3 py-2.5 hover:bg-canvas">
            <span class="grid place-items-center w-9 h-9 rounded-lg bg-brand-50 text-brand-600 shrink-0 mt-0.5">📞</span>
            <span class="min-w-0">
              <span class="block text-[15px] font-semibold text-ink">Inbound</span>
              <span class="block text-[13px] text-muted leading-snug">A +91 business number that answers every caller 24/7.</span>
            </span>
          </a>
        </div>
        <div class="grid gap-0.5 border-t border-line pt-4">
          <a href="/voices" class="flex items-center justify-between rounded-xl px-3 py-3 text-[16px] font-medium text-ink hover:bg-canvas">Voices</a>
          <a href="/pricing" class="flex items-center justify-between rounded-xl px-3 py-3 text-[16px] font-medium text-ink hover:bg-canvas">Pricing</a>
          <a href="/contact" class="flex items-center justify-between rounded-xl px-3 py-3 text-[16px] font-medium text-ink hover:bg-canvas">Contact</a>
          <a href="/crm" class="flex items-center justify-between rounded-xl px-3 py-3 text-[16px] font-medium text-ink hover:bg-canvas">CRM Station</a>
        </div>
        <div class="mt-auto grid grid-cols-2 gap-2.5 pt-4 border-t border-line">
          <a href="/login" class="btn inline-flex items-center justify-center font-medium bg-paper text-ink border border-line h-12 rounded-xl text-[15px]">Sign in</a>
          <a href="/crm" class="btn inline-flex items-center justify-center font-medium bg-brand-600 text-white h-12 rounded-xl text-[15px]">Start free →</a>
        </div>
      `;
      header.appendChild(drawer);
      mobileBtn.addEventListener("click", () => {
        const isOpen = !drawer.classList.contains("hidden");
        if (isOpen) {
          drawer.classList.add("hidden");
          drawer.classList.remove("flex");
          document.body.style.overflow = "";
        } else {
          drawer.classList.remove("hidden");
          drawer.classList.add("flex");
          document.body.style.overflow = "hidden";
        }
      });
    }
  }

  // =========================================================================
  // 3. POINTER EFFECTS (.lift, .magnet, .tilt)
  // =========================================================================
  function initPointerEffects() {
    if (!window.matchMedia("(pointer: fine)").matches) return;
    let activeLift = null;
    let activeMagnet = null;
    let activeTilt = null;

    function onMove(e) {
      const target = e.target;
      if (!(target instanceof Element)) return;

      const lift = target.closest(".lift");
      if (lift instanceof HTMLElement) {
        const r = lift.getBoundingClientRect();
        lift.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
        lift.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
        activeLift = lift;
      }

      const magnet = target.closest(".magnet");
      if (activeMagnet && activeMagnet !== magnet) {
        activeMagnet.style.translate = "";
        activeMagnet = null;
      }
      if (magnet instanceof HTMLElement) {
        const r = magnet.getBoundingClientRect();
        const dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
        const dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
        magnet.style.translate = `${(6 * dx).toFixed(2)}px ${(5 * dy).toFixed(2)}px`;
        activeMagnet = magnet;
      }

      const tilt = target.closest(".tilt");
      if (activeTilt && activeTilt !== tilt) {
        activeTilt.style.transform = "";
        activeTilt = null;
      }
      if (tilt instanceof HTMLElement) {
        const r = tilt.getBoundingClientRect();
        const dx = (e.clientX - r.left) / r.width - 0.5;
        const dy = (e.clientY - r.top) / r.height - 0.5;
        tilt.style.transform = `perspective(1100px) rotateX(${(-3.5 * dy).toFixed(2)}deg) rotateY(${(4.5 * dx).toFixed(2)}deg)`;
        activeTilt = tilt;
      }
    }

    window.addEventListener("pointermove", onMove, { passive: true });
  }

  // =========================================================================
  // 4. HERO SECTION: GREETING ROTATOR, TYPEWRITER BRIEF, VOICE & BUILDER
  // =========================================================================
  function initHero() {
    // 1. Greeting word rotator
    const wordSpan = document.querySelector(".rise-1 span.animate-word-in");
    if (wordSpan) {
      let gIdx = 0;
      setInterval(() => {
        gIdx = (gIdx + 1) % GREETING_WORDS.length;
        const item = GREETING_WORDS[gIdx];
        wordSpan.setAttribute("lang", item.lang);
        wordSpan.textContent = item.text;
        wordSpan.classList.remove("animate-word-in");
        void wordSpan.offsetWidth;
        wordSpan.classList.add("animate-word-in");
      }, 2600);
    }

    // 2. Brief textarea typewriter & chips
    const briefInput = document.getElementById("brief");
    if (!briefInput) return;

    let phIdx = 0;
    let charIdx = 0;
    let deleting = false;
    let focused = false;
    let twTimer = null;

    function stepTypewriter() {
      if (focused || briefInput.value.length > 0) return;
      const target = BRIEF_PLACEHOLDERS[phIdx];
      if (!deleting) {
        if (charIdx < target.length) {
          charIdx++;
          briefInput.setAttribute("placeholder", target.slice(0, charIdx));
          twTimer = setTimeout(stepTypewriter, 24);
        } else {
          twTimer = setTimeout(() => {
            deleting = true;
            stepTypewriter();
          }, 2000);
        }
      } else {
        if (charIdx > 0) {
          charIdx = Math.max(0, charIdx - 3);
          briefInput.setAttribute("placeholder", target.slice(0, charIdx));
          twTimer = setTimeout(stepTypewriter, 12);
        } else {
          deleting = false;
          phIdx = (phIdx + 1) % BRIEF_PLACEHOLDERS.length;
          twTimer = setTimeout(stepTypewriter, 250);
        }
      }
    }

    briefInput.addEventListener("focus", () => {
      focused = true;
      if (twTimer) clearTimeout(twTimer);
    });
    briefInput.addEventListener("blur", () => {
      focused = false;
      if (!briefInput.value) stepTypewriter();
    });
    stepTypewriter();

    // Prompt chips ("Try: Remind about renewals", etc.)
    const form = briefInput.closest("form");
    if (form) {
      const allBtns = Array.from(form.querySelectorAll("button[type='button']"));
      allBtns.forEach(btn => {
        const label = (btn.textContent || "").trim();
        if (BRIEF_CHIPS[label]) {
          btn.addEventListener("click", () => {
            briefInput.value = BRIEF_CHIPS[label];
            briefInput.focus();
          });
        } else if (label.includes("Describe it by voice")) {
          btn.addEventListener("click", () => {
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SR) {
              try {
                const rec = new SR();
                rec.lang = "en-IN";
                btn.innerHTML = `<span class="w-2 h-2 rounded-full bg-danger animate-pulse"></span> Listening...`;
                rec.onresult = (ev) => {
                  const transcript = ev.results?.[0]?.[0]?.transcript || "";
                  if (transcript) briefInput.value = transcript;
                };
                rec.onerror = () => {
                  briefInput.value = BRIEF_CHIPS["Call new property leads"];
                };
                rec.onend = () => {
                  btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-mic text-brand-300"><path d="M12 19v3"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><rect x="9" y="2" width="6" height="13" rx="3"></rect></svg> Describe it by voice`;
                };
                rec.start();
                return;
              } catch (_) {}
            }
            briefInput.value = BRIEF_CHIPS["Call new property leads"];
            briefInput.focus();
          });
        }
      });

      // Submit handler: interactive Outpero Employee Builder inside the purple stage card
      const stageInner = form.parentElement;
      const originalStageHTML = stageInner ? stageInner.innerHTML : "";

      function attachBuilderForm() {
        const currentForm = stageInner ? stageInner.querySelector("form") : null;
        if (!currentForm) return;
        currentForm.addEventListener("submit", (e) => {
          e.preventDefault();
          const currentBrief = (stageInner.querySelector("#brief")?.value || "").trim() || BRIEF_PLACEHOLDERS[0];
          runEmployeeBuilderStage(stageInner, currentBrief, originalStageHTML, attachBuilderForm);
        });
      }
      attachBuilderForm();
    }
  }

  function runEmployeeBuilderStage(container, briefText, originalHTML, rebindFn) {
    if (!container) return;
    // Also trigger backend draft generation asynchronously
    fetch("/api/employees/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: briefText })
    }).catch(() => {});

    container.innerHTML = `
      <div class="text-left text-white py-2">
        <div class="flex items-center justify-between gap-3">
          <span class="inline-flex items-center gap-2 text-[12.5px] font-medium text-brand-200">
            <span class="w-2 h-2 rounded-full bg-ok animate-pulse"></span>
            Employee ready · Meera (Hindi + English)
          </span>
          <button type="button" id="backToBriefBtn" class="text-[12.5px] text-white/60 hover:text-white transition-colors">← Edit brief</button>
        </div>
        <h3 class="mt-3 text-[22px] sm:text-[26px] font-semibold tracking-tight">Meera is ready to call your customers</h3>
        <p class="mt-1 text-[13.5px] text-white/65 line-clamp-2">Brief: "${briefText.replace(/"/g, "&quot;")}"</p>
        <div class="mt-5 grid sm:grid-cols-3 gap-2.5">
          <div class="rounded-xl bg-white/[0.07] border border-white/15 p-3.5">
            <div class="text-[11px] font-mono uppercase tracking-wider text-brand-200">Step 1 · Greeting</div>
            <div class="mt-1 text-[13.5px] font-medium text-white">Confirms who she's speaking with &amp; asks for 2 minutes</div>
          </div>
          <div class="rounded-xl bg-white/[0.07] border border-white/15 p-3.5">
            <div class="text-[11px] font-mono uppercase tracking-wider text-brand-200">Step 2 · Qualification</div>
            <div class="mt-1 text-[13.5px] font-medium text-white">Checks requirement, budget &amp; timeline in natural Hindi/English</div>
          </div>
          <div class="rounded-xl bg-white/[0.07] border border-white/15 p-3.5">
            <div class="text-[11px] font-mono uppercase tracking-wider text-brand-200">Step 3 · Outcome</div>
            <div class="mt-1 text-[13.5px] font-medium text-white">Books calendar slot &amp; sends confirmation on WhatsApp</div>
          </div>
        </div>
        <div class="mt-5 flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-white/10">
          <button type="button" id="previewMeeraVoiceBtn" class="inline-flex items-center gap-2 h-11 px-4 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 text-[14px] font-medium text-white transition-colors">
            ▶ Hear Meera's opening line
          </button>
          <a href="/crm" class="inline-flex items-center gap-2 h-11 px-5 rounded-xl bg-white text-stage text-[14.5px] font-semibold hover:bg-brand-50 transition-colors">
            Open in app
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
          </a>
        </div>
      </div>
    `;

    const backBtn = container.querySelector("#backToBriefBtn");
    if (backBtn) {
      backBtn.addEventListener("click", () => {
        container.innerHTML = originalHTML;
        initHero();
        if (rebindFn) rebindFn();
      });
    }

    const previewBtn = container.querySelector("#previewMeeraVoiceBtn");
    if (previewBtn) {
      previewBtn.addEventListener("click", () => {
        playAudioUrl("https://outpero.com/site/calls/hindi/realestate-arjun-p4.mp3", previewBtn);
      });
    }
  }

  // =========================================================================
  // 5. "HOW IT WORKS" 7-LANGUAGE ANIMATED PHONE + CRM SIMULATOR
  // =========================================================================
  function initHowItWorks() {
    const tablist = document.querySelector("div[role='tablist'][aria-label='Call language']");
    if (!tablist) return;
    const section = tablist.closest("section");
    if (!section) return;

    const tabs = Array.from(tablist.querySelectorAll("button[role='tab']"));
    const mobileSelect = section.querySelector("select[aria-label='Call language']");
    const mobileLabelSpans = mobileSelect ? mobileSelect.parentElement.querySelectorAll("span") : [];

    // Locate phone screen & CRM card elements inside section
    const phoneFrame = section.querySelector(".w-\\[268px\\]");
    const crmFrame = section.querySelector(".tilt");
    if (!phoneFrame || !crmFrame) return;

    const phoneTimeSpan = phoneFrame.querySelector(".font-mono");
    const phoneCityNode = phoneTimeSpan ? phoneTimeSpan.parentElement?.lastElementChild : null;
    const waveBars = Array.from(phoneFrame.querySelectorAll(".bg-brand-300"));
    const chatContainer = phoneFrame.querySelector("div[lang]");

    const crmStatusBadge = crmFrame.querySelector(".ml-auto");
    const crmAvatar = crmFrame.querySelector(".w-9.h-9.rounded-full");
    const crmLeadName = crmAvatar ? crmAvatar.nextElementSibling?.firstElementChild : null;
    const crmLeadMeta = crmAvatar ? crmAvatar.nextElementSibling?.lastElementChild : null;
    const crmLangPill = crmAvatar ? crmAvatar.parentElement?.lastElementChild : null;
    const crmFieldBoxes = Array.from(crmFrame.querySelectorAll(".grid-cols-2 > div.bg-paper"));
    const crmSummaryP = crmFrame.querySelector("p.mt-4");

    let activeIdx = 0;
    let animTimers = [];

    function clearTimers() {
      animTimers.forEach(t => clearTimeout(t));
      animTimers = [];
    }

    function renderHowItWorksLanguage(idx, animate) {
      clearTimers();
      activeIdx = idx;
      const d = HOW_IT_WORKS_DATA[idx] || HOW_IT_WORKS_DATA[0];

      // Update tabs active styling
      tabs.forEach((btn, i) => {
        if (i === idx) {
          btn.setAttribute("aria-selected", "true");
          btn.className = "relative shrink-0 h-9 px-3.5 rounded-xl text-[14px] font-medium transition-colors bg-ink text-white";
        } else {
          btn.setAttribute("aria-selected", "false");
          btn.className = "relative shrink-0 h-9 px-3.5 rounded-xl text-[14px] font-medium transition-colors text-muted hover:text-ink hover:bg-canvas";
        }
      });

      if (mobileSelect) mobileSelect.value = String(idx);
      if (mobileLabelSpans.length >= 2) {
        mobileLabelSpans[0].textContent = d.label;
        mobileLabelSpans[1].textContent = d.label === d.english ? "" : d.english;
      }

      if (phoneTimeSpan) phoneTimeSpan.textContent = d.duration;
      if (phoneCityNode) {
        phoneCityNode.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-map-pin" aria-hidden="true"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"></path><circle cx="12" cy="10" r="3"></circle></svg> ${d.leadCity}`;
      }

      if (crmAvatar) crmAvatar.textContent = d.leadInitials;
      if (crmLeadName) crmLeadName.textContent = d.leadName;
      if (crmLeadMeta) crmLeadMeta.textContent = `${d.leadPhone} · Meta ad · ${d.leadCity}`;
      if (crmLangPill) crmLangPill.textContent = d.languagePill;

      function applyStep(stepCount) {
        // Render chat bubbles up to stepCount
        if (chatContainer) {
          chatContainer.setAttribute("lang", d.langAttr);
          let html = `<div class="flex-1"></div>`;
          for (let i = 0; i < stepCount; i++) {
            const turn = d.turns[i];
            const isAi = turn.from === "ai";
            const bubbleCls = isAi
              ? "self-start bg-white/[0.09] rounded-bl-md"
              : "self-end bg-brand-500/45 rounded-br-md";
            html += `<div class="contents"><div class="max-w-[88%] rounded-2xl px-3 py-1.5 text-[12px] leading-[1.45] ${bubbleCls} animate-bubble">${turn.text}</div>`;
            if (i === 4) {
              html += `<div class="self-center my-0.5 inline-flex items-center gap-1.5 rounded-full bg-ok/20 text-[#7FE0B5] px-2.5 py-1 text-[10.5px] font-medium animate-pop"><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-message-circle" aria-hidden="true"><path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719"></path></svg> Location sent on WhatsApp</div>`;
            }
            html += `</div>`;
          }
          chatContainer.innerHTML = html;
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Update waveform bars
        waveBars.forEach((bar, bIdx) => {
          if (stepCount > 0 && stepCount < 6) {
            const h = 25 + ((bIdx * 37 + stepCount * 19) % 70);
            bar.style.height = `${h}%`;
          } else {
            bar.style.height = "20%";
          }
        });

        // Update CRM fields
        crmFieldBoxes.forEach((box, fIdx) => {
          const field = d.fields[fIdx];
          if (!field) return;
          const revealed = stepCount >= field.revealAt;
          box.innerHTML = `
            <div class="text-[11.5px] text-muted">${field.k}</div>
            ${
              revealed
                ? `<div class="flex items-center gap-1.5 text-[14px] font-medium text-ink mt-0.5 animate-pop"><span class="truncate">${field.v}</span><span class="grid place-items-center w-3.5 h-3.5 rounded-full bg-ok-soft text-ok shrink-0"><svg xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg></span></div>`
                : `<div class="text-[13px] text-faint mt-0.5 italic">Listening…</div>`
            }
          `;
        });

        // Update CRM summary & top badge
        if (crmSummaryP) {
          if (stepCount >= 6) {
            crmSummaryP.className = "mt-4 text-[13.5px] leading-relaxed min-h-[44px] transition-colors text-ink-2";
            crmSummaryP.textContent = d.summary;
          } else {
            crmSummaryP.className = "mt-4 text-[13.5px] leading-relaxed min-h-[44px] transition-colors text-faint italic";
            crmSummaryP.textContent = "Writing summary as the call happens…";
          }
        }
        if (crmStatusBadge) {
          if (stepCount >= 6) {
            crmStatusBadge.innerHTML = `<span class="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px] font-medium leading-none bg-ok-soft text-ok border-[#C7EBD9]"><svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg> Site visit booked</span>`;
          } else {
            crmStatusBadge.innerHTML = `<span class="flex items-center gap-1.5 text-[12px] text-muted"><span class="relative inline-flex w-2 h-2"><span class="absolute inset-0 rounded-full animate-pulse-dot bg-ok"></span></span> Live · ${d.duration}</span>`;
          }
        }
      }

      if (!animate) {
        applyStep(6);
      } else {
        applyStep(1);
        [2, 3, 4, 5, 6].forEach((step, idxStep) => {
          const t = setTimeout(() => applyStep(step), (idxStep + 1) * 900);
          animTimers.push(t);
        });
      }
    }

    tabs.forEach((btn, idx) => {
      btn.addEventListener("click", () => renderHowItWorksLanguage(idx, true));
    });
    if (mobileSelect) {
      mobileSelect.addEventListener("change", () => {
        renderHowItWorksLanguage(Number(mobileSelect.value) || 0, true);
      });
    }
  }

  // =========================================================================
  // 6. "HEAR OUR VOICES" 7-LANGUAGE x 8-INDUSTRY AUDIO PLAYER
  // =========================================================================
  let sharedAudio = null;
  let activePlayButton = null;
  let activeProgressInterval = null;

  function formatMMSS(sec) {
    if (!isFinite(sec) || sec < 0) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  }

  function stopCurrentAudio() {
    if (sharedAudio) {
      sharedAudio.pause();
      sharedAudio = null;
    }
    if (activeProgressInterval) {
      clearInterval(activeProgressInterval);
      activeProgressInterval = null;
    }
    if (activePlayButton) {
      activePlayButton.setAttribute("aria-pressed", "false");
      activePlayButton.classList.remove("border-brand-300", "shadow-lift", "ring-1", "ring-brand-200");
      const iconWrap = activePlayButton.querySelector(".w-9.h-9.rounded-full, .w-8.h-8.rounded-full");
      if (iconWrap) {
        iconWrap.classList.remove("bg-brand-600");
        iconWrap.classList.add("bg-ink");
        iconWrap.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-play ml-0.5"><path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"></path></svg>`;
      }
      const bars = activePlayButton.querySelectorAll(".h-7 > span");
      bars.forEach(b => {
        b.classList.remove("bg-brand-600");
        b.classList.add("bg-line-2");
      });
      activePlayButton = null;
    }
  }

  function playAudioUrl(url, cardBtn) {
    if (activePlayButton === cardBtn && sharedAudio && !sharedAudio.paused) {
      stopCurrentAudio();
      return;
    }
    stopCurrentAudio();

    const audio = new Audio(url);
    sharedAudio = audio;
    activePlayButton = cardBtn;
    cardBtn.setAttribute("aria-pressed", "true");
    cardBtn.classList.add("border-brand-300", "shadow-lift", "ring-1", "ring-brand-200");

    const iconWrap = cardBtn.querySelector(".w-9.h-9.rounded-full, .w-8.h-8.rounded-full");
    if (iconWrap) {
      iconWrap.classList.remove("bg-ink");
      iconWrap.classList.add("bg-brand-600");
      iconWrap.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-pause"><rect x="14" y="3" width="5" height="18" rx="1"></rect><rect x="5" y="3" width="5" height="18" rx="1"></rect></svg>`;
    }

    const bars = Array.from(cardBtn.querySelectorAll(".h-7 > span"));
    const durationSpan = cardBtn.querySelector(".font-mono.text-\\[12px\\]");
    const defaultDurationText = durationSpan ? durationSpan.textContent : "1:10";

    audio.play().catch(async () => {
      // Fallback to local TTS endpoint if external audio blocked/offline
      try {
        const resp = await fetch("/api/tts/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            speaker: "kavitha_te_conversation",
            text: "నమస్కారం అండి! నేను మీరా, నెస్ట్ రియాల్టీ నుండి మాట్లాడుతున్నాను. రెండు నిమిషాలు మాట్లాడవచ్చా?"
          })
        });
        if (resp.ok) {
          const blob = await resp.blob();
          audio.src = URL.createObjectURL(blob);
          audio.play().catch(() => stopCurrentAudio());
        } else {
          stopCurrentAudio();
        }
      } catch (_) {
        stopCurrentAudio();
      }
    });

    activeProgressInterval = setInterval(() => {
      if (!sharedAudio || sharedAudio.paused) return;
      const ratio = sharedAudio.duration ? sharedAudio.currentTime / sharedAudio.duration : 0;
      const litCount = Math.floor(ratio * bars.length);
      bars.forEach((b, idx) => {
        if (idx <= litCount) {
          b.classList.remove("bg-line-2");
          b.classList.add("bg-brand-600");
        } else {
          b.classList.remove("bg-brand-600");
          b.classList.add("bg-line-2");
        }
      });
      if (durationSpan && sharedAudio.currentTime > 0) {
        durationSpan.textContent = formatMMSS(sharedAudio.currentTime);
      }
    }, 100);

    audio.addEventListener("ended", () => {
      if (durationSpan) durationSpan.textContent = defaultDurationText;
      stopCurrentAudio();
    });
  }

  function initVoicePlayers() {
    const langKeys = ["hindi", "telugu", "tamil", "kannada", "malayalam", "marathi", "english"];
    const langLabels = [
      { native: "हिन्दी", en: "Hindi" },
      { native: "తెలుగు", en: "Telugu" },
      { native: "தமிழ்", en: "Tamil" },
      { native: "ಕನ್ನಡ", en: "Kannada" },
      { native: "മലയാളം", en: "Malayalam" },
      { native: "मराठी", en: "Marathi" },
      { native: "English", en: "English" }
    ];

    // Find all 8-industry voice sections (on "/" #hear and on "/voices")
    const languageTablists = Array.from(document.querySelectorAll("div[role='tablist'][aria-label='Language']"));
    languageTablists.forEach(tablist => {
      const container = tablist.parentElement?.parentElement;
      if (!container) return;
      const cards = Array.from(container.querySelectorAll("button[aria-pressed]"));
      if (cards.length !== 8) return; // 8-industry grid

      const tabs = Array.from(tablist.querySelectorAll("button[role='tab']"));
      const mobileSelect = container.querySelector("select[aria-label='Language']");
      const mobileLabelSpans = mobileSelect ? mobileSelect.parentElement.querySelectorAll("span") : [];

      let currentLang = "hindi";

      function updateIndustryCards(langKey) {
        stopCurrentAudio();
        currentLang = langKey;
        const clips = CALL_CLIPS[langKey] || CALL_CLIPS.hindi;
        const lIdx = Math.max(0, langKeys.indexOf(langKey));

        tabs.forEach((btn, i) => {
          if (i === lIdx) {
            btn.setAttribute("aria-selected", "true");
            btn.className = "shrink-0 h-9 px-3.5 rounded-xl text-[14px] font-medium transition-colors bg-ink text-white";
          } else {
            btn.setAttribute("aria-selected", "false");
            btn.className = "shrink-0 h-9 px-3.5 rounded-xl text-[14px] font-medium transition-colors text-muted hover:text-ink hover:bg-canvas";
          }
        });

        if (mobileSelect) mobileSelect.value = langKey;
        if (mobileLabelSpans.length >= 2) {
          mobileLabelSpans[0].textContent = langLabels[lIdx].native;
          mobileLabelSpans[1].textContent = langLabels[lIdx].native === langLabels[lIdx].en ? "" : langLabels[lIdx].en;
        }

        cards.forEach((card, cIdx) => {
          const ind = CALL_INDUSTRIES[cIdx];
          const clip = clips[ind.key];
          if (!clip) return;
          card.dataset.audioSrc = clip.src;
          const durEl = card.querySelector(".font-mono.text-\\[12px\\]");
          if (durEl) durEl.textContent = clip.duration;
          const avatarEl = card.querySelector(".w-6.h-6.rounded-full");
          if (avatarEl) avatarEl.textContent = clip.person[0];
          const personWrap = avatarEl ? avatarEl.nextElementSibling : null;
          if (personWrap) {
            personWrap.innerHTML = `<span class="text-ink-2 font-medium">${clip.person}</span> · Voice <span class="font-mono">${clip.voice}</span>`;
          }
        });
      }

      tabs.forEach((btn, idx) => {
        btn.addEventListener("click", () => updateIndustryCards(langKeys[idx]));
      });
      if (mobileSelect) {
        mobileSelect.addEventListener("change", () => updateIndustryCards(mobileSelect.value));
      }
      cards.forEach((card, cIdx) => {
        const ind = CALL_INDUSTRIES[cIdx];
        card.dataset.audioSrc = CALL_CLIPS.hindi[ind.key].src;
        card.addEventListener("click", () => {
          playAudioUrl(card.dataset.audioSrc || CALL_CLIPS[currentLang][ind.key].src, card);
        });
      });
    });

    // Also wire the "#listen" individual voice catalog on /voices if present
    const listenSection = document.getElementById("listen");
    if (listenSection) {
      const tablist = listenSection.querySelector("div[role='tablist'][aria-label='Language']");
      const voiceCards = Array.from(listenSection.querySelectorAll("button[aria-pressed]"));
      if (tablist && voiceCards.length > 0 && voiceCards.length !== 8) {
        const tabs = Array.from(tablist.querySelectorAll("button[role='tab']"));
        let activeLang = "hindi";
        const fallbackPool = Object.values(CALL_CLIPS.hindi);
        tabs.forEach((btn, idx) => {
          btn.addEventListener("click", () => {
            stopCurrentAudio();
            activeLang = langKeys[idx] || "hindi";
            tabs.forEach((b, i) => {
              b.setAttribute("aria-selected", i === idx ? "true" : "false");
              b.className = i === idx
                ? "shrink-0 h-9 px-3.5 rounded-xl text-[14px] font-medium transition-colors bg-ink text-white"
                : "shrink-0 h-9 px-3.5 rounded-xl text-[14px] font-medium transition-colors text-muted hover:text-ink hover:bg-canvas";
            });
          });
        });
        voiceCards.forEach((card, idx) => {
          card.addEventListener("click", () => {
            const clipsObj = CALL_CLIPS[activeLang] || CALL_CLIPS.hindi;
            const clipsArr = Object.values(clipsObj);
            const clip = clipsArr[idx % clipsArr.length] || fallbackPool[0];
            playAudioUrl(clip.src, card);
          });
        });
      }
    }
  }

  // =========================================================================
  // 7. "ONE OUTPERO EMPLOYEE, EVERY CHANNEL" 3-TAB SWITCHER
  // =========================================================================
  function initChannelTabs() {
    const tablist = document.querySelector("div[role='tablist'][aria-label='Channels']");
    if (!tablist) return;
    const tabs = Array.from(tablist.querySelectorAll("button[role='tab']"));
    const contentGrid = tablist.nextElementSibling;
    if (!contentGrid || tabs.length !== 3) return;

    const leftCol = contentGrid.firstElementChild;
    const rightCol = contentGrid.lastElementChild;
    if (!leftCol || !rightCol) return;

    function selectChannel(idx) {
      const d = CHANNEL_TABS_DATA[idx] || CHANNEL_TABS_DATA[0];
      tabs.forEach((btn, i) => {
        const isActive = i === idx;
        btn.setAttribute("aria-selected", isActive ? "true" : "false");
        btn.className = isActive
          ? "flex items-center gap-3 rounded-2xl border p-3 sm:p-4 text-left transition-[background-color,border-color,box-shadow] bg-paper border-brand-300 shadow-lift ring-1 ring-brand-200"
          : "flex items-center gap-3 rounded-2xl border p-3 sm:p-4 text-left transition-[background-color,border-color,box-shadow] bg-canvas border-line hover:bg-paper hover:border-line-2";
        const iconSpan = btn.firstElementChild;
        if (iconSpan) {
          iconSpan.className = isActive
            ? "grid place-items-center w-9 h-9 sm:w-10 sm:h-10 rounded-xl shrink-0 transition-colors bg-brand-600 text-white"
            : "grid place-items-center w-9 h-9 sm:w-10 sm:h-10 rounded-xl shrink-0 transition-colors bg-paper border border-line text-muted";
        }
      });

      leftCol.innerHTML = `
        <h3 class="text-[26px] sm:text-[30px] leading-[1.1] tracking-[-0.03em] font-semibold text-ink text-balance">${d.title}</h3>
        <ul class="mt-5 grid gap-3">
          ${d.points
            .map(
              p => `<li class="flex items-center gap-3 text-[15px] text-ink-2"><span class="grid place-items-center w-5 h-5 rounded-full bg-brand-50 text-brand-600"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg></span>${p}</li>`
            )
            .join("")}
        </ul>
        <a class="inline-flex items-center min-h-11 sm:min-h-0 gap-1.5 mt-6 text-[14.5px] font-medium text-brand-700 hover:text-brand-800 group" href="${d.href}">
          Explore ${d.label.toLowerCase()}
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-arrow-right transition-transform group-hover:translate-x-0.5"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
        </a>
      `;

      const tiltFrame = rightCol.querySelector(".tilt");
      if (tiltFrame) {
        tiltFrame.innerHTML = `
          <div class="flex items-center gap-3 h-11 px-4 border-b border-line bg-paper">
            <span class="hidden sm:flex gap-1.5" aria-hidden="true">
              <span class="w-2.5 h-2.5 rounded-full bg-line"></span>
              <span class="w-2.5 h-2.5 rounded-full bg-line"></span>
              <span class="w-2.5 h-2.5 rounded-full bg-line"></span>
            </span>
            <img alt="Outpero" width="67" height="12" class="shrink-0 ml-1" src="/static/site/brand/outpero-wordmark.png"/>
            <span class="text-line-2 -mx-1">/</span>
            <span class="min-w-0 text-[13px] text-muted font-medium truncate">${d.frameTitle}</span>
            <span class="ml-auto shrink-0 whitespace-nowrap">${d.frameRight}</span>
          </div>
          ${d.frameBody}
        `;
      }
    }

    tabs.forEach((btn, idx) => {
      btn.addEventListener("click", () => selectChannel(idx));
    });
  }

  // =========================================================================
  // 8. SUB-PAGE WIDGETS (/pricing CALCULATOR, /voices ENHANCE, /contact FORM)
  // =========================================================================
  function initSubpageWidgets() {
    // 1. Pricing calculator (#calls, #mins, Standard / Premium)
    const callsInput = document.getElementById("calls");
    const minsInput = document.getElementById("mins");
    if (callsInput && minsInput) {
      const calcSection = callsInput.closest("section");
      const callsValSpan = callsInput.previousElementSibling?.querySelector(".font-mono");
      const minsValSpan = minsInput.previousElementSibling?.querySelector(".font-mono");
      const radioBtns = calcSection ? Array.from(calcSection.querySelectorAll("button[role='radio']")) : [];
      const rightPanel = calcSection ? calcSection.querySelector(".text-white.flex.flex-col") : null;
      let ratePerMin = 5;

      function updatePricingCalc() {
        const calls = Number(callsInput.value) || 2000;
        const mins = Number(minsInput.value) || 1.5;
        if (callsValSpan) callsValSpan.textContent = calls.toLocaleString("en-IN");
        if (minsValSpan) minsValSpan.textContent = String(mins);

        const talkTimeCost = Math.round(calls * mins * ratePerMin);
        const numberCost = 649;
        const totalCost = talkTimeCost + numberCost;
        const perCall = Math.max(1, Math.round(totalCost / calls));

        if (rightPanel) {
          const bigTotal = rightPanel.querySelector(".text-\\[44px\\]");
          const dds = rightPanel.querySelectorAll("dd.font-mono");
          if (bigTotal) bigTotal.textContent = "₹" + totalCost.toLocaleString("en-IN");
          if (dds.length >= 3) {
            dds[0].textContent = "₹" + talkTimeCost.toLocaleString("en-IN");
            dds[1].textContent = "₹" + numberCost.toLocaleString("en-IN");
            dds[2].textContent = "₹" + perCall.toLocaleString("en-IN");
          }
        }
      }

      callsInput.addEventListener("input", updatePricingCalc);
      minsInput.addEventListener("input", updatePricingCalc);
      radioBtns.forEach((btn, idx) => {
        btn.addEventListener("click", () => {
          ratePerMin = idx === 0 ? 5 : 6.8;
          radioBtns.forEach((b, i) => {
            const checked = i === idx;
            b.setAttribute("aria-checked", checked ? "true" : "false");
            b.className = checked
              ? "rounded-xl border px-3 py-2.5 text-left transition-colors border-brand-300 bg-brand-50 ring-1 ring-brand-200"
              : "rounded-xl border px-3 py-2.5 text-left transition-colors border-line hover:border-line-2";
          });
          updatePricingCalc();
        });
      });
    }

    // 2. Channels +/- counter (#channels on /pricing)
    const channelsSec = document.getElementById("channels");
    if (channelsSec) {
      const btns = Array.from(channelsSec.querySelectorAll("button[type='button']"));
      const bigNum = channelsSec.querySelector(".text-\\[38px\\], .text-\\[36px\\], .text-\\[34px\\], .font-mono.text-\\[28px\\]");
      const statCards = Array.from(channelsSec.querySelectorAll(".bg-white\\/\\[0\\.06\\] .text-\\[26px\\]"));
      let chCount = 3;
      if (btns.length >= 2 && statCards.length >= 2) {
        const updateCh = () => {
          const numDisplay = btns[0].nextElementSibling;
          if (numDisplay) numDisplay.textContent = String(chCount);
          const hrs = Math.max(1, Math.round(18 / chCount));
          statCards[0].textContent = `~${hrs} hr${hrs > 1 ? "s" : ""}`;
          statCards[1].textContent = "₹" + (chCount * 649).toLocaleString("en-IN");
        };
        btns[0].addEventListener("click", () => {
          chCount = Math.max(1, chCount - 1);
          updateCh();
        });
        btns[1].addEventListener("click", () => {
          chCount = Math.min(30, chCount + 1);
          updateCh();
        });
      }
    }

    // 3. "Enhance" widget on /voices
    const enhanceBtn = Array.from(document.querySelectorAll("button[aria-pressed]")).find(b =>
      (b.textContent || "").includes("Enhanced")
    );
    if (enhanceBtn) {
      const card = enhanceBtn.closest(".rounded-\\[28px\\]");
      const tablist = card ? card.querySelector("div[role='tablist']") : null;
      const tabs = tablist ? Array.from(tablist.querySelectorAll("button[role='tab']")) : [];
      const bodyP = card ? card.querySelector("p.text-\\[19px\\]") : null;
      const eyebrow = bodyP ? bodyP.previousElementSibling : null;
      const ENHANCE_SAMPLES = [
        {
          plain: "Hello! You had enquired. Can you come on Saturday at 11 AM? Budget is ₹85,00,000.",
          enhanced: `<mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">Namaste ji! </mark><span>Aapne enquiry ki thi. Kya aap Saturday </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">subah 11 baje</mark><span> aa payenge? Budget </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">pachasi lakh</mark><span> hai.</span>`
        },
        {
          plain: "Namaskaram! Meeru enquiry chesaru. Saturday 11 AM ki vastara? Price ₹85,00,000.",
          enhanced: `<mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">నమస్కారం అండి! </mark><span>మీరు enquiry చేశారు కదా. Saturday </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">ఉదయం 11 గంటలకు</mark><span> రాగలరా అండి? ధర </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">85 లక్షలు</mark><span>.</span>`
        },
        {
          plain: "Vanakkam! Neenga enquiry pannirundheenga. Saturday 11 AM vara mudiyuma? Price ₹85,00,000.",
          enhanced: `<mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">வணக்கம் சார்! </mark><span>நீங்க enquiry பண்ணிருந்தீங்க. Saturday </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">காலைல 11 மணிக்கு</mark><span> வர முடியுமாங்க? விலை </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">85 லட்சம்</mark><span>.</span>`
        },
        {
          plain: "Namaskar! Tumhi चौकशी keli hoti. Saturday 11 AM la yeil ka? Kimmat ₹85,00,000.",
          enhanced: `<mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">नमस्कार सर! </mark><span>तुम्ही चौकशी केली होती. Saturday </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">सकाळी 11 वाजता</mark><span> येणं जमेल का? किंमत </span><mark class="bg-brand-100 text-brand-800 rounded-md px-1 font-medium">पंच्याऐंशी लाख</mark><span> आहे.</span>`
        }
      ];
      let eIdx = 0;
      let isEnhanced = true;
      const renderEnhance = () => {
        const s = ENHANCE_SAMPLES[eIdx] || ENHANCE_SAMPLES[0];
        if (eyebrow) eyebrow.textContent = isEnhanced ? "After Enhance" : "Before Enhance (plain script)";
        if (bodyP) bodyP.innerHTML = isEnhanced ? s.enhanced : s.plain;
        enhanceBtn.setAttribute("aria-pressed", isEnhanced ? "true" : "false");
        tabs.forEach((b, i) => {
          b.setAttribute("aria-selected", i === eIdx ? "true" : "false");
          b.className = i === eIdx
            ? "h-8 px-3 rounded-lg text-[13.5px] font-medium transition-colors bg-ink text-white"
            : "h-8 px-3 rounded-lg text-[13.5px] font-medium transition-colors text-muted hover:text-ink";
        });
      };
      tabs.forEach((b, i) => {
        b.addEventListener("click", () => {
          eIdx = i;
          renderEnhance();
        });
      });
      enhanceBtn.addEventListener("click", () => {
        isEnhanced = !isEnhanced;
        renderEnhance();
      });
    }

    // 4. Contact form handler (/contact)
    const contactForm = document.querySelector("form input[name='business']")?.closest("form");
    if (contactForm) {
      contactForm.addEventListener("submit", (e) => {
        e.preventDefault();
        contactForm.innerHTML = `
          <div class="py-10 text-center">
            <div class="mx-auto grid place-items-center w-12 h-12 rounded-2xl bg-ok-soft text-ok mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            </div>
            <div class="text-[20px] font-semibold text-ink">We got your message</div>
            <p class="mt-1 text-[14.5px] text-muted">Thanks — we'll get back to you within one business day.</p>
          </div>
        `;
      });
    }
  }

  // =========================================================================
  // BOOTSTRAP ON DOM READY
  // =========================================================================
  function initAll() {
    initHeader();
    initPointerEffects();
    initHero();
    initHowItWorks();
    initVoicePlayers();
    initChannelTabs();
    initSubpageWidgets();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
