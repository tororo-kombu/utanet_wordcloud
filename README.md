**インストール**
```
pip install requests beautifulsoup4 fugashi[unidic-lite] wordcloud
```
**実行**
```
python utanet_wordcloud.py 12795
```
`12795` は歌ネットのアーティスト番号です。(https://www.uta-net.com/artist/12795/)
 `--limit 3` で数曲だけ試せます。

***
- MeCab ではなく fugashi + unidic-lite にしたので、Windows/Mac どちらでも `pip` だけで動きます。
- 日本語フォントは OS ごとに自動検出します。見つからない場合は `--font` で指定してください。
- アーティストページが複数ページある場合も辿ります。
- 歌詞そのものはファイルに保存せず、単語の集計結果だけを出力します。

**注意**
- 歌ネットのHTML構造が変わっていると、歌詞や曲一覧を取れない場合があります（その際はエラーメッセージが出ます）。
- 歌詞は著作物なので、個人の分析用途にとどめ、`--wait`（既定1.5秒）は短くしすぎないでください。