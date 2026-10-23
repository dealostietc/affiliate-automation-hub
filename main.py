import os
import datetime
import requests
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher
from core.price_tracker import DIYPriceTracker

# Comprehensive category keyword matrix covering all major store catalogs
CATEGORY_KEYWORDS = [
    # Electronics & Gadgets
    "smartphones", "laptops", "headphones", "smartwatches", "bluetooth speakers", 
    "tablets", "power banks", "trimmers", "gaming mice", "earbuds",
    
    # Fashion & Apparel (Men, Women & Kids)
    "tshirt", "men shirts", "jeans", "kurti", "saree", "running shoes", 
    "sneakers", "formal shoes", "jackets", "hoodies", "handbags", "sunglasses",
    
    # Home, Kitchen & Daily Essentials
    "bedsheets", "pillows", "curtains", "wall decor", "cookware", "water bottles", 
    "lunch boxes", "storage containers", "led bulbs", "organizers",
    
    # Beauty, Skincare & Personal Care
    "face wash", "shampoo", "moisturizer", "sunscreen", "lipstick", 
    "perfume", "hair serum", "body lotion", "makeup kit", "beard oil"
]

# Automatically build dynamic source tasks across all supported platforms
DYNAMIC_SOURCES = []
for keyword in CATEGORY_KEYWORDS:
    DYNAMIC_SOURCES.append((keyword, "Myntra", "search"))
    DYNAMIC_SOURCES.append((keyword, "Ajio", "search"))
    DYNAMIC_SOURCES.append((keyword, "Croma", "search"))
    DYNAMIC_SOURCES.append((keyword, "Meesho", "search"))
    DYNAMIC_SOURCES.append((keyword, "Shopsy", "search"))
    DYNAMIC_SOURCES.append((keyword, "Mamaearth", "search"))

DISCOUNT_THRESHOLD = 40.0  # 🔥 40% and above heavy discount threshold
HISTORY_FILE = "posted_deals.txt"

def already_posted(url: str) -> bool:
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r") as f:
        return url in f.read().splitlines()

def mark_as_posted(url: str):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{url}\n")

def send_telegram_post(deal: dict, tracker_info: dict):
    """Sends formatted deal alert with DIY price history insights."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not chat_id:
        return

    title = deal.get("title", "Hot Deal")
    platform = deal.get("platform", "E-Commerce")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", price)
    discount = deal.get("discount", 0)
    url_link = deal.get("url", "")
    image_url = deal.get("image")

    lowest_badge = "🌟 **ALL-TIME LOWEST PRICE EVER!** 🌟\n" if tracker_info.get("is_lowest_ever") else ""

    caption = (
        f"🔥 <b>DEAL ALERT - {discount}% OFF!</b> 🔥\n\n"
        f"{lowest_badge}"
        f"📦 <b>{title}</b>\n\n"
        f"🏷️ <b>Platform:</b> {platform}\n"
        f"💰 <b>Deal Price:</b> ₹{price:,.2f}\n"
        f"❌ <b>MRP:</b> ₹{mrp:,.2f}\n"
        f"📉 <b>Tracked Lowest:</b> ₹{tracker_info.get('lowest_ever', price):,.2f}\n"
        f"📊 <b>Historical Avg:</b> ₹{tracker_info.get('historical_avg', price):,.2f}\n\n"
        f"🔗 <a href='{url_link}'>Grab This Deal Now</a>"
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
                return
        except Exception:
            pass

    # Fallback to text message
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "disable_web_page_preview": False},
        headers=headers
    )

def run_deal_pipeline():
    fetcher = MultiEcomFetcher()
    tracker = DIYPriceTracker()  # Initialized with SQLite database
    valid_deals = []

    print(f"🚀 Running Comprehensive DIY Price Engine ({len(CATEGORY_KEYWORDS)} categories across {len(DYNAMIC_SOURCES)} feeds)...")

    for source, platform, source_type in DYNAMIC_SOURCES:
        print(f"\nScanning [{platform}] for '{source}'")
        extracted_products = []

        try:
            if platform.lower() == "myntra":
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
                
                # Log and evaluate using your DIY SQLite Price Engine
                tracker_info = tracker.track_and_evaluate(
                    url=url,
                    title=product.get("title"),
                    platform=platform,
                    price=price,
                    mrp=mrp
                )
                product["tracker_info"] = tracker_info

                valid_deals.append(product)
                print(f" -> Logged & Verified Deal: {product.get('title')} ({discount}% off) on {platform}")

    if not valid_deals:
        print("\nNo new 40%+ deals discovered across current categories.")
        return

    print(f"\nDiscovered {len(valid_deals)} deal(s). Broadcasting to Telegram...")
    for deal in valid_deals:
        send_telegram_post(deal, deal.get("tracker_info", {}))
        mark_as_posted(deal.get("url"))

if __name__ == "__main__":
    run_deal_pipeline()
