import os
import requests

class LinkConverter:
    def __init__(self):
        self.cuelinks_key = os.getenv("CUELINKS_API_KEY")
        self.earnkaro_key = os.getenv("EARNKARO_API_KEY")
        self.amazon_tag = os.getenv("AMAZON_AFFILIATE_TAG")

    def convert(self, raw_url: str, platform: str) -> str:
        platform_lower = platform.lower()
        
        # Amazon direct tagging
        if "amazon" in platform_lower and self.amazon_tag:
            sep = "&" if "?" in raw_url else "?"
            return f"{raw_url}{sep}tag={self.amazon_tag}"
        
        # Cuelinks API Conversion
        if self.cuelinks_key:
            try:
                res = requests.get(
                    "https://www.cuelinks.com/api/v2/link.json",
                    params={"url": raw_url, "api_key": self.cuelinks_key},
                    timeout=5
                )
                if res.status_code == 200:
                    return res.json().get("affiliate_url", raw_url)
            except Exception as e:
                print(f"Cuelinks conversion error: {e}")

        # EarnKaro API fallback
        if self.earnkaro_key:
            try:
                res = requests.post(
                    "https://api.earnkaro.com/v1/convert",
                    json={"api_key": self.earnkaro_key, "url": raw_url},
                    timeout=5
                )
                if res.status_code == 200 and res.json().get("affiliate_url"):
                    return res.json()["affiliate_url"]
            except Exception as e:
                print(f"EarnKaro conversion error: {e}")

        return raw_url
