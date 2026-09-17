import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

RAKUTEN_APPLICATION_ID = os.getenv("RAKUTEN_APPLICATION_ID")
RAKUTEN_ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY")
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([
    RAKUTEN_APPLICATION_ID,
    RAKUTEN_ACCESS_KEY,
    RAKUTEN_AFFILIATE_ID,
    OPENAI_API_KEY
]):
    raise ValueError("認証情報を.envから読み込めません。")


def get_rakuten_items(keyword, hits=10):
    url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"

    params = {
        "applicationId": RAKUTEN_APPLICATION_ID,
        "accessKey": RAKUTEN_ACCESS_KEY,
        "affiliateId": RAKUTEN_AFFILIATE_ID,
        "keyword": keyword,
        "hits": hits,
        "format": "json",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    items = []

    for entry in data.get("Items", []):
        item = entry.get("Item", entry)

        items.append({
            "name": item.get("itemName", ""),
            "price": item.get("itemPrice", 0),
            "review_average": item.get("reviewAverage", 0),
            "review_count": item.get("reviewCount", 0),
            "affiliate_url": item.get("affiliateUrl", ""),
        })

    return items


def select_product(items):
    client = OpenAI(api_key=OPENAI_API_KEY)

    products = []

    for i, item in enumerate(items, 1):
        products.append({
            "number": i,
            "name": item["name"],
            "price": item["price"],
            "review_average": item["review_average"],
            "review_count": item["review_count"],
        })

    prompt = f"""
あなたは楽天市場の商品をXで紹介する商品選定アシスタントです。

以下の候補から、Xで紹介する商品を1つ選んでください。

評価基準：
・興味を持たれやすい
・価格と商品の魅力のバランス
・レビュー評価
・レビュー件数
・SNSで紹介しやすい特徴がある

実際に使用した、購入した、愛用している等の
事実ではない表現は禁止です。
過度な誇張も禁止です。

候補商品：
{json.dumps(products, ensure_ascii=False)}

必ず次のJSON形式だけで回答してください。

{{
  "product_number": 1,
  "reason": "選定理由",
  "post": "X投稿文"
}}

投稿文にはURLを入れないでください。
投稿文には#PRを入れてください。
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    text = response.output_text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


keyword = input("検索したい商品キーワードを入力してください: ")

print("\n楽天市場から商品を探しています...\n")

items = get_rakuten_items(keyword)

if not items:
    print("商品が見つかりませんでした。")
    raise SystemExit

print(f"{len(items)}件の商品を取得しました。")
print("AIが商品を分析しています...\n")

result = select_product(items)

product_number = int(result["product_number"])

if product_number < 1 or product_number > len(items):
    raise ValueError("AIが不正な商品番号を返しました。")

selected = items[product_number - 1]

print("====================================")
print("       AI 商品選定結果")
print("====================================")
print()
print("商品名:")
print(selected["name"])
print()
print(f"価格: {selected['price']}円")
print(
    f"レビュー: {selected['review_average']} "
    f"（{selected['review_count']}件）"
)
print()
print("選定理由:")
print(result["reason"])

print()
print("====================================")
print("       X 投稿用 完成文章")
print("====================================")
print()
print(result["post"])
print()
print(selected["affiliate_url"])
print()
print("====================================")
