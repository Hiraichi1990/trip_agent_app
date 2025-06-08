from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import UserProxyAgent
from autogen_core.tools import FunctionTool
from yahooquery import Ticker
import os
import getpass
import asyncio
import boto3, streamlit as st

# 環境変数の読み込み
from dotenv import load_dotenv
load_dotenv()

# セッションステートの初期化
if "messages" not in st.session_state:
    # チャット履歴
    st.session_state.messages = []
if "response_buffer" not in st.session_state:
    # 応答途中のバッファ
    st.session_state.response_buffer = ""

api_key = os.environ["OPENAI_API_KEY"]
model_client = OpenAIChatCompletionClient(model = os.environ["OPENAI_API_MODEL"])

def get_exchange_rate(currency_code: str) -> dict:
    '''
    指定した国の通貨と日本円（JPY）の為替レートを取得する。

    Args:
        currency_code (str): 通貨コード（例: "USD", "EUR", "GBP"）

    Returns:
        dict: 為替レート情報（通貨ペア、レート、取得時間）
    '''
    symbol = f"{currency_code}JPY=X" # 例: "USDJPY=x"
    ticker = Ticker(symbol)
    data = ticker.price[symbol]

    if "regularMarketPrice" in data:
        return {
            "currency_pair": f"{currency_code}/JPY",
            "exchange_rate": data["regularMarketPrice"],
            "timestamp": data["regularMarketTime"]
        }
    else:
        return {"error": "為替レートが取得できませんでした。"}

# rate_info = get_exchange_rate("USD") # USD/JPYのレート取得
# print(rate_info)

# Function Callingとして定義
get_exchange_rate_tool = FunctionTool(
    get_exchange_rate, description = "現在の為替レートを取得します。"
)

# 予定の全体をプランするエージェントplanner_agentを定義
planner_agent = AssistantAgent(
    "planner_agent",
    model_client,
    description = "現地のアクティビティや訪問先を提案できる現地アシスタント",
    system_message = "あなたは、ユーザーのリクエストに基づいて旅行プランを提案できる便利なアシスタントです。",
)

# 訪問先の観光地やアクティビティを提案するエージェントlocal_agentを定義
local_agent = AssistantAgent(
    "local_agent",
    model_client,
    description = "現地のアクティビティや訪問先を提案できる地元アシスタント",
    system_message = "あなたは、本物で興味深い現地のアクティビティや訪問する場所をユーザーに提案し、提案されたコンテキスト情報を利用できる便利なアシスタントです。",
)

# 訪問先の公用語について教えてくれるエージェントlanguage_agentを定義
language_agent = AssistantAgent(
    "language_agent",
    model_client,
    description = "特定の目的地に関する言語のヒントを提供できる便利なアシスタント",
    system_message = "あなたは、旅行計画を検討し、特定の目的地での公用語やコミュニケーションの課題に対処する最善の方法に関する重要なヒントについてフィードバックを提供できる便利なアシスタントです。計画に言語に関するヒントがすでに含まれている場合は、その計画が満足のいくものであることを根拠を添えて言及できます。",
)

exchange_agent = AssistantAgent(
    "exchange_agent",
    model_client,
    description = "訪問先での通貨に関する情報を提供できる便利なアシスタント",
    system_message = "あなたは、旅行計画の中にある訪問先での通貨と日本円の為替レートをget_exchange_rate_toolを使って提供できる便利なアシスタントです。",
    tools = [get_exchange_rate_tool]
)

# 上記のエージェントの提案をサマリーし最終的な旅程を提案するエージェントtravel_summary_agentを定義
travel_summary_agent = AssistantAgent(
    "travel_summary_agent",
    model_client,
    description = "旅行計画をまとめるのに役立つアシスタント",
    system_message = "あなたは、他のエージェントからの提案やアドバイスをすべて取り入れ、詳細な最終的な旅行計画を提供できる、役に立つアシスタントです。最終計画が統合され、完全であることを確認する必要があります。最終的な対応は完全な計画でなければなりません。計画が完了し、すべてのパースペクティブが統合されたら、TERMINATE で応答できます。",
)

# グループチャットの最後に必ずこのUserProxyAgentに処理が渡されユーザーの入力を求める
user_proxy = UserProxyAgent("user_proxy", input_func=input)

# エージェントの処理が終了した際のキーワードを設定
termination = TextMentionTermination("APPROVE")

st.title("TripAgent")
chat_placeholder = st.empty()
output_lines = []

async def send_request(task):
    '''
    各メッセージの後に次のエージェントを選択し、順番にメッセージを送信する
    プロンプトを設定し、旅程のリクエスト
'''
    group_chat = RoundRobinGroupChat(
        [planner_agent, local_agent, language_agent, exchange_agent, travel_summary_agent],
        termination_condition = termination,
        max_turns = 10 # 最大10ターンで終了
    )

    # Autogenからのstreamを順次取得
    async for msg in group_chat.run_stream(task = task):
        # リアルタイム更新
        with st.chat_message("assistant"):
            st.text(msg.content)
            await asyncio.sleep(0.05)
            break

# 入力フォーム、実行ボタンを設定
task = st.text_input("旅のプランを入力してください。")
button = st.button("質問する")

if button:
    # 非同期ラッパー
    asyncio.run(send_request(task))