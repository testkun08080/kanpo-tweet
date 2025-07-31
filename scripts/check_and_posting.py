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
    Post a tweet to X (Twitter) using tweepy (Twitter API v2).
    If in_reply_to_tweet_id is given, posts as a reply.
    Returns tweet id or None if failed.
    """
    # OAuth 1.0a User Context認証（Twitter/X公式が要求）
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
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
            continue  # pubDateがないitemはスキップ

        if pub_dt >= diff_time:
            updated_entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "pubDate": pub_dt.strftime("%Y-%m-%d %H:%M:%S, GMT"),
            })

    updated = bool(updated_entries)

    # --- X (Twitter) posting ---
    # 必要な認証情報がある場合のみ投稿
    required_env = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    if all(os.environ.get(k) for k in required_env):
        for entry in updated_entries:
            tweet_text = f"{entry['title']}\n{entry['link']}"
            tweet_id = post_to_x(tweet_text)
            if tweet_id is None:
                continue  # Failed to post

            # For feed_toc, reply for summary that includes this title
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
