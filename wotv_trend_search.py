import os
import sys
import requests
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

# --- Configuration ---
SOCIALDATA_API_KEY = os.environ.get("SOCIALDATA_API_KEY")
# 送信先は一旦イルディラのチャンネル（またはムーアのチャンネル等）にします
DISCORD_WEBHOOK_URL = os.environ.get("ILDYRA_WEBHOOK_URL")

PERSONA_NAME = "シャドウリンクス"
INTRODUCTION = "……密偵報告よ。過去24時間の『幻影戦争』界隈における、界隈の注目（いいねやRT）を集めている情報をまとめたわ。"

def fetch_popular_tweets():
    """SocialData APIから幻影戦争のトレンドツイートを取得する"""
    if not SOCIALDATA_API_KEY:
        print("SOCIALDATA_API_KEY is not set.")
        return []
        
    # クエリ: "幻影戦争"を含み、リプライを除外し、いいねが20以上のツイート
    # さらに本日〜昨日（過去24h程度）の範囲にするため、クエリに since を付けるか取得後にフィルタリングします。
    # APIの制約で since:YYYY-MM-DD が使えるのでそれを使う。
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    query = f"幻影戦争 min_faves:10 -filter:replies since:{yesterday}"
    
    url = f"https://api.socialdata.tools/twitter/search?query={quote(query)}"
    headers = {
        'Authorization': f'Bearer {SOCIALDATA_API_KEY}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        tweets = data.get('tweets', [])
        
        # 取得したツイートを、いいね数(favorite_count)で降順ソート
        tweets.sort(key=lambda x: x.get('favorite_count', 0), reverse=True)
        
        return tweets[:10]  # 上位10件
    except Exception as e:
        print(f"Error fetching from SocialData: {e}")
        return []

def format_trend_report(tweets):
    """上位10件のツイートをDiscord向けに整形する"""
    if not tweets:
        return "……特に目ぼしい情報はなかったようね。"
        
    text = f"{INTRODUCTION}\n\n"
    
    for i, t in enumerate(tweets):
        # fxtwitterに変換してDiscord上で綺麗にプレビューされるようにする
        screen_name = t.get('user', {}).get('screen_name', 'unknown')
        tweet_id = t.get('id_str', '')
        faves = t.get('favorite_count', 0)
        
        # テキストはある程度短縮する
        full_text = t.get('full_text', '').replace('\n', ' ')
        if len(full_text) > 40:
            full_text = full_text[:40] + "..."
            
        url = f"https://fxtwitter.com/{screen_name}/status/{tweet_id}"
        
        text += f"**{i+1}位** (❤️{faves}): {full_text}\n{url}\n\n"
        
    text += "報告は以上よ。また明日のこの時間にお届けするわ。"
    return text

def send_discord_webhook(content, username=PERSONA_NAME):
    if not DISCORD_WEBHOOK_URL:
        print("Discord Webhook URL is not set. Skipping send.")
        return
        
    data = {
        "username": username,
        "content": content
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
        print("Successfully sent to Discord.")
    except Exception as e:
        print(f"Error sending to Discord: {e}")

if __name__ == "__main__":
    print("Fetching trend data via SocialData...")
    popular_tweets = fetch_popular_tweets()
    
    if popular_tweets:
        print(f"Found {len(popular_tweets)} popular tweets.")
        report = format_trend_report(popular_tweets)
        
        # for testing visibility
        safe_report = report.encode('cp932', errors='ignore').decode('cp932')
        print("========== Report ==========")
        print(safe_report)
        print("============================")
        
        send_discord_webhook(report)
    else:
        print("No trend tweets found or API connection failed.")
