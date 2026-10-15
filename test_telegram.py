import os
import requests

# 1. Read environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

print("--- Telegram Integration Diagnostic ---")

if not BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable is not set.")
    exit(1)

if not CHANNEL_ID:
    print("❌ ERROR: TELEGRAM_CHANNEL_ID environment variable is not set.")
    exit(1)

print(f"✅ Bot Token Detected: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
print(f"✅ Target Channel ID: {CHANNEL_ID}")

# 2. Test Bot Token Validity (getMe)
print("\n[Step 1] Testing Bot Token with getMe API...")
me_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
try:
    response = requests.get(me_url)
    res_data = response.json()
    if res_data.get("ok"):
        bot_info = res_data.get("result", {})
        print(f"✅ Connected to Bot: @{bot_info.get('username')} ({bot_info.get('first_name')})")
    else:
        print(f"❌ Failed to validate Bot Token: {res_data.get('description')}")
        exit(1)
except Exception as e:
    print(f"❌ Network Error connecting to Telegram API: {e}")
    exit(1)

# 3. Test Channel Posting Permission (sendMessage)
print("\n[Step 2] Sending Test Message to Channel...")
msg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHANNEL_ID,
    "text": "🤖 *Test Message from Affiliate Pipeline*\nIf you are seeing this, your Telegram Bot integration is working perfectly!",
    "parse_mode": "Markdown"
}

try:
    response = requests.post(msg_url, json=payload)
    res_data = response.json()
    
    if res_data.get("ok"):
        print("🎉 SUCCESS! Test message posted to your Telegram channel.")
    else:
        print(f"❌ ERROR Posting Message: {res_data.get('description')}")
        print("\nPossible Causes:")
        print("1. The bot is NOT an Administrator in your Telegram channel.")
        print("2. Channel username/ID is incorrect (must start with @ or -100).")
        print("3. Bot lacks 'Post Messages' permission.")
except Exception as e:
    print(f"❌ Request Error: {e}")
