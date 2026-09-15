"""
[생성] gosu-001 훅 전투 — Seedance 공식 프롬프트 구조 적용 (2.0-mini, 720p, 오디오 포함)

공식 가이드(assets/gosu/prompt-guide.md 9절) 반영 사항
- 인물은 프롬프트 본문에서 **Image 1 / Image 2**로 지칭한다. `asset://`는 API 필드에만.
- 샷 내부 순서: 카메라 무빙 → 동작·표정 → 위치 변화 → 오디오
- **한 샷에 카메라 무빙 1종만**
- 화질·룩 블록과 제약 블록은 **전 컷에서 글자 그대로 재사용**한다 (연속성)
- 9:16은 자막 오출력 확률이 높아 제약문을 고정으로 붙인다

격한 동작은 유지한다(훅이라 필요). 공식은 고폭발 동작을 피하라고 하지만, 대신
**샷마다 결정적 동작 하나만** 신체 부위·속도·힘으로 쓰고 나머지는 총괄 서술로 둔다.
실패하면 같은 프롬프트로 재시도한다 (컷당 약 $0.12).

실행: python3 -m scripts.gen_gosu_hook           # 전체
      python3 -m scripts.gen_gosu_hook h2_clash  # 지정만 (재시도용)
"""

import json
import sys
from pathlib import Path

from rich.console import Console

from src.providers import modelark_video as ark

console = Console()
MODEL = "dreamina-seedance-2-0-mini-260615"
OUT = Path("output/gosu/cuts")
IDS = json.loads(Path("assets/gosu/asset_ids.json").read_text())

# 전 컷 공통 — 글자 그대로 재사용해야 룩이 통일된다
LOOK = (" Cold moonlight with a faint warm rim light. Live-action historical film, shot on a "
        "35mm cinema lens, shallow depth of field, fine film grain, authentic skin texture, "
        "no beautification or skin smoothing. HD, rich details, cinematic texture.")
LIMITS = (" No subtitles. Do not generate a logo. Do not generate a watermark. "
          "Only one of each character is in frame; do not generate duplicate characters.")

MASTER = [f"asset://{IDS['r2_face_b']}", f"asset://{IDS['r2_full_b']}"]
VILLAIN = [f"asset://{IDS['c1_villain']}"]

# 이름: (참조, 프롬프트) — 4초 고정
SHOTS = {
    "h1_face": (MASTER,
        "Image 1 is a facial reference of the old swordsman; Image 2 is his full-body "
        "reference. The camera slowly orbits around him, then settles. The old swordsman "
        "from Image 1 hovers in mid-air on the left above a misty cliff at night, his robe "
        "and long white hair snapping in the wind, and he lifts his eyes to his opponent."
        + LOOK + " Sound: howling wind." + LIMITS),

    "h2_clash": (MASTER + VILLAIN,
        "Image 1 is a facial reference of the old swordsman; Image 2 is his full-body "
        "reference; Image 3 is the woman in black and crimson. The camera arcs around them "
        "quickly. In mid-air above the night cliff, the old swordsman on the left drives his "
        "palm forward into the woman's guard on the right, a white shockwave ring bursting "
        "at the point of contact and blowing dust outward."
        + LOOK + " Sound: a sharp cracking impact." + LIMITS),

    "h3_fire": (VILLAIN,
        "Image 1 is the woman in black and crimson. The camera pulls back fast, then holds. "
        "The woman from Image 1 hangs in mid-air facing the lens, sweeps both palms together "
        "and thrusts them forward, and a huge fireball erupts toward the camera and fills "
        "the frame with fire and embers."
        + LOOK + " Sound: a rushing whoosh and a fire blast." + LIMITS),

    "h4_hit": (MASTER,
        "Image 1 is a facial reference of the old swordsman; Image 2 is his full-body "
        "reference. The camera whip pans to the right to follow him. The old swordsman from "
        "Image 1 is struck square in the chest in mid-air and is thrown backward across the "
        "night sky, spinning, his robe billowing and embers trailing behind him."
        + LOOK + " Sound: an explosion and rushing wind." + LIMITS),

    "h5_crash": (MASTER,
        "Image 1 is a facial reference of the old swordsman; Image 2 is his full-body "
        "reference. The camera stays locked low at ground level. The old swordsman from "
        "Image 1 slams down onto the rocky cliff, cracking the stone, and a ring of dust "
        "blasts outward toward the lens before he lies still."
        + LOOK + " Sound: a heavy ground impact and falling rubble." + LIMITS),

    "h6_portal": (MASTER,
        "Image 1 is a facial reference of the old swordsman; Image 2 is his full-body "
        "reference. The camera looks straight down and slowly rises. A spinning blue-white "
        "portal tears open in the ground directly beneath the fallen swordsman from Image 1, "
        "its light beaming upward, and it pulls him down through it until he vanishes."
        + LOOK + " Sound: a deep rising vortex whoosh that snaps shut." + LIMITS),
}


def main() -> None:
    names = sys.argv[1:] or list(SHOTS)
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in names:
        refs, prompt = SHOTS[n]
        path = OUT / f"{n}.mp4"
        if path.exists() and not sys.argv[1:]:
            console.print(f"[dim]{n} 건너뜀[/dim]")
            continue
        console.print(f"[bold]{n}[/bold] ({len(prompt.split())}단어, 참조 {len(refs)}개)")
        try:
            ark.generate(prompt=prompt, output_path=path, reference_images=refs,
                         model=MODEL, resolution="720p", ratio="9:16", duration=4,
                         generate_audio=True)
            console.print(f"  [green]✓ {path}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:160]}[/red]")
            failed.append(n)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_hook {' '.join(failed)}[/yellow]")


if __name__ == "__main__":
    main()
