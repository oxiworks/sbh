import base64
import pandas as pd
import json
import os
import logging
import socket
import requests
from urllib.parse import quote
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURATION PART (설정 및 파일 경로 정의)
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 1. 파일 설정
MISSION_FILE = 'mission_2026_bio.xlsx'
MISSION_JSON_OUT = 'mission_2026_bio.json'

# 2. ntfy 실시간 알림 설정
NTFY_URL = "https://ntfy.sh/oxinotify"
# ==============================================================================

def get_hostname():
    """현재 리눅스 서버의 실제 hostname을 가져오는 함수"""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"

def send_ntfy_alert(message, logger):
    """에러 발생 시 ntfy 서버로 실시간 알림을 보내는 함수 (Priority: Normal)"""
    hostname = get_hostname()
    payload = f"{message}\n\n- from '{hostname}'"

    # [수정] quote 대신 base64를 사용하여 정밀하게 인코딩 포맷 매핑
    title_text = "⚠️ [Mission] 예정 업무 생성 실패"
    b64_bytes = base64.b64encode(title_text.encode('utf-8'))
    encoded_title = f"=?utf-8?B?{b64_bytes.decode('utf-8')}?="

    headers = {
        "Title": encoded_title,
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

    log_file_path = os.path.join(LOG_DIR, 'mission_update.log')
    logger = logging.getLogger("MissionLogger")
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
        # 캘린더 매핑 편의를 위해 'YYYY/MM/DD' 포맷 생성
        dates.append(curr.strftime('%Y/%m/%d'))
        curr += timedelta(days=1)
    return dates

def update_mission_cache(logger):
    """B2 셀에서 연도를 읽고, A/B/C열 규칙에 따라 1년치 날짜별 JSON을 매핑 및 캐싱하는 함수 (중복 작업 누적 지원)"""
    logger.info("[예정업무] 1년치 캐시 업데이트 시작")

    filename = os.path.join(DATA_DIR, MISSION_FILE)
    save_path = os.path.join(DATA_DIR, MISSION_JSON_OUT)

    if not os.path.exists(filename):
        err_msg = f"[예정업무] 입력 소스 파일이 존재하지 않습니다.\n경로: {filename}"
        logger.warning(err_msg)
        send_ntfy_alert(err_msg, logger)
        return

    try:
        df_raw = pd.read_excel(filename, header=None, engine='openpyxl')

        try:
            target_year = int(float(df_raw.iloc[1, 1])) # B2 셀 값
            logger.info(f"[예정업무] 기준 연도 확인 완료: {target_year}년")
        except Exception as year_err:
            raise ValueError(f"B2 셀에서 유효한 연도(숫자)를 가져오지 못했습니다. 확인 요망: {year_err}")

        # 2. 파싱용 딕셔너리 초기화 (중복 누적을 위해 밸류를 리스트[] 형태로 수집)
        rules_date = {}    # 특정 날짜 규칙 { "2026/03/16": ["작업1", "작업2"] }
        rules_weekday = {} # 요일별 고정 규칙 { 0: ["월요작업1", "월요작업2"] }

        # 3. 데이터 행을 돌며 규칙 수집 (A=작업내용, B=날짜, C=요일)
        for idx, row in df_raw.iterrows():
            val_task = str(row[0]).strip() if not pd.isna(row[0]) else ""
            val_date = str(row[1]).strip() if not pd.isna(row[1]) else ""
            val_weekday = str(row[2]).strip() if not pd.isna(row[2]) else ""

            if not val_task or val_task in ["작업내용", "Task"]:
                continue

            # Case A: B열에 날짜 데이터가 존재하는 경우
            if val_date and val_date != "nan" and val_date != "-":
                try:
                    clean_date = pd.to_datetime(val_date.split()[0], errors='coerce')
                    if not pd.isna(clean_date):
                        date_key = clean_date.strftime('%Y/%m/%d')
                        if date_key not in rules_date:
                            rules_date[date_key] = []
                        rules_date[date_key].append(val_task) # 리스트에 누적
                except Exception:
                    pass

            # Case B: C열에 요일 숫자 데이터가 존재하는 경우
            if val_weekday and val_weekday.replace('.0', '').isdigit():
                weekday_key = int(float(val_weekday))
                if weekday_key not in rules_weekday:
                    rules_weekday[weekday_key] = []
                rules_weekday[weekday_key].append(val_task) # 리스트에 누적

        # 4. 1년치 날짜 배열(딕셔너리)을 만들고 규칙에 따라 값 채우기
        year_mission_calendar = {}
        all_days_of_year = generate_year_dates(target_year)

        for date_str in all_days_of_year:
            dt_obj = datetime.strptime(date_str, '%Y/%m/%d')
            day_of_week = (dt_obj.weekday() + 1) % 7

            # 하루에 여러 작업이 들어갈 수 있도록 리스트로 생성
            day_tasks = []
            
            # 1. 요일 반복 규칙이 있다면 먼저 모두 추가
            if day_of_week in rules_weekday:
                day_tasks.extend(rules_weekday[day_of_week])
                
            # 2. 특정 날짜 지정 규칙이 있다면 이어서 모두 추가 (덮어쓰지 않고 추가됨)
            if date_str in rules_date:
                day_tasks.extend(rules_date[date_str])

            # 등록된 작업이 있는 날짜만 최종 캐시에 등록
            if day_tasks:
                # 중복 항목 제거를 원하시면 list(set(day_tasks)) 로 처리 가능합니다.
                year_mission_calendar[date_str] = day_tasks

        # 5. 최종 구조화 및 파일 영구 저장
        output_payload = {
            "target_year": target_year,
            "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "schedule": year_mission_calendar
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(output_payload, f, ensure_ascii=False, indent=4)

        logger.info(f"[예정업무] 1년치 캐시 변환 성공: {save_path} (총 {len(year_mission_calendar)}일 맵핑 완료)")

    except Exception as e:
        err_trace = f"[예정업무] 1년치 스크립트 실행 중 치명적 에러 발생: {e}"
        logger.error(err_trace, exc_info=True)
        send_ntfy_alert(err_trace, logger)

if __name__ == "__main__":
    main_logger = setup_logger()
    main_logger.info("================ 예정업무 1년치 단독 배치 시작 ================")
    update_mission_cache(main_logger)
    main_logger.info("================ 예정업무 1년치 단독 배치 완료 ================")
