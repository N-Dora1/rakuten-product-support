import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEYが.envから読み込めません。")

client = OpenAI(api_key=api_key)

response = client.responses.create(
    model="gpt-5-mini",
    input="接続テストです。「OpenAI API接続成功」とだけ答えてください。"
)

print(response.output_text)
