"""
세린 파이프라인 — 설정
모든 설정값은 이 파일에서만 관리 (하드코딩 금지)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 로드
load_dotenv()


def _get(key: str, default: str = "") -> str:
    """환경변수(.env 포함)에서 값 읽기"""
    return os.getenv(key, default)

# ── 경로 설정 ──
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")

# ── OpenAI (TTS 오디션) ──
OPENAI_API_KEY = _get("OPENAI_API_KEY")
TTS_MODEL = _get("TTS_MODEL") or "tts-1-hd"

# ── Gemini (TTS 오디션) ──
GEMINI_API_KEY = _get("GEMINI_API_KEY")

# ── ElevenLabs (보이스 · 효과음 · BGM) ──
ELEVENLABS_API_KEY = _get("ELEVENLABS_API_KEY")

# ── BytePlus ModelArk (Seedance 영상 생성) ──
MODELARK_API_KEY = _get("MODELARK_API_KEY")
MODELARK_BASE_URL = _get("MODELARK_BASE_URL") or "https://ark.ap-southeast.bytepluses.com/api/v3"
# 캐릭터 락(omni reference-to-video) 지원 + 최저가 모델
MODELARK_VIDEO_MODEL = _get("MODELARK_VIDEO_MODEL") or "dreamina-seedance-2-0-mini-260615"

# ── YouTube ──
_yt_secret_raw = _get("YOUTUBE_CLIENT_SECRET") or "credentials/youtube_oauth.json"
YOUTUBE_CLIENT_SECRET = str(BASE_DIR / _yt_secret_raw) if not os.path.isabs(_yt_secret_raw) else _yt_secret_raw

# ── YouTube OAuth (클라우드 배포용 refresh token 방식) ──
YOUTUBE_REFRESH_TOKEN = _get("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_OAUTH_CLIENT_ID = _get("YOUTUBE_OAUTH_CLIENT_ID")
YOUTUBE_OAUTH_CLIENT_SECRET = _get("YOUTUBE_OAUTH_CLIENT_SECRET")
UPLOAD_PRIVACY = os.getenv("UPLOAD_PRIVACY", "private")


def validate():
    """필수 설정값 검증"""
    errors = []
    if not MODELARK_API_KEY:
        errors.append("MODELARK_API_KEY가 설정되지 않았습니다. (영상 컷 생성)")
    if not ELEVENLABS_API_KEY:
        errors.append("ELEVENLABS_API_KEY가 설정되지 않았습니다. (보이스·효과음·BGM)")
    if not Path(YOUTUBE_CLIENT_SECRET).exists() and not YOUTUBE_REFRESH_TOKEN:
        errors.append(f"YouTube OAuth JSON을 찾을 수 없습니다: {YOUTUBE_CLIENT_SECRET}")
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

    console.print("\n[bold]세린 파이프라인 — 설정 검증[/bold]\n")
    console.print(f"  ModelArk Key:    {'✓ 설정됨' if MODELARK_API_KEY else '✗ 미설정'}")
    console.print(f"  ElevenLabs Key:  {'✓ 설정됨' if ELEVENLABS_API_KEY else '✗ 미설정'}")
    console.print(f"  OpenAI Key:      {'✓ 설정됨' if OPENAI_API_KEY else '✗ 미설정 (오디션용)'}")
    console.print(f"  Gemini Key:      {'✓ 설정됨' if GEMINI_API_KEY else '✗ 미설정 (오디션용)'}")
    console.print(f"  YouTube OAuth:   {'✓ 파일 존재' if Path(YOUTUBE_CLIENT_SECRET).exists() else '✗ 파일 없음'}")
    console.print(f"  Upload Privacy:  {UPLOAD_PRIVACY}")
    console.print(f"  Output Dir:      {OUTPUT_DIR}")

    errors = validate()
    if errors:
        console.print("\n[bold red]⚠ 문제 발견:[/bold red]")
        for e in errors:
            console.print(f"  [red]• {e}[/red]")
    else:
        console.print("\n[bold green]✓ 모든 설정이 정상입니다.[/bold green]")
