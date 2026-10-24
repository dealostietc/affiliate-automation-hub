print("DEBUG: main.py started successfully!", flush=True)

import os
import re
import datetime
import requests
from urllib.parse import urlparse
from core.price_tracker import DIYPriceTracker

# =========================================================================
# 🎛️ E-COMMERCE PLATFORM FILTER TOGGLE (Set True to Enable, False to Disable)
# =========================================================================
ENABLED_PLATFORMS = {
    # Heavyweight Retail & Marketplace
    "amazon": True,         # Amazon India
    "flipkart": True,       # Flipkart
    "meesho": True,         # Meesho
    "shopsy": True,         # Shopsy
    "tata cliq": True,      # Tata Cliq
    
    # Fashion & Apparel
    "myntra": True,         # Myntra
    "ajio": True,           # Ajio
    "nykaa": True,          # Nykaa
    "shoppers stop": True,  # Shoppers Stop
    
    # Electronics & Gadgets
    "croma": True,          # Croma
    "vijay sales": True,    # Vijay Sales
    "reliance digital": True,
    "samsung": True,        # Samsung India
    
    # Beauty, Personal Care & Baby
    "mamaearth": True,      # Mamaearth
    "firstcry": True,       # FirstCry
}

DISCOUNT_THRESHOLD = 40.0  # 🔥 Minimum target discount percentage
MAX_PAGES_TO_FETCH = 10    # 🔄 Fetch up to 10 pages (~300 to 500 deals per run)
CUELINKS_API_URL = "https://developers.cuelinks.com/pub_api/v3/offers"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "posted_deals.txt")

def get_canonical_deal_id(url: str) -> str:
    """Extracts immutable product IDs or clean canonical URLs to prevent repetition."""
    if not url:
        return ""
    
    asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
    if asin_match:
        return f"amazon_{asin_match.group(1)}"

    ajio_match = re.search(r'/p/([a-zA-Z0-9_]+)', url)
    if ajio_match:
        return f"ajio_{ajio_match.group(1)}"

    myntra_match = re.search(r'myntra\.com/(?:[^/]+/)?(\d+)', url)
    if myntra_match:
        return f"myntra_{myntra_match.group(1)}"

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
        print(f"🔄 Skipped Duplicate: [{deal_id}]", flush=True)
    return is_posted

def mark_as_posted(url: str):
    deal_id = get_canonical_deal_id(url)
    if not deal_id:
        return
        
    posted_ids = set()
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w") as f:
            pass

    try:
        with open(HISTORY_FILE, "r") as f:
            posted_ids = set(f.read().splitlines())
    except Exception:
        pass
            
    posted_ids.add(deal_id)
    posted_list = list(posted_ids)[-2000:]
    try:
        with open(HISTORY_FILE, "w") as f:
            f.write("\n".join(posted_list) + "\n")
        print(f"📝 Saved deal ID [{deal_id}] to history.", flush=True)
    except Exception as e:
        print(f"⚠️ Error writing history: {e}", flush=True)

def is_platform_enabled(platform_name: str) -> bool:
    if not platform_name:
        return True

    platform_lower = platform_name.lower().strip()
    for key, is_enabled in ENABLED_PLATFORMS.items():
        if key in platform_lower:
            return is_enabled
    return True

def extract_discount_from_title(title: str) -> float:
    """Parses text titles like 'Flat 50% OFF' or 'Get 60% Discount' to discover high deals."""
    match = re.search(r'(\d{2})%\s*(?:off|discount)', title, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 0.0

def fetch_cuelinks_deals() -> list:
    """Fetches paginated deal feeds across multiple pages from Cuelinks V3 API."""
    api_key = os.getenv("CUELINKS_API_KEY")
    if not api_key:
        print("❌ CRITICAL ERROR: CUELINKS_API_KEY secret is missing!", flush=True)
        return []

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    products = []
    print(f"🌐 Fetching live deal feed across {MAX_PAGES_TO_FETCH} pages from Cuelinks V3...", flush=True)

    for page in range(1, MAX_PAGES_TO_FETCH + 1):
        try:
            url = f"{CUELINKS_API_URL}?page={page}&per_page=50"
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                print(f"⚠️ Page {page} returned status {response.status_code}", flush=True)
                break

            data = response.json()
            deals_list = data.get("data", data) if isinstance(data, dict) else data

            if not isinstance(deals_list, list) or not deals_list:
                print(f"ℹ️ Reached end of available deals at page {page - 1}.", flush=True)
                break

            print(f"📦 Page {page}: Retrieved {len(deals_list)} items.", flush=True)

            for item in deals_list:
                title = item.get("title") or item.get("name") or item.get("description", "Hot Deal")
                tracking_url = item.get("tracking_url") or item.get("affiliate_url") or item.get("url", "")
                image = item.get("image_url") or item.get("image", "")
                
                campaign_field = item.get("campaign")
                if isinstance(campaign_field, dict):
                    platform = campaign_field.get("name", "E-Commerce")
                else:
                    platform = item.get("merchant") or item.get("store") or str(campaign_field or "E-Commerce")

                if not is_platform_enabled(platform):
                    continue

                try:
                    price = float(item.get("special_price") or item.get("price") or item.get("selling_price", 0))
                    mrp = float(item.get("mrp") or item.get("value") or item.get("list_price", price))
                except (ValueError, TypeError):
                    price, mrp = 0.0, 0.0

                if tracking_url:
                    products.append({
                        "title": title,
                        "url": tracking_url,
                        "image": image,
                        "platform": platform,
                        "price": price,
                        "mrp": mrp
                    })

        except Exception as e:
            print(f"❌ Error fetching page {page}: {e}", flush=True)
            break

    print(f"📊 Total raw items collected across all pages: {len(products)}", flush=True)
    return products

def send_telegram_post(deal: dict, tracker_info: dict):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram bot token or chat ID missing.", flush=True)
        return

    title = deal.get("title", "Hot Deal")
    platform = deal.get("platform", "E-Commerce")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", price)
    discount = deal.get("discount", 0)
    url_link = deal.get("url", "")
    image_url = deal.get("image")

    lowest_badge = "⚡ **ALL-TIME LOWEST PRICE EVER!** ⚡\n" if tracker_info.get("is_lowest_ever") else ""

    caption = (
        f"🚨 <b>LIVE FLASH DEAL - {discount}% OFF!</b> 🚨\n\n"
        f"{lowest_badge}"
        f"📦 <b>{title}</b>\n\n"
        f"🏷️ <b>Platform:</b> {platform}\n"
        f"💰 <b>Deal Price:</b> ₹{price:,.2f}\n"
        f"❌ <b>MRP:</b> ₹{mrp:,.2f}\n"
        f"📉 <b>Tracked Lowest:</b> ₹{tracker_info.get('lowest_ever', price):,.2f}\n"
        f"📊 <b>Historical Avg:</b> ₹{tracker_info.get('historical_avg', price):,.2f}\n\n"
        f"🔗 <a href='{url_link}'>Grab Flash Deal Now</a>"
    )

    headers = {"Content-Type": "application/json"}

    if image_url:
        try:
            res = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                json={"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "HTML"},
                headers=headers
            ).json()
            if res.get("ok"):
                print(f"✅ Sent photo alert for: {title}", flush=True)
                return
        except Exception as e:
            print(f"⚠️ Failed photo post: {e}", flush=True)

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "disable_web_page_preview": False},
            headers=headers
        )
    except Exception as e:
        print(f"⚠️ Failed text post: {e}", flush=True)

def run_deal_pipeline():
    print("DEBUG: Initializing price tracker...", flush=True)
    try:
        tracker = DIYPriceTracker()
        print("DEBUG: Price tracker initialized successfully.", flush=True)
    except Exception as e:
        print(f"❌ CRITICAL ERROR during tracker initialization: {e}", flush=True)
        return

    valid_deals = []
    extracted_products = fetch_cuelinks_deals()

    for product in extracted_products:
        url = product.get("url")
        title = product.get("title", "")
        if not url or already_posted(url):
            continue

        price = float(product.get("price", 0))
        mrp = float(product.get("mrp", price))
        
        # Method 1: Calculated Numeric Discount
        discount = 0.0
        if mrp > price > 0:
            discount = round(((mrp - price) / mrp) * 100, 2)

        # Method 2: Fallback Title Keyword Discount Parsing
        if discount == 0.0:
            discount = extract_discount_from_title(title)

        if discount >= DISCOUNT_THRESHOLD:
            product["discount"] = discount
            
            tracker_info = tracker.track_and_evaluate(
                url=url,
                title=title,
                platform=product.get("platform"),
                price=price,
                mrp=mrp
            )
            product["tracker_info"] = tracker_info

            valid_deals.append(product)
            print(f" -> Best Deal Captured: {title[:40]} ({discount}% off) on {product.get('platform')}", flush=True)

    if not valid_deals:
        print("\nNo new matching 40%+ deals found in this run.", flush=True)
        return

    print(f"\nDiscovered {len(valid_deals)} deal(s). Broadcasting to Telegram...", flush=True)
    for deal in valid_deals:
        send_telegram_post(deal, deal.get("tracker_info", {}))
        mark_as_posted(deal.get("url"))

if __name__ == "__main__":
    run_deal_pipeline()
