#!/bin/bash

## 오늘 업무 추출 스크립트
`python3 /home/oxisnail/script/sbh_mission.py`

now_date=$(date +"%Y-%m-%d")
now_time=$(date +"%H")
now_dayofweek=$(date +"%w")   # 0=Sunday, 1=Monday...3=Wednesday...5=Friday 6=Saturday

csvfile="/tmp/mission.csv"
sendflag="0"


# TEST PARAMETER
#now_date="2025-12-13"       # format: 2024-06-31
#now_dayofweek="6"       # format: 0=Sunday, 1=Monday...3=Wednesday...5=Friday 6=Saturday


logfile="/tmp/sbh_mission_bio.log"
{
    echo "[$(date)_sbh_mission_bio.sh] ###스크립트 시작###"

	# 데이터 형식:
	# 100,오늘의 업무,2025-03-16 00:00:00,,,,,,2025-03-16 00:00:00
	
    # 오늘날짜 스케줄 읽어오기
    mission_date=`grep $now_date $csvfile`
    m_date=$(echo "$mission_date"|cut -f 2 -d ',') # cut index 는 1부터 시작함# cut index 는 1부터 시작함
    m_day_mission=$(echo "$mission_date"|cut -f 1 -d ',')

	echo "[$(date)_sbh_mission_bio.sh] m_date = $m_date"

    # 오늘요일 스케줄 읽어오기
    mission_dayofweek=`awk -F',' '($3 == '$now_dayofweek')' $csvfile`

        echo "[$(date)_sbh_mission_bio.sh] mission_dayofweek = $mission_dayofweek"

    m_dayofweek=$(echo "$mission_dayofweek"|cut -f 3 -d ',')  # cut index 는 1부터 시작함
    m_dayofweek_mission=$(echo "$mission_dayofweek"|cut -f 1 -d ',')


        echo "[$(date)_sbh_mission_bio.sh] m_dayofweek_mission = $m_dayofweek_mission"


    if [ "$m_day_mission" != "" ] || [ "$m_dayofweek_mission" != "" ];then
        if [ "$m_day_mission" = "" ] && [ "$m_dayofweek_mission" != "" ];then # 내용 채우기
                m_day_mission="-없음-"
        fi
        if [ "$m_day_mission" != "" ] && [ "$m_dayofweek_mission" = "" ];then # 내용 채우기
                m_dayofweek_mission="-없음-"
        fi
        sendflag="1"
    fi

    echo "[$(date)_sbh_mission_bio.sh] -------------------------------------------"
    echo "[$(date)_sbh_mission_bio.sh] [작업 내역]"
    echo "[$(date)_sbh_mission_bio.sh] - 현재날짜: $now_date , 현재요일: $now_dayofweek (0~6:일~토)"
    echo "[$(date)_sbh_mission_bio.sh] - 추출날짜: $m_date  , 추출요일: $m_dayofweek (0~6:일~토)"
    echo "[$(date)_sbh_mission_bio.sh] - 오늘 날짜업무 내용"
    echo "[$(date)_sbh_mission_bio.sh] $m_day_mission"
    echo "[$(date)_sbh_mission_bio.sh] "
    echo "[$(date)_sbh_mission_bio.sh] - 오늘 요일업무 내용"
    echo "[$(date)_sbh_mission_bio.sh] $m_dayofweek_mission"
    echo "[$(date)_sbh_mission_bio.sh] "
    echo "[$(date)_sbh_mission_bio.sh] - 메시지 전송 내용 작성"



# 전송 메시지 작성 시작
formatted_day=$(echo "$m_day_mission" | sed 's/:/ : /' | column -t -s ':' | sed 's/^/  /')
formatted_week=$(echo "$m_dayofweek_mission" | sed 's/:/ : /' | column -t -s ':' | sed 's/^/  /')

message=$(cat <<EOF
📅 금일 업무($now_date)
$formatted_day

⚙️ 고정 업무
$formatted_week

FromOxiFile
EOF
)

# 최종 출력
echo "$message"
# 확인
echo "$message"


    echo "$m_day_mission"
    echo "-------------------------------------------"
# 전송 메시지 작성 끝

    echo "[$(date)_sbh_mission_bio.sh] $message"


    if [ "$sendflag" == "1" ];then
        echo "[$(date)_sbh_mission_bio.sh] [NTFY.SH 전송]"
        printf "  "
        curl -s -d "`printf "$message"`" ntfy.sh/sbhmission
        printf "  "
        echo "[$(date)_sbh_mission_bio.sh] NTFY.SH 메시지 전송 완료"
    fi

    #스케줄 내용별 동작
    #if [ $work_type = "비번" ] || [ $work_type = "휴무" ];then # 스케줄에 오늘 날짜 확인
    #        echo "[$(date)_sbh_mission_bio.sh] -근무없음. 메시지 전송 안함"
    #fi
    #if [[ "$mode" != "test" ]];then
    #fi


    echo "[$(date)_sbh_mission_bio.sh] ###스크립트 종료###"

} >> "$logfile" 2>&1
