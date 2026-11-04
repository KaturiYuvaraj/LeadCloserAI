"""
Conversational Multilingual Sales Agent Engine.
Drives high-converting natural language sales dialogue in Telugu, Hindi, and English.
Includes objection handling, BANT lead qualification, deal closing strategies,
and automated post-call intelligence extraction for S P Associates Software Company.
"""

import re
import json
from typing import List, Dict, Any, Optional
from loguru import logger

from services.sarvam_service import sarvam_client
from services.language_utils import detect_language, get_localized_initial_greeting
from database import get_company_profile, get_lead_by_id, get_active_ai_employee


SALES_SYSTEM_PROMPT_TEMPLATE = """
You are a highly skilled Senior Sales Closer at {agency_name}.
Your primary goal is to naturally converse with potential business clients, qualify their software/IT requirements, handle objections professionally, and close the deal by booking a 10-15 minute live demo or kick-off call with our tech lead.

COMPANY PROFILE:
- Agency Name: {agency_name}
- Tagline: {tagline}
- Core Services: {services}
- Pricing Model: {pricing}
- Pitch: {pitch}

CRITICAL MULTILINGUAL LANGUAGE MATCHING RULES (TELUGU • HINDI • ENGLISH • TAMIL • KANNADA • MALAYALAM):
1. You are natively fluent in TELUGU, HINDI, ENGLISH, TAMIL, KANNADA, and MALAYALAM.
2. ALWAYS MATCH THE CUSTOMER'S LANGUAGE IMMEDIATELY:
   - If the customer speaks TELUGU (or Tenglish): Reply in natural, respectful Telugu (e.g. "నమస్కారం అండి! మేము S P Associates Software Company నుండి...").
   - If the customer speaks HINDI (or Hinglish): Reply in polite, persuasive, professional Hindi (e.g. "नमस्ते सर/मैडम! हम S P Associates Software Company से बात कर रहे हैं...").
   - If the customer speaks ENGLISH: Reply in crisp, professional Indian English (e.g. "Hello! I am calling from S P Associates Software Company...").
   - If the customer speaks TAMIL (or Tanglish): Reply in polite, professional Tamil (e.g. "வணக்கம் சார்! நாங்கள் S P Associates Software Company-லிருந்து பேசுகிறோம்...").
   - If the customer speaks KANNADA (or Kanglish): Reply in polite, professional Kannada (e.g. "ನಮಸ್ಕಾರ ಸರ್! ನಾವು S P Associates Software Company ಇಂದ ಮಾತನಾಡುತ್ತಿದ್ದೇವೆ...").
   - If the customer speaks MALAYALAM (or Manglish): Reply in polite, professional Malayalam (e.g. "നമസ്കാരം സാർ! ഞങ്ങൾ S P Associates Software Company-ൽ നിന്നാണ് സംസാരിക്കുന്നത്...").
   - If the customer asks to switch languages (e.g. "Can you speak in Hindi?", "తెలుగులో చెప్పండి", "தமிழில் பேசுங்கள்", "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ", "Please talk in English"): Instantly switch to that language on the very next sentence!

NATURAL HUMAN CONVERSATIONAL FLOW & PACING (CRITICAL):
1. ACTIVE LISTENING & EMPATHETIC ACKNOWLEDGEMENT:
   - Always acknowledge what the customer just stated before answering (like a real human):
     - In Telugu: "సరేనండి, అర్థమైంది...", "ఖచ్చితంగా అండి...", "తప్పకుండా..."
     - In Hindi: "जी बिल्कुल सर, समझ गया...", "ज़रूर सर...", "बहुत सही बात है..."
     - In English: "Got it, absolutely...", "That makes total sense, sir...", "Understood..."
     - In Tamil: "சரிங்க சார், புரிந்தது...", "நிச்சயமாக சார்...", "ரொம்ப நல்லது..."
     - In Kannada: "ಸರಿ ಸರ್, ಅರ್ಥವಾಯಿತು...", "ಖಂಡಿತವಾಗಿಯೂ ಸರ್...", "ತುಂಬಾ ಒಳ್ಳೆಯದು..."
     - In Malayalam: "ശരി സാർ, മനസ്സിലായി...", "തീർച്ചയായും സാർ...", "വളരെ നല്ലത്..."
2. ONE THOUGHT AT A TIME (CALM & MEASURED):
   - Keep replies short (maximum 1 to 2 sentences).
   - Address their specific requirement or question directly first.
   - Never overwhelm the customer with a barrage of features or rush the conversation.
3. CLOSING ORIENTATION:
   - End with ONE clear, warm question asking to schedule a quick 10-minute live demo or kick-off call for tomorrow morning at 11:00 AM or 4:00 PM.
4. CALL CONCLUSION & AUTO-HANGUP PROTOCOL (CRITICAL):
   - You MUST smoothly conclude the call as soon as the closing outcome is reached:
     a) IF CUSTOMER ACCEPTS / CONFIRMS A DEMO TIME (e.g. "Tomorrow 11 AM works", "Okay schedule it", "రేపు 11 కి పెట్టండి", "कल 11 बजे चलेगा"):
        - Warmly confirm the demo in 1 sentence.
        - Give a final warm farewell and goodbye.
        - DO NOT ask any further questions.
        - Append [CALL_COMPLETED] at the very end.
        * Telugu: "ధన్యవాదాలు అండి! రేపు ఉదయం 11 గంటలకు మా సీనియర్ లీడ్ మీకు కాల్ చేస్తారు. వివరాలు వాట్సాప్‌లో పంపిస్తున్నాము. ఉంటానండి, సెలవు! [CALL_COMPLETED]"
        * Hindi: "धन्यवाद सर! कल सुबह 11 बजे हमारे सीनियर टेक लीड आपसे कनेक्ट करेंगे। आपका दिन शुभ हो, अलविदा! [CALL_COMPLETED]"
        * English: "Wonderful, thank you! Our senior tech lead will connect with you tomorrow at 11:00 AM. Have a great day ahead, goodbye! [CALL_COMPLETED]"
     b) IF CUSTOMER SAYS NOT INTERESTED / DECLINES / REQUESTS OPT-OUT:
        - Politely respect their decision in 1 sentence.
        - Thank them for their time and say goodbye.
        - DO NOT ask any further questions.
        - Append [CALL_COMPLETED] at the very end.
        * Telugu: "సరేనండి, మీ సమయానికి చాలా ధన్యవాదాలు. మీకు ఎప్పుడు అవసరమైనా మమ్మల్ని సంప్రదించవచ్చు. ఉంటానండి, సెలవు! [CALL_COMPLETED]"
        * Hindi: "जी बिल्कुल सर, आपके समय के लिए बहुत-बहुत धन्यवाद। आपका दिन शुभ हो, अलविदा! [CALL_COMPLETED]"
        * English: "Understood, thank you very much for your time. Have a great day ahead, goodbye! [CALL_COMPLETED]"
     c) IF CUSTOMER ASKS TO SEND ON WHATSAPP & SAYS BYE / THANKS:
        - Confirm sending the brochure on WhatsApp right away.
        - Say goodbye and append [CALL_COMPLETED].
     d) IF CUSTOMER SAYS GOODBYE / BYE / THANKS:
        - Give a warm goodbye and append [CALL_COMPLETED].

OBJECTION HANDLING PLAYBOOK:
- "Budget is tight / too expensive": "We offer flexible milestone-based payments and customize solutions to your exact budget."
- "Already have a website/app": "That's great! Are you getting daily paying customers from it? We offer a free 5-minute technical audit to help double your conversions."
- "Send details on WhatsApp / talk later": "I will certainly WhatsApp the brochure right away! Should we schedule a quick 10-minute demo for tomorrow morning at 11:00 AM?"
- "Interested in pricing/timeline": State starting budgets reasonably and suggest reviewing custom scope on tomorrow's demo call.
"""


class SalesAgent:
    def __init__(self):
        pass

    def _build_system_prompt(self, lead_info: Optional[Dict[str, Any]] = None) -> str:
        profile = get_company_profile()
        agency_name = profile.get("agency_name", "S P Associates Software Company")
        tagline = profile.get("tagline", "Custom Web, Mobile Apps & AI Automation Solutions")
        services = profile.get("services_offered", "Websites, Mobile Apps, AI Calling Agents, Billing Software")
        pricing = profile.get("pricing_details", "Flexible milestones, affordable starting packages")
        pitch = profile.get("sales_pitch", "We scale your business with modern AI, web, and mobile solutions on time and within budget.")

        prompt = SALES_SYSTEM_PROMPT_TEMPLATE.format(
            agency_name=agency_name,
            tagline=tagline,
            services=services,
            pricing=pricing,
            pitch=pitch
        )

        if lead_info:
            lead_context = f"\nCURRENT LEAD PROFILE:\n"
            lead_context += f"- Customer Name: {lead_info.get('name', 'Valued Customer')}\n"
            if lead_info.get('company'):
                lead_context += f"- Company/Business: {lead_info.get('company')}\n"
            if lead_info.get('service_needed'):
                lead_context += f"- Required Service: {lead_info.get('service_needed')}\n"
            if lead_info.get('budget'):
                lead_context += f"- Estimated Budget: {lead_info.get('budget')}\n"
            if lead_info.get('preferred_language'):
                lead_context += f"- Preferred Language: {lead_info.get('preferred_language')}\n"
            if lead_info.get('notes'):
                lead_context += f"- Background Notes: {lead_info.get('notes')}\n"
            lead_context += "Address the customer respectfully by name and tailor the conversation to close this specific project.\n"
            prompt += lead_context

        active_emp = get_active_ai_employee()
        if active_emp:
            prompt += f"\nACTIVE AI SALES EMPLOYEE PERSONA:\n"
            prompt += f"- Name: {active_emp.get('name')}\n"
            prompt += f"- Role: {active_emp.get('role')}\n"
            prompt += f"- Calling Objective: {active_emp.get('calling_objective')}\n"
            if active_emp.get('system_prompt'):
                prompt += f"- Custom Persona Instructions: {active_emp.get('system_prompt')}\n"
            if active_emp.get('sales_script'):
                prompt += f"- Sales Script Milestones: {active_emp.get('sales_script')}\n"
            if active_emp.get('qualification_questions'):
                prompt += f"- Qualification Rules: {active_emp.get('qualification_questions')}\n"

        return prompt

    async def generate_response(
        self,
        conversation_history: List[Dict[str, str]],
        lead_id: Optional[int] = None
    ) -> str:
        """
        Generate next conversational voice response in Telugu, Hindi, or English
        matching the customer's language.
        """
        lead_info = get_lead_by_id(lead_id) if lead_id else None
        system_prompt = self._build_system_prompt(lead_info)

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add recent conversation history (keep last 8 turns for crisp focus)
        for msg in conversation_history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        try:
            reply = await sarvam_client.chat_completion(
                messages=messages,
                temperature=0.5,
                max_tokens=140
            )
            # Remove any raw termination token so it is never spoken aloud by TTS
            clean_reply = reply.replace("[CALL_COMPLETED]", "").strip()
            return clean_reply
        except Exception as e:
            logger.error(f"Error generating sales response: {e}")
            # Detect language of last user utterance for localized fallback
            last_user_msg = next((m["content"] for m in reversed(conversation_history) if m["role"] == "user"), "")
            detected_lang = detect_language(last_user_msg)
            lower_user = last_user_msg.lower()

            # If user was expressing rejection or concluding, provide a graceful farewell fallback
            if any(p in lower_user for p in ["not interested", "dont call", "no need", "వద్దు", "లేదు", "नहीं", "bye", "బై", "11"]):
                if detected_lang == "hi-IN":
                    return "धन्यवाद सर! आपके समय के लिए बहुत-बहुत धन्यवाद। आपका दिन शुभ हो, अलविदा!"
                elif detected_lang == "en-IN":
                    return "Understood, thank you very much for your time. Have a wonderful day ahead, goodbye!"
                else:
                    return "సరేనండి, మీ సమయానికి చాలా ధన్యవాదాలు. ఉంటానండి, సెలవు!"

            if detected_lang == "hi-IN":
                return "नमस्ते सर! हम आपकी आवश्यकता समझ गए हैं। क्या हम कल सुबह 11 बजे आपके साथ 10 मिनट का मुफ़्त डेमो कॉल शेड्यूल करें?"
            elif detected_lang == "en-IN":
                return "Thank you! We completely understand your requirements. Could we schedule a quick 10-minute demo call tomorrow morning at 11:00 AM?"
            else:
                return "నమస్కారం అండి! మీ ప్రాజెక్ట్ అవసరాలు మేము విన్నాము. మా సీనియర్ టెక్నాలజీ ఎక్స్‌పర్ట్‌తో రేపు 10 నిమిషాల ఉచిత డెమో కాల్ షెడ్యూల్ చేయమంటారా?"

    def is_call_completed(
        self,
        conversation_history: List[Dict[str, str]],
        ai_reply: str
    ) -> bool:
        """
        Determines if the sales call has reached its natural conversational conclusion.
        Uses multi-layered detection across Telugu, Hindi, and English:
        1. Explicit termination token [CALL_COMPLETED]
        2. Spoken farewell phrases in the AI's final statement
        3. Customer explicit agreement/rejection/goodbye paired with AI acknowledgment
        """
        if not ai_reply:
            return False

        if "[CALL_COMPLETED]" in ai_reply:
            return True

        lower_ai = ai_reply.lower().strip()

        # Spoken farewell markers in Telugu, Hindi, and English
        farewell_markers = [
            # Telugu
            "సెలవు", "ఉంటానండి", "ఉంటాను", "వీడ్కోలు", "మంచి రోజు",
            "బై", "బై బై", "కాల్ ముగిస్తున్నాను", "కలుద్దాం. ఉంటాను",
            # Hindi
            "अलविदा", "बाय", "बाय बाय", "शुभ दिन", "दिन शुभ हो", "फिर मिलेंगे",
            # English
            "goodbye", "good-bye", "have a great day", "have a wonderful day",
            "have a nice day", "have a good day", "take care, bye", "take care!",
            "talk to you tomorrow", "talk soon", "bye for now", "bye!", "bye."
        ]
        for marker in farewell_markers:
            if marker in lower_ai:
                return True

        # Check customer's latest utterance for closing intent + AI confirmation
        last_user_turn = ""
        for m in reversed(conversation_history):
            if m.get("role") == "user":
                last_user_turn = m.get("content", "").lower().strip()
                break

        if last_user_turn:
            # Customer declined / opted-out
            rejection_patterns = [
                "not interested", "don't call", "dont call", "no need", "no thanks", "stop calling",
                "వద్దు", "ఆసక్తి లేదు", "వద్దు లేండి", "నాకు వద్దు", "కాల్ చేయకండి", "ఫోన్ చేయకండి",
                "नहीं चाहिए", "कॉल मत करना", "फोन मत करो", "रुचि नहीं"
            ]
            if any(p in last_user_turn for p in rejection_patterns):
                ai_ack = ["ధన్యవాదాలు", "సరేనండి", "అర్థమైంది", "thank you", "understood", "okay", "धन्यवाद", "समझ गया", "जी बिल्कुल"]
                if any(w in lower_ai for w in ai_ack):
                    return True

            # Customer confirmed demo schedule
            demo_patterns = [
                "11 am", "11:00", "11am", "4 pm", "4:00", "4pm", "tomorrow works", "schedule it", "confirm it",
                "yes tomorrow", "okay schedule", "done send link", "that works", "sounds good",
                "రేపు 11", "11 గంటలకు", "సాయంత్రం 4", "ఓకే పెట్టండి", "షెడ్యూల్ చేయండి", "రేపు కలుద్దాం", "సరే రేపు", "రేపు ఉదయం",
                "कल 11", "11 बजे", "शाम 4", "शेड्यूल कर दीजिए", "कल मिलते हैं", "हाँ ठीक है", "कल चलेगा"
            ]
            if any(p in last_user_turn for p in demo_patterns):
                ai_confirm = ["ధన్యవాదాలు", "కలుద్దాం", "షెడ్యూల్", "వాట్సాప్", "thank you", "tomorrow", "scheduled", "connect", "धन्यवाद", "मिलते हैं", "शेड्यूल"]
                if any(w in lower_ai for w in ai_confirm):
                    return True

            # Customer said goodbye / thank you
            goodbye_patterns = [
                "thank you bye", "thanks bye", "bye", "bye bye", "goodbye",
                "ధన్యవాదాలు బై", "థాంక్యూ బై", "సరే బై",
                "धन्यवाद बाय", "बाय", "बाय बाय"
            ]
            if any(p in last_user_turn for p in goodbye_patterns):
                return True

        return False

    async def get_initial_greeting(
        self,
        lead_id: Optional[int] = None,
        language_code: Optional[str] = None
    ) -> str:
        """
        Generate opening hook greeting when call connects, customized to lead and language.
        """
        profile = get_company_profile()
        agency = profile.get("agency_name", "S P Associates Software Company")
        lead = get_lead_by_id(lead_id) if lead_id else None

        greeting, _ = get_localized_initial_greeting(agency_name=agency, lead=lead, language_code=language_code)
        return greeting

    async def extract_call_intelligence(self, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Post-call AI intelligence extraction to summarize, qualify, and update CRM status.
        CRITICAL: All summaries and fields are strictly stored in professional English,
        regardless of whether the conversation was in Telugu, Hindi, or English.
        """
        if not conversation_history:
            return {
                "summary": "No conversation took place on this call.",
                "sentiment": "neutral",
                "deal_stage": "qualifying",
                "outcome_label": "no_answer",
                "outcome_bucket": "not_reachable",
                "outcome_reason": "No speech captured",
                "confidence": 1.0,
                "needs_human_review": False,
                "callback_at": None,
                "whatsapp_opt_in": False,
                "extracted_budget": "Not specified",
                "extracted_timeline": "Not specified",
                "extracted_requirements": "Software Services",
                "objections_raised": "None",
                "action_items": "Place follow-up call."
            }

        from services.outcomes import normalize_outcome, parse_callback_time_ist

        transcript_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in conversation_history])

        prompt = f"""
You are an expert sales CRM intelligence engine. Analyze the following telephone sales conversation (which may be conducted in Telugu, Hindi, English, Tamil, Kannada, Malayalam, or mixed languages) and extract structured sales insights.

CRITICAL REQUIREMENT:
All JSON field values ('summary', 'extracted_requirements', 'objections_raised', 'action_items', 'outcome_reason') MUST BE WRITTEN IN CLEAR, PROFESSIONAL ENGLISH, even if the spoken dialogue was in an Indian language.
Never output Telugu, Hindi, Tamil, Kannada, Malayalam, or non-English script in the JSON values. Always summarize and translate into fluent English for executive CRM records.

TRANSCRIPT:
\"\"\"
{transcript_text}
\"\"\"

Return ONLY valid JSON matching this exact structure (no markdown fences, no backticks):
{{
  "summary": "1-2 sentence concise executive summary in English of what was discussed, client needs, and what was agreed upon",
  "sentiment": "positive / neutral / hesitant / negative",
  "deal_stage": "closed_won / demo_scheduled / qualified / follow_up / lost",
  "outcome_label": "interested_now | meeting_booked | human_requested | callback_scheduled | interested_later | send_details_first | decision_maker | busy_no_time | not_interested | do_not_call | wrong_person | invalid_lead",
  "outcome_reason": "Short English reason for the outcome (e.g. Agreed to demo tomorrow, Price concern, Busy driving, Requested WhatsApp brochure)",
  "callback_at": "Requested callback time in English or ISO 8601 (e.g. tomorrow 6 PM, or null)",
  "whatsapp_opt_in": true,
  "confidence": 0.9,
  "extracted_budget": "Budget discussed in English (e.g. ₹50,000 or Not specified)",
  "extracted_timeline": "Timeline discussed in English (e.g. 2 weeks, Immediate, or Not specified)",
  "extracted_requirements": "Specific services required in English (e.g. E-Commerce Web, Mobile App, AI Calling Agent)",
  "objections_raised": "Customer objections or hesitations in English (e.g. Budget concern, Requested details on WhatsApp first, None)",
  "action_items": "Immediate next action item for sales team in English (e.g. Send Zoom demo link for tomorrow at 11 AM)"
}}
"""

        messages = [
            {"role": "system", "content": "You are a precise sales CRM data extraction engine. Return raw valid JSON only with all values in professional English."},
            {"role": "user", "content": prompt}
        ]

        try:
            raw_response = await sarvam_client.chat_completion(messages=messages, temperature=0.2, max_tokens=400)
            clean_json = raw_response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)

            # Strict CRM guarantee: Ensure summary and action items are 100% in professional English
            indic_pattern = re.compile(r'[\u0900-\u0D7F]')
            for key in ["summary", "action_items", "objections_raised", "extracted_requirements", "outcome_reason"]:
                val = str(data.get(key, ""))
                if val and indic_pattern.search(val):
                    try:
                        trans = await sarvam_client.chat_completion(
                            messages=[
                                {"role": "system", "content": "You are a professional sales CRM translator. Translate the text into fluent, concise English for executive records. Never output Indian scripts or non-English characters."},
                                {"role": "user", "content": f"Translate this CRM record to English:\n{val}"}
                            ],
                            temperature=0.1,
                            max_tokens=120
                        )
                        trans_clean = trans.strip().strip('"').strip("'")
                        if trans_clean and not indic_pattern.search(trans_clean):
                            data[key] = trans_clean
                        else:
                            data[key] = "Discussed software project requirements and agreed on next steps."
                    except Exception as te:
                        logger.warning(f"Translation fallback for {key}: {te}")
                        data[key] = "Discussed software project requirements and agreed on next steps."

            raw_label = data.get("outcome_label") or data.get("deal_stage")
            norm = normalize_outcome(raw_label, transcript_text=transcript_text, confidence=data.get("confidence", 0.9))
            data["outcome_label"] = norm["outcome_label"]
            data["outcome_bucket"] = norm["outcome_bucket"]
            data["confidence"] = norm["confidence"]
            data["needs_human_review"] = norm["needs_human_review"]
            data["opt_out_requested"] = norm["opt_out_requested"]
            if not data.get("deal_stage"):
                data["deal_stage"] = norm["legacy_stage"]
            parsed_cb = parse_callback_time_ist(str(data.get("callback_at") or ""))
            data["callback_at"] = parsed_cb.isoformat() if parsed_cb else None
            return data
        except Exception as e:
            logger.error(f"Intelligence extraction failed, using heuristic: {e}")
            lower_transcript = transcript_text.lower()
            deal_stage = "follow_up"
            sentiment = "neutral"

            if any(w in lower_transcript for w in ["demo", "డెమో", "डेमो", "రేపు", "tomorrow", "schedule", "మీటింగ్"]):
                deal_stage = "demo_scheduled"
                sentiment = "positive"
            elif any(w in lower_transcript for w in ["done", "ఓకే", "हाँ", "start", "agree", "ఫైనల్"]):
                deal_stage = "closed_won"
                sentiment = "positive"
            elif any(w in lower_transcript for w in ["వద్దు", "नहीं", "no", "not interested", "dont call"]):
                deal_stage = "lost"
                sentiment = "negative"

            norm = normalize_outcome(deal_stage, transcript_text=transcript_text, confidence=0.75)
            parsed_cb = parse_callback_time_ist(transcript_text) if norm["outcome_bucket"] == "follow_up" else None

            return {
                "summary": "Discussed custom software requirements and agreed to schedule an upcoming project review.",
                "sentiment": sentiment,
                "deal_stage": deal_stage,
                "outcome_label": norm["outcome_label"],
                "outcome_bucket": norm["outcome_bucket"],
                "outcome_reason": "Heuristic classification from conversation transcript",
                "confidence": norm["confidence"],
                "needs_human_review": norm["needs_human_review"],
                "opt_out_requested": norm["opt_out_requested"],
                "callback_at": parsed_cb.isoformat() if parsed_cb else None,
                "whatsapp_opt_in": any(w in lower_transcript for w in ["whatsapp", "వాట్సాప్", "व्हाट्सएप"]),
                "extracted_budget": "Flexible",
                "extracted_timeline": "Standard",
                "extracted_requirements": "Software & AI Solutions",
                "objections_raised": "None noted",
                "action_items": "Follow up with client via WhatsApp or schedule demo."
            }


sales_agent = SalesAgent()
