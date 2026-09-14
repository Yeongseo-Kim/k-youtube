"""
[생성] gosu-001 — 컷 영상 (ModelArk Seedance, 1080p 9:16)

방식(md 제작 방식 참조): CUT 1 액션은 미리 뽑은 스틸을 레퍼런스로,
한의원 컷은 인물 표정 + 공간 + 소품 레퍼런스를 바로 넣어 영상 직행.
공모 규격이 FHD 이상이라 **1080p 고정** (채널 720p 파이프라인 아님).

실행: python3 -m scripts.gen_gosu_video          # 전체
      python3 -m scripts.gen_gosu_video v1_fire  # 지정만
"""

import sys
from pathlib import Path

from rich.console import Console

from src.providers import modelark_video as ark

console = Console()
MODEL = "dreamina-seedance-2-0-mini-260615"
OUT = Path("output/gosu/cuts")
REF = Path("assets/gosu")

PHOTO = (
    "Photorealistic cinematic live-action film, 9:16 vertical. Keep the person EXACTLY "
    "identical to the reference image (same face, hair, beard, headband, costume) and keep "
    "the room and equipment exactly as in the references. Natural skin texture, film grain, "
    "shallow depth of field. No text, no letters, no subtitles, no watermark. "
)

# (이름, 초, 첫프레임/레퍼런스 파일들, 프롬프트)
# CUT 1 액션은 뽑아둔 스틸을 first_frame으로 — 구도가 그대로 유지된다
CUTS = {
    # ── CUT 1
    "v1_fire": (4, ["cuts/c1_villain.png"],
        PHOTO +
        "The flames burning above her palms swell rapidly into a huge roaring fireball, "
        "then she thrusts both palms forward and the fireball LAUNCHES straight at the "
        "camera, filling the frame with fire and embers at the end. Her hair and sleeves "
        "blow back from the blast. Camera holds steady, she stays centered. One "
        "continuous shot, dramatic night cliff lighting."),
}


def main():
    names = sys.argv[1:] or list(CUTS)
    bad = [n for n in names if n not in CUTS]
    if bad:
        console.print(f"[red]알 수 없는 이름: {bad} — 가능: {list(CUTS)}[/red]")
        raise SystemExit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in names:
        dur, refs, prompt = CUTS[n]
        console.print(f"[bold]{n}[/bold] ({dur}초, ref: {refs})")
        try:
            first = REF / refs[0] if n.startswith("v1_") else None
            rest = [REF / f for f in (refs[1:] if first else refs)] or None
            ark.generate(
                prompt=prompt, output_path=OUT / f"{n}.mp4",
                first_frame=first, reference_images=rest,
                model=MODEL, resolution="1080p", ratio="9:16", duration=dur,
                task_type="i2v" if first else "reference",
            )
            console.print(f"  [green]✓ {n}.mp4[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:300]}[/red]")
            failed.append(n)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_video {' '.join(failed)}[/yellow]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
