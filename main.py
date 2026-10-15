import os
import asyncio
from telegram import Bot
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher
from core.affiliate.converter import LinkConverter
from db.db_manager import DatabaseManager

fetcher = MultiEcomFetcher()
converter = LinkConverter()
db = DatabaseManager()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

async def post_to_telegram(title: str, platform: str, price: float, mrp: float, discount: int, link: str, image_url: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("Missing Telegram Bot token or Channel ID. Printing message locally:")
        print(f"\n[TELEGRAM PREVIEW]\nPlatform: {platform}\nTitle: {title}\nPrice: ₹{price} (MRP: ₹{mrp}, {discount}% OFF)\nLink: {link}\n")
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
    
    # Check if it's a test/placeholder URL
    if "1234567" in url:
        print("Using MOCK deal data for testing purposes...")
        deal = {
            "platform": "Myntra",
            "title": "Roadster Men Solid Padded Jacket (Test Item)",
            "price": 799.0,
            "mrp": 1999.0,
            "image": "https://assets.myntassets.com/h_720,q_90,w_540/v1/assets/images/1234567/2020/1/1/test.jpg",
            "url": url
        }
    else:
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

    if discount < 20:
        print(f"Skipping: Discount of {discount}% is below threshold.")
        return

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
        print(f"Successfully processed and posted deal for {deal['title']}!")
    else:
        print(f"Skipping: Price ₹{price} is not the lowest recorded price.")

if __name__ == "__main__":
    # Test with dummy URL (triggers mock mode) or a real e-commerce link
    test_urls = [
        ("https://www.myntra.com/jackets/roadster/roadster-men-solid-padded-jacket/1234567/buy", "myntra"),
    ]
    
    for url, platform in test_urls:
        process_deal(url, platform)
