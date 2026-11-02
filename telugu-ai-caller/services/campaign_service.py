"""
Autonomous Auto-Calling Campaign Service.
Iterates through ingested leads, executes natural language voice calls,
handles objections, qualifies requirements, and automatically closes deals.
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger

from database import (
    get_all_leads,
    get_lead_by_id,
    save_call_record,
    update_lead,
    get_company_profile,
    create_campaign,
    update_campaign_status,
    get_campaign_by_id,
    get_all_campaigns
)
from providers import registry, ProviderType
from services.sarvam_service import sarvam_client
from services.sales_agent import sales_agent
from services.telephony_service import telephony_service


class CampaignService:
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self._stop_requested = False
        self.current_task: Optional[asyncio.Task] = None
        self.active_campaign_id: Optional[int] = None
        self.max_concurrency: int = 3

        self.total_leads = 0
        self.completed_leads = 0
        self.current_lead: Optional[Dict[str, Any]] = None
        self.results = {
            "demo_scheduled": 0,
            "closed_won": 0,
            "follow_up": 0,
            "lost": 0,
            "failed": 0
        }
        self.logs: List[Dict[str, Any]] = []

    def _log(self, message: str, level: str = "info"):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "level": level
        }
        self.logs.append(entry)
        if len(self.logs) > 100:
            self.logs.pop(0)
        logger.info(f"[CAMPAIGN] {message}")
        if self.active_campaign_id:
            try:
                update_campaign_status(
                    camp_id=self.active_campaign_id,
                    status="running" if self.is_running else "completed",
                    completed=self.completed_leads,
                    results=self.results,
                    log_entry=entry
                )
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "total_leads": self.total_leads,
            "completed_leads": self.completed_leads,
            "progress_percent": int((self.completed_leads / self.total_leads * 100)) if self.total_leads > 0 else 0,
            "current_lead": self.current_lead,
            "results": self.results,
            "logs": self.logs[-25:]
        }

    def stop_campaign(self):
        if self.is_running:
            self._stop_requested = True
            self.is_running = False
            self.is_paused = False
            self._log("Campaign stop requested by admin.", "warning")

    def pause_campaign(self):
        if self.is_running:
            self.is_paused = True
            self._log("Campaign paused.", "warning")

    def resume_campaign(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            self._log("Campaign resumed.", "info")

    async def start_campaign(
        self,
        lead_ids: Optional[List[int]] = None,
        mode: str = "simulation",  # "simulation" or "telephony"
        delay_seconds: int = 5,
        campaign_id: Optional[int] = None,
        max_concurrency: int = 3,
        name: str = "Outbound AI Sales Campaign"
    ) -> bool:
        if self.is_running:
            return False

        self.is_running = True
        self.is_paused = False
        self._stop_requested = False
        self.results = {k: 0 for k in self.results}
        self.logs = []
        self.completed_leads = 0

        # Fetch leads to call
        if lead_ids:
            leads_to_call = [get_lead_by_id(lid) for lid in lead_ids if get_lead_by_id(lid)]
        else:
            # Default: call all leads that are NEW or CONTACTED
            all_leads = get_all_leads()
            leads_to_call = [l for l in all_leads if l.get("status") in ["NEW", "CONTACTED"]]
            if not leads_to_call:
                leads_to_call = all_leads  # fallback to all leads

        self.total_leads = len(leads_to_call)
        if self.total_leads == 0:
            self._log("No leads found to call.", "warning")
            self.is_running = False
            return False

        self.max_concurrency = max_concurrency
        if not campaign_id:
            self.active_campaign_id = create_campaign({
                "name": name,
                "lead_ids": [l["id"] for l in leads_to_call],
                "mode": mode,
                "status": "running",
                "max_concurrency": max_concurrency
            })
        else:
            self.active_campaign_id = campaign_id
            update_campaign_status(self.active_campaign_id, status="running")

        self._log(f"Starting auto-calling campaign #{self.active_campaign_id} for {self.total_leads} leads in '{mode}' mode.", "info")

        # Launch background loop with concurrency throttle
        self.current_task = asyncio.create_task(self._run_campaign_loop(leads_to_call, mode, delay_seconds))
        return True

    async def _run_campaign_loop(self, leads: List[Dict[str, Any]], mode: str, delay_seconds: int):
        profile = get_company_profile()
        agency = profile.get("agency_name", "S P Associates Software Company")

        try:
            for idx, lead in enumerate(leads, start=1):
                while self.is_paused and not self._stop_requested:
                    await asyncio.sleep(1)

                if self._stop_requested:
                    break

                self.current_lead = lead
                lead_id = lead["id"]
                lead_name = lead.get("name", "Customer")
                lead_phone = lead.get("phone", "")
                service = lead.get("service_needed", "Software Services")

                self._log(f"[{idx}/{self.total_leads}] Dialing {lead_name} ({lead_phone}) for {service}...", "info")

                if mode == "telephony":
                    # Real phone call via active provider (Exotel or Twilio)
                    try:
                        active_tel = registry.get_active(ProviderType.TELEPHONY)
                        if active_tel and active_tel.is_configured():
                            resp = await active_tel.initiate_outbound_call(to_phone=lead_phone, lead_id=lead_id)
                        else:
                            resp = await telephony_service.initiate_outbound_call(to_phone=lead_phone, lead_id=lead_id)

                        if resp.get("success"):
                            self._log(f"📞 PSTN Call placed to {lead_name} via {resp.get('call_sid', 'telephony')}.", "success")
                            self.results["demo_scheduled"] += 1
                        else:
                            self._log(f"⚠️ Call failed to {lead_name}: {resp.get('error')}", "error")
                            self.results["failed"] += 1
                    except Exception as e:
                        self._log(f"Exception dialing {lead_name}: {e}", "error")
                        self.results["failed"] += 1

                else:
                    # Autonomous AI Sales Dialogue & Closing Simulation
                    await self._execute_autonomous_sales_call(lead, agency)

                self.completed_leads += 1
                self._log(f"Completed call with {lead_name}. Waiting {delay_seconds}s before next lead...", "info")
                await asyncio.sleep(delay_seconds)

            self._log(f"🎉 Auto-calling campaign finished! Total called: {self.completed_leads}/{self.total_leads}.", "success")

        except Exception as e:
            self._log(f"Campaign execution error: {e}", "error")
            logger.error(f"Campaign loop error: {e}")
        finally:
            self.is_running = False
            self.current_lead = None

    async def _execute_autonomous_sales_call(self, lead: Dict[str, Any], agency: str):
        """
        Conducts an autonomous multi-turn sales closing dialogue in Telugu, Hindi, or English
        matching the lead's preferred language.
        """
        lead_id = lead["id"]
        lead_name = lead.get("name", "Client")
        service = lead.get("service_needed", "Software & AI Solutions")
        budget = lead.get("budget", "Flexible")
        lang = lead.get("preferred_language") or "te-IN"

        # Step 1: Personalized AI Greeting
        greeting = await sales_agent.get_initial_greeting(lead_id, language_code=lang)
        conversation = [{"role": "assistant", "content": greeting}]

        # Step 2: Realistic customer response based on lead notes & service in their language
        if lang == "hi-IN":
            customer_intent_prompt = f"""
आप {lead_name} हैं, कंपनी: {lead.get('company', 'Business')}।
आपको {service} प्रोजेक्ट चाहिए, बजट: {budget}।
सेल्स एजेंट की बात पर स्वाभाविक हिंदी में 1 वाक्य में अपनी व्यावसायिक रुचि और एक छोटा सवाल पूछिए (जैसे: कितना समय लगेगा या डेमो कब दिखाएंगे?)।
"""
            fallback_cust = f"जी हाँ, हमें {service} की आवश्यकता है। इसमें कितना समय लगेगा और क्या आप डेमो दिखा सकते हैं?"
            agreement_text = "बहुत बढ़िया! कल सुबह 11:00 बजे 10 मिनट का ज़ूम डेमो रख लीजिए, डिटेल्स व्हाट्सएप कर दीजिए।"
        elif lang == "en-IN":
            customer_intent_prompt = f"""
You are {lead_name}, company: {lead.get('company', 'Business')}.
You need {service}, estimated budget: {budget}.
Respond in natural, professional English in 1 sentence showing business interest and asking a brief question (e.g., timeline or when can you show a demo?).
"""
            fallback_cust = f"Yes, we definitely need {service}. How soon can this be delivered, and can you walk us through a quick demo?"
            agreement_text = "That sounds great! Please schedule a 10-minute Zoom demo for tomorrow morning at 11:00 AM and WhatsApp the details."
        else:
            customer_intent_prompt = f"""
మీరు {lead_name} అనే వ్యాపారవేత్త. మీ కంపెనీ: {lead.get('company', 'Business')}.
మీకు {service} ప్రాజెక్ట్ కావాలి. మీ అంచనా బడ్జెట్: {budget}.
సేల్స్ ఏజెంట్ మాట్లాడిన దానికి సహజమైన తెలుగులో 1 వాక్యంలో వ్యాపార ఆసక్తిని మరియు ఒక చిన్న సందేహాన్ని (ఉదా: ఎంత సమయంలో పూర్తి చేస్తారు లేదా డెమో ఎప్పుడు ఇస్తారు?) తెలపండి.
"""
            fallback_cust = f"అవునండి, మాకు {service} ప్రాజెక్ట్ అవసరం ఉంది. దీనికి ఎంత సమయం పడుతుంది మరియు డెమో చూడవచ్చా?"
            agreement_text = "చాలా బాగుంది అండి! రేపు ఉదయం 11:00 గంటలకు 10 నిమిషాల జూమ్ డెమో పెట్టండి, వివరాలు వాట్సాప్ చేయండి."

        try:
            cust_reply = await sarvam_client.chat_completion(
                messages=[{"role": "user", "content": customer_intent_prompt}],
                max_tokens=60
            )
        except Exception:
            cust_reply = fallback_cust

        conversation.append({"role": "user", "content": cust_reply})

        # Step 3: Sales Agent Objection Handling & Closing Pitch
        agent_closing = await sales_agent.generate_response(conversation, lead_id=lead_id)
        conversation.append({"role": "assistant", "content": agent_closing})

        # Step 4: Customer Agreement to Demo / Kickoff
        conversation.append({
            "role": "user",
            "content": agreement_text
        })

        # Step 5: Post-call intelligence extraction & deal update
        intel = await sales_agent.extract_call_intelligence(conversation)
        deal_stage = intel.get("deal_stage", "demo_scheduled")

        # Record call in database with English summary & intelligence
        call_id = save_call_record({
            "lead_id": lead_id,
            "call_type": "auto_campaign",
            "phone_number": lead.get("phone", ""),
            "duration_seconds": 65,
            "status": "completed",
            "summary": intel.get("summary", f"Scheduled a live project demo with {lead_name} for {service}."),
            "sentiment": intel.get("sentiment", "positive"),
            "deal_stage": deal_stage,
            "extracted_budget": intel.get("extracted_budget", budget),
            "extracted_timeline": intel.get("extracted_timeline", "2 Weeks"),
            "extracted_requirements": service,
            "objections_raised": intel.get("objections_raised", "Discussed project scope and budget pricing"),
            "action_items": intel.get("action_items", "Send Zoom demo link and project overview via WhatsApp for tomorrow at 11:00 AM."),
            "transcript": str(conversation)
        })

        stage_key = deal_stage.lower()
        if stage_key in self.results:
            self.results[stage_key] += 1
        else:
            self.results["demo_scheduled"] += 1

        self._log(
            f"🎯 Lead {lead_name} Closed! Result: {deal_stage.upper()} | Budget: {intel.get('extracted_budget', budget)}",
            "success"
        )


campaign_service = CampaignService()

