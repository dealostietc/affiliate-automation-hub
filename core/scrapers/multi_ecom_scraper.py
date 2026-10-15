import json
import requests
from bs4 import BeautifulSoup

class MultiEcomFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

    def fetch_myntra(self, url: str) -> dict:
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return {}
            
            soup = BeautifulSoup(res.text, "html.parser")
            for script in soup.find_all("script"):
                if script.string and "window.__myx =" in script.string:
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
            print(f"Myntra scraping error: {e}")
        return {}

    def fetch_croma(self, url: str) -> dict:
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return {}
            soup = BeautifulSoup(res.text, "html.parser")
            title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Croma Product"
            price_elem = soup.find("span", {"id": "pdp-product-discount-price"})
            price = float(price_elem.get_text().replace("₹", "").replace(",", "").strip()) if price_elem else 0.0
            
            return {
                "platform": "Croma",
                "title": title,
                "price": price,
                "mrp": price,
                "image": "",
                "url": url
            }
        except Exception as e:
            print(f"Croma scraping error: {e}")
        return {}

    def fetch_ajio(self, url: str) -> dict:
        # Implementation for Ajio endpoint
        return {}
