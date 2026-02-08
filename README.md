# 📢 官報RSS-Tweet

## 📌 概要

[官報公式サイト](https://www.kanpo.go.jp/index.html) にはTweetで告知するアカウントなどが存在していないようなので、tweet用のbot作成を行いました。

✅ [官報RSS](https://github.com/testkun08080/kanpo-rss) を使って、  
毎日およそ8:40分に自動でTweetします。
アカウントはこちら、https://x.com/dailykanpo

---

## ローカルでテストする

### 1. セットアップ

```zsh
# リポジトリをクローン
git clone https://github.com/testkun08080/kanpo-tweet.git
cd kanpo-tweet

# Python 3.9+ で仮想環境を作成
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 依存関係をインストール
pip install feedparser tweepy twitter-text-parser "google-genai"
```

### 2. 環境変数（.env または export）

投稿テストには X（Twitter）API の認証情報が必要です。Gemini 要約を使う場合は `GEMINI_API_KEY` も必要です。

| 変数名                  | 説明                                 | 必要なスクリプト |
| ----------------------- | ------------------------------------ | ---------------- |
| `X_API_KEY`             | X API キー                           | 投稿する場合     |
| `X_API_SECRET`          | X API シークレット                   | 投稿する場合     |
| `X_ACCESS_TOKEN`        | X アクセストークン                   | 投稿する場合     |
| `X_ACCESS_TOKEN_SECRET` | X アクセストークンシークレット       | 投稿する場合     |
| `GEMINI_API_KEY`        | Gemini API キー（AIza...）           | Gemini 要約投稿  |
| `GEMINI_MODEL`          | モデル名（省略時: gemini-2.0-flash） | Gemini 要約投稿  |

`.env` を使う場合（**Git にコミットしないこと**）:

```zsh
# 例
RSS_URL='https://kanpo-viewer.com/feed.xml'
RSS_TOC_URL='https://kanpo-viewer.com/feed_toc.xml'
X_API_KEY="your-api-key"
X_API_SECRET="your-api-secret"
X_ACCESS_TOKEN="your-access-token"
X_ACCESS_TOKEN_SECRET="your-access-token-secret"
GEMINI_API_KEY="AIza..."
GEMINI_MODEL="gemini-2.0-flash"
```

読み込み例:

```zsh
set -a && source .env && set +a
```

### 3. 通常の RSS 投稿（詳細版の項目ごとリンク付き）

**投稿せずに実行する（推奨）:** スクリプト内の `DEBUG = True` のときは X には投稿されません。

```zsh
MINUTES="720"
RSS_URL='https://kanpo-viewer.com/feed.xml'
RSS_TOC_URL='https://kanpo-viewer.com/feed_toc.xml'

# 環境変数が未設定なら .env を読み込んでから
# set -a && source .env && set +a

python scripts/check_rss_and_posting.py "$RSS_URL" "$RSS_TOC_URL" "$MINUTES"
```

- `MINUTES`: 何分以内に更新されたエントリを対象にするか（例: 720 = 12時間）
- 実行すると RSS を取得し、更新分のツイート文を組み立ててログに出力します（DEBUG 時は投稿しない）

### 4. 当日分を Gemini で要約して 1 ツイートで投稿

**投稿せずに実行する:** `DEBUG_GEMINI_POST=1` を付けると X には投稿されず、要約まで実行してログに出力します。

```zsh
# .env を読み込む場合
set -a && source .env && set +a

# 投稿せずに要約まで実行（推奨）
DEBUG_GEMINI_POST=1 python scripts/check_rss_gemini_and_posting.py "https://kanpo-viewer.com/feed_toc.xml"
```

- 引数1: 詳細版 RSS の URL（省略時は上記 URL）
- 引数2（任意）: 対象日 `YYYY-MM-DD`（省略時は当日 JST）

**実際に投稿する場合:** `DEBUG_GEMINI_POST` を付けず、X の認証情報を設定して実行します。

```zsh
python scripts/check_rss_gemini_and_posting.py "https://kanpo-viewer.com/feed_toc.xml"
```

### 5. RSS の更新チェックのみ（投稿しない）

```zsh
python scripts/check_rss.py "https://kanpo-viewer.com/feed.xml" 720
```

- 第1引数: RSS URL、第2引数: 分数
- 標準出力に更新有無とエントリ一覧が JSON で出ます。

---

## 💬 補足

- 本tweetは非公式のものであり、正確性を保証するものではありません。
- 利用に関して問題があれば[Issue](https://github.com/testkun08080/kanpo-rss/issues)からご連絡ください。

---

## 📄 ライセンス

MIT License © [testkun08080](https://github.com/testkun08080)

## 😀 貢献

バグ報告や機能リクエスト、プルリクエストは大歓迎です。問題や提案がある場合は、GitHubのIssueを作成してください。
その他に、いいなと思ったらスターもらえるとシンプルに喜びます。もしくはコーヒー奢ってもらえるとより喜びます。
