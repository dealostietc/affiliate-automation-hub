print("DEBUG: Cuelinks Smart Offer & Price Extractor started!", flush=True)

import os
import re
import requests
from collections import Counter
from urllib.parse import urlparse

# =========================================================================
# 🎛️ E-COMMERCE & QUICK-COMMERCE PLATFORM TOGGLES
# =========================================================================
ENABLED_PLATFORMS = {
    # 🛒 Mainstream E-Commerce
    "amazon": True,
    "flipkart": True,
    "myntra": True,
    "ajio": True,
    "croma": True,
    "meesho": True,
    "tata cliq": True,
    "nykaa": True,
    "reliance digital": True,
    "samsung": True,
    "mamaearth": True,
    "firstcry": True,

    # ⚡ Quick-Commerce & Hyperlocal Delivery
    "zepto": True,
    "blinkit": True,
    "zomato": True,
    "swiggy": True,
    "instamart": True,
}

DISCOUNT_THRESHOLD = 40.0  # 🔥 Minimum discount target percentage (40%)
MAX_PAGES_TO_FETCH = 5     # Scan top API pages
CUELINKS_API_URL = "https://developers.cuelinks.com/pub_api/v3/offers"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "posted_deals.txt")

def get_canonical_deal_id(url: str) -> str:
    """Extracts clean canonical URLs to prevent duplicate posts."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        return clean_url
    except Exception:
        return url.strip()

def get_history_count() -> int:
    """Returns the total number of unique deals already recorded in history."""
    if not os.path.exists(HISTORY_FILE):
        return 0
    try:
        with open(HISTORY_FILE, "r") as f:
            return len([line.strip() for line in f.read().splitlines() if line.strip()])
    except Exception:
        return 0

def already_posted(url: str) -> bool:
    deal_id = get_canonical_deal_id(url)
    if not deal_id or not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r") as f:
        posted_ids = set(f.read().splitlines())
    return deal_id in posted_ids

def mark_as_posted(url: str):
    deal_id = get_canonical_deal_id(url)
    if not deal_id:
        return
    posted_ids = set()
    if os.path.exists(HISTORY_FILE):
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
    except Exception as e:
        print(f"⚠️ Error writing history: {e}", flush=True)

def extract_real_platform_name(item: dict) -> str:
    """Resolves the real store name, ignoring intermediary networks like Linksdirect."""
    candidates = [
        item.get("merchant_name"),
        item.get("store_name"),
        item.get("brand"),
        item.get("merchant"),
        item.get("store")
    ]
    
    campaign = item.get("campaign")
    if isinstance(campaign, dict):
        candidates.insert(0, campaign.get("name") or campaign.get("title"))

    for candidate in candidates:
        if candidate and isinstance(candidate, str):
            clean = candidate.strip()
            if "linksdirect" not in clean.lower() and "cuelinks" not in clean.lower():
                return clean

    target_url = item.get("tracking_url") or item.get("affiliate_url") or item.get("url", "")
    if target_url:
        url_lower = target_url.lower()
        if "instamart" in url_lower:
            return "Swiggy Instamart"
        elif "swiggy" in url_lower:
            return "Swiggy"
        elif "zomato" in url_lower:
            return "Zomato"
        elif "zepto" in url_lower:
            return "Zepto"
        elif "blinkit" in url_lower or "grofers" in url_lower:
            return "Blinkit"
            
        try:
            domain = urlparse(target_url).netloc.lower()
            domain = re.sub(r'^(www\.|m\.|links\.)', '', domain)
            parts = domain.split('.')
            if len(parts) >= 2 and "linksdirect" not in parts[0]:
                return parts[0].capitalize()
        except Exception:
            pass

    return "E-Commerce Store"

def is_platform_enabled(platform_name: str) -> bool:
    if not platform_name:
        return True
    platform_lower = platform_name.lower().strip()
    for key, is_enabled in ENABLED_PLATFORMS.items():
        if key in platform_lower:
            return is_enabled
    return True

def extract_prices_from_text(text: str) -> tuple:
    """Extracts price and MRP values from promotional description text."""
    if not text:
        return 0.0, 0.0
    prices = re.findall(r'(?:₹|rs\.?)\s*([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
    cleaned = []
    for p in prices:
        try:
            val = float(p.replace(',', ''))
            if val > 0:
                cleaned.append(val)
        except ValueError:
            continue
    
    if len(cleaned) >= 2:
        cleaned.sort()
        return cleaned[0], cleaned[-1]  # (Deal Price, MRP)
    elif len(cleaned) == 1:
        return cleaned[0], 0.0
    return 0.0, 0.0

def parse_deal_offer(item: dict) -> tuple:
    """Extracts discount percentage, prices, and coupon codes from offer payload."""
    title = item.get("title") or item.get("name") or ""
    desc = item.get("description") or ""
    combined_text = f"{title} {desc}"
    
    discount = 0.0
    matches = re.findall(r'(?:up to|flat|min[imu\s]*um)?\s*(\d{1,2})%', combined_text, re.IGNORECASE)
    if matches:
        discount = max([float(p) for p in matches])

    price, mrp = extract_prices_from_text(combined_text)
    if mrp > price > 0 and discount == 0.0:
        discount = round(((mrp - price) / mrp) * 100, 2)

    coupon_code = (
        item.get("coupon_code") or 
        item.get("code") or 
        item.get("voucher_code") or 
        item.get("promo_code")
    )
    if coupon_code and str(coupon_code).strip().lower() in ["none", "null", "n/a", "no code required", ""]:
        coupon_code = None

    return discount, price, mrp, coupon_code

def fetch_cuelinks_deals() -> list:
    """Fetches live promotional offers from Cuelinks V3 API."""
    api_key = os.getenv("CUELINKS_API_KEY")
    if not api_key:
        print("❌ CRITICAL ERROR: CUELINKS_API_KEY secret is missing!", flush=True)
        return []

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    products = []
    platform_tally = Counter()

    print(f"🌐 Fetching live offers from Cuelinks across {MAX_PAGES_TO_FETCH} pages...", flush=True)

    for page in range(1, MAX_PAGES_TO_FETCH + 1):
        try:
            url = f"{CUELINKS_API_URL}?page={page}&per_page=50"
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                break

            data = response.json()
            deals_list = data.get("data", data) if isinstance(data, dict) else data

            if not isinstance(deals_list, list) or not deals_list:
                break

            for item in deals_list:
                title = item.get("title") or item.get("name") or item.get("description", "Hot Offer")
                tracking_url = item.get("tracking_url") or item.get("affiliate_url") or item.get("url", "")
                image = item.get("image_url") or item.get("image", "")
                
                platform = extract_real_platform_name(item)
                platform_tally[platform] += 1

                if not is_platform_enabled(platform):
                    continue

                discount, price, mrp, coupon_code = parse_deal_offer(item)

                if tracking_url and discount >= DISCOUNT_THRESHOLD:
                    products.append({
                        "title": title,
                        "url": tracking_url,
                        "image": image,
                        "platform": platform,
                        "discount": discount,
                        "price": price,
                        "mrp": mrp,
                        "coupon_code": coupon_code
                    })

        except Exception as e:
            print(f"❌ Error fetching page {page}: {e}", flush=True)
            break

    # 📊 Diagnostics table for GitHub Actions logs
    print("\n--------------------------------------------------")
    print("📈 PLATFORM BREAKDOWN (Parsed from Cuelinks Feed):")
    print("--------------------------------------------------")
    for store, count in platform_tally.most_common(15):
        print(f"   • {store}: {count} offers")
    print("--------------------------------------------------\n")

    print(f"📊 Total offers matching >=40% discount criteria: {len(products)}", flush=True)
    return products

def send_telegram_post(deal: dict):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram credentials missing.", flush=True)
        return

    title = deal.get("title", "Hot Offer")
    platform = deal.get("platform", "E-Commerce")
    discount = deal.get("discount", 0)
    price = deal.get("price", 0)
    mrp = deal.get("mrp", 0)
    url_link = deal.get("url", "")
    image_url = deal.get("image")
    coupon_code = deal.get("coupon_code")

    price_block = ""
    if price > 0 and mrp > price:
        price_block = f"💰 <b>Deal Price:</b> ₹{price:,.2f} <s>₹{mrp:,.2f}</s>\n"
    elif price > 0:
        price_block = f"💰 <b>Effective Price:</b> ₹{price:,.2f}\n"

    coupon_block = f"🎟️ <b>Use Promo Code:</b> <code>{coupon_code}</code>\n" if coupon_code else ""

    caption = (
        f"🔥 <b>MEGA DEAL ALERT - {int(discount)}% OFF!</b> 🔥\n\n"
        f"📦 <b>{title}</b>\n\n"
        f"🏷️ <b>Platform:</b> {platform}\n"
        f"{price_block}"
        f"{coupon_block}\n"
        f"🔗 <a href='{url_link}'>👉 Grab Best Deal Now</a>"
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
                print(f"✅ Sent photo alert for [{platform}]: {title[:30]}", flush=True)
                return
        except Exception:
            pass

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "disable_web_page_preview": False},
            headers=headers
        )
        print(f"✅ Sent text alert for [{platform}]: {title[:30]}", flush=True)
    except Exception as e:
        print(f"⚠️ Failed text post: {e}", flush=True)

def run_deal_pipeline():
    print("DEBUG: Initializing deal collection pipeline...", flush=True)
    
    history_count = get_history_count()
    print(f"📁 History Status: {history_count} deal(s) currently recorded in `posted_deals.txt`.", flush=True)

    valid_deals = []
    extracted_products = fetch_cuelinks_deals()

    for product in extracted_products:
        url = product.get("url")
        if not url or already_posted(url):
            continue
        valid_deals.append(product)

    if not valid_deals:
        print("\nNo new matching 40%+ discount offers found in this run.", flush=True)
        return

    print(f"\nDiscovered {len(valid_deals)} new offer(s). Broadcasting to Telegram...", flush=True)
    for deal in valid_deals:
        send_telegram_post(deal)
        mark_as_posted(deal.get("url"))

if __name__ == "__main__":
    run_deal_pipeline()
