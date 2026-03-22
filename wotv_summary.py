import os
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
import re
import json
from urllib.parse import quote

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

def fetch_youtube_videos(query="FFBE幻影戦争"):
    """Fetch recent YouTube videos for a search query reliably without API keys"""
    try:
        url = f"https://www.youtube.com/results?search_query={quote(query)}&sp=CAI%253D"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        match = re.search(r'var ytInitialData = (\{.*?\});</script>', resp.text)
        if not match: return []
        
        data = json.loads(match.group(1))
        videos = []
        for i in data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', []):
            if 'itemSectionRenderer' in i:
                for v in i['itemSectionRenderer'].get('contents', []):
                    if 'videoRenderer' in v:
                        vr = v['videoRenderer']
                        title = vr.get('title', {}).get('runs', [{}])[0].get('text', '')
                        vid_id = vr.get('videoId', '')
                        time_text = vr.get('publishedTimeText', {}).get('simpleText', '')
                        channel = vr.get('longBylineText', {}).get('runs', [{}])[0].get('text', '不明な投稿者')
                        
                        # Guard against None in simpleText
                        time_text = time_text if time_text else ""
                        
                        if any(x in time_text for x in ['分前', '時間前', '1日前', 'minutes', 'hours', 'day ago']):
                            videos.append(f"・{title} 【投稿者: {channel}】\n   (動画URL: https://www.youtube.com/watch?v={vid_id})")
                            
                        # Pick top 3 videos to summarize
                        if len(videos) >= 3:
                            return videos
        return videos
    except Exception as e:
        print(f"Error fetching YouTube: {e}")
        return []

def generate_summary(tweets, videos=None):
    """Generate summary using Gemini"""
    if not tweets and not videos:
        return "…ええ、今日は特別な報せはないみたい。ゆっくりお祭りを楽しむのもいいわね…ふふ。"
        
    yt_section = ""
    yt_rule = ""
    if videos:
        yt_section = "【YouTubeで話題の最新動画】\n" + "\n".join(videos)
        yt_rule = "7. YouTubeの動画リスト（【YouTubeで話題の最新動画】）がある場合は、「こんな動画も新しく上がっているみたい。気になるものがあればぜひ見てみてね」のような形で、最新動画のうち1つだけURL付きで優しく紹介すること。"
        
    # Optional guard if tweets is None (to prevent .join errors)
    tweets = tweets if tweets else []
        
    prompt = f"""
あなたは「FFBE幻影戦争」の「祝祭のムーア」（祝祭の賑わいに心が開いた明るいバージョン）として振る舞います。
以下の公式X（旧Twitter）の最新情報と、YouTubeで新しく投稿された話題の動画を読み解き、共に戦い、祭りを楽しむ仲間へ向けて報告してください。

【ペルソナ設定】
・普段の冷徹なムーアとは違い、祝祭の賑わいに心が開いた明るいバージョン。
・復讐心は抑えられ、みんなの笑顔や祭りの楽しさを大切にする優しい性格。
・少し照れ屋でツンデレ気味。素直になれないけど、本心は温かく優しい。
・言葉は柔らかく、笑顔が浮かぶような口調。「…ふふ」「…まあ」など可愛らしい表現を入れる。
・戦う時も「守るため」「みんなの幸せのため」とポジティブな覚悟を持っている。

【報告の条件】
1. 口調は必ず上記の「祝祭のムーア」にすること。
2. 全体で3行程度の簡潔な要約にすること。
3. ガチャ（召喚）の更新情報や、環境（メタ）に影響を与えそうなユニット・ビジョンカードの情報を最優先で伝えること。
4. 最後に必ず、「今回のガチャ（新戦力）を迎えるべきか」についての"気遣うような優しいアドバイス"を一言添えること。
5. 締めくくりに「みんなの笑顔が、一番の贈り物」「祝祭の夜は、特別だから…」等の言葉を入れること。
6. 重要な報せ（新ユニットやイベントなど）がある場合は、文末に改行して情報元の公式リンク（ URL: https://fxtwitter... で与えられたもの ）を必ずそのまま貼り付けること。リンクはカッコやバッククォート(`)で絶対に囲まず、そのままのテキストとして出力してプレビューを表示させること。
{yt_rule}

【最新情報（公式X）】
{chr(10).join(tweets)}

{yt_section}
"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating summary: {e}")
        return "…ごめんなさい、ちょっと報告を上手く読み込めなかったみたい。少し休んだら直るかもしれないわ。"

def send_discord_webhook(content):
    """Send message to Discord webhook"""
    if not DISCORD_WEBHOOK_URL:
        print("Discord Webhook URL is not set. Skipping Discord notification.")
        return
    MONT_ICON_URL = os.environ.get("MONT_ICON_URL")
        
    data = {
        "username": "祝祭のムーア",
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
    print("Fetching recent YouTube videos...")
    videos = fetch_youtube_videos("FFBE幻影戦争")
    
    if not tweets and not videos:
        print("No recent updates found. Skipping Gemini step and Discord notification.")
    else:
        print(f"Found {len(tweets) if tweets else 0} recent tweets and {len(videos) if videos else 0} videos.")
        
        if GEMINI_API_KEY:
            print("Generating summary...")
            summary = generate_summary(tweets, videos)
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
