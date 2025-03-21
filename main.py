from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
import os
import getpass
import asyncio

# 環境変数の読み込み
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ["OPENAI_API_KEY"]

model_client = OpenAIChatCompletionClient(model = os.environ["OPENAI_API_MODEL"])
# 一つ目のエージェント：予定の全体をプランするエージェントplanner_agentを定義
planner_agent = AssistantAgent(
    "planner_agent",
    model_client,
    description = "現地のアクティビティや訪問先を提案できる現地アシスタント",
    system_message = "あなたは、ユーザーのリクエストに基づいて旅行プランを提案できる便利なアシスタントです。",
)

# 二つ目のエージェント：訪問先の観光地やアクティビティを提案するエージェントlocal_agentを定義
local_agent = AssistantAgent(
    "local_agent",
    model_client,
    description = "現地のアクティビティや訪問先を提案できる地元アシスタント",
    system_message = "あなたは、本物で興味深い現地のアクティビティや訪問する場所をユーザーに提案し、提案されたコンテキスト情報を利用できる便利なアシスタントです。",
)

# 三つ目のエージェント：訪問先の公用語について教えてくれるエージェントlanguage_agentを定義
language_agent = AssistantAgent(
    "language_agent",
    model_client,
    description = "特定の目的地に関する言語のヒントを提供できる便利なアシスタント",
    system_message = "あなたは、旅行計画を検討し、特定の目的地での公用語やコミュニケーションの課題に対処する最善の方法に関する重要なヒントについてフィードバックを提供できる便利なアシスタントです。計画に言語に関するヒントがすでに含まれている場合は、その計画が満足のいくものであることを根拠を添えて言及できます。",
)

# 四つ目のエージェント：上記３つのエージェントの提案をサマリーし最終的な旅程を提案するエージェントtravel_summary_agentを定義
travel_summary_agent = AssistantAgent(
    "travel_summary_agent",
    model_client,
    description = "旅行計画をまとめるのに役立つアシスタント",
    system_message = "あなたは、他のエージェントからの提案やアドバイスをすべて取り入れ、詳細な最終的な旅行計画を提供できる、役に立つアシスタントです。最終計画が統合され、完全であることを確認する必要があります。最終的な対応は完全な計画でなければなりません。計画が完了し、すべてのパースペクティブが統合されたら、TERMINATE で応答できます。",
)

# エージェントの出力に TERMINATE という文字が入っている場合に会話終了
termination = TextMentionTermination("TERMINATE")

# 各メッセージの後に次のエージェントを選択し、順番にメッセージを送信する
async def SendRequest():
    group_chat = RoundRobinGroupChat(
        [planner_agent, local_agent, language_agent, travel_summary_agent],
        termination_condition = termination,
        max_turns = 10 # 最大10ターンで終了
    )

    # プロンプトを設定し、旅程のリクエスト
    await Console(group_chat.run_stream(task="ハワイへの3日間の旅行を計画してください。"))

asyncio.run(SendRequest())
