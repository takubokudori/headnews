# Headnews

RSSを翻訳してSlackに投稿するスクリプト

# Usage

## 登録

```bash
python main.py subscribe [feed URL]
```

## 登録解除

```bash
python main.py unsubscribe [feed URL]
```

## 取得

登録済みRSSの最新記事をすべて取得して投稿する場合

```bash
python main.py get all [webhook URL]
```

特定のRSSのみ取得する場合

```bash
python main.py get [feed URL] [webhook URL]
```
