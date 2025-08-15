"""指定した時間幅内でRSSフィードの更新をチェックしてTweetするスクリプト"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
import re

import feedparser
import tweepy
# from google import genai
# from google.genai import types


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

TWEET_URL_LENGTH = 23
MAX_TWEET_LENGTH = 159  # X（旧Twitter）のツイートの最大文字数
RSS_VIEWER_URL = "https://testkun08080.github.io/kanpo-rss"
DEBUG = os.getenv("DEBUG_CHECK", False)

# def ping_to_gemini(prompt: str) -> str:
#     """Gemini API にプロンプトを送信し、応答を返す関数。

#     Google の Gemini モデル「gemini-2.5-flash」を使用して、
#     指定したプロンプトに基づくテキストを生成します。
#     APIキーは環境変数 `GEMINI_API_KEY` から取得します。
#     処理速度を優先するため "thinking" 機能は無効化しています。

#     Args:
#         prompt (str): Gemini に送信するプロンプト（質問や指示文）。

#     Returns:
#         str: Gemini から返ってきた応答テキスト。

#     Raises:
#         EnvironmentError: 環境変数 `GEMINI_API_KEY` が設定されていない場合。
#         Exception: Gemini API リクエストが失敗した場合など。
#     """
#     api_key = os.environ.get("GEMINI_API_KEY")
#     if not api_key:
#         raise EnvironmentError("環境変数 GEMINI_API_KEY が設定されていません。")

#     try:
#         client = genai.Client(api_key=api_key)
#         response = client.models.generate_content(
#             model="gemini-2.5-flash-lite",
#             contents=prompt,
#             config=types.GenerateContentConfig(
#                 thinking_config=types.ThinkingConfig(thinking_budget=0)  # thinking無効化
#             ),
#         )
#         return response.text
#     except Exception as e:
#         return f"エラーが発生しました: {str(e)}"


def clean_duplicate_tags(text):
    """ポスト用のタグ重複を削除し、本文の改行は保持して整形する関数."""
    # ハッシュタグ抽出（本文から除去するためのリスト）
    tags = re.findall(r"#\S+", text)

    # 重複削除（順序保持）
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)

    # 本文部分（タグは削除するが改行は保持）
    lines = text.splitlines()
    non_tag_lines = []
    for line in lines:
        cleaned_line = re.sub(r"#\S+", "", line)
        non_tag_lines.append(cleaned_line)

    # 本文そのまま結合（余計な改行整形はしない）
    non_tag_text = "\n".join(non_tag_lines).rstrip()

    # 本文 + タグ（本文最後に必ず1行空けてタグ）
    return f"{non_tag_text}\n\n" + "\n".join(unique_tags)


def count_tweet_length(text: str) -> int:
    """
    Twitterの文字数カウント仕様に準拠して、テキストの長さを返す。
    URLはすべて23文字としてカウントする。

    Args:
        text (str): ツイートテキスト

    Returns:
        Optional[int]: 投稿されたツイートのID。失敗した場合はNone。
    """
    # URLを見つけてその部分を23文字に換算
    url_regex = re.compile(r"https?://\S+")
    adjusted_text = text
    for url_match in url_regex.finditer(text):
        url = url_match.group(0)
        adjusted_text = adjusted_text.replace(url, "X" * TWEET_URL_LENGTH, 1)
    return len(adjusted_text)


def post_to_x(text, in_reply_to_tweet_id=None):
    """
    テキストをX（旧Twitter）に投稿します。tweepy（Twitter API v2）を使用します。
    in_reply_to_tweet_idが指定された場合は、リプライとして投稿します。
    投稿に成功した場合はツイートIDを返し、失敗した場合はNoneを返します。

    Args:
        text (str): 投稿するツイートの本文。
        in_reply_to_tweet_id (Optional[int]): リプライ先のツイートID（省略可）。

    Returns:
        Optional[int]: 投稿されたツイートのID。失敗した場合はNone。
    """

    logging.info(f":-------------------Tweet内容:-------------------")

    if in_reply_to_tweet_id:
        text = clean_duplicate_tags(text)
    logging.info(text)

    if DEBUG:
        return 1

    # bearer_token = os.environ.get("BEARER_TOKEN")
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
    if not (api_key and api_secret and access_token and access_token_secret):
        logging.error("Twitter APIの認証情報が環境変数に設定されていません。")
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=True,
    )

    tweet_id = None  # 先に定義しておくことで finally でも参照可能

    try:
        if in_reply_to_tweet_id:
            response = client.create_tweet(
                text=text,
                in_reply_to_tweet_id=in_reply_to_tweet_id,
            )
        else:
            response = client.create_tweet(text=text)

        tweet_id = response.data["id"]

    except Exception as e:
        logging.error(f"Tweetに失敗 tweet: {e}")
        tweet_id = None

    finally:
        logging.info(f"Tweet ID: {tweet_id}")
        logging.info(f":-------------------Tweet内容End:-------------------")

    return tweet_id


def main():
    """
    RSSフィードをチェックし、指定した時間幅内に更新されたエントリを抽出してX（旧Twitter）に投稿します。
    また、関連する要約情報があればリプライとして投稿します。GitHub Actions用の出力も行います。

    コマンドライン引数:
        rss_url (str): チェック対象のRSSフィードURL。
        rss_toc_url (str): 関連情報取得用のRSSフィードURL。
        minutes (int): 何分前からの更新をチェックするか。

    環境変数:
        BEARER_TOKEN: X Bearerトークン。
        X_API_KEY: X APIキー。
        X_API_SECRET: X APIキーシークレット。
        X_ACCESS_TOKEN: Xアクセストークン。
        X_ACCESS_TOKEN_SECRET: Xアクセストークンシークレット。
        GITHUB_OUTPUT: GitHub Actions用の出力ファイルパス（オプション）。

    処理内容:
        1. RSSフィードから指定時間幅内の新規エントリを抽出。
        2. 新規エントリがあればXに投稿し、関連する要約情報があればリプライとして投稿。
        3. GitHub Actions用に更新有無とエントリ情報を出力。

    例外:
        Twitter APIの認証情報が不足している場合は投稿をスキップします。
        新規エントリがない場合は警告を出力します。
    """
    logging.basicConfig(level=logging.INFO)

    rss_url = sys.argv[1]
    rss_toc_url = sys.argv[2]
    minutes = int(sys.argv[3])
    diff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    logging.info(f"RSS URL: {rss_url}")
    logging.info(f"RSS_toc URL: {rss_toc_url}")
    logging.info(f"チェック時間幅: {minutes}分前 = {diff_time.isoformat()}以降")

    feed = feedparser.parse(rss_url)
    feed_toc = feedparser.parse(rss_toc_url)
    updated_entries = []
    updated_toc_entries = []

    # RSSフィードのエントリをチェックして、更新必要分だけにフィルタリングする
    for entry in feed.entries:
        if hasattr(entry, "published_parsed"):
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        else:
            continue  # Skip items without pubDate

        if pub_dt >= diff_time:
            updated_entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "pubDate": pub_dt.strftime("%Y-%m-%d %H:%M:%S, GMT"),
            })

    updated = bool(updated_entries)

    # RSS_TOC(詳細版)もフィードのエントリをチェックして、更新必要分だけにフィルタリングする
    for entry in feed_toc.entries:
        if hasattr(entry, "published_parsed"):
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        else:
            continue  # Skip items without pubDate

        if pub_dt >= diff_time:
            updated_toc_entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "pubDate": pub_dt.strftime("%Y-%m-%d %H:%M:%S, GMT"),
                "categories": [tag["term"] for tag in entry.get("tags", [])],
            })
    logging.info(f"更新されたRSSフィードのエントリ数: {len(updated_entries)}")
    logging.info(f"更新されたRSS_TOCのエントリ数: {len(updated_toc_entries)}")

    # --- X (Twitter) posting ---
    base_tags = ["#官報", "#官報通知"]

    if not DEBUG:
        required_env = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    else:
        required_env = []
    if all(os.environ.get(env_key) for env_key in required_env):
        if updated:
            for entry in updated_entries:
                # ツイート内容を作成
                # extra = "各項目のリンクなどは以下リプライをご覧ください.."
                extra = f"以下RSSビューワーwebで項目ごとで見ることも可能です。。。\n{RSS_VIEWER_URL}"
                tweet_text = f"📚{entry['title']}\n{entry['link']}\n\n{' '.join(base_tags)}\n\n{extra}"
                tweet_id = post_to_x(tweet_text)
                if tweet_id is None:
                    continue

                # feed_tocからタグを抽出
                batch_text = f"{entry['title']}\n{entry['link']}\n\n"
                serch_entries = [e for e in updated_toc_entries if entry["title"] in e.get("summary", "")]
                for toc_entry in serch_entries:
                    summary = toc_entry.get("summary", "")
                    categories = toc_entry.get("categories", [])

                    if entry["title"] not in summary:
                        logging.info(f"{entry['title']} not in {summary}")
                        continue

                    entry_text = ""
                    if categories:
                        categories_tags = " ".join([f"#{cat}" for cat in categories])
                        entry_text = f"{categories_tags}\n"
                    else:
                        continue

                    # このentryを追加したら文字数制限を超えるか？
                    if count_tweet_length(batch_text + entry_text) > MAX_TWEET_LENGTH:
                        post_to_x(batch_text.strip(), in_reply_to_tweet_id=tweet_id)
                        time.sleep(1)
                        batch_text = entry_text
                    else:
                        batch_text += entry_text

                # 最後に残っていたら投稿
                if batch_text:
                    post_to_x(batch_text.strip(), in_reply_to_tweet_id=tweet_id)

                # # feed_tocから関連情報を探してリプライ
                # batch_text = ""
                # serch_entries = [e for e in updated_toc_entries if entry["title"] in e.get("summary", "")]
                # for toc_entry in serch_entries:
                #     summary = toc_entry.get("summary", "")
                #     categories = toc_entry.get("categories", [])

                #     if entry["title"] not in summary:
                #         logging.info(f"{entry['title']} not in {summary}")
                #         continue

                #     reply_title = toc_entry.get("title", "")
                #     reply_link = toc_entry.get("link", "")

                #     if categories:
                #         categories_tags = " ".join([f"#{cat}" for cat in categories])
                #         entry_text = f"✐{reply_title}\n{reply_link}\n{categories_tags}\n\n"
                #     else:
                #         entry_text = f"✐{reply_title}\n{reply_link}\n\n"

                #     # このentryを追加したら文字数制限を超えるか？
                #     if count_tweet_length(batch_text + entry_text) > MAX_TWEET_LENGTH:
                #         post_to_x(batch_text.strip(), in_reply_to_tweet_id=tweet_id)
                #         time.sleep(1)
                #         batch_text = entry_text
                #     else:
                #         batch_text += entry_text

                # # 最後に残っていたら投稿
                # if batch_text:
                #     post_to_x(batch_text.strip(), in_reply_to_tweet_id=tweet_id)

                # リプライの間隔を空ける
                time.sleep(2)
        else:
            logging.warning("RSSフィードのアップデートが見つかりません.")
    else:
        logging.warning("Twwitter APIの認証情報が不足しています。投稿をスキップします。")

    # 結果の出力
    if "GITHUB_OUTPUT" in os.environ:
        output_path = os.environ["GITHUB_OUTPUT"]
        with open(output_path, "a") as fh:
            print(f"updated={'true' if updated else 'false'}", file=fh)
            print(f"entries={json.dumps(updated_entries, ensure_ascii=False)}", file=fh)
    else:
        result = {"updated": updated, "entries": updated_entries}
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
