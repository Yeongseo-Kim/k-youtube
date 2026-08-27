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

# 컷 구성: (파일, 사용 길이)
CUTS = [
    ("cut1.mp4", 3.8),
    ("cut2.mp4", 6.0),
    ("C3_spray_tissue.mp4", 6.0),
    ("edu1_why.mp4", 6.0),
    ("edu2_bleach.mp4", 6.0),
    ("edu3_pinch.mp4", 8.0),
    ("C4_peel_result.mp4", 5.5),
    ("B2_chestup_rise.mp4", 5.5),
]

# 보이스: (파일명, 시작초). 의미 단위로 묶어 생성했다 —
# 문장을 쪼개면 낭독조가 되어 리듬이 끊긴다.
VOICE = [
    ("G1", 0.4),
    ("G2", 4.3),
    ("G3", 10.3),
    ("G4", 16.2),
    ("G5", 22.8),
    ("G6", 29.2),
    ("G7", 37.2),
    ("G8", 42.0),
]

# 자막: (텍스트, 시작초, 끝초) — 영상 전체 기준 절대 시각. 대사와 동일한 문장.
SUBTITLES = [
    ("변기에 묻은 이거 안 생기게 하는 법 알려줄게", 0.4, 3.3),
    ("이건 물때가 아니라 요석이라고 하는 거야", 4.3, 7.0),
    ("요석은 알칼리성이라 산으로 녹일 수 있어", 7.0, 9.6),
    ("구연산 뿌리고 휴지로 덮어놔", 10.3, 12.5),
    ("소변 속 요소가 세균을 만나면 암모니아가 나오고", 16.2, 19.3),
    ("물이 알칼리로 변하면서 미네랄이 굳어", 19.3, 22.4),
    ("락스는 알칼리라서 알칼리인 요석을 못 녹여", 22.8, 25.8),
    ("색깔만 하얘지고 더러운 게 남아있는 거야", 25.8, 28.8),
    ("구연산이 굳은 미네랄을 집게처럼 붙잡아 녹여", 29.2, 32.5),
    ("이걸 킬레이션이라고 해", 32.5, 34.4),
    ("아예 녹여내니까 락스보다 훨씬 오래가", 34.4, 36.8),
    ("기다렸다 벗기면 말끔히 지워져", 37.2, 39.6),
    ("다 됐다. 깨끗하지?", 42.0, 43.5),
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
    "edu3_pinch.mp4": [
        ("chelate ← chele\n그리스어로 '게 집게'", "40", 225, 34, "white@0.92"),
    ],
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


def prepare_cut(index: int, name: str, duration: float, cut_start: float) -> Path:
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

    vf = f"scale={W}:{H},fps=30"
    if overlay:
        vf = f"{vf},{overlay}"

    run([FFMPEG, "-y", "-v", "error", "-i", str(source), "-t", str(duration),
         "-vf", vf, "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", str(output)])

    console.print(f"  [green]✓[/green] [{index}] {name} → {duration}초")
    return output


def mux_voice(video: Path, output: Path) -> None:
    """보이스를 각자의 시작 초에 얹어 하나의 오디오 트랙으로 합친다.

    보이스가 컷 경계를 넘어가도 된다 — 오히려 사운드 브릿지가 되어 전환을 이어준다.
    """
    lines = [(start, VOICE_DIR / f"{name}.mp3")
             for name, start in VOICE if (VOICE_DIR / f"{name}.mp3").exists()]
    if not lines:
        console.print("[yellow]⚠ 보이스 파일이 없어 무음으로 출력합니다.[/yellow]")
        video.replace(output)
        return

    args = [FFMPEG, "-y", "-v", "error", "-i", str(video)]
    for _, path in lines:
        args += ["-i", str(path)]

    # amix는 입력 수만큼 볼륨을 낮추므로 normalize=0으로 원음을 유지한다.
    delays = "".join(
        f"[{i + 1}:a]adelay={int(start * 1000)}|{int(start * 1000)}[a{i}];"
        for i, (start, _) in enumerate(lines)
    )
    mix_in = "".join(f"[a{i}]" for i in range(len(lines)))
    filters = f"{delays}{mix_in}amix=inputs={len(lines)}:normalize=0[out]"

    run(args + ["-filter_complex", filters, "-map", "0:v", "-map", "[out]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(output)])
    console.print(f"  [green]✓[/green] 보이스 {len(lines)}개 합성")


def main() -> Path:
    console.print("\n[bold blue]━━ episode-001 조립 ━━[/bold blue]\n")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    segments, cursor = [], 0.0
    for i, (name, duration) in enumerate(CUTS):
        segments.append(prepare_cut(i, name, duration, cursor))
        cursor += duration

    concat_list = WORK_DIR / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8"
    )

    silent = WORK_DIR / "silent.mp4"
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(silent)])

    mux_voice(silent, FINAL)

    size_mb = FINAL.stat().st_size / 1e6
    console.print(
        f"\n[bold green]✓ 완성: {FINAL}[/bold green]  "
        f"[dim]{cursor:.1f}초 / {size_mb:.1f}MB / {W}x{H}[/dim]\n"
    )
    return FINAL


if __name__ == "__main__":
    main()
