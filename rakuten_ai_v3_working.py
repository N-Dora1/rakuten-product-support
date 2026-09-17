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
# 1. AIが楽天市場の検索キーワードを決める
# ==========================================

def create_keyword():

    prompt = """
あなたは楽天市場の商品をXで紹介する
アフィリエイト商品の発掘担当です。

楽天市場で検索する商品キーワードを1つだけ決めてください。

目的：
Xで思わずクリックしたくなる商品を発見すること。

条件：
・SNSで紹介しやすい
・商品画像だけでも特徴が伝わりやすい
・実用品、便利グッズ、食品、生活用品、ガジェットなど
・検索結果が十分ありそう
・季節需要や話題性も考慮する
・価格が極端に高すぎない
・ありきたりな商品だけに偏らない
・「これ何？」「ちょっと欲しい」と思わせる商品も狙う

例：
モバイルバッテリー
防災グッズ
便利グッズ
お取り寄せグルメ
キッチングッズ
旅行グッズ
デスク周り
収納グッズ

キーワードだけを返してください。
説明は不要です。
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    keyword = response.output_text.strip()
    keyword = keyword.replace("「", "").replace("」", "")
    keyword = keyword.splitlines()[0].strip()

    return keyword


# ==========================================
# 2. 楽天市場から候補商品を取得
# ==========================================

def get_rakuten_items(keyword, hits=30):

    url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"

    params = {
        "applicationId": RAKUTEN_APPLICATION_ID,
        "accessKey": RAKUTEN_ACCESS_KEY,
        "affiliateId": RAKUTEN_AFFILIATE_ID,
        "keyword": keyword,
        "hits": hits,
        "format": "json"
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
            "shop_name": item.get("shopName", ""),
            "catchcopy": item.get("catchcopy", ""),
            "affiliate_url": item.get("affiliateUrl", "")
        })

    return items


# ==========================================
# 3. AIが「Xで売れそうな商品」を選ぶ
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
            "shop_name": item["shop_name"],
            "catchcopy": item["catchcopy"]
        })

    prompt = f"""
あなたはSNSアフィリエイトの商品選定担当です。

以下は楽天市場の商品候補です。

この中から
「Xで紹介したときにクリックされやすく、購入につながる可能性が高い商品」
を1つ選んでください。

単純にレビュー数が最大の商品を選んではいけません。

評価基準：

1. 一瞬で商品の魅力が伝わるか
2. 「これ欲しい」と思わせる要素があるか
3. SNSで話題にしやすいか
4. 価格が衝動買い・比較検討しやすい範囲か
5. レビュー評価とレビュー数に一定の信頼性があるか
6. 悩み・不便を解決する商品か
7. 意外性・新しさ・面白さがあるか
8. Xの短い文章でも魅力を説明できるか

レビュー数が少なくても、
商品自体に強い魅力があれば選んで構いません。

候補商品：
{json.dumps(products, ensure_ascii=False)}

JSONだけで回答してください。

形式：
{{
  "product_number": 1,
  "reason": "選定理由"
}}
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    text = response.output_text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


# ==========================================
# 4. X投稿文をAIが作成
# ==========================================

def create_x_post(item):

    prompt = f"""
あなたはX向けの商品紹介文を作成するコピーライターです。

以下の商品を紹介する投稿文を作ってください。

商品名：
{item["name"]}

価格：
{item["price"]}円

レビュー：
{item["review_average"]} / 5
レビュー件数：
{item["review_count"]}件

キャッチコピー：
{item["catchcopy"]}

条件：
・日本語
・自然で読みやすい
・商品の魅力がすぐ伝わる
・広告っぽすぎる文章にしない
・実際に購入・使用したとは書かない
・根拠のない効果を断定しない
・短くテンポよくする
・絵文字は多用しない
・最後に #PR を入れる
・URLは本文に入れない

投稿文だけを返してください。
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text.strip()


# ==========================================
# 5. メイン処理
# ==========================================

print("AIが検索テーマを考えています...\n")

keyword = create_keyword()

print(f"AIが選んだ検索キーワード：{keyword}\n")
print("楽天市場から商品を探しています...\n")

items = get_rakuten_items(keyword)

if not items:
    raise SystemExit("商品が見つかりませんでした。")

print(f"{len(items)}件の商品を取得しました。")
print("AIが売れそうな商品を分析しています...\n")

result = select_product(items)

product_number = int(result["product_number"])

if product_number < 1 or product_number > len(items):
    raise ValueError("AIが不正な商品番号を返しました。")

selected = items[product_number - 1]

print("========================================")
print("        AI 商品選定結果")
print("========================================")
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
print("X投稿文を作成しています...\n")

post = create_x_post(selected)

print("========================================")
print("        X投稿用 完成文章")
print("========================================")
print()
print(post)
print()
print("楽天アフィリエイトURL：")
print(selected["affiliate_url"])
print()
print("========================================")
