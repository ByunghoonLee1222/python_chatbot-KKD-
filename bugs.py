# -*- coding: utf-8 -*-
import re

import urllib.request

from bs4 import BeautifulSoup
from flask import Flask
from slack import WebClient
from slackeventsapi import SlackEventAdapter
from config2 import *



app = Flask(__name__)
# /listening 으로 슬랙 이벤트를 받습니다.
slack_events_adaptor = SlackEventAdapter(SLACK_SIGNING_SECRET, "/listening", app)
slack_web_client = WebClient(token=SLACK_TOKEN)

def _crawl_music_chart(text):
    if not "music" in text:
        return "`@<봇이름> music` 과 같이 멘션해주세요."
    message=[]
    # 여기에 함수를 구현해봅시다.
    url = "https://music.bugs.co.kr/chart/track/realtime/total?wl_ref=M_contents_03_01"
    sourcecode = urllib.request.urlopen(url).read()
    soup = BeautifulSoup(sourcecode, "html.parser")
    ranktable = soup.find("table", class_="list trackList byChart")
    for tr in ranktable.find_all("tr"):
        title = tr.find("p", class_="title")
        artist = tr.find("p", class_="artist")
        if title is None:
            continue
        rank = tr.find("div", class_="ranking").find("strong")
        artist = artist.find("a")
        temp = rank.get_text().strip() + "\t" + title.get_text().strip() + "\t" + artist['title'].strip()
        message.append(temp)
        if rank.get_text().strip() == '10':
            break
    message = '\n'.join(message)
    return message



# 챗봇이 멘션을 받았을 경우
@slack_events_adaptor.on("app_mention")
def app_mentioned(event_data):
    channel = event_data["event"]["channel"]
    text = event_data["event"]["text"]
    message = _crawl_music_chart(text)
    slack_web_client.chat_postMessage(
        channel=channel,
        text=message
    )


# / 로 접속하면 서버가 준비되었다고 알려줍니다.
@app.route("/", methods=["GET"])
def index():
    return "<h1>Server is ready.</h1>"


if __name__ == '__main__':
    app.run('0.0.0.0', port=5001)
