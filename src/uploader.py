"""
[모듈 6] 유튜브 업로드 — YouTube Data API v3

입력: final_video.mp4 + thumbnail.png + metadata.json
출력: 유튜브 게시 완료 (Video ID 반환)

최초 1회: python src/uploader.py --auth-only 로 OAuth 토큰 취득
이후: 자동 갱신
"""

import json
import argparse
from pathlib import Path
from rich.console import Console

import config

console = Console()

# Google API 클라이언트
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    console.print("[yellow]⚠ google-api-python-client가 설치되지 않았습니다.[/yellow]")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
TOKEN_PATH = Path("credentials/youtube_token.json")


def get_authenticated_service():
    """OAuth 2.0 인증 및 YouTube 서비스 객체 반환
    
    우선순위:
    1. config.YOUTUBE_REFRESH_TOKEN (Streamlit Cloud Secrets) — 클라우드 배포 시
    2. credentials/youtube_token.json — 로컬 개발 시
    3. 브라우저 OAuth 플로우 — 초기 설정 시 (로컬만 가능)
    """
    creds = None

    # ── 방법 1: Secrets에서 refresh token으로 인증 (클라우드 배포용) ──
    if config.YOUTUBE_REFRESH_TOKEN and config.YOUTUBE_OAUTH_CLIENT_ID:
        console.print("  [dim]YouTube Secrets refresh token으로 인증 중...[/dim]")
        creds = Credentials(
            token=None,
            refresh_token=config.YOUTUBE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=config.YOUTUBE_OAUTH_CLIENT_ID,
            client_secret=config.YOUTUBE_OAUTH_CLIENT_SECRET,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)

    # ── 방법 2: 로컬 토큰 파일 ──
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # 토큰 없거나 만료됨
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            console.print("  [dim]OAuth 토큰 갱신 중...[/dim]")
            creds.refresh(Request())
        else:
            console.print("  [cyan]브라우저에서 Google 계정 인증이 필요합니다...[/cyan]")
            flow = InstalledAppFlow.from_client_secrets_file(
                config.YOUTUBE_CLIENT_SECRET, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 토큰 저장
        TOKEN_PATH.parent.mkdir(exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        console.print(f"  [green]✓ 토큰 저장 완료: {TOKEN_PATH}[/green]")

    return build("youtube", "v3", credentials=creds)



def _trim_tags(tags_str: str, max_chars: int = 500) -> list[str]:
    """태그 문자열을 YouTube API 500자 제한에 맞게 잘라 리스트로 반환"""
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    result, total = [], 0
    for tag in tags:
        if total + len(tag) + (1 if result else 0) > max_chars:
            break
        result.append(tag)
        total += len(tag) + (1 if len(result) > 1 else 0)
    return result


def upload_video(
    youtube,
    video_path: Path,
    metadata: dict,
    privacy: str = None,
) -> str:
    """영상 업로드 및 Video ID 반환"""
    privacy = privacy or config.UPLOAD_PRIVACY

    body = {
        "snippet": {
            "title": metadata.get("title", "K-Content Update")[:100],
            "description": metadata.get("description", "#Shorts"),
            "tags": _trim_tags(metadata.get("tags", "")),
            "categoryId": "24",  # Entertainment
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,  # 5MB 청크
    )

    console.print(f"  [dim]업로드 시작: {video_path.name} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)[/dim]")

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            console.print(f"  [dim]  업로드 {pct}%...[/dim]", end="\r")

    video_id = response["id"]
    console.print(f"\n  [green]✓ 업로드 완료! Video ID: {video_id}[/green]")
    console.print(f"  [cyan]  → https://www.youtube.com/shorts/{video_id}[/cyan]")
    return video_id


# 타겟 언어 — 일본·중국·동남아 K-content 주요 시장
LOCALIZATION_TARGETS = {
    "ja":      "Japanese",
    "zh-Hans": "Simplified Chinese",
    "zh-TW":   "Traditional Chinese",
    "fil":     "Filipino (Tagalog)",
    "id":      "Indonesian",
    "th":      "Thai",
    "vi":      "Vietnamese",
}


def translate_and_localize(youtube, video_id: str, metadata: dict):
    """GPT로 제목·설명 다국어 번역 → YouTube localizations API 등록"""
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    title_en = metadata.get("title", "")
    desc_en = metadata.get("description", "")

    console.print(f"  [dim]🌏 다국어 번역 중 ({len(LOCALIZATION_TARGETS)}개 언어)...[/dim]")

    lang_list = "\n".join(
        f'"{code}": translate to {name}'
        for code, name in LOCALIZATION_TARGETS.items()
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content":
            f"Translate the following YouTube Shorts title and description for K-content fans.\n\n"
            f"TITLE (English): {title_en}\n"
            f"DESCRIPTION (English): {desc_en}\n\n"
            f"Translate into these languages:\n{lang_list}\n\n"
            f"Rules:\n"
            f"- Keep hashtags (#Shorts #Kpop etc.) in original English at the end\n"
            f"- Title: keep under 60 chars, keep energy and excitement\n"
            f"- Description: natural, culturally appropriate tone for K-content fans\n"
            f"- Return ONLY valid JSON: {{\"ja\": {{\"title\": \"...\", \"description\": \"...\"}}, ...}}"
        }],
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    translations = json.loads(resp.choices[0].message.content)

    # YouTube localizations 등록
    localizations = {}
    for code, texts in translations.items():
        if isinstance(texts, dict) and "title" in texts:
            localizations[code] = {
                "title": texts["title"][:100],
                "description": texts.get("description", desc_en),
            }

    if not localizations:
        console.print("  [yellow]⚠ 번역 결과 없음[/yellow]")
        return

    youtube.videos().update(
        part="localizations,snippet",
        body={
            "id": video_id,
            "snippet": {
                "title": title_en[:100],
                "description": desc_en,
                "categoryId": "24",
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
                "tags": _trim_tags(metadata.get("tags", "")),
            },
            "localizations": localizations,
        },
    ).execute()

    console.print(f"  [green]✓ 다국어 설정 완료: {', '.join(localizations.keys())}[/green]")


def set_thumbnail(youtube, video_id: str, thumbnail_path: Path):
    """썸네일 설정"""
    if not thumbnail_path.exists():
        console.print("  [yellow]⚠ 썸네일 파일 없음 — 스킵[/yellow]")
        return

    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/png"),
    ).execute()
    console.print(f"  [green]✓ 썸네일 설정 완료[/green]")


def run(output_dir: Path, video_path: Path, thumbnail_path: Path, metadata_path: Path) -> str:
    """업로드 모듈 실행"""
    console.print("\n[bold blue]━━ [6/6] 유튜브 업로드 시작 ━━[/bold blue]")

    if not GOOGLE_API_AVAILABLE:
        raise RuntimeError("google-api-python-client가 설치되지 않았습니다.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    # 1. 인증
    youtube = get_authenticated_service()

    # 2. 영상 업로드 (3회 재시도)
    video_id = None
    for attempt in range(1, 4):
        try:
            video_id = upload_video(youtube, video_path, metadata)
            break
        except Exception as e:
            console.print(f"  [yellow]업로드 실패 (시도 {attempt}/3): {e}[/yellow]")
            if attempt == 3:
                raise

    # 3. 썸네일 설정
    set_thumbnail(youtube, video_id, thumbnail_path)

    # 4. 다국어 제목/설명 설정
    try:
        translate_and_localize(youtube, video_id, metadata)
    except Exception as e:
        console.print(f"  [yellow]⚠ 다국어 설정 실패: {e}[/yellow]")

    # 5. 결과 저장
    result = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "privacy": config.UPLOAD_PRIVACY,
    }
    (output_dir / "upload_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )

    return video_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth-only", action="store_true", help="OAuth 토큰 취득만 실행")
    args = parser.parse_args()

    if args.auth_only:
        console.print("[bold]YouTube OAuth 인증 시작...[/bold]")
        get_authenticated_service()
        console.print("[bold green]✓ 인증 완료. 이제 main.py를 실행하세요.[/bold green]")
    else:
        output_dir = config.get_today_output_dir()
        run(
            output_dir,
            output_dir / "final_video.mp4",
            output_dir / "thumbnail.png",
            output_dir / "metadata.json",
        )
