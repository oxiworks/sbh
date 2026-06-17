import pandas as pd
import json
import os
import logging
import socket
import requests
import io
import base64
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURATION PART (설정 및 파일 경로 정의)
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 1. 구글 스프레드시트 및 출력 파일 설정
GOOGLE_SPREADSHEET_ID = "144VXK8vUlIu2HPOOYJUmm324mdu7oG8bAfkIdf7ckqM"
MOVE_JSON_OUT = 'move_2026.json'

# 2. ntfy 실시간 알림 설정
NTFY_URL = "https://ntfy.sh/oxinotify"
# ==============================================================================

def get_hostname():
    """현재 리눅스 서버의 실제 hostname을 가져오는 함수"""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"

def send_ntfy_alert(title, message, logger):
    """에러 발생 시 ntfy 서버로 실시간 알림을 보내는 함수 (Base64 안전 헤더 규격)"""
    hostname = get_hostname()
    payload = f"{message}\n\n- from '{hostname}'"

    # 한글/이모지 처리를 위한 RFC 2047 Base64 인코딩
    utf8_title = title.encode('utf-8')
    base64_title = base64.b64encode(utf8_title).decode('utf-8')

    headers = {
        "Title": f"=?utf-8?B?{base64_title}?=",
        "Priority": "default",
        "Tags": "warning,computer"
    }

    try:
        response = requests.post(NTFY_URL, data=payload.encode('utf-8'), headers=headers, timeout=10)
        if response.ok:
            logger.info("[알림] ntfy 에러 알림 전송 완료")
        else:
            logger.error(f"[알림] ntfy 전송 실패 (Status Code: {response.status_code})")
    except Exception as ntfy_err:
        logger.error(f"[알림] ntfy 통신 에러 발생: {ntfy_err}")

def setup_logger():
    """로그 폴더를 생성하고 로거를 설정하는 함수"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    log_file_path = os.path.join(LOG_DIR, 'move_update.log')
    logger = logging.getLogger("MoveLogger")
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

def generate_year_dates(year):
    """지정된 연도의 1월 1일부터 12월 31일까지 모든 날짜 리스트를 생성"""
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    
    dates = []
    curr = start_date
    while curr <= end_date:
        dates.append(curr.strftime('%Y/%m/%d'))
        curr += timedelta(days=1)
    return dates

def update_move_cache(logger):
    """구글 스프레드시트에서 이사 정보를 가져와 현재 연도 기준의 1년치 스케줄판을 빌드 및 캐싱하는 함수"""
    logger.info("[이사정보] 구글 스프레드시트 로드 및 1년치 스케줄링 변환 시작")

    base_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SPREADSHEET_ID}/export?format=csv"
    save_path = os.path.join(DATA_DIR, MOVE_JSON_OUT)

    # [수정] 외부 파일 확인 없이 현재 실행 시점 시스템 날짜 기준 연도 자동 바인딩
    target_year = datetime.now().year
    logger.info(f"[이사정보] 현재 날짜 기준 연도 설정 완료: {target_year}년")

    try:
        # 구글 드라이브 웹사이트 접속 시도
        response = requests.get(base_url, timeout=30)
        response.raise_for_status()
    except Exception as conn_err:
        err_msg = f"[이사정보] 구글 스프레드시트 웹 접속에 실패했습니다.\n사유: {conn_err}"
        logger.error(err_msg, exc_info=True)
        send_ntfy_alert("⚠️ [Move] 구글 드라이브 연동 실패", err_msg, logger)
        return

    try:
        df = pd.read_csv(io.StringIO(response.text), header=None)

        # 1년치 빈 바인더 초기화
        year_move_calendar = {}
        all_days_of_year = generate_year_dates(target_year)
        for d in all_days_of_year:
            year_move_calendar[d] = []

        total_records = 0

        # 구글 시트 레코드 파싱 및 맵핑
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

                # 날짜 형식 정규화 분리 ("2026. 6. 17" -> "2026.6.17")
                date_part = col_time.replace(". ", ".").split()[0]
                clean_date = pd.to_datetime(date_part, format='%Y.%m.%d', errors='coerce')
                
                if pd.isna(clean_date):
                    clean_date = pd.to_datetime(date_part, errors='coerce')

                if pd.isna(clean_date):
                    continue

                date_key = clean_date.strftime('%Y/%m/%d')

                # 생성된 1년 달력 범위 내에 있는 데이터만 적재
                if date_key in year_move_calendar:
                    # 초 단위(:00) 제거 핸들링
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
                    year_move_calendar[date_key].append(move_item)
                    total_records += 1

            except Exception:
                continue

        # 비어있지 않은 날짜 데이터만 필터링
        final_schedule = {k: v for k, v in year_move_calendar.items() if v}

        combined_payload = {
            "target_year": target_year,
            "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "schedule": final_schedule
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(combined_payload, f, ensure_ascii=False, indent=4)

        logger.info(f"[이사정보] 1년치 캐시 빌드 성공: {save_path} (총 {total_records}건 데이터 바인딩 완료)")

    except Exception as e:
        err_msg = f"[이사정보] 구글 시트 파싱 및 캐시 저장 중 치명적 에러 발생: {e}"
        logger.error(err_msg, exc_info=True)
        send_ntfy_alert("⚠️ [Move] 이사 일정 데이터 처리 에러", err_msg, logger)

if __name__ == "__main__":
    main_logger = setup_logger()
    main_logger.info("================ 이사 일정 구글 연동 배치 시작 ================")
    update_move_cache(main_logger)
    main_logger.info("================ 이사 일정 구글 연동 배치 완료 ================")
