import pandas as pd
import json
import os
import logging
import requests
import io
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURATION PART (설정 및 파일 경로 정의 - 이곳에서 쉽게 수정하세요)
# ==============================================================================
# 1. 파일 및 디렉토리 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 2. 시간표(Timetable) 설정
SCHEDULE_FILES = [
    "schedule_2026_bio.xlsm",
    "schedule_2026_power.xlsm"
]
SCHEDULE_SHEET = 'cal1'

# 3. 예정 업무(Mission) 설정
MISSION_FILE = 'mission.xlsx'
MISSION_JSON_OUT = 'mission.json'

# 4. 이사 일정 구글 스프레드시트 설정
GOOGLE_SPREADSHEET_ID = "144VXK8vUlIu2HPOOYJUmm324mdu7oG8bAfkIdf7ckqM"
MOVE_JSON_OUT = 'move.json'
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


def update_schedule_cache(logger):
    """1. 근무 시간표 엑셀 파일들을 JSON으로 캐싱하는 함수"""
    for file_name in SCHEDULE_FILES:
        file_path = os.path.join(DATA_DIR, file_name)
        base_name, _ = os.path.splitext(file_name)
        save_path = os.path.join(DATA_DIR, f"{base_name}.json")

        if not os.path.exists(file_path):
            logger.warning(f"[시간표] 파일이 존재하지 않아 건너뜜: {file_path}")
            continue

        logger.info(f"[시간표] {file_name} 캐시 업데이트 시작")

        try:
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
                    "holiday": str(row['공휴일']) if not pd.isna(row['공휴일']) else "",
                    "work_type": str(row['근무형태']),
                    "day_workers": {pos: str(name) for pos, name in zip(positions, day_vals)},
                    "night_workers": {pos: str(name) for pos, name in zip(positions, night_vals)}
                }

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(schedule_dict, f, ensure_ascii=False, indent=4)

            logger.info(f"[시간표] 성공: {save_path} (총 {len(schedule_dict)}일치 완료)")

        except Exception as e:
            logger.error(f"[시간표] {file_name} 처리 중 에러 발생: {e}", exc_info=True)


def update_mission_cache(logger):
    """2. 예정 업무(Mission) 엑셀을 읽어 JSON으로 변환하는 함수"""
    logger.info("[예정업무] 캐시 업데이트 시작")
    
    filename = os.path.join(DATA_DIR, MISSION_FILE)
    save_path = os.path.join(DATA_DIR, MISSION_JSON_OUT)

    if not os.path.exists(filename):
        logger.warning(f"[예정업무] 파일이 존재하지 않아 건너뜜: {filename}")
        return

    try:
        df = pd.read_excel(filename, header=None, engine='openpyxl')
        
        mission_dict = {
            "date_tasks": {},    # 날짜 기준 ("2026-03-16")
            "weekday_tasks": {}  # 요일 기준 ("1")
        }

        for _, row in df.iterrows():
            try:
                val_1 = str(row[0]).strip() if not pd.isna(row[0]) else ""
                val_2 = str(row[1]).strip() if not pd.isna(row[1]) else ""
                val_3 = str(row[2]).strip() if not pd.isna(row[2]) else ""

                if not val_1:
                    continue

                if '-' in val_3:
                    date_key = val_3.split()[0]
                    mission_dict["date_tasks"][date_key] = val_2 if val_2 else val_1
                elif val_3.isdigit():
                    weekday_key = str(int(val_3))
                    mission_dict["weekday_tasks"][weekday_key] = val_1

            except Exception as row_err:
                logger.debug(f"[예정업무] 개별 행 파싱 건너뜀: {row_err}")
                continue

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(mission_dict, f, ensure_ascii=False, indent=4)

        logger.info(f"[예정업무] 성공: {save_path} (날짜 {len(mission_dict['date_tasks'])}건 / 요일 {len(mission_dict['weekday_tasks'])}건 완료)")

    except Exception as e:
        logger.error(f"[예정업무] 처리 중 에러 발생: {e}", exc_info=True)


def update_move_cache(logger):
    """3. 구글 스프레드시트에서 이사 정보를 긁어와 오늘/내일 메시지를 캐싱하는 함수"""
    logger.info("[이사정보] 구글 스프레드시트 스크래핑 시작")
    
    base_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SPREADSHEET_ID}/export?format=csv"
    save_path = os.path.join(DATA_DIR, MOVE_JSON_OUT)

    # 쉘의 date 매칭 포맷 완벽 재현
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    
    today_match = now.strftime('%Y. %#m. %#d') if os.name == 'nt' else now.strftime('%Y. %-m. %-d')
    tomorrow_match = tomorrow.strftime('%Y. %#m. %#d') if os.name == 'nt' else tomorrow.strftime('%Y. %-m. %-d')
    
    today_disp = now.strftime('%Y-%m-%d')
    tomorrow_disp = tomorrow.strftime('%Y-%m-%d')

    try:
        response = requests.get(base_url, timeout=30)
        response.raise_for_status()
        
        # 큰따옴표가 포함된 구글 CSV를 깨끗하게 메모리 DataFrame으로 변환
        df = pd.read_csv(io.StringIO(response.text), header=None)
        
        today_msg = f"[오늘 일정 - {today_disp}]\n\n"
        tomorrow_msg = f"[내일 일정 - {tomorrow_disp}]\n\n"
        t_count = 0
        tm_count = 0

        # 기존 awk 로직을 순수 파이썬 데이터 바인딩으로 정밀 변환
        for _, row in df.iterrows():
            try:
                # 각 열 데이터 로드 및 결측값 제거 (컬럼 인덱스는 0부터 시작)
                # awk의 $2(동/호수), $3(시간), $4(이름/종류), $5(구분), $6(대상), $7(물품)
                col_name    = str(row[1]).strip() if not pd.isna(row[1]) else ""
                col_time    = str(row[2]).strip() if not pd.isna(row[2]) else ""
                col_type    = str(row[3]).strip() if not pd.isna(row[3]) else ""
                col_div     = str(row[4]).strip() if not pd.isna(row[4]) else ""
                col_target  = str(row[5]).strip() if not pd.isna(row[5]) else ""
                col_item    = str(row[6]).strip() if not pd.isna(row[6]) else ""

                if not col_time:
                    continue

                # 초 단위( :00 ) 잘라내기
                if len(col_time.split(':')) == 3:
                    col_time = ':'.join(col_time.split(':')[:2])

                # 개별 아이템 문자열 포맷 조립
                item_content = f"{col_type} {col_name}\n"
                item_content += f" - 일 정: {col_time}\n"
                if col_target: item_content += f" - 대 상: {col_target}\n"
                if col_item:   item_content += f" - 물품명: {col_item}\n"
                if col_div:    item_content += f" - 구 분: {col_div}\n"
                item_content += "\n"

                # 오늘/내일 일정 그룹핑 검증
                if col_time.startswith(today_match):
                    t_count += 1
                    # 숫자 이모지 처리 (1️⃣, 2️⃣ 형태)
                    today_msg += f"{t_count}️⃣ {item_content}"
                elif col_time.startswith(tomorrow_match):
                    tm_count += 1
                    tomorrow_msg += f"{tm_count}️⃣ {item_content}"

            except Exception as row_err:
                continue

        if t_count == 0:  today_msg += "일정이 없습니다.\n\n"
        if tm_count == 0: tomorrow_msg += "일정이 없습니다.\n\n"

        # 두 블록을 병합하여 최종 결과 구조 생성
        combined_payload = {
            "last_updated": now.strftime('%Y-%m-%d %H:%M:%S'),
            "message": f"{today_msg}--------------------\n\n{tomorrow_msg}"
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(combined_payload, f, ensure_ascii=False, indent=4)

        logger.info(f"[이사정보] 성공: {save_path} (오늘 {t_count}건 / 내일 {tm_count}건 완료)")

    except Exception as e:
        logger.error(f"[이사정보] 처리 중 에러 발생: {e}", exc_info=True)


if __name__ == "__main__":
    main_logger = setup_logger()
    main_logger.info("================ 크론 캐시 일원화 배치 시작 ================")
    
    # 1. 근무 시간표 파싱
    update_schedule_cache(main_logger)
    
    # 2. 예정 업무(Mission) 파싱
    update_mission_cache(main_logger)
    
    # 3. 구글 스프레드시트 이사 일정 스크래핑 및 파싱 (추가됨)
    update_move_cache(main_logger)
    
    main_logger.info("================ 크론 캐시 일원화 배치 완료 ================")
