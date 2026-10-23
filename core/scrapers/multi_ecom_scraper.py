import asyncio
import json
import urllib.parse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class MultiEcomFetcher:
    def __init__(self):
        pass

    async def _fetch_page_content(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="Asia/Kolkata",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                }
            )
            
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            try:
                # Wait for network idle to ensure flash sale API payloads complete
                await page.goto(url, timeout=60000, wait_until="networkidle")
                
                # Scroll down in increments to trigger lazy-loaded flash deal grids
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight / 3);")
                    await asyncio.sleep(1.5)
                
                content = await page.content()
                return content
            except Exception as e:
                print(f"Playwright navigation error for {url}: {e}")
                return ""
            finally:
                await browser.close()

    def _parse_schema_org(self, soup: BeautifulSoup) -> dict:
        try:
            schema_scripts = soup.find_all("script", {"type": "application/ld+json"})
            for script in schema_scripts:
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = next((item for item in data if item.get("@type") == "Product"), {})
                    
                    if data.get("@type") == "Product":
                        title = data.get("name", "")
                        offers = data.get("offers", {})
                        if isinstance(offers, list) and len(offers) > 0:
                            offers = offers[0]
                        
                        price = float(offers.get("price", 0)) if offers.get("price") else 0.0
                        mrp = float(offers.get("highPrice", price)) if offers.get("highPrice") else price
                        image_url = data.get("image", "")
                        if isinstance(image_url, list) and len(image_url) > 0:
                            image_url = image_url[0]

                        if title and price > 0:
                            return {
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "image": image_url
                            }
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Schema.org parsing error: {e}")
        return {}

    def fetch_croma(self, url: str) -> dict:
        async def scrape():
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                schema_data = self._parse_schema_org(soup)
                if schema_data and schema_data.get("price", 0) > 0:
                    schema_data.update({"platform": "Croma", "url": url})
                    return schema_data
            return {}
        return asyncio.run(scrape())

    def fetch_myntra(self, url: str) -> dict:
        async def scrape():
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                schema_data = self._parse_schema_org(soup)
                if schema_data and schema_data.get("price", 0) > 0:
                    schema_data.update({"platform": "Myntra", "url": url})
                    return schema_data

                for script in soup.find_all("script"):
                    if script.string and "window.__myx =" in script.string:
                        try:
                            json_text = script.string.split("window.__myx =")[1].strip().rstrip(";")
                            data = json.loads(json_text)
                            p_data = data.get("pdpData", {})
                            price = float(p_data.get("price", {}).get("discounted", 0))
                            mrp = float(p_data.get("price", {}).get("mrp", price))
                            return {
                                "platform": "Myntra",
                                "title": p_data.get("name", ""),
                                "price": price,
                                "mrp": mrp,
                                "image": p_data.get("media", {}).get("albums", [{}])[0].get("images", [{}])[0].get("imageURL", ""),
                                "url": url
                            }
                        except Exception as e:
                            print(f"Myntra parse error: {e}")
            return {}
        return asyncio.run(scrape())

    def fetch_ajio(self, url: str) -> dict:
        async def scrape():
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                schema_data = self._parse_schema_org(soup)
                if schema_data and schema_data.get("price", 0) > 0:
                    schema_data.update({"platform": "Ajio", "url": url})
                    return schema_data
            return {}
        return asyncio.run(scrape())

    # --- ROBUST FLASH DEAL & LISTING SCRAPERS WITH FALLBACK SELECTORS ---
    def fetch_myntra_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.myntra.com/{urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("li.product-base, div.product-base, div[class*='product-base']")
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.myntra.com/{href}" if href and not href.startswith("http") else href
                        
                        title_el = item.select_one(".product-product, .product-brand, h3, h4")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one(".product-discountedPrice, span[class*='discountedPrice']")
                        mrp_el = item.select_one(".product-strike, span[class*='strike']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("Rs.", "").replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("Rs.", "").replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") or img_el.get("data-src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({"title": title, "price": price, "mrp": mrp, "url": full_url, "image": image, "platform": "Myntra"})
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_ajio_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.ajio.com/search/?text={urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div.item, div.rilrtl-products-item, div[class*='item']")
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.ajio.com{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one(".nameCls, .brand, div[class*='name']")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one(".price, span[class*='price']")
                        mrp_el = item.select_one(".orginal-price, span[class*='original']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") or img_el.get("data-src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({"title": title, "price": price, "mrp": mrp, "url": full_url, "image": image,
