"""
S P Associates price list: the one place prices live.

The AI's call instructions (PRICE_LIST_FOR_AI), the company profile's service list (SERVICES)
and the quotation price book (PRICE_BOOK) are all built from here, so they can't disagree.
Change a price here only. Prices exclude GST unless the business says otherwise.
"""

from typing import Any, Dict, List


def _item(code: str, name: str, category: str, price: float, days: int, deliverables: str) -> Dict[str, Any]:
    return {"code": code, "name": name, "category": category, "base_price_inr": float(price),
            "max_discount_pct": 10.0, "delivery_days": days, "deliverables": deliverables, "active": True}


# delivery_days 0 = not agreed yet: the team confirms it
PRICE_BOOK: List[Dict[str, Any]] = [
    _item("pkg_starter", "Starter Package (website + marketing)", "Website + Digital Marketing", 24500, 0,
          "Static website / landing page Rs 5,000 (one-time). Facebook + Instagram: 10 posters + 3 reels Rs 7,000/month. "
          "Meta + Google Ads, 2 campaigns each, Rs 12,500/month. Includes the first month. "
          "Ad budget extra, paid to Meta/Google. Domain and hosting Rs 3,000 extra."),
    _item("pkg_growth", "Growth Package (website + marketing)", "Website + Digital Marketing", 66500, 0,
          "Dynamic website Rs 19,500 (one-time). Facebook, Instagram, YouTube: 15 posters + 6 reels Rs 21,500/month. "
          "Meta + Google Ads, 4 campaigns each, Rs 25,500/month. AI tele-calling automation, 3 months post-launch support. "
          "Includes the first month. Ad budget extra. Domain and hosting Rs 3,000 extra."),
    _item("pkg_premium", "Premium Package (website + marketing)", "Website + Digital Marketing", 121500, 0,
          "Premium website / e-commerce Rs 45,500 (one-time). Facebook, Instagram, YouTube, LinkedIn, X: daily posting "
          "Rs 40,500/month. Meta, Google + LinkedIn Ads, 6 campaigns each, Rs 35,500/month. AI tele-calling automation, "
          "3 months post-launch support. Includes the first month. Ad budget extra. Domain and hosting Rs 3,000 extra."),
    _item("svc_static_website", "Static Website (individual)", "Individual Services", 6700, 0,
          "5-6 pages / landing page. Domain and hosting Rs 3,000 extra."),
    _item("svc_social_media", "Social Media Marketing (individual)", "Individual Services", 6500, 0, "7 posters + 4 reels."),
    _item("svc_meta_ads", "Meta Ads (individual)", "Individual Services", 8500, 0,
          "2 campaigns. Ad budget extra, e.g. Rs 200/day."),
    _item("svc_google_ads", "Google Ads (individual)", "Individual Services", 9500, 0,
          "2 campaigns. Ad budget extra, e.g. Rs 350/day."),
    _item("svc_gmb", "Google My Business Profile Setup", "Individual Services", 6000, 0, "One-time."),
    _item("app_basic_android", "Mobile App Basic (MVP), Android", "Mobile App", 200000, 42, "Single platform, first version. 4-6 weeks."),
    _item("app_basic_both", "Mobile App Basic (MVP), Android + iOS", "Mobile App", 300000, 42, "First version. 4-6 weeks."),
    _item("app_standard_android", "Mobile App Standard, Android", "Mobile App", 600000, 84, "Business growth app. 8-12 weeks."),
    _item("app_standard_both", "Mobile App Standard, Android + iOS", "Mobile App", 1000000, 84, "Business growth app. 8-12 weeks."),
    _item("app_premium_android", "Mobile App Premium, Android", "Mobile App", 1500000, 180, "Enterprise, scalable platform. 4-6 months."),
    _item("app_premium_both", "Mobile App Premium, Android + iOS", "Mobile App", 3000000, 180, "Enterprise, scalable platform. 4-6 months."),
    _item("erp_basic", "ERP Basic (MVP)", "ERP", 200000, 42, "Single platform. 4-6 weeks."),
    _item("erp_standard", "ERP Standard", "ERP", 600000, 84, "Growing businesses. 8-12 weeks."),
    _item("erp_premium", "ERP Premium", "ERP", 1500000, 180, "Large-scale operations. 4-6 months."),
    _item("crm", "CRM Development", "CRM", 60000, 0,
          "Customers and sales pipeline in one place. Rs 60,000 to Rs 1,20,000 depending on scope; this is the starting price."),
]

SERVICES = [
    {"name": "Website + Digital Marketing packages", "telugu": "వెబ్‌సైట్ + డిజిటల్ మార్కెటింగ్ ప్యాకేజీలు", "starting": "₹24,500"},
    {"name": "Websites", "telugu": "వెబ్‌సైట్లు", "starting": "₹6,700"},
    {"name": "Social media, Meta Ads, Google Ads, Google My Business", "telugu": "సోషల్ మీడియా & యాడ్స్", "starting": "₹6,000"},
    {"name": "Mobile apps (Android & iOS)", "telugu": "మొబైల్ యాప్స్", "starting": "₹2,00,000"},
    {"name": "ERP development", "telugu": "ERP సాఫ్ట్‌వేర్", "starting": "₹2,00,000"},
    {"name": "CRM development", "telugu": "CRM సాఫ్ట్‌వేర్", "starting": "₹60,000"},
]

PRICE_LIST_FOR_AI = """
PRICE LIST (the only prices you may quote; all exclude GST):

Website + digital marketing packages. The website is one-time; social media and ads are monthly; the total includes the first month. Ad budget is extra, paid to Meta/Google (for example ₹300 a day). Domain and hosting add ₹3,000.
- Starter, for small businesses and start-ups: total ₹24,500. Static website / landing page ₹5,000; Facebook + Instagram ₹7,000 a month (10 posters + 3 reels); Meta + Google Ads ₹12,500 a month (2 campaigns each).
- Growth, for medium businesses: total ₹66,500. Dynamic website ₹19,500; Facebook, Instagram, YouTube ₹21,500 a month (15 posters + 6 reels); Meta + Google Ads ₹25,500 a month (4 campaigns each); AI tele-calling automation; 3 months post-launch support.
- Premium, for large businesses: total ₹1,21,500. Premium website / e-commerce ₹45,500; Facebook, Instagram, YouTube, LinkedIn, X ₹40,500 a month (daily posting); Meta, Google + LinkedIn Ads ₹35,500 a month (6 campaigns each); AI tele-calling automation; 3 months post-launch support.

Individual services (Starter level):
- Static website, 5-6 pages / landing page: ₹6,700, plus ₹3,000 domain and hosting.
- Social media marketing, 7 posters + 4 reels: ₹6,500.
- Meta Ads, 2 campaigns: ₹8,500; ad budget extra, for example ₹200 a day.
- Google Ads, 2 campaigns: ₹9,500; ad budget extra, for example ₹350 a day.
- Google My Business profile setup: ₹6,000, one-time.

Mobile app development:
- Basic (first version), 4-6 weeks: Android ₹2,00,000; Android + iOS ₹3,00,000.
- Standard (growing businesses), 8-12 weeks: Android ₹6,00,000; Android + iOS ₹10,00,000.
- Premium (enterprise), 4-6 months: Android ₹15,00,000; Android + iOS ₹30,00,000.

ERP development: Basic, 4-6 weeks, ₹2,00,000. Standard, 8-12 weeks, ₹6,00,000. Premium, 4-6 months, ₹15,00,000.
CRM development (customers and sales pipeline in one place): ₹60,000 to ₹1,20,000.

HOW TO TALK ABOUT PRICE:
- When asked the price, give the exact price at once. If you don't yet know which service they mean, ask that one question first.
- Give one price or one short comparison per reply. Never read out the list.
- Say amounts in words in the customer's language (for example "ఇరవై నాలుగు వేల ఐదు వందల రూపాయలు", "రెండు లక్షలు").
- Mention extras when they matter: ad budget, ₹3,000 domain and hosting, monthly charges after the first month. If they ask about tax, say prices exclude GST.
- A package's website price applies only inside that package; a website on its own is ₹6,700.
- Never give a discount, never invent or estimate a price, and never add prices together yourself beyond the totals above. For anything not listed (Growth or Premium individual services, custom software, payment terms, whether an individual service is monthly), say the team will confirm.
"""
