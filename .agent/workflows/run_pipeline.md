---
description: 전체 파이프라인 실행 방법
---

# 파이프라인 실행 워크플로우

## 사전 요구사항
1. `.env` 파일에 API 키 설정 완료
2. `credentials/youtube_oauth.json` 존재
3. `ffmpeg` 설치 완료 (`ffmpeg -version`)

## 초기 환경 설정 (최초 1회)

// turbo
1. 환경 설정 스크립트 실행
```
bash setup.sh
```

2. YouTube OAuth 토큰 취득 (최초 1회, 브라우저 열림)
```
python src/uploader.py --auth-only
```

## 방법 A — 웹 대시보드 (추천)

// turbo
3. Streamlit 미션 컨트롤 실행
```
cd /Users/eldrac/Desktop/youtube/k-content-shorts && streamlit run app.py
```
브라우저에서 `http://localhost:8501` 접속.
대시보드에서 [▶ 뉴스 리서치 실행] 버튼으로 시작. 각 체크포인트에서 대본/에셋/썸네일/영상 확인 후 승인.

## 방법 B — 터미널 인터랙티브 (체크포인트 대기)

4. 인터랙티브 모드 실행
```
python main.py --interactive
```
각 체크포인트에서 `y/n` 입력으로 승인/중지.

## 방법 C — 전체 자동 실행 (무인 실행)

// turbo
5. 드라이런 (업로드 제외)
```
python main.py --dry-run
```

6. 전체 파이프라인 자동 실행
```
python main.py
```

## 단계별 재개 (오류 복구)

7. 특정 단계부터 재개
```
python main.py --step [단계번호]
```
- `--step 2`: 대본 생성부터
- `--step 3`: 에셋 수집부터
- `--step 5`: 영상 편집부터
- `--step 6`: 업로드만 재실행

## 결과물 확인

// turbo
8. 오늘 날짜 폴더에서 결과 확인
```
ls output/$(date +%Y-%m-%d)/
```
