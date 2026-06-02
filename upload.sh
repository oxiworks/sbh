#!/bin/bash

# 1. 스크립트가 있는 현재 폴더 경로로 강제 이동
cd "$(dirname "$0")"

# 2. 로컬의 모든 변경 사항(추가, 수정, _CNAME 삭제 등)을 먼저 안전하게 등록(Stage)
git add -A

# 3. 변경 사항이 한 줄이라도 있는지 검사
if ! git diff --cached --quiet; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 변경 사항이 감지되었습니다. 로컬 커밋을 생성합니다."
    
    # 4. 임시 자동 커밋 생성
    git commit -m "자동 업데이트: 파일 변경 사항 반영 ($(date '+%Y-%m-%d %H:%M:%S'))"
    
    # 5. [핵심 순서 교정] 커밋이 완료된 깔끔한 상태에서 깃허브 최신 내용을 가져와 합침
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub 원격 저장소와 동기화 중..."
    git pull origin main --rebase
    
    # 6. 최종 GitHub으로 밀어내기(Push)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub 업로드를 시작합니다."
    if git push origin main; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub 최종 업로드 성공!"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ 일반 푸시 실패. 강제 동기화(--force)를 시도합니다."
        git push origin main --force
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub 강제 업로드 완료!"
    fi
else
    # 로컬에 바뀐 파일은 없지만 원격에 혹시 모를 새 데이터가 있을 수 있으므로 안전을 위한 동기화
    git pull origin main --rebase > /dev/null 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 변경된 파일이 없습니다."
fi

