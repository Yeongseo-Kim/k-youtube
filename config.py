"""
K-Content YouTube Shorts Automation - 설정 관리
로컬: .env 파일에서 로드
Streamlit Cloud: st.secrets에서 로드 (fallback)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 로드 (로컬 개발용)
load_dotenv()


def _get(key: str, default: str = "") -> str:
    """로컬 .env 또는 Streamlit Cloud secrets에서 값 읽기"""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default

# ── 경로 설정 ──
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
CREDENTIALS_DIR = BASE_DIR / "credentials"

# ── OpenAI ──
OPENAI_API_KEY = _get("OPENAI_API_KEY")
LLM_MODEL = "gpt-4o"
TTS_MODEL = _get("TTS_MODEL") or "tts-1-hd"
TTS_VOICE = _get("TTS_VOICE") or "coral"
TTS_SPEED = float(_get("TTS_SPEED") or "1.25")
WHISPER_MODEL = "whisper-1"

# ── Gemini ──
GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_IMAGE_MODEL = _get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image"

# ── YouTube ──
_yt_secret_raw = _get("YOUTUBE_CLIENT_SECRET") or "credentials/youtube_oauth.json"
YOUTUBE_CLIENT_SECRET = str(BASE_DIR / _yt_secret_raw) if not os.path.isabs(_yt_secret_raw) else _yt_secret_raw

# ── YouTube OAuth (클라우드 배포용 refresh token 방식) ──
YOUTUBE_REFRESH_TOKEN = _get("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_OAUTH_CLIENT_ID = _get("YOUTUBE_OAUTH_CLIENT_ID")
YOUTUBE_OAUTH_CLIENT_SECRET = _get("YOUTUBE_OAUTH_CLIENT_SECRET")
UPLOAD_PRIVACY = os.getenv("UPLOAD_PRIVACY", "private")

# ── 파이프라인 설정 ──
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
MAX_DAILY_VIDEOS = int(os.getenv("MAX_DAILY_VIDEOS", "2"))

# ── 콘텐츠 설정 ──
SCRIPT_WORD_COUNT = (70, 110)  # 25~30초 분량 영문 내레이션 (쇼츠 최적화)
VIDEO_RESOLUTION = (1080, 1920)  # 9:16 세로 (width, height)
VIDEO_FPS = 30
VIDEO_MAX_DURATION = 60  # 초
THUMBNAIL_SIZE = (1080, 1920)  # 9:16 세로 (YouTube Shorts)

# ── RSS 피드 소스 ──
RSS_FEEDS = [
    "https://www.soompi.com/feed",
    "https://www.allkpop.com/feed",
    "https://www.koreaboo.com/feed/",
]

# ── yt-dlp 설정 ──
YTDLP_MAX_RESULTS = 5       # 검색 시 최대 결과 수
YTDLP_CLIP_DURATION = 8     # 클립 추출 길이 (초)
YTDLP_FORMAT = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
ASSET_VIDEO_TARGET = 10     # 영상 에셋 목표 개수
ASSET_IMAGE_TARGET = 10     # 이미지 에셋 목표 개수
# YouTube 봇 차단 우회: cookies.txt (Netscape 형식). Streamlit secrets에 YT_COOKIES로 내용 저장 가능
YT_COOKIES_PATH = _get("YT_COOKIES_PATH", "")  # credentials/yt_cookies.txt
YT_COOKIES = _get("YT_COOKIES", "")            # secrets에 cookies 전체 내용

# ── 영상 편집 설정 ──
CROSSFADE_DURATION = 0.4     # 씬 전환 페이드 (초)
KEN_BURNS_ZOOM = 1.15        # 줌인 배율
SUBTITLE_FONT_SIZE = 40
SUBTITLE_FONT_COLOR = "white"
VIDEO_BITRATE = "4M"


def validate():
    """필수 설정값 검증"""
    errors = []
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY가 설정되지 않았습니다.")
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY가 설정되지 않았습니다.")
    if not Path(YOUTUBE_CLIENT_SECRET).exists() and not DRY_RUN:
        errors.append(
            f"YouTube OAuth JSON을 찾을 수 없습니다: {YOUTUBE_CLIENT_SECRET}\n"
            "  → 기획서 5장 'YouTube API 설정 가이드' 참고"
        )
    return errors


def get_today_output_dir():
    """오늘 날짜 기반 출력 폴더 생성 및 반환"""
    from datetime import date
    today_dir = OUTPUT_DIR / date.today().isoformat()
    today_dir.mkdir(parents=True, exist_ok=True)
    (today_dir / "assets").mkdir(exist_ok=True)
    return today_dir


if __name__ == "__main__":
    # 설정 검증 테스트
    from rich.console import Console
    console = Console()

    console.print("\n[bold]K-Content Shorts — 설정 검증[/bold]\n")
    console.print(f"  OpenAI API Key: {'✓ 설정됨' if OPENAI_API_KEY else '✗ 미설정'}")
    console.print(f"  Gemini API Key: {'✓ 설정됨' if GEMINI_API_KEY else '✗ 미설정'}")
    console.print(f"  YouTube OAuth:  {'✓ 파일 존재' if Path(YOUTUBE_CLIENT_SECRET).exists() else '✗ 파일 없음'}")
    console.print(f"  TTS Voice:      {TTS_VOICE}")
    console.print(f"  Upload Privacy: {UPLOAD_PRIVACY}")
    console.print(f"  Dry Run:        {DRY_RUN}")
    console.print(f"  Output Dir:     {OUTPUT_DIR}")

    errors = validate()
    if errors:
        console.print("\n[bold red]⚠ 문제 발견:[/bold red]")
        for e in errors:
            console.print(f"  [red]• {e}[/red]")
    else:
        console.print("\n[bold green]✓ 모든 설정이 정상입니다.[/bold green]")
