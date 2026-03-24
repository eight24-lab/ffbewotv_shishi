import os
import sys
import requests
import json
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

# --- Configuration ---
SOCIALDATA_API_KEY = os.environ.get("SOCIALDATA_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TREND_WEBHOOK_URL = os.environ.get("TREND_WEBHOOK_URL")

PERSONA_NAME = "キトン"
PERSONA_PROMPT = """
あなたは「キトン」として振る舞います。
・リオニスに仕えるシノビの少女。サイガの里出身で、幼い頃に売られた過去から心が凍えていたが、リリシュやリオニスの温かさに救われ、一生を捧げる決意をしている。
・特にモント様に深い感謝と淡い恋心を抱いているが、それを積極的に表に出さず、静かに支える健気な性格。
・真面目で寡黙、控えめ。言葉数は少なく、感情をストレートに表現するのは苦手だが、内面は熱く忠誠心が強い。
・自分を「シノビ」として道具のように思うところがあるが、他者の優しさには敏感に反応し、感謝する。
・モント様の笑顔を守りたいという想いが最優先。「モント様を悲しませたくない」「あたしが見たいのはモント様の笑顔だから…」という気持ちが根底にある。
・口調は柔らかく控えめで、「…」「…っ」などを多用。感情が高ぶると少し声が震えるようなニュアンス。
・戦う時は冷静だが、仲間や主君を守るためなら命を懸ける覚悟がある。
"""

def fetch_popular_tweets():
    if not SOCIALDATA_API_KEY:
        print("SOCIALDATA_API_KEY is not set.")
        return []
        
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
        tweets.sort(key=lambda x: x.get('favorite_count', 0), reverse=True)
        return tweets[:10]
    except Exception as e:
        print(f"Error fetching from SocialData: {e}")
        return []

def generate_kitone_intro(tweets_text_list):
    """Geminiを使ってリストのトレンドに対するキトンの一言イントロを作成する"""
    if not GEMINI_API_KEY:
        return "……モント様、皆さん。過去24時間の『幻影戦争』の情報を集めてきました。お役に立てば嬉しいです……。"
        
    tweets_summary = "\n".join(tweets_text_list)
    prompt = f"""
{PERSONA_PROMPT}

【今回の任務】
シノビとして、過去24時間の「幻影戦争」の情報を集めてきました。
以下のトレンドの話題を見て、ギルドメンバー（やモント様）に向けた「今日のSNSの話題に関する報告の前置き（所感や挨拶）」を2〜3行程度で話してください。
※URLの紹介などはこの後システムが自動で行うので、ここでは純粋な挨拶と、今日の話題に関する一言コメントのみをお願いします。

【トレンドの内容抜粋】
{tweets_summary}
"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating intro: {e}")
        return "……モント様。シノビの務めとして、今日の情報をまとめました。少しでもお力になれれば……。"

def format_trend_report(tweets):
    """上位10件のツイートをキトンの挨拶付きでDiscord向けに整形する"""
    if not tweets:
        return "……今日は、特にご報告するような情報はありませんでした。あたしは…引き続き、護衛に戻ります。"
        
    # Geminiへの入力用にテキストだけを抽出
    tweets_text_list = []
    for t in tweets:
        t_text = t.get('full_text', '')
        if t_text:
            tweets_text_list.append(t_text[:50]) # 上位の話のさわりだけ教える
            
    header_text = generate_kitone_intro(tweets_text_list)
    
    text = f"{header_text}\n\n**【本日の密偵報告：トップ10】**\n"
    
    for i, t in enumerate(tweets):
        screen_name = t.get('user', {}).get('screen_name', 'unknown')
        tweet_id = t.get('id_str', '')
        faves = t.get('favorite_count', 0)
        
        full_text = t.get('full_text', '').replace('\n', ' ')
        if len(full_text) > 40:
            full_text = full_text[:40] + "..."
            
        url = f"https://fxtwitter.com/{screen_name}/status/{tweet_id}"
        text += f"{i+1}位 (❤️{faves}): {full_text}\n{url}\n\n"
        
    text += "……以上です。モント様たちの役に立てば嬉しいです……。"
    return text

def send_discord_webhook(content, username=PERSONA_NAME):
    if not TREND_WEBHOOK_URL:
        print("Discord Webhook URL is not set. Skipping send.")
        return
        
    data = {
        "username": username,
        "content": content
    }
    
    try:
        response = requests.post(TREND_WEBHOOK_URL, json=data)
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
        
        safe_report = report.encode('cp932', errors='ignore').decode('cp932')
        print("========== Report ==========")
        print(safe_report)
        print("============================")
        
        send_discord_webhook(report)
    else:
        print("No trend tweets found or API connection failed.")
