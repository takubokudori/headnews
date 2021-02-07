#!/usr/bin/python3
"""
MIT License

Copyright (c) 2021 takubokudori
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import requests
import sys
import feedparser
import json
import sqlite3

db_path = 'rss_data.db'


def summarize(s: str):
    return s \
        .replace("\r", "") \
        .replace("\n", " ") \
        .replace("  ", " ") \
        .replace(". ", ".\r\n") \
        .replace(".\n", ".\r\n") \
        .replace(".\t", ".\r\n") \
        .replace("! ", "!\r\n") \
        .replace("!\n", "!\r\n") \
        .replace("!\t", "!\r\n") \
        .replace("? ", "?\r\n") \
        .replace("?\n", "?\r\n") \
        .replace("?\t", "?\r\n") \
        .replace("Fig.\r\n", "Fig. ") \
        .replace("et al.\r\n", "et al. ") \
        .replace("et al,.\r\n", "et al. ")


def translate(text: str):
    resp = requests.get("https://translate.googleapis.com/translate_a/single", params={
        "client": "it",
        "sl": "en",
        "tl": "ja",
        "dt": "t",
        "ie": "UTF-8",
        "oe": "UTF-8",
        "dj": "1",
        "otf": "2",
        "q": text}, headers={
        "Host": "translate.googleapis.com",
        "User-Agent": "GoogleTranslate/5.9.59004 (iPhone; iOS 10.2; ja; iPhone9,1)",
        "Accept": "*/*",
        "Accept-Language": "ja-JP,en-US,*"
    })
    trans = json.loads(resp.text)
    s = ""
    for sentence in trans["sentences"]:
        s += sentence["trans"]
    return s


def get_bunsyou(entry):
    summary = summarize(entry["summary"][3:][:-4])  # pタグ除去してから整形したもの
    trans = translate(summary)  # 翻訳後
    # 翻訳前を投稿したいなら下記の{trans}を{summary}にすること
    return f'''-----------------------
{entry["id"]}
{entry["title"]}
{trans}
'''


class RSS_DB:
    conn = None
    c = None
    rss_id = 0

    def __init__(self):
        self.conn = sqlite3.connect(db_path)
        self.c = self.conn.cursor()

    def subscribe_rss(self, rss_url: str):
        """
        RSSを登録する。URLの重複は許されない
        :param rss_url: str
        :return: str
        """
        self.c.execute('SELECT * FROM rss WHERE url = ?', (rss_url,))
        data = self.c.fetchone()
        if data is None:
            print(f'exec subscribe {rss_url}')
            self.c.execute('INSERT INTO rss(url) VALUES(?)', (rss_url,))
        else:
            print(f'{rss_url} is already subscribed.')

    def unsubscribe_rss_from_url(self, rss_url: str):
        """
        RSSを解除する。
        :param rss_url:
        :return:
        """
        pass

    def is_exists_url(self, url: str):
        data = self.c.execute('SELECT * FROM urls WHERE url = ?', (url,))
        data = data.fetchone()
        return data is not None

    def add_url(self, url):
        """
        URLを登録する
        :param url:
        :return: bool
        """
        self.c.execute('INSERT INTO urls(url,rss_id) VALUES(?,?)', (url, self.rss_id))

    def create_db(self):
        self.c.execute('PRAGMA foreign_keys=true')
        self.c.execute(
            'CREATE TABLE rss('
            'id integer PRIMARY KEY AUTOINCREMENT,'
            'url TEXT,'
            'last_fetched TEXT DEFAULT (DATETIME(\'now\', \'localtime\')))'
        )
        self.c.execute(
            'CREATE TABLE urls('
            'url text PRIMARY KEY,'
            'created_at TEXT DEFAULT (DATETIME(\'now\', \'localtime\')),'
            'rss_id INTEGER,'
            'foreign key (rss_id) references rss(id))'
        )
        self.conn.commit()

    def get_rss_id_from_url(self, rss_url):
        data = self.c.execute('SELECT id FROM rss WHERE url = ?', (rss_url,))
        data = data.fetchone()
        if data is None:
            return None
        else:
            return data[0]

    def commit(self):
        self.conn.commit()

    def get_all_rss(self):
        data = self.c.execute('SELECT url from rss').fetchall()
        return data


rss = RSS_DB()


def subscribe(rss_url):
    global rss
    rss.subscribe_rss(rss_url)
    rss.commit()


def get_rss(rss_url, webhook_url):
    global rss
    rss.subscribe_rss(rss_url)
    rss_id = rss.get_rss_id_from_url(rss_url)
    rss.rss_id = rss_id
    d = feedparser.parse(rss_url)
    print(d['feed']['title'])
    for entry in d['entries']:
        link = entry['link']
        title = entry['title']
        summary = entry['summary']
        published = ""
        if 'published' in entry:
            published = entry['published']
        summary = summary[0:summary.rfind('<')]

        if not rss.is_exists_url(link):
            # 新着記事
            title = translate(title)
            summary = translate(summarize(summary))
            text = f"---------------\n{title}\n{link}\n{published}\n{summary}"
            print(text)
            print("NEW")
            rss.add_url(link)
            rss.commit()
            if webhook_url is not None:
                if not send_to_slack(webhook_url, text):
                    print("Failed to send to slack")
        else:
            text = f"---------------\n{title}\n{link}\n{published}\n{summary}"
            print(text)
            print("EXIST")


def get_all(webhook_url):
    global rss
    urls = rss.get_all_rss()
    print("Try to get_all")
    for url in urls:
        print(f"do {url[0]}")
        try:
            get_rss(url[0], webhook_url)
        except:
            print(f"Failed to get rss {url[0]}")


def send_to_slack(webhook_url, text):
    resp = requests.post(webhook_url,
                         data={"payload": {"text": text}.__str__()})
    return resp.status_code == 200


def usage():
    print(f"./{sys.argv[0]} subscribe [RSS URL]")
    print(f"./{sys.argv[0]} unsubscribe [RSS URL]")
    print(f"./{sys.argv[0]} get [RSS URL] [webhook url]")
    print(f"./{sys.argv[0]} get [RSS ID] [webhook url]")
    print(f"./{sys.argv[0]} get all [webhook url]")
    exit()


# rss.py subscribe https://example.com/feed
if __name__ == '__main__':
    print("rss.py")
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]
    print(f"cmd is {cmd}")

    if cmd == "subscribe":
        subscribe(sys.argv[2])
    elif cmd == "unsubscribe":
        print("Unimplemented")
        exit(-1)
    elif cmd == "get":
        if sys.argv[2] == "all":
            get_all(sys.argv[3])
        elif len(sys.argv) > 3:
            get_rss(sys.argv[2], sys.argv[3])
        else:
            get_rss(sys.argv[2], None)
    elif cmd == "create":
        RSS_DB().create_db()
    else:
        usage()

# main(sys.argv[1], sys.argv[2], sys.argv[3])
