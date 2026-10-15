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
                print(f"Croma returned HTTP status {res.status_code}")
                return {}

            soup = BeautifulSoup(res.text, "html.parser")
            
            # Extract Title
            title_elem = soup.find("h1", class_=lambda c: c and "pd-title" in c) or soup.find("h1")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Extract Price
            price_elem = (
                soup.find("span", {"id": "pdp-product-discount-price"}) or
                soup.find("span", class_=lambda c: c and ("amount" in c or "pdpPrice" in c)) or
                soup.find("span", class_="new-price")
            )
            
            price = 0.0
            if price_elem:
                raw_price = price_elem.get_text().replace("₹", "").replace(",", "").strip()
                try:
                    price = float(raw_price)
                except ValueError:
                    price = 0.0

            # Extract MRP
            mrp_elem = soup.find("span", class_=lambda c: c and ("old-price" in c or "mrp" in c))
            mrp = price
            if mrp_elem:
                raw_mrp = mrp_elem.get_text().replace("₹", "").replace(",", "").strip()
                try:
                    mrp = float(raw_mrp)
                except ValueError:
                    mrp = price

            # Extract Image URL
            img_elem = soup.find("img", id="pdp-product-image") or soup.find("img", class_=lambda c: c and "main-img" in c)
            image_url = img_elem.get("src", "") if img_elem else ""

            if not title or price == 0:
                return {}

            return {
                "platform": "Croma",
                "title": title,
                "price": price,
                "mrp": mrp,
                "image": image_url,
                "url": url
            }
        except Exception as e:
            print(f"Croma scraping error: {e}")
        return {}

    def fetch_ajio(self, url: str) -> dict:
        return {}
