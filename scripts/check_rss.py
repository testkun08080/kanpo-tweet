import sys
import feedparser
import time
from datetime import datetime, timedelta, timezone
import os
import logging
import json


def main():
    logging.basicConfig(level=logging.INFO)

    rss_url = sys.argv[1]
    minutes = int(sys.argv[2])
    window = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    logging.info(f"RSS URL: {rss_url}")
    logging.info(f"チェック時間幅: {minutes}分前 = {window.isoformat()}以降")

    feed = feedparser.parse(rss_url)
    updated_entries = []

    for entry in feed.entries:
        if hasattr(entry, "published_parsed"):
            logging.info(f"公開日時: {entry.published}")
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        else:
            continue  # pubDateがないitemはスキップ

        if pub_dt >= window:
            updated_entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "pubDate": pub_dt.strftime("%Y-%m-%d %H:%M:%S, GMT"),
            })

    updated = bool(updated_entries)

    # Make outputs
    if "GITHUB_OUTPUT" in os.environ:
        output_path = os.environ["GITHUB_OUTPUT"]
        logging.info("GITHUB_OUTPUT 環境変数が設定されています。出力を行います。")
        with open(output_path, "a") as fh:
            print(f"updated={'true' if updated else 'false'}", file=fh)
            print(f"entries={json.dumps(updated_entries, ensure_ascii=False)}", file=fh)

        logging.info(f"GITHUB_OUTPUT のパス: {output_path}")
        try:
            with open(output_path, "r") as f:
                content = f.read()
            logging.info("GITHUB_OUTPUT ファイルの中身:")
            logging.info(content)
        except Exception as e:
            logging.error(f"ファイル読み込みエラー: {e}")
    else:
        logging.info("ローカルで起動しているか、GITHUB_OUTPUT 環境変数が未設定です。標準出力します。")
        result = {"updated": updated, "entries": updated_entries}
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
