import os
import requests
from dotenv import load_dotenv

# .envから認証情報を読み込む
load_dotenv()

application_id = os.getenv("RAKUTEN_APPLICATION_ID")
access_key = os.getenv("RAKUTEN_ACCESS_KEY")
affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID")

if not application_id or not access_key:
    raise ValueError("楽天APIの認証情報が.envから読み込めません。")

# 楽天市場 商品検索API
url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"

params = {
    "applicationId": application_id,
    "accessKey": access_key,
    "keyword": "モバイルバッテリー",
    "hits": 3,
    "format": "json",
}

if affiliate_id:
    params["affiliateId"] = affiliate_id

response = requests.get(url, params=params, timeout=20)

print("HTTP STATUS:", response.status_code)

if response.status_code != 200:
    print(response.text)
    raise SystemExit

data = response.json()

for i, entry in enumerate(data.get("Items", []), 1):
    item = entry.get("Item", entry)

    print("\n--------------------")
    print(f"商品 {i}")
    print("商品名:", item.get("itemName"))
    print("価格:", item.get("itemPrice"), "円")
    print("レビュー:", item.get("reviewAverage"))
    print("レビュー件数:", item.get("reviewCount"))
    print("商品URL:", item.get("itemUrl"))
    print("アフィリエイトURL:", item.get("affiliateUrl"))
