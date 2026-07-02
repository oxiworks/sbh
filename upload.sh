#!/bin/bash

# 1. 스크립트가 있는 현재 폴더 경로로 강제 이동
cd "$(dirname "$0")"

# 🌟 [보완] GitHub Pages 404 에러 방지를 위해 index.html을 404.html로 자동 갱신
cp -f index.html 404.html

# 2. 로컬의 모든 변경 사항(추가, 수정, 삭제 등)을 등록
git add -A

# 3. 변경 사항이 한 줄이라도 있는지 검사
if ! git diff --cached --quiet; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 변경 사항이 감지되었습니다. 로컬 커밋을 생성합니다."

    # 4. 임시 자동 커밋 생성
    git commit -m "자동 업데이트: 파일 변경 사항 반영 ($(date '+%Y-%m-%d %H:%M:%S'))"

    # 5. 🌟 [구조 교정] 실시간 로그 파일 충돌 방지를 위한 안전한 동기화
    # rebase 도중 충돌이 나면 자동으로 내 로컬 파일(--strategy-option=theirs)을 선택하도록 강제합니다.
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] GitHub 원격 저장소와 안전하게 동기화 중..."
    if ! git pull origin main --rebase -X theirs; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ 동기화 락 감지! 깃 상태를 초기화하고 강제 진행합니다."
        git rebase --abort > /dev/null 2>&1
    fi

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
    # 🌟 로컬 변경이 없을 때도 혹시 모를 락 방지를 위해 안전장치 추가
    git pull origin main --rebase -X theirs > /dev/null 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 변경된 파일이 없습니다."
fi
