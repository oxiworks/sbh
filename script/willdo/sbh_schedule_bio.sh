#!/bin/bash



## 근무시간표 웹페이지용 데이터 생성 스크립트 실행
`python3 /home/oxisnail/script/sbh_mission.py`



### 스크립트 설정
#### mode=(test,normal) test시, SMS 및 NTFY 의 테크를 test 로 변경 날짜,시간을 지정값으로 변경, 지정 안되어 있으면 기본 동작

# CONFIGURATION PART------------------------------

#mode="test"
team_name="bio"

test_date="2025/12/29"       # format: 2024-06-31
test_time="16"               # format: 주간,당직 07~08(0꼭 붙일것)  , 야간 16~17

# ------------------------------------------------


logfile="/home/oxisnail/script/${team_name}_sch_script.log"
{

    echo "[$(date)_sbh_schedule_${team_name}.sh] ###스크립트 시작###"

    logger "${0##*/} : Start Script"


    now_day=$(date +"%Y/%m/%d")
    now_time=$(date +"%H")
    now_ym=$(date +"%Y%m")


    # 테스트 모드 변수 설정 완료
    if [ "$mode" = "test" ];then #  test 모드 시, 변수 설정
        echo "[$(date)_sbh_schedule_${team_name}.sh] **테스트 모드 입니다"
        now_day="$test_date"
        now_time="$test_time"
        now_ym=$(printf "%s" "${test_date//\//}" | cut -c1-6)
        echo now_ym=${now_ym}
    fi


    if [[ $now_ym -le 202512 ]]; then
        schfile="/home/oxisnail/data/schedule/sbh_${team_name}/finish_sbh_timetable_${team_name}.xlsm"
	echo $schfile
    else
        schfile="/home/oxisnail/data/schedule/sbh_${team_name}/${team_name}_schedule_2026.xlsm"
	echo $schfile
    fi

    csvfile="/var/www/html/sbh_${team_name}/schedule.csv"
    sendflag="0"

    # schedule.csv 추출
    ssconvert -S --export-type=Gnumeric_stf:stf_csv $schfile /tmp/schedule_${team_name}.csv
    mv /tmp/schedule_${team_name}.csv.7 $csvfile


    # 오늘날짜 스케줄 읽어오기
    line=`grep $now_day $csvfile`
    sch_day=$(echo $line|cut -f 1 -d ',')
    work_type=$(echo $line|cut -f 2 -d ',')
    a_mission=$(echo $line|cut -f 13 -d ','|sed -e 's/"//g')

    #변수내용 출력	
    echo "[$(date)_sbh_schedule_${team_name}.sh] [검색결과]"
    echo "[$(date)_sbh_schedule_${team_name}.sh] --조건:검색일, 검색시간-"
    echo "[$(date)_sbh_schedule_${team_name}.sh] ---현재날짜: $now_day"
    echo "[$(date)_sbh_schedule_${team_name}.sh] ---현재시간: $now_time"
    echo "[$(date)_sbh_schedule_${team_name}.sh] "
    echo "[$(date)_sbh_schedule_${team_name}.sh] --조건 검색된 내용-"
    echo "[$(date)_sbh_schedule_${team_name}.sh] ---전체내용: $line"
    echo "[$(date)_sbh_schedule_${team_name}.sh] "
    echo "[$(date)_sbh_schedule_${team_name}.sh] ---변수_날짜: $sch_day"
    echo "[$(date)_sbh_schedule_${team_name}.sh] ---변수_근무: $work_type"
    echo "[$(date)_sbh_schedule_${team_name}.sh] ---변수_담당(전송 메시지):"
    echo "[$(date)_sbh_schedule_${team_name}.sh] >>> $a_mission"
    echo "[$(date)_sbh_schedule_${team_name}.sh] "
    echo "[$(date)_sbh_schedule_${team_name}.sh] [처리결과]"

    #스케줄 내용별 동작
    if [ "$work_type" = "비번" ] || [ "$work_type" = "휴무" ];then # 스케줄에 오늘 날짜 확인
        echo "[$(date)_sbh_schedule_${team_name}.sh] -근무없음. 메시지 전송 안함"
    fi

    if [ "$now_day" = "$sch_day" ];then # 스케줄에 오늘 날짜 확인
        if [ "$now_time" = "07" ] || [ "$now_time" = "08" ];then
            if [ "$work_type" = "당직" ] || [ "$work_type" = "주간" ];then # '당직/주간' 인지?
                sendflag="1"
                echo "[$(date)_sbh_schedule_${team_name}.sh] -$work_type근무확인"
            fi
        fi

        if [ "$now_time" = "16" ] || [ "$now_time" = "17" ];then
            if [ "$work_type" = "야간" ];then
                sendflag="1"
                echo "[$(date)_sbh_schedule_${team_name}.sh] -$work_type근무확인"
            fi
        fi


        echo "[$(date)_sbh_schedule_${team_name}.sh] sendflag=$sendflag"

        if [ "$sendflag" = "1" ];then
            echo -n "[$(date)_sbh_schedule_${team_name}.sh] 날짜: $sch_day"; echo "[$(date)_sbh_schedule_${team_name}.sh]  근무형태: $work_type"
            echo "[$(date)_sbh_schedule_${team_name}.sh] $a_mission"

            ## 테스트 모드 NTFY.SH SBHTEST 로 메시지 전송
            if [ "$mode" = "test" ];then
                echo "[$(date)_sbh_schedule_${team_name}.sh] 테스트 모드 메시지 전송"
                ## 메시지 전송 부분
                # Message Send to TELEGRAM
                #printf "$a_mission" | /home/oxisnail/.local/bin/telegram-send --stdin
            
                # Message Send to NTFY
                curl -s -d "`printf "$a_mission"`" ntfy.sh/sbhtest

                # Today Mission Send to NTFY
#                sleep 5 ; /home/oxisnail/script/sbh_mission_${team_name}.sh
            fi

            if [[ "$mode" != "test" ]];then
                ## 메시지 전송 부분
                # Message Send to TELEGRAM
                #printf "$a_mission" | /home/oxisnail/.local/bin/telegram-send --stdin
                #echo "[$(date)_sbh_schedule_${team_name}.sh] -SMS 전송을 완료하였습니다."

                # Message Send to NTFY
                curl -s -d "`printf "$a_mission"`" ntfy.sh/sbh${team_name}
                echo "[$(date)_sbh_schedule_${team_name}.sh] -NTFY.SH 전송을 완료하였습니다."
                
                # Today Mission Send to NTFY
                sleep 3 ; /home/oxisnail/script/sbh_mission_${team_name}.sh

                # Today Move Schedule to NTFY
                sleep 3 ; /home/oxisnail/script/sbh_move.sh
            fi
        fi
    fi

    echo "[$(date)_sbh_schedule_${team_name}.sh] ###스크립트 종료###"

} >> "$logfile" 2>&1
