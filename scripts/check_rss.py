"""指定した時間幅内でRSSフィードの更新をチェックするスクリプト"""

import sys
import feedparser
import time
from datetime import datetime, timedelta, timezone
import os
import logging
import json


def main():
    """指定した時間幅内でRSSフィードのエントリをチェックします。

    引数:
        sys.argv[1]: RSSフィードのURL
        sys.argv[2]: 時間幅（分）
    """
    logging.basicConfig(level=logging.INFO)

    rss_url = sys.argv[1]
    minutes = int(sys.argv[2])
    window_start = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    logging.info(f"RSS URL: {rss_url}")
    logging.info(f"チェック時間幅: {minutes}分前 = {window_start.isoformat()}以降")

    feed = feedparser.parse(rss_url)
    updated_entries = []

    for entry in feed.entries:
        if hasattr(entry, "published_parsed"):
            logging.info(f"公開日時: {entry.published}")
            pub_datetime = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        else:
            continue  # pubDateがない場合はスキップ

        if pub_datetime >= window_start:
            updated_entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "pubDate": pub_datetime.strftime("%Y-%m-%d %H:%M:%S, GMT"),
            })

    is_updated = bool(updated_entries)

    # 結果の出力
    if "GITHUB_OUTPUT" in os.environ:
        output_path = os.environ["GITHUB_OUTPUT"]
        logging.info("GITHUB_OUTPUT環境変数が設定されています。出力を行います。")
        with open(output_path, "a") as file_handle:
            print(f"updated={'true' if is_updated else 'false'}", file=file_handle)
            print(f"entries={json.dumps(updated_entries, ensure_ascii=False)}", file=file_handle)

        logging.info(f"GITHUB_OUTPUTのパス: {output_path}")
        try:
            with open(output_path, "r") as file_handle:
                content = file_handle.read()
            logging.info("GITHUB_OUTPUTファイルの中身:")
            logging.info(content)
        except Exception as error:
            logging.error(f"ファイル読み込みエラー: {error}")
    else:
        logging.info("ローカルで起動しているか、GITHUB_OUTPUT環境変数が未設定です。標準出力します。")
        result = {"updated": is_updated, "entries": updated_entries}
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
