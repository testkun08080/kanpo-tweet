"""詳細版RSSから当日分を取得し、Geminiで要約してXに投稿するスクリプト"""

import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

import feedparser
import tweepy
from google import genai
from google.genai import errors as genai_errors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

JST = ZoneInfo("Asia/Tokyo")
RSS_VIEWER_URL = "https://kanpo-viewer.com"
MAX_TWEET_LENGTH = 280  # 要約ツイート用
DEBUG = os.getenv("DEBUG_GEMINI_POST", "0").lower() in ("1", "true", "yes")


def get_today_entries_from_toc(rss_toc_url: str, target_date: Optional[datetime] = None) -> List[dict]:
    """詳細版RSSから指定日（省略時は今日・JST）のエントリを返す。"""
    if target_date is None:
        target_date = datetime.now(JST).date()
    elif hasattr(target_date, "date"):
        target_date = target_date.date()

    start_jst = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=JST)
    end_jst = start_jst + timedelta(days=1)
    start_utc = start_jst.astimezone(timezone.utc)
    end_utc = end_jst.astimezone(timezone.utc)

    feed = feedparser.parse(rss_toc_url)
    entries = []

    for entry in feed.entries:
        if not hasattr(entry, "published_parsed"):
            continue
        pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if start_utc <= pub_dt < end_utc:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "description": entry.get("description", ""),
                "summary": entry.get("summary", ""),
                "pubDate": pub_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "categories": [t.get("term", "") for t in entry.get("tags", [])],
            })

    return entries


def summarize_with_gemini(entries: List[dict]) -> str:
    """Gemini APIで当日分の内容を要約する。APIキーは環境変数 GEMINI_API_KEY から取得。"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("環境変数 GEMINI_API_KEY が設定されていません。")

    if not entries:
        return ""

    # 詳細版のテキストを1つにまとめる
    parts = []
    for e in entries:
        parts.append(f"【{e['title']}】\n{e.get('description') or e.get('summary', '')}\nリンク: {e['link']}\n")
    raw_text = "\n".join(parts)

    prompt = f"""以下は本日の官報（詳細版）の内容です。
X（Twitter）に投稿するための短い要約を日本語で作成してください。

条件:
- 280文字以内に収めてください。
- 最後に「#官報 #官報通知」を付けてください。
- 日付や重要な項目名は残してください。箇条書きや改行は自由です。

--- 本日の官報詳細 ---

{raw_text}

--- ここまで ---

上記の条件を満たす投稿文のみを出力してください。"""

    client = genai.Client(api_key=api_key)
    model = (os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash").strip()
    if not model or model == "{model}":
        model = "gemini-2.0-flash"
    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("Gemini が空の要約を返しました。")
            return text
        except genai_errors.ClientError as e:
            last_error = e
            if getattr(e, "code", None) != 429:
                raise
            # 429 の場合はメッセージから待機秒数を取り、リトライ
            wait_sec = 45
            msg = getattr(e, "message", None) or str(getattr(e, "details", ""))
            if msg:
                match = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", msg, re.I)
                if match:
                    wait_sec = max(10, int(float(match.group(1))) + 1)
            logging.warning(
                "Gemini API 429 (クォータ/レート制限)。%d 秒後にリトライ (%d/%d)",
                wait_sec,
                attempt + 1,
                max_retries,
            )
            time.sleep(wait_sec)

    raise last_error


def post_to_x(text: str) -> Optional[str]:
    """テキストをXに投稿する。成功時はツイートID、失敗時はNone。"""
    logging.info("Tweet内容: %s", text[:200] + "..." if len(text) > 200 else text)

    if DEBUG:
        logging.info("DEBUG のため投稿をスキップしました")
        return "debug"

    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
    if not all((api_key, api_secret, access_token, access_token_secret)):
        logging.error("X API の認証情報が環境変数に設定されていません。")
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=True,
    )

    try:
        response = client.create_tweet(text=text)
        tweet_id = response.data.get("id")
        logging.info("Tweet ID: %s", tweet_id)
        return str(tweet_id)
    except Exception as e:
        logging.error("Tweet に失敗: %s", e)
        return None


def main() -> None:
    """詳細版RSSから当日分を取得し、Geminiで要約してXに投稿する。"""
    # 引数: rss_toc_url [YYYY-MM-DD]
    rss_toc_url = sys.argv[1] if len(sys.argv) > 1 else "https://kanpo-viewer.com/feed_toc.xml"
    target_date = None
    if len(sys.argv) > 2:
        try:
            target_date = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
        except ValueError:
            logging.warning("日付の形式が不正です (YYYY-MM-DD): %s", sys.argv[2])

    logging.info("RSS TOC URL: %s", rss_toc_url)

    entries = get_today_entries_from_toc(rss_toc_url, target_date=target_date)
    logging.info("当日分のエントリ数: %d", len(entries))

    if not entries:
        logging.warning("当日の詳細版エントリがありません。投稿をスキップします。")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("updated=false\n")
                f.write("entries=[]\n")
        return

    summary = summarize_with_gemini(entries)
    if len(summary) > MAX_TWEET_LENGTH:
        summary = summary[: MAX_TWEET_LENGTH - 3] + "..."

    tweet_id = post_to_x(summary)

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("updated=true\n")
            f.write(f"tweet_id={tweet_id or ''}\n")
            f.write(f"entries_count={len(entries)}\n")


if __name__ == "__main__":
    main()
