import os
import datetime
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
            valid_deals.append(product_data)
        else:
            print(f" -> Skipping: Discount of {discount}% is below threshold ({DISCOUNT_THRESHOLD}%).")

    if not valid_deals:
        print("\nNo new deals met the minimum discount threshold or all were already posted today.")
        return

    print(f"\nDiscovered {len(valid_deals)} valid deal(s) ready for Telegram channel:")

    for deal in valid_deals:
        print(f"Posting: [{deal.get('platform')}] {deal.get('title')} ({deal.get('discount')}% off)")
        
        # TODO: Trigger Telegram Bot notification API here
        # send_telegram_post(deal)

        mark_as_posted(deal.get("url"))
        print(f"Successfully posted and recorded: {deal.get('url')}")

if __name__ == "__main__":
    run_deal_pipeline()
