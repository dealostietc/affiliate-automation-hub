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

DISCOUNT_THRESHOLD = 20  # Minimum discount percentage required
HISTORY_FILE = "posted_deals_today.txt"

def already_posted_today(url: str) -> bool:
    """Checks if a deal URL has already been posted today."""
    if not os.path.exists(HISTORY_FILE):
        return False
    
    today_str = datetime.date.today().isoformat()
    with open(HISTORY_FILE, "r") as f:
        lines = f.read().splitlines()
        for line in lines:
            parts = line.split("|")
            if len(parts) == 2:
                posted_date, posted_url = parts
                if posted_date == today_str and posted_url == url:
                    return True
    return False

def mark_as_posted(url: str):
    """Records that a deal URL has been posted today."""
    today_str = datetime.date.today().isoformat()
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{today_str}|{url}\n")

def send_telegram_post(deal: dict):
    """Sends formatted deal alert with image and affiliate link to Telegram channel."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    print(f"DEBUG -> Bot Token present: {bool(bot_token)}, Channel ID: {chat_id}")

    if not bot_token or not chat_id:
        print("❌ CRITICAL ERROR: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID environment variables!")
        return

    title = deal.get("title", "Hot Deal")
    platform = deal.get("platform", "E-Commerce")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", price)
    discount = deal.get("discount", 0)
    url_link = deal.get("url", "")

    caption = (
        f"🔥 <b>{title}</b>\n\n"
        f"🏷️ <b>Platform:</b> {platform}\n"
        f"💰 <b>Deal Price:</b> ₹{price:,.2f}\n"
        f"❌ <b>MRP:</b> ₹{mrp:,.2f} ({discount}% OFF)\n\n"
        f"🔗 <a href='{url_link}'>Grab This Deal</a>"
    )

    image_url = deal.get("image")
    if image_url:
        endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    else:
        endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": caption,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

    try:
        response = requests.post(endpoint, json=payload)
        res_data = response.json()
        print(f"DEBUG -> Telegram API Response: {res_data}")

        if res_data.get("ok"):
            print(f"✅ Successfully posted to Telegram: {title}")
        else:
            print(f"❌ Telegram API Error: {res_data.get('description')}")
    except Exception as e:
        print(f"❌ Exception during Telegram request: {e}")

def run_deal_pipeline():
    fetcher = MultiEcomFetcher()
    valid_deals = []

    print("Scanning candidate deals across Croma, Myntra, and Ajio...")

    for url, platform in CANDIDATE_DEALS:
        if already_posted_today(url):
            print(f"Skipping (Already posted today): {url}")
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
            print(f" -> Skipping: Discount of {discount}% is below threshold ({DISCOUNT_THRESHOLD}%).")

    if not valid_deals:
        print("\nNo new deals met the minimum discount threshold or all were already posted today.")
        return

    print(f"\nDiscovered {len(valid_deals)} valid deal(s) ready for Telegram channel:")

    for deal in valid_deals:
        print(f"Posting: [{deal.get('platform')}] {deal.get('title')} ({deal.get('discount')}% off)")
        
        # Send deal to Telegram channel
        send_telegram_post(deal)

        mark_as_posted(deal.get("url"))
        print(f"Recorded in daily lockfile: {deal.get('url')}")

if __name__ == "__main__":
    run_deal_pipeline()
