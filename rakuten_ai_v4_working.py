import os
import json
import math
import time
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
# 1. AIが5つの検索キーワードを作る
# ==========================================

def create_keywords():

    prompt = """
あなたは楽天市場の商品をXで紹介する
アフィリエイト商品の発掘担当です。

Xで紹介したときに興味を持たれやすい商品を探すため、
楽天市場で使う検索キーワードを5つ考えてください。

重要：
5つはできるだけ違うジャンルにしてください。

候補ジャンル：
・便利グッズ
・生活用品
・食品、お取り寄せ
・ガジェット
・旅行用品
・防災用品
・キッチン用品
・季節商品
・デスク周り
・収納
・健康、リラックス用品
・プレゼント向け商品

選定条件：
・商品画像だけでも特徴が伝わりやすい
・Xで短く魅力を説明できる
・「これ何？」「ちょっと欲しい」が生まれやすい
・悩みや不便の解決につながる
・極端に高額な商品に偏らない
・ありきたりな商品だけに偏らない
・季節性も考慮する

楽天市場で実際に検索できそうな
具体的なキーワードにしてください。

JSONだけで返してください。

形式：
{
  "keywords": [
    "キーワード1",
    "キーワード2",
    "キーワード3",
    "キーワード4",
    "キーワード5"
  ]
}
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    text = response.output_text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    data = json.loads(text)

    return data["keywords"][:5]


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
        "format": "json"
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    items = []

    for entry in data.get("Items", []):
        item = entry.get("Item", entry)

        items.append({
            "keyword": keyword,
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
# 3. 同じ商品をある程度除外
# ==========================================

def remove_duplicates(items):

    unique = []
    seen = set()

    for item in items:

        key = (
            item["name"][:60],
            item["price"]
        )

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


# ==========================================
# 4. 数値データで候補を絞る
# ==========================================

def preliminary_score(item):

    try:
        rating = float(item["review_average"] or 0)
    except:
        rating = 0

    try:
        reviews = int(item["review_count"] or 0)
    except:
        reviews = 0

    try:
        price = int(item["price"] or 0)
    except:
        price = 0

    score = 0

    # レビュー評価
    if rating >= 4.7:
        score += 25
    elif rating >= 4.5:
        score += 20
    elif rating >= 4.3:
        score += 15
    elif rating >= 4.0:
        score += 8

    # レビュー件数
    score += min(math.log10(reviews + 1) * 10, 30)

    # Xアフィリエイトで扱いやすい価格帯
    if 1000 <= price <= 10000:
        score += 20
    elif 500 <= price < 1000:
        score += 12
    elif 10000 < price <= 30000:
        score += 10

    # アフィリエイトURLがある
    if item["affiliate_url"]:
        score += 5

    return score


# ==========================================
# 5. AIが最終商品を選定
# ==========================================

def select_product(items):

    ranked = sorted(
        items,
        key=preliminary_score,
        reverse=True
    )

    # 100商品全部をAIへ渡さず上位30商品に絞る
    candidates = ranked[:30]

    products = []

    for i, item in enumerate(candidates, 1):

        products.append({
            "number": i,
            "search_keyword": item["keyword"],
            "name": item["name"],
            "price": item["price"],
            "review_average": item["review_average"],
            "review_count": item["review_count"],
            "catchcopy": item["catchcopy"]
        })

    prompt = f"""
あなたはSNSアフィリエイトの商品発掘担当です。

楽天市場から複数ジャンルの商品を集めました。

以下の候補から、
Xで紹介した場合に興味を持たれ、
クリックや購入につながる可能性がある商品を
1つ選んでください。

重要：
レビュー件数が最大という理由だけで
商品を選んではいけません。

評価ポイント：

・商品を見た瞬間に内容が分かる
・「これ欲しい」と感じる理由がある
・悩みや不便を解決する
・SNSで説明しやすい
・意外性や面白さがある
・価格と商品の魅力のバランス
・レビュー評価の信頼性
・レビュー件数
・季節との相性
・プレゼント需要
・衝動買いしやすさ
・他の商品との差別化
・Xで話題の入口を作りやすい

単なる人気商品ではなく、
「SNSで紹介する価値」を重視してください。

候補：
{json.dumps(products, ensure_ascii=False)}

JSONだけで回答してください。

形式：
{{
  "product_number": 1,
  "reason": "この商品を選んだ具体的な理由"
}}
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    text = response.output_text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    result = json.loads(text)

    number = int(result["product_number"])

    if number < 1 or number > len(candidates):
        raise ValueError("AIが不正な商品番号を返しました。")

    return candidates[number - 1], result["reason"]


# ==========================================
# 6. X投稿文を作成
# ==========================================

def create_x_post(item):

    prompt = f"""
あなたはXの商品紹介投稿を作るコピーライターです。

次の商品について、
思わず詳細を見たくなる紹介文を作ってください。

商品名：
{item["name"]}

価格：
{item["price"]}円

レビュー：
{item["review_average"]} / 5

レビュー件数：
{item["review_count"]}件

商品情報：
{item["catchcopy"]}

条件：
・日本語
・冒頭で興味を引く
・商品の特徴を短く分かりやすく
・広告文のように煽りすぎない
・実際に購入、使用したとは書かない
・根拠のない効果を断定しない
・価格やレビューなど提供された情報以外を捏造しない
・読みやすく改行する
・絵文字は必要最小限
・URLは入れない
・最後に #PR を入れる

投稿文だけを返してください。
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text.strip()


# ==========================================
# 7. メイン処理
# ==========================================

print()
print("AIが商品発掘テーマを考えています...")
print()

keywords = create_keywords()

print("今回の検索キーワード")
print("--------------------------------")

for keyword in keywords:
    print(f"・{keyword}")

print()
print("楽天市場を横断検索しています...")
print()

all_items = []

for keyword in keywords:

    print(f"検索中：{keyword}")

    try:
        items = get_rakuten_items(keyword, hits=20)
        all_items.extend(items)
        print(f"  → {len(items)}件取得")

    except Exception as e:
        print(f"  → 取得失敗：{e}")

    # APIへの連続アクセスを少し空ける
    time.sleep(1.1)


all_items = remove_duplicates(all_items)

print()
print(f"重複整理後：{len(all_items)}商品")
print()

if not all_items:
    raise SystemExit("商品を取得できませんでした。")


print("有力候補を絞り込み、AIが比較しています...")
print()

selected, reason = select_product(all_items)


print("========================================")
print("        AI 最終選定商品")
print("========================================")
print()
print(f"検索ジャンル：{selected['keyword']}")
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
print("AI選定理由：")
print(reason)


print()
print("X投稿文を作成しています...")
print()

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
