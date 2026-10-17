#!/usr/bin/env python3
"""
歌ネット(uta-net.com)のアーティスト番号を入力すると、
全曲の歌詞を取得 → 形態素解析 → 頻出単語CSV + ワードクラウド画像を出力します。

使い方:
    pip install requests beautifulsoup4 fugashi[unidic-lite] wordcloud
    python utanet_wordcloud.py 12795 米津玄師
    python utanet_wordcloud.py 12795 米津玄師 --wait 2 --top 50 --font "C:/Windows/Fonts/YuGothM.ttc"

出力:
    output/{アーティスト番号}_{アーティスト名}/{アーティスト番号}_{アーティスト名}_wordcloud.png
    output/{アーティスト番号}_{アーティスト名}/{アーティスト番号}_{アーティスト名}_words.csv

※ 歌詞は著作物です。取得した歌詞は保存せず、個人利用の分析にのみ使い、
   サーバーに負荷をかけないよう待機時間(--wait)を必ず入れてください。
"""
import argparse
import csv
import platform
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import bs4
import requests
from fugashi import Tagger
from wordcloud import WordCloud

BASE = "https://www.uta-net.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (personal lyrics analysis script)"}

# 除外する単語（必要に応じて追加）
STOPWORDS = {"する", "いる", "ある", "なる", "れる", "られる", "せる", "ない",
             "ん", "の", "こと", "もの", "よう", "ため", "それ", "これ", "あれ"}
KEEP_POS = {"名詞", "動詞", "形容詞", "副詞"}
SKIP_POS2 = {"非自立可能", "数詞", "助数詞", "固有名詞"}  # 固有名詞も除外したくなければここから削除


def fetch(url: str) -> str:
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()
    res.encoding = res.apparent_encoding if not res.encoding else res.encoding
    return res.text


def collect_song_urls(artist_id: str, wait: float) -> list[str]:
    """アーティストページ（ページネーション含む）から曲URLを集める"""
    start = f"{BASE}/artist/{artist_id}/"
    queue, seen_pages, songs = [start], set(), []
    while queue:
        page = queue.pop(0)
        if page in seen_pages:
            continue
        seen_pages.add(page)
        soup = bs4.BeautifulSoup(fetch(page), "html.parser")
        # サイドのランキング欄（他アーティストの曲）を除外
        for box in soup.select(".side-ranking-box"):
            box.decompose()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.match(r"^/song/\d+/?$", href):
                u = urljoin(BASE, href)
                if u not in songs:
                    songs.append(u)
            elif re.match(rf"^/artist/{artist_id}/\d+/\d+/?$", href):
                queue.append(urljoin(BASE, href))
        time.sleep(wait)
    return songs


def extract_lyrics(html: str) -> str:
    soup = bs4.BeautifulSoup(html, "html.parser")
    node = soup.select_one("#kashi_area") or soup.select_one('[itemprop="text"]')
    if not node:
        return ""
    text = node.get_text(separator=" ")
    text = re.sub(r"[A-Za-z0-9０-９Ａ-Ｚａ-ｚ]", "", text)
    text = re.sub(r"[\s　♪・…！？!?\-/:;,.、。「」『』（）()＜＞<>~〜]", " ", text)
    return text


def tokenize(tagger: Tagger, text: str) -> list[str]:
    words = []
    for w in tagger(text):
        f = w.feature
        if f.pos1 not in KEEP_POS or f.pos2 in SKIP_POS2:
            continue
        base = (getattr(f, "lemma", None) or w.surface).split("-")[0]
        if base in STOPWORDS or len(base) < 2 and re.fullmatch(r"[ぁ-ん]", base):
            continue
        words.append(base)
    return words


def find_font(user_font: str | None) -> str:
    if user_font:
        return user_font
    candidates = {
        "Windows": ["C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/meiryo.ttc"],
        "Darwin": ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                   "/System/Library/Fonts/Hiragino Sans GB.ttc",
                   "/Library/Fonts/Arial Unicode.ttf"],
        "Linux": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                  "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
                  "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"],
    }[platform.system()] if platform.system() in ("Windows", "Darwin", "Linux") else []
    for c in candidates:
        if Path(c).exists():
            return c
    sys.exit("日本語フォントが見つかりません。--font でフォントファイルを指定してください。")


def main():
    p = argparse.ArgumentParser(description="歌ネット アーティスト歌詞 単語分析")
    p.add_argument("artist_id", help="歌ネットのアーティスト番号（例: 12795）")
    p.add_argument("artist_name", help="アーティスト名（出力フォルダ・ファイル名に使用。例: 米津玄師）")
    p.add_argument("--wait", type=float, default=1.5, help="リクエスト間の待機秒数")
    p.add_argument("--top", type=int, default=30, help="コンソールに表示する上位単語数")
    p.add_argument("--font", help="日本語フォントのパス")
    p.add_argument("--out", default="output", help="出力ルートディレクトリ")
    p.add_argument("--limit", type=int, default=0, help="取得曲数の上限（テスト用、0で全曲）")
    args = p.parse_args()

    safe_name = re.sub(r'[\\/:*?"<>|\s]+', "_", args.artist_name).strip("_")
    prefix = f"{args.artist_id}_{safe_name}"
    out = Path(args.out) / prefix
    out.mkdir(parents=True, exist_ok=True)

    print(f"{args.artist_name}（{args.artist_id}）の曲一覧を取得中…")
    urls = collect_song_urls(args.artist_id, args.wait)
    if args.limit:
        urls = urls[: args.limit]
    if not urls:
        sys.exit("曲が見つかりませんでした。アーティスト番号を確認してください。")
    print(f"{len(urls)} 曲を検出")

    tagger = Tagger()
    counter: Counter = Counter()
    ok = 0
    for i, u in enumerate(urls, 1):
        try:
            text = extract_lyrics(fetch(u))
        except requests.RequestException as e:
            print(f"  [{i}/{len(urls)}] 失敗: {u} ({e})")
            time.sleep(args.wait)
            continue
        if text:
            counter.update(tokenize(tagger, text))
            ok += 1
        print(f"  [{i}/{len(urls)}] {u}")
        time.sleep(args.wait)

    if not counter:
        sys.exit("歌詞を取得できませんでした（サイト構造が変わった可能性があります）。")

    csv_path = out / f"{prefix}_words.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["単語", "出現数"])
        w.writerows(counter.most_common())

    wc = WordCloud(font_path=find_font(args.font), background_color="white",
                   width=1200, height=800).generate_from_frequencies(counter)
    png_path = out / f"{prefix}_wordcloud.png"
    wc.to_file(str(png_path))

    print(f"\n解析曲数: {ok}/{len(urls)}  異なり語数: {len(counter)}")
    print(f"--- 頻出単語 TOP{args.top} ---")
    for word, n in counter.most_common(args.top):
        print(f"{word}\t{n}")
    print(f"\n出力: {csv_path}\n      {png_path}")


if __name__ == "__main__":
    main()