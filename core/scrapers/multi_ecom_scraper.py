import json
import requests
from bs4 import BeautifulSoup

class MultiEcomFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_croma(self, url: str) -> dict:
        try:
            res = requests.get(url, headers=self.headers, timeout=12)
            if res.status_code != 200:
                print(f"Croma returned HTTP status: {res.status_code}")
                return {}

            soup = BeautifulSoup(res.text, "html.parser")
            
            # Find Next.js hydration state
            next_data = soup.find("script", id="__NEXT_DATA__")
            if next_data and next_data.string:
                data = json.loads(next_data.string)
                # Navigate Croma's state tree safely
                page_props = data.get("props", {}).get("pageProps", {})
                initial_state = page_props.get("initialState", {})
                product_data = initial_state.get("product", {}).get("productDetails", {})
                
                if not product_data:
                    # Fallback path in Croma JSON schema
                    product_data = page_props.get("productData", {})

                title = product_data.get("name", "")
                price = float(product_data.get("price", {}).get("value", 0))
                mrp = float(product_data.get("mrp", {}).get("value", price))
                
                images = product_data.get("images", [])
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

            print("Could not locate __NEXT_DATA__ payload on Croma page.")
        except Exception as e:
            print(f"Croma scraping error: {e}")
        return {}
