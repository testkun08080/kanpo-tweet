# 📢 官報RSS-Tweet

## 📌 概要
[官報公式サイト](https://www.kanpo.go.jp/index.html) にはTweetで告知するアカウントなどが存在していないようなので、tweet用のbot作成を行いました。  

✅ [官報RSS](https://github.com/testkun08080/kanpo-rss) を使って、  
毎日およそ8:40分に自動でTweetします。
アカウントはこちら、https://x.com/dailykanpo
---

## ローカルテスト用
```zsh
RSS_URL='https://raw.githubusercontent.com/testkun08080/kanpo-rss/refs/heads/main/feed.xml'
MINUTES="720"
uv run scripts/check_rss.py "$RSS_URL" "$MINUTES"
```

```zsh
X_API_KEY="api-key"
X_API_SECRET="api-secret"
X_ACCESS_TOKEN="access-token"
X_ACCESS_TOKEN_SECRET="access-token-secret"
RSS_URL='https://raw.githubusercontent.com/testkun08080/kanpo-rss/refs/heads/main/feed.xml'
RSS_TOC_URL='https://raw.githubusercontent.com/testkun08080/kanpo-rss/refs/heads/main/feed_toc.xml'

#GEMINI_API_KEY='gemni_api_key'

# 720分以内のフィードをチェック
uv run scripts/check_rss_and_posting.py "$RSS_URL" "$RSS_TOC_URL" 720
```

## 💬 補足
- 本tweetは非公式のものであり、正確性を保証するものではありません。
- 利用に関して問題があれば[Issue](https://github.com/testkun08080/kanpo-rss/issues)からご連絡ください。

---

## 📄 ライセンス

MIT License © [testkun08080](https://github.com/testkun08080)

## 😀 貢献
バグ報告や機能リクエスト、プルリクエストは大歓迎です。問題や提案がある場合は、GitHubのIssueを作成してください。
その他に、いいなと思ったらスターもらえるとシンプルに喜びます。もしくはコーヒー奢ってもらえるとより喜びます。
