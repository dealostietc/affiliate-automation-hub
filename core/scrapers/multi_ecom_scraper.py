import json
import re
import requests
from bs4 import BeautifulSoup

class MultiEcomFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_croma(self, url: str) -> dict:
        try:
            # Extract product code/ID from Croma URL (e.g., '309180' from '/p/309180')
            match = re.search(r'/p/(\d+)', url)
            if not match:
                print("Could not parse Croma product ID from URL.")
                return {}
            
            product_id = match.group(1)
            
            # Croma internal product detail API
            api_url = f"https://www.croma.com/api/v1/products/{product_id}"
            
            res = requests.get(api_url, headers=self.headers, timeout=10)
            
            # Fallback if API route direct check fails: Parse embedded JSON state from HTML page
            if res.status_code != 200:
                res = requests.get(url, headers=self.headers, timeout=10)
                if res.status_code != 200:
                    return {}
                
                soup = BeautifulSoup(res.text, "html.parser")
                script = soup.find("script", id="__NEXT_DATA__")
                if script and script.string:
                    data = json.loads(script.string)
                    p_data = data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("product", {}).get("productDetails", {})
                    return {
                        "platform": "Croma",
                        "title": p_data.get("name", ""),
                        "price": float(p_data.get("price", {}).get("value", 0)),
                        "mrp": float(p_data.get("mrp", {}).get("value", 0)),
                        "image": p_data.get("images", [{}])[0].get("url", ""),
                        "url": url
                    }
                return {}

            data = res.json()
            
            title = data.get("name", "")
            price = float(data.get("price", {}).get("value", 0))
            mrp = float(data.get("mrp", {}).get("value", price))
            images = data.get("images", [])
            image_url = images[0].get("url", "") if images else ""

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

    def fetch_ajio(self, url: str) -> dict:
        return {}
