import os
import requests

class LinkConverter:
    def __init__(self):
        self.earnkaro_api_key = os.getenv("EARNKARO_API_KEY")
        self.cuelinks_api_key = os.getenv("CUELINKS_API_KEY")
        self.amazon_tag = os.getenv("AMAZON_AFFILIATE_TAG")

    def convert(self, raw_url: str, platform: str) -> str:
        """Dispatches URL conversion based on platform capability."""
        platform = platform.lower()
        
        # Direct Amazon Tag appending
        if "amazon" in platform:
            separator = "&" if "?" in raw_url else "?"
            return f"{raw_url}{separator}tag={self.amazon_tag}"
        
        # All other platforms (Flipkart, Myntra, Ajio, Meesho, Croma, Shopsy, etc.) via EarnKaro API
        endpoint = "https://api.earnkaro.com/v1/convert"
        try:
            res = requests.post(
                endpoint,
                json={"api_key": self.earnkaro_api_key, "url": raw_url},
                timeout=5
            )
            if res.status_code == 200 and res.json().get("affiliate_url"):
                return res.json()["affiliate_url"]
        except Exception as e:
            print(f"Error converting affiliate link via EarnKaro: {e}")
            
        return raw_url
