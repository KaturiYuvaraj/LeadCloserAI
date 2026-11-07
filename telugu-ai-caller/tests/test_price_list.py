"""The real price list reaches the AI, the company profile and the quotation price book. Offline."""

import json

from database import get_company_profile
from services.price_list import PRICE_BOOK, PRICE_LIST_FOR_AI, SERVICES
from services.quotation_service import DEFAULT_PRICE_BOOK
from services.sales_agent import sales_agent

PRICES = {item["code"]: item["base_price_inr"] for item in PRICE_BOOK}


def test_package_totals_add_up():
    assert PRICES["pkg_starter"] == 5000 + 7000 + 12500
    assert PRICES["pkg_growth"] == 19500 + 21500 + 25500
    assert PRICES["pkg_premium"] == 45500 + 40500 + 35500


def test_every_listed_price():
    assert PRICES == {
        "pkg_starter": 24500, "pkg_growth": 66500, "pkg_premium": 121500,
        "svc_static_website": 6700, "svc_social_media": 6500, "svc_meta_ads": 8500, "svc_google_ads": 9500, "svc_gmb": 6000,
        "svc_growth_website": 14500, "svc_growth_social": 16500, "svc_growth_meta_ads": 16500, "svc_growth_google_ads": 10500,
        "svc_growth_gmb": 8500, "svc_premium_website": 35500, "svc_premium_social": 32500, "svc_premium_meta_ads": 32500,
        "svc_premium_google_ads": 10500, "svc_premium_gmb": 15500,
        "app_basic_android": 200000, "app_basic_both": 300000, "app_standard_android": 600000, "app_standard_both": 1000000,
        "app_premium_android": 1500000, "app_premium_both": 3000000,
        "erp_basic": 200000, "erp_standard": 600000, "erp_premium": 1500000, "crm": 60000,
    }


def test_ai_is_told_every_price_and_the_rules():
    prompt = sales_agent._build_system_prompt(None)
    for text in ("₹24,500", "₹66,500", "₹1,21,500", "₹6,700", "₹6,500", "₹8,500", "₹9,500", "₹6,000", "₹2,00,000", "₹3,00,000",
                 "₹6,00,000", "₹10,00,000", "₹15,00,000", "₹30,00,000", "₹60,000 to ₹1,20,000", "₹3,000", "excludes 18% GST"):
        assert text in prompt, text
    assert "never offer or agree to a discount" in prompt and "team will confirm" in prompt


def test_old_prices_are_gone_from_what_the_ai_sees():
    prompt = sales_agent._build_system_prompt(None)
    for old in ("₹25,000", "₹45,000", "₹20,000", "₹30,000\"", "₹5.00/min", "Flexible milestone"):
        assert old not in prompt, old


def test_profile_and_quotations_use_the_same_list():
    assert json.loads(get_company_profile()["services_offered"]) == SERVICES
    assert DEFAULT_PRICE_BOOK is PRICE_BOOK
    assert "₹6,700" in PRICE_LIST_FOR_AI


def test_monthly_amounts_and_gst_figures_are_right():
    for price, with_gst in ((24500, "₹28,910"), (66500, "₹78,470"), (121500, "₹1,43,370"), (200000, "₹2,36,000"), (300000, "₹3,54,000")):
        lakhs = round(price * 1.18)
        digits = "".join(ch for ch in with_gst if ch.isdigit())
        assert int(digits) == lakhs and with_gst in PRICE_LIST_FOR_AI
    # the owner said these from-second-month amounts are wrong: the AI must not quote them
    for wrong in ("₹19,500 a month", "₹47,000 a month", "₹76,000 a month", "From the second month"):
        assert wrong not in PRICE_LIST_FOR_AI
    assert "billed after the first month" in PRICE_LIST_FOR_AI


def test_guide_rules_are_in_the_prompt():
    for text in ("Our prices are fixed", "free consultation", "server and hosting", "in lakhs and thousands",
                 "Why is the ad budget separate", "Never promise a shorter time", "[CONTACT: name | number]"):
        assert text.lower() in PRICE_LIST_FOR_AI.lower(), text


def test_contact_details_are_saved():
    from core.db import SessionLocal
    from models import Lead
    from tests.test_dialer import make_lead
    from voice_agent.actions import save_contact

    def variables(lead_id):
        session = SessionLocal()
        try:
            return dict(session.get(Lead, lead_id).variables or {})
        finally:
            session.close()

    lead = make_lead(name="Contact Chinna", phone="+919812300901")
    assert save_contact(lead, "Ravi | 98765 43210")["ok"]
    assert variables(lead)["contact_name"] == "Ravi" and variables(lead)["whatsapp_number"] == "+919876543210"
    same = make_lead(name="Same Sudha", phone="+919812300902")
    save_contact(same, "Sudha | same")
    assert variables(same)["whatsapp_number"] == "+919812300902"
    bad = make_lead(name="Bad Bala", phone="+919812300903")
    save_contact(bad, "| 12345")
    assert "whatsapp_number" not in variables(bad) and variables(bad)["whatsapp_number_to_check"] == "12345"


def test_inbound_caller_gets_their_real_name():
    from core.db import SessionLocal
    from models import Lead
    from tests.test_dialer import make_lead
    from voice_agent.actions import save_contact
    lead = make_lead(name="Inbound caller 9812300904", phone="+919812300904")
    save_contact(lead, "Lakshmi | same")
    session = SessionLocal()
    assert session.get(Lead, lead).name == "Lakshmi"
    session.close()


def test_contact_marker_is_removed_from_speech():
    from voice_agent.conclusion import split_actions
    emit, _, actions = split_actions("ధన్యవాదాలు అండి. [CONTACT: Ravi | 9876543210]")
    assert "CONTACT" not in emit and actions == [("CONTACT", "Ravi | 9876543210")]


def test_individual_totals_and_every_gst_figure():
    assert 6700 + 6500 + 8500 + 9500 + 6000 == 37200
    assert 14500 + 16500 + 16500 + 10500 + 8500 == 66500
    assert 35500 + 32500 + 32500 + 10500 + 15500 == 126500

    def rupees(n):  # Indian grouping: 1,49,270
        text = str(n)
        if len(text) <= 3:
            return "₹" + text
        head, tail = text[:-3], text[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        return "₹" + ",".join(([head] if head else []) + groups + [tail])

    for price in (24500, 66500, 121500, 6700, 6500, 8500, 9500, 6000, 37200, 14500, 16500, 10500, 35500, 32500, 15500,
                  126500, 200000, 300000, 600000, 1000000, 1500000, 3000000, 60000, 120000):
        assert rupees(round(price * 1.18)) in PRICE_LIST_FOR_AI, price

