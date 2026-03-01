"""
[모듈 5] 영상 편집 — MoviePy로 최종 쇼츠 영상 합성

입력: audio.mp3 + assets/ + subtitle.srt
출력: final_video.mp4 (9:16, 1080x1920, ≤60초)

특징:
- 이미지: Ken Burns 이펙트 (줌인 + 패닝)
- 비디오 클립: center crop → 9:16
- 씬 간 crossfade 전환
- 하단 자막 자동 삽입
"""

import re
from pathlib import Path
from datetime import datetime
from rich.console import Console

import config

console = Console()

# Pillow 10+ 호환 패치 (ANTIALIAS → LANCZOS)
try:
    from PIL import Image as _PILImage
    if not hasattr(_PILImage, "ANTIALIAS"):
        _PILImage.ANTIALIAS = _PILImage.LANCZOS
except Exception:
    pass

# MoviePy import — 설치 필요: pip install moviepy
try:
    from moviepy.editor import (
        VideoFileClip, ImageClip, AudioFileClip,
        concatenate_videoclips, CompositeVideoClip,
    )
    from moviepy.video.fx.all import crop, resize
    import numpy as np
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    console.print("[yellow]⚠ moviepy가 설치되지 않았습니다. pip install moviepy[/yellow]")


def parse_srt(srt_path: Path) -> list[dict]:
    """SRT 파일 파싱 → [{start, end, text}, ...]"""
    srt_text = srt_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\d+\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)",
        re.DOTALL
    )

    def to_seconds(ts: str) -> float:
        h, m, s_ms = ts.split(":")
        s, ms = s_ms.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    subtitles = []
    for match in pattern.finditer(srt_text):
        subtitles.append({
            "start": to_seconds(match.group(1)),
            "end": to_seconds(match.group(2)),
            "text": match.group(3).replace("\n", " ").strip(),
        })
    return subtitles


def ken_burns_effect(image_clip, zoom_ratio: float = None, duration: float = None):
    """이미지에 Ken Burns 이펙트 (줌인 + 느린 패닝) 적용"""
    zoom_ratio = zoom_ratio or config.KEN_BURNS_ZOOM
    duration = duration or image_clip.duration

    def zoom_and_pan(t):
        # 시간에 따라 1.0 → zoom_ratio 선형 보간
        scale = 1.0 + (zoom_ratio - 1.0) * (t / duration)
        return scale

    return image_clip.resize(zoom_and_pan)


def load_scene_clip(asset_path: Path, duration: float, target_size: tuple) -> object:
    """에셋 파일을 씬 클립으로 로드 (영상/이미지 자동 판별)"""
    w, h = target_size
    suffix = asset_path.suffix.lower()

    if suffix in [".mp4", ".mov", ".avi", ".webm"]:
        # 비디오 클립
        clip = VideoFileClip(str(asset_path))
        clip = clip.without_audio()  # 원본 오디오 제거 (내레이션만 사용)

        # 9:16 center crop
        clip_ratio = clip.w / clip.h
        target_ratio = w / h
        if clip_ratio > target_ratio:
            clip = crop(clip, width=int(clip.h * target_ratio), x_center=clip.w / 2)
        else:
            clip = crop(clip, height=int(clip.w / target_ratio), y_center=clip.h / 2)

        clip = resize(clip, (w, h))
        clip = clip.subclip(0, min(duration, clip.duration))
        if clip.duration < duration:
            clip = clip.loop(duration=duration)

    elif suffix in [".jpg", ".jpeg", ".png", ".webp"]:
        # 이미지 클립 → Ken Burns
        clip = ImageClip(str(asset_path), duration=duration)
        clip = clip.resize((w, h))
        clip = ken_burns_effect(clip, duration=duration)

    else:
        raise ValueError(f"지원하지 않는 파일 형식: {suffix}")

    return clip.set_duration(duration)


def _split_into_chunks(subtitles: list[dict], words_per_chunk: int = 3) -> list[dict]:
    """SRT 자막을 Shorts 스타일로 2~3단어씩 분할"""
    chunks = []
    for sub in subtitles:
        words = sub["text"].split()
        duration = sub["end"] - sub["start"]
        if not words or duration <= 0:
            continue
        n = max(1, (len(words) + words_per_chunk - 1) // words_per_chunk)
        step = duration / n
        for i in range(n):
            chunk_words = words[i * words_per_chunk:(i + 1) * words_per_chunk]
            chunks.append({
                "start": sub["start"] + i * step,
                "end": sub["start"] + (i + 1) * step,
                "text": " ".join(chunk_words),
            })
    return chunks


def _make_draw_fn(chunks: list[dict], video_size: tuple):
    """Pillow 기반 자막 드로우 함수 반환 — fl(gf, t) 에 사용"""
    from PIL import Image as PILImg, ImageDraw, ImageFont

    w, h = video_size
    font_size = max(80, w // 12)  # 1080px 기준 약 90px

    # Impact → Arial Bold → 기본 폰트 순으로 시도
    font = None
    for fp in [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    ]:
        try:
            font = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    y_center = int(h * 0.80)  # 화면 80% 지점 (하단)

    def draw_frame(frame, t):
        # MoviePy 프로브 프레임 방어 (비정상 크기)
        if frame.shape[0] < 100 or frame.shape[1] < 100:
            return frame

        text = next((c["text"] for c in chunks if c["start"] <= t < c["end"]), None)
        if not text:
            return frame.astype(np.uint8)

        img = PILImg.fromarray(frame.astype(np.uint8))  # RGB
        draw = ImageDraw.Draw(img)

        # 텍스트 크기 측정
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (w - tw) // 2
        y = y_center - th // 2

        # 반투명 박스 — paste 방식 (alpha_composite 사용 안 함)
        pad = 22
        box = PILImg.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 160))
        img_rgba = img.convert("RGBA")
        img_rgba.paste(box, (x - pad, y - pad), box)
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

        # 외곽선 (stroke 4px)
        stroke = 4
        for dx in range(-stroke, stroke + 1):
            for dy in range(-stroke, stroke + 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))

        # 흰색 텍스트
        draw.text((x, y), text, font=font, fill=(255, 255, 255))

        return np.array(img, dtype=np.uint8)

    return draw_frame


def add_subtitles(base_clip, subtitles: list[dict], video_size: tuple) -> object:
    """Pillow 기반 Shorts 스타일 자막 합성 (ImageMagick 불필요)"""
    chunks = _split_into_chunks(subtitles, words_per_chunk=3)
    if not chunks:
        return base_clip
    draw_fn = _make_draw_fn(chunks, video_size)
    console.print(f"  [dim]자막 청크: {len(chunks)}개[/dim]")
    return base_clip.fl(lambda gf, t: draw_fn(gf(t), t))


def run(output_dir: Path, audio_path: Path, assets_dir: Path, subtitle_path: Path) -> Path:
    """영상 편집 모듈 실행"""
    console.print("\n[bold blue]━━ [5/6] 영상 편집 시작 ━━[/bold blue]")

    if not MOVIEPY_AVAILABLE:
        raise RuntimeError("moviepy가 설치되지 않았습니다. setup.sh를 실행하세요.")

    target_size = config.VIDEO_RESOLUTION  # (1080, 1920)

    # 1. 오디오 로드 및 길이 측정
    audio = AudioFileClip(str(audio_path))
    total_duration = min(audio.duration, config.VIDEO_MAX_DURATION)
    console.print(f"  [dim]오디오 길이: {total_duration:.1f}초[/dim]")

    # 2. 에셋 파일 목록 수집
    asset_files = sorted([
        f for f in assets_dir.iterdir()
        if f.suffix.lower() in [".mp4", ".mov", ".jpg", ".jpeg", ".png", ".webp"]
    ])

    if not asset_files:
        raise FileNotFoundError(f"에셋 파일이 없습니다: {assets_dir}")

    console.print(f"  [dim]{len(asset_files)}개 에셋으로 영상 구성[/dim]")

    # 3. 썸네일 준비 (씬과 동일 비중으로 분배)
    thumbnail_path = output_dir / "thumbnail.png"
    has_thumb = thumbnail_path.exists()

    # 4. 씬당 시간 균등 분배 (썸네일 포함 총 클립 수 기준)
    total_clips = len(asset_files) + (1 if has_thumb else 0)
    scene_duration = total_duration / total_clips

    thumb_clip = None
    if has_thumb:
        try:
            thumb_clip = load_scene_clip(thumbnail_path, scene_duration, target_size)
            console.print("  [dim]썸네일 클립 포함[/dim]")
        except Exception as e:
            console.print(f"  [yellow]⚠ 썸네일 클립 생성 실패: {e}[/yellow]")

    # 5. 씬 클립 생성
    scene_clips = []
    loaded_clips = []  # 렌더링 후 명시적 해제를 위한 추적 리스트
    for i, asset_path in enumerate(asset_files):
        console.print(f"  [dim]  씬 {i+1}/{len(asset_files)}: {asset_path.name}[/dim]")
        try:
            clip = load_scene_clip(asset_path, scene_duration, target_size)
            scene_clips.append(clip)
            loaded_clips.append(clip)
        except Exception as e:
            console.print(f"  [yellow]  ⚠ 씬 {i+1} 로드 실패: {e} — 스킵[/yellow]")

    if not scene_clips:
        raise RuntimeError("모든 씬 로드 실패. 에셋을 확인하세요.")

    # 6. 클립 연결 — 썸네일 + 씬들 (crossfade)
    crossfade = config.CROSSFADE_DURATION
    all_clips = ([thumb_clip] if thumb_clip else []) + scene_clips
    final_clip = concatenate_videoclips(
        all_clips,
        method="compose",
        padding=-crossfade,
    )

    # 6. 자막 합성
    if subtitle_path.exists():
        console.print("  [dim]자막 합성 중...[/dim]")
        subtitles = parse_srt(subtitle_path)
        if subtitles:
            final_clip = add_subtitles(final_clip, subtitles, target_size)

    # 7. 오디오 합성
    final_clip = final_clip.set_audio(audio)
    final_clip = final_clip.subclip(0, total_duration)

    # 8. 렌더링
    output_path = output_dir / "final_video.mp4"
    console.print(f"  [dim]렌더링 중... (시간이 걸릴 수 있습니다)[/dim]")

    final_clip.write_videofile(
        str(output_path),
        fps=config.VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate=config.VIDEO_BITRATE,
        preset="fast",
        verbose=False,
        logger=None,
    )

    # 9. 정리
    final_clip.close()
    audio.close()
    for clip in loaded_clips:
        try:
            clip.close()
        except Exception:
            pass

    console.print(f"  [green]✓ 영상 렌더링 완료: {output_path}[/green]")
    console.print(f"  [dim]  크기: {output_path.stat().st_size / 1024 / 1024:.1f} MB[/dim]")

    return output_path


if __name__ == "__main__":
    output_dir = config.get_today_output_dir()
    run(
        output_dir,
        output_dir / "audio.mp3",
        output_dir / "assets",
        output_dir / "subtitle.srt",
    )
