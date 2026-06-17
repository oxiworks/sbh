#!/bin/sh
set -e

# ===== 설정 =====
SPREADSHEET_ID="144VXK8vUlIu2HPOOYJUmm324mdu7oG8bAfkIdf7ckqM"
NTFY_TOPIC="sbhmove"
BASE_URL="https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/export"

# 날짜 매칭용
TODAY_MATCH=$(date '+%Y. %-m. %-d')
TOMORROW_MATCH=$(date -d "next day" '+%Y. %-m. %-d')

# 표시용 날짜
TODAY_DISP=$(date '+%Y-%m-%d')
TOMORROW_DISP=$(date -d "next day" '+%Y-%m-%d')

echo "Processing schedules..."

# ===== 1. 데이터 다운로드 및 가공 =====
send_message=$(curl -sL "${BASE_URL}?format=csv" | awk -F',' \
-v today="$TODAY_MATCH" -v tomorrow="$TOMORROW_MATCH" \
-v t_disp="$TODAY_DISP" -v tm_disp="$TOMORROW_DISP" '
BEGIN {
    today_msg = "[오늘 일정 - " t_disp "]\n\n"
    tomorrow_msg = "[내일 일정 - " tm_disp "]\n\n"
    t_count = 0
    tm_count = 0
}
{
    # 큰따옴표 제거
    for (i=1; i<=NF; i++) gsub(/^"|"$/, "", $i)
    
    datetime = $3
    sub(/:[0-9][0-9]$/, "", datetime)

    # 개별 일정 블록 생성
    item_content = $4 " " $2 "\n"
    item_content = item_content " - 일 정: " datetime "\n"
    if ($6 != "") item_content = item_content " - 대 상: " $6 "\n"
    if ($7 != "") item_content = item_content " - 물품명: " $7 "\n"
    if ($5 != "") item_content = item_content " - 구 분: " $5 "\n"
    item_content = item_content "\n" # 일정 간 공백 한 칸

    # 오늘 날짜 매칭
    if ($3 ~ "^"today) {
        t_count++
        today_msg = today_msg t_count "️⃣ " item_content
    }
    # 내일 날짜 매칭
    else if ($3 ~ "^"tomorrow) {
        tm_count++
        tomorrow_msg = tomorrow_msg tm_count "️⃣ " item_content
    }
}
END {
    if (t_count == 0) today_msg = today_msg "일정이 없습니다.\n\n"
    if (tm_count == 0) tomorrow_msg = tomorrow_msg "일정이 없습니다.\n\n"
    
    # 오늘과 내일 일정 합치기
    printf "%s--------------------\n\n%s\nFromOxiFile", today_msg, tomorrow_msg
}')

# ===== 2. ntfy 전송 =====
echo "$send_message" | curl -s --data-binary @- "ntfy.sh/$NTFY_TOPIC"

echo "[$(date)] - 메시지 전송 완료"
