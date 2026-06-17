import os
import json
import logging
import socket  # 호스트네임을 가져오기 위해 추가
import pandas as pd
import base64
import requests  # ntfy 전송을 위해 추가
from email.header import Header

# ==============================================================================
# CONFIGURATION PART
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

SCHEDULE_FILES = [
    "schedule_2026_bio.xlsm",
    "schedule_2026_power.xlsm"
]
SCHEDULE_SHEET = 'cal1'

# ntfy 설정
NTFY_URL = "https://ntfy.sh/oxinotify"
# ==============================================================================


def setup_logger():
    """로그 폴더를 생성하고 로거를 설정하는 함수"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    log_file_path = os.path.join(LOG_DIR, 'timetable_update.log')
    logger = logging.getLogger("TimetableLogger")
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


import base64  # ◀ 최상단 import 모음에 추가해 주세요

def send_ntfy_notification(title, message, logger):
    """ntfy.sh로 알림을 전송하는 함수 (Base64 헤더 안전화 버전)"""
    hostname = socket.gethostname()
    full_message = f"{message}\n\n-from hostname:'{hostname}'"
    
    # 한글/이모지 깨짐 및 인코딩 에러를 방지하는 ntfy 공식 추천 방식 (X-Title + Base64)
    utf8_title = title.encode('utf-8')
    base64_title = base64.b64encode(utf8_title).decode('utf-8')

    try:
        # 변수 정의가 확실하게 처리되도록 정돈
        res = requests.post(
            NTFY_URL,
            data=full_message.encode('utf-8'),
            headers={
                "X-Title": f"=?utf-8?B?{base64_title}?=",  # RFC 2047 규격 적용
                "Priority": "normal",
                "Tags": "warning,error"
            },
            timeout=10
        )
        res.raise_for_status()
        logger.info("[ntfy] 알림 전송 성공")
    except Exception as e:
        logger.error(f"[ntfy] 알림 전송 실패 원인: {e}", exc_info=True)

def update_schedule_cache(logger):
    """근무 시간표 엑셀 파일들을 JSON으로 캐싱하는 함수"""
    for file_name in SCHEDULE_FILES:
        file_path = os.path.join(DATA_DIR, file_name)
        base_name, _ = os.path.splitext(file_name)
        save_path = os.path.join(DATA_DIR, f"{base_name}.json")

        try:
            # 1. 파일이 없으면 '파일 없음 에러'를 강제로 터트립니다.
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"필수 엑셀 파일이 존재하지 않습니다: {file_path}")

            logger.info(f"[시간표] {file_name} 캐시 업데이트 시작")


            df = pd.read_excel(file_path, sheet_name=SCHEDULE_SHEET, header=1, engine='openpyxl')
            df.columns = [str(c).replace(" ", "").replace("\n", "").replace("\xa0", "") for c in df.columns]
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce').dt.strftime('%Y/%m/%d')

            schedule_dict = {}

            for _, row in df.iterrows():
                date_key = row['날짜']
                if pd.isna(date_key):
                    continue

                positions = ["지원동", "글로벌", "외곽1", "외곽2"]
                day_vals = row[['주간근무지원동', '주간근무글로벌', '주간근무외곽1', '주간근무외곽2']].values
                night_vals = row[['야간근무지원동', '야간근무글로벌', '야간근무외곽1', '야간근무외곽2']].values

                schedule_dict[date_key] = {
                    "weekday": str(row['요일']) if not pd.isna(row['요일']) else "",
                    "holiday": str(row['공휴일']) if not pd.isna(row['공휴일']) else "",
                    "work_type": str(row['근무형태']),
                    "day_workers": {pos: str(name) for pos, name in zip(positions, day_vals)},
                    "night_workers": {pos: str(name) for pos, name in zip(positions, night_vals)}
                }

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(schedule_dict, f, ensure_ascii=False, indent=4)

            logger.info(f"[시간표] 성공: {save_path} (총 {len(schedule_dict)}일치 완료)")

        except Exception as e:
            msg = f"[시간표] {file_name} 처리 중 에러 발생: {e}"
            logger.error(msg, exc_info=True)
            send_ntfy_notification("🚨 시간표 업데이트 에러 발생", msg, logger)


if __name__ == "__main__":
    main_logger = setup_logger()
    main_logger.info("================ 시간표 캐시 업데이트 시작 ================")
    
    update_schedule_cache(main_logger)
    
    main_logger.info("================ 시간표 캐시 업데이트 완료 ================")
