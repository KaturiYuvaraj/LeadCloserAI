"""
Tests for the replicated Outpero.com pages, static assets, and navigation links.
"""
import re
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_outpero_pages_render_200():
    routes = [
        "/",
        "/voices",
        "/pricing",
        "/contact",
        "/product/instant-leads",
        "/product/campaigns",
        "/product/inbound",
        "/ai-voice-agents",
        "/compare",
        "/crm",
        "/login",
    ]
    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 200, f"Route {route} returned {resp.status_code}"
        assert "/static/logo.png" in resp.text, f"Route {route} missing /static/logo.png"


def test_outpero_static_assets_exist():
    assets = [
        "/static/css/outpero.css",
        "/static/js/outpero.js",
        "/static/logo.png",
        "/static/sarvam-logo.png",
        "/static/cartesia-logo.png",
        "/static/site/brand/outpero-wordmark.png",
        "/static/site/integrations/whatsapp.svg",
        "/static/site/integrations/google-calendar.svg",
        "/static/site/integrations/meta.svg",
        "/static/site/integrations/hubspot.svg",
        "/static/site/integrations/zoho.svg",
    ]
    for asset in assets:
        resp = client.get(asset)
        assert resp.status_code == 200, f"Asset {asset} returned {resp.status_code}"


def test_no_broken_next_image_urls():
    pages = [
        "/",
        "/voices",
        "/pricing",
        "/contact",
        "/product/instant-leads",
        "/product/campaigns",
        "/product/inbound",
    ]
    for page in pages:
        html = client.get(page).text
        assert "/_next/image" not in html, f"Page {page} still contains /_next/image URL"
        for img_src in re.findall(r'<img[^>]+src="([^"]+)"', html):
            if img_src.startswith("/"):
                r = client.get(img_src)
                assert r.status_code == 200, f"Broken image {img_src} on {page}"
