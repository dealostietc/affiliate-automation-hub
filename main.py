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
        print(f"🔄 Skipped Duplicate: [{deal_id}]", flush=True)
    return is_posted

def mark_as_posted(url: str):
    deal_id = get_canonical_deal_id(url)
    if not deal_id:
        print(f"⚠️ Warning: Could not extract deal ID from URL: {url}", flush=True)
        return
        
    posted_ids = set()
    
    # Ensure file exists or create it explicitly
    if not os.path.exists(HISTORY_FILE):
        print(f"📁 Initializing history file at: {HISTORY_FILE}", flush=True)
        with open(HISTORY_FILE, "w") as f:
            pass

    try:
        with open(HISTORY_FILE, "r") as f:
            posted_ids = set(f.read().splitlines())
    except Exception as e:
        print(f"⚠️ Error reading history file: {e}", flush=True)
            
    posted_ids.add(deal_id)
        
    posted_list = list(posted_ids)[-2000:]
    try:
        with open(HISTORY_FILE, "w") as f:
            f.write("\n".join(posted_list) + "\n")
        print(f"📝 Successfully saved deal ID [{deal_id}] to history.", flush=True)
    except Exception as e:
        print(f"⚠️ Error writing to history file: {e}", flush=True)

def send_telegram_post(deal: dict, tracker_info: dict):
    """Sends formatted flash deal alert with DIY price history insights."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram bot token or chat ID not set in environment variables.", flush=True)
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
                print(f"✅ Sent photo alert to Telegram for: {title}", flush=True)
                return
        except Exception as e:
            print(f"⚠️ Failed to send photo message: {e}", flush=True)

    # Fallback to text message
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "disable_web_page_preview": False},
            headers=headers
        ).json()
        if res.get("ok"):
            print(f"✅ Sent text alert to Telegram for: {title}", flush=True)
        else:
            print(f"⚠️ Telegram API error: {res}", flush=True)
    except Exception as e:
        print(f"⚠️ Failed to send text message: {e}", flush=True)

def run_deal_pipeline():
    print("DEBUG: Initializing fetcher and price tracker...", flush=True)
    try:
        fetcher = MultiEcomFetcher()
        tracker = DIYPriceTracker()  # Initialized with SQLite database
        print("DEBUG: Fetcher and tracker initialized successfully.", flush=True)
    except Exception as e:
        print(f"❌ CRITICAL ERROR during initialization: {e}", flush=True)
        return

    valid_deals = []

    print(f"🚀 Running Flash Deals & Deals of the Day Pipeline ({len(FLASH_DEAL_SOURCES)} targeted live hubs)...", flush=True)

    for source, platform, source_type in FLASH_DEAL_SOURCES:
        print(f"\nScanning Live Deal Hub [{platform}] -> {source}", flush=True)
        extracted_products = []

        try:
            if platform.lower() == "amazon":
                extracted_products = fetcher.fetch_amazon_search(source)
            elif platform.lower() == "myntra":
                extracted_products = fetcher.fetch_myntra_search(source)
            elif platform.lower() == "ajio":
                extracted_products = fetcher.fetch_ajio_search(source)
            elif platform.lower() == "croma":
                extracted_products = fetcher.fetch_croma_search(source)
            elif platform.lower() == "meesho":
                extracted_products = fetcher.fetch_meesho_search(source)
            elif platform.lower() == "shopsy":
                extracted_products = fetcher.fetch_shopsy_search(source)
            elif platform.lower() == "mamaearth":
                extracted_products = fetcher.fetch_mamaearth_search(source)
            print(f"DEBUG [{platform}]: Extracted {len(extracted_products)} raw items.", flush=True)
        except Exception as e:
            print(f"⚠️ Error fetching live deals from {platform} ({source}): {e}", flush=True)
            continue

        for product in extracted_products:
            url = product.get("url")
            if not url or already_posted(url):
                continue

            price = float(product.get("price", 0))
            mrp = float(product.get("mrp", price))
            discount = 0.0
            if mrp > price > 0:
                discount = round(((mrp - price) / mrp) * 100, 2)

            if discount >= DISCOUNT_THRESHOLD:
                product["discount"] = discount
                product["platform"] = platform
                
                tracker_info = tracker.track_and_evaluate(
                    url=url,
                    title=product.get("title"),
                    platform=platform,
                    price=price,
                    mrp=mrp
                )
                product["tracker_info"] = tracker_info

                valid_deals.append(product)
                print(f" -> Flash Deal Captured: {product.get('title')} ({discount}% off) on {platform}", flush=True)

    if not valid_deals:
        print("\nNo new 40%+ flash deals discovered in this run.", flush=True)
        return

    print(f"\nDiscovered {len(valid_deals)} flash deal(s). Broadcasting to Telegram...", flush=True)
    for deal in valid_deals:
        send_telegram_post(deal, deal.get("tracker_info", {}))
        mark_as_posted(deal.get("url"))

if __name__ == "__main__":
    run_deal_pipeline()
