import asyncio
from playwright.async_api import async_playwright
import re

class MultiEcomFetcher:
    def __init__(self):
        pass

    async def _fetch_page_content(self, url: str) -> str:
        async with async_playwright() as p:
            # Launch headless browser in stealth mode
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            try:
                await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                # Wait briefly for dynamic hydration/rendering
                await asyncio.sleep(3)
                content = await page.content()
                return content
            except Exception as e:
                print(f"Playwright navigation error for {url}: {e}")
                return ""
            finally:
                await browser.close()

    def fetch_croma(self, url: str) -> dict:
        async def scrape():
            html = await self._fetch_page_content(url)
            if not html:
                return {}
            
            from bs4 import BeautifulSoup
            import json
            
            soup = BeautifulSoup(html, "html.parser")
            
            # Extract from Next.js payload if available
            next_data = soup.find("script", id="__NEXT_DATA__")
            if next_data and next_data.string:
                try:
                    data = json.loads(next_data.string)
                    page_props = data.get("props", {}).get("pageProps", {})
                    initial_state = page_props.get("initialState", {})
                    p_data = initial_state.get("product", {}).get("productDetails", {}) or page_props.get("productData", {})
                    
                    title = p_data.get("name", "")
                    price = float(p_data.get("price", {}).get("value", 0))
                    mrp = float(p_data.get("mrp", {}).get("value", price))
                    images = p_data.get("images", [])
                    image_url = images[0].get("url", "") if images else ""

                    if title and price > 0:
                        return {
                            "platform": "Croma",
                            "title": title,
                            "price": price,
                            "mrp": mrp,
                            "image": image_url,
                            "url": url
                        }
                except Exception as ex:
                    print(f"JSON parse error in Playwright Croma scraper: {ex}")

            # Fallback DOM selectors for Croma
            title_elem = soup.find("h1")
            title = title_elem.get_text(strip=True) if title_elem else "Croma Product"
            
            # Try finding price via common classes
            price_elem = soup.find("span", {"id": "pdp-product-discount-price"}) or soup.find("span", class_=lambda c: c and "amount" in c)
            price = 0.0
            if price_elem:
                try:
                    price = float(price_elem.get_text().replace("₹", "").replace(",", "").strip())
                except ValueError:
                    pass

            return {
                "platform": "Croma",
                "title": title,
                "price": price,
                "mrp": price,
                "image": "",
                "url": url
            }

        return asyncio.run(scrape())

    def fetch_myntra(self, url: str) -> dict:
        async def scrape():
            html = await self._fetch_page_content(url)
            if not html:
                return {}
            
            from bs4 import BeautifulSoup
            import json
            
            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script"):
                if script.string and "window.__myx =" in script.string:
                    try:
                        json_text = script.string.split("window.__myx =")[1].strip().rstrip(";")
                        data = json.loads(json_text)
                        p_data = data.get("pdpData", {})
                        return {
                            "platform": "Myntra",
                            "title": p_data.get("name", ""),
                            "price": float(p_data.get("price", {}).get("discounted", 0)),
                            "mrp": float(p_data.get("price", {}).get("mrp", 0)),
                            "image": p_data.get("media", {}).get("albums", [{}])[0].get("images", [{}])[0].get("imageURL", ""),
                            "url": url
                        }
                    except Exception as e:
                        print(f"Myntra parse error: {e}")
            return {}

        return asyncio.run(scrape())

    def fetch_ajio(self, url: str) -> dict:
        return {}
