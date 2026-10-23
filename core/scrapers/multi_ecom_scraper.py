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
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(2)
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

    # --- DYNAMIC SEARCH & LISTING SCRAPERS ---
    def fetch_myntra_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.myntra.com/{urllib.parse.quote(query_or_url)}?f=Discount%20Range%3A70.0_100.0"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("li.product-base")
                for item in items[:20]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.myntra.com/{href}" if href and not href.startswith("http") else href
                        
                        title_el = item.select_one(".product-product, .product-brand")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one(".product-discountedPrice")
                        mrp_el = item.select_one(".product-strike")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("Rs.", "").replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("Rs.", "").replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

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
                items = soup.select("div.item")
                for item in items[:20]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.ajio.com{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one(".nameCls")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one(".price")
                        mrp_el = item.select_one(".orginal-price")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({"title": title, "price": price, "mrp": mrp, "url": full_url, "image": image, "platform": "Ajio"})
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_croma_search(self, query: str) -> list:
        async def scrape():
            products = []
            url = f"https://www.croma.com/searchB?q={urllib.parse.quote(query)}%3Arelevance&text={urllib.parse.quote(query)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("li.product-item")
                for item in items[:20]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.croma.com{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one("h3.product-title, .plp-prod-title")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("span.amount")
                        mrp_el = item.select_one("span.old-price")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({"title": title, "price": price, "mrp": mrp, "url": full_url, "image": image, "platform": "Croma"})
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_meesho_search(self, query: str) -> list:
        async def scrape():
            products = []
            url = f"https://www.meesho.com/search?q={urllib.parse.quote(query)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div[class*='ProductCard']")
                for item in items[:20]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.meesho.com{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one("p[class*='ProductTitle']")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("h5[class*='Price']")
                        mrp_el = item.select_one("p[class*='StrikeThrough']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({"title": title, "price": price, "mrp": mrp, "url": full_url, "image": image, "platform": "Meesho"})
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_shopsy_search(self, query: str) -> list:
        async def scrape():
            products = []
            url = f"https://www.shopsy.in/search?q={urllib.parse.quote(query)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div.slAVV4")
                for item in items[:20]:
                    try:
                        a_tag = item.select_one("a.wjcEIp")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.shopsy.in{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one("a.wjcEIp")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("div.Nx9bqj")
                        mrp_el = item.select_one("div.yRaY8j")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({"title": title, "price": price, "mrp": mrp, "url": full_url, "image": image, "platform": "Shopsy"})
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_mamaearth_search(self, query: str) -> list:
        async def scrape():
            products = []
            url = f"https://mamaearth.in/search?q={urllib.parse.quote(query)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div[class*='productCard']")
                for item in items[:20]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://mamaearth.in{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one("h3, p[class*='title']")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("span[class*='price']")
                        mrp_el = item.select_one("span[class*='mrp']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({"title": title, "price": price, "mrp": mrp, "url": full_url, "image": image, "platform": "Mamaearth"})
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())
