import os
import asyncio
from telegram import Bot
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher
from core.affiliate.converter import LinkConverter
from db.db_manager import DatabaseManager

# Initialize modules
fetcher = MultiEcomFetcher()
converter = LinkConverter()
db = DatabaseManager()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

async def post_to_telegram(title: str, platform: str, price: float, mrp: float, discount: int, link: str, image_url: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("Missing Telegram Bot token or Channel ID.")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message = (
        f"🔥 **{platform.upper()} PRICE DROP ALERT** 🔥\n\n"
        f"📌 **{title}**\n\n"
        f"💰 **Offer Price:** ₹{int(price)}  ~~₹{int(mrp)}~~\n"
        f"📉 **Discount:** {discount}% OFF\n\n"
        f"🛒 **Buy Now:** {link}"
    )
    
    if image_url:
        await bot.send_photo(chat_id=TELEGRAM_CHANNEL_ID, photo=image_url, caption=message, parse_mode="Markdown")
    else:
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode="Markdown")

def process_deal(url: str, platform: str):
    deal = {}
    if platform == "myntra":
        deal = fetcher.fetch_myntra(url)
    elif platform == "ajio":
        deal = fetcher.fetch_ajio(url)
    elif platform == "croma":
        deal = fetcher.fetch_croma(url)

    if not deal or deal.get("price", 0) == 0:
        print(f"Skipping: Could not extract details for {url}")
        return

    price = deal["price"]
    mrp = deal.get("mrp", price)
    discount = round(((mrp - price) / mrp) * 100) if mrp > price else 0

    # Discount threshold filter (e.g. >= 20% off)
    if discount < 20:
        print(f"Skipping: Discount of {discount}% is below threshold.")
        return

    # Check for historical lowest price
    product_key = f"{deal['platform']}_{deal['title']}"
    if db.is_lowest_price(product_key, price):
        affiliate_link = converter.convert(url, deal["platform"])
        asyncio.run(post_to_telegram(
            title=deal["title"],
            platform=deal["platform"],
            price=price,
            mrp=mrp,
            discount=discount,
            link=affiliate_link,
            image_url=deal.get("image", "")
        ))
        print(f"Successfully posted deal for {deal['title']}!")
    else:
        print(f"Skipping: Price ₹{price} is not the lowest recorded price.")

if __name__ == "__main__":
    # Test batch URLs
    test_urls = [
        ("https://www.myntra.com/jackets/roadster/roadster-men-solid-padded-jacket/1234567/buy", "myntra"),
    ]
    
    for url, platform in test_urls:
        process_deal(url, platform)
