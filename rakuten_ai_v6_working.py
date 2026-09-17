import os
import json
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
# 1. AIが5つの検索キーワードを作成
# ==========================================

def create_keywords():

    prompt = """
あなたは楽天市場の商品発掘を担当する
アフィリエイト商品の専門リサーチャーです。

X（旧Twitter）で紹介したときに、
思わずクリックして商品ページを見たくなる商品を発見するため、
楽天市場で検索するキーワードを5つ考えてください。

条件：
・5つはできるだけ違うジャンルにする
・便利グッズ
・食品、飲料
・生活用品
・ガジェット
・季節商品
・プレゼント向け
・趣味用品
など幅広く考える

特に、
「これ何？」
「こんなのあるんだ」
「ちょっと欲しい」
と思わせる商品が見つかりやすいキーワードを優先してください。

検索キーワードだけをJSONで返してください。

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

    return data["keywords"]


# ==========================================
# 2. 楽天市場から商品取得
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
            "affiliate_url": item.get("affiliateUrl", ""),
            "item_url": item.get("itemUrl", ""),
            "shop_name": item.get("shopName", ""),
            "keyword": keyword
        })

    return items


# ==========================================
# 3. 重複商品を削除
# ==========================================

def remove_duplicates(items):

    unique = []
    seen = set()

    for item in items:

        key = item["item_url"] or item["name"]

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


# ==========================================
# 4. 数値条件で候補を20商品に絞る
# ==========================================

def prefilter_items(items, limit=20):

    def base_score(item):

        review = float(item["review_average"] or 0)
        count = int(item["review_count"] or 0)
        price = int(item["price"] or 0)

        score = 0

        # レビュー評価：最大50点
        score += min(review, 5.0) * 10

        # レビュー件数：最大30点
        # 極端にレビュー数が多い商品だけが有利になりすぎないようにする
        if count >= 1000:
            score += 30
        elif count >= 500:
            score += 27
        elif count >= 200:
            score += 24
        elif count >= 100:
            score += 21
        elif count >= 50:
            score += 18
        elif count >= 20:
            score += 14
        elif count >= 10:
            score += 10
        elif count >= 1:
            score += 5

        # 買いやすい価格帯：最大20点
        if 1000 <= price <= 5000:
            score += 20
        elif 5000 < price <= 10000:
            score += 17
        elif 10000 < price <= 20000:
            score += 12
        elif 20000 < price <= 30000:
            score += 8
        elif 500 <= price < 1000:
            score += 10

        return score

    # 検索キーワードごとに商品を分ける
    groups = {}

    for item in items:
        keyword = item["keyword"]

        if keyword not in groups:
            groups[keyword] = []

        groups[keyword].append(item)

    candidates = []

    # 各検索ジャンルから上位商品を均等に残す
    per_keyword = max(1, limit // max(1, len(groups)))

    for keyword, group_items in groups.items():

        ranked = sorted(
            group_items,
            key=base_score,
            reverse=True
        )

        candidates.extend(ranked[:per_keyword])

    # 20件に満たない場合は、残りの商品から補充
    if len(candidates) < limit:

        selected_urls = {
            item["item_url"] or item["name"]
            for item in candidates
        }

        remaining = [
            item for item in items
            if (item["item_url"] or item["name"]) not in selected_urls
        ]

        remaining = sorted(
            remaining,
            key=base_score,
            reverse=True
        )

        candidates.extend(
            remaining[:limit - len(candidates)]
        )

    # 最後にスコア順で並べる
    candidates = sorted(
        candidates,
        key=base_score,
        reverse=True
    )

    return candidates[:limit]


# ==========================================
# 5. AIが20商品を比較してTOP5を作成
# ==========================================

def evaluate_top5(items):

    products = []

    for i, item in enumerate(items, 1):

        products.append({
            "number": i,
            "name": item["name"],
            "price": item["price"],
            "review_average": item["review_average"],
            "review_count": item["review_count"],
            "search_keyword": item["keyword"]
        })

    prompt = """
あなたはSNSアフィリエイトの商品選定担当者です。

以下は楽天市場から取得し、
レビュー等の数値条件で事前に絞った商品候補です。

候補商品：
{json.dumps(products, ensure_ascii=False)}

この中からX（旧Twitter）で紹介した場合に
販売につながる可能性が比較的高いと考えられる商品を
5商品選んでください。

ただし、実際の販売数や将来の売上を知ることはできません。
ここでの点数は候補商品を比較するための
「販売期待スコア」としてください。

以下の5項目をそれぞれ20点満点で評価してください。

1. click_score
クリックされやすさ。
商品名や特徴を見て興味を持ちやすいか。

2. interesting_score
面白さ・意外性。
「こんなのあるんだ」と思わせやすいか。

3. buy_score
買いやすさ。
価格・用途・衝動購入との相性を考える。

4. trust_score
信頼性。
レビュー評価・レビュー件数などを考える。

5. sns_score
SNS紹介適性。
短い投稿でも魅力を伝えやすいか。

5項目の合計をtotal_scoreとして100点満点にしてください。

重要：
・同じ商品を重複して選ばない
・TOP5は原則として異なるsearch_keywordの商品を1商品ずつ選ぶ
・同じsearch_keywordから複数商品を選ばない
・5種類のsearch_keywordが候補に存在する場合は、必ず5種類すべてから1商品ずつ選ぶ
・必ず候補商品のnumberを使用する
・total_scoreは5項目の合計と完全に一致させる
・点数が高い順に5商品並べる
・レビュー件数だけで順位を決めない
・価格が安いだけで順位を決めない
・Xで紹介する意味がある商品を重視する
・reasonは日本語で簡潔に書く

必ず次のJSON形式だけで返してください。

{
  "top5": [
    {
      "product_number": 1,
      "total_score": 88,
      "click_score": 18,
      "interesting_score": 18,
      "buy_score": 17,
      "trust_score": 18,
      "sns_score": 17,
      "reason": "選定理由"
    },
    {
      "product_number": 2,
      "total_score": 85,
      "click_score": 17,
      "interesting_score": 17,
      "buy_score": 17,
      "trust_score": 18,
      "sns_score": 16,
      "reason": "選定理由"
    },
    {
      "product_number": 3,
      "total_score": 82,
      "click_score": 17,
      "interesting_score": 16,
      "buy_score": 16,
      "trust_score": 17,
      "sns_score": 16,
      "reason": "選定理由"
    },
    {
      "product_number": 4,
      "total_score": 79,
      "click_score": 16,
      "interesting_score": 16,
      "buy_score": 15,
      "trust_score": 17,
      "sns_score": 15,
      "reason": "選定理由"
    },
    {
      "product_number": 5,
      "total_score": 76,
      "click_score": 15,
      "interesting_score": 15,
      "buy_score": 15,
      "trust_score": 16,
      "sns_score": 15,
      "reason": "選定理由"
    }
  ]
}
"""

    prompt = prompt.replace("{json.dumps(products, ensure_ascii=False)}", json.dumps(products, ensure_ascii=False))
    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    text = response.output_text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    data = json.loads(text)

    top5 = data["top5"]

    # 念のためPython側でも点数を再計算
    for result in top5:

        result["total_score"] = (
            int(result["click_score"])
            + int(result["interesting_score"])
            + int(result["buy_score"])
            + int(result["trust_score"])
            + int(result["sns_score"])
        )

    # Python側でも高得点順に並べる
    top5 = sorted(
        top5,
        key=lambda x: x["total_score"],
        reverse=True
    )

    return top5


# ==========================================
# 6. X投稿文を生成
# ==========================================

def create_x_post(item):

    prompt = f"""
あなたはX向けの商品紹介文を書くコピーライターです。

以下の商品を紹介するX投稿文を作成してください。

商品名：
{item["name"]}

価格：
{item["price"]}円

レビュー：
{item["review_average"]} / 5

レビュー件数：
{item["review_count"]}件

条件：
・広告っぽすぎない
・冒頭で興味を引く
・商品の魅力がすぐ分かる
・短く読みやすくする
・実際に購入・使用したような表現は禁止
・確認できない性能や効果を断定しない
・最後に #PR を入れる
・URLは本文に入れない

投稿文だけ返してください。
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text.strip()


# ==========================================
# メイン処理
# ==========================================

def main():

    print("\nAIが商品発掘テーマを考えています...\n")

    keywords = create_keywords()

    print("今回の検索キーワード")
    print("--------------------------------")

    for keyword in keywords:
        print("・", keyword)

    print("\n楽天市場を横断検索しています...\n")

    all_items = []

    for keyword in keywords:

        try:
            items = get_rakuten_items(keyword, hits=30)
            all_items.extend(items)

            print(f"検索中：{keyword}")
            print(f"  → {len(items)}件取得")

            time.sleep(1)

        except Exception as e:
            print(f"検索エラー：{keyword}")
            print(e)

    items = remove_duplicates(all_items)

    print(f"\n重複整理後：{len(items)}商品")

    if not items:
        print("商品が見つかりませんでした。")
        return

    candidates = prefilter_items(items, limit=20)

    print(f"有力候補：{len(candidates)}商品")
    print("AIが候補商品を比較し、TOP5を作成しています...\n")

    top5 = evaluate_top5(candidates)

    print("========================================")
    print("       販売期待スコア TOP5")
    print("========================================")

    valid_results = []

    for result in top5:

        product_number = int(result["product_number"])

        if product_number < 1 or product_number > len(candidates):
            continue

        item = candidates[product_number - 1]
        valid_results.append((result, item))

    if not valid_results:
        raise ValueError("AIが有効な商品番号を返しませんでした。")

    for rank, (result, item) in enumerate(valid_results, 1):

        print(f"\n【第{rank}位】")
        print(f"販売期待スコア：{result['total_score']} / 100")
        print(f"検索ジャンル：{item['keyword']}")
        print("商品名：")
        print(item["name"])
        print(f"価格：{item['price']}円")
        print(
            f"レビュー：{item['review_average']} "
            f"（{item['review_count']}件）"
        )

        print(
            "内訳："
            f"クリック{result['click_score']} / "
            f"面白さ{result['interesting_score']} / "
            f"買いやすさ{result['buy_score']} / "
            f"信頼性{result['trust_score']} / "
            f"SNS適性{result['sns_score']}"
        )

        print("理由：")
        print(result["reason"])

        print("----------------------------------------")

    # TOP1の商品でX投稿文を作成
    best_result, selected = valid_results[0]

    print("\n第1位の商品でX投稿文を作成しています...\n")

    post = create_x_post(selected)

    print("========================================")
    print("        X投稿用 完成文章")
    print("========================================\n")

    print(post)

    print("\n価格：", selected["price"], "円")
    print(
        "レビュー：",
        selected["review_average"],
        f"（{selected['review_count']}件）"
    )

    print("\n楽天アフィリエイトURL：")
    print(selected["affiliate_url"])

    print("\n========================================")
    print("※販売期待スコアは実際の売上・販売確率ではなく、")
    print("  楽天APIの取得情報とAI評価による候補比較用の指標です。")
    print("========================================")


if __name__ == "__main__":
    main()
