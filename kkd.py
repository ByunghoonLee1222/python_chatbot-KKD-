# -*- coding: utf-8 -*-
import re
import urllib.request
from slack.web.classes import extract_json
from slack.web.classes.blocks import *
import http
from bs4 import BeautifulSoup
from urllib import parse
from flask import Flask
from slack import WebClient
import sys
from slackeventsapi import SlackEventAdapter
import random
import threading
import time
from config import *

from slack_progress import SlackProgress


app = Flask(__name__)
# /listening 으로 슬랙 이벤트를 받습니다.
slack_events_adaptor = SlackEventAdapter(SLACK_SIGNING_SECRET, "/listening", app)
slack_web_client = WebClient(token=SLACK_TOKEN)
slack_web_client2 = WebClient(token=SLACK_TOKEN)

# STATUS
WAITING = 0
THINKING = 1


def get_meaning_of_word(word):
    text = parse.quote(word)
    if text.isspace():
        return
    url = 'https://wordrow.kr/%EC%9D%98%EB%AF%B8/' + text

    try:
        sourcecode = urllib.request.urlopen(url).read()

    except http.client.IncompleteRead as e:
        sourcecode = e.partial

    sop = BeautifulSoup(sourcecode, "html.parser")
    word_list = sop.find("h3", class_="card-caption").get_text()
    return word_list


def send_one_line(channel, text):
    time.sleep(0.25)
    slack_web_client.chat_postMessage(
        channel=channel,
        text=text,
    )


def send_multi_line(channel, text_list):
    block = SectionBlock(
        text='\n'.join(text_list)
    )
    my_blocks = [block]
    slack_web_client.chat_postMessage(
        channel=channel,
        blocks=extract_json(my_blocks),
    )


def get_last_char(text):
    du_em = {'라': '나', '락': '낙', '란': '난',
             '랄': '날', '람': '남', '랍': '납',
             '랑': '낭', '래': '내', '랭': '냉',
             '략': '약', '냑': '약', '냥': '양',
             '녀': '여', '려': '여', '녁': '역',
             '력': '역', '년': '연', '련': '연',
             '녈': '열', '렬': '열', '념': '염',
             '렴': '염', '렵': '엽', '녕': '영',
             '녜': '예', '뢰': '뇌', '뉵': '육',
             '례': '예', '뇨': '요', '륜': '윤',
             '로': '노', '료': '요', '률': '율',
             '록': '녹', '룡': '용', '륭': '융',
             '론': '논', '루': '누', '륵': '늑',
             '롱': '논', '리': '이', '립': '입',
             '릉': '능', '린': '인', '니': '이',
             '림': '임'}

    if len(text) == 3:
        if text[2] in du_em:
            last_text = du_em[text[2]]
        else:
            last_text = text[2]
    else:
        if text in du_em:
            last_text = du_em[text]
        else:
            last_text = text
    return last_text


# 해당 글자로 시작하는 단어 찾기
def get_random_word(one_character, level):
    url = "https://www.wordrow.kr/"
    part_url = "시작하는-말/" + one_character
    en_url = parse.quote(part_url) + "/%EC%84%B8%20%EA%B8%80%EC%9E%90"
    url += en_url

    temp_word_list = []
    try:
        source_code = urllib.request.urlopen(url).read()
    except http.client.IncompleteRead as e:
        source_code = e.partial

    soup = BeautifulSoup(source_code, "html.parser")

    for h3 in soup.find_all("h3", class_="card-caption"):
        word = h3.find("a")["href"][-3:]
        if word[2] == "다" or word[2] == "히":
            continue
        if word[0] == one_character:
            temp_word_list.append(h3.find("a")["href"][-3:])
        else:
            continue
    print("컴퓨터 패배 확률 %.2f%% (%d / %d)" % (((6-level)*2)*100/(len(temp_word_list)+(6-level)*2), (6-level)*2, len(temp_word_list)+(6-level)*2))
    for i in range((6-level)*2):
        temp_word_list.append("모르겠다")

    return random.choice(temp_word_list)


def is_exist_word(text):
    if not len(text) == 3:
        return "세글자를 입력해주세요."
    # 여기에 함수를 구현해봅시다.
    en_text = parse.quote(text)
    url = "https://stdict.korean.go.kr/search/searchResult.do?pageSize=10&searchKeyword="+en_text
    sourcecode = urllib.request.urlopen(url).read()
    soup = BeautifulSoup(sourcecode, "html.parser")
    search = soup.find("div", class_="contentData wrap_container")
    if search is not None:
        return True
    sam = soup.find("span", class_="t_gray")
    if sam is not None:
        return True
    else:
        return False

    return message


# Status
WAIT_START = 0
USER_TURN = 1
BOT_TURN = 2
USER_WIN = 3
BOT_WIN_first_wrong = 4
BOT_WIN_not_exist = 5
BOT_WIN_default = 6

# Loading
LOADING = 1
DONE = 0

info_dict = {
    "user_send_count": 0,   # 해당 프로그램을 실행한 후 유저가 보낸 메세지 개수
    "KKD_count": 0,         # 유저가 쿵쿵따하며 보낸 메세지 개수
    "Status": WAIT_START,
    "last_word_of_bot": "",
    "level_setting": 3,     # MAX Level = 5, Min Level = 1, Default Level = 3
    "Loading": DONE
}


def user_info_dict_reset(user):
    user["user_send_count"] = 0
    user["KKD_count"] = 0
    user["Status"] = WAIT_START
    user["last_word_of_bot"] = ""
    user["level_setting"] = 3

def user_info_dict_reset2(user):
    user["user_send_count"] = 1
    user["KKD_count"] = 0
    user["Status"] = WAIT_START
    user["last_word_of_bot"] = ""
    user["level_setting"] = 3

temptemp = "asdasd"
new_input = False
# 챗봇이 멘션을 받았을 경우
@slack_events_adaptor.on("app_mention")
def app_mentioned(event_data):
    global new_input
    new_input = True
    channel = event_data["event"]["channel"]        # 사용자가 있는 채널
    text = event_data["event"]["text"][13:]         # 사용자가 보낸 내용
    text_id = event_data["event"]["client_msg_id"]

    global temptemp
    if text_id == temptemp:
        return
    temptemp = text_id

    # pbar = sp.new(total=500)  # create new bar where 100% == pos 500
    # pbar.pos = 100  # 20% complete
    # time.sleep(0.3)
    # pbar.pos = 500  # 100% complete
    # 해당 유저가 메세지 보낸 횟수 카운트
    if event_data["event"]['user'] not in user_dict:
        user_dict[event_data["event"]['user']] = info_dict     # user id 를 key 로 하는 dict
        user_dict[event_data["event"]['user']]["user_send_count"] = 1
    else:
        user_dict[event_data["event"]['user']]["user_send_count"] += 1

    if user_dict[event_data["event"]['user']]["Status"] == BOT_TURN:
        slack_web_client2.chat_postMessage(
            channel=channel,
            text="`경고`\n 연속해서 메세지를 보내지 마세요"
        )
        return
    # 시작 문구 출력
    if "시작" in text and user_dict[event_data["event"]['user']]["KKD_count"] == 0:
        user_info_dict_reset2(user_dict[event_data["event"]['user']])
        slack_web_client.chat_postMessage(
            channel=channel,
            text="*현재 난이도* : " + str(user_dict[event_data["event"]['user']]["level_setting"]) + "\n`쿵쿵따라~ 쿵쿵따`\n```\n3글자 아무단어나 입력해!\n```\n난이도 설정하려면 '@KungKungDDA 난이도3'이라 입력하세요 (난이도는 1~5만 입력하세요)",
        )
        user_dict[event_data["event"]['user']]["Status"] = USER_TURN
    # 튜토리얼 출력
    elif user_dict[event_data["event"]['user']]["user_send_count"] == 1 or len(text) is 0 or 'help' in text:
        fields = ["<@" + event_data["event"]['user'] + "> `챗봇과 1:1 쿵쿵따 룰`",
                  "*현재 난이도* : " + str(user_dict[event_data["event"]['user']]["level_setting"]),
                  "```",
                  " 단어는 항상 3글자여야 한다.",
                  " 사용자는 5초 이내로 대답해야한다!",
                  " 사용자는 연속해서 단어를 입력하면 패배한다!",
                  " 사용자는 뛰어쓰기가 있는 단어를 사용하면 안된다!",
                  " 두음법칙 가능 (ex : 락 -> 낙)",
                  "```",
                  " 난이도 설정하려면 '@KungKungDDA 난이도3'이라 입력하세요 (난이도는 1~5만 입력하세요)",
                  "_시작하시려면 '@KungKungDDA 시작'이라 입력하세요_"]
        th8 = threading.Thread(target=send_multi_line, args=(channel, fields))
        th8.start()
        th8.join()
        user_dict[event_data["event"]['user']]["Status"] = WAIT_START

    elif "난이도" in text and len(text) == 4:
        user_dict[event_data["event"]['user']]["level_setting"] = int(text[-1])
        slack_web_client.chat_postMessage(
            channel=channel,
            text="_난이도가 " + str(user_dict[event_data["event"]['user']]["level_setting"]) + "로 변경되었습니다._\n_시작하시려면 '@KungKungDDA 시작'이라 입력하세요_",
        )
    # 에러 처리
    elif len(text) != 3 or " " in text:
        slack_web_client.chat_postMessage(
            channel=channel,
            text="`공백이 있거나 3글자가 아니면 안돼~`",
        )
        user_dict[event_data["event"]['user']]["Status"] = BOT_WIN_default
    # 사용자 정상 입력시
    elif user_dict[event_data["event"]['user']]["Status"] == USER_TURN:
        if user_dict[event_data["event"]['user']]["last_word_of_bot"] != "" and \
                get_last_char(user_dict[event_data["event"]['user']]["last_word_of_bot"]) != text[0] and user_dict[event_data["event"]['user']]["last_word_of_bot"][2] != text[0]:
            print("여기 실행")
            print(user_dict[event_data["event"]['user']]["last_word_of_bot"])
            print(text[0])
            print(user_dict[event_data["event"]['user']]["last_word_of_bot"] != "")
            print(get_last_char(user_dict[event_data["event"]['user']]["last_word_of_bot"]) != text[0])
            print(user_dict[event_data["event"]['user']]["last_word_of_bot"][2] != text[0])

            th0 = threading.Thread(target=send_one_line, args=(channel, "`당신의 패배!`\n" + get_last_char(user_dict[event_data["event"]['user']]["last_word_of_bot"]) + "로 시작하는 단어를 썼어야지!"))
            th0.start()
            th0.join()
            user_dict[event_data["event"]['user']]["Status"] = BOT_WIN_first_wrong
        else:
            if not is_exist_word(text):
                th1 = threading.Thread(target=send_one_line, args=(channel, "`당신의 패배!`\nhttps://stdict.korean.go.kr/search/searchResult.do?pageSize=10&searchKeyword=" + text + " 를 확인해본 결과, \n없는 단어이므로 당신의 패배!"))
                th1.start()
                th1.join()
                user_dict[event_data["event"]['user']]["Status"] = BOT_WIN_not_exist
            else:
                user_dict[event_data["event"]['user']]["Status"] = BOT_TURN
                block = ImageBlock(
                    image_url="http://drive.google.com/uc?export=view&id=19NShAd-6IV_xUQmlKniEdILnASdnjF7d",
                    alt_text="`쿵쿵따라~ 쿵쿵따!`"
                )
                my_blocks = [block]
                slack_web_client.chat_postMessage(
                    channel=channel,
                    blocks=extract_json(my_blocks),
                )
                user_dict[event_data["event"]['user']]["last_word_of_bot"] = get_random_word(get_last_char(text), user_dict[event_data["event"]['user']]['level_setting'])
                if user_dict[event_data["event"]['user']]["last_word_of_bot"] == "모르겠다":
                    th1 = threading.Thread(target=send_one_line, args=(channel, " 젠장.. 생각이 안나..!"))
                    th1.start()
                    th1.join()
                    user_dict[event_data["event"]['user']]["Status"] = USER_WIN
                else:
                    temp = "_단어의 뜻: " + get_meaning_of_word(user_dict[event_data["event"]['user']]["last_word_of_bot"]) + "_"
                    slack_web_client.chat_postMessage(
                        channel=channel,
                        text=">*" + user_dict[event_data["event"]['user']]["last_word_of_bot"] + "*\n" + temp,
                    )
                    time.sleep(0.5)
                    block = ImageBlock(
                        image_url="http://drive.google.com/uc?export=view&id=19NShAd-6IV_xUQmlKniEdILnASdnjF7d",
                        alt_text="`쿵쿵따라~ 쿵쿵따!`"
                    )
                    my_blocks = [block]
                    slack_web_client.chat_postMessage(
                        channel=channel,
                        blocks=extract_json(my_blocks),
                    )
                    new_input = False
                    tmp = False
                    if user_dict[event_data["event"]['user']]["Loading"] == DONE:
                        sp = SlackProgress(SLACK_TOKEN, channel)
                        user_dict[event_data["event"]['user']]["Status"] = LOADING
                        for i in sp.iter(range(21)):
                            if new_input is True:
                                break
                            time.sleep(0.17)
                            if i >= 20:
                                # user_dict[event_data["event"]['user']]["Status"] = BOT_WIN_default
                                tmp = True
                    if tmp is False:
                        user_dict[event_data["event"]['user']]["Status"] = USER_TURN
                    else:
                        time.sleep(1.5)
                        if new_input is True:
                            user_dict[event_data["event"]['user']]["Status"] = USER_TURN
                        else:
                            user_dict[event_data["event"]['user']]["Status"] = BOT_WIN_default

    if user_dict[event_data["event"]['user']]["Status"] >= BOT_WIN_first_wrong:
        block = ImageBlock(
            image_url="http://drive.google.com/uc?export=view&id=1PCEtywkZnyVzYOf6e_TBrXf0SWJ_0PXb",
            alt_text="`쿵쿵따라~ 쿵쿵따!`"
        )
        my_blocks = [block]
        slack_web_client.chat_postMessage(
            channel=channel,
            blocks=extract_json(my_blocks),
        )
        slack_web_client.chat_postMessage(
            channel=channel,
            text="`쿵쿵따봇의 승리!!!`\n ```\n개못행 ㅋㅋ\n```",
        )
        user_dict[event_data["event"]['user']]["Status"] = WAIT_START
        # 초기화
        user_info_dict_reset(user_dict[event_data["event"]['user']])
        return
    elif user_dict[event_data["event"]['user']]["Status"] is USER_WIN:
        block = ImageBlock(
            image_url="http://drive.google.com/uc?export=view&id=1W_h7ruepUk0UKbRyfPWzkvYQQo5jhnMn",
            alt_text="`쿵쿵따라~ 쿵쿵따!`"
        )
        my_blocks = [block]
        slack_web_client.chat_postMessage(
            channel=channel,
            blocks=extract_json(my_blocks),
        )
        slack_web_client.chat_postMessage(
            channel=channel,
            text="<@" + event_data["event"]['user'] + "> 의 승리!!!\n```\n바준거임 리겜 ㄱ\n```\n시작하시려면 '@KungKungDDA 시작'이라 입력하세요",
        )
        user_dict[event_data["event"]['user']]["Status"] = WAIT_START
        # 초기화
        user_info_dict_reset(user_dict[event_data["event"]['user']])
        return


# / 로 접속하면 서버가 준비되었다고 알려줍니다.
@app.route("/", methods=["GET"])
def index():
    return "<h1>Server is ready.</h1>"


if __name__ == '__main__':
    user_dict = {}
    app.run('0.0.0.0', port=5000)
