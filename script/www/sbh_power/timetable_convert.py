import pandas as pd
import json
from collections import OrderedDict
import datetime

def excel_to_js():
    file_name = 'power_schedule_2026.xlsm'
    sheet_name = 'cal2'
    
    ROW_MAP = {
        "날짜": 0, "요일": 3, "공휴일": 5, "근무": 7,
        "지원동": 33, "글로벌": 34, "외곽-1": 35, "외곽-2": 36
    }
    
    try:
        df = pd.read_excel(file_name, sheet_name=sheet_name, header=None, engine='openpyxl')
        schedule_data = OrderedDict()
        
        print(f"--- 데이터 변환 시작 (총 {df.shape[1]-1}열 대상) ---")

        for col_idx in range(1, df.shape[1]):
            raw_val = df.iloc[ROW_MAP["날짜"], col_idx]
            if pd.isna(raw_val): continue
                
            try:
                if isinstance(raw_val, (datetime.datetime, pd.Timestamp)):
                    d = raw_val
                elif isinstance(raw_val, (int, float)):
                    d = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(raw_val))
                else:
                    d = pd.to_datetime(str(raw_val).strip())
            except:
                continue

            date_key = d.strftime('%Y-%m-%d')
            item = OrderedDict()
            
            for key, row_idx in ROW_MAP.items():
                val = df.iloc[row_idx, col_idx]
                
                # 데이터 정제 및 추출 보강
                if pd.isna(val):
                    item[key] = ""
                else:
                    val_str = str(val).strip()
                    # "0", "0.0", "nan" 등은 빈칸 처리
                    if val_str in ["0", "0.0", "nan", "NaN"]:
                        item[key] = ""
                    else:
                        item[key] = val_str
            
            # '근무' 값이 비어있지 않은지 로그 출력 (디버깅용)
            # if item["근무"]: print(f"{date_key}: {item['근무']}")

            schedule_data[date_key] = item

        with open('timetable_data.js', 'w', encoding='utf-8') as f:
            f.write(f"const scheduleData = {json.dumps(schedule_data, ensure_ascii=False, indent=4)};")
            
        print(f"--- 완료: {len(schedule_data)}일치 데이터가 저장되었습니다. ---")

    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    excel_to_js()
