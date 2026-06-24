#!/usr/bin/env python3
# ==============================================================================
# 💡 [TEST MODE 사용법 및 수동 검증 가이드]
# ------------------------------------------------------------------------------
# 스크립트 실행 시 뒤에 '대상날짜(YYYY/MM/DD)'와 '시간(시)' 파라미터를 넘기면,
# 무한 루프(데몬)를 돌지 않고 해당 날짜의 JSON 데이터를 즉시 파싱하여 
# 'ntfy.sh/sbhtest' 채널로 실제 메시지를 딱 한 번 발송한 뒤 종료됩니다.
#
# 💻 실행 예시 (터미널 입력):
#    python3 bio_gisu_alarm.py 2026/12/29 07  (주간/당직 테스트)
#    python3 bio_gisu_alarm.py 2026/12/30 16  (야간 테스트)
#
# ==============================================================================
# ⚙️ [systemd 데몬 서비스 등록 및 관리 가이드]
# ------------------------------------------------------------------------------
# 1) 서비스 파일 생성 및 편집:
#    sudo vi /etc/systemd/system/ sbh_bio_schedule_alarm.service
#
# 2) 파일 내용 붙여넣기 (아래 6줄 복사):
#    [Unit]
#    Description=SBH Bio Schedule Alarm Daemon
#    After=network.target
#
#    [Service]
#    ExecStart=/usr/bin/python3 /home/oxisnail/work/git/sbh/script/schedule_bio_alarm.py
#    Restart=always
#    User=oxisnail
#
#    [Install]
#    WantedBy=multi-user.target
#
# 3) 데몬 명령어 가이드:
#    sudo systemctl daemon-reload        # systemd 설정 리로드
#    sudo systemctl enable sbh_bio_schedule_alarm # 부팅 시 자동 시작 등록
#    sudo systemctl start sbh_bio_schedule_alarm  # 서비스 즉시 시작
#    sudo systemctl status sbh_bio_schedule_alarm # 서비스 상태 확인
#    sudo systemctl restart sbh_bio_schedule_alarm # 서비스 재시작
# ==============================================================================



import os
import sys
import datetime
import time
import json
import requests
import socket
import base64

# ==============================================================================
# CONFIGURATION PART (경로 자동화 및 환경 설정)
# ==============================================================================
# 1. 🌟 이 변수 하나만 변경하면 아래 모든 경로와 NTFY 채널이 자동으로 매핑됩니다.
TEAM_NAME = "power"  # "bio" 또는 "power" 등 팀명 지정

# 2. 파일 시스템 기반 디렉터리 동적 정의
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 3. 팀별 맞춤 파일 및 로그 자동 바인딩
# (예: /home/oxisnail/script/data/schedule_2026_bio.json)
JSON_CACHE_FILE = os.path.join(DATA_DIR, f"schedule_2026_{TEAM_NAME}.json")
LOG_FILE = os.path.join(LOG_DIR, f"schedule_alarm.log")

# 4. 업무별 알림 발송 시간 설정 (HH:MM 형식, 24시간제)
DAY_WORK_ALERT_TIME = "07:30"     # 주간 / 당직 근무 시 알림 시간
NIGHT_WORK_ALERT_TIME = "16:30"   # 야간 근무 시 알림 시간

# 5. NTFY 채널 설정
NTFY_WORK_URL = f"https://ntfy.sh/sbh{TEAM_NAME}_new"  # 정상 알림 채널 (sbhbio, sbhpower 등)
NTFY_TEST_URL = "https://ntfy.sh/sbhtest"         # 테스트 모드 전송 채널
NTFY_SYSTEM_URL = "https://ntfy.sh/oxinotify"      # 시스템 에러 알림 채널
# ==============================================================================

def get_hostname():
    """현재 시스템의 호스트네임 반환"""
    try:
        return socket.gethostname()
    except:
        return "unknown"

def log_message(msg):
    """타임스탬프와 함께 로그 파일에 기록"""
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_line = f"[{timestamp}_{TEAM_NAME}_alarm.py] {msg}"
    print(log_line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except:
        pass

def send_system_error_ntfy(title, error_msg):
    """스크립트 장애 발생 시 oxinotify 채널로 장치 호스트네임을 포함하여 즉시 발송"""
    hostname = get_hostname()
    payload = f"사유: {error_msg}\n\n- from '{hostname}'"

    # 한글 깨짐 방지를 위한 RFC 2047 Base64 타이틀 인코딩
    utf8_title = title.encode('utf-8')
    base64_title = base64.b64encode(utf8_title).decode('utf-8')

    headers = {
        "Title": f"=?utf-8?B?{base64_title}?=",
        "Priority": "default",
        "Tags": "warning,computer"
    }
    try:
        requests.post(NTFY_SYSTEM_URL, data=payload.encode('utf-8'), headers=headers, timeout=10)
    except Exception as e:
        log_message(f"[ERROR-NOTIFY-FAIL] 시스템 장애 알림 전송 실패: {str(e)}")

def send_ntfy_message(url, message):
    """ntfy 채널로 가공된 텍스트 메시지 전송"""
    try:
        res = requests.post(url, data=message.encode('utf-8'), timeout=10)
        if res.status_code == 200:
            log_message(f"- NTFY.SH 전송 완료 (Target: {url.split('/')[-1]})")
            return True
        else:
            log_message(f"- NTFY.SH 전송 실패 (Status: {res.status_code})")
            return False
    except Exception as e:
        log_message(f"- NTFY.SH 통신 에러: {str(e)}")
        return False

def make_weekday_str(date_str, weekday_val):
    try:
        parts = date_str.split('/')
        month_day = f"{parts[1]}/{parts[2]}"
        val_str = str(weekday_val).strip()
        
        if val_str in ["월", "화", "수", "목", "금", "토", "일"]:
            return f"{month_day}({val_str})"

        # 엑셀 표준 요일 규격 반영 (1: 일, 2: 월, 3: 화, 4: 수, 5: 목, 6: 금, 7: 토)
        weekday_map = {
            "1": "일",
            "2": "월",
            "3": "화",
            "4": "수",
            "5": "목",
            "6": "금",
            "7": "토"
        }
        w_char = weekday_map.get(val_str, "")
        
        return f"{month_day}({w_char})" if w_char else month_day
    except:
        return date_str

def process_schedule(target_day, target_hour, is_test=False):
    """새로운 JSON 파일을 열어 스케줄 및 타임라인 조건 판별 후 알림 메시지 빌드"""
    
    # 1. JSON 파일 존재 유무 검증
    if not os.path.exists(JSON_CACHE_FILE):
        err = f"스케줄 JSON 캐시 파일이 존재하지 않습니다: {JSON_CACHE_FILE}"
        log_message(err)
        send_system_error_ntfy("⚠️ [Alarm 데몬] JSON 파일 누락", err)
        return

    # 2. JSON 로드 및 파싱 처리
    try:
        with open(JSON_CACHE_FILE, "r", encoding="utf-8") as f:
            schedule_data = json.load(f)
    except Exception as e:
        err = f"JSON 데이터 파싱에 실패했습니다: {str(e)}"
        log_message(err)
        send_system_error_ntfy("⚠️ [Alarm 데몬] JSON 파싱 에러", err)
        return

    # 3. 당일 데이터 추출
    if target_day not in schedule_data:
        log_message(f"[검색결과] {target_day} 날짜에 해당하는 스케줄 데이터가 JSON에 없습니다.")
        return

    day_data = schedule_data[target_day]
    work_type = day_data.get("work_type", "").strip()
    weekday = day_data.get("weekday", "")

    log_message(f"[검색결과] 대상날짜: {target_day} / 시간대: {target_hour}시 / 근무형태: {work_type}")

    # 비번 및 휴무 조건 필터링
    if work_type in ["비번", "휴무", "-", ""]:
        log_message(f"- 금일 근무 형태가 '{work_type}'이므로 메시지 전송을 건너뜁니다.")
        return

    # 4. 시간대 및 근무 매칭 판별 엔진
    send_flag = False
    if not is_test:
        if target_hour in ["07", "08"] and work_type in ["당직", "주간"]:
            send_flag = True
        elif target_hour in ["16", "17"] and work_type == "야간":
            send_flag = True
    else:
        send_flag = True
        log_message("- [TEST MODE] 시간 조건 검사를 강제 통과합니다.")

    # 5. 매칭 성공 시 동적 텍스트 메시지 조합 및 발송
    if send_flag:
        # 근무 형태에 따른 근무자 딕셔너리 타겟팅 선택 (주간/당직이면 day_workers, 야간이면 night_workers)
        worker_key = "night_workers" if work_type in ["야간", "당직"] else "day_workers"
        workers = day_data.get(worker_key, {})

        # 일자 표기 변환 (예: 12/29(화))
        date_display = make_weekday_str(target_day, weekday)
        hostname = get_hostname()


        # 공백 가독성을 고려한 정렬 유지
        message_body = (
            f"[오늘의_근무 {date_display} - {work_type}]\n"
            f"▸ 산업지원동 : {workers.get('지원동', '-')}\n"
            f"▸ 글로벌센터 : {workers.get('글로벌', '-')}\n"
            f"▸ 외      곽1 : {workers.get('외곽1', '-')}\n"
            f"▸ 외      곽2 : {workers.get('외곽2', '-')}\n\n"
            f"-------------------------\n"
            f"🏠 용역원실   : {day_data.get('staffroom', '-')}\n"
            f"-------------------------\n\n"
            f"🔗 시간표 확인\n"
            f"https://{TEAM_NAME}.oxisnail.top\n"
            f"https://sbh.oxisnail.top/{TEAM_NAME}/\n\n"
            f"From_{hostname}"
        )

        log_message(f"[BUILD MESSAGE]\n{message_body}\n")

        # 전송 목적지 설정 및 발송
        target_url = NTFY_TEST_URL if is_test else NTFY_WORK_URL
        send_ntfy_message(target_url, message_body)

def run_daemon():
    """1분 단위 상시 대몬 스캐너 백그라운드 코어"""
    log_message("### 스크립트 실시간 서비스 데몬 기동 (JSON 캐시 스캔 모드) ###")
    
    last_checked_minute = ""

    while True:
        try:
            now = datetime.datetime.now()
            current_minute_str = now.strftime("%H:%M")

            # 중복 실행 방지 가드
            if current_minute_str != last_checked_minute:
                # 지정된 발송 골든 타임인 경우에만 핸들링
                if current_minute_str in [DAY_WORK_ALERT_TIME, NIGHT_WORK_ALERT_TIME]:
                    last_checked_minute = current_minute_str
                    
                    now_day = now.strftime("%Y/%m/%d")
                    now_hour = now.strftime("%H")
                    
                    log_message(f"[⏱️ MATCH TIME] 알림 시간 감지 -> {now_day} {current_minute_str}")
                    process_schedule(now_day, now_hour, is_test=False)
            
            # 10초 간격 유휴 대기 루프
            time.sleep(10)

        except Exception as e:
            err = f"데몬 메인 루프 내부 치명적 예외 발생: {str(e)}"
            log_message(err)
            send_system_error_ntfy("🚨 [Alarm 데몬] 루프 크래시", err)
            time.sleep(30)

if __name__ == "__main__":
    # 파라미터 기반 동적 CLI 실행 스펙 분기 조율
    if len(sys.argv) > 1:
        input_date = sys.argv[1]
        input_hour = sys.argv[2] if len(sys.argv) > 2 else "07"
        
        log_message("==================================================")
        log_message(f"🎯 [수동 검증 모드] 파라미터가 감지되었습니다.")
        log_message(f"🎯 대상 날짜: {input_date} / 대상 시간 대역: {input_hour}시")
        log_message("==================================================")
        
        process_schedule(input_date, input_hour, is_test=True)
    else:
        try:
            run_daemon()
        except Exception as fatal_err:
            err_text = f"최상단 메인 데몬 프로세스 사망: {str(fatal_err)}"
            log_message(f"[FATAL] {err_text}")
            send_system_error_ntfy("🚨 [Alarm 데몬] 프로세스 사망", err_text)
