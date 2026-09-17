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

client = OpenAI(api_key=OPENAI_API_KEY)


# ==========================================
# 1. AIが検索キーワードを決める
# ==========================================

def create_keyword():

    prompt = """
あなたは楽天市場の商品をXで紹介する
アフィリエイト商品リサーチ担当です。

楽天市場で検索する商品キーワードを1つだけ決めてください。

目的：
Xで思わずクリックしたくなる商品を見つけること。

条件：
・SNSで紹介しやすい
・商品画像だけでも特徴が伝わりやすい
・実用性、便利グッズ、食品、生活用品、ガジェットなど
・極端に高額ではない
・検索結果が十分ありそう
・季節需要や話題性も考慮する
・毎回できるだけ違うジャンルを考える

例：
モバイルバッテリー
防災グッズ
便利グッズ
お取り寄せグルメ
キッチングッズ

キーワードだけを返してください。
説明は不要です。
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    keyword = response.output_text.strip()
    keyword = keyword.replace('"', '').replace("'", "")
    keyword = keyword.splitlines()[0].strip()

    return keyword


# ==========================================
# 2. 楽天市場から商品を取得
# ==========================================

def get_rakuten_items(keyword, hits=20):

    url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"

    params = {
        "applicationId": RAKUTEN_APPLICATION_ID,
        "accessKey": RAKUTEN_ACCESS_KEY,
        "affiliateId": RAKUTEN_AFFILIATE_ID,
        "keyword": keyword,
        "hits": hits,
        "format": "json",
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

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


# ==========================================
# 3. AIが一番紹介しやすい商品を選ぶ
# ==========================================

def select_product(items):

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
あなたは楽天市場の商品をXで紹介する
アフィリエイト商品選定担当です。

次の商品候補から、
Xで紹介する商品を1つ選んでください。

商品候補：
{json.dumps(products, ensure_ascii=False)}

重視するポイント：
・商品名だけでも特徴が伝わる
・価格と商品の魅力のバランス
・レビュー評価
・レビュー件数
・SNSで紹介しやすい特徴
・「便利そう」「欲しい」と思われやすい
・ありふれた商品でも、明確な訴求ポイントがある

注意：
実際に使用した、購入した、愛用している等の
事実ではない表現は禁止です。
過度な誇張表現も禁止です。

必ず次のJSON形式だけで返してください。

{{
  "product_number": 1,
  "reason": "選定理由",
  "post": "X投稿文"
}}

X投稿文の条件：
・自然な日本語
・広告っぽくなりすぎない
・商品の具体的なメリットを入れる
・短く読みやすい
・URLは文章に入れない
・最後に #PR を入れる
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    text = response.output_text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)


# ==========================================
# 4. 実行
# ==========================================

print()
print("AIが検索テーマを考えています...")
print()

keyword = create_keyword()

print(f"AIが選んだ検索キーワード：{keyword}")
print()
print("楽天市場から商品を探しています...")
print()

items = get_rakuten_items(keyword)

if not items:
    print("商品が見つかりませんでした。")
    raise SystemExit

print(f"{len(items)}件の商品を取得しました。")
print("AIが商品を分析しています...")
print()

result = select_product(items)

product_number = int(result["product_number"])

if product_number < 1 or product_number > len(items):
    raise ValueError("AIが不正な商品番号を返しました。")

selected = items[product_number - 1]

print("=" * 50)
print("AI 商品選定結果")
print("=" * 50)

print()
print(f"検索キーワード：{keyword}")

print()
print("商品名：")
print(selected["name"])

print()
print(f"価格：{selected['price']}円")

print(
    f"レビュー：{selected['review_average']} "
    f"（{selected['review_count']}件）"
)

print()
print("選定理由：")
print(result["reason"])

print()
print("=" * 50)
print("X投稿用 完成文章")
print("=" * 50)

print()
print(result["post"])

print()
print(selected["affiliate_url"])

print()
print("=" * 50)
