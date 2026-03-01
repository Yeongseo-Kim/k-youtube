#!/bin/bash
# ============================================
# K-Content YouTube Shorts — 초기 환경 설정
# ============================================
# 사용법: bash setup.sh
# ============================================

set -e  # 오류 발생 시 즉시 중단

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " K-Content Shorts 환경 설정 시작"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Python 버전 확인
python_version=$(python3 --version 2>&1)
echo "✓ Python: $python_version"

# Python 3.10+ 체크
python3 -c "
import sys
if sys.version_info < (3, 10):
    print('✗ Python 3.10 이상이 필요합니다.')
    sys.exit(1)
"

# pip 업그레이드
echo ""
echo "→ pip 업그레이드 중..."
pip install --upgrade pip --quiet

# 의존성 설치
echo "→ 패키지 설치 중... (1~3분 소요)"
pip install -r requirements.txt --quiet

echo "✓ 패키지 설치 완료"

# yt-dlp 최신 버전 확인
echo ""
echo "→ yt-dlp 최신 버전 확인..."
pip install -U yt-dlp --quiet
yt_dlp_version=$(yt-dlp --version 2>&1)
echo "✓ yt-dlp: $yt_dlp_version"

# ffmpeg 확인 (moviepy 필수 의존성)
echo ""
if command -v ffmpeg &> /dev/null; then
    ffmpeg_version=$(ffmpeg -version 2>&1 | head -n 1)
    echo "✓ ffmpeg: 설치됨"
else
    echo "⚠ ffmpeg가 설치되지 않았습니다. moviepy 영상 편집에 필요합니다."
    echo ""
    echo "  macOS:   brew install ffmpeg"
    echo "  Ubuntu:  sudo apt install ffmpeg"
    echo "  Windows: https://ffmpeg.org/download.html"
    echo ""
fi

# .env 파일 생성
echo ""
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ .env 파일 생성됨"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " ⚠ 다음 작업이 필요합니다:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " 1. .env 파일을 열고 API 키를 입력하세요:"
    echo "    - OPENAI_API_KEY"
    echo "    - GEMINI_API_KEY"
    echo ""
    echo " 2. YouTube OAuth 설정 (기획서 5장 참고):"
    echo "    - Google Cloud Console에서 OAuth JSON 다운로드"
    echo "    - credentials/youtube_oauth.json 에 저장"
    echo "    - python src/uploader.py --auth-only 실행"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "✓ .env 파일이 이미 존재합니다."
fi

# credentials 폴더 생성
mkdir -p credentials output

# 설정 검증 실행
echo ""
echo "→ 설정 검증 중..."
python3 config.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 설정 완료!"
echo ""
echo " 테스트 실행:"
echo "   python main.py --dry-run"
echo ""
echo " 전체 실행:"
echo "   python main.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
