"""
[조립] gosu-001 CUT 1 — 훅 전투 시퀀스 (빠르게, 겹치지 않게)

원칙
- 준비 샷 없음. 공중 대치 → 난타 → 화염 → 격추 → 포탈로 바로 간다.
- **같은 클립을 두 번 쓰지 않는다** (반복이 느껴지는 원인).
- 샷당 0.3~0.9초. 생성물이 느리면 **배속(speed)**을 걸어 체감 속도를 올린다.
- 좌=노고수, 우=악녀로 위치를 고정한 샷을 써서 컷이 이어지게 한다.

실행: python3 -m src.assemble_gosu_c1
"""

import subprocess
from pathlib import Path

from rich.console import Console

console = Console()
CUTS = Path("output/gosu/cuts")
OUT = CUTS / "cut1_fast.mp4"

# (파일, 시작초, 길이초, 배속) — 길이는 배속 적용 후 최종 길이
SEQ = [
    ("d_face",        1.0, 0.7, 1.6),  # 공중 대치, 카메라 빠르게 빠짐
    ("d_clash",       0.5, 0.9, 1.8),  # 난타
    ("b_eyes",        1.0, 0.3, 1.5),  # 눈 한 프레임
    ("d_fire",        0.8, 0.9, 1.5),  # 악녀 멀어지며 발사
    ("d_hit",         0.6, 0.7, 1.6),  # 직격 후 날아감
    ("c_crash",       0.9, 0.6, 1.5),  # 지면 격추
    ("c1_juhwa",      1.2, 0.5, 1.4),  # 주화입마 한 박
    ("c_portal_suck", 0.6, 1.4, 1.2),  # 포탈 흡입 (마지막만 여유)
]


def main() -> None:
    tmp = CUTS / "_c1parts"
    tmp.mkdir(exist_ok=True)
    for old in tmp.glob("*.mp4"):
        old.unlink()

    parts = []
    for i, (name, ss, dur, speed) in enumerate(SEQ):
        src = CUTS / f"{name}.mp4"
        if not src.exists():
            console.print(f"[yellow]없음, 건너뜀: {name}[/yellow]")
            continue
        dst = tmp / f"{i:02d}_{name}.mp4"
        src_dur = dur * speed  # 배속 전 원본에서 잘라낼 길이
        vf = (f"setpts=PTS/{speed},"
              "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30")
        af = f"atempo={min(speed, 2.0)}"
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-t", f"{src_dur:.3f}",
            "-i", str(src), "-vf", vf, "-af", af,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", str(dst),
        ], check=True)
        parts.append(dst)

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", str(OUT),
    ], check=True)
    total = sum(d for _, _, d, _ in SEQ)
    console.print(f"[green]✓ {OUT} (샷 {len(parts)}개, 약 {total:.1f}초)[/green]")


if __name__ == "__main__":
    main()
