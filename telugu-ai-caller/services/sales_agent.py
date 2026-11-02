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

CRITICAL MULTILINGUAL LANGUAGE MATCHING RULES (TELUGU • HINDI • ENGLISH):
1. You are natively fluent in TELUGU, HINDI, and ENGLISH.
2. ALWAYS MATCH THE CUSTOMER'S LANGUAGE IMMEDIATELY:
   - If the customer speaks TELUGU (or Tenglish): Reply in natural, respectful Telugu (e.g. "నమస్కారం అండి! మేము S P Associates Software Company నుండి...").
   - If the customer speaks HINDI (or Hinglish): Reply in polite, persuasive, professional Hindi (e.g. "नमस्ते सर/मैडम! हम S P Associates Software Company से बात कर रहे हैं...").
   - If the customer speaks ENGLISH: Reply in crisp, professional Indian English (e.g. "Hello! I am calling from S P Associates Software Company...").
   - If the customer asks to switch languages (e.g. "Can you speak in Hindi?", "తెలుగులో చెప్పండి", "Please talk in English"): Instantly switch to that language on the very next sentence!

NATURAL HUMAN CONVERSATIONAL FLOW & PACING (CRITICAL):
1. ACTIVE LISTENING & EMPATHETIC ACKNOWLEDGEMENT:
   - Always acknowledge what the customer just stated before answering (like a real human):
     - In Telugu: "సరేనండి, అర్థమైంది...", "ఖచ్చితంగా అండి...", "తప్పకుండా..."
     - In Hindi: "जी बिल्कुल सर, समझ गया...", "ज़रूर सर...", "बहुत सही बात है..."
     - In English: "Got it, absolutely...", "That makes total sense, sir...", "Understood..."
2. ONE THOUGHT AT A TIME (CALM & MEASURED):
   - Keep replies short (maximum 1 to 2 sentences).
   - Address their specific requirement or question directly first.
   - Never overwhelm the customer with a barrage of features or rush the conversation.
3. CLOSING ORIENTATION:
   - End with ONE clear, warm question asking to schedule a quick 10-minute live demo or kick-off call for tomorrow morning at 11:00 AM or 4:00 PM.

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
            return reply
        except Exception as e:
            logger.error(f"Error generating sales response: {e}")
            # Detect language of last user utterance for localized fallback
            last_user_msg = next((m["content"] for m in reversed(conversation_history) if m["role"] == "user"), "")
            detected_lang = detect_language(last_user_msg)

            if detected_lang == "hi-IN":
                return "नमस्ते सर! हम आपकी आवश्यकता समझ गए हैं। क्या हम कल सुबह 11 बजे आपके साथ 10 मिनट का मुफ़्त डेमो कॉल शेड्यूल करें?"
            elif detected_lang == "en-IN":
                return "Thank you! We completely understand your requirements. Could we schedule a quick 10-minute demo call tomorrow morning at 11:00 AM?"
            else:
                return "నమస్కారం అండి! మీ ప్రాజెక్ట్ అవసరాలు మేము విన్నాము. మా సీనియర్ టెక్నాలజీ ఎక్స్‌పర్ట్‌తో రేపు 10 నిమిషాల ఉచిత డెమో కాల్ షెడ్యూల్ చేయమంటారా?"

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
                "extracted_budget": "Not specified",
                "extracted_timeline": "Not specified",
                "extracted_requirements": "Software Services",
                "objections_raised": "None",
                "action_items": "Place follow-up call."
            }

        transcript_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in conversation_history])

        prompt = f"""
You are an expert sales CRM intelligence engine. Analyze the following telephone sales conversation (which may be conducted in Telugu, Hindi, English, or mixed languages) and extract structured sales insights.

CRITICAL REQUIREMENT:
All JSON field values ('summary', 'extracted_requirements', 'objections_raised', 'action_items') MUST BE WRITTEN IN CLEAR, PROFESSIONAL ENGLISH, even if the spoken dialogue was in Telugu or Hindi.
Never output Telugu, Hindi, or non-English script in the JSON values. Always summarize and translate into fluent English for executive CRM records.

TRANSCRIPT:
\"\"\"
{transcript_text}
\"\"\"

Return ONLY valid JSON matching this exact structure (no markdown fences, no backticks):
{{
  "summary": "1-2 sentence concise executive summary in English of what was discussed, client needs, and what was agreed upon",
  "sentiment": "positive / neutral / hesitant / negative",
  "deal_stage": "closed_won / demo_scheduled / qualified / follow_up / lost",
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
            raw_response = await sarvam_client.chat_completion(messages=messages, temperature=0.2, max_tokens=350)
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
            for key in ["summary", "action_items", "objections_raised", "extracted_requirements"]:
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

            return {
                "summary": "Discussed custom software requirements and agreed to schedule an upcoming project review.",
                "sentiment": sentiment,
                "deal_stage": deal_stage,
                "extracted_budget": "Flexible",
                "extracted_timeline": "Standard",
                "extracted_requirements": "Software & AI Solutions",
                "objections_raised": "None noted",
                "action_items": "Follow up with client via WhatsApp or schedule demo."
            }


sales_agent = SalesAgent()
