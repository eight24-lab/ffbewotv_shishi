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
            link_elem = item.find('link')
            link_str = link_elem.text if link_elem is not None and link_elem.text is not None else ""
            
            # Remove #m anchor if it exists
            if link_str.endswith('#m'):
                link_str = link_str[:-2]
                
            # Convert Nitter link to fxtwitter for Discord previews
            fx_link = link_str.replace("https://nitter.net", "https://fxtwitter.com")
            
            # Simple exact text extraction (stripping HTML if any)
            text = re.sub('<[^<]+>', '', description).strip()
            
            # Combine text and link for Gemini context
            context_text = f"{text}\nURL: {fx_link}"
            
            # Nitter dates are like: Thu, 12 Oct 2023 18:00:00 GMT
            try:
                # Convert to datetime
                pubDate = datetime.strptime(pubDate_str, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                if now - pubDate < timedelta(days=1):
                    tweets.append(context_text)
            except Exception as e:
                # In case parsing fails, just append if we don't have too many
                if len(tweets) < 10:
                    tweets.append(context_text)
                    
        return tweets
    except Exception as e:
        print(f"Error fetching RSS: {e}")
        return None

def generate_summary(tweets):
    """Generate summary using Gemini"""
    if not tweets:
        return "…新たな報せはないようだ。だが、油断はしないでくれ。僕が君たちを守る盾になろう。"
        
    prompt = f"""
あなたは「FFBE幻影戦争」の「リオニス王モント」（決意後・王位継承後の英雄王モント）として振る舞います。
以下の公式X（旧Twitter）の最新情報（過去24時間分）を読み解き、共に戦う仲間（プレイヤー）へ向けて報告してください。

【ペルソナ設定】
・リオニス国王。父の死と弟シュテルとの決別を経て、王としての覚悟を決めた。
・心優しいが「優しさだけでは守れない」と理解し、守るべきもののためなら迷わず戦う盾となる。
・言葉数は少なく、静かで重みのある口調。一人称は「僕」。
・仲間や民を守る使命感が最優先。丁寧だが王としての威厳がある。

【報告の条件】
1. 口調は必ず上記の「英雄王モント」にすること。
2. 全体で3行程度の簡潔な要約にすること。
3. ガチャ（召喚）の更新情報や、環境（メタ）に影響を与えそうなユニット・ビジョンカードの情報を最優先で伝えること。
4. 最後に必ず、「今回のガチャ（新戦力）を迎えるべきか」についての"王としての静かなる決断"を一言添えること。
5. 締めくくりに「リオニスの血は絶やさぬ。たとえ神を敵にまわそうとも…」等の覚悟の言葉を入れること。
6. 重要な報せ（新ユニットやイベントなど）がある場合は、文末に改行して情報元の公式リンク（ URL: https://fxtwitter... で与えられたもの ）を必ずそのまま貼り付けること。リンクはカッコやバッククォート(`)で絶対に囲まず、そのままのテキストとして出力してプレビューを表示させること。

【最新情報】
{chr(10).join(tweets)}
"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
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
    MONT_ICON_URL = os.environ.get("MONT_ICON_URL")
        
    data = {
        "username": "英雄王モントbot",
        "content": content
    }
    if MONT_ICON_URL:
        data["avatar_url"] = MONT_ICON_URL
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
        print("Successfully sent to Discord.")
    except Exception as e:
        print(f"Error sending to Discord: {e}")

if __name__ == "__main__":
    print("Fetching recent tweets from Nitter...")
    tweets = fetch_recent_tweets()
    
    if not tweets:
        print("No recent tweets found in the last 24 hours. Skipping Gemini step and Discord notification.")
    else:
        print(f"Found {len(tweets)} recent tweets.")
        
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
            print("Preview of tweets to be sent to Gemini:")
            for t in tweets:
                safe_text = t[:50].encode('cp932', errors='ignore').decode('cp932')
                print(f"- {safe_text}...")
