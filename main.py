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
    "amazon": True,
    "flipkart": True,
    "meesho": True,
    "shopsy": True,
    "tata cliq": True,
    "myntra": True,
    "ajio": True,
    "nykaa": True,
    "shoppers stop": True,
    "croma": True,
    "vijay sales": True,
    "reliance digital": True,
    "samsung": True,
    "mamaearth": True,
    "firstcry": True,
}

DISCOUNT_THRESHOLD = 40.0  # 🔥 Minimum discount target (40%)
MAX_PAGES_TO_FETCH = 5     # Scan top 5 pages of live offers
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

def already_posted(url: str) -> bool:
    deal_id = get_canonical_deal_id(url)
    if not os.path.exists(HISTORY_FILE):
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

def extract_platform_name(item: dict) -> str:
    """Extracts merchant/store name from Cuelinks V3 API response object."""
    candidate = (
        item.get("merchant_name") or 
        item.get("store_name") or 
        item.get("merchant") or 
        item.get("store") or 
        item.get("brand")
    )
    if candidate and isinstance(candidate, str) and candidate.strip():
        return candidate.strip()

    campaign = item.get("campaign")
    if isinstance(campaign, dict):
        camp_title = campaign.get("title") or campaign.get("name") or campaign.get("domain")
        if camp_title and isinstance(camp_title, str):
            return camp_title.strip()
    elif isinstance(campaign, str) and campaign.strip():
        return campaign.strip()

    target_url = item.get("tracking_url") or item.get("affiliate_url") or item.get("url", "")
    if target_url:
        try:
            domain = urlparse(target_url).netloc.lower()
            domain = re.sub(r'^(www\.|m\.)', '', domain)
            parts = domain.split('.')
            if len(parts) >= 2:
                return parts[0].capitalize()
        except Exception:
            pass

    return "E-Commerce"

def is_platform_enabled(platform_name: str) -> bool:
    if not platform_name:
        return True
    platform_lower = platform_name.lower().strip()
    for key, is_enabled in ENABLED_PLATFORMS.items():
        if key in platform_lower:
            return is_enabled
    return True

def extract_discount_percentage(text: str) -> float:
    """Extracts percentage numbers preceding 'off' or 'discount' from offer titles."""
    if not text:
        return 0.0
    # Matches patterns like "50% off", "up to 40% discount", "min 40% off"
    matches = re.findall(r'(?:up to|flat|min[imu\s]*um)?\s*(\d{1,2})%', text, re.IGNORECASE)
    if matches:
        # Return the highest percentage found in the title string
        percentages = [float(p) for p in matches]
        return max(percentages)
    return 0.0

def fetch_cuelinks_deals() -> list:
    """Fetches promotional offer feeds from Cuelinks V3 API."""
    api_key = os.getenv("CUELINKS_API_KEY")
    if not api_key:
        print("❌ CRITICAL ERROR: CUELINKS_API_KEY secret is missing!", flush=True)
        return []

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    products = []
    print(f"🌐 Fetching live promotional offers across {MAX_PAGES_TO_FETCH} pages...", flush=True)

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
                
                platform = extract_platform_name(item)
                if not is_platform_enabled(platform):
                    continue

                # Extract discount percentage directly from the offer title text
                discount = extract_discount_percentage(title)

                if tracking_url and discount >= DISCOUNT_THRESHOLD:
                    products.append({
                        "title": title,
                        "url": tracking_url,
                        "image": image,
                        "platform": platform,
                        "discount": discount
                    })

        except Exception as e:
            print(f"❌ Error fetching page {page}: {e}", flush=True)
            break

    print(f"📊 Total high-discount offers matched: {len(products)}", flush=True)
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
    url_link = deal.get("url", "")
    image_url = deal.get("image")

    caption = (
        f"🚨 <b>MEGA DEAL ALERT - {int(discount)}% OFF!</b> 🚨\n\n"
        f"📦 <b>{title}</b>\n\n"
        f"🏷️ <b>Platform:</b> {platform}\n\n"
        f"🔗 <a href='{url_link}'>Grab Offer Now</a>"
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
                print(f"✅ Sent photo alert for: {title[:30]}", flush=True)
                return
        except Exception:
            pass

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "disable_web_page_preview": False},
            headers=headers
        )
        print(f"✅ Sent text alert for: {title[:30]}", flush=True)
    except Exception as e:
        print(f"⚠️ Failed text post: {e}", flush=True)

def run_deal_pipeline():
    print("DEBUG: Initializing deal collection pipeline...", flush=True)
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
