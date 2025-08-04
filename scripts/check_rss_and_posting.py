"""指定した時間幅内でRSSフィードの更新をチェックしてTweetするスクリプト"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import feedparser
import tweepy


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
    # bearer_token = os.environ.get("BEARER_TOKEN")
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
    if not (api_key and api_secret and access_token and access_token_secret):
        logging.error("Twitter APIの認証情報が環境変数に設定されていません。")
        return None

    # auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    # client = tweepy.API(auth)

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    try:
        if in_reply_to_tweet_id:
            response = client.create_tweet(
                text=text,
                in_reply_to_tweet_id=in_reply_to_tweet_id,
            )
        else:
            response = client.create_tweet(text=text)

        tweet_id = response.data["id"]
        logging.info(f"TweetのポストID: {tweet_id}")

        return tweet_id
    except Exception as e:
        logging.error(f"Tweetに失敗 tweet: {e}")
        return None


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
    required_env = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    if all(os.environ.get(env_key) for env_key in required_env):
        if updated:
            for entry in updated_entries:
                # ツイート内容を作成
                tweet_text = f"{entry['title']}\n{entry['link']}\n\n{' '.join(base_tags)}"
                logging.info(f"Tweet内容: {tweet_text}")
                tweet_id = post_to_x(tweet_text)
                logging.info(f"Tweet ID: {tweet_id}")
                if tweet_id is None:
                    continue

                # feed_tocから関連情報を探してリプライ
                serch_entries = [e for e in updated_toc_entries if entry["title"] in e.get("summary", "")]
                for toc_entry in serch_entries:
                    summary = toc_entry.get("summary", "")
                    categories = toc_entry.get("categories", [])
                    if entry["title"] in summary:
                        reply_title = toc_entry.get("title", "")
                        reply_link = toc_entry.get("link", "")

                        if categories:
                            categories_tags = " ".join([f"#{cat}" for cat in categories])
                            reply_text = f"カテゴリ:{categories}\n{reply_title}\n{reply_link}\n\n{categories_tags}"
                        else:
                            reply_text = f"{reply_title}\n{reply_link}"
                        logging.info(f"reply_text: {reply_text}")
                        post_to_x(reply_text, in_reply_to_tweet_id=tweet_id)
                        time.sleep(1)
                    else:
                        logging.info(f"{entry['title']} not in {summary}")

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
