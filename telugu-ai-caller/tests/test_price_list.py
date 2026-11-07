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
        "app_basic_android": 200000, "app_basic_both": 300000, "app_standard_android": 600000, "app_standard_both": 1000000,
        "app_premium_android": 1500000, "app_premium_both": 3000000,
        "erp_basic": 200000, "erp_standard": 600000, "erp_premium": 1500000, "crm": 60000,
    }


def test_ai_is_told_every_price_and_the_rules():
    prompt = sales_agent._build_system_prompt(None)
    for text in ("₹24,500", "₹66,500", "₹1,21,500", "₹6,700", "₹6,500", "₹8,500", "₹9,500", "₹6,000", "₹2,00,000", "₹3,00,000",
                 "₹6,00,000", "₹10,00,000", "₹15,00,000", "₹30,00,000", "₹60,000 to ₹1,20,000", "₹3,000", "exclude GST"):
        assert text in prompt, text
    assert "Never give a discount" in prompt and "the team will confirm" in prompt


def test_old_prices_are_gone_from_what_the_ai_sees():
    prompt = sales_agent._build_system_prompt(None)
    for old in ("₹25,000", "₹45,000", "₹20,000", "₹30,000\"", "₹5.00/min", "Flexible milestone"):
        assert old not in prompt, old


def test_profile_and_quotations_use_the_same_list():
    assert json.loads(get_company_profile()["services_offered"]) == SERVICES
    assert DEFAULT_PRICE_BOOK is PRICE_BOOK
    assert "₹6,700" in PRICE_LIST_FOR_AI
