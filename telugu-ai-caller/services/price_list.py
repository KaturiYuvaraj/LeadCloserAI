"""
S P Associates price list: the one place prices live.

The AI's call instructions (PRICE_LIST_FOR_AI), the company profile's service list (SERVICES)
and the quotation price book (PRICE_BOOK) are all built from here, so they can't disagree.
Change a price here only. All prices exclude 18% GST.
"""

from typing import Any, Dict, List


def _item(code: str, name: str, category: str, price: float, days: int, deliverables: str) -> Dict[str, Any]:
    return {"code": code, "name": name, "category": category, "base_price_inr": float(price),
            "max_discount_pct": 10.0, "delivery_days": days, "deliverables": deliverables, "active": True}


# delivery_days 0 = not agreed yet: the team confirms it
PRICE_BOOK: List[Dict[str, Any]] = [
    _item("pkg_starter", "Starter Package (website + marketing)", "Website + Digital Marketing", 24500, 0,
          "Static website / landing page Rs 5,000 (one-time). Facebook + Instagram: 10 posters + 3 reels Rs 7,000/month. "
          "Meta + Google Ads, 2 campaigns each, Rs 12,500/month. "
          "Ad budget extra, paid to Meta/Google. Domain and hosting Rs 3,000 extra."),
    _item("pkg_growth", "Growth Package (website + marketing)", "Website + Digital Marketing", 66500, 0,
          "Dynamic website Rs 19,500 (one-time). Facebook, Instagram, YouTube: 15 posters + 6 reels Rs 21,500/month. "
          "Meta + Google Ads, 4 campaigns each, Rs 25,500/month. AI tele-calling automation, 3 months post-launch support. "
          "Ad budget extra. Domain and hosting Rs 3,000 extra."),
    _item("pkg_premium", "Premium Package (website + marketing)", "Website + Digital Marketing", 121500, 0,
          "Premium website / e-commerce Rs 45,500 (one-time). Facebook, Instagram, YouTube, LinkedIn, X: daily posting "
          "Rs 40,500/month. Meta, Google + LinkedIn Ads, 6 campaigns each, Rs 35,500/month. AI tele-calling automation, "
          "3 months post-launch support. Ad budget extra. Domain and hosting Rs 3,000 extra."),
    _item("svc_static_website", "Static Website (individual)", "Individual Services", 6700, 0,
          "5-6 pages / landing page. Domain and hosting Rs 3,000 extra."),
    _item("svc_social_media", "Social Media Marketing (individual)", "Individual Services", 6500, 0, "7 posters + 4 reels."),
    _item("svc_meta_ads", "Meta Ads (individual)", "Individual Services", 8500, 0,
          "2 campaigns. Ad budget extra, e.g. Rs 200/day."),
    _item("svc_google_ads", "Google Ads (individual)", "Individual Services", 9500, 0,
          "2 campaigns. Ad budget extra, e.g. Rs 350/day."),
    _item("svc_gmb", "Google My Business Profile Setup", "Individual Services", 6000, 0, "One-time."),
    _item("svc_growth_website", "Dynamic Website, 10-15 pages (individual)", "Individual Services", 14500, 0, "Domain and hosting Rs 3,000 extra."),
    _item("svc_growth_social", "Complete Social Media Marketing (individual)", "Individual Services", 16500, 0, "15 posters + 6 reels."),
    _item("svc_growth_meta_ads", "Meta Ads, Growth (individual)", "Individual Services", 16500, 0, "3 campaigns. Ad budget extra, e.g. Rs 300/day."),
    _item("svc_growth_google_ads", "Google Ads, Growth (individual)", "Individual Services", 10500, 0, "3 campaigns. Ad budget extra, e.g. Rs 400/day."),
    _item("svc_growth_gmb", "GMB Setup + GMB Ads, Growth", "Individual Services", 8500, 0, "One-time setup, GMB Ads included. Ad budget Rs 500/day."),
    _item("svc_premium_website", "Premium Website (individual)", "Individual Services", 35500, 0, "Domain and hosting Rs 3,000 extra."),
    _item("svc_premium_social", "360 Complete Social Media Marketing (individual)", "Individual Services", 32500, 0, "Posting daily."),
    _item("svc_premium_meta_ads", "Meta Ads, Premium (individual)", "Individual Services", 32500, 0, "10 campaigns. Ad budget extra, e.g. Rs 1,000/day."),
    _item("svc_premium_google_ads", "Google Ads, Premium (individual)", "Individual Services", 10500, 0, "3 campaigns. Ad budget extra, e.g. Rs 1,500/day."),
    _item("svc_premium_gmb", "GMB Setup + GMB Ads, Premium", "Individual Services", 15500, 0, "One-time setup, GMB Ads included. Ad budget Rs 1,000/day."),
    _item("app_basic_android", "Mobile App Basic / MVP, Android", "Mobile App", 200000, 42, "Single platform, first version. 4-6 weeks. Server and hosting paid by the client."),
    _item("app_basic_both", "Mobile App Basic / MVP, Android + iOS", "Mobile App", 300000, 42, "First version. 4-6 weeks. Server and hosting paid by the client."),
    _item("app_standard_android", "Mobile App Standard / Business Growth, Android", "Mobile App", 600000, 84, "Business growth app. 8-12 weeks. Server and hosting paid by the client."),
    _item("app_standard_both", "Mobile App Standard / Business Growth, Android + iOS", "Mobile App", 1000000, 84, "Business growth app. 8-12 weeks. Server and hosting paid by the client."),
    _item("app_premium_android", "Mobile App Premium / Enterprise, Android", "Mobile App", 1500000, 180, "Enterprise, scalable platform. 4-6 months. Server and hosting paid by the client."),
    _item("app_premium_both", "Mobile App Premium / Enterprise, Android + iOS", "Mobile App", 3000000, 180, "Enterprise, scalable platform. 4-6 months. Server and hosting paid by the client."),
    _item("erp_basic", "ERP Basic / MVP", "ERP", 200000, 42, "Single platform. 4-6 weeks. Server and hosting paid by the client."),
    _item("erp_standard", "ERP Standard / Business Growth", "ERP", 600000, 84, "Growing businesses. 8-12 weeks. Server and hosting paid by the client."),
    _item("erp_premium", "ERP Premium / Enterprise", "ERP", 1500000, 180, "Large-scale operations. 4-6 months. Server and hosting paid by the client."),
    _item("crm", "CRM Development", "CRM", 60000, 0,
          "Customers and sales pipeline in one place. Rs 60,000 to Rs 1,20,000 depending on features; this is the starting price. Server and hosting paid by the client."),
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
PRICE GUIDE (the only prices you may quote). Every price excludes 18% GST.

FIND THE RIGHT SERVICE FIRST. If it isn't clear which service they mean, ask; never guess. Ask only what you don't already know, one question at a time: what kind of business they have; whether they need a website, social media and ads, a mobile app, or software like ERP or CRM; for marketing, whether the business is small and just starting, growing, or already large; for apps, Android only or both Android and iPhone.

WEBSITE + DIGITAL MARKETING PACKAGES:
- Starter (small businesses, start-ups). Static website / landing page ₹5,000 one-time. Facebook + Instagram, 10 posters + 3 reels, ₹7,000 a month. Meta + Google Ads, 2 campaigns each, ₹12,500 a month. Package total ₹24,500.
- Growth (medium businesses ready to scale). Dynamic website ₹19,500 one-time. Facebook, Instagram, YouTube, 15 posters + 6 reels, ₹21,500 a month. Meta + Google Ads, 4 campaigns each, ₹25,500 a month. Free: AI tele-calling automation and 3 months support after launch. Package total ₹66,500.
- Premium (large businesses). Premium website / e-commerce ₹45,500 one-time. Facebook, Instagram, YouTube, LinkedIn, X, daily posting, ₹40,500 a month. Meta, Google and LinkedIn Ads, 6 campaigns each, ₹35,500 a month. Free: AI tele-calling automation and 3 months support after launch. Package total ₹1,21,500.
With every package, say in one short sentence: this is our service charge; the ad budget on Facebook or Google is separate, around ₹300 a day; domain and hosting is ₹3,000 extra; GST is 18% on top.

INDIVIDUAL SERVICES, Starter (small businesses):
- Static website, 5-6 pages or a landing page: ₹6,700, plus ₹3,000 domain and hosting.
- Social media marketing, 7 posters + 4 reels: ₹6,500 (team will confirm if monthly).
- Meta Ads, 2 campaigns: ₹8,500, ad budget extra, for example ₹200 a day (team will confirm if monthly).
- Google Ads, 2 campaigns: ₹9,500, ad budget extra, for example ₹350 a day (team will confirm if monthly).
- Google My Business setup: ₹6,000 one-time.
- All five together: ₹37,200.

INDIVIDUAL SERVICES, Growth (medium businesses):
- Dynamic website, 10-15 pages: ₹14,500, plus ₹3,000 domain and hosting.
- Complete social media marketing, 15 posters + 6 reels: ₹16,500 (team will confirm if monthly).
- Meta Ads, 3 campaigns: ₹16,500, ad budget extra, for example ₹300 a day (team will confirm if monthly).
- Google Ads, 3 campaigns: ₹10,500, ad budget extra, for example ₹400 a day (team will confirm if monthly).
- Google My Business setup + GMB Ads: ₹8,500 one-time, ad budget ₹500 a day.
- All five together: ₹66,500.

INDIVIDUAL SERVICES, Premium (large businesses):
- Premium website: ₹35,500, plus ₹3,000 domain and hosting.
- 360 complete social media marketing, posting daily: ₹32,500 (team will confirm if monthly).
- Meta Ads, 10 campaigns: ₹32,500, ad budget extra, for example ₹1,000 a day (team will confirm if monthly).
- Google Ads, 3 campaigns: ₹10,500, ad budget extra, for example ₹1,500 a day (team will confirm if monthly).
- Google My Business setup + GMB Ads: ₹15,500 one-time, ad budget ₹1,000 a day.
- All five together: ₹1,26,500.

Package prices and individual prices are separate lists: never mix them. For example the Starter website is ₹5,000 inside the package and ₹6,700 on its own.

MOBILE APPS (server and hosting paid separately by the client, GST 18% extra):
- Basic / MVP (first version), 4-6 weeks: Android only ₹2,00,000; Android + iPhone ₹3,00,000.
- Standard / Business Growth (growing businesses), 8-12 weeks: Android only ₹6,00,000; Android + iPhone ₹10,00,000.
- Premium / Enterprise (large products), 4-6 months: Android only ₹15,00,000; Android + iPhone ₹30,00,000.

ERP SOFTWARE (server and hosting paid by the client, GST extra): Basic / MVP, 4-6 weeks, ₹2,00,000. Standard / Business Growth, 8-12 weeks, ₹6,00,000. Premium / Enterprise, 4-6 months, ₹15,00,000.

CRM SOFTWARE (server and hosting paid by the client, GST extra): ₹60,000 to ₹1,20,000 depending on features; the team gives the exact price after understanding their needs.

FINAL AMOUNT WITH 18% GST, only if they ask:
- Packages: Starter ₹28,910. Growth ₹78,470. Premium ₹1,43,370.
- Individual, Starter: website ₹7,906; social media ₹7,670; Meta Ads ₹10,030; Google Ads ₹11,210; Google My Business ₹7,080; all five ₹43,896.
- Individual, Growth: website ₹17,110; social media ₹19,470; Meta Ads ₹19,470; Google Ads ₹12,390; Google My Business ₹10,030; all five ₹78,470.
- Individual, Premium: website ₹41,890; social media ₹38,350; Meta Ads ₹38,350; Google Ads ₹12,390; Google My Business ₹18,290; all five ₹1,49,270.
- Apps, Android: ₹2,36,000 / ₹7,08,000 / ₹17,70,000. Android + iPhone: ₹3,54,000 / ₹11,80,000 / ₹35,40,000 (Basic / Standard / Premium).
- ERP: ₹2,36,000 / ₹7,08,000 / ₹17,70,000 (Basic / Standard / Premium). CRM: ₹70,800 to ₹1,41,600.

HOW TO TALK ABOUT PRICE:
- Give the exact price at once, then the extras that apply, in the customer's language. A price reply may be up to about 45 words. Never read out the list.
- Say amounts in words, in lakhs and thousands, never "hundred thousand". Telugu: ₹24,500 = ఇరవై నాలుగు వేల ఐదు వందల రూపాయలు; ₹1,21,500 = ఒక లక్ష ఇరవై ఒక్క వేల ఐదు వందల రూపాయలు; ₹2,00,000 = రెండు లక్షల రూపాయలు. English: one lakh twenty-one thousand five hundred rupees.
- Never invent a price and never add prices yourself.
- NEGOTIABLE: after giving a price, mention once, politely, that the price is negotiable and our team can discuss the final amount with them, for example if they want to start soon. Never name a discount, a percentage or a lower amount yourself: the team decides the final price.
- SEVERAL SERVICES OR A DETAILED REQUIREMENT: when the customer explains a full requirement (several services together, a custom app or software with many features) and asks what it will cost in total, don't add up prices or guess a total. Say politely, in their language, the meaning of: "I understand your requirement. I'll share it with our team, and they'll send you the pricing as soon as possible." Then ask for their name and WhatsApp number.
- If a price isn't here or is marked team will confirm, say the team will confirm that price and call back. The same goes for how packages are billed after the first month, payment terms, whether domain and hosting repeats every year, and anything else not written here.
- Timelines: use only the times above for apps and ERP. For websites and everything else, say the team will confirm the timeline after the free consultation. Never promise a shorter time than listed.

COMMON QUESTIONS (say the meaning, in their language):
- Why is the ad budget separate? It goes directly to Facebook or Google to show their ads. Our fee is for planning, creating and managing those ads. They stay in full control of how much they spend.
- What is domain and hosting? The domain is the website name, like yourbusiness.com. Hosting keeps the website online. Together they are ₹3,000.
- Can I start small? Yes. Starter or individual services are a good start, and they can move to Growth later.
- Too expensive? Say you understand, that the price is negotiable and our team will discuss it with them. You can also suggest Starter or individual services, and offer a free consultation call.

CLOSING. A demo and a free consultation are the same call: call it a free consultation. End every pricing conversation by asking for their name and WhatsApp number, one at a time, and offering the free consultation with a detailed quotation. If you already know their name, don't ask it again; ask if this same number is on WhatsApp. When they give these details, add [CONTACT: name | number] at the end of the reply, writing "same" for the number they are calling on.
"""
