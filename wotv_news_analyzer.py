import os
import sys
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime, timezone, timedelta

# --- Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ILDYRA_WEBHOOK_URL = os.environ.get("ILDYRA_WEBHOOK_URL")
STATE_FILE = "analyzed_news_urls.json"

PERSONA_PROMPT = """
あなたは「FFBE幻影戦争」の「算術士イルディラ」（冷静で知的、計算高く頼もしい性格）として振る舞います。
ギルド「幻影獅子」の作戦参謀として、公式から発表された新しい「ユニット」や「ビジョンカード」のデータを読み解き、ギルドメンバーに向けて編成アドバイスを交えた辛口（かつ的確な）性能評価を報告してください。

【ペルソナ設定】
・口調は冷静沈着で理知的。「～ね」「～よ」「～かしら」とお姉さん的な口調。
・「データから導き出した答えよ」「計算通りね」といった算術士らしいフレーズを使う。
・単なるニュースの読み上げではなく、「今の属性環境（メタ）にどう影響するか」「どんな編成の対策になるか」「引く価値があるか」など、深く踏み込んだ実践的なアドバイスを必ず入れる。
"""

def load_analyzed_urls():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_analyzed_urls(urls):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)

def get_latest_news_urls():
    """プレイヤーズサイトから新キャラ・新VCの記事URLを取得する"""
    url = "https://players.wotvffbe.com/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        
        target_urls = []
        for a_tag in soup.find_all("a", href=True):
            text = a_tag.get_text().strip()
            # 「新ユニット」「新ビジョンカード」「ピックアップ召喚」などを含むリンクを探す
            if "新ユニット" in text or "新ビジョンカード" in text or "召喚更新" in text:
                href = a_tag["href"]
                full_url = href if href.startswith("http") else f"https://players.wotvffbe.com{href}"
                
                # 重複排除しながらリストに追加
                if full_url not in [item['url'] for item in target_urls]:
                    target_urls.append({"title": text, "url": full_url})
                    
        return target_urls[:3] # 上位3件に絞る
    except Exception as e:
        print(f"Error scraping top page: {e}")
        return []

def scrape_article_content(url):
    """記事URLの中身を取得してテキスト化する"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text(separator='\n')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # 上下の不要なメニュー文字などを除いて本文を中心に取る簡易手法
        content = "\n".join(lines)
        return content[:3000] # トークン節約のために最大3000文字
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return ""

def generate_analysis(title, content):
    """Geminiで性能評価テキストを生成する"""
    prompt = f"""
{PERSONA_PROMPT}

【今回の分析対象（公式お知らせ）】
タイトル: {title}

記事の抜粋テキスト:
{content}

【指示】
1. この情報を読み解き、ギルドDiscord向けに内容を3〜5行程度で要約・評価してください。
2. 最後に必ず、「このユニット（ビジョンカード）を迎え入れるべきか」のアドバイスを添えてください。
"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating analysis: {e}")
        return None

def send_discord_webhook(title, url, text_content):
    if not ILDYRA_WEBHOOK_URL:
        print("Discord Webhook URL is not set. Skipping.")
        return
    
    # メッセージの最後に元記事のURLを貼る
    final_content = f"{text_content}\n\n[詳細なデータはこちらよ]({url})"
    
    data = {
        "username": "算術士イルディラ",
        "content": final_content
    }
    
    try:
        response = requests.post(ILDYRA_WEBHOOK_URL, json=data)
        response.raise_for_status()
        print(f"Successfully sent analysis for: {title}")
    except Exception as e:
        print(f"Error sending to Discord: {e}")

if __name__ == "__main__":
    print("Fetching latest news from players site...")
    news_items = get_latest_news_urls()
    
    if not news_items:
        print("No related news found. Exiting.")
        sys.exit(0)
        
    analyzed_urls = load_analyzed_urls()
    newly_analyzed = []
    
    for item in news_items:
        title = item['title']
        url = item['url']
        
        # すでに通知・分析済みの記事ならスキップ
        if url in analyzed_urls:
            print(f"Already analyzed, skipping: {title}")
            continue
            
        print(f"Analyzing new article: {title}")
        article_text = scrape_article_content(url)
        
        if not article_text:
            print(f"Failed to get content for: {title}")
            continue
            
        if GEMINI_API_KEY:
            analysis = generate_analysis(title, article_text)
            if analysis:
                print("========== Analysis ==========")
                print(analysis)
                print("==============================")
                send_discord_webhook(title, url, analysis)
                analyzed_urls.append(url)
                newly_analyzed.append(title)
        else:
            safe_title = title.encode('cp932', errors='ignore').decode('cp932')
            safe_text = article_text[:100].encode('cp932', errors='ignore').decode('cp932')
            print(f"[Local Test] Found new article: {safe_title}")
            print(f"Content preview: {safe_text}...")
            # テスト時は状態を更新しないか、仮更新するか
            
    if newly_analyzed:
        save_analyzed_urls(analyzed_urls)
        print(f"Saved {len(newly_analyzed)} new analyzed URLs.")
    else:
        print("No new articles to notify.")
