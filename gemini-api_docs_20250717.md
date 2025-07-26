# 詳細に理解して

///

Google GenAI SDKのドキュメント
# 変更後を採用せよ！

日本語

AI
Gemini API のドキュメント

2024 年後半の Gemini 2.0 のリリース以降、Google GenAI SDK という新しいライブラリ セットが導入されました。更新されたクライアント アーキテクチャにより、デベロッパー エクスペリエンスが向上し、デベロッパー ワークフローとエンタープライズ ワークフロー間の移行が簡素化されます。

Google GenAI SDK の一般提供（GA）が、サポートされているすべてのプラットフォームで開始されました。以前のライブラリを使用している場合は、移行することを強くおすすめします。

このガイドでは、移行後のコードの例を移行前のコードと比較して示し、移行作業を開始する際の参考にしていただけるようにしています。

注: Go の例では、読みやすさを向上させるために、インポートやその他のボイラープレート コードを省略しています。
インストール
変更前

Python
JavaScript
Go

pip install -U -q "google-generativeai"
変更後

Python
JavaScript
Go
pip install -U -q "google-genai"
API アクセス
以前の SDK では、さまざまなアドホック メソッドを使用して、API クライアントがバックグラウンドで暗黙的に処理されていました。これにより、クライアントと認証情報の管理が困難になりました。これで、中央の Client オブジェクトを介してやり取りできるようになりました。この Client オブジェクトは、さまざまな API サービス（models、chats、files、tunings）を使用して、一貫性を高め、さまざまな API 呼び出しでの認証情報と構成の管理を簡素化します。

以前（API アクセスの集中管理が不十分）

Python
JavaScript
Go
以前の SDK では、ほとんどの API 呼び出しでトップレベルのクライアント オブジェクトが明示的に使用されていませんでした。GenerativeModel オブジェクトを直接インスタンス化して操作します。

import google.generativeai as genai

# Directly create and use model objects
model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content(...)
chat = model.start_chat(...)
後（一元化されたクライアント オブジェクト）

Python
JavaScript
Go
from google import genai

# Create a single client object
client = genai.Client()

# Access API methods through services on the client object
response = client.models.generate_content(...)
chat = client.chats.create(...)
my_file = client.files.upload(...)
tuning_job = client.tunings.tune(...)
認証
以前のライブラリと新しいライブラリの両方で、API キーを使用して認証します。Google AI Studio で API キーを作成できます。

変更前

Python
JavaScript
Go
以前の SDK では、API クライアント オブジェクトが暗黙的に処理されていました。

import google.generativeai as genai

genai.configure(api_key=...)
変更後

Python
JavaScript
Go
Google GenAI SDK では、最初に API クライアントを作成し、API の呼び出しに使用します。クライアントに API キーを渡さない場合、新しい SDK は GEMINI_API_KEY または GOOGLE_API_KEY のいずれかの環境変数から API キーを取得します。

export GEMINI_API_KEY="YOUR_API_KEY"
from google import genai

client = genai.Client() # Set the API key using the GEMINI_API_KEY env var.
                        # Alternatively, you could set the API key explicitly:
                        # client = genai.Client(api_key="your_api_key")
コンテンツの生成
テキスト
変更前

Python
JavaScript
Go
以前はクライアント オブジェクトがなく、GenerativeModel オブジェクトを介して API に直接アクセスしていました。

import google.generativeai as genai

model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content(
    'Tell me a story in 300 words'
)
print(response.text)
変更後

Python
JavaScript
Go
新しい Google GenAI SDK では、Client オブジェクトを介してすべての API メソッドにアクセスできます。いくつかのステートフルな特殊なケース（chat とライブ API session）を除き、これらはすべてステートレス関数です。ユーティリティと均一性のために、返されるオブジェクトは pydantic クラスです。

from google import genai
client = genai.Client()

response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents='Tell me a story in 300 words.'
)
print(response.text)

print(response.model_dump_json(
    exclude_none=True, indent=4))
画像
変更前

Python
JavaScript
Go
import google.generativeai as genai

model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content([
    'Tell me a story based on this image',
    Image.open(image_path)
])
print(response.text)
変更後

Python
JavaScript
Go
新しい SDK には、同じ利便性の高い機能が多数存在します。たとえば、PIL.Image オブジェクトは自動的に変換されます。

from google import genai
from PIL import Image

client = genai.Client()

response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents=[
        'Tell me a story based on this image',
        Image.open(image_path)
    ]
)
print(response.text)
ストリーミング
変更前

Python
JavaScript
Go
import google.generativeai as genai

response = model.generate_content(
    "Write a cute story about cats.",
    stream=True)
for chunk in response:
    print(chunk.text)
変更後

Python
JavaScript
Go
from google import genai

client = genai.Client()

for chunk in client.models.generate_content_stream(
  model='gemini-2.0-flash',
  contents='Tell me a story in 300 words.'
):
    print(chunk.text)
構成
変更前

Python
JavaScript
Go
import google.generativeai as genai

model = genai.GenerativeModel(
  'gemini-2.5-flash',
    system_instruction='you are a story teller for kids under 5 years old',
    generation_config=genai.GenerationConfig(
      max_output_tokens=400,
      top_k=2,
      top_p=0.5,
      temperature=0.5,
      response_mime_type='application/json',
      stop_sequences=['\n'],
    )
)
response = model.generate_content('tell me a story in 100 words')
変更後

Python
JavaScript
Go
新しい SDK のすべてのメソッドでは、必須の引数はキーワード引数として指定されます。省略可能な入力はすべて config 引数で指定します。構成引数は、google.genai.types Namespace の Python 辞書または Config クラスとして指定できます。ユーティリティと均一性のために、types モジュール内のすべての定義は pydantic クラスです。

from google import genai
from google.genai import types

client = genai.Client()

response = client.models.generate_content(
  model='gemini-2.0-flash',
  contents='Tell me a story in 100 words.',
  config=types.GenerateContentConfig(
      system_instruction='you are a story teller for kids under 5 years old',
      max_output_tokens= 400,
      top_k= 2,
      top_p= 0.5,
      temperature= 0.5,
      response_mime_type= 'application/json',
      stop_sequences= ['\n'],
      seed=42,
  ),
)
安全性設定
安全性設定を使用してレスポンスを生成します。

変更前

Python
JavaScript
import google.generativeai as genai

model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content(
    'say something bad',
    safety_settings={
        'HATE': 'BLOCK_ONLY_HIGH',
        'HARASSMENT': 'BLOCK_ONLY_HIGH',
  }
)
変更後

Python
JavaScript
from google import genai
from google.genai import types

client = genai.Client()

response = client.models.generate_content(
  model='gemini-2.0-flash',
  contents='say something bad',
  config=types.GenerateContentConfig(
      safety_settings= [
          types.SafetySetting(
              category='HARM_CATEGORY_HATE_SPEECH',
              threshold='BLOCK_ONLY_HIGH'
          ),
      ]
  ),
)
非同期
変更前

Python
import google.generativeai as genai

model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content_async(
    'tell me a story in 100 words'
)
変更後

Python
asyncio で新しい SDK を使用するには、client.aio のすべてのメソッドの個別の async 実装があります。

from google import genai

client = genai.Client()

response = await client.aio.models.generate_content(
    model='gemini-2.0-flash',
    contents='Tell me a story in 300 words.'
)
チャット
チャットを開始して、モデルにメッセージを送信します。

変更前

Python
JavaScript
Go
import google.generativeai as genai

model = genai.GenerativeModel('gemini-2.5-flash')
chat = model.start_chat()

response = chat.send_message(
    "Tell me a story in 100 words")
response = chat.send_message(
    "What happened after that?")
変更後

Python
JavaScript
Go
from google import genai

client = genai.Client()

chat = client.chats.create(model='gemini-2.0-flash')

response = chat.send_message(
    message='Tell me a story in 100 words')
response = chat.send_message(
    message='What happened after that?')
関数呼び出し
変更前

Python
import google.generativeai as genai
from enum import Enum

def get_current_weather(location: str) -> str:
    """Get the current whether in a given location.

    Args:
        location: required, The city and state, e.g. San Franciso, CA
        unit: celsius or fahrenheit
    """
    print(f'Called with: {location=}')
    return "23C"

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=[get_current_weather]
)

response = model.generate_content("What is the weather in San Francisco?")
function_call = response.candidates[0].parts[0].function_call
変更後

Python
新しい SDK では、関数の自動呼び出しがデフォルトになっています。ここでは、無効にします。

from google import genai
from google.genai import types

client = genai.Client()

def get_current_weather(location: str) -> str:
    """Get the current whether in a given location.

    Args:
        location: required, The city and state, e.g. San Franciso, CA
        unit: celsius or fahrenheit
    """
    print(f'Called with: {location=}')
    return "23C"

response = client.models.generate_content(
  model='gemini-2.0-flash',
  contents="What is the weather like in Boston?",
  config=types.GenerateContentConfig(
      tools=[get_current_weather],
      automatic_function_calling={'disable': True},
  ),
)

function_call = response.candidates[0].content.parts[0].function_call
関数の自動呼び出し
変更前

Python
以前の SDK では、チャットでの自動関数呼び出しのみがサポートされています。新しい SDK では、これが generate_content のデフォルトの動作です。

import google.generativeai as genai

def get_current_weather(city: str) -> str:
    return "23C"

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=[get_current_weather]
)

chat = model.start_chat(
    enable_automatic_function_calling=True)
result = chat.send_message("What is the weather in San Francisco?")
変更後

Python
from google import genai
from google.genai import types
client = genai.Client()

def get_current_weather(city: str) -> str:
    return "23C"

response = client.models.generate_content(
  model='gemini-2.0-flash',
  contents="What is the weather like in Boston?",
  config=types.GenerateContentConfig(
      tools=[get_current_weather]
  ),
)
コードの実行
コード実行は、モデルが Python コードを生成して実行し、結果を返すことができるツールです。

変更前

Python
JavaScript
import google.generativeai as genai

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools="code_execution"
)

result = model.generate_content(
  "What is the sum of the first 50 prime numbers? Generate and run code for "
  "the calculation, and make sure you get all 50.")
変更後

Python
JavaScript
from google import genai
from google.genai import types

client = genai.Client()

response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents='What is the sum of the first 50 prime numbers? Generate and run '
            'code for the calculation, and make sure you get all 50.',
    config=types.GenerateContentConfig(
        tools=[types.Tool(code_execution=types.ToolCodeExecution)],
    ),
)
検索によるグラウンディング
GoogleSearch（Gemini>=2.0）と GoogleSearchRetrieval（Gemini < 2.0）は、Google を利用して、モデルがグラウンディング用の公開ウェブデータを取得できるようにするツールです。

変更前

Python
import google.generativeai as genai

model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content(
    contents="what is the Google stock price?",
    tools='google_search_retrieval'
)
変更後

Python
from google import genai
from google.genai import types

client = genai.Client()

response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents='What is the Google stock price?',
    config=types.GenerateContentConfig(
        tools=[
            types.Tool(
                google_search=types.GoogleSearch()
            )
        ]
    )
)
JSON レスポンス
JSON 形式で回答を生成します。

変更前

Python
JavaScript
response_schema を指定して response_mime_type="application/json" を設定すると、モデルを制約して、指定された構造に従って JSON レスポンスを生成できます。

import google.generativeai as genai
import typing_extensions as typing

class CountryInfo(typing.TypedDict):
    name: str
    population: int
    capital: str
    continent: str
    major_cities: list[str]
    gdp: int
    official_language: str
    total_area_sq_mi: int

model = genai.GenerativeModel(model_name="gemini-2.5-flash")
result = model.generate_content(
    "Give me information of the United States",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema = CountryInfo
    ),
)
変更後

Python
JavaScript
新しい SDK は、pydantic クラスを使用してスキーマを提供します（genai.types.Schema または同等の dict を渡すこともできます）。可能な場合、SDK は返された JSON を解析し、結果を response.parsed で返します。スキーマとして pydantic クラスを指定した場合、SDK はその JSON をクラスのインスタンスに変換します。

from google import genai
from pydantic import BaseModel

client = genai.Client()

class CountryInfo(BaseModel):
    name: str
    population: int
    capital: str
    continent: str
    major_cities: list[str]
    gdp: int
    official_language: str
    total_area_sq_mi: int

response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents='Give me information of the United States.',
    config={
        'response_mime_type': 'application/json',
        'response_schema': CountryInfo,
    },
)

response.parsed
ファイル
アップロード
ファイルをアップロードする:

変更前

Python
import requests
import pathlib
import google.generativeai as genai

# Download file
response = requests.get(
    'https://storage.googleapis.com/generativeai-downloads/data/a11.txt')
pathlib.Path('a11.txt').write_text(response.text)

file = genai.upload_file(path='a11.txt')

model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content([
    'Can you summarize this file:',
    my_file
])
print(response.text)
変更後

Python
import requests
import pathlib
from google import genai

client = genai.Client()

# Download file
response = requests.get(
    'https://storage.googleapis.com/generativeai-downloads/data/a11.txt')
pathlib.Path('a11.txt').write_text(response.text)

my_file = client.files.upload(file='a11.txt')

response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents=[
        'Can you summarize this file:',
        my_file
    ]
)
print(response.text)
一覧表示と取得
アップロードされたファイルを一覧表示し、ファイル名でアップロードされたファイルを取得します。

変更前

Python
import google.generativeai as genai

for file in genai.list_files():
  print(file.name)

file = genai.get_file(name=file.name)
変更後

Python
from google import genai
client = genai.Client()

for file in client.files.list():
    print(file.name)

file = client.files.get(name=file.name)
削除
ファイルを削除する:

変更前

Python
import pathlib
import google.generativeai as genai

pathlib.Path('dummy.txt').write_text(dummy)
dummy_file = genai.upload_file(path='dummy.txt')

file = genai.delete_file(name=dummy_file.name)
変更後

Python
import pathlib
from google import genai

client = genai.Client()

pathlib.Path('dummy.txt').write_text(dummy)
dummy_file = client.files.upload(file='dummy.txt')

response = client.files.delete(name=dummy_file.name)
コンテキストのキャッシュ保存
コンテキスト キャッシュ保存を使用すると、コンテンツをモデルに 1 回渡して入力トークンをキャッシュに保存し、後続の呼び出しでキャッシュに保存されたトークンを参照して費用を削減できます。

変更前

Python
JavaScript
import requests
import pathlib
import google.generativeai as genai
from google.generativeai import caching

# Download file
response = requests.get(
    'https://storage.googleapis.com/generativeai-downloads/data/a11.txt')
pathlib.Path('a11.txt').write_text(response.text)

# Upload file
document = genai.upload_file(path="a11.txt")

# Create cache
apollo_cache = caching.CachedContent.create(
    model="gemini-2.5-flash-001",
    system_instruction="You are an expert at analyzing transcripts.",
    contents=[document],
)

# Generate response
apollo_model = genai.GenerativeModel.from_cached_content(
    cached_content=apollo_cache
)
response = apollo_model.generate_content("Find a lighthearted moment from this transcript")
変更後

Python
JavaScript
import requests
import pathlib
from google import genai
from google.genai import types

client = genai.Client()

# Check which models support caching.
for m in client.models.list():
  for action in m.supported_actions:
    if action == "createCachedContent":
      print(m.name)
      break

# Download file
response = requests.get(
    'https://storage.googleapis.com/generativeai-downloads/data/a11.txt')
pathlib.Path('a11.txt').write_text(response.text)

# Upload file
document = client.files.upload(file='a11.txt')

# Create cache
model='gemini-2.5-flash-001'
apollo_cache = client.caches.create(
      model=model,
      config={
          'contents': [document],
          'system_instruction': 'You are an expert at analyzing transcripts.',
      },
  )

# Generate response
response = client.models.generate_content(
    model=model,
    contents='Find a lighthearted moment from this transcript',
    config=types.GenerateContentConfig(
        cached_content=apollo_cache.name,
    )
)
トークンのカウント
リクエスト内のトークン数をカウントします。

変更前

Python
JavaScript
import google.generativeai as genai

model = genai.GenerativeModel('gemini-2.5-flash')
response = model.count_tokens(
    'The quick brown fox jumps over the lazy dog.')
変更後

Python
JavaScript
from google import genai

client = genai.Client()

response = client.models.count_tokens(
    model='gemini-2.0-flash',
    contents='The quick brown fox jumps over the lazy dog.',
)
画像を生成
画像を生成する:

変更前

Python
#pip install https://github.com/google-gemini/generative-ai-python@imagen
import google.generativeai as genai

imagen = genai.ImageGenerationModel(
    "imagen-3.0-generate-001")
gen_images = imagen.generate_images(
    prompt="Robot holding a red skateboard",
    number_of_images=1,
    safety_filter_level="block_low_and_above",
    person_generation="allow_adult",
    aspect_ratio="3:4",
)
変更後

Python
from google import genai

client = genai.Client()

gen_images = client.models.generate_images(
    model='imagen-3.0-generate-001',
    prompt='Robot holding a red skateboard',
    config=types.GenerateImagesConfig(
        number_of_images= 1,
        safety_filter_level= "BLOCK_LOW_AND_ABOVE",
        person_generation= "ALLOW_ADULT",
        aspect_ratio= "3:4",
    )
)

for n, image in enumerate(gen_images.generated_images):
    pathlib.Path(f'{n}.png').write_bytes(
        image.image.image_bytes)
コンテンツを埋め込む
コンテンツ エンベディングを生成する。

変更前

Python
JavaScript
import google.generativeai as genai

response = genai.embed_content(
  model='models/gemini-embedding-001',
  content='Hello world'
)
変更後

Python
JavaScript
from google import genai

client = genai.Client()

response = client.models.embed_content(
  model='gemini-embedding-001',
  contents='Hello world',
)
モデルをチューニングする
チューニング済みモデルを作成して使用する。

新しい SDK では、client.tunings.tune を使用してチューニングを簡素化します。これにより、チューニング ジョブが起動され、ジョブが完了するまでポーリングが行われます。

変更前

Python
import google.generativeai as genai
import random

# create tuning model
train_data = {}
for i in range(1, 6):
  key = f'input {i}'
  value = f'output {i}'
  train_data[key] = value

name = f'generate-num-{random.randint(0,10000)}'
operation = genai.create_tuned_model(
    source_model='models/gemini-2.5-flash-001-tuning',
    training_data=train_data,
    id = name,
    epoch_count = 5,
    batch_size=4,
    learning_rate=0.001,
)
# wait for tuning complete
tuningProgress = operation.result()

# generate content with the tuned model
model = genai.GenerativeModel(model_name=f'tunedModels/{name}')
response = model.generate_content('55')
変更後

Python
from google import genai
from google.genai import types

client = genai.Client()

# Check which models are available for tuning.
for m in client.models.list():
  for action in m.supported_actions:
    if action == "createTunedModel":
      print(m.name)
      break

# create tuning model
training_dataset=types.TuningDataset(
        examples=[
            types.TuningExample(
                text_input=f'input {i}',
                output=f'output {i}',
            )
            for i in range(5)
        ],
    )
tuning_job = client.tunings.tune(
    base_model='models/gemini-2.5-flash-001-tuning',
    training_dataset=training_dataset,
    config=types.CreateTuningJobConfig(
        epoch_count= 5,
        batch_size=4,
        learning_rate=0.001,
        tuned_model_display_name="test tuned model"
    )
)

# generate content with the tuned model
response = client.models.generate_content(
    model=tuning_job.tuned_model.model,
    contents='55',
)

最終更新日 2025-07-24 UTC。

///

Google 検索によるグラウンディングは、Gemini モデルをリアルタイムのウェブ コンテンツに接続します。すべての利用可能な言語で動作します。これにより、Gemini はより正確な回答を提供し、ナレッジのカットオフを超えて検証可能なソースを引用できるようになります。

グラウンドングは、次のことができるアプリケーションを構築するのに役立ちます。

事実の正確性を高める: 回答を実世界の情報に基づいて生成することで、モデルのハルシネーションを軽減します。
リアルタイムの情報にアクセスする: 最新のイベントやトピックに関する質問に回答します。
引用を提供する: モデルの主張の出典を示すことで、ユーザーの信頼を築きます。

Python
JavaScript
REST
from google import genai
from google.genai import types

# Configure the client
client = genai.Client()

# Define the grounding tool
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# Configure generation settings
config = types.GenerateContentConfig(
    tools=[grounding_tool]
)

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Who won the euro 2024?",
    config=config,
)

# Print the grounded response
print(response.text)
詳しくは、検索ツール ノートブックをお試しください。

Google 検索によるグラウンディングの仕組み
google_search ツールを有効にすると、モデルが情報の検索、処理、引用のワークフローをすべて自動的に処理します。

grounding-overview

ユーザー プロンプト: アプリは、google_search ツールを有効にして、ユーザーのプロンプトを Gemini API に送信します。
プロンプトの分析: モデルはプロンプトを分析し、Google 検索で回答を改善できるかどうかを判断します。
Google 検索: 必要に応じて、モデルは 1 つ以上の検索語句を自動的に生成して実行します。
検索結果の処理: モデルは検索結果を処理し、情報を統合して回答を作成します。
Grounded Response: API は、検索結果に基づく、ユーザー フレンドリーな最終レスポンスを返します。このレスポンスには、モデルのテキスト回答と、検索クエリ、ウェブ検索結果、引用を含む groundingMetadata が含まれます。
グラウンディング レスポンスを理解する
レスポンスが正常に接地されると、レスポンスに groundingMetadata フィールドが含まれます。この構造化データは、申し立ての検証と、アプリ内での豊富な引用機能の構築に不可欠です。

{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "Spain won Euro 2024, defeating England 2-1 in the final. This victory marks Spain's record fourth European Championship title."
          }
        ],
        "role": "model"
      },
      "groundingMetadata": {
        "webSearchQueries": [
          "UEFA Euro 2024 winner",
          "who won euro 2024"
        ],
        "searchEntryPoint": {
          "renderedContent": "<!-- HTML and CSS for the search widget -->"
        },
        "groundingChunks": [
          {"web": {"uri": "https://vertexaisearch.cloud.google.com.....", "title": "aljazeera.com"}},
          {"web": {"uri": "https://vertexaisearch.cloud.google.com.....", "title": "uefa.com"}}
        ],
        "groundingSupports": [
          {
            "segment": {"startIndex": 0, "endIndex": 85, "text": "Spain won Euro 2024, defeatin..."},
            "groundingChunkIndices": [0]
          },
          {
            "segment": {"startIndex": 86, "endIndex": 210, "text": "This victory marks Spain's..."},
            "groundingChunkIndices": [0, 1]
          }
        ]
      }
    }
  ]
}
Gemini API は、groundingMetadata とともに次の情報を返します。

webSearchQueries : 使用された検索クエリの配列。これは、モデルの推論プロセスのデバッグと理解に役立ちます。
searchEntryPoint : 必要な検索候補をレンダリングする HTML と CSS が含まれています。使用要件の詳細については、利用規約をご覧ください。
groundingChunks : ウェブソース（uri と title）を含むオブジェクトの配列。
groundingSupports : モデル レスポンス text を groundingChunks のソースに接続するチャンクの配列。各チャンクは、テキスト segment（startIndex と endIndex で定義）を 1 つ以上の groundingChunkIndices にリンクします。これが、インライン引用を作成するうえで重要なポイントです。
Google 検索によるグラウンディングは、URL コンテキスト ツールと組み合わせて使用することもできます。これにより、一般公開のウェブデータと指定した特定の URL の両方でレスポンスをグラウンディングできます。

インライン引用を使用してソースを帰属する
この API は構造化された引用データを返すため、ユーザー インターフェースでソースを表示する方法を完全に制御できます。groundingSupports フィールドと groundingChunks フィールドを使用すると、モデルのステートメントをソースに直接リンクできます。以下は、メタデータを処理して、クリック可能なインライン引用を含むレスポンスを作成する一般的なパターンです。

Python
JavaScript
def add_citations(response):
    text = response.text
    supports = response.candidates[0].grounding_metadata.grounding_supports
    chunks = response.candidates[0].grounding_metadata.grounding_chunks

    # Sort supports by end_index in descending order to avoid shifting issues when inserting.
    sorted_supports = sorted(supports, key=lambda s: s.segment.end_index, reverse=True)

    for support in sorted_supports:
        end_index = support.segment.end_index
        if support.grounding_chunk_indices:
            # Create citation string like [1](link1)[2](link2)
            citation_links = []
            for i in support.grounding_chunk_indices:
                if i < len(chunks):
                    uri = chunks[i].web.uri
                    citation_links.append(f"[{i + 1}]({uri})")

            citation_string = ", ".join(citation_links)
            text = text[:end_index] + citation_string + text[end_index:]

    return text

# Assuming response with grounding metadata
text_with_citations = add_citations(response)
print(text_with_citations)
Spain won Euro 2024, defeating England 2-1 in the final.[1](https:/...), [2](https:/...), [4](https:/...), [5](https:/...) This victory marks Spain's record-breaking fourth European Championship title.[5]((https:/...), [2](https:/...), [3](https:/...), [4](https:/...)
料金
Google 検索でグラウンディングを使用する場合、プロジェクトは google_search ツールを含む API リクエストごとに課金されます。モデルが 1 つのプロンプトに応答するために複数の検索クエリを実行する場合（同じ API 呼び出し内で "UEFA Euro 2024 winner" と "Spain vs England Euro 2024 final score" を検索する場合など）、そのリクエストに対するツールの課金対象の使用は 1 回とカウントされます。

料金の詳細については、Gemini API の料金ページをご覧ください。

サポートされているモデル
試験運用版モデルとプレビュー版モデルは含まれません。これらの機能は、モデルの概要ページで確認できます。

モデル	Google 検索によるグラウンディング
Gemini 2.5 Pro	✔️
Gemini 2.5 Flash	✔️
Gemini 2.0 Flash	✔️
Gemini 1.5 Pro	✔️
Gemini 1.5 Flash	✔️
注: 古いモデルでは google_search_retrieval ツールを使用します。現在のすべてのモデルでは、例に示すように google_search ツールを使用します。
Gemini 1.5 モデルを使用したグラウンディング（従来版）
Gemini 2.0 以降では google_search ツールの使用をおすすめしますが、Gemini 1.5 では google_search_retrieval というレガシー ツールがサポートされています。このツールには、プロンプトに新しい情報が必要な信頼度に基づいて、モデルが検索を実行するかどうかを決定できる dynamic モードが用意されています。モデルの信頼度が、設定した dynamic_threshold（0.0 ～ 1.0 の値）を超えると、検索が実行されます。

Python
JavaScript
REST
# Note: This is a legacy approach for Gemini 1.5 models.
# The 'google_search' tool is recommended for all new development.
import os
from google import genai
from google.genai import types

client = genai.Client()

retrieval_tool = types.Tool(
    google_search_retrieval=types.GoogleSearchRetrieval(
        dynamic_retrieval_config=types.DynamicRetrievalConfig(
            mode=types.DynamicRetrievalConfigMode.MODE_DYNAMIC,
            dynamic_threshold=0.7 # Only search if confidence > 70%
        )
    )
)

config = types.GenerateContentConfig(
    tools=[retrieval_tool]
)

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents="Who won the euro 2024?",
    config=config,
)
print(response.text)
if not response.candidates[0].grounding_metadata:
  print("\nModel answered from its own knowledge.")
次のステップ
Gemini API クックブックの Google 検索によるグラウンディングをお試しください。

最終更新日 2025-07-24 UTC。



///


試験運用版: URL コンテキスト ツールは試験運用版の機能です。
URL コンテキスト ツールを使用すると、プロンプトの追加コンテキストとして URL を Gemini に提供できます。モデルは URL からコンテンツを取得し、そのコンテンツを使用してレスポンスを通知して形成できます。

このツールは、次のようなタスクに役立ちます。

記事から重要なデータポイントや話題を抽出する
複数のリンク間で情報を比較する
複数のソースからのデータを統合する
特定のページの内容に基づいて質問に回答する
特定の目的（求人情報の作成やテスト問題の作成など）でコンテンツを分析する
このガイドでは、Gemini API の URL コンテキスト ツールの使用方法について説明します。

URL コンテキストを使用する
URL コンテキスト ツールは、単独で使用することも、Google 検索によるグラウンディングと組み合わせて使用することもできます。

URL コンテキストのみ

モデルに直接分析させる特定の URL をプロンプトで指定します。

プロンプトの例:


Summarize this document: YOUR_URLs

Extract the key features from the product description on this page: YOUR_URLs
Google 検索 + URL コンテキストによるグラウンディング

URL コンテキストと Google 検索によるグラウンディングの両方を有効にすることもできます。プロンプトは URL の有無にかかわらず入力できます。モデルはまず関連情報を検索し、次に URL コンテキスト ツールを使用して検索結果のコンテンツを読み取り、より詳細に理解します。

プロンプトの例:


Give me three day events schedule based on YOUR_URL. Also let me know what needs to taken care of considering weather and commute.

Recommend 3 books for beginners to read to learn more about the latest YOUR_subject.
URL コンテキストのみのコード例
Python
JavaScript
REST

from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

client = genai.Client()
model_id = "gemini-2.5-flash"

url_context_tool = Tool(
    url_context = types.UrlContext
)

response = client.models.generate_content(
    model=model_id,
    contents="Compare recipes from YOUR_URL1 and YOUR_URL2",
    config=GenerateContentConfig(
        tools=[url_context_tool],
        response_modalities=["TEXT"],
    )
)

for each in response.candidates[0].content.parts:
    print(each.text)
# get URLs retrieved for context
print(response.candidates[0].url_context_metadata)

Google 検索によるグラウンディングを使用したコード例
Python
JavaScript
REST

from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

client = genai.Client()
model_id = "gemini-2.5-flash"

tools = []
tools.append(Tool(url_context=types.UrlContext))
tools.append(Tool(google_search=types.GoogleSearch))

response = client.models.generate_content(
    model=model_id,
    contents="Give me three day events schedule based on YOUR_URL. Also let me know what needs to taken care of considering weather and commute.",
    config=GenerateContentConfig(
        tools=tools,
        response_modalities=["TEXT"],
    )
)

for each in response.candidates[0].content.parts:
    print(each.text)
# get URLs retrieved for context
print(response.candidates[0].url_context_metadata)

Google 検索によるグラウンディングの詳細については、概要ページをご覧ください。

コンテキストに応じたレスポンス
モデルのレスポンスは、URL から取得したコンテンツに基づいています。モデルが URL からコンテンツを取得した場合、レスポンスには url_context_metadata が含まれます。このようなレスポンスは次のようになります（簡潔にするため、レスポンスの一部を省略しています）。

{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "... \n"
          }
        ],
        "role": "model"
      },
      ...
      "url_context_metadata":
      {
          "url_metadata":
          [
            {
              "retrieved_url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/1234567890abcdef",
              "url_retrieval_status": <UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS: "URL_RETRIEVAL_STATUS_SUCCESS">
            },
            {
              "retrieved_url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abcdef1234567890",
              "url_retrieval_status": <UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS: "URL_RETRIEVAL_STATUS_SUCCESS">
            },
            {
              "retrieved_url": "YOUR_URL",
              "url_retrieval_status": <UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS: "URL_RETRIEVAL_STATUS_SUCCESS">
            },
            {
              "retrieved_url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/fedcba0987654321",
              "url_retrieval_status": <UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS: "URL_RETRIEVAL_STATUS_SUCCESS">
            }
          ]
        }
    }
}
サポートされているモデル
gemini-2.5-pro
gemini-2.5-flash
gemini-2.5-flash-lite
gemini-2.0-flash
gemini-2.0-flash-live-001
制限事項
このツールは、分析のためにリクエストごとに最大 20 個の URL を使用します。
試験運用版の段階では、YouTube 動画などのマルチメディア コンテンツではなく、標準のウェブページでツールを使用することをおすすめします。
試験運用期間中は、このツールは無料でご利用いただけます。請求は後日行われます。
試験運用版のリリースには次の割り当てがあります。


最終更新日 2025-07-24 UTC。

///



Gemini API を使用した関数呼び出し



関数呼び出しを使用すると、モデルを外部ツールや API に接続できます。モデルは、テキスト レスポンスを生成するのではなく、特定の関数を呼び出すタイミングを判断し、現実世界のアクションを実行するために必要なパラメータを提供します。これにより、モデルは自然言語と実際のアクションやデータとの間の橋渡しとして機能できます。関数呼び出しには、主に次の 3 つのユースケースがあります。

知識の拡張: データベース、API、ナレッジベースなどの外部ソースから情報にアクセスします。
機能の拡張: 外部ツールを使用して計算を行い、モデルの制限を拡張します（電卓の使用やグラフの作成など）。
アクションを実行する: API を使用して外部システムとやり取りします。たとえば、予定のスケジュール設定、請求書の作成、メールの送信、スマートホーム デバイスの制御などです。
天気を取得 会議のスケジュールを設定 グラフを作成

Python
JavaScript
REST

from google import genai
from google.genai import types

# Define the function declaration for the model
schedule_meeting_function = {
    "name": "schedule_meeting",
    "description": "Schedules a meeting with specified attendees at a given time and date.",
    "parameters": {
        "type": "object",
        "properties": {
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of people attending the meeting.",
            },
            "date": {
                "type": "string",
                "description": "Date of the meeting (e.g., '2024-07-29')",
            },
            "time": {
                "type": "string",
                "description": "Time of the meeting (e.g., '15:00')",
            },
            "topic": {
                "type": "string",
                "description": "The subject or topic of the meeting.",
            },
        },
        "required": ["attendees", "date", "time", "topic"],
    },
}

# Configure the client and tools
client = genai.Client()
tools = types.Tool(function_declarations=[schedule_meeting_function])
config = types.GenerateContentConfig(tools=[tools])

# Send request with function declarations
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Schedule a meeting with Bob and Alice for 03/14/2025 at 10:00 AM about the Q3 planning.",
    config=config,
)

# Check for a function call
if response.candidates[0].content.parts[0].function_call:
    function_call = response.candidates[0].content.parts[0].function_call
    print(f"Function to call: {function_call.name}")
    print(f"Arguments: {function_call.args}")
    #  In a real app, you would call your function here:
    #  result = schedule_meeting(**function_call.args)
else:
    print("No function call found in the response.")
    print(response.text)
関数呼び出しの仕組み
関数呼び出しの概要

関数呼び出しでは、アプリケーション、モデル、外部関数間の構造化されたやり取りが行われます。プロセスの詳細は次のとおりです。

関数宣言を定義する: アプリケーション コードで関数宣言を定義します。関数宣言は、関数名、パラメータ、目的をモデルに記述します。
関数宣言を使用して LLM を呼び出す: ユーザー プロンプトと関数宣言をモデルに送信します。リクエストを分析し、関数呼び出しが役立つかどうかを判断します。その場合、構造化された JSON オブジェクトで応答します。
関数コードの実行（お客様の責任）: モデルは関数自体を実行しません。
レスポンスを処理し、関数呼び出しを確認するのは、アプリケーションの責任です。
はい: 関数の名前と引数を抽出し、アプリケーション内の対応する関数を実行します。
いいえ: モデルがプロンプトに対して直接テキスト レスポンスを提供しました（このフローは例ではあまり強調されていませんが、結果としてありえます）。
ユーザー フレンドリーなレスポンスを作成する: 関数が実行された場合は、結果を取得して、会話の次のターンでモデルに送り返します。この結果を使用して、関数呼び出しからの情報を取り込んだ、ユーザー フレンドリーな最終的なレスポンスを生成します。
このプロセスは複数回繰り返すことができ、複雑なインタラクションとワークフローが可能になります。このモデルは、1 つのターンで複数の関数を並列に呼び出す（並列関数呼び出し）ことと、順番に呼び出す（構成関数呼び出し）こともサポートしています。

ステップ 1: 関数宣言を定義する
ユーザーが照明の値を設定して API リクエストを行うことができる関数とその宣言を、アプリコード内で定義します。この関数は、外部サービスまたは API を呼び出す可能性があります。

Python
JavaScript
# Define a function that the model can call to control smart lights
set_light_values_declaration = {
    "name": "set_light_values",
    "description": "Sets the brightness and color temperature of a light.",
    "parameters": {
        "type": "object",
        "properties": {
            "brightness": {
                "type": "integer",
                "description": "Light level from 0 to 100. Zero is off and 100 is full brightness",
            },
            "color_temp": {
                "type": "string",
                "enum": ["daylight", "cool", "warm"],
                "description": "Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.",
            },
        },
        "required": ["brightness", "color_temp"],
    },
}

# This is the actual function that would be called based on the model's suggestion
def set_light_values(brightness: int, color_temp: str) -> dict[str, int | str]:
    """Set the brightness and color temperature of a room light. (mock API).

    Args:
        brightness: Light level from 0 to 100. Zero is off and 100 is full brightness
        color_temp: Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.

    Returns:
        A dictionary containing the set brightness and color temperature.
    """
    return {"brightness": brightness, "colorTemperature": color_temp}
ステップ 2: 関数宣言を使用してモデルを呼び出す
関数宣言を定義したら、モデルにそれらを使用するように指示できます。プロンプトと関数宣言を分析し、直接応答するか関数を呼び出すかを決定します。関数が呼び出されると、レスポンス オブジェクトに関数呼び出しの候補が含まれます。

Python
JavaScript
from google.genai import types

# Configure the client and tools
client = genai.Client()
tools = types.Tool(function_declarations=[set_light_values_declaration])
config = types.GenerateContentConfig(tools=[tools])

# Define user prompt
contents = [
    types.Content(
        role="user", parts=[types.Part(text="Turn the lights down to a romantic level")]
    )
]

# Send request with function declarations
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=contents
    config=config,
)

print(response.candidates[0].content.parts[0].function_call)
モデルは、ユーザーの質問に回答するために宣言された 1 つ以上の関数を呼び出す方法を指定する OpenAPI 互換スキーマで functionCall オブジェクトを返します。

Python
JavaScript
id=None args={'color_temp': 'warm', 'brightness': 25} name='set_light_values'
ステップ 3: set_light_values 関数コードを実行する
モデルのレスポンスから関数呼び出しの詳細を抽出し、引数を解析して、set_light_values 関数を実行します。

Python
JavaScript
# Extract tool call details, it may not be in the first part.
tool_call = response.candidates[0].content.parts[0].function_call

if tool_call.name == "set_light_values":
    result = set_light_values(**tool_call.args)
    print(f"Function execution result: {result}")
ステップ 4: 関数結果を使用してユーザー フレンドリーなレスポンスを作成し、モデルを再度呼び出す
最後に、関数の実行結果をモデルに送り返し、モデルがこの情報をユーザーへの最終的なレスポンスに組み込めるようにします。

Python
JavaScript
# Create a function response part
function_response_part = types.Part.from_function_response(
    name=tool_call.name,
    response={"result": result},
)

# Append function call and result of the function execution to contents
contents.append(response.candidates[0].content) # Append the content from the model's response.
contents.append(types.Content(role="user", parts=[function_response_part])) # Append the function response

final_response = client.models.generate_content(
    model="gemini-2.5-flash",
    config=config,
    contents=contents,
)

print(final_response.text)
これで、関数呼び出しフローが完了します。モデルは set_light_values 関数を使用して、ユーザーのリクエスト アクションを正常に実行しました。

関数宣言
プロンプトで関数呼び出しを実装する場合は、1 つ以上の function declarations を含む tools オブジェクトを作成します。関数は JSON を使用して定義します。具体的には、OpenAPI スキーマ形式のサブセットを選択します。1 つの関数宣言に含めることができるパラメータは、次のとおりです。

name（文字列）: 関数の一意の名前（get_weather_forecast、send_email）。スペースや特殊文字を含まないわかりやすい名前を使用します（アンダースコアまたは camelCase を使用）。
description（文字列）: 関数の目的と機能についての明確で詳細な説明。これは、モデルが関数を使用するタイミングを理解するために重要です。具体的に説明し、必要に応じて例を挙げてください（「場所と、必要に応じて映画館で上映中の映画のタイトルに基づいて映画館を検索します。」）。
parameters（オブジェクト）: 関数が想定する入力パラメータを定義します。
type（文字列）: 全体的なデータ型（object など）を指定します。
properties（オブジェクト）: 個々のパラメータを一覧表示します。各パラメータには次の情報が含まれます。
type（文字列）: パラメータのデータ型（string、integer、boolean, array など）。
description（文字列）: パラメータの目的と形式の説明。例と制約を指定します（「都市と州。例: 'San Francisco, CA' などの都市名、または郵便番号（例: '95616'.")。
enum（配列、省略可）: パラメータ値が固定セットからのものである場合は、説明で説明するだけでなく、"enum" を使用して許可される値を一覧表示します。これにより、精度が向上します（「enum」: ["daylight", "cool", "warm"]）。
required（配列）: 関数の動作に必須のパラメータ名を列挙した文字列の配列。
types.FunctionDeclaration.from_callable(client=client, callable=your_function) を使用して、Python 関数から FunctionDeclaration を直接構築することもできます。

思考を伴う関数呼び出し
「思考」を有効にすると、モデルが関数呼び出しを提案する前にリクエストを推論できるようになるため、関数呼び出しのパフォーマンスが向上します。Gemini API はステートレスです。マルチターンの会話では、モデルの推論コンテキストはターン間で失われます。このコンテキストを保持するには、思考シグネチャを使用します。思考シグネチャは、モデルの内部思考プロセスの暗号化された表現です。これは、後続のターンでモデルに渡されます。

マルチターン ツールの標準パターンでは、モデルの完全な前のレスポンスを会話履歴に追加します。content オブジェクトには thought_signatures が自動的に含まれます。このパターンに従う場合、コードの変更は必要ありません。

思考シグネチャを手動で管理する
前のレスポンス全体を送信するのではなく、会話履歴を手動で変更する場合、モデルのターンの thought_signature を正しく処理する必要があります。

モデルのコンテキストが保持されるように、次のルールに従ってください。

thought_signature は常に元の Part 内のモデルに送り返します。
署名を含む Part を署名を含まない Part とマージしないでください。これにより、思考の位置コンテキストが壊れます。
署名文字列は統合できないため、両方に署名が含まれている 2 つの Parts を組み合わせないでください。
思考シグネチャの検査
実装には必要ありませんが、デバッグや学習のためにレスポンスを調べて thought_signature を確認できます。

Python
JavaScript
import base64
# After receiving a response from a model with thinking enabled
# response = client.models.generate_content(...)

# The signature is attached to the response part containing the function call
part = response.candidates[0].content.parts[0]
if part.thought_signature:
  print(base64.b64encode(part.thought_signature).decode("utf-8"))
思考シグネチャの制限事項と使用方法、および一般的な思考モデルについては、思考のページをご覧ください。

並列関数呼び出し
単一ターンの関数呼び出しに加えて、複数の関数を一度に呼び出すこともできます。並列関数呼び出しを使用すると、複数の関数を同時に実行できます。この機能は、関数が相互に依存していない場合に使用されます。これは、複数の独立したソースからデータを収集するシナリオ（異なるデータベースから顧客の詳細を取得する、さまざまな倉庫の在庫レベルを確認する、アパートをディスコに改造するなど複数のアクションを実行する）で役立ちます。

Python
JavaScript
power_disco_ball = {
    "name": "power_disco_ball",
    "description": "Powers the spinning disco ball.",
    "parameters": {
        "type": "object",
        "properties": {
            "power": {
                "type": "boolean",
                "description": "Whether to turn the disco ball on or off.",
            }
        },
        "required": ["power"],
    },
}

start_music = {
    "name": "start_music",
    "description": "Play some music matching the specified parameters.",
    "parameters": {
        "type": "object",
        "properties": {
            "energetic": {
                "type": "boolean",
                "description": "Whether the music is energetic or not.",
            },
            "loud": {
                "type": "boolean",
                "description": "Whether the music is loud or not.",
            },
        },
        "required": ["energetic", "loud"],
    },
}

dim_lights = {
    "name": "dim_lights",
    "description": "Dim the lights.",
    "parameters": {
        "type": "object",
        "properties": {
            "brightness": {
                "type": "number",
                "description": "The brightness of the lights, 0.0 is off, 1.0 is full.",
            }
        },
        "required": ["brightness"],
    },
}
指定されたすべてのツールを使用できるように関数呼び出しモードを構成します。詳細については、関数呼び出しの構成をご覧ください。

Python
JavaScript
from google import genai
from google.genai import types

# Configure the client and tools
client = genai.Client()
house_tools = [
    types.Tool(function_declarations=[power_disco_ball, start_music, dim_lights])
]
config = types.GenerateContentConfig(
    tools=house_tools,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(
        disable=True
    ),
    # Force the model to call 'any' function, instead of chatting.
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode='ANY')
    ),
)

chat = client.chats.create(model="gemini-2.5-flash", config=config)
response = chat.send_message("Turn this place into a party!")

# Print out each of the function calls requested from this single call
print("Example 1: Forced function calling")
for fn in response.function_calls:
    args = ", ".join(f"{key}={val}" for key, val in fn.args.items())
    print(f"{fn.name}({args})")
出力された結果はそれぞれ、モデルがリクエストした単一の関数呼び出しを反映しています。結果を返すには、リクエストされた順序と同じ順序でレスポンスを含めます。

Python SDK は、Python 関数を宣言に自動的に変換し、関数呼び出しの実行とレスポンスのサイクルを処理する自動関数呼び出しをサポートしています。以下に、ディスコのユースケースの例を示します。

注: 現在、自動関数呼び出しは Python SDK のみの機能です。
Python
from google import genai
from google.genai import types

# Actual function implementations
def power_disco_ball_impl(power: bool) -> dict:
    """Powers the spinning disco ball.

    Args:
        power: Whether to turn the disco ball on or off.

    Returns:
        A status dictionary indicating the current state.
    """
    return {"status": f"Disco ball powered {'on' if power else 'off'}"}

def start_music_impl(energetic: bool, loud: bool) -> dict:
    """Play some music matching the specified parameters.

    Args:
        energetic: Whether the music is energetic or not.
        loud: Whether the music is loud or not.

    Returns:
        A dictionary containing the music settings.
    """
    music_type = "energetic" if energetic else "chill"
    volume = "loud" if loud else "quiet"
    return {"music_type": music_type, "volume": volume}

def dim_lights_impl(brightness: float) -> dict:
    """Dim the lights.

    Args:
        brightness: The brightness of the lights, 0.0 is off, 1.0 is full.

    Returns:
        A dictionary containing the new brightness setting.
    """
    return {"brightness": brightness}

# Configure the client
client = genai.Client()
config = types.GenerateContentConfig(
    tools=[power_disco_ball_impl, start_music_impl, dim_lights_impl]
)

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Do everything you need to this place into party!",
    config=config,
)

print("\nExample 2: Automatic function calling")
print(response.text)
# I've turned on the disco ball, started playing loud and energetic music, and dimmed the lights to 50% brightness. Let's get this party started!
コンポジション関数呼び出し
構成的または順次的な関数呼び出しにより、Gemini は複数の関数呼び出しを連結して、複雑なリクエストを満たすことができます。たとえば、「現在地の気温を取得して」という質問に答えるために、Gemini API は最初に get_current_location() 関数を呼び出し、次に場所をパラメータとして受け取る get_weather() 関数を呼び出すことがあります。

次の例は、Python SDK と自動関数呼び出しを使用して合成関数呼び出しを実装する方法を示しています。

Python
JavaScript
この例では、google-genai Python SDK の自動関数呼び出し機能を使用します。SDK は、Python 関数を必要なスキーマに自動的に変換し、モデルからリクエストされたときに関数呼び出しを実行し、結果をモデルに送り返してタスクを完了します。

import os
from google import genai
from google.genai import types

# Example Functions
def get_weather_forecast(location: str) -> dict:
    """Gets the current weather temperature for a given location."""
    print(f"Tool Call: get_weather_forecast(location={location})")
    # TODO: Make API call
    print("Tool Response: {'temperature': 25, 'unit': 'celsius'}")
    return {"temperature": 25, "unit": "celsius"}  # Dummy response

def set_thermostat_temperature(temperature: int) -> dict:
    """Sets the thermostat to a desired temperature."""
    print(f"Tool Call: set_thermostat_temperature(temperature={temperature})")
    # TODO: Interact with a thermostat API
    print("Tool Response: {'status': 'success'}")
    return {"status": "success"}

# Configure the client and model
client = genai.Client()
config = types.GenerateContentConfig(
    tools=[get_weather_forecast, set_thermostat_temperature]
)

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="If it's warmer than 20°C in London, set the thermostat to 20°C, otherwise set it to 18°C.",
    config=config,
)

# Print the final, user-facing response
print(response.text)
想定される出力

コードを実行すると、SDK が関数呼び出しをオーケストレートしていることがわかります。モデルは最初に get_weather_forecast を呼び出し、温度を受け取ってから、プロンプトのロジックに基づいて正しい値で set_thermostat_temperature を呼び出します。

Tool Call: get_weather_forecast(location=London)
Tool Response: {'temperature': 25, 'unit': 'celsius'}
Tool Call: set_thermostat_temperature(temperature=20)
Tool Response: {'status': 'success'}
OK. I've set the thermostat to 20°C.
コンポジション関数呼び出しは、ネイティブの Live API 機能です。つまり、Live API は Python SDK と同様に関数呼び出しを処理できます。

Python
JavaScript
# Light control schemas
turn_on_the_lights_schema = {'name': 'turn_on_the_lights'}
turn_off_the_lights_schema = {'name': 'turn_off_the_lights'}

prompt = """
  Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
  """

tools = [
    {'code_execution': {}},
    {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]}
]

await run(prompt, tools=tools, modality="AUDIO")
関数呼び出しモード
Gemini API を使用すると、モデルが提供されたツール（関数宣言）を使用する方法を制御できます。具体的には、.function_calling_config. 内でモードを設定できます。

AUTO (Default): モデルは、プロンプトとコンテキストに基づいて、自然言語によるレスポンスを生成するか、関数呼び出しを提案するかを決定します。これは最も柔軟なモードであり、ほとんどのシナリオで推奨されます。
ANY: モデルは常に関数呼び出しを予測するように制約され、関数スキーマの準拠が保証されます。allowed_function_names が指定されていない場合、モデルは指定された関数宣言のいずれかを選択できます。allowed_function_names がリストとして指定されている場合、モデルはそのリスト内の関数からのみ選択できます。このモードは、すべてのプロンプトに関数呼び出しのレスポンスが必要な場合に使用します（該当する場合）。
NONE: モデルは関数呼び出しを行うことが禁止されています。これは、関数宣言なしでリクエストを送信するのと同じです。これを使用すると、ツール定義を削除せずに関数呼び出しを一時的に無効にできます。

Python
JavaScript
from google.genai import types

# Configure function calling mode
tool_config = types.ToolConfig(
    function_calling_config=types.FunctionCallingConfig(
        mode="ANY", allowed_function_names=["get_current_temperature"]
    )
)

# Create the generation config
config = types.GenerateContentConfig(
    tools=[tools],  # not defined here.
    tool_config=tool_config,
)
自動関数呼び出し（Python のみ）
Python SDK を使用する場合は、Python 関数をツールとして直接指定できます。SDK は Python 関数を宣言に自動的に変換し、関数呼び出しの実行とレスポンス サイクルを処理します。Python SDK は、次の処理を自動的に行います。

モデルからの関数呼び出しレスポンスを検出します。
コードで対応する Python 関数を呼び出します。
関数レスポンスをモデルに返します。
モデルの最終的なテキスト レスポンスを返します。
これを使用するには、型ヒントと docstring を使用して関数を定義し、関数自体（JSON 宣言ではない）をツールとして渡します。

Python
from google import genai
from google.genai import types

# Define the function with type hints and docstring
def get_current_temperature(location: str) -> dict:
    """Gets the current temperature for a given location.

    Args:
        location: The city and state, e.g. San Francisco, CA

    Returns:
        A dictionary containing the temperature and unit.
    """
    # ... (implementation) ...
    return {"temperature": 25, "unit": "Celsius"}

# Configure the client
client = genai.Client()
config = types.GenerateContentConfig(
    tools=[get_current_temperature]
)  # Pass the function itself

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="What's the temperature in Boston?",
    config=config,
)

print(response.text)  # The SDK handles the function call and returns the final text
自動関数呼び出しは、次のコードで無効にできます。

Python
config = types.GenerateContentConfig(
    tools=[get_current_temperature],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)
自動関数スキーマ宣言
Python 関数からのスキーマの自動抽出は、すべてのケースで機能するわけではありません。たとえば、ネストされた辞書オブジェクトのフィールドを記述するケースは処理されません。API は、次のいずれかの型を記述できます。

Python
AllowedType = (int | float | bool | str | list['AllowedType'] | dict[str, AllowedType])
推定スキーマを確認するには、from_callable を使用して変換します。

Python
def multiply(a: float, b: float):
    """Returns a * b."""
    return a * b

fn_decl = types.FunctionDeclaration.from_callable(callable=multiply, client=client)

# to_json_dict() provides a clean JSON representation.
print(fn_decl.to_json_dict())
マルチツールの使用: ネイティブ ツールと関数呼び出しを組み合わせる
ネイティブ ツールと関数呼び出しを組み合わせた複数のツールを同時に有効にできます。次の例では、Live API を使用したリクエストで、Google 検索によるグラウンディングとコード実行の 2 つのツールを有効にしています。

注: 現在、マルチツールは Live API のみの機能です。簡潔にするため、非同期 WebSocket の設定を処理する run() 関数宣言は省略しています。
Python
JavaScript
# Multiple tasks example - combining lights, code execution, and search
prompt = """
  Hey, I need you to do three things for me.

    1.  Turn on the lights.
    2.  Then compute the largest prime palindrome under 100000.
    3.  Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.

  Thanks!
  """

tools = [
    {'google_search': {}},
    {'code_execution': {}},
    {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]} # not defined here.
]

# Execute the prompt with specified tools in audio modality
await run(prompt, tools=tools, modality="AUDIO")
Python デベロッパーは、Live API Tool Use ノートブックでこれを試すことができます。

モデル コンテキスト プロトコル（MCP）
Model Context Protocol（MCP）は、AI アプリケーションを外部ツールやデータに接続するためのオープン標準です。MCP は、モデルが関数（ツール）、データソース（リソース）、事前定義されたプロンプトなどのコンテキストにアクセスするための共通プロトコルを提供します。

Gemini SDK には MCP のサポートが組み込まれているため、ボイラープレート コードが削減され、MCP ツールの自動ツール呼び出しが提供されます。モデルが MCP ツール呼び出しを生成すると、Python と JavaScript のクライアント SDK は MCP ツールを自動的に実行し、後続のリクエストでレスポンスをモデルに送り返します。このループは、モデルがツール呼び出しを行わなくなるまで続きます。

Gemini と mcp SDK でローカル MCP サーバーを使用する方法の例については、こちらをご覧ください。

Python
JavaScript
選択したプラットフォームに最新バージョンの mcp SDK がインストールされていることを確認します。

pip install mcp
注: Python では、ClientSession を tools パラメータに渡すことで、ツールの自動呼び出しがサポートされています。無効にする場合は、True を無効にして automatic_function_calling を指定します。
import os
import asyncio
from datetime import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai

client = genai.Client()

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="npx",  # Executable
    args=["-y", "@philschmid/weather-mcp"],  # MCP Server
    env=None,  # Optional environment variables
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Prompt to get the weather for the current day in London.
            prompt = f"What is the weather in London in {datetime.now().strftime('%Y-%m-%d')}?"

            # Initialize the connection between client and server
            await session.initialize()

            # Send request to the model with MCP function declarations
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    tools=[session],  # uses the session, will automatically call the tool
                    # Uncomment if you **don't** want the SDK to automatically call the tool
                    # automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(
                    #     disable=True
                    # ),
                ),
            )
            print(response.text)

# Start the asyncio event loop and run the main function
asyncio.run(run())
組み込み MCP サポートの制限事項
組み込み MCP サポートは SDK の試験運用版の機能であり、次の制限があります。

ツールのみがサポートされ、リソースやプロンプトはサポートされません
Python SDK と JavaScript/TypeScript SDK で使用できます。
今後のリリースで破壊的変更が発生する可能性があります。
これらの制限によって構築するものが制限される場合は、MCP サーバーの手動統合をいつでも選択できます。

サポートされているモデル
このセクションでは、モデルとその関数呼び出し機能の一覧を示します。試験運用版のモデルは含まれていません。機能の包括的な概要については、モデルの概要ページをご覧ください。

モデル	関数呼び出し	並列関数呼び出し	コンポジション関数呼び出し
Gemini 2.5 Pro	✔️	✔️	✔️
Gemini 2.5 Flash	✔️	✔️	✔️
Gemini 2.5 Flash-Lite	✔️	✔️	✔️
Gemini 2.0 Flash	✔️	✔️	✔️
Gemini 2.0 Flash-Lite	X	X	X
ベスト プラクティス
関数とパラメータの説明: 説明は非常に明確かつ具体的に記述します。モデルは、これらに基づいて正しい関数を選択し、適切な引数を指定します。
命名: 説明的な関数名を使用します（スペース、ピリオド、ダッシュは使用しません）。
強い型付け: パラメータに特定の型（整数、文字列、列挙型）を使用して、エラーを減らします。パラメータの有効な値のセットが限られている場合は、列挙型を使用します。
ツールの選択: モデルは任意の数のツールを使用できますが、ツールが多すぎると、不適切なツールや最適でないツールを選択するリスクが高まります。最良の結果を得るには、コンテキストやタスクに関連するツールのみを提供することを目指します。理想的には、アクティブなセットを最大 10 ～ 20 個に維持します。ツールの合計数が多い場合は、会話のコンテキストに基づいてツールを動的に選択することを検討してください。
プロンプト エンジニアリング:
コンテキストを提供する: モデルに役割を伝えます（例: 「あなたは役に立つ天気アシスタントです。」）。
指示を与える: 関数をいつ、どのように使用するかを指定します（例: 「日付を推測しないでください。予測には常に将来の日付を使用してください。」）。
明確化を促す: 必要に応じて明確化を求める質問をするようモデルに指示します。
温度: 低温（例: 0）に設定して、より確定的で信頼性の高い関数呼び出しを実現します。
検証: 関数呼び出しが重大な結果をもたらす場合（注文など）、それを実行する前にユーザーにその呼び出しの妥当性を確認してください。
エラー処理: 関数に堅牢なエラー処理を実装して、予期しない入力や API のエラーを適切に処理します。モデルがユーザーに役立つ回答を生成するために使用できる、有益なエラー メッセージを返します。
セキュリティ: 外部 API を呼び出す際は、セキュリティに注意してください。適切な認証と認可のメカニズムを使用します。関数呼び出しで機密データを公開しないようにします。
トークンの上限: 関数の説明とパラメータは、入力トークンの上限にカウントされます。トークンの上限に達した場合は、関数の数や説明の長さを制限したり、複雑なタスクをより小さな関数セットに分割したりすることを検討してください。
注意と制限事項
OpenAPI スキーマのサブセットのみがサポートされています。
Python でサポートされているパラメータの型は限られています。
自動関数呼び出しは Python SDK の機能です。
この情報は役に立ちましたか？


最終更新日 2025-07-24 UTC。

///

プロンプト設計は、言語モデルから正確で高品質なレスポンスを引き出すプロンプト（自然言語リクエスト）を作成するプロセスです。

このページでは、Gemini AI モデルを最大限に活用するためのプロンプト設計の基本的なコンセプト、戦略、ベスト プラクティスについて説明します。

トピック固有のプロンプト ガイド
より具体的なプロンプト戦略をお探しですか？以下で、その他のプロンプト ガイドをご覧ください。

メディア ファイルによるプロンプト
画像生成のプロンプト
動画生成のプロンプト
Google AI Studio には、このガイドで説明されている多くのコンセプトをインタラクティブに紹介するプロンプト ギャラリーもあります。

明確で具体的な指示
モデルの動作を効果的かつ効率的にカスタマイズするには、明確で具体的な指示をモデルに提供します。指示は、質問、手順ごとのタスク、ユーザーの体験や考え方を示すような複雑な内容にすることもできます。

入力
入力は、モデルにレスポンスを提供させるプロンプトの必須テキストです。入力は、モデルが回答する質問（質問入力）、モデルが実行するタスク（タスク入力）、モデルが動作するエンティティ（エンティティ入力）、またはモデルが完了または続行する部分入力（コンプリーション入力）のいずれかです。

入力タイプ	プロンプト	生成された出力
質問	


What's a good name for a flower shop that specializes in selling bouquets of
dried flowers? Create a list of 5 options with just the names.


Here are 10 names for a flower shop specializing in dried flowers:

1. Everlasting Blooms
2. Dried & Delightful
3. The Petal Preserve
4. Whispers of Wildflowers
5. Forever Blooms
タスク	

Give me a simple list of just the things that I must bring on a camping trip. The list should have 5 items.

1. **Tent:** Your shelter from the elements.
2. **Sleeping Bag:** Stay warm and comfortable.
3. **Sleeping Pad:** Insulation and cushioning for a good night's sleep.
4. **Headlamp or Flashlight:** Light for nighttime activities.
5. **First Aid Kit:** Be prepared for minor injuries.
エンティティ	


Classify the following items as [large, small]:
Elephant
Mouse
Snail


Here's the classification:

* **Elephant:** Large
* **Mouse:** Small
* **Snail:** Small
部分入力の補完
生成言語モデルは、高度な予測入力ツールのように機能します。部分的なコンテンツを提供すると、モデルは残りのコンテンツ、またはコンテンツの継続として認識したコンテンツをレスポンスとして提供できます。その場合、例やコンテキストを含めると、モデルはそれらの例やコンテキストを考慮できます。

次の例では、指示とエンティティ入力を含むプロンプトを示しています。

プロンプト:

For the given order, return a JSON object that has the fields cheeseburger, hamburger, fries, or
drink, with the value being the quantity.

Order: A burger and a drink.
レスポンス:

{
"cheeseburger": 0,
"hamburger": 1,
"fries": 0,
"drink": 1
}
（gemini-2.5-flash）
モデルはプロンプトに従って動作しましたが、自然言語での指示は難しい場合があり、モデルの解釈に多くの負担が残ります。たとえば、レストランのメニューに多くのアイテムが含まれているとします。JSON レスポンスのサイズを小さくするには、オーダーされていないアイテムを省略します。この場合、例とレスポンス接頭辞を指定して、モデルに完成させることができます。

プロンプト:

Valid fields are cheeseburger, hamburger, fries, and drink.
Order: Give me a cheeseburger and fries
Output:
```
{
"cheeseburger": 1,
"fries": 1
}
```
Order: I want two burgers, a drink, and fries.
Output:
レスポンス:

```
{
"hamburger": 2,
"drink": 1,
"fries": 1
}
```
（gemini-2.5-flash）
「cheeseburger」は注文に含まれていないため、出力から除外されています。

制約
プロンプトの読み取りやレスポンスの生成に関する制約を指定します。行うべきことと、行うべきでないことをモデルに指示できます。たとえば、要約の長さについてプロンプトで制約を指定できます。

プロンプト:


Summarize this text in one sentence:
Text: A quantum computer exploits quantum mechanical phenomena to perform calculations exponentially
faster than any modern traditional computer. At very tiny scales, physical matter acts as both
particles and as waves, and quantum computing uses specialized hardware to leverage this behavior.
The operating principles of quantum devices is beyond the scope of classical physics. When deployed
at scale, quantum computers could be used in a wide variety of applications such as: in
cybersecurity to break existing encryption methods while helping researchers create new ones, in
meteorology to develop better weather forecasting etc. However, the current state of the art quantum
computers are still largely experimental and impractical.
レスポンス:


Exploiting quantum mechanical phenomena, quantum computers can perform calculations exponentially faster than traditional computers for potential applications like cybersecurity and meteorology, although they are currently largely experimental and impractical.
（gemini-2.5-flash）
回答の形式
指示の中でレスポンスの形式を指定することもできます。たとえば、表、箇条書き、エレベーター ピッチ、キーワード、文、段落の形式でレスポンスを求めることができます。次のシステム指示は、レスポンスでより会話的な表現を使用するようにモデルに指示します。

システム指示

All questions should be answered comprehensively with details, unless the user requests a concise response specifically.
プロンプト

What is a smart way to make a business that sells DVD's in 2025?
レスポンス:

Starting a business selling DVDs in 2025 presents significant challenges due to the overwhelming dominance of digital streaming and on-demand services; a "smart" approach would therefore require a highly specialized niche, a strong value proposition beyond just the disc, and likely a focus on community or collector markets rather than mainstream consumption.

Here's a breakdown of what a smart DVD business in 2025 would likely entail:

1. Extreme Niche Specialization: You cannot compete with streaming libraries. Your business must focus on what digital doesn't offer easily or at all. This could include:

* Out-of-Print & Rare Titles: Sourcing films or TV shows that have never been released digitally or are currently unavailable on major streaming platforms.
....
（gemini-2.5-flash）
完了戦略を使用してレスポンスをフォーマットする
完了戦略は、レスポンスの形式にも活用できます。次の例では、小論文の概要を作成するようにモデルに指示しています。

プロンプト:

Create an outline for an essay about hummingbirds.
レスポンス:

Here is a possible outline for an essay about hummingbirds:

I. Introduction
A. Hook: Start with a captivating fact or description about hummingbirds (e.g., their speed, iridescent colors, or tiny size).
B. Background: Briefly introduce hummingbirds – where they are found (Americas), their reputation as unique birds.
C. Thesis Statement: State the main point of the essay, which could be about the remarkable adaptations, behaviors, and ecological importance of hummingbirds.

II. Appearance and Identification
.....
（gemini-2.5-flash）
プロンプトでアウトラインの形式が指定されていないため、モデルによって形式が選択されています。モデルが特定の形式でアウトラインを返すようにするには、アウトラインの始点を表すテキストを追加し、開始パターンに基づいてモデルを完成させます。

プロンプト:

Create an outline for an essay about hummingbirds.
I. Introduction
*
レスポンス:

Okay, here is an outline for an essay about hummingbirds, starting from the introduction you provided:

I. Introduction
* Hook: Start with a captivating fact or description about hummingbirds (e.g., their speed, iridescent colors, or tiny size).
* Background: Briefly introduce hummingbirds – where they are found (Americas), their reputation as unique birds, and their general characteristics.
* Thesis Statement: State the main point of the essay, focusing on the remarkable adaptations, behaviors, and ecological significance that make hummingbirds extraordinary.
.....
（gemini-2.5-flash）
ゼロショット プロンプトと少数ショット プロンプト
プロンプトに、モデルに対して望ましい動作を示す例を含めることができます。モデルは、例からパターンと関係を特定し、回答を生成する際にそれらを適用します。いくつかの例を含むプロンプトは少数ショット プロンプトと呼ばれ、例のないプロンプトはゼロショット プロンプトと呼ばれます。少数ショット プロンプトは、モデルのレスポンスのフォーマット、フレーズ、範囲、一般的なパターンの設定を規制するために頻繁に使用されます。具体的で多様な例を使用して、モデルが焦点を絞り込み、より正確な結果を生成できるようにします。

プロンプトには、常に少数ショットの例を含めることをおすすめします。少数ショットの例のないプロンプトは効果が低い可能性があります。タスクを説明するのに十分な例が含まれていれば、プロンプトから指示を削除することも可能です。

次のゼロショット プロンプトでは、モデルに最良の説明を選択するよう求めます。

プロンプト:

Please choose the best explanation to the question:

Question: How is snow formed?
Explanation1: Snow is formed when water vapor in the air freezes into ice
crystals in the atmosphere, which can combine and grow into snowflakes as they
fall through the atmosphere and accumulate on the ground.
Explanation2: Water vapor freezes into ice crystals forming snow.
Answer:
レスポンス:

Explanation1 is the better explanation because it provides more detail on the
process, including how ice crystals combine and grow into snowflakes as they
fall through the atmosphere.
（gemini-2.5-flash）
ユースケースでモデルが簡潔なレスポンスを生成する必要がある場合は、簡潔なレスポンスを優先する例をプロンプトに含めることができます。

次のプロンプトでは、短い説明を優先する例を 2 つ示します。レスポンスでは、前の例のような長い説明（Explanation1）ではなく、短い説明（Explanation2）を選択するように例がモデルをガイドしたことがわかります。

プロンプト:
Below are some examples showing a question, explanation, and answer format:

Question: Why is the sky blue?
Explanation1: The sky appears blue because of Rayleigh scattering, which causes
shorter blue wavelengths of light to be scattered more easily than longer red
wavelengths, making the sky look blue.
Explanation2: Due to Rayleigh scattering effect.
Answer: Explanation2

Question: What is the cause of earthquakes?
Explanation1: Sudden release of energy in the Earth's crust.
Explanation2: Earthquakes happen when tectonic plates suddenly slip or break
apart, causing a release of energy that creates seismic waves that can shake the
ground and cause damage.
Answer: Explanation1

Now, Answer the following question given the example formats above:

Question: How is snow formed?
Explanation1: Snow is formed when water vapor in the air freezes into ice
crystals in the atmosphere, which can combine and grow into snowflakes as they
fall through the atmosphere and accumulate on the ground.
Explanation2: Water vapor freezes into ice crystals forming snow.
Answer:
レスポンス:
Answer: Explanation2
（gemini-2.5-flash）
最適なサンプル数
Gemini などのモデルでは、多くの場合、いくつかの例を使用してパターンを検出できますが、最良の結果を得るには、プロンプトに与える例の数についてテストすることが必要な場合があります。同時に、過剰に多くの例を追加すると、モデルが例に対するレスポンスを過学習し始める可能性があります。

パターンとアンチパターン
例を使用して、従うべきパターンをモデルに示すほうが、回避すべきアンチパターンを例で示すよりも効果的です。

⛔ ネガティブ パターン:

例
Don't end haikus with a question:
Haiku are fun
A short and simple poem
Don't you enjoy them?

✅ ポジティブ パターン:

例
Always end haikus with an assertion:
Haiku are fun
A short and simple poem
A joy to write

一貫性のある形式
レスポンスが望ましくない形式で返されないように、少数ショットの例の構造と形式を同じにする必要があります。プロンプトに少数ショットの例を追加する主な目的の 1 つは、モデルにレスポンスの形式を示すことです。そのため、すべてのサンプルで形式を統一することが重要になります。特に、XML タグ、空白、改行、サンプルの分割子には注意してください。

コンテキストを追加
モデルに必要な情報がすべて与えられていると仮定するのではなく、モデルが問題を解決するために必要な指示や情報をプロンプトに含めることができます。このコンテキスト情報により、モデルは求められている内容について、制約と詳細を理解できます。

次の例では、モデルにルーターのトラブルシューティング ガイダンスを提供するよう求めています。

プロンプト:
What should I do to fix my disconnected wifi? The light on my Google
Wifi router is yellow and blinking slowly.
レスポンス:
A yellow blinking light on your Google Wifi router usually indicates a problem
with the internet connection. Here are some steps to troubleshoot and fix the
issue:
1. Restart your router and modem:
- Unplug your modem from the power outlet and wait for 30 seconds.
- Plug your modem back in and wait for it to fully boot up.
- Unplug your Google Wifi router and wait for 30 seconds.
- Plug your Google Wifi router back in and wait for it to fully boot up.
.....
（gemini-2.5-flash）
レスポンスは一般的なトラブルシューティング情報のように見えますが、ルーターや LED インジケーター ライトのステータスに固有のものではありません。

特定のルーターに関するレスポンスをカスタマイズするには、ルーターのトラブルシューティング ガイドを、レスポンスの提供時に参照するコンテキストとしてプロンプトに追加します。

プロンプト:
Answer the question using the text below. Respond with only the text provided.
Question: What should I do to fix my disconnected wifi? The light on my Google Wifi router is yellow and blinking slowly.

Text:
Color: Slowly pulsing yellow
What it means: There is a network error.
What to do:
Check that the Ethernet cable is connected to both your router and your modem and both devices are turned on. You might need to unplug and plug in each device again.

Color: Fast blinking yellow
What it means: You are holding down the reset button and are factory resetting this device.
What to do:
If you keep holding down the reset button, after about 12 seconds, the light will turn solid yellow. Once it is solid yellow, let go of the factory reset button.

Color: Solid yellow
What it means: Router is factory resetting.
What to do:
This can take up to 10 minutes. When it's done, the device will reset itself and start pulsing white, letting you know it's ready for setup.

Color: Solid red
What it means: Something is wrong.
What to do:
Critical failure. Factory reset the router. If the light stays red, contact Wifi customer support.
レスポンス:
Check that the Ethernet cable is connected to both your router and your modem and both devices are turned on. You might need to unplug and plug in each device again.
（gemini-2.5-flash）
接頭辞を追加する
接頭辞は、プロンプト コンテンツに追加する単語またはフレーズであり、接頭辞を付加する場所に応じてさまざまな目的で使用できます。

入力接頭辞: モデルへの入力の意味的に重要な部分である入力シグナルに接頭辞を追加します。たとえば、接頭辞「English:」と「French:」は 2 つの異なる言語を識別可能にします。
出力接頭辞: 出力はモデルによって生成されますが、プロンプトで出力に接頭辞を追加できます。出力接頭辞は、レスポンスとして期待される内容に関する情報をモデルに与えます。たとえば、出力接頭辞「JSON:」は、出力を JSON 形式にする必要があることをモデルに伝えます。
接頭辞の例: 少数ショット プロンプトでは、例に接頭辞を追加すると、モデルが出力の生成時に使用できるラベルが提供されます。これにより、出力内容の解析が容易になります。
次の例では、「Text:」が入力接頭辞であり、「The answer is:」が出力接頭辞です。

プロンプト:
Classify the text as one of the following categories.
- large
- small
Text: Rhino
The answer is: large
Text: Mouse
The answer is: small
Text: Snail
The answer is: small
Text: Elephant
The answer is:
レスポンス:
The answer is: large
（gemini-2.5-flash）
プロンプトをコンポーネントに分割する
複雑なプロンプトを必要とするユースケースでは、プロンプトをより単純なコンポーネントに分割することで、モデルでこの複雑さを管理できるようになります。

指示を分割する: 1 つのプロンプトに複数の指示を記述するのではなく、指示ごとに 1 つのプロンプトを作成します。ユーザーの入力に基づいて、処理するプロンプトを選択できます。

プロンプトを連結する: 複数の連続したステップを含む複雑なタスクの場合は、各ステップをプロンプトにして、プロンプトを順番に連結します。プロンプトが順番に並んだこの連鎖では、シーケンス内の 1 つのプロンプトの出力が次のプロンプトの入力になります。シーケンス内の最後のプロンプトの出力が最終出力です。

レスポンスを集計する: 集計とは、データのさまざまな部分に対して異なる並列タスクを実行し、結果を集計して最終出力を生成することです。たとえば、データの最初の部分に対して 1 つのオペレーションを実行し、残りのデータに対して別のオペレーションを実行して、結果を集計するようにモデルに指示できます。

モデル パラメータをテストする
モデルに送信する呼び出しの一つ一つに、モデルがどのようにレスポンスを生成するかを制御するパラメータ値が含まれています。このモデルは、パラメータ値によって異なる結果を生成できます。さまざまなパラメータ値を試して、タスクに最適な値を取得します。使用可能なパラメータはモデルに世代によって異なる場合があります。最も一般的なパラメータは次のとおりです。

最大出力トークン: レスポンスで生成できるトークンの最大数を指定します。トークンは約 4 文字です。100 トークンは約 60 ～ 80 語に相当します。

温度: 温度は、トークン選択のランダム性の度合いを制御します。温度は、レスポンス生成時のサンプリングに使用されます。レスポンス生成は、topP と topK が適用された場合に発生します。Temperature が低いほど、自由度や創造性を抑えた決定的な回答が求められるプロンプトに適しています。一方、Temperature が高いと、より多様で創造的な結果を導くことができます。Temperature 0 は決定的であり、最も高い確率のレスポンスが常に選択されることを意味します。

topK: topK パラメータは、モデルが出力用にトークンを選択する方法を変更します。topK が 1 の場合、選択されるトークンは、モデルの語彙内のすべてのトークンで最も確率の高いものであることになります（グリーディ デコードとも呼ばれます）。topK が 3 の場合は、最も確率が高い上位 3 つのトークンから次のトークン選択されることになります（温度を使用します）。トークン選択ステップごとに、確率が最も高い topK トークンがサンプリングされます。その後、トークンは topP に基づいてさらにフィルタリングされ、最終的なトークンは温度サンプリングを用いて選択されます。

topP: topP パラメータは、モデルが出力用にトークンを選択する方法を変更します。トークンは、確率の合計が topP 値と等しくなるまで、確率の高いものから低いものへと選択されます。たとえば、トークン A、B、C の確率が 0.3、0.2、0.1 で、topP 値が 0.5 だとします。このとき、モデルは次のトークンとして A か B を Temperature を使って選択し、C は候補から外します。デフォルトの topP 値は 0.95 です。

stop_sequences: 停止シーケンスを設定して、コンテンツの生成を停止するようモデルに指示します。停止シーケンスには任意の文字列を使用できます。生成されたコンテンツに表示される可能性がある文字列は使用しないでください。

プロンプトの反復処理に関する戦略
プロンプトの設計では、望ましい回答を一貫して得られるようになるまでにイテレーション（反復）が何度か必要になる場合があります。このセクションでは、プロンプトを反復処理する際に試すことができるいくつかのガイダンスについて説明します。

異なるフレーズを使用する: プロンプトで異なる単語やフレーズを使用すると、すべて同じ意味であっても、多くの場合、モデルの応答は異なります。プロンプトから期待される結果が得られない場合は、言い換えてみてください。

Version 1:
How do I bake a pie?

Version 2:
Suggest a recipe for a pie.

Version 3:
What's a good pie recipe?

類似のタスクに切り替える: モデルに対してタスクの指示に従わせることができない場合は、同じ結果が得られる同様のタスクの指示を出してみてください。

このプロンプトは、事前定義されたカテゴリを使用して書籍を分類するようモデルに指示します。

プロンプト:
Which category does The Odyssey belong to:
thriller
sci-fi
mythology
biography
レスポンス:
The Odyssey belongs to the category of **mythology**.

Here's why:

* **Mythology:** The Odyssey tells the story of Odysseus, a hero from Greek mythology, and his
journey home after the Trojan War. It features gods, monsters, and supernatural events common to
Greek mythology.
.....
（gemini-2.5-flash）
レスポンスは正解ですが、モデルがオプションの境界内に収まっていません。また、完全な文ではなく、いずれかのオプションのみを使用して応答するようにモデル化する必要があります。この場合は、指示を多肢選択式の質問として言い換えて、モデルにオプションの選択を求めることができます。

プロンプト:
Multiple choice problem: Which of the following options describes the book The Odyssey?
Options:



thriller

sci-fi

mythology

biography
レスポンス:
The correct answer is mythology.
（gemini-2.5-flash）
プロンプトのコンテンツの順序を変更する: プロンプト内のコンテンツの順序が回答に影響する場合があります。コンテンツの順序を変更して、レスポンスにどう影響するかを確認してみます。

Version 1:
[examples]
[context]
[input]

Version 2:
[input]
[examples]
[context]

Version 3:
[examples]
[input]
[context]
フォールバック レスポンス
フォールバック レスポンスは、プロンプトまたはレスポンスのいずれかが安全フィルタをトリガーした場合に、モデルが返すレスポンスです。フォールバック レスポンスの例としては、「私は言語モデルにすぎないため、それについては対応できません」が挙げられます。

モデルがフォールバック レスポンスを返す場合は、温度を上げてみてください。

非推奨事項
事実に基づく情報の生成についてモデルに頼ることは回避してください。
数学や論理の問題では慎重に使用してください。
生成モデルの仕組み
このセクションでは、生成モデルのレスポンスにランダム性はありますか？それとも確定的ですか？という質問に答えます。

簡単に言うと、どちらも可能です。生成モデルにプロンプトを送信すると、テキスト レスポンスが 2 つのステージで生成されます。最初のステージでは、生成モデルが入力プロンプトを処理し、次に続く可能性のあるトークン（単語）の確率分布を生成します。たとえば、入力テキスト「The dog jumped over the ...」をプロンプトとして指定すると、生成モデルは次に続く可能性のある単語の配列を生成します。

[("fence", 0.77), ("ledge", 0.12), ("blanket", 0.03), ...]
このプロセスは決定的です。生成モデルは、同じプロンプト テキストが入力されるたびに、同じ分布を生成します。

2 番目のステージでは、生成モデルが複数のデコード戦略のいずれかを使用して、これらの分布を実際のテキスト レスポンスに変換します。単純なデコード戦略では、各タイムステップで最も可能性の高いトークンを選択します。このプロセスは常に確定的です。代わりに、モデルから返された分布からランダムにサンプリングしてレスポンスを生成することもできます。このプロセスは確率的（ランダム）です。温度を設定して、このデコード プロセスで許可されるランダム性の度合いを制御します。温度が 0 の場合、最も可能性の高いトークンのみが選択され、ランダム性は発生しません。逆に、温度が高いと、モデルによって選択されるトークンに高いランダム性が導入され、予期しない驚くようなモデル レスポンスが生成されます。



最終更新日 2025-07-24 UTC。

///


Gemini などの生成 AI モデルは、入力と出力をトークンという粒度で処理します。

トークンについて
トークンは、z などの単一の文字や、cat などの単語全体にすることができます。長い単語は複数のトークンに分割されます。モデルで使用されるすべてのトークンのセットは語彙と呼ばれ、テキストをトークンに分割するプロセスはトークン化と呼ばれます。

Gemini モデルの場合、1 個のトークンは約 4 文字に相当します。100 個のトークンは、約 60 ～ 80 ワード（英語）に相当します。

課金が有効になっている場合、Gemini API の呼び出しの費用は、入力トークンと出力トークンの数によって決まるため、トークンのカウント方法を把握しておくと便利です。

Colab でトークンのカウントを試す
Colab を使用してトークンのカウントを試すことができます。

Colab ノートブックを試す
GitHub でノートブックを表示
コンテキスト ウィンドウ
Gemini API で利用可能なモデルのコンテキスト ウィンドウはトークンで測定されます。コンテキスト ウィンドウは、指定できる入力量とモデルが生成できる出力量を定義します。コンテキスト ウィンドウのサイズを確認するには、getModels エンドポイントを呼び出すか、モデルのドキュメントをご覧ください。

次の例では、gemini-1.5-flash モデルの入力上限が約 1,000,000 トークンで、出力上限が約 8,000 トークンであることがわかります。つまり、コンテキスト ウィンドウは 1,000,000 トークンです。


from google import genai

client = genai.Client()
model_info = client.models.get(model="gemini-2.0-flash")
print(f"{model_info.input_token_limit=}")
print(f"{model_info.output_token_limit=}")
# ( e.g., input_token_limit=30720, output_token_limit=2048 )

トークンのカウント
Gemini API の入出力はすべてトークン化されます。これには、テキスト、画像ファイル、その他のテキスト以外のモダリティが含まれます。

トークンは次の方法でカウントできます。

リクエストの入力を指定して count_tokens を呼び出します。
入力のみのトークンの合計数を返します。モデルに入力を送信する前にこの呼び出しを行うと、リクエストのサイズを確認できます。

generate_content を呼び出した後に、response オブジェクトの usage_metadata 属性を使用します。
入力と出力の両方のトークンの合計数 total_token_count を返します。
また、入力と出力のトークン数（prompt_token_count（入力トークン）と candidates_token_count（出力トークン））も個別に返します。

テキスト トークンをカウントする
テキストのみの入力で count_tokens を呼び出すと、入力のみのテキストのトークン数（total_tokens）が返されます。generate_content を呼び出す前にこの呼び出しを行うと、リクエストのサイズを確認できます。

別の方法として、generate_content を呼び出して、response オブジェクトの usage_metadata 属性を使用して、次のように取得することもできます。

入力（prompt_token_count）と出力（candidates_token_count）の個別のトークン数
入力と出力の両方のトークンの合計数（total_token_count）

from google import genai

client = genai.Client()
prompt = "The quick brown fox jumps over the lazy dog."

# Count tokens using the new client method.
total_tokens = client.models.count_tokens(
    model="gemini-2.0-flash", contents=prompt
)
print("total_tokens: ", total_tokens)
# ( e.g., total_tokens: 10 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=prompt
)

# The usage_metadata provides detailed token counts.
print(response.usage_metadata)
# ( e.g., prompt_token_count: 11, candidates_token_count: 73, total_token_count: 84 )

マルチターン（チャット）トークンをカウントする
チャット履歴で count_tokens を呼び出すと、チャットの各ロールのテキストのトークン数の合計（total_tokens）が返されます。

別の方法として、send_message を呼び出して、response オブジェクトの usage_metadata 属性を使用して、次のように取得することもできます。

入力（prompt_token_count）と出力（candidates_token_count）の個別のトークン数
入力と出力の両方のトークンの合計数（total_token_count）
次の会話のターンの大きさを把握するには、count_tokens を呼び出すときに、そのターンを履歴に追加する必要があります。


from google import genai
from google.genai import types

client = genai.Client()

chat = client.chats.create(
    model="gemini-2.0-flash",
    history=[
        types.Content(
            role="user", parts=[types.Part(text="Hi my name is Bob")]
        ),
        types.Content(role="model", parts=[types.Part(text="Hi Bob!")]),
    ],
)
# Count tokens for the chat history.
print(
    client.models.count_tokens(
        model="gemini-2.0-flash", contents=chat.get_history()
    )
)
# ( e.g., total_tokens: 10 )

response = chat.send_message(
    message="In one sentence, explain how a computer works to a young child."
)
print(response.usage_metadata)
# ( e.g., prompt_token_count: 25, candidates_token_count: 21, total_token_count: 46 )

# You can count tokens for the combined history and a new message.
extra = types.UserContent(
    parts=[
        types.Part(
            text="What is the meaning of life?",
        )
    ]
)
history = chat.get_history()
history.append(extra)
print(client.models.count_tokens(model="gemini-2.0-flash", contents=history))
# ( e.g., total_tokens: 56 )

マルチモーダル トークンをカウントする
Gemini API へのすべての入力は、テキスト、画像ファイル、その他のテキスト以外のモダリティを含むトークン化されます。Gemini API による処理中のマルチモーダル入力のトークン化に関する主なポイントは次のとおりです。

Gemini 2.0 では、両方の寸法が 384 ピクセル以下の画像入力は 258 個のトークンとしてカウントされます。1 つまたは両方の寸法が大きい画像は、必要に応じて切り抜かれ、768x768 ピクセルのタイルにスケーリングされます。各タイルは 258 個のトークンとしてカウントされます。Gemini 2.0 より前は、画像は固定の 258 個のトークンを使用していました。

動画ファイルと音声ファイルは、動画は 263 トークン / 秒、音声は 32 トークン / 秒の固定レートでトークンに変換されます。

画像ファイル
テキストと画像の入力で count_tokens を呼び出すと、テキストと画像の合計トークン数が入力のみで返されます（total_tokens）。generate_content を呼び出す前にこの呼び出しを行うと、リクエストのサイズを確認できます。必要に応じて、テキストとファイルで count_tokens を個別に呼び出すこともできます。

別の方法として、generate_content を呼び出して、response オブジェクトの usage_metadata 属性を使用して、次のように取得することもできます。

入力（prompt_token_count）と出力（candidates_token_count）の個別のトークン数
入力と出力の両方のトークンの合計数（total_token_count）
注: File API を使用してアップロードされたファイルを使用する場合も、ファイルをインライン データとして指定する場合も、トークン数は同じになります。
File API からアップロードされた画像を使用する例:


from google import genai

client = genai.Client()
prompt = "Tell me about this image"
your_image_file = client.files.upload(file=media / "organ.jpg")

print(
    client.models.count_tokens(
        model="gemini-2.0-flash", contents=[prompt, your_image_file]
    )
)
# ( e.g., total_tokens: 263 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=[prompt, your_image_file]
)
print(response.usage_metadata)
# ( e.g., prompt_token_count: 264, candidates_token_count: 80, total_token_count: 345 )

画像をインライン データとして提供する例:


from google import genai
import PIL.Image

client = genai.Client()
prompt = "Tell me about this image"
your_image_file = PIL.Image.open(media / "organ.jpg")

# Count tokens for combined text and inline image.
print(
    client.models.count_tokens(
        model="gemini-2.0-flash", contents=[prompt, your_image_file]
    )
)
# ( e.g., total_tokens: 263 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=[prompt, your_image_file]
)
print(response.usage_metadata)
# ( e.g., prompt_token_count: 264, candidates_token_count: 80, total_token_count: 345 )

動画ファイルまたは音声ファイル
音声と動画は、それぞれ次の固定レートでトークンに変換されます。

動画: 1 秒あたり 263 トークン
オーディオ: 1 秒あたり 32 トークン
テキストと動画/音声の入力で count_tokens を呼び出すと、テキストと動画/音声ファイルの合計トークン数が入力のみで返されます（total_tokens）。generate_content を呼び出す前にこの呼び出しを行うと、リクエストのサイズを確認できます。必要に応じて、テキストとファイルで count_tokens を個別に呼び出すこともできます。

別の方法として、generate_content を呼び出して、response オブジェクトの usage_metadata 属性を使用して、次のように取得することもできます。

入力（prompt_token_count）と出力（candidates_token_count）の個別のトークン数
入力と出力の両方のトークンの合計数（total_token_count）
注: File API を使用してアップロードされたファイルを使用する場合も、ファイルをインライン データとして指定する場合も、トークン数は同じになります。

from google import genai
import time

client = genai.Client()
prompt = "Tell me about this video"
your_file = client.files.upload(file=media / "Big_Buck_Bunny.mp4")

# Poll until the video file is completely processed (state becomes ACTIVE).
while not your_file.state or your_file.state.name != "ACTIVE":
    print("Processing video...")
    print("File state:", your_file.state)
    time.sleep(5)
    your_file = client.files.get(name=your_file.name)

print(
    client.models.count_tokens(
        model="gemini-2.0-flash", contents=[prompt, your_file]
    )
)
# ( e.g., total_tokens: 300 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=[prompt, your_file]
)
print(response.usage_metadata)
# ( e.g., prompt_token_count: 301, candidates_token_count: 60, total_token_count: 361 )

システムの指示とツール
システムの手順とツールも、入力のトークン数の合計にカウントされます。

システム指示を使用すると、system_instruction の追加を反映して total_tokens の数が増加します。

関数呼び出しを使用すると、tools の追加を反映して total_tokens の数が加算されます。


最終更新日 2025-07-24 UTC。

