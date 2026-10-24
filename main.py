print("DEBUG: Local Feed Direct Scraping & Affiliate Automation started!", flush=True)

import os
import json
import re
import requests
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

# =========================================================================
# 🎛️ E-COMMERCE & QUICK-COMMERCE PLATFORM TOGGLES
# =========================================================================
ENABLED_PLATFORMS = {
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
    "zepto": True,
    "blinkit": True,
    "zomato": True,
    "swiggy": True,
    "instamart": True,
}

DISCOUNT_THRESHOLD = 40.0  # 🔥 Strictly 40% or higher discount

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "posted_deals.txt")
DEALS_FILE = os.path.join(BASE_DIR, "deals.json")

def get_canonical_deal_id(url: str) -> str:
    """Extracts clean permanent product IDs to prevent duplicate posts."""
    if not url:
        return ""
    
    url_lower = url.lower()

    # 1. Amazon ASIN
    amazon_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url, re.IGNORECASE)
    if amazon_match:
        return f"amazon_{amazon_match.group(1)}"

    # 2. Flipkart Product ID
    fk_match = re.search(r'pid=([A-Z0-9]+)', url, re.IGNORECASE)
    if fk_match:
        return f"flipkart_{fk_match.group(1)}"

    # 3. Myntra Item ID
    myntra_match = re.search(r'myntra\.com/(?:[^/]+/)?(\d+)', url, re.IGNORECASE)
    if myntra_match:
        return f"myntra_{myntra_match.group(1)}"

    # 4. Swiggy Instamart / Swiggy Item ID
    if "swiggy" in url_lower:
        swiggy_match = re.search(r'/item/([a-zA-Z0-9_\-]+)', url)
        if swiggy_match:
            return f"swiggy_{swiggy_match.group(1)}"

    # 5. Blinkit Product ID
    if "blinkit" in url_lower or "grofers" in url_lower:
        blinkit_match = re.search(r'/prid/(\d+)', url)
        if blinkit_match:
            return f"blinkit_{blinkit_match.group(1)}"

    # 6. Zepto Product ID
    if "zepto" in url_lower:
        zepto_match = re.search(r'/p/([a-zA-Z0-9_\-]+)', url)
        if zepto_match:
            return f"zepto_{zepto_match.group(1)}"

    try:
        parsed = urlparse(url)
        clean_path = re.sub(r'/(ref|tag)=[^/]+', '', parsed.path)
        return f"{parsed.netloc}{clean_path}".rstrip("/")
    except Exception:
        return url.strip()

def get_history_count() -> int:
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

def detect_platform_from_url(url: str) -> str:
    """Accurately identifies e-commerce and quick-commerce store names."""
    if not url:
        return "E-Commerce"
    
    url_lower = url.lower()

    if "instamart" in url_lower:
        return "Swiggy Instamart"
    elif "swiggy" in url_lower:
        return "Swiggy"
    elif "zomato" in url_lower:
        return "Zomato"
    elif "zepto" in url_lower or "zeptoconsumer" in url_lower:
        return "Zepto"
    elif "blinkit" in url_lower or "grofers" in url_lower:
        return "Blinkit"

    try:
        domain = urlparse(url).netloc.lower()
        domain = re.sub(r'^(www\.|m\.)', '', domain)
        parts = domain.split('.')
        if parts:
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

def apply_affiliate_tag(product_url: str) -> str:
    """Appends your affiliate tracking tag or converts via Cuelinks if key exists."""
    api_key = os.getenv("CUELINKS_API_KEY")
    if api_key:
        try:
            convert_url = "https://developers.cuelinks.com/pub_api/v3/links/convert"
            headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
            payload = {"url": product_url, "shorten": True}
            response = requests.post(convert_url, json=payload, headers=headers, timeout=8)
            if response.status_code == 200:
                data = response.json()
                aff_url = data.get("affiliate_url") or data.get("tracking_url") or data.get("short_url")
                if aff_url:
                    return aff_url
        except Exception:
            pass

    # Fallback tag append
    parsed = urlparse(product_url)
    netloc = parsed.netloc.lower()
    
    if "amazon" in netloc:
        amz_tag = os.getenv("AMAZON_AFFILIATE_TAG", "yourtag-21")
        query_params = dict(parse_qsl(parsed.query))
        query_params['tag'] = amz_tag
        parsed = parsed._replace(query=urlencode(query_params))
        return urlunparse(parsed)
        
    elif "flipkart" in netloc:
        fk_id = os.getenv("FLIPKART_AFFILIATE_ID", "")
        if fk_id:
            query_params = dict(parse_qsl(parsed.query))
            query_params['affid'] = fk_id
            parsed = parsed._replace(query=urlencode(query_params))
            return urlunparse(parsed)

    return product_url

def fetch_local_deals() -> list:
    """Reads product deals directly from the local deals.json file."""
    print(f"📁 Reading deals from local {DEALS_FILE}...", flush=True)
    if not os.path.exists(DEALS_FILE):
        print(f"⚠️ {DEALS_FILE} not found! Please create it with product entries.", flush=True)
        return []

    products = []
    try:
        with open(DEALS_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
            if isinstance(items, list):
                for item in items:
                    title = item.get("title", "Hot Deal")
                    raw_url = item.get("url") or item.get("link", "")
                    image = item.get("image", "")
                    
                    try:
                        price = float(item.get("price", 0))
                        mrp = float(item.get("mrp", price))
                    except (ValueError, TypeError):
                        continue

                    if price <= 0 or mrp <= 0 or mrp < price:
                        continue

                    platform = detect_platform_from_url(raw_url)
                    if not is_platform_enabled(platform):
                        continue

                    discount = round(((mrp - price) / mrp) * 100, 2)

                    if discount >= DISCOUNT_THRESHOLD and raw_url:
                        products.append({
                            "title": title,
                            "raw_url": raw_url,
                            "image": image,
                            "platform": platform,
                            "price": price,
                            "mrp": mrp,
                            "discount": discount,
                            "coupon_code": item.get("coupon_code")
                        })
    except Exception as e:
        print(f"❌ Error reading {DEALS_FILE}: {e}", flush=True)

    print(f"📊 Total valid product items matching >=40% discount criteria: {len(products)}", flush=True)
    return products

def send_telegram_post(deal: dict):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram credentials missing.", flush=True)
        return

    title = deal.get("title", "Hot Product Deal")
    platform = deal.get("platform", "E-Commerce")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", 0)
    discount = deal.get("discount", 0)
    affiliate_url = deal.get("affiliate_url", "")
    image_url = deal.get("image")
    coupon_code = deal.get("coupon_code")

    coupon_block = f"🎟️ <b>Use Promo Code:</b> <code>{coupon_code}</code>\n" if coupon_code else ""

    caption = (
        f"🔥 <b>LOOT DEAL - {int(discount)}% OFF!</b> 🔥\n\n"
        f"📦 <b>{title}</b>\n\n"
        f"🏷️ <b>Platform:</b> {platform}\n"
        f"💰 <b>Deal Price:</b> ₹{price:,.2f} <s>₹{mrp:,.2f}</s>\n"
        f"{coupon_block}\n"
        f"🔗 <a href='{affiliate_url}'>👉 Grab Deal Now</a>"
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
                print(f"✅ Sent photo deal for [{platform}]: {title[:30]}", flush=True)
                return
        except Exception:
            pass

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "disable_web_page_preview": False},
            headers=headers
        )
        print(f"✅ Sent text deal for [{platform}]: {title[:30]}", flush=True)
    except Exception as e:
        print(f"⚠️ Failed Telegram post: {e}", flush=True)

def run_deal_pipeline():
    print("DEBUG: Initializing local feed & tagging pipeline...", flush=True)
    
    history_count = get_history_count()
    print(f"📁 History Status: {history_count} deal(s) recorded in `posted_deals.txt`.", flush=True)

    valid_deals = []
    raw_products = fetch_local_deals()

    for product in raw_products:
        raw_url = product.get("raw_url")
        if not raw_url or already_posted(raw_url):
            continue
        
        affiliate_url = apply_affiliate_tag(raw_url)
        product["affiliate_url"] = affiliate_url
        
        valid_deals.append(product)

    if not valid_deals:
        print("\nNo new unposted deals found in `deals.json` matching >=40% discount.", flush=True)
        return

    print(f"\nDiscovered {len(valid_deals)} new deal(s). Broadcasting to Telegram...", flush=True)
    for deal in valid_deals:
        send_telegram_post(deal)
        mark_as_posted(deal.get("raw_url"))

if __name__ == "__main__":
    run_deal_pipeline()
