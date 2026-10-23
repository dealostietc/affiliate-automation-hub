import os
import datetime
import requests
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher

# Candidate URLs across supported platforms (Croma, Myntra, Ajio)
CANDIDATE_DEALS = [
    # Croma Products
    ("https://www.croma.com/apple-airpods-4-bluetooth-headphone-with-active-noise-cancellation-white-/p/309180", "Croma"),
    ("https://www.croma.com/apple-iphone-15-128gb-black/p/300652", "Croma"),
    
    # Myntra Products
    ("https://www.myntra.com/headphones/boat/boat-rockerz-450-bluetooth-headphone/11782250/buy", "Myntra"),
    ("https://www.myntra.com/shoes/nike/nike-men-black-air-max-running-shoes/14298118/buy", "Myntra"),
    
    # Ajio Products
    ("https://www.ajio.com/p/461119105_black", "Ajio")
]

DISCOUNT_THRESHOLD = 70.0  # 🔥 Strict heavy discount threshold (70% and above)
HISTORY_FILE = "posted_deals.txt"  # Permanent history file to stop duplicates forever

def already_posted(url: str) -> bool:
    """Checks if a deal URL has ever been posted before."""
    if not os.path.exists(HISTORY_FILE):
        return False
    
    with open(HISTORY_FILE, "r") as f:
        posted_urls = f.read().splitlines()
        if url in posted_urls:
            return True
    return False

def mark_as_posted(url: str):
    """Permanently records that a deal URL has been posted."""
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{url}\n")

def send_telegram_post(deal: dict):
    """Sends formatted heavy discount deal alert with automatic fallback."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not chat_id:
        print("❌ CRITICAL ERROR: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID environment variables!")
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

    # Try sending as photo first
    if image_url:
        photo_endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(photo_endpoint, json=payload, headers=headers)
            res_data = response.json()
            if res_data.get("ok"):
                print(f"✅ Successfully posted photo deal: {title}")
                return
        except Exception:
            pass

    # Fallback to text message
    msg_endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(msg_endpoint, json=payload, headers=headers)
        res_data = response.json()
        if res_data.get("ok"):
            print(f"✅ Successfully posted text deal: {title}")
        else:
            print(f"❌ Telegram API Error: {res_data.get('description')}")
    except Exception as e:
        print(f"❌ Exception during Telegram request: {e}")

def run_deal_pipeline():
    fetcher = MultiEcomFetcher()
    valid_deals = []

    print(f"Scanning candidate deals (Minimum discount filter: {DISCOUNT_THRESHOLD}%)...")

    for url, platform in CANDIDATE_DEALS:
        if already_posted(url):
            print(f"Skipping (Already posted permanently): {url}")
            continue

        print(f"Checking {platform}: {url}")
        product_data = {}
        if platform.lower() == "croma":
            product_data = fetcher.fetch_croma(url)
        elif platform.lower() == "myntra":
            product_data = fetcher.fetch_myntra(url)
        elif platform.lower() == "ajio":
            product_data = fetcher.fetch_ajio(url)

        if not product_data or not product_data.get("title"):
            print(" -> Could not extract details.")
            continue

        price = product_data.get("price", 0)
        mrp = product_data.get("mrp", price)
        
        discount = 0.0
        if mrp > price > 0:
            discount = round(((mrp - price) / mrp) * 100, 2)

        print(f" -> Found: {product_data.get('title')} | Price: ₹{price} | MRP: ₹{mrp} | Discount: {discount}%")

        if discount >= DISCOUNT_THRESHOLD:
            product_data["discount"] = discount
            product_data["url"] = url
            product_data["platform"] = platform
            valid_deals.append(product_data)
        else:
            print(f" -> Skipping: Discount of {discount}% is below the 70% threshold.")

    if not valid_deals:
        print("\nNo new deals met the heavy 70%+ discount threshold today.")
        return

    print(f"\nDiscovered {len(valid_deals)} heavy discount deal(s):")

    for deal in valid_deals:
        print(f"Posting: [{deal.get('platform')}] {deal.get('title')} ({deal.get('discount')}% off)")
        send_telegram_post(deal)
        mark_as_posted(deal.get("url"))
        print(f"Recorded in permanent history: {deal.get('url')}")

if __name__ == "__main__":
    run_deal_pipeline()
