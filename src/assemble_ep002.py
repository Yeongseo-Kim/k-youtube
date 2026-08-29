"""
[조립] episode-002 — 유나 · 100배 맛있어지는 맥주잔

자막=대사 규칙(branding.md §8): SUBTITLES는 VOICE와 같은 문장·같은 시각을 쓴다.
컷 슬롯은 보이스 실측 길이에 맞춰 잡았다 (총 35.0초).

자막은 drawtext가 아니라 **PIL로 렌더한 투명 PNG를 overlay**로 얹는다 —
이 맥의 ffmpeg 빌드에 freetype(drawtext)이 빠져 있어서다. overlay는 어느 빌드에나 있다.

CUT 4(택배)는 still_package.png에 줌인만 입힌 스틸 컷이다.
BGM·효과음은 output/ep002/audio/ 에 파일이 있으면 얹고 없으면 건너뛴다.

실행: python3 -m src.assemble_ep002
"""

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console

console = Console()

FFMPEG = shutil.which("ffmpeg")
if not FFMPEG:
    raise RuntimeError("ffmpeg을 찾을 수 없습니다.")

# (폰트 경로, ttc 페이스 인덱스) — 맥은 Apple SD 산돌고딕 Bold(6)
_FONT_CANDIDATES = [
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
]
_font_pick = next(((p, i) for p, i in _FONT_CANDIDATES if Path(p).exists()), None)
if not _font_pick:
    raise RuntimeError("한글 폰트를 찾을 수 없습니다.")
FONT_PATH, FONT_INDEX = _font_pick

SRC_DIR = Path("output/ep002/cuts")
WORK_DIR = Path("output/ep002/work")
VOICE_DIR = Path("output/ep002/voice_eleven_v3")   # ElevenLabs v3 + 감정 태그
AUDIO_DIR = Path("output/ep002/audio")
STILL_PACKAGE = Path("assets/yuna/still_package.png")
FINAL = Path("output/ep002/episode-002.mp4")

W, H = 720, 1280
FONT_SIZE = 40
WRAP_CHARS = 15
Y_SUB = 880

# 컷 구성: (소스, 슬롯 길이, 배속, 소스 시작초) — 배속<1은 슬로우. "STILL"은 택배 스틸 컷.
# cut1은 상상 컷(cut1d)을 사이에 두고 홀림(1a)/가격 충격(1b)으로 쪼개 쓴다.
# ElevenLabs 보이스가 짧고 펀치 있어서 쇼츠 템포로 전체 32.5초.
CUTS = [
    ("cut1.mp4", 3.4, 0.79, 0.0),    # 1a 홀림
    ("cut1d.mp4", 5.1, 1.96, 0.0),   # 상상 — 맥주 망상 (압축)
    ("cut1.mp4", 1.2, 1.15, 2.6),    # 1b 가격 충격 (상상에서 추락)
    ("cut2.mp4", 3.9, 1.03, 0.0),    # 시무룩
    ("cut3.mp4", 4.4, 0.91, 0.0),    # 번뜩 → 아싸
    ("STILL",    1.5, 1.0, 0.0),     # 딩동 · 택배
    ("cut5.mp4", 3.0, 1.33, 0.0),    # 언박싱
    ("cut6.mp4", 1.6, 2.50, 0.0),    # 냉장고 대시
    ("cut7.mp4", 5.0, 1.0, 0.0),     # ★붓기 머니샷 (유지)
    ("cut8a.mp4", 2.6, 1.54, 0.0),   # 원샷
    ("cut8b.mp4", 4.2, 0.95, 0.0),   # 최고!
]

# 보이스: (파일명, 시작초) — 시각은 영상 전체 기준
VOICE = [
    ("01_hook_a", 0.3),
    ("01_cool", 2.7),
    ("01_imagine", 5.1),
    ("01_kya", 7.6),
    ("01_hook_b", 8.8),
    ("02_sulk", 10.0),
    ("03_idea", 13.8),
    ("03_yes", 15.7),
    ("05_arrive", 19.9),
    ("08_kya", 30.8),
    ("08_final", 32.0),
    ("08_best", 35.1),
]

# 자막 = 대사와 같은 문장·같은 시각 (branding.md §8)
SUBTITLES = [
    ("우와… 이 잔 뭐야…", 0.3, 2.5),
    ("보기만 해도 시원하잖아…", 2.7, 4.8),
    ("여기에 맥주 딱 하면…", 5.1, 7.3),
    ("크으~", 7.6, 8.2),
    ("5만 원…?", 8.8, 9.6),
    ("아무리 그래도 잔 하나에 5만 원은…", 10.0, 13.6),
    ("혹시… 인터넷?!", 13.8, 15.5),
    ("쿠팡 2만 원?! 아싸!", 15.7, 17.9),
    ("왔다…!", 19.9, 21.8),
    ("캬아~", 30.8, 31.5),
    ("기다린 보람이 있잖아~!", 32.0, 35.0),
    ("최고!", 35.1, 35.8),
]

# 강조 — 대사에 있는 단어만 키운다 (2만 원 반전): (텍스트, 시작, 끝, 크기, 색, y)
EMPHASIS = [
    ("2만 원?!", 15.7, 17.9, 76, "#F28C39", 500),
]

# 가격표 오버레이 — 상상에서 추락하는 1b 구간에 등장. 컷 확인 후 좌표 조정.
PRICE_TAG = ("₩50,000", 8.5, 9.7, 46, "white", 750)

BGM = "bgm.mp3"
BGM_GAIN = 0.16
SFX_GAIN = 0.34
# (파일, 시작초) — output/ep002/audio/ 에 파일이 생기면 자동으로 얹는다
SFX = [
    ("sfx_thud.mp3", 8.6),        # 가격 충격 "쿵" (상상 추락)
    ("sfx_dingdong.mp3", 18.2),   # 초인종
    ("sfx_dash.mp3", 22.6),       # 후다닥
    ("sfx_can_open.mp3", 24.3),   # 캔 칙-
    ("sfx_pour.mp3", 25.1),       # 따르는 소리
    ("sfx_sparkle.mp3", 35.1),    # 최고! 반짝
]


def run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]✗ ffmpeg 실패[/red]\n{result.stderr[-1500:]}")
        raise RuntimeError("ffmpeg 실패")


def wrap(text: str, limit: int = WRAP_CHARS) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


_label_seq = 0


def render_label(text: str, size: int = FONT_SIZE, color: str = "white",
                 box: bool = True) -> Path:
    """자막 한 덩어리를 투명 PNG로 렌더한다. box=False면 외곽선 텍스트."""
    global _label_seq
    _label_seq += 1
    path = WORK_DIR / f"label_{_label_seq:03d}.png"

    font = ImageFont.truetype(FONT_PATH, size, index=FONT_INDEX)
    lines = wrap(text)
    spacing = 12
    stroke = 0 if box else max(2, size // 16)

    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    widths, heights = [], []
    for line in lines:
        l, t, r, b = probe.textbbox((0, 0), line, font=font, stroke_width=stroke)
        widths.append(r - l)
        heights.append(b - t)
    line_h = max(heights)
    text_w, text_h = max(widths), line_h * len(lines) + spacing * (len(lines) - 1)

    pad = 16 if box else stroke + 4
    img = Image.new("RGBA", (text_w + pad * 2, text_h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if box:
        draw.rounded_rectangle((0, 0, img.width - 1, img.height - 1),
                               radius=12, fill=(0, 0, 0, 140))
    y = pad
    for i, line in enumerate(lines):
        lw = widths[i]
        draw.text(((img.width - lw) // 2, y), line, font=font, fill=color,
                  stroke_width=stroke, stroke_fill=(0, 0, 0, 220), anchor="lt")
        y += line_h + spacing

    img.save(path)
    return path


def overlays_for_cut(cut_start: float, cut_end: float) -> list[tuple[Path, int, float, float]]:
    """이 컷 구간에 걸치는 자막·강조·가격표를 (PNG, y, 상대시작, 상대끝)으로 돌려준다."""
    out = []

    def clip(start, end):
        return max(start, cut_start) - cut_start, min(end, cut_end) - cut_start

    for text, start, end in SUBTITLES:
        if end <= cut_start or start >= cut_end:
            continue
        s, e = clip(start, end)
        out.append((render_label(text), Y_SUB, s, e))
    for text, start, end, size, color, y in EMPHASIS:
        if end <= cut_start or start >= cut_end:
            continue
        s, e = clip(start, end)
        out.append((render_label(text, size, color, box=False), y, s, e))
    text, start, end, size, color, y = PRICE_TAG
    if not (end <= cut_start or start >= cut_end):
        s, e = clip(start, end)
        out.append((render_label(text, size, color, box=False), y, s, e))
    return out


def overlay_chain(first_label: str, labels: list[tuple[Path, int, float, float]]) -> str:
    """[v0]에 라벨들을 차례로 overlay하는 필터 문자열. 입력 인덱스는 1부터."""
    chain = ""
    for k, (_, y, s, e) in enumerate(labels):
        src = first_label if k == 0 else f"[v{k}]"
        chain += (f";{src}[{k + 1}:v]overlay=(main_w-overlay_w)/2:{y}:"
                  f"enable='between(t,{s:.2f},{e:.2f})'[v{k + 1}]")
    return chain


def make_still(duration: float, labels, output: Path) -> None:
    """택배 스틸에 느린 줌인을 입힌다."""
    frames = int(duration * 30)
    args = [FFMPEG, "-y", "-v", "error", "-loop", "1", "-t", str(duration),
            "-i", str(STILL_PACKAGE)]
    for path, _, _, _ in labels:
        args += ["-i", str(path)]
    chain = (f"[0:v]scale={W * 2}:{H * 2},"
             f"zoompan=z='1+0.06*on/{frames}':d={frames}:s={W}x{H}:fps=30[v0]")
    chain += overlay_chain("[v0]", labels)
    label = f"[v{len(labels)}]"
    run(args + ["-filter_complex", chain, "-map", label, "-t", str(duration),
                "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", str(output)])


def prepare_cut(index: int, name: str, duration: float, speed: float,
                cut_start: float, ss: float = 0.0) -> Path:
    output = WORK_DIR / f"{index:02d}_{Path(name).stem}.mp4"
    labels = overlays_for_cut(cut_start, cut_start + duration)

    if name == "STILL":
        make_still(duration, labels, output)
        console.print(f"  [green]✓[/green] [{index}] 택배 스틸 → {duration}초")
        return output

    args = [FFMPEG, "-y", "-v", "error"]
    if ss > 0:
        args += ["-ss", str(ss)]
    args += ["-i", str(SRC_DIR / name)]
    for path, _, _, _ in labels:
        args += ["-i", str(path)]

    chain = f"[0:v]scale={W}:{H}"
    if speed != 1.0:
        chain += f",setpts=PTS/{speed}"
    chain += ",fps=30[v0]"
    chain += overlay_chain("[v0]", labels)
    label = f"[v{len(labels)}]"

    run(args + ["-t", str(duration), "-filter_complex", chain, "-map", label, "-an",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", str(output)])
    console.print(f"  [green]✓[/green] [{index}] {name} → {duration}초"
                  + (f" [dim](x{speed})[/dim]" if speed != 1.0 else ""))
    return output


def mux_audio(video: Path, output: Path, total: float) -> None:
    """보이스 + (있으면) BGM·효과음. BGM은 보이스에 사이드체인 더킹."""
    voices = [(start, VOICE_DIR / f"{name}.mp3")
              for name, start in VOICE if (VOICE_DIR / f"{name}.mp3").exists()]
    if not voices:
        console.print("[yellow]⚠ 보이스 파일이 없어 무음으로 출력합니다.[/yellow]")
        video.replace(output)
        return

    args = [FFMPEG, "-y", "-v", "error", "-i", str(video)]
    parts, idx, labels = [], 1, []
    for start, path in voices:
        args += ["-i", str(path)]
        delay = int(start * 1000)
        parts.append(f"[{idx}:a]adelay={delay}|{delay},aformat=sample_rates=44100:"
                     f"channel_layouts=stereo[v{idx}]")
        labels.append(f"[v{idx}]")
        idx += 1
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0[voice]")

    sfx_labels = []
    for name, start in SFX:
        path = AUDIO_DIR / name
        if not path.exists():
            continue
        args += ["-i", str(path)]
        delay = int(start * 1000)
        parts.append(f"[{idx}:a]adelay={delay}|{delay},volume={SFX_GAIN},"
                     f"aformat=sample_rates=44100:channel_layouts=stereo[s{idx}]")
        sfx_labels.append(f"[s{idx}]")
        idx += 1

    bgm_path = AUDIO_DIR / BGM
    if bgm_path.exists():
        args += ["-i", str(bgm_path)]
        parts.append(f"[{idx}:a]volume={BGM_GAIN},afade=t=out:st={total - 2.5}:d=2.5,"
                     f"aformat=sample_rates=44100:channel_layouts=stereo[bgmraw]")
        parts.append("[voice]asplit=2[voice_out][voice_sc]")
        parts.append("[bgmraw][voice_sc]sidechaincompress="
                     "threshold=0.03:ratio=12:attack=15:release=350[bgm]")
        mix_in = "[voice_out][bgm]" + "".join(sfx_labels)
        count = 2 + len(sfx_labels)
    else:
        mix_in = "[voice]" + "".join(sfx_labels)
        count = 1 + len(sfx_labels)

    parts.append(f"{mix_in}amix=inputs={count}:normalize=0,alimiter=limit=0.95,apad[out]")
    run(args + ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[out]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", str(total), str(output)])
    console.print(f"  [green]✓[/green] 보이스 {len(voices)} · 효과음 {len(sfx_labels)} · "
                  f"BGM {'있음' if bgm_path.exists() else '없음'}")


def main() -> Path:
    console.print("\n[bold blue]━━ episode-002 조립 ━━[/bold blue]\n")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    missing = [n for n, _, _, _ in CUTS if n != "STILL" and not (SRC_DIR / n).exists()]
    if missing:
        console.print(f"[red]✗ 컷 파일 없음: {missing} — 생성이 끝난 뒤 실행하세요.[/red]")
        raise SystemExit(1)

    segments, cursor = [], 0.0
    for i, (name, duration, speed, ss) in enumerate(CUTS):
        segments.append(prepare_cut(i, name, duration, speed, cursor, ss))
        cursor += duration

    concat_list = WORK_DIR / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in segments),
                           encoding="utf-8")
    silent = WORK_DIR / "silent.mp4"
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(silent)])

    mux_audio(silent, FINAL, cursor)
    size_mb = FINAL.stat().st_size / 1e6
    console.print(f"\n[bold green]✓ 완성: {FINAL}[/bold green]  "
                  f"[dim]{cursor:.1f}초 / {size_mb:.1f}MB / {W}x{H}[/dim]\n")
    return FINAL


if __name__ == "__main__":
    main()
