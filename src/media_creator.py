"""
[모듈 4] 미디어 생성 — TTS 음성 + Whisper 자막 + Gemini 썸네일

입력: script.txt + metadata.json
출력: audio.mp3 + subtitle.srt + thumbnail.png
"""

import json
from pathlib import Path
from openai import OpenAI
import google.generativeai as genai
from rich.console import Console

import config
from src import reviewer

console = Console()


def generate_audio(script_text: str, output_path: Path) -> Path:
    """OpenAI TTS로 영어 내레이션 음성 생성"""
    console.print("  [dim]🎙 TTS 음성 생성 중...[/dim]")
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    response = client.audio.speech.create(
        model=config.TTS_MODEL,
        voice=config.TTS_VOICE,
        input=script_text,
        response_format="mp3",
        speed=config.TTS_SPEED,
    )
    response.stream_to_file(str(output_path))

    console.print(f"  [green]✓ 음성 생성 완료: {output_path}[/green]")
    return output_path


def generate_subtitles(audio_path: Path, output_path: Path) -> Path:
    """OpenAI Whisper로 음성 → SRT 자막 자동 생성"""
    console.print("  [dim]📝 자막 생성 중 (Whisper)...[/dim]")
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model=config.WHISPER_MODEL,
            file=f,
            response_format="srt",
        )

    output_path.write_text(transcript, encoding="utf-8")
    console.print(f"  [green]✓ 자막 생성 완료: {output_path}[/green]")
    return output_path


def generate_thumbnail(
    metadata: dict,
    output_path: Path,
    base_image_path: Path = None,
    overlay_text: str = None,
) -> Path:
    """Gemini 네이티브 이미지 생성으로 썸네일 제작

    Args:
        metadata: 제목·태그 등 메타데이터 dict
        output_path: 저장 경로 (.png)
        base_image_path: 베이스로 쓸 에셋 이미지 경로 (None이면 순수 생성)
        overlay_text: 썸네일에 넣을 텍스트 문구 (None이면 자동 생성)
    """
    console.print("  [dim]🎨 Gemini 썸네일 생성 중...[/dim]")

    genai.configure(api_key=config.GEMINI_API_KEY)

    title = metadata.get("title", "K-Content Update")

    text_instruction = (
        f'Use this exact text as a large, bold overlay: "{overlay_text}"'
        if overlay_text
        else f"Generate impactful 2-4 word overlay text based on the title: {title}"
    )

    if base_image_path and Path(base_image_path).exists():
        # ── 이미지 + 텍스트 → Gemini에 합성 요청 ──
        import base64
        with open(base_image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        # MIME 타입 추론
        suffix = Path(base_image_path).suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}
        mime = mime_map.get(suffix, "image/jpeg")

        prompt = f"""You are a YouTube Shorts thumbnail designer.
I'm giving you a reference image. Use it as the background/base and create a stunning 9:16 vertical YouTube Shorts thumbnail (1080x1920).

{text_instruction}

Text style requirements:
- Very large, bold font — must be readable at small sizes
- High contrast color (white with black outline, or bright yellow/gold)
- Place the text in the TOP SECTION only (between 15%~35% from top) — never at the very top (leave a 15% deadzone for UI elements)
- Add subtle glow or shadow for legibility

Overall thumbnail style:
- K-pop / K-drama aesthetic: glossy, vibrant, energetic
- Add dynamic elements: sparkles, light rays, gradient overlays, Korean design motifs
- Eye-catching enough to stop scrolling
- 9:16 portrait format (vertical), 1080x1920 resolution
"""
        content_parts = [
            {"mime_type": mime, "data": img_b64},
            prompt,
        ]
    else:
        # ── 텍스트만으로 순수 생성 ──
        prompt = f"""Create a vibrant YouTube Shorts thumbnail for K-content.
Title: {title}

{text_instruction}

Style requirements:
- Bright, high-contrast colors (pink, purple, gold combinations)
- Bold large text overlay placed in the TOP SECTION (between 15%~35% from top) — leave a 15% deadzone at the very top for UI elements
- K-pop/K-drama aesthetic (glossy, modern, energetic)
- 9:16 portrait orientation, 1080x1920 resolution (vertical, for YouTube Shorts)
- Eye-catching design that stops scrolling
- NO people's faces (copyright safe)
- Include relevant visual elements: stage lights, confetti, sparkles, Korean symbols
"""
        content_parts = [prompt]

    # Gemini REST API 직접 호출 (구형 SDK 오류 회피)
    try:
        import requests
        import base64
        from PIL import Image as _PILImg
        import io as _io

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_IMAGE_MODEL}:generateContent?key={config.GEMINI_API_KEY}"

        # REST API 페이로드 구성
        parts = []
        if base_image_path and Path(base_image_path).exists():
            with open(base_image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            suffix = Path(base_image_path).suffix.lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
            mime = mime_map.get(suffix, "image/jpeg")
            parts.append({"inlineData": {"mimeType": mime, "data": img_b64}})

        parts.append({"text": prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE"]  # REST API에서는 IMAGE만 요청
            }
        }

        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # 이미지 데이터 추출
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError(f"응답에 candidates 없음: {data}")

        parts_out = candidates[0].get("content", {}).get("parts", [])
        image_saved = False

        for p in parts_out:
            if "inlineData" in p and "data" in p["inlineData"]:
                b64_data = p["inlineData"]["data"]
                img_data = base64.b64decode(b64_data)

                # PIL 검증
                try:
                    _PILImg.open(_io.BytesIO(img_data)).verify()
                except Exception as pil_err:
                    console.print(f"  [red]✗ 반환 데이터가 유효한 이미지 아님: {pil_err}[/red]")
                    raise ValueError(f"유효성 검사 실패: {pil_err}")

                output_path.write_bytes(img_data)
                image_saved = True
                break
        
        if not image_saved:
            console.print(f"  [red]✗ 이미지 데이터 없음. 전체 응답: {data}[/red]")
            raise ValueError(f"이미지 데이터 추출 실패. 응답: {data}")

        console.print(f"  [green]✓ 썸네일 생성 완료: {output_path}[/green]")

    except Exception as e:
        console.print(f"  [red]✗ Gemini 썸네일 오류: {e}[/red]")
        raise

    return output_path


def _create_fallback_thumbnail(title: str, output_path: Path):
    """Gemini 실패 시 Pillow로 기본 썸네일 생성"""
    from PIL import Image, ImageDraw, ImageFont

    # 그라데이션 배경
    img = Image.new("RGB", config.THUMBNAIL_SIZE, color=(30, 10, 60))
    draw = ImageDraw.Draw(img)

    # 간단한 텍스트 오버레이
    draw.rectangle([0, 0, *config.THUMBNAIL_SIZE], fill=(30, 10, 60))
    draw.text(
        (config.THUMBNAIL_SIZE[0] // 2, config.THUMBNAIL_SIZE[1] // 2),
        title[:50],
        fill=(255, 220, 100),
        anchor="mm"
    )
    img.save(output_path)


def run(output_dir: Path, script_path: Path, metadata_path: Path) -> tuple[Path, Path, Path]:
    """미디어 생성 모듈 실행"""
    console.print("\n[bold blue]━━ [4/6] 미디어 생성 시작 ━━[/bold blue]")

    script_text = script_path.read_text(encoding="utf-8")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    audio_path = output_dir / "audio.mp3"
    subtitle_path = output_dir / "subtitle.srt"
    thumbnail_path = output_dir / "thumbnail.png"

    # 1. TTS 음성 생성
    generate_audio(script_text, audio_path)

    # 2. Whisper 자막 생성
    generate_subtitles(audio_path, subtitle_path)

    # 3. Gemini 썸네일 생성
    generate_thumbnail(metadata, thumbnail_path)

    # 4. SEO 리뷰 (메타데이터 품질 검사)
    console.print("  [dim]🤖 SEO 리뷰어 검토 중...[/dim]")
    metadata_str = json.dumps(metadata, indent=2)
    seo_review = reviewer.evaluate("seo_optimizer", metadata_str)

    if not seo_review.get("passed") and seo_review.get("improved_title"):
        console.print("  [cyan]SEO 개선사항 적용 중...[/cyan]")
        metadata["title"] = seo_review.get("improved_title", metadata["title"])
        if seo_review.get("improved_tags"):
            metadata["tags"] = seo_review.get("improved_tags", metadata["tags"])
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    return audio_path, subtitle_path, thumbnail_path


if __name__ == "__main__":
    output_dir = config.get_today_output_dir()
    run(
        output_dir,
        output_dir / "script.txt",
        output_dir / "metadata.json"
    )
