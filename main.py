import os
import datetime
import requests
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher

# Dynamic search terms & category listing feeds instead of hardcoded product URLs
DYNAMIC_SOURCES = [
    # Format: (Query or Category URL, Platform, Type: 'search' or 'category')
    ("headphones", "Myntra", "search"),
    ("running shoes", "Myntra", "search"),
    ("men shirts", "Ajio", "search"),
    ("smartwatches", "Croma", "search"),
    ("https://www.myntra.com/men-footwear?f=Discount%20Range%3A70.0_100.0", "Myntra", "category"),
    ("https://www.ajio.com/s/70-percent-or-more-off", "Ajio", "category")
]

DISCOUNT_THRESHOLD = 70.0  # 🔥 Strictly heavy discounts (70%+ off)
HISTORY_FILE = "posted_deals.txt"

def already_posted(url: str) -> bool:
    """Checks if a deal URL has ever been posted before."""
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r") as f:
        posted_urls = set(f.read().splitlines())
        return url in posted_urls

def mark_as_posted(url: str):
    """Permanently records that a deal URL has been posted."""
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{url}\n")

def send_telegram_post(deal: dict):
    """Sends formatted heavy discount deal alert with automatic fallback."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not chat_id:
        print("❌ CRITICAL ERROR: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID!")
        return

    title = deal.get("title", "Mega Deal")
    platform = deal.get("platform", "E-Commerce")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", price)
    discount = deal.get("discount", 0)
    url_link = deal.get("url", "")
    image_url = deal.get("image")

    caption = (
        f"🚨 <b>MEGA DEAL - {discount}% OFF!</b> 🔥\n\n"
        f"🔥 <b>{title}</b>\n\n"
        f"🏷️ <b>Platform:</b> {platform}\n"
        f"💰 <b>Deal Price:</b> ₹{price:,.2f}\n"
        f"❌ <b>MRP:</b> ₹{mrp:,.2f}\n\n"
        f"🔗 <a href='{url_link}'>Grab This Deal Before It Expires</a>"
    )

    headers = {"Content-Type": "application/json"}

    # 1. Try sending with photo first
    if image_url:
        photo_endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(photo_endpoint, json=payload, headers=headers).json()
            if res.get("ok"):
                print(f"✅ Posted photo deal: {title}")
                return
        except Exception:
            pass

    # 2. Fallback to text message
    msg_endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(msg_endpoint, json=payload, headers=headers).json()
        if res.get("ok"):
            print(f"✅ Posted text deal: {title}")
        else:
            print(f"❌ Telegram API Error: {res.get('description')}")
    except Exception as e:
        print(f"❌ Exception during Telegram request: {e}")

def run_deal_pipeline():
    fetcher = MultiEcomFetcher()
    valid_deals = []

    print(f"🚀 Dynamically scanning sources for 70%+ deals...")

    for source, platform, source_type in DYNAMIC_SOURCES:
        print(f"\nScanning [{platform}] query/category: '{source}'")
        extracted_products = []

        try:
            if hasattr(fetcher, "fetch_dynamic_deals"):
                extracted_products = fetcher.fetch_dynamic_deals(source, platform, source_type)
            elif platform.lower() == "myntra":
                extracted_products = fetcher.fetch_myntra_search(source)
            elif platform.lower() == "ajio":
                extracted_products = fetcher.fetch_ajio_search(source)
            elif platform.lower() == "croma":
                extracted_products = fetcher.fetch_croma_search(source)
        except Exception as e:
            print(f"⚠️ Error fetching from {platform} ({source}): {e}")
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
                valid_deals.append(product)
                print(f" -> FOUND 70%+ DEAL: {product.get('title')} ({discount}% off)")

    if not valid_deals:
        print("\nNo new 70%+ deals discovered across current dynamic feeds.")
        return

    print(f"\nDiscovered {len(valid_deals)} new heavy deal(s). Posting to Telegram...")
    for deal in valid_deals:
        send_telegram_post(deal)
        mark_as_posted(deal.get("url"))

if __name__ == "__main__":
    run_deal_pipeline()
