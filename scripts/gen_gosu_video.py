"""
[생성] gosu-001 — 컷 영상 (Seedance 2.0-mini, 720p 9:16)

실사 얼굴은 직접 못 넣는다. `scripts/gosu_assets_register.py`로 등록해 둔
자산을 `asset://<자산ID>`로 참조한다 (자산 ID는 assets/gosu/asset_ids.json).
2.0-mini는 720p까지 지원 — 공모 규격(1080×1920)은 조립 단계에서 업스케일한다.
오디오는 `generate_audio=True`로 **영상과 함께 생성**한다 (실측: 토큰 소비가 무음과 동일해
추가 비용 없음, 32kHz 스테레오 AAC). 효과음·환경음은 프롬프트 끝에 "Sound: ..." 로 지시하고,
한국어 대사만 ElevenLabs로 따로 만들어 조립에서 올린다.

실행: python3 -m scripts.gen_gosu_video           # 미생성분 전체
      python3 -m scripts.gen_gosu_video c1_slash  # 지정만 (재시도용)
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

STYLE = (
    "Photorealistic live-action cinematic film, vertical 9:16. The person must look "
    "exactly like the reference asset. Natural skin texture, film grain, shallow depth "
    "of field. No text, no letters, no subtitles, no watermark. "
)

# 이름: (초, 참조 자산 키들, 프롬프트)
CUTS = {
    "c1_slash": (4, ["c1_slash"], STYLE +
        "Extreme close-up of the old master's face, eyes blazing. He thrusts his sword "
        "straight toward the camera — the blade rushes at the lens with motion blur and "
        "the frame shakes on impact. Misty night cliff, cold blue moonlight. "
        "Sound: a sharp sword slash whoosh and wind on the cliff. No music, no speech."),
    "c1_villain": (4, ["c1_villain"], STYLE +
        "The flames above her palms swell into a huge roaring fireball, then she thrusts "
        "both palms forward and the fireball launches straight at the camera, filling the "
        "frame with fire and embers. Her hair and sleeves blow back. Camera holds steady. "
        "Sound: fire roaring and bursting forward, crackling embers. No music, no speech."),
    "c1_hit": (4, ["c1_hit"], STYLE +
        "The fireball slams into the old master's chest. His body snaps backward, robe and "
        "white hair blown back, sparks and embers scattering, firelight flashing across his "
        "shocked face. Slight slow motion on the impact. Night cliff. "
        "Sound: a heavy fiery impact thud with crackling sparks. No music, no speech."),
    "c1_juhwa": (4, ["c1_juhwa"], STYLE +
        "Kneeling on the night cliff, the old master grits his teeth as a faint red glow "
        "pulses out of his chest and thin red wisps of energy rise off his shoulders. His "
        "hand trembles. Slow push in. No blood. "
        "Sound: strained breathing and a low ominous energy hum. No music, no speech."),
    "c1_fall": (4, ["c1_fall"], STYLE +
        "The old master collapses forward onto the rocky ground and lies still, eyes losing "
        "focus, one arm outstretched. Dust drifts. The red glow fades out. Low ground-level "
        "angle, night mist. "
        "Sound: a body dropping onto gravel, faint wind. No music, no speech."),
    "c1_portal": (4, ["c1_portal"], STYLE +
        "Top-down view: a swirling blue-white portal opens in the ground directly beneath "
        "the fallen master, its light growing and spinning faster, then he sinks through and "
        "disappears as the portal closes. Night cliff. "
        "Sound: a deep swirling vortex hum rising then snapping shut. No music, no speech."),
}


def main() -> None:
    names = sys.argv[1:] or list(CUTS)
    bad = [n for n in names if n not in CUTS]
    if bad:
        console.print(f"[red]알 수 없는 이름: {bad} — 가능: {list(CUTS)}[/red]")
        raise SystemExit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in names:
        dur, refs, prompt = CUTS[n]
        path = OUT / f"{n}.mp4"
        if path.exists() and n not in sys.argv[1:]:
            console.print(f"[dim]{n} 건너뜀 (이미 있음)[/dim]")
            continue
        uris = [f"asset://{IDS[k]}" for k in refs]
        console.print(f"[bold]{n}[/bold] ({dur}초, ref: {refs})")
        try:
            ark.generate(prompt=prompt, output_path=path, reference_images=uris,
                         model=MODEL, resolution="720p", ratio="9:16", duration=dur,
                         generate_audio=True)
            console.print(f"  [green]✓ {path}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:200]}[/red]")
            failed.append(n)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_video {' '.join(failed)}[/yellow]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
