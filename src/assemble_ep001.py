"""
[조립] episode-001 — 생성된 컷들을 트림·자막·전환으로 이어 붙여 완성본을 만든다.

보이스/BGM은 별도로 입히므로 여기서는 무음 영상 + 자막까지만 처리한다.
moviepy 대신 ffmpeg을 직접 호출한다(빌드 실패 회피 + 트림 정밀도).

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
FINAL = SRC_DIR / "episode-001.mp4"

W, H = 720, 1280
# 쇼츠 세이프존: 상단 15%(192px), 하단 20%(256px)는 UI가 가린다
Y_TOPIC = 235      # 주제 자막 (상단 세이프존 아래)
Y_SUB = 950        # 보조 자막 (하단 세이프존 위)
Y_WARN = 330       # 안전 경고

# 컷 구성: (파일, 사용 길이, 자막 목록)
# 자막: (텍스트, 시작초, 지속초, 크기, y좌표, 글자색, 박스색)
# 자막 톤: 세린의 혼잣말(반말·짧게·종결 내림)이 대사 자리에 오고,
# 정보/훅은 상단에 크게 얹는다. 정보 전달과 캐릭터를 자막 하나로 겸한다.
CUTS = [
    ("cut1.mp4", 3.8, [
        ("…또 누레졌네", 0.3, 1.5, 34, Y_SUB, "white", "black@0.5"),
        ("닦아도 다시 생기는 이유", 1.9, 1.9, 48, Y_TOPIC, "white", "black@0.55"),
    ]),
    ("cut2.mp4", 5.0, [
        ("이거 물때 아니야. 요석이야.", 0.3, 2.2, 42, Y_TOPIC, "white", "black@0.55"),
        ("락스는 소용없어", 2.7, 2.1, 34, Y_SUB, "white", "black@0.5"),
    ]),
    ("C3_spray_tissue.mp4", 7.8, [
        ("알칼리라서 산으로 녹여야 돼", 0.4, 2.6, 42, Y_TOPIC, "white", "black@0.55"),
        ("구연산 15g + 물 500mL", 0.7, 2.6, 32, Y_SUB, "white", "black@0.5"),
        # 산성 세제를 쓰는 영상이라 안전 조건은 같은 주제 안에 반드시 들어가야 한다.
        # 스치듯 지나가면 안 읽히므로 1.8초 노출.
        ("락스랑 같이 쓰면 염소가스", 3.5, 1.8, 34, Y_WARN, "white", "red@0.78"),
        ("세로면은 흘러내리니까 휴지로 붙잡아", 5.6, 2.0, 38, Y_TOPIC, "white", "black@0.55"),
    ]),
    ("__timecard__", 1.0, [
        ("20분 뒤", 0.0, 1.0, 56, 600, "white", "black@0.6"),
    ]),
    ("C4_peel_result.mp4", 5.5, [
        ("힘 안 줘도 벗겨져", 0.6, 3.4, 46, Y_TOPIC, "white", "black@0.55"),
    ]),
    ("B2_chestup_rise.mp4", 5.5, [
        ("…깨끗하지?", 2.4, 2.1, 34, Y_SUB, "white", "black@0.5"),
    ]),
]


def run(args: list[str]) -> None:
    """ffmpeg 호출. 실패 시 stderr를 그대로 노출한다."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]✗ ffmpeg 실패[/red]\n{result.stderr[-1500:]}")
        raise RuntimeError("ffmpeg 실패")


def escape(text: str) -> str:
    """drawtext 필터용 이스케이프."""
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def build_drawtext(subs: list[tuple]) -> str:
    """자막 목록을 drawtext 필터 체인으로 변환."""
    parts = []
    for text, start, dur, size, y, color, box in subs:
        parts.append(
            f"drawtext=fontfile={FONT_BOLD}:text='{escape(text)}':"
            f"fontsize={size}:fontcolor={color}:x=(w-text_w)/2:y={y}:"
            f"box=1:boxcolor={box}:boxborderw=18:"
            f"enable='between(t,{start},{start + dur})'"
        )
    return ",".join(parts)


def make_timecard(source: Path, output: Path, duration: float) -> None:
    """직전 컷의 마지막 프레임을 정지시켜 시간 경과 카드를 만든다.

    결과가 즉효처럼 보이면 조작 의심을 사므로, 시간이 걸린다는 것을 명시한다.
    """
    still = WORK_DIR / "timecard_still.png"
    run([FFMPEG, "-y", "-v", "error", "-sseof", "-0.5", "-i", str(source),
         "-vsync", "0", "-frames:v", "1", "-update", "1", str(still)])
    run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-t", str(duration), "-i", str(still),
         "-vf", f"scale={W}:{H},eq=brightness=-0.06", "-r", "30",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)])


def prepare_cut(index: int, name: str, duration: float, subs: list[tuple]) -> Path:
    """컷 하나를 트림 + 자막 처리해 중간 파일로 저장한다.

    끝부분 트림이 중요하다 — AI 생성 영상은 마지막 몇 프레임에서 동작이
    뭉개지는 경우가 잦아, 잘라내야 이어 붙였을 때 깔끔하다.
    """
    output = WORK_DIR / f"{index:02d}_{Path(name).stem}.mp4"

    if name == "__timecard__":
        raw = WORK_DIR / f"{index:02d}_timecard_raw.mp4"
        make_timecard(WORK_DIR / "02_C3_spray_tissue.mp4", raw, duration)
        source = raw
    else:
        source = SRC_DIR / name

    vf = f"scale={W}:{H},fps=30"
    drawtext = build_drawtext(subs)
    if drawtext:
        vf = f"{vf},{drawtext}"

    run([FFMPEG, "-y", "-v", "error", "-i", str(source), "-t", str(duration),
         "-vf", vf, "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", str(output)])

    console.print(f"  [green]✓[/green] [{index}] {name} → {duration}초")
    return output


def mux_voice(video: Path, output: Path) -> None:
    """컷별 보이스 파일을 각자의 시작 초에 얹어 하나의 오디오 트랙으로 합친다.

    보이스는 컷 경계를 넘어가도 된다 — 오히려 사운드 브릿지가 되어
    컷 전환을 이어준다. BGM/효과음은 이후 단계에서 추가한다.
    """
    from pathlib import Path as _P
    VOICE_DIR = _P("output/ep001/voice_chaerin")
    # 의미 단위로 묶어 생성한다 — 문장을 쪼개면 낭독조가 되어 리듬이 끊긴다
    LINES = [("G1", 0.5, ""), ("G2", 4.2, ""), ("G3", 10.8, ""),
             ("G4", 18.7, ""), ("G5", 25.8, "")]

    lines = [(start, VOICE_DIR / f"{name}.mp3")
             for name, start, _ in LINES if (VOICE_DIR / f"{name}.mp3").exists()]
    if not lines:
        console.print("[yellow]⚠ 보이스 파일이 없어 무음으로 출력합니다.[/yellow]")
        video.replace(output)
        return

    args = [FFMPEG, "-y", "-v", "error", "-i", str(video)]
    for _, path in lines:
        args += ["-i", str(path)]

    # 각 대사를 시작 초만큼 지연시킨 뒤 하나로 섞는다.
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
    console.print(f"  [green]✓[/green] 보이스 {len(lines)}줄 합성")


def main() -> Path:
    console.print("\n[bold blue]━━ episode-001 조립 ━━[/bold blue]\n")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    segments = []
    for i, (name, duration, subs) in enumerate(CUTS):
        segments.append(prepare_cut(i, name, duration, subs))

    concat_list = WORK_DIR / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8"
    )

    silent = WORK_DIR / "silent.mp4"
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(silent)])

    mux_voice(silent, FINAL)

    total = sum(d for _, d, _ in CUTS)
    size_mb = FINAL.stat().st_size / 1e6
    console.print(
        f"\n[bold green]✓ 완성: {FINAL}[/bold green]  "
        f"[dim]{total:.1f}초 / {size_mb:.1f}MB / {W}x{H}[/dim]\n"
    )
    return FINAL


if __name__ == "__main__":
    main()
