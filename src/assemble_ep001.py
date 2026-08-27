"""
[조립] episode-001 — 생성된 컷들을 트림·자막·보이스로 이어 붙여 완성본을 만든다.

자막과 대사는 같은 문장을 쓴다. 숏폼 시청자 상당수가 무음으로 보기 때문에
대사가 곧 자막이어야 한다.

자막 시각은 영상 전체 기준(절대 초)으로 적고, 컷 경계에 맞춰 자동 분배한다 —
한 문장이 컷을 넘어가도 끊기지 않게 하기 위해서다.

실행: python3 -m src.assemble_ep001
"""

import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

# drawtext 필터(freetype)가 필요하므로 시스템 ffmpeg을 쓴다.
# imageio-ffmpeg 번들 바이너리에는 drawtext가 빠져 있다.
FFMPEG = shutil.which("ffmpeg")
if not FFMPEG:
    raise RuntimeError("ffmpeg을 찾을 수 없습니다. apt-get install ffmpeg 로 설치하세요.")
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

SRC_DIR = Path("output/ep001")
WORK_DIR = SRC_DIR / "work"
VOICE_DIR = SRC_DIR / "voice_final"
FINAL = SRC_DIR / "episode-001.mp4"

W, H = 720, 1280
FONT_SIZE = 40
WRAP_CHARS = 15    # 720px 폭에서 40px 글자가 넘치지 않는 한 줄 길이
Y_SUB = 880        # 하단 세이프존(20%) 위. 2줄까지 안전하게 들어간다

# 컷 구성: (파일, 사용 길이, 배속)
# 자르면 동작 뒷부분이 날아가므로 액션 컷은 빨리감기로 줄인다.
# 설명 컷은 대사와 입/동작이 어긋나므로 원속, 엔딩은 미소가 살아야 해 완만하게만.
CUTS = [
    ("cut1.mp4", 3.5, 1.15),
    ("cut2.mp4", 5.75, 1.05),
    ("C3_spray_tissue.mp4", 4.45, 1.80),
    ("edu1_why.mp4", 6.04, 1.0),
    ("edu2_bleach.mp4", 6.04, 1.0),
    ("edu3_crab.mp4", 8.04, 1.0),
    ("C4_peel_result.mp4", 4.15, 1.45),
    ("B2_chestup_rise.mp4", 4.03, 1.50),
]

# 보이스: (파일명, 시작초). 의미 단위로 묶어 생성했다 —
# 문장을 쪼개면 낭독조가 되어 리듬이 끊긴다.
VOICE = [
    ("G1", 0.3),
    ("G2", 3.8),
    ("G3", 9.6),
    ("G4", 14.1),
    ("G5", 20.7),
    ("G6", 27.1),
    ("G7", 35.3),
    ("G8", 39.4),
]

# 자막: (텍스트, 시작초, 끝초) — 영상 전체 기준 절대 시각. 대사와 동일한 문장.
SUBTITLES = [
    ("변기에 묻은 이거 안 생기게 하는 법 알려줄게", 0.3, 3.2),
    ("이건 물때가 아니라 요석이라고 하는 거야", 3.8, 6.4),
    ("요석은 알칼리성이라 산으로 녹일 수 있어", 6.4, 9.1),
    ("구연산 뿌리고 휴지 덮어두면 돼", 9.6, 11.8),
    ("소변 속 요소가 세균을 만나면 암모니아가 나오고", 14.1, 17.5),
    ("물이 알칼리로 변하면서 미네랄이 굳어", 17.5, 20.3),
    ("락스는 알칼리라서 알칼리인 요석을 못 녹여", 20.7, 23.8),
    ("색깔만 하얘지고 더러운 게 남아있는 거야", 23.8, 26.7),
    ("구연산이 굳은 미네랄을 집게처럼 붙잡아 녹여", 27.1, 30.3),
    ("이걸 킬레이션이라고 해", 30.3, 32.0),
    ("아예 녹여내니까 락스보다 훨씬 오래가", 32.0, 34.7),
    ("기다렸다 벗기면 말끔히 지워져", 35.3, 37.7),
    ("청소 끝", 39.4, 40.5),
]

# 칠판 판서 — 컷 파일명 → (텍스트, x식, y, 크기, 색). 분필처럼 박스 없이 흰 글씨로 얹는다.
# 빈 칠판은 어색하고, AI에게 직접 쓰게 하면 한글이 깨져서 오버레이로 처리한다.
# 아래첨자(₂ ³ ⁺)는 Noto Sans CJK에 글리프가 없어 두부로 깨지므로 일반 숫자를 쓴다.
BOARDS = {
    "edu1_why.mp4": [
        ("CO(NH2)2  →  NH3\n요소            암모니아\n\npH ↑  →  미네랄 결정",
         "(w-text_w)/2", 240, 36, "white@0.92"),
    ],
    "edu2_bleach.mp4": [
        ("NaOCl  (알칼리)", "(w-text_w)/2", 210, 38, "white@0.92"),
        ("X", "(w-text_w)/2", 268, 56, "red@0.9"),
        ("CaCO3  (알칼리)", "(w-text_w)/2", 336, 38, "white@0.92"),
    ],
    "edu3_crab.mp4": [
        ("chelate ← chele\n그리스어로 '게 집게'", "60", 240, 36, "white@0.92"),
        ("C6H8O7 + Ca2+\n→ 물에 녹는 형태", "60", 380, 34, "white@0.88"),
    ],
}

# ── 사운드 ──────────────────────────────────────────────
AUDIO_DIR = SRC_DIR / "audio"
BGM = "bgm_B_light.mp3"
BGM_GAIN = 0.16          # 보이스 대비 약 -16dB. 더킹이 추가로 눌러준다
SFX_GAIN = 0.34

# (파일, 시작초) — 화면에서 그 동작이 실제로 일어나는 시점에 맞춘다
SFX = [
    ("01_lid.mp3", 0.25),            # 훅 시작, 뚜껑 탁
    ("06_flush.mp3", 4.6),           # CUT2에서 실제로 물을 내린다
    ("02_spray.mp3", 9.7),           # 구연산 분사
    ("03_tissue_lay.mp3", 11.2),     # 휴지 덮기
    ("04_transition.mp3", 13.6),     # 욕실 → 칠판
    ("09_transition_back.mp3", 33.7),  # 칠판 → 욕실 복귀
    ("05_tissue_peel.mp3", 35.3),    # 휴지 떼기
    ("10_brush.mp3", 36.5),          # 솔로 한 번 문지르기
    # 반짝임은 컷 전환(37.97s)보다 먼저 시작해야 소리가 컷을 이끈다.
    ("08_sparkle.mp3", 37.5),        # 솔질 직후 반짝, 여운이 엔딩으로 넘어간다

]


# 컷별 이미지 오버레이 — 컬러 이모지는 drawtext(freetype)에서 색이 빠지므로
# PNG로 렌더해 overlay 필터로 합성한다.
IMAGE_OVERLAYS = {
    "edu3_crab.mp4": [("assets/serin/crab.png", 450, 288)],
}

# 시간 경과 카드 — 결과가 즉효처럼 보이면 조작 의심을 사므로 시간을 명시한다
TIMECARD_TEXT = "20분 뒤"


def run(args: list[str]) -> None:
    """ffmpeg 호출. 실패 시 stderr를 그대로 노출한다."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]✗ ffmpeg 실패[/red]\n{result.stderr[-1500:]}")
        raise RuntimeError("ffmpeg 실패")


def wrap(text: str, limit: int = WRAP_CHARS) -> str:
    """긴 문장을 단어 단위로 접는다. 720px 폭을 넘으면 글자가 잘린다."""
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
    return "\n".join(lines)


_text_file_seq = 0


def drawtext(text: str, start: float, end: float, size: int = FONT_SIZE,
             y: int = Y_SUB, color: str = "white", box: str = "black@0.55") -> str:
    """자막 하나를 drawtext 필터 문자열로 만든다.

    text= 대신 textfile=을 쓴다. 필터그래프 문자열 안에서는 줄바꿈과 한글을
    이스케이프하기가 까다로워, 실제 개행이 든 파일로 넘기는 편이 확실하다.
    """
    global _text_file_seq
    _text_file_seq += 1
    path = WORK_DIR / f"sub_{_text_file_seq:03d}.txt"
    path.write_text(wrap(text), encoding="utf-8")
    return (
        f"drawtext=fontfile={FONT_BOLD}:textfile={path}:"
        f"fontsize={size}:fontcolor={color}:x=(w-text_w)/2:y={y}:"
        f"line_spacing=12:box=1:boxcolor={box}:boxborderw=16:"
        f"enable='between(t,{start},{end})'"
    )



def chalk(text: str, x: str, y: int, size: int, color: str,
          start: float, end: float) -> str:
    """칠판 판서용 오버레이. 박스 없이 흰 글씨 + 옅은 그림자로 분필처럼 보이게 한다."""
    global _text_file_seq
    _text_file_seq += 1
    path = WORK_DIR / f"board_{_text_file_seq:03d}.txt"
    path.write_text(text, encoding="utf-8")
    return (
        f"drawtext=fontfile={FONT_BOLD}:textfile={path}:fontsize={size}:"
        f"fontcolor={color}:x={x}:y={y}:line_spacing=16:"
        f"shadowcolor=black@0.35:shadowx=2:shadowy=2:"
        f"enable='between(t,{start},{end})'"
    )


def subs_for_cut(cut_start: float, cut_end: float) -> str:
    """이 컷 구간에 걸치는 자막을 골라 컷 기준 상대 시각으로 변환한다.

    한 문장이 컷 경계를 넘으면 양쪽 컷에 나눠 그린다 — 이어 붙이면 연속으로 보인다.
    """
    parts = []
    for text, start, end in SUBTITLES:
        if end <= cut_start or start >= cut_end:
            continue
        rel_start = max(start, cut_start) - cut_start
        rel_end = min(end, cut_end) - cut_start
        parts.append(drawtext(text, rel_start, rel_end))
    return ",".join(parts)


def make_timecard(source: Path, output: Path, duration: float) -> None:
    """직전 컷의 마지막 프레임을 정지시켜 시간 경과 카드를 만든다."""
    still = WORK_DIR / "timecard_still.png"
    run([FFMPEG, "-y", "-v", "error", "-sseof", "-0.5", "-i", str(source),
         "-vsync", "0", "-frames:v", "1", "-update", "1", str(still)])
    run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-t", str(duration), "-i", str(still),
         "-vf", f"scale={W}:{H},eq=brightness=-0.06", "-r", "30",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)])


def prepare_cut(index: int, name: str, duration: float, speed: float,
                cut_start: float) -> Path:
    """컷 하나를 트림 + 자막 처리해 중간 파일로 저장한다.

    끝부분 트림이 중요하다 — AI 생성 영상은 마지막 몇 프레임에서 동작이
    뭉개지는 경우가 잦아, 잘라내야 이어 붙였을 때 깔끔하다.
    """
    output = WORK_DIR / f"{index:02d}_{Path(name).stem}.mp4"

    source = SRC_DIR / name
    layers = [chalk(t, x, y, size, color, 0.3, duration)
              for t, x, y, size, color in BOARDS.get(name, [])]
    subs = subs_for_cut(cut_start, cut_start + duration)
    if subs:
        layers.append(subs)
    overlay = ",".join(layers)

    images = IMAGE_OVERLAYS.get(name, [])
    args = [FFMPEG, "-y", "-v", "error", "-i", str(source)]
    for path, _, _ in images:
        args += ["-i", path]

    # setpts로 배속 — 자막은 배속 후 시간축 기준이라 그대로 얹으면 된다
    chain = f"[0:v]scale={W}:{H}"
    if speed != 1.0:
        chain += f",setpts=PTS/{speed}"
    chain += ",fps=30"
    if overlay:
        chain += f",{overlay}"
    chain += "[v0]"
    for i, (_, ix, iy) in enumerate(images):
        chain += f";[v{i}][{i + 1}:v]overlay={ix}:{iy}[v{i + 1}]"
    label = f"[v{len(images)}]"

    run(args + ["-t", str(duration), "-filter_complex", chain, "-map", label, "-an",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", str(output)])

    console.print(f"  [green]✓[/green] [{index}] {name} → {duration}초"
                  + (f" [dim](x{speed})[/dim]" if speed != 1.0 else ""))
    return output


def mux_audio(video: Path, output: Path, total: float) -> None:
    """보이스 + BGM + 효과음을 한 트랙으로 합친다.

    BGM은 sidechaincompress로 보이스에 물려 더킹한다 — 대사가 나올 때만
    자동으로 눌리므로, 여백에서는 살아 있고 설명 구간에서는 방해하지 않는다.
    """
    voices = [(start, VOICE_DIR / f"{name}.mp3")
              for name, start in VOICE if (VOICE_DIR / f"{name}.mp3").exists()]
    if not voices:
        console.print("[yellow]⚠ 보이스 파일이 없어 무음으로 출력합니다.[/yellow]")
        video.replace(output)
        return

    args = [FFMPEG, "-y", "-v", "error", "-i", str(video)]
    parts, idx = [], 1

    # 1) 보이스 — 각자의 시작 초에 배치해 하나로 합친다
    labels = []
    for start, path in voices:
        args += ["-i", str(path)]
        delay = int(start * 1000)
        parts.append(f"[{idx}:a]adelay={delay}|{delay},aformat=sample_rates=44100:"
                     f"channel_layouts=stereo[v{idx}]")
        labels.append(f"[v{idx}]")
        idx += 1
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0[voice]")

    # 2) 효과음 — 화면 동작에 맞춘 시점에 배치
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

    # 3) BGM — 더킹 후 페이드아웃
    bgm_path = AUDIO_DIR / BGM
    if bgm_path.exists():
        args += ["-i", str(bgm_path)]
        parts.append(
            f"[{idx}:a]volume={BGM_GAIN},afade=t=out:st={total - 2.5}:d=2.5,"
            f"aformat=sample_rates=44100:channel_layouts=stereo[bgmraw]"
        )
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
    console.print("\n[bold blue]━━ episode-001 조립 ━━[/bold blue]\n")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    segments, cursor = [], 0.0
    for i, (name, duration, speed) in enumerate(CUTS):
        segments.append(prepare_cut(i, name, duration, speed, cursor))
        cursor += duration

    concat_list = WORK_DIR / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8"
    )

    silent = WORK_DIR / "silent.mp4"
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(silent)])

    mux_audio(silent, FINAL, cursor)

    size_mb = FINAL.stat().st_size / 1e6
    console.print(
        f"\n[bold green]✓ 완성: {FINAL}[/bold green]  "
        f"[dim]{cursor:.1f}초 / {size_mb:.1f}MB / {W}x{H}[/dim]\n"
    )
    return FINAL


if __name__ == "__main__":
    main()
