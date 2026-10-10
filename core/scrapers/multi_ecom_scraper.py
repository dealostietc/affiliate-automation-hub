import re
import json
import requests
from bs4 import BeautifulSoup

class MultiEcomFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_myntra(self, url: str) -> dict:
        """Extracts Myntra product details via embedded window state."""
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            match = re.search(r'<script>window.__myx\s*=\s*({.*?})</script>', res.text)
            if match:
                data = json.loads(match.group(1)).get('pdpData', {})
                return {
                    "platform": "Myntra",
                    "title": data.get('name'),
                    "price": float(data.get('price', 0)),
                    "mrp": float(data.get('mrp', 0)),
                    "image": data.get('media', {}).get('albums', [{}])[0].get('images', [{}])[0].get('src'),
                    "url": url
                }
        return {}

    def fetch_ajio(self, url: str) -> dict:
        """Extracts Ajio product metadata using internal page state JSON."""
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            match = re.search(r'window.__PRELOADED_STATE__\s*=\s*({.*?});', res.text)
            if match:
                data = json.loads(match.group(1)).get('product', {}).get('productDetails', {})
                price_data = data.get('price', {})
                return {
                    "platform": "Ajio",
                    "title": data.get('name'),
                    "price": float(price_data.get('value', 0)),
                    "mrp": float(price_data.get('wasPriceData', {}).get('value', 0)),
                    "image": data.get('baseOptions', [{}])[0].get('options', [{}])[0].get('modelImage', {}).get('url'),
                    "url": url
                }
        return {}

    def fetch_croma(self, url: str) -> dict:
        """Extracts Croma product information."""
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            title = soup.find("h1")
            price_elem = soup.find("span", {"id": "pdp-product-price"}) or soup.find("span", {"class": "amount"})
            mrp_elem = soup.find("span", {"class": "old-price"})
            img_elem = soup.find("img", {"class": "pdp-img"})

            def parse_num(val):
                return float(re.sub(r'[^\d.]', '', val)) if val else 0.0

            return {
                "platform": "Croma",
                "title": title.text.strip() if title else "Croma Product",
                "price": parse_num(price_elem.text) if price_elem else 0.0,
                "mrp": parse_num(mrp_elem.text) if mrp_elem else 0.0,
                "image": img_elem['src'] if img_elem else "",
                "url": url
            }
        return {}

    def fetch_zepto_instamart(self, platform_name: str, payload_data: dict) -> dict:
        """
        Quick commerce apps (Zepto/Instamart) rely on store pin-codes and mobile APIs.
        Parse payload response from app request proxies.
        """
        return {
            "platform": platform_name,
            "title": payload_data.get("name"),
            "price": float(payload_data.get("discounted_price", 0)),
            "mrp": float(payload_data.get("mrp", 0)),
            "image": payload_data.get("image_url"),
            "url": payload_data.get("deep_link")
        }
