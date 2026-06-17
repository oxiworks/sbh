import json
import datetime
import time
import requests
import os

# 설정
MY_NAME = "이기수"
CACHE_FILE = '/home/oxisnail/script/bio_schedule.json'
TASK_FILE = '/home/oxisnail/script/bio_task.json'
LOG_FILE = '/tmp/bio_gisu_alarm.log'


def log_message(msg):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {msg}\n")
    except:
        pass


def load_json(path):
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


def run_alarm_check():
    log_message("알람 데몬이 보완되어 활성화되었습니다. (초 단위 누락 방지 적용)")

    weekdays_kor = ["월", "화", "수", "목", "금", "토", "일"]
    last_executed_minute = ""

    while True:
        try:
            now = datetime.datetime.now()
            current_time = now.strftime("%H:%M")

            if current_time != last_executed_minute:
                last_executed_minute = current_time

                log_message(f"[CHECK] 분 검사 시작: {current_time}")

                current_date_int = int(now.strftime("%Y%m%d"))
                current_day_kor = weekdays_kor[now.weekday()]
                today_str = now.strftime("%Y/%m/%d")
                yesterday_str = (
                    now - datetime.timedelta(days=1)
                ).strftime("%Y/%m/%d")

                log_message(
                    f"[DATE] today={today_str}, "
                    f"yesterday={yesterday_str}, "
                    f"weekday={current_day_kor}"
                )

                schedule = load_json(CACHE_FILE)
                tasks = load_json(TASK_FILE)

                if not schedule:
                    log_message("[SKIP] schedule 로드 실패")
                    time.sleep(45)
                    continue

                if today_str not in schedule:
                    log_message(f"[SKIP] 오늘 일정 없음: {today_str}")
                    time.sleep(45)
                    continue

                t_info = schedule[today_str]
                y_info = schedule.get(yesterday_str)

                today_type = t_info.get('work_type', "미정")
                yesterday_type = (
                    y_info.get('work_type', "없음")
                    if y_info else "없음"
                )

                pos_today = get_my_position(t_info, MY_NAME)
                pos_yesterday = get_my_position(y_info, MY_NAME)

                is_weekend = now.weekday() >= 5
                is_holiday = t_info.get('holiday', "") != ""

                log_message(
                    f"[STATUS] "
                    f"today_type={today_type}, "
                    f"yesterday_type={yesterday_type}, "
                    f"pos_today={pos_today}, "
                    f"pos_yesterday={pos_yesterday}, "
                    f"weekend={is_weekend}, "
                    f"holiday={is_holiday}"
                )

                if not tasks:
                    log_message("[SKIP] task 로드 실패")
                    time.sleep(45)
                    continue

                log_message(f"[TASK] 총 task 수: {len(tasks)}")

                for task in tasks:
                    try:
                        task_id = task.get('id')
                        task_name = task.get('name', '이름없음')

                        if task_id == 0:
                            continue

                        log_message(
                            f"[TASK:{task_id}] 검사 시작 - {task_name}"
                        )

                        # 1. 기간/요일/시간 기본 필터
                        s_date = task.get('start_date', "")
                        e_date = task.get('end_date', "")

                        if s_date and current_date_int < int(s_date):
                            log_message(
                                f"[TASK:{task_id}] "
                                f"SKIP 시작일 이전 "
                                f"({current_date_int} < {s_date})"
                            )
                            continue

                        if e_date and current_date_int > int(e_date):
                            log_message(
                                f"[TASK:{task_id}] "
                                f"SKIP 종료일 이후 "
                                f"({current_date_int} > {e_date})"
                            )
                            continue

                        w_days = task.get('work_days', [])

                        if w_days and (
                            current_day_kor not in w_days
                        ):
                            log_message(
                                f"[TASK:{task_id}] "
                                f"SKIP 요일 불일치 "
                                f"({current_day_kor} not in {w_days})"
                            )
                            continue

                        task_time = task.get('time')

                        if task_time != current_time:
                            continue

                        log_message(
                            f"[TASK:{task_id}] 시간 일치 "
                            f"({task_time})"
                        )

                        # 2. 오늘 근무 형태 필터
                        work_types = task.get('work_type', [])

                        if today_type not in work_types:
                            log_message(
                                f"[TASK:{task_id}] "
                                f"SKIP 근무형태 불일치 "
                                f"({today_type} not in {work_types})"
                            )
                            continue

                        # 3. 주말/휴일 스킵 필터
                        if (
                            task.get('skip_on_weekend', False)
                            and is_weekend
                        ):
                            log_message(
                                f"[TASK:{task_id}] "
                                f"SKIP 주말 제외"
                            )
                            continue

                        if (
                            task.get('skip_on_holiday', False)
                            and is_holiday
                        ):
                            log_message(
                                f"[TASK:{task_id}] "
                                f"SKIP 휴일 제외"
                            )
                            continue

                        # 4. 어제 근무 및 위치 필터
                        y_cond = task.get(
                            'if_yesterday_was', []
                        )
                        target_pos = task.get(
                            'position', []
                        )

                        if y_cond:
                            if yesterday_type not in y_cond:
                                log_message(
                                    f"[TASK:{task_id}] "
                                    f"SKIP 어제근무 불일치 "
                                    f"({yesterday_type} "
                                    f"not in {y_cond})"
                                )
                                continue

                            if pos_yesterday not in target_pos:
                                log_message(
                                    f"[TASK:{task_id}] "
                                    f"SKIP 어제위치 불일치 "
                                    f"({pos_yesterday} "
                                    f"not in {target_pos})"
                                )
                                continue
                        else:
                            if pos_today not in target_pos:
                                log_message(
                                    f"[TASK:{task_id}] "
                                    f"SKIP 오늘위치 불일치 "
                                    f"({pos_today} "
                                    f"not in {target_pos})"
                                )
                                continue

                        # 5. 알람 전송
                        msg = task.get(
                            'message',
                            f"[알림] "
                            f"{task.get('name', '미명명 업무')} "
                            f"시간입니다."
                        )

                        log_message(
                            f"[TASK:{task_id}] "
                            f"전송 시도: {msg}"
                        )

                        send_ntfy(msg)

                    except Exception as e:
                        log_message(
                            f"[TASK:{task_id}] "
                            f"task 처리 오류: {str(e)}"
                        )

                time.sleep(45)

            time.sleep(1)

        except Exception as e:
            log_message(
                f"[LOOP ERROR] while 루프 오류: {str(e)}"
            )
            time.sleep(5)


def send_ntfy(msg):
    tail = "\nFromOxiFile"
    full_msg = f"{msg}{tail}"

    try:
        log_message("[NTFY] POST 요청 시작")

        response = requests.post(
            "https://ntfy.sh/sbhmission",
            data=full_msg.encode('utf-8'),
            timeout=5
        )

        if response.status_code == 200:
            log_message(f"[NTFY] 전송 성공: {msg}")
        else:
            log_message(
                f"[NTFY] 전송 실패 "
                f"(코드: {response.status_code})"
            )

    except Exception as e:
        log_message(
            f"[NTFY] 전송 중 예외 발생: {str(e)}"
        )


if __name__ == "__main__":
    try:
        run_alarm_check()
    except Exception as e:
        log_message(
            f"[FATAL] 데몬 치명적 오류 발생: {e}"
        )
