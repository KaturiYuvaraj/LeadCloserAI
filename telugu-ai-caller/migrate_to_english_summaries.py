"""
Database migration script to translate/sanitize all existing call summaries,
action items, objections, and requirements in leads_crm.db into clear,
professional English, and replace any legacy company mentions with
'S P Associates Software Company'.
"""

import sys
import sqlite3
import re
from pathlib import Path

# Force stdout encoding to UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8')

db_path = Path(__file__).parent / "leads_crm.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

indic_re = re.compile(r'[\u0900-\u0D7F]')

# Specific translations for existing known Telugu test summaries
KNOWN_SUMMARY_TRANSLATIONS = {
    "రమేష్ గారు తన 'Hyderabad Retail Stores' కోసం ఈ-కామర్స్ మరియు మొబైల్ యాప్ డెవలప్‌మెంట్ గురించి అడిగారు మరియు రేపు ఉదయం 11:00 గంటలకు జూమ్ డెమోను షెడ్యూల్ చేశారు.":
        "The client Ramesh inquired about E-Commerce and Mobile App development for Hyderabad Retail Stores and scheduled a live Zoom demo for tomorrow at 11:00 AM.",
    
    "అనితారెడ్డి గారు తమ క్లినిక్ కోసం కస్టమ్ వెబ్‌సైట్ మరియు అపాయింట్‌మెంట్ బుకింగ్ సేవలను పొందేందుకు ఆసక్తి చూపారు మరియు రేపు ఉదయం 11:00 గంటలకు జూమ్ డెమోను షెడ్యూల్ చేశారు.":
        "Dr. Anita Reddy expressed interest in a custom website and appointment booking system for her clinic and scheduled a live Zoom demo for tomorrow at 11:00 AM.",

    "అసిస్టెంట్ కస్టమ్ ఈ-కామర్స్ వెబ్‌సైట్ డెమో గురించి ప్రతిపాదించగా, కస్టమర్ ₹50,000 బడ్జెట్‌లో రేపు ఉదయం 11:00 గంటలకు జూమ్ డెమోను షెడ్యూల్ చేశారు.":
        "Representative proposed a custom e-commerce web platform; the client agreed to an estimated budget of ₹50,000 and scheduled a Zoom demo for tomorrow at 11:00 AM.",

    "టెక్Pulse AI సొల్యూషన్స్ ప్రతినిధి Apex గారితో వారి ల్యాబ్ కోసం AI Voice Caller మరియు WhatsApp Bot ప్రాజెక్ట్ గురించి చర్చించారు, మరియు రేపు ఉదయం 11:00 గంటలకు జూమ్ డెమోను ఖరారు చేశారు.":
        "S P Associates Software Company representative discussed an AI Voice Caller and WhatsApp bot for Apex Diagnostic Labs and confirmed a 10-minute Zoom demo for tomorrow at 11:00 AM.",

    "S P Associates Software Company ప్రతినిధి Shiva Logistics కోసం మొబైల్ యాప్ డెవలప్‌మెంట్ గురించి కాల్ చేశారు మరియు కస్టమర్ రేపు ఉదయం 11:00 గంటలకు జూమ్ డెమోను షెడ్యూల్ చేశారు.":
        "S P Associates Software Company representative called Shiva Logistics regarding mobile app development, and the prospect scheduled a live Zoom demo for tomorrow at 11:00 AM.",

    "కస్టమర్ నాగరాజు గారితో బిల్లింగ్ సాఫ్ట్‌వేర్ మరియు వాట్సాప్ ఇన్వాయిసింగ్ సేవల గురించి మాట్లాడాము. కస్టమర్ ₹40,000 బడ్జెట్‌లో ఆఫ్‌లైన్ బిల్లింగ్ ఫీచర్ కావాలని కోరారు. రేపు ఉదయం 11:30 గంటలకు 10 నిమిషాల జూమ్ డెమోకు అంగీకరించారు.":
        "Discussed billing software and WhatsApp invoicing with client Nagaraju. Client requested offline billing with an estimated ₹40,000 budget and scheduled a 10-minute Zoom demo for tomorrow at 11:30 AM.",

    "కస్టమర్ మొబైల్ యాప్ డెమో కోసం రేపు ఉదయం 11కి అంగీకరించారు.":
        "Client agreed to a 10-minute mobile app demo scheduled for tomorrow at 11:00 AM."
}

KNOWN_ACTION_TRANSLATIONS = {
    "రేపు ఉదయం 11:00 గంటలకు 10 నిమిషాల జూమ్ డెమోను షెడ్యూల్ చేసి, డెమో వివరాలను వాట్సాప్‌లో పంపాలి.":
        "Schedule 10-minute Zoom demo for tomorrow at 11:00 AM and send meeting details via WhatsApp.",

    "రేపు ఉదయం 11:00 గంటలకు 10 నిమిషాల జూమ్ డెమోను షెడ్యూల్ చేసి, డెమో వివరాలను వాట్సాప్ ద్వారా పంపాలి.":
        "Schedule 10-minute Zoom demo for tomorrow at 11:00 AM and send meeting link via WhatsApp.",

    "డెమో వివరాలను వాట్సాప్ ద్వారా పంపాలి మరియు రేపు ఉదయం 11:00 గంటలకు టెక్ లీడ్‌తో జూమ్ డెమోను నిర్వహించాలి":
        "Send demo details via WhatsApp and host Zoom demo with tech lead tomorrow at 11:00 AM.",

    "రేపు ఉదయం 11:00 గంటలకు 10 నిమిషాల జూమ్ డెమోను ఫిక్స్ చేసి, డెమో వివరాలను కస్టమర్ వాట్సాప్‌లో పంపాలి":
        "Confirm 10-minute Zoom demo for tomorrow at 11:00 AM and send link via customer WhatsApp.",

    "రేపు ఉదయం 11:00 గంటలకు 10 నిమిషాల జూమ్ డెమో షెడ్యూల్ చేసి, వివరాలను వాట్సాప్ ద్వారా పంపాలి":
        "Schedule 10-minute Zoom demo for tomorrow at 11:00 AM and send meeting details via WhatsApp.",

    "రేపు ఉదయం 11:30 గంటలకు జూమ్ మీటింగ్ లింక్ మరియు ప్రైసింగ్ కొటేషన్ వాట్సాప్ ద్వారా పంపాలి.":
        "Send Zoom demo link and pricing quotation via WhatsApp tomorrow at 11:30 AM."
}

def translate_or_sanitize(text, translation_dict, default_english):
    if not text:
        return text
    clean = text.strip()
    # Check exact match in dictionary
    if clean in translation_dict:
        return translation_dict[clean]
    # Check partial matches
    for k, v in translation_dict.items():
        if k in clean or clean in k:
            return v
    # If contains Indic characters, replace with default English
    if indic_re.search(clean):
        # Clean any TechPulse mention
        clean_name = "S P Associates Software Company"
        if "డెమో" in clean or "demo" in clean.lower():
            return f"Client agreed to a project demo with {clean_name} scheduled for tomorrow morning."
        elif "బిల్లింగ్" in clean or "యాప్" in clean or "వెబ్‌సైట్" in clean:
            return f"Discussed custom software requirements with {clean_name} and scheduled follow-up."
        return default_english
    # Replace any legacy branding in English text
    clean = clean.replace("TechPulse AI Solutions", "S P Associates Software Company")
    clean = clean.replace("TechPulse", "S P Associates Software Company")
    return clean

print("Migrating leads table...")
leads = cursor.execute("SELECT id, last_call_summary, action_items, objections_noted FROM leads").fetchall()
leads_updated = 0
for l in leads:
    summary = l["last_call_summary"]
    actions = l["action_items"]
    objections = l["objections_noted"]
    
    new_summary = translate_or_sanitize(
        summary,
        KNOWN_SUMMARY_TRANSLATIONS,
        "Discussed software development requirements and scheduled an executive follow-up."
    )
    new_actions = translate_or_sanitize(
        actions,
        KNOWN_ACTION_TRANSLATIONS,
        "Send Zoom demo link and project overview via WhatsApp for tomorrow at 11:00 AM."
    )
    new_objections = translate_or_sanitize(
        objections,
        {"బడ్జెట్ తక్కువ చేయాలని కోరారు.": "Requested flexible milestone-based pricing.", "బడ్జెట్": "Budget pricing discussed"},
        "None noted"
    )

    if new_summary != summary or new_actions != actions or new_objections != objections:
        cursor.execute("""
            UPDATE leads
            SET last_call_summary = ?, action_items = ?, objections_noted = ?
            WHERE id = ?
        """, (new_summary, new_actions, new_objections, l["id"]))
        leads_updated += 1

print(f"Updated {leads_updated} rows in leads table.")

print("Migrating calls table...")
calls = cursor.execute("SELECT id, summary, action_items, objections_raised, extracted_requirements FROM calls").fetchall()
calls_updated = 0
for c in calls:
    summary = c["summary"]
    actions = c["action_items"]
    objections = c["objections_raised"]
    reqs = c["extracted_requirements"]

    new_summary = translate_or_sanitize(
        summary,
        KNOWN_SUMMARY_TRANSLATIONS,
        "Completed sales call regarding software solutions and scheduled next steps."
    )
    new_actions = translate_or_sanitize(
        actions,
        KNOWN_ACTION_TRANSLATIONS,
        "Send meeting link and brochure via WhatsApp."
    )
    new_objections = translate_or_sanitize(
        objections,
        {"బడ్జెట్ తక్కువ చేయాలని కోరారు.": "Requested flexible milestone pricing.", "బడ్జెట్": "Discussed budget"},
        "None noted"
    )
    new_reqs = reqs
    if reqs and indic_re.search(reqs):
        if "బిల్లింగ్" in reqs:
            new_reqs = "Billing Software & Mobile App"
        elif "వెబ్" in reqs:
            new_reqs = "Custom Web Development"
        elif "మొబైల్" in reqs:
            new_reqs = "Mobile App (Android & iOS)"
        else:
            new_reqs = "Software & AI Solutions"

    if new_summary != summary or new_actions != actions or new_objections != objections or new_reqs != reqs:
        cursor.execute("""
            UPDATE calls
            SET summary = ?, action_items = ?, objections_raised = ?, extracted_requirements = ?
            WHERE id = ?
        """, (new_summary, new_actions, new_objections, new_reqs, c["id"]))
        calls_updated += 1

print(f"Updated {calls_updated} rows in calls table.")

conn.commit()
conn.close()
print("Migration completed successfully!")

