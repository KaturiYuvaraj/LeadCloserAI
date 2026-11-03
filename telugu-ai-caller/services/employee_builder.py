"""
AI Employee Builder & Creation Assistant.
Generates specialized AI sales employees from plain-language user instructions
with approval gates and customization parameters.
"""

import json
import re
from typing import Dict, Any, Optional
from loguru import logger

from services.sarvam_service import sarvam_client
from database import get_company_profile


class EmployeeBuilder:
    def __init__(self):
        pass

    async def generate_draft_from_instruction(
        self,
        instruction: str,
        preferred_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive, configurable AI employee draft based on user prompt.
        Always generated in status 'draft' requiring admin approval.
        """
        profile = get_company_profile()
        company_name = profile.get("agency_name", "S P Associates Software Company")

        # Determine target language code
        lower_inst = instruction.lower()
        if "telugu" in lower_inst or (preferred_language and "te" in preferred_language):
            lang = "te-IN"
            speaker = "kavitha_te_conversation"
        elif "hindi" in lower_inst or (preferred_language and "hi" in preferred_language):
            lang = "hi-IN"
            speaker = "pooja"
        elif "tamil" in lower_inst or (preferred_language and "ta" in preferred_language):
            lang = "ta-IN"
            speaker = "meera_ta_conversation"
        elif "kannada" in lower_inst or (preferred_language and "kn" in preferred_language):
            lang = "kn-IN"
            speaker = "shreya_kn_conversation"
        elif "malayalam" in lower_inst or (preferred_language and "ml" in preferred_language):
            lang = "ml-IN"
            speaker = "arya_ml_conversation"
        else:
            lang = "en-IN"
            speaker = "tarun"

        llm_prompt = f"""
You are an expert AI Voice Agent Architect. The user wants to create a specialized AI sales agent for {company_name}.
User instruction:
"{instruction}"

Generate a complete, production-grade JSON configuration for this AI employee.
Return ONLY valid JSON with exactly these keys:
{{
  "name": "Professional Name of Agent (e.g. Kavitha - Web Solutions Specialist)",
  "role": "Specific Job Title (e.g. Dental Clinic Software Sales Closer)",
  "description": "Short 1-2 sentence description of persona and calling focus",
  "language": "{lang}",
  "voice_speaker": "{speaker}",
  "greeting": "A warm, natural 1-sentence opening greeting hook matching the target language ({lang})",
  "calling_objective": "Primary call conversion goal",
  "system_prompt": "Complete, rigorous system instructions for the conversational AI agent",
  "sales_script": "Step-by-step conversational milestones (Hook -> Qualify -> Pitch -> Close)",
  "qualification_questions": "3 core BANT qualification questions",
  "knowledge_base": "Key service offerings, pricing flexibility, and trust factors for {company_name}",
  "working_hours": "09:00 - 19:00",
  "max_call_duration_seconds": 600,
  "status": "draft"
}}
"""

        try:
            messages = [
                {"role": "system", "content": "You are a specialized AI system prompt engineer. Return ONLY pure raw JSON."},
                {"role": "user", "content": llm_prompt}
            ]
            raw_response = await sarvam_client.chat_completion(messages=messages, temperature=0.3, max_tokens=600)

            # Extract JSON block
            json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                parsed["status"] = "draft"
                parsed["is_active"] = False
                return parsed
        except Exception as e:
            logger.warning(f"Sarvam LLM draft generation failed, using intelligent template builder: {e}")

        # Intelligent structured fallback
        name = "Specialized AI Sales Agent"
        role = "Sales Specialist"
        if "dental" in lower_inst or "clinic" in lower_inst or "health" in lower_inst:
            name = "Ananya - Healthcare & Clinic Tech Specialist"
            role = "Clinic Automation Consultant"
            objective = "Qualify patient appointment booking challenges and schedule a demo of our clinic management software."
            if lang == "te-IN":
                greeting = f"నమస్కారం డాక్టర్ గారు! నేను {company_name} నుండి మాట్లాడుతున్నాను. మీ క్లినిక్‌కి ఆటోమేటెడ్ వాట్సాప్ మరియు పేషెంట్ అపాయింట్‌మెంట్ సాఫ్ట్‌వేర్ గురించి మాట్లాడటానికి కాల్ చేశాను."
            elif lang == "hi-IN":
                greeting = f"नमस्ते डॉक्टर साहब! मैं {company_name} से बात कर रहा हूँ। क्या आपके क्लिनिक के लिए ऑटोमेटेड अपॉइंटमेंट और बिलिंग सॉफ़्टवेयर का लाइव डेमो देख सकते हैं?"
            else:
                greeting = f"Hello Doctor! I am calling from {company_name}. We help specialty clinics automate patient appointments and WhatsApp reminders."
        elif "web" in lower_inst or "site" in lower_inst or "saas" in lower_inst:
            name = "Kavitha - Web Solutions Specialist"
            role = "Website & SaaS Development Specialist"
            objective = "Introduce custom web development services, assess digital presence, and schedule a live portfolio demo."
            greeting = f"నమస్కారం అండి! మీ బిజినెస్‌కి మోడరన్ కస్టమ్ వెబ్‌సైట్ లేదా ఈ-కామర్స్ పోర్టల్ కోసం {company_name} నుండి కాల్ చేస్తున్నాను." if lang == "te-IN" else f"Hello! I am calling from {company_name} regarding modern web app development for your business."
        else:
            name = "Vikram - Enterprise Business Consultant"
            role = "Software Solutions Closer"
            objective = "Qualify custom IT and software requirements, address budget, and schedule a 10-minute live demo."
            greeting = f"నమస్కారం అండి! నేను {company_name} నుండి మాట్లాడుతున్నాను. మీ బిజినెస్ గ్రోత్ కోసం కస్టమ్ సాఫ్ట్‌వేర్ లేదా యాప్ గురించి మాట్లాడటానికి కాల్ చేశాను." if lang == "te-IN" else f"Hello! Calling from {company_name} regarding custom software and AI solutions for your company."

        return {
            "name": name,
            "role": role,
            "description": f"Specialized AI employee configured to close deals for {company_name}.",
            "language": lang,
            "voice_speaker": speaker,
            "greeting": greeting,
            "calling_objective": objective,
            "system_prompt": f"You are {name}, {role} at {company_name}. Your primary objective is to naturally qualify the customer's needs and book a 10-minute demo call.",
            "sales_script": "1. Friendly Hook -> 2. Understand Current Pain Points -> 3. Present Custom Solution -> 4. Overcome Objections -> 5. Schedule 10-Min Demo",
            "qualification_questions": "1. What is your primary business challenge?\\n2. What is your estimated timeline for this project?\\n3. Are you open to a 10-minute demo tomorrow?",
            "knowledge_base": f"{company_name} delivers custom software, mobile apps, websites, and AI voice automation with flexible milestone payments.",
            "working_hours": "09:00 - 19:00",
            "max_call_duration_seconds": 600,
            "status": "draft",
            "is_active": False
        }


employee_builder = EmployeeBuilder()

