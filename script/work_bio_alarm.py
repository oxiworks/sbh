#!/usr/bin/env python3
# ==============================================================================
# 💡 [TEST MODE 사용법 및 수동 검증 가이드]
# ------------------------------------------------------------------------------
# 스크립트 실행 시 뒤에 '대상날짜(YYYY/MM/DD)' 파라미터를 넘기면,
# 무한 루프(데몬)를 돌지 않고 해당 날짜의 JSON 데이터를 즉시 파싱하여
# 'ntfy.sh/sbhtest' 채널로 실제 메시지를 딱 한 번 발송한 뒤 종료됩니다.
#
# 💻 실행 예시 (터미널 입력):
#    python3 schedule_bio_alarm.py 2026/06/23
#
# ==============================================================================
# ⚙️ [systemd 데몬 서비스 등록 및 관리 가이드]
# ------------------------------------------------------------------------------
# 1) 서비스 파일 생성 및 편집:
#    sudo vi /etc/systemd/system/sbh_bio_schedule_alarm.service
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
# 1. 변수 변경 시 아래 모든 경로와 NTFY 채널이 자동으로 매핑됩니다.
TEAM_NAME = "bio"  # "bio" 또는 "power" 등 팀명 지정
MY_NAME = "이기수"

# 2. 파일 시스템 기반 디렉터리 동적 정의
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 로그 디렉터리가 없을 경우 자동 생성 가드
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except:
        pass

# 3. 팀별 맞춤 파일 및 로그 자동 바인딩
JSON_CACHE_FILE = os.path.join(DATA_DIR, f"schedule_2026_{TEAM_NAME}.json")
TASK_FILE = os.path.join(DATA_DIR, f"{TEAM_NAME}_task.json")
LOG_FILE = os.path.join(LOG_DIR, f"schedule_alarm.log")

# 4. NTFY 채널 설정
NTFY_WORK_URL = "https://ntfy.sh/sbhmission_new"  # 기존 알림 대상 채널 유지
NTFY_TEST_URL = "https://ntfy.sh/sbhtest"      # 테스트 모드 전송 채널
NTFY_SYSTEM_URL = "https://ntfy.sh/oxinotify"  # 시스템 에러 알림 채널
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
    """스크립트 장애 발생 시 oxinotify 채널로 장애 통보"""
    hostname = get_hostname()
    payload = f"사유: {error_msg}\n\n- from '{hostname}'"

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

def send_ntfy(msg, url=NTFY_WORK_URL):
    hostname = get_hostname()
    tail = f"\n\nFrom_{hostname}"
    full_msg = f"{msg}{tail}"

    try:
        log_message(f"[NTFY] POST 요청 시작 (Target: {url.split('/')[-1]})")
        response = requests.post(
            url,
            data=full_msg.encode('utf-8'),
            timeout=5
        )
        if response.status_code == 200:
            log_message(f"[NTFY] 전송 성공: {msg.replace('\n', ' ')}")
            return True
        else:
            log_message(f"[NTFY] 전송 실패 (코드: {response.status_code})")
            return False
    except Exception as e:
        log_message(f"[NTFY] 전송 중 예외 발생: {str(e)}")
        return False

def load_json(path):
    """JSON 로더"""
    if not os.path.exists(path):
        log_message(f"[JSON] 파일 없음: {path}")
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log_message(f"[JSON] 로드 성공: {path}")
        return data
    except Exception as e:
        log_message(f"[JSON] 로드 실패: {path} / {str(e)}")
        return None

def get_my_position(day_info, name):
    """기존 검사 대상자 위치 판별 엔진 알고리즘 그대로 복사"""
    if not day_info:
        log_message("[POSITION] day_info 없음")
        return "None"
    try:
        for pos, workers in day_info.get("day_workers", {}).items():
            if name in workers:
                log_message(f"[POSITION] 주간 위치 발견: {pos}")
                return pos

        for pos, workers in day_info.get("night_workers", {}).items():
            if name in workers:
                log_message(f"[POSITION] 야간 위치 발견: {pos}")
                return pos
    except Exception as e:
        log_message(f"[POSITION] 위치 탐색 오류: {str(e)}")

    log_message("[POSITION] 위치 없음")
    return "None"

def process_alarm_logic(target_now, is_test=False):
    """기존 핵심 알람 조건 판별 루프 코어 체계"""
    weekdays_kor = ["월", "화", "수", "목", "금", "토", "일"]
    
    current_time = target_now.strftime("%H:%M")
    current_date_int = int(target_now.strftime("%Y%m%d"))
    current_day_kor = weekdays_kor[target_now.weekday()]
    
    today_str = target_now.strftime("%Y/%m/%d")
    yesterday_str = (target_now - datetime.timedelta(days=1)).strftime("%Y/%m/%d")

    if is_test:
        log_message(f"[CHECK][TEST MODE] 분 검사 시작: {current_time}")
    else:
        log_message(f"[CHECK] 분 검사 시작: {current_time}")

    log_message(f"[DATE] today={today_str}, yesterday={yesterday_str}, weekday={current_day_kor}")

    schedule = load_json(JSON_CACHE_FILE)
    tasks = load_json(TASK_FILE)

    if not schedule:
        log_message("[SKIP] schedule 로드 실패")
        if not is_test: send_system_error_ntfy("⚠️ [Alarm 데몬] schedule 캐시 누락", "파일을 읽을 수 없거나 비어있습니다.")
        return

    if today_str not in schedule:
        log_message(f"[SKIP] 오늘 일정 없음: {today_str}")
        return

    t_info = schedule[today_str]
    y_info = schedule.get(yesterday_str)

    today_type = t_info.get('work_type', "미정")
    yesterday_type = y_info.get('work_type', "없음") if y_info else "없음"

    pos_today = get_my_position(t_info, MY_NAME)
    pos_yesterday = get_my_position(y_info, MY_NAME)

    is_weekend = target_now.weekday() >= 5
    is_holiday = t_info.get('holiday', "") != ""

    log_message(
        f"[STATUS] today_type={today_type}, yesterday_type={yesterday_type}, "
        f"pos_today={pos_today}, pos_yesterday={pos_yesterday}, "
        f"weekend={is_weekend}, holiday={is_holiday}"
    )

    if not tasks:
        log_message("[SKIP] task 로드 실패")
        return

    log_message(f"[TASK] 총 task 수: {len(tasks)}")

    # 각 Task 순회 판별 필터링 구조 그대로 유지
    for task in tasks:
        try:
            task_id = task.get('id')
            task_name = task.get('name', '이름없음')

            if task_id == 0:
                continue

            log_message(f"[TASK:{task_id}] 검사 시작 - {task_name}")

            # 1. 기간/요일/시간 기본 필터
            s_date = task.get('start_date', "")
            e_date = task.get('end_date', "")

            if s_date and current_date_int < int(s_date):
                log_message(f"[TASK:{task_id}] SKIP 시작일 이전 ({current_date_int} < {s_date})")
                continue

            if e_date and current_date_int > int(e_date):
                log_message(f"[TASK:{task_id}] SKIP 종료일 이후 ({current_date_int} > {e_date})")
                continue

            w_days = task.get('work_days', [])
            if w_days and (current_day_kor not in w_days):
                log_message(f"[TASK:{task_id}] SKIP 요일 불일치 ({current_day_kor} not in {w_days})")
                continue

            task_time = task.get('time')
            # 테스트 모드가 아닐 때만 정확한 알람 시각 필터 적용
            if not is_test and task_time != current_time:
                continue

            log_message(f"[TASK:{task_id}] 시간 일치 ({task_time if not is_test else 'TEST 강제통과'})")

            # 2. 오늘 근무 형태 필터
            work_types = task.get('work_type', [])
            if today_type not in work_types:
                log_message(f"[TASK:{task_id}] SKIP 근무형태 불일치 ({today_type} not in {work_types})")
                continue

            # 3. 주말/휴일 스킵 필터
            if task.get('skip_on_weekend', False) and is_weekend:
                log_message(f"[TASK:{task_id}] SKIP 주말 제외")
                continue

            if task.get('skip_on_holiday', False) and is_holiday:
                log_message(f"[TASK:{task_id}] SKIP 휴일 제외")
                continue

            # 4. 어제 근무 및 위치 필터
            y_cond = task.get('if_yesterday_was', [])
            target_pos = task.get('position', [])

            if y_cond:
                if yesterday_type not in y_cond:
                    log_message(f"[TASK:{task_id}] SKIP 어제근무 불일치 ({yesterday_type} not in {y_cond})")
                    continue
                if pos_yesterday not in target_pos:
                    log_message(f"[TASK:{task_id}] SKIP 어제위치 불일치 ({pos_yesterday} not in {target_pos})")
                    continue
            else:
                if pos_today not in target_pos:
                    log_message(f"[TASK:{task_id}] SKIP 오늘위치 불일치 ({pos_today} not in {target_pos})")
                    continue

            # 5. 알람 전송 준비
            msg = task.get('message', f"[알림] {task.get('name', '미명명 업무')} 시간입니다.")
            log_message(f"[TASK:{task_id}] 전송 시도: {msg}")

            # 목적지 전송 주소 분기 처리 (테스트인 경우 sbhtest 채널 채택)
            target_url = NTFY_TEST_URL if is_test else NTFY_WORK_URL
            send_ntfy(msg, url=target_url)

        except Exception as e:
            log_message(f"[TASK:{task_id}] task 처리 오류: {str(e)}")

def run_daemon():
    """상시 실시간 서비스 백그라운드 데몬 루프 코어"""
    log_message("### 스크립트 실시간 서비스 데몬 기동 (JSON 캐시 스캔 모드) ###")
    last_executed_minute = ""

    while True:
        try:
            now = datetime.datetime.now()
            current_time = now.strftime("%H:%M")

            if current_time != last_executed_minute:
                last_executed_minute = current_time
                process_alarm_logic(now, is_test=False)

            time.sleep(45)  # 1분 중복 처리 완전 방어를 위한 슬립 시간 배정
            time.sleep(1)

        except Exception as e:
            err = f"데몬 메인 루프 내부 치명적 예외 발생: {str(e)}"
            log_message(err)
            send_system_error_ntfy("🚨 [Alarm 데몬] 루프 크래시", err)
            time.sleep(5)

if __name__ == "__main__":
    # 파라미터 기반 동적 수동 테스트 검증 분기 구현
    if len(sys.argv) > 1:
        input_date_str = sys.argv[1]  # 예: "2026/06/23"
        
        try:
            # 테스트 날짜 데이터 타임 변환 (시간은 임의로 현재 시각 세팅하여 조건 스캔 유도)
            current_real_time = datetime.datetime.now()
            parsed_date = datetime.datetime.strptime(input_date_str, "%Y/%m/%d")
            test_datetime = parsed_date.replace(hour=current_real_time.hour, minute=current_real_time.minute)
        except Exception as date_err:
            print(f"[ERROR] 날짜 인자 포맷 오류 (YYYY/MM/DD 형식 필요): {str(date_err)}")
            sys.exit(1)

        log_message("==================================================")
        log_message(f"🎯 [수동 검증 모드] 파라미터가 감지되었습니다.")
        log_message(f"🎯 대상 날짜: {test_datetime.strftime('%Y/%m/%d')}")
        log_message(f"🎯 알람 발송 타겟: {NTFY_TEST_URL}")
        log_message("==================================================")

        process_alarm_logic(test_datetime, is_test=True)
    else:
        try:
            run_daemon()
        except Exception as fatal_err:
            err_text = f"최상단 메인 데몬 프로세스 사망: {str(fatal_err)}"
            log_message(f"[FATAL] {err_text}")
            send_system_error_ntfy("🚨 [Alarm 데몬] 프로세스 사망", err_text)
