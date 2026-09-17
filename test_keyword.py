import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEYが.envから読み込めません。")

client = OpenAI(api_key=api_key)

prompt = """
あなたは楽天市場の商品発掘アシスタントです。

X（旧Twitter）で楽天アフィリエイト商品を紹介します。
SNSで興味を持たれやすく、購入につながる可能性のある商品を
楽天市場から探すための「検索キーワード」を1つだけ考えてください。

条件：
・具体的な商品カテゴリーにする
・日常生活で使いやすい
・衝動買いしやすい価格帯の商品が多い
・SNSで紹介しやすい
・食品、日用品、便利グッズ、家電、ガジェットなどから選ぶ
・ブランド名は使わない
・検索キーワードだけを出力する
"""

response = client.responses.create(
    model="gpt-5-mini",
    input=prompt
)

keyword = response.output_text.strip()

print("")
print("AIが選んだ検索キーワード")
print("========================")
print(keyword)
print("========================")
