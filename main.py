import os
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher
from core.affiliate.converter import LinkConverter

fetcher = MultiEcomFetcher()
converter = LinkConverter()

def evaluate_and_publish_deal(url: str, platform_type: str):
    # 1. Scrape product information
    if platform_type == "myntra":
        deal = fetcher.fetch_myntra(url)
    elif platform_type == "ajio":
        deal = fetcher.fetch_ajio(url)
    elif platform_type == "croma":
        deal = fetcher.fetch_croma(url)
    else:
        print(f"Unsupported or custom handler required for {platform_type}")
        return

    if not deal or deal.get("price", 0) == 0:
        print("Could not retrieve price information.")
        return

    # 2. Check discount logic
    price = deal["price"]
    mrp = deal.get("mrp", price)
    discount_pct = round(((mrp - price) / mrp) * 100) if mrp > price else 0

    # Discount filter threshold (e.g., minimum 30% off)
    if discount_pct < 30:
        print(f"Skipping deal: Discount of {discount_pct}% is below threshold.")
        return

    # 3. Monetize Link
    affiliate_url = converter.convert(url, deal["platform"])

    # 4. Construct Promotional Post
    message = (
        f"🚨 **{deal['platform'].upper()} PRICE DROP ALERT** 🚨\n\n"
        f"🛍 **{deal['title']}**\n\n"
        f"💥 **Offer Price:** ₹{int(price)}  ~~₹{int(mrp)}~~\n"
        f"🔥 **Discount:** {discount_pct}% OFF\n\n"
        f"👉 **Buy Link:** {affiliate_url}"
    )

    print("--- POST READY FOR TELEGRAM & WHATSAPP ---")
    print(message)
    
    # 5. Call Telegram and WhatsApp Bot Dispatchers here
    # telegram_bot.send(message, deal['image'])
    # whatsapp_bot.send_to_groups(message, deal['image'])

if __name__ == "__main__":
    # Test execution
    sample_url = "https://www.myntra.com/jackets/roadster/roadster-men-solid-padded-jacket/1234567/buy"
    evaluate_and_publish_deal(sample_url, "myntra")
