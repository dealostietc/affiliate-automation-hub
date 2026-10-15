import os
from core.scrapers.multi_ecom_scraper import MultiEcomFetcher

# Define your target deal URLs here
TEST_DEALS = [
    ("https://www.croma.com/apple-airpods-4-bluetooth-headphone-with-active-noise-cancellation-white-/p/309180", "Croma"),
]

DISCOUNT_THRESHOLD = 10  # Lowered temporarily for testing (was 20)

def process_deal(url: str, platform: str):
    fetcher = MultiEcomFetcher()
    
    print(f"\nProcessing {platform} deal: {url}")
    
    product_data = {}
    if platform.lower() == "croma":
        product_data = fetcher.fetch_croma(url)
    elif platform.lower() == "myntra":
        product_data = fetcher.fetch_myntra(url)
    elif platform.lower() == "ajio":
        product_data = fetcher.fetch_ajio(url)

    if not product_data or not product_data.get("title"):
        print(f"Skipping: Could not extract details for {url}")
        return

    price = product_data.get("price", 0)
    mrp = product_data.get("mrp", price)
    
    # Calculate discount percentage
    discount = 0.0
    if mrp > price > 0:
        discount = round(((mrp - price) / mrp) * 100, 2)

    print(f"Found: {product_data.get('title')}")
    print(f"Price: ₹{price} | MRP: ₹{mrp} | Discount: {discount}%")

    if discount < DISCOUNT_THRESHOLD:
        print(f"Skipping: Discount of {discount}% is below threshold ({DISCOUNT_THRESHOLD}%).")
        return

    print(f"Successfully processed and validated deal! Ready to post to Telegram.")
    # Add your Telegram bot sending logic here

if __name__ == "__main__":
    for url, platform in TEST_DEALS:
        process_deal(url, platform)
