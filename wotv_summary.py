import os
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
import re

# --- Configuration ---
RSS_URL = "https://nitter.net/WOTV_FFBE/rss"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def fetch_recent_tweets():
    """Fetch recent tweets from Nitter RSS"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(RSS_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        tweets = []
        
        # Get items from the last 24 hours
        now = datetime.now(timezone.utc)
        
        for item in root.findall('./channel/item'):
            title = item.find('title').text if item.find('title') is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""
            pubDate_str = item.find('pubDate').text if item.find('pubDate') is not None else ""
            
            # Simple exact text extraction (stripping HTML if any)
            text = re.sub('<[^<]+>', '', description).strip()
            
            # Nitter dates are like: Thu, 12 Oct 2023 18:00:00 GMT
            try:
                # Convert to datetime
                pubDate = datetime.strptime(pubDate_str, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                if now - pubDate < timedelta(days=7):
                    tweets.append(text)
            except Exception as e:
                # In case parsing fails, just append if we don't have too many
                if len(tweets) < 10:
                    tweets.append(text)
                    
        return tweets
    except Exception as e:
        print(f"Error fetching RSS: {e}")
        return None

def generate_summary(tweets):
    """Generate summary using Gemini"""
    if not tweets:
        return "我が軍に報告すべき新たな報せは届いておらんようだ。"
        
    prompt = f"""
あなたは「FFBE幻影戦争」を熟知した歴戦のベテラン軍師です。
以下の公式X（旧Twitter）の最新情報（過去24時間分）を読み解き、プレイヤーである城主へ報告してください。

【報告の条件】
1. 口調は「威厳あるベテラン軍師」風にすること（「〜である」「〜でござるな」「城主殿」など）。
2. 全体で3行程度の簡潔な要約にすること。
3. ガチャ（召喚）の更新情報や、環境（メタ）に影響を与えそうなユニット・ビジョンカードの情報を最優先で伝えること。
4. 最後に必ず、「今回のガチャを引くべきか」についての軍師としての結論（引くべき、見送るべき、様子見など）を一言添えること。

【最新情報】
{chr(10).join(tweets)}
"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "無念…密偵からの報告を解読するのに失敗したようだ。"

def send_discord_webhook(content):
    """Send message to Discord webhook"""
    if not DISCORD_WEBHOOK_URL:
        print("Discord Webhook URL is not set. Skipping Discord notification.")
        return
        
    data = {
        "username": "幻影戦争 報告軍師",
        "content": content
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
        print("Successfully sent to Discord.")
    except Exception as e:
        print(f"Error sending to Discord: {e}")

if __name__ == "__main__":
    print("Fetching recent tweets from Nitter...")
    tweets = fetch_recent_tweets()
    
    if tweets:
        print(f"Found {len(tweets)} recent tweets.")
    else:
        print("No recent tweets found or failed to fetch.")
        
    # We still run summary even if empty to send the 'no new reports' message
    if GEMINI_API_KEY:
        print("Generating summary...")
        summary = generate_summary(tweets)
        print("========== Summary ==========")
        print(summary)
        print("=============================")
        
        print("Sending to Discord...")
        send_discord_webhook(summary)
    else:
        print("GEMINI_API_KEY is not set. Skipping generation and notification for local test.")
        if tweets:
            print("Preview of tweets to be sent to Gemini:")
            for t in tweets:
                safe_text = t[:50].encode('cp932', errors='ignore').decode('cp932')
                print(f"- {safe_text}...")
