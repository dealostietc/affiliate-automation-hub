print("DEBUG: main.py started successfully!", flush=True)

import os
import re
import datetime
import requests
from urllib.parse import urlparse
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher
from core.price_tracker import DIYPriceTracker

# Targeted High-Urgency Feeds: Flash Deals, Deals of the Day, and Promotional Hubs
FLASH_DEAL_SOURCES = [
    # Amazon
    ("https://www.amazon.in/gp/goldbox", "Amazon", "url"),
    
    # Croma
    ("https://www.croma.com/deal-of-the-day", "Croma", "url"),
    ("https://www.croma.com/offers", "Croma", "url"),
    
    # Myntra
    ("https://www.myntra.com/shop/sale", "Myntra", "url"),
    ("https://www.myntra.com/myntra-fashion-store?f=Discount%20Range%3A50.0_100.0", "Myntra", "url"),
    
    # Ajio
    ("https://www.ajio.com/c/83", "Ajio", "url"),
    ("https://www.ajio.com/s/flash-deals", "Ajio", "url"),
    
    # Meesho
    ("https://www.meesho.com/blockbuster-deals/pl/3tp", "Meesho", "url"),
    
    # Shopsy
    ("https://www.shopsy.in/search?q=deal%20of%20the%20day", "Shopsy", "url"),
    
    # Mamaearth
    ("https://mamaearth.in/offers", "Mamaearth", "url")
]

DISCOUNT_THRESHOLD = 40.0  # 🔥 40% and above heavy discount threshold

# Use an absolute path based on this script's directory so the file is always created in the right place
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "posted_deals.txt")

def get_canonical_deal_id(url: str) -> str:
    """Extracts immutable product IDs or clean canonical URLs to prevent repetition."""
    if not url:
        return ""
    
    # 1. Amazon ASIN extraction (e.g., /dp/B08N5WRWNW or /gp/product/B08N5WRWNW)
    asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
    if asin_match:
        return f"amazon_{asin_match.group(1)}"

    # 2. Ajio Product ID extraction (e.g., /p/460123456_blue)
    ajio_match = re.search(r'/p/([a-zA-Z0-9_]+)', url)
    if ajio_match:
        return f"ajio_{ajio_match.group(1)}"

    # 3. Myntra Product ID extraction
    myntra_match = re.search(r'myntra\.com/(?:[^/]+/)?(\d+)', url)
    if myntra_match:
        return f"myntra_{myntra_match.group(1)}"

    # Fallback: Strip query parameters, fragments, and trailing slashes
    try:
        parsed = urlparse(url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        return clean_url
    except Exception:
        return url.strip()

def already_posted(url: str) -> bool:
    deal_id = get_canonical_deal_id(url)
    if not os.path.exists(HISTORY_FILE):
        return False
    
    with open(HISTORY_FILE, "r") as f:
        posted_ids = set(f.read().splitlines())
        
    is_posted = deal_id in posted_ids
    if is_posted:
        print(f"🔄 Skipped Duplicate: [{deal_id}]")
    return is_posted

def mark_as_posted(url: str):
    deal_id = get_canonical_deal_id(url)
    if not deal_id:
        print(f"⚠️ Warning: Could not extract deal ID from URL: {url}")
        return
        
    posted_ids = set()
    
    # Ensure file exists or create it explicitly
    if not os.path.exists(HISTORY_FILE):
        print(f"📁 Initializing history file at: {HISTORY_FILE}")
        with open(HISTORY_FILE, "w") as f:
            pass

    try:
        with open(HISTORY_FILE, "r") as f:
            posted_ids = set(f.read().splitlines())
    except Exception as e:
        print(f"⚠️ Error reading history file: {e}")
            
    posted_ids.add(deal_id)
        
    posted_list = list(posted_ids)[-2000:]
    try:
        with open(HISTORY_FILE, "w") as f:
            f.write("\n".join(posted_list) + "\n")
        print(f"📝 Successfully saved deal ID [{deal_id}] to history.")
    except Exception as e:
        print(f"⚠️ Error writing to history file: {e}")
