"""指定した時間幅内でRSSフィードの更新をチェックしてTweetするスクリプト"""

import sys
import feedparser
import time
from datetime import datetime, timedelta, timezone
import os
import logging
import json
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
    api_key = os.environ.get("TWITTER_APIKEY")
    api_secret = os.environ.get("TWITTER_APIKEY_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
    if not (api_key and api_secret and access_token and access_token_secret):
        logging.error("Twitter API credentials are not set in environment variables.")
        return None

    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    client = tweepy.API(auth)

    try:
        if in_reply_to_tweet_id:
            tweet = client.update_status(
                status=text, in_reply_to_status_id=in_reply_to_tweet_id, auto_populate_reply_metadata=True
            )
        else:
            tweet = client.update_status(status=text)
        logging.info(f"Tweet posted: {tweet.id}")
        return tweet.id
    except Exception as e:
        logging.error(f"Failed to post tweet: {e}")
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
        TWITTER_APIKEY: X APIキー。
        TWITTER_APIKEY_SECRET: X APIキーシークレット。
        TWITTER_ACCESS_TOKEN: Xアクセストークン。
        TWITTER_ACCESS_TOKEN_SECRET: Xアクセストークンシークレット。
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

    # --- X (Twitter) posting ---
    required_env = ["TWITTER_APIKEY", "TWITTER_APIKEY_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"]
    if all(os.environ.get(env_key) for env_key in required_env):
        if updated:
            for entry in updated_entries:
                tweet_text = f"{entry['title']}\n{entry['link']}"
                tweet_id = post_to_x(tweet_text)
                if tweet_id is None:
                    continue  # Failed to post

                # Reply for summary that includes this title in feed_toc
                for toc_entry in feed_toc.entries:
                    summary = toc_entry.get("summary", "")
                    if entry["title"] in summary:
                        reply_title = toc_entry.get("title", "")
                        reply_link = toc_entry.get("link", "")
                        reply_text = f"関連: {reply_title}\n{reply_link}\n{summary}"
                        post_to_x(reply_text, in_reply_to_tweet_id=tweet_id)
                        time.sleep(1)  # Avoid posting too fast

                time.sleep(2)  # Avoid rate limits
        else:
            logging.warning("No new updates found in the RSS feed.")
    else:
        logging.warning("Twitter API credentials are not set. Skipping X posting.")

    # --- Output for GitHub Actions ---
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
