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
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--start-maximized",
                    "--disable-dev-shm-usage",
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                extra_http_headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                }
            )
            
            page = await context.new_page()
            
            # Stealth injections to mask automated chromium fingerprints
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            await page.add_init_script("window.navigator.chrome = { runtime: {} };")
            await page.add_init_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-IN', 'en-US', 'en']});")
            
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(4)  # Allow JavaScript challenge gates to settle
                
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight / 3);")
                    await asyncio.sleep(2)

                content = await page.content()
                print(f"Debug: Fetched {len(content)} bytes for {url}")
                if len(content) < 5000:
                    print(f"⚠️ Warning: Page might be blocked or returning empty shell for {url}")
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

    def fetch_amazon_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.amazon.in/s?k={urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div.s-result-item[data-component-type='s-search-result'], div.DealCard-module__dealCardItem_1USnhUlIxAg8uXSaFyKBqB")
                print(f"Debug [Amazon]: Found {len(items)} items matching selectors on {url}")
                
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a.a-link-normal.s-no-outline, a[class*='link']")
                        href = a_tag["href"] if a_tag and a_tag.has_attr("href") else ""
                        clean_href = href.split("/ref=")[0] if href else ""
                        full_url = f"https://www.amazon.in{clean_href}" if clean_href and not clean_href.startswith("http") else clean_href

                        title_el = item.select_one("h2 span, span[class*='title']")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("span.a-price-whole, span[class*='price']")
                        mrp_el = item.select_one("span.a-text-price span.a-offscreen, span[class*='strike']")
                        img_el = item.select_one("img.s-image, img")

                        price = float(price_el.get_text(strip=True).replace(",", "").replace("₹", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el and img_el.has_attr("src") else ""

                        if full_url and title and price > 0:
                            products.append({
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "url": full_url,
                                "image": image,
                                "platform": "Amazon"
                            })
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

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

    # --- DYNAMIC FLASH DEALS & PROMOTIONAL URL SCRAPERS WITH FALLBACK SELECTORS ---
    def fetch_myntra_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.myntra.com/search?p=1&q={urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("li.product-base, div.product-base, div[class*='product-base'], div.results-base li")
                print(f"Debug [Myntra]: Found {len(items)} items matching selectors on {url}")
                
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.myntra.com/{href}" if href and not href.startswith("http") else href
                        
                        title_el = item.select_one(".product-product, .product-brand, h3, h4")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one(".product-discountedPrice, span[class*='price']")
                        mrp_el = item.select_one(".product-strike, span[class*='strike']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("Rs.", "").replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("Rs.", "").replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "url": full_url,
                                "image": image,
                                "platform": "Myntra"
                            })
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
                items = soup.select("div.item, div.rilrtl-products-list__item, div[class*='card']")
                print(f"Debug [Ajio]: Found {len(items)} items matching selectors on {url}")
                
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.ajio.com{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one(".nameCls, .brand, h3")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one(".price, span[class*='price']")
                        mrp_el = item.select_one(".orginal-price, span[class*='original']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "url": full_url,
                                "image": image,
                                "platform": "Ajio"
                            })
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_croma_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.croma.com/searchB?q={urllib.parse.quote(query_or_url)}%3Arelevance&text={urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("li.product-item, div.product-card, div[class*='product-item'], div[class*='product-card'], div.cp-product")
                print(f"Debug [Croma]: Found {len(items)} items matching selectors on {url}")
                
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag and a_tag.has_attr("href") else ""
                        full_url = f"https://www.croma.com{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one("h3.product-title, .plp-prod-title, h3, a[class*='title']")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("span.amount, .pdp-price, span[class*='price']")
                        mrp_el = item.select_one("span.old-price, .old-price, span[class*='old']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el and img_el.has_attr("src") else ""

                        if full_url and title and price > 0:
                            products.append({
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "url": full_url,
                                "image": image,
                                "platform": "Croma"
                            })
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_meesho_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.meesho.com/search?q={urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div[class*='ProductCard'], div[class*='product-card']")
                print(f"Debug [Meesho]: Found {len(items)} items matching selectors on {url}")
                
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a")
                        href = a_tag["href"] if a_tag else ""
                        full_url = f"https://www.meesho.com{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one("p[class*='ProductTitle'], p")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("h5[class*='Price']")
                        mrp_el = item.select_one("p[class*='StrikeThrough']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el else ""

                        if full_url and title and price > 0:
                            products.append({
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "url": full_url,
                                "image": image,
                                "platform": "Meesho"
                            })
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_shopsy_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://www.shopsy.in/search?q={urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div.slAVV4, div[class*='slAVV4'], div[class*='row'] > div, div[class*='_2kHMtA']")
                print(f"Debug [Shopsy]: Found {len(items)} items matching selectors on {url}")
                
                for item in items[:30]:
                    try:
                        a_tag = item.select_one("a.wjcEIp, a[class*='link'], a")
                        href = a_tag["href"] if a_tag and a_tag.has_attr("href") else ""
                        full_url = f"https://www.shopsy.in{href}" if href and not href.startswith("http") else href

                        title_el = item.select_one("a.wjcEIp, a[class*='title'], div[class*='title']")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = item.select_one("div.Nx9bqj, span[class*='price']")
                        mrp_el = item.select_one("div.yRaY8j, span[class*='strike']")
                        img_el = item.select_one("img")

                        price = float(price_el.get_text(strip=True).replace("₹", "").replace(",", "")) if price_el else 0.0
                        mrp = float(mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")) if mrp_el else price
                        image = img_el.get("src") if img_el and img_el.has_attr("src") else ""

                        if full_url and title and price > 0:
                            products.append({
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "url": full_url,
                                "image": image,
                                "platform": "Shopsy"
                            })
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())

    def fetch_mamaearth_search(self, query_or_url: str) -> list:
        async def scrape():
            products = []
            url = query_or_url if query_or_url.startswith("http") else f"https://mamaearth.in/search?q={urllib.parse.quote(query_or_url)}"
            html = await self._fetch_page_content(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select("div[class*='productCard'], div[class*='product-card']")
                print(f"Debug [Mamaearth]: Found {len(items)} items matching selectors on {url}")
                
                for item in items[:30]:
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
                            products.append({
                                "title": title,
                                "price": price,
                                "mrp": mrp if mrp > price else price,
                                "url": full_url,
                                "image": image,
                                "platform": "Mamaearth"
                            })
                    except Exception:
                        continue
            return products
        return asyncio.run(scrape())
