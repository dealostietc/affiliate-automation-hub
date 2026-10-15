def process_deal(url: str, platform: str):
    deal = {}
    
    # Live scraping (Mock check removed so it fetches real data)
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
    # Replace these with real product URLs you want to track
    test_urls = [
        ("https://www.myntra.com/your-actual-product-url-here", "myntra"),
        ("https://www.ajio.com/your-actual-product-url-here", "ajio"),
    ]
    
    for url, platform in test_urls:
        process_deal(url, platform)
