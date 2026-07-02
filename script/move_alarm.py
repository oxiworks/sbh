#!/usr/bin/env python3
import os
import io
import sys
import json
import socket
import logging
import base64
import requests
import pandas as pd
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURATION PART (경로 및 NTFY 설정)
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 1. 구글 스프레드시트 소스 정보
GOOGLE_SPREADSHEET_ID = "144VXK8vUlIu2HPOOYJUmm324mdu7oG8bAfkIdf7ckqM"

# 2. NTFY 발송 채널 트리거
NTFY_TOPIC = "sbhmission"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
NTFY_TEST_URL = "https://ntfy.sh/sbhtest"

# 3. 시스템 에러 발생시 수신 채널
NTFY_SYSTEM_URL = "https://ntfy.sh/oxinotify"
# ==============================================================================

def get_hostname():
    """현재 리눅스 서버의 실제 hostname 반환"""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"

def setup_logger():
    """로그 디렉터리를 자동 생성하고 로거 설정"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    log_file_path = os.path.join(LOG_DIR, 'move_alarm.log')
    logger = logging.getLogger("MoveAlarmLogger")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

def send_system_error_ntfy(title, error_msg, logger):
    """스크립트 내부 장애 발생 시 oxinotify 채널로 실시간 알림 통보"""
    hostname = get_hostname()
    payload = f"{error_msg}\n\n- from '{hostname}'"

    # RFC 2047 규격 적용 안전 Base64 타이틀 인코딩
    utf8_title = title.encode('utf-8')
    base64_title = base64.b64encode(utf8_title).decode('utf-8')

    headers = {
        "Title": f"=?utf-8?B?{base64_title}?=",
        "Priority": "default",
        "Tags": "warning,computer"
    }
    try:
        requests.post(NTFY_SYSTEM_URL, data=payload.encode('utf-8'), headers=headers, timeout=10)
        logger.info("[알림] 시스템 에러 알림 ntfy 전송 완료")
    except Exception as ntfy_err:
        logger.error(f"[알림] 시스템 에러 알ify 전송 실패: {ntfy_err}")

def get_number_emoji(num):
    """숫자를 기존 스크립트 스타일의 이모지 번호로 변환"""
    emojis = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    if 0 <= num <= 10:
        return emojis[num]
    return f"[{num}] "

def build_item_message(item):
    """기존 가공 규칙과 100% 일치하는 개별 일정 텍스트 블록 빌드"""
    building = item.get("type", "").strip()
    name = item.get("name", "").strip()
    time_str = item.get("time", "").strip()

    # 초 단위가 포함되어 있을 경우 슬라이싱 분리 처리
    if len(time_str.split(':')) > 2:
        time_str = ':'.join(time_str.split(':')[:-1])

    content = f"{building} {name}\n"
    content += f" - 일 정: {time_str}\n"

    if item.get("target"):
        content += f" - 대 상: {item.get('target').strip()}\n"
    if item.get("item"):
        content += f" - 물품명: {item.get('item').strip()}\n"
    if item.get("division"):
        content += f" - 구 분: {item.get('division').strip()}\n"

    content += "\n"  # 일정 간 공백 라인 보존
    return content

def fetch_and_parse_schedule(logger, today_key, tomorrow_key):
    """구글 시트에서 실시간 데이터를 받아와 오늘/내일 일정 딕셔너리로 분류"""
    base_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SPREADSHEET_ID}/export?format=csv"
    
    today_list = []
    tomorrow_list = []

    try:
        response = requests.get(base_url, timeout=30)
        response.raise_for_status()
    except Exception as conn_err:
        err_msg = f"구글 스프레드시트 웹 접속에 실패했습니다.\n사유: {conn_err}"
        logger.error(err_msg)
        send_system_error_ntfy("⚠️ [Move] 구글 드라이브 연동 실패", err_msg, logger)
        return None, None

    try:
        df = pd.read_csv(io.StringIO(response.text), header=None)

        for _, row in df.iterrows():
            try:
                col_name    = str(row[1]).strip() if not pd.isna(row[1]) else ""
                col_time    = str(row[2]).strip() if not pd.isna(row[2]) else ""
                col_type    = str(row[3]).strip() if not pd.isna(row[3]) else ""
                col_div     = str(row[4]).strip() if not pd.isna(row[4]) else ""
                col_target  = str(row[5]).strip() if not pd.isna(row[5]) else ""
                col_item    = str(row[6]).strip() if not pd.isna(row[6]) else ""

                if not col_time:
                    continue

                # 날짜 전처리 정규화 ("2026. 6. 17" -> "2026.6.17")
                date_part = col_time.replace(". ", ".").split()[0]
                clean_date = pd.to_datetime(date_part, format='%Y.%m.%d', errors='coerce')

                if pd.isna(clean_date):
                    clean_date = pd.to_datetime(date_part, errors='coerce')

                if pd.isna(clean_date):
                    continue

                date_key = clean_date.strftime('%Y/%m/%d')

                # 초 단위 정리 작업 반영
                time_detail = " ".join(col_time.split()[1:]) if len(col_time.split()) > 1 else ""
                if len(time_detail.split(':')) == 3:
                    time_detail = ':'.join(time_detail.split(':')[:2])

                move_item = {
                    "name": col_name,
                    "time": time_detail if time_detail else col_time,
                    "type": col_type,
                    "division": col_div,
                    "target": col_target,
                    "item": col_item
                }

                # 오늘/내일 날짜 매칭 분류
                if date_key == today_key:
                    today_list.append(move_item)
                elif date_key == tomorrow_key:
                    tomorrow_list.append(move_item)

            except Exception:
                continue

        return today_list, tomorrow_list

    except Exception as parse_err:
        err_msg = f"구글 시트 파싱 중 예외 발생: {parse_err}"
        logger.error(err_msg)
        send_system_error_ntfy("⚠️ [Move] 데이터 파싱 에러", err_msg, logger)
        return None, None

def main():
    logger = setup_logger()
    logger.info("================ 이사 일정 추출 및 NTFY 알림 전송 시작 ================")

    # 1. 날짜 데이터 셋업
    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    today_key = now.strftime("%Y/%m/%d")        # 시트 비교 매칭용 (2026/06/23)
    tomorrow_key = tomorrow.strftime("%Y/%m/%d")

    today_disp = now.strftime("%Y-%m-%d")        # 헤더 노출용 (2026-06-23)
    tomorrow_disp = tomorrow.strftime("%Y-%m-%d")

    # 2. 구글 시트에서 실시간 분류 데이터 파싱 완료본 획득
    today_items, tomorrow_items = fetch_and_parse_schedule(logger, today_key, tomorrow_key)
    
    if today_items is None and tomorrow_items is None:
        logger.error("데이터 획득 실패로 알림 프로세스를 전면 중단합니다.")
        return

    # 3. NTFY 메시지 바디 문자열 빌드
    today_msg = f"[오늘 일정 - {today_disp}]\n\n"
    tomorrow_msg = f"[내일 일정 - {tomorrow_disp}]\n\n"

    t_count = 0
    for item in today_items:
        t_count += 1
        today_msg += f"{get_number_emoji(t_count)} {build_item_message(item)}"

    tm_count = 0
    for item in tomorrow_items:
        tm_count += 1
        tomorrow_msg += f"{get_number_emoji(tm_count)} {build_item_message(item)}"

    # 4. 빈 일정을 위한 예외 문자열 결합
    if t_count == 0:
        today_msg += "일정이 없습니다.\n\n"
    if tm_count == 0:
        tomorrow_msg += "일정이 없습니다.\n\n"

    # 5. 기존 꼬리말 규칙 병합
    hostname = get_hostname()
    full_message = f"{today_msg}--------------------\n\n{tomorrow_msg}\n\nFrom_{hostname}"

    # 6. 실시간 ntfy 채널 발송
    try:
        logger.info(f"[보내기] 전송 대상 채널 주소: {NTFY_URL}")
        
        response = requests.post(
            NTFY_URL,
            data=full_message.encode('utf-8'),
            timeout=15
        )
        
        if response.status_code == 200:
            logger.info(f"NTFY 알림 발송 완료 (Topic: {NTFY_TOPIC}, 오늘: {t_count}건 / 내일: {tm_count}건)")
        else:
            logger.error(f"NTFY 전송 실패 응답 수신 (코드: {response.status_code})")

    except Exception as ntfy_api_err:
        logger.error(f"NTFY 서버 네트워크 API 전송 오류: {ntfy_api_err}")

    logger.info("================ 이사 일정 추출 및 NTFY 알림 전송 종료 ================")

if __name__ == "__main__":
# 🌟 [단순한 전환] 메인 스크립트가 뒤에 'test'를 붙여서 깨웠다면, 테스트 채널로 주소를 덮어씁니다.
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        NTFY_URL = NTFY_TEST_URL  # (상단에 정의된 https://ntfy.sh/sbhtest)

    main()
