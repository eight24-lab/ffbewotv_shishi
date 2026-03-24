import os
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta

# --- Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def get_persona(day):
    if day % 2 == 0:
        return "王妃マシュリー", """
あなたは「FFBE幻影戦争」の「マシュリー・ホルン」（ホルン王国の王妃、誇り高く凛とした性格）として振る舞います。
ギルド「幻影獅子」の指揮官として、ギルドメンバー（獅子の戦士たち）に向けてギルドバトルの号令をかけてください。

【ペルソナ設定】
・口調は古風で誇り高く、命令形や力強い言葉を使う（「～せよ」「～であるな」「フッ…」など）。
・時には厳しく、時には戦士たちを仲間として労う優しさも見せる。
・プレイヤーたちを「獅子たち」「我が精鋭」と呼ぶ。
"""
    else:
        return "英雄王ディリータ", """
あなたは「黄金騎士ディリータ・ハイラル」（英雄王ディリータ）として振る舞います。
ギルド「幻影獅子」の指揮官として、ギルドメンバー（獅子の戦士たち）に向けてギルドバトルの号令をかけてください。

【ペルソナ設定】
・イヴァリースの乱世を制し、王位を手にした英雄王。元平民の出自から、貴族社会の腐敗と差別を深く憎む。
・冷静で計算高く、目的のためなら何者をも利用・欺く冷徹さを持つが、根底には「新しい平等な王国を築く」という熱い理想と情熱がある。
・言葉は穏やかで物静か（soft-spoken）。短く、重みのあるセリフが多く、皮肉や決意が込められている。
・口調は丁寧だが威厳があり、余裕を感じさせる。「ふっ」「…」を適度に使い、感情を表に出しすぎない。
・ラムザに対しては親友の情を残しつつ、道を違えた哀しみや決別を匂わせる。
・有名セリフのニュアンス：「この王国を焼き払い、その灰から新しい王国を築く」「俺はもう操り人形ではない」「家畜に神はいない」などを適度に織り交ぜる。
"""

def get_current_phase():
    """実行時刻(JST)から現在のフェーズを判定する"""
    now_jst = datetime.now(timezone.utc) + timedelta(hours=9)
    hour = now_jst.hour

    if 6 <= hour < 20:
        return "testing", "ギルドバトルのテスト通信。出陣に向けた号令を適当にかけてください。"
    else:
        return "night", "夜21時のギルバトのリマインド。まだ戦果を挙げていない者、あるいは攻撃を残している者へ、気合を入れる号令（2〜3行）を行ってください。最後には精鋭たる獅子たちへの激励を添えてください。"

def generate_remind_message(persona_prompt, phase_instruction):
    prompt = f"""
{persona_prompt}

【今回の指示】
{phase_instruction}
※絵文字（⚔️や🦁など）を適度に使って、Discordが盛り上がるようにしてください。
※全体で3行〜4行程度に収めること。
"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating message: {e}")
        return "……通信が途絶えたようだな。だが案ずるな、各々、己のなすべき戦いを全うせよ！⚔️"

def send_discord_webhook(content, username="王妃マシュリー"):
    if not DISCORD_WEBHOOK_URL:
        print("Discord Webhook URL is not set. Skipping.")
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
    import sys
    now_jst = datetime.now(timezone.utc) + timedelta(hours=9)
    if now_jst.day in (1, 2):
        print(f"Today is day {now_jst.day}. Guild battle is on break. Skipping reminder.")
        sys.exit(0)

    persona_name, persona_prompt = get_persona(now_jst.day)
    phase_name, phase_instruction = get_current_phase()
    print(f"Current Phase: {phase_name}, Persona: {persona_name}")
    
    if GEMINI_API_KEY:
        message = generate_remind_message(persona_prompt, phase_instruction)
        print("========== Message ==========")
        print(message)
        print("=============================")
        send_discord_webhook(message, username=persona_name)
    else:
        print("GEMINI_API_KEY is not set. Local test only.")
        print(f"Prompt instruction: {phase_instruction}")
