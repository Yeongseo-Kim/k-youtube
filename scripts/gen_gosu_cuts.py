"""
[생성] gosu-001 — 컷별 스틸 (gpt-image-1 images.edit, 레퍼런스 다중 입력)

assets/gosu/contest-nikom-2026.md의 컷 구성 그대로.
얼굴 일관성은 인물 레퍼런스(gosu_front / expr_* / enemy_fire)가 잡고,
공간·소품은 clinic_* / prop_* 이 잡는다. 프롬프트는 "무엇을 하는가"만.

실행: python3 -m scripts.gen_gosu_cuts            # 전체
      python3 -m scripts.gen_gosu_cuts c1_slash   # 지정만 (재시도용)
      python3 -m scripts.gen_gosu_cuts cut1       # 접두어로 컷 단위
"""

import base64
import sys
from pathlib import Path

from openai import OpenAI
from rich.console import Console

import config

console = Console()
MODEL = "gpt-image-1"
OUT = Path("assets/gosu/cuts")
REF = Path("assets/gosu")
SIZE = "1024x1536"

BASE = (
    "Photorealistic cinematic film still, 9:16 vertical. Keep the people EXACTLY "
    "identical to the reference images (same faces, hair, beard, headband, costume) and "
    "keep the room/equipment exactly as in the reference. 85mm lens, shallow depth of "
    "field, natural skin texture, film grain. No text, no letters, no subtitles, no "
    "watermark anywhere in the frame. Scene: "
)

# (파일명, [레퍼런스들], 프롬프트)
CUTS = [
    # ── CUT 1 — 훅 · 화염장 → 포탈 (0:00~0:05)
    ("c1_slash", ["expr_killing.png"],
     "EXTREME CLOSE-UP of the old master's face filling the frame, eyes blazing with "
     "killing intent, as he thrusts his sword blade straight TOWARD THE CAMERA — the "
     "blade tip rushing at the lens, motion blur on the blade. Misty night cliff top, "
     "cold blue moonlight. Dynamic, aggressive, attacking the viewer."),
    ("c1_villain", ["enemy_fire.png"],
     "The strikingly beautiful villainess standing tall on a night cliff, seen from the "
     "chest up so her face is large and clearly visible, lit beautifully by the fire: "
     "flawless skin, red lips, elegant sharp features, a cold confident smirk, silver "
     "hairpin, glossy black hair and wide silk sleeves streaming in the wind. Her palms "
     "are raised at the lower edge of the frame with fire blooming from them, embers "
     "rising past her face. Glamorous beauty lighting, orange flame glow against deep "
     "blue night. She looks powerful and gorgeous, NOT goofy."),
    ("c1_hit", ["expr_hit.png"],
     "The old master struck square in the chest by a ball of fire — his body snapping "
     "backward, robe and hair blown back, orange fireball bursting against his chest, "
     "embers and sparks flying. Night cliff. Full impact moment, dramatic."),
    ("c1_juhwa", ["expr_collapse.png"],
     "The old master on one knee on the night cliff, doubled over, both hands clenched, "
     "a faint red glow radiating from his chest through the robe and thin wisps of red "
     "smoke-like energy rising off his shoulders and back — subtle, atmospheric, NOT "
     "glowing veins or lightning bolts on the skin. Gritting his teeth, one hand pressed "
     "to his chest, enduring. No blood, no wounds. Dark blue misty night."),
    ("c1_fall", ["expr_collapse.png"],
     "The old master collapsed face-down on the rocky cliff ground, eyes half-open and "
     "unfocused, one arm outstretched, his sword fallen beside him. Shot from a low "
     "angle at ground level. Faint red glow fading from his body. Night, mist."),
    ("c1_portal", ["gosu_front.png"],
     "TOP-DOWN overhead shot of the old master lying face-down on rocky ground, and "
     "directly UNDERNEATH his body a glowing swirling circular portal has opened in the "
     "ground — a vortex of blue-white light with spiral energy, its glow lighting his "
     "face and robe from below as he begins to sink into it. Night cliff, dramatic."),
]

CUTS_BY_NAME = {name: (refs, prompt) for name, refs, prompt in CUTS}


def generate(refs, prompt: str) -> bytes:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    r = client.images.edit(
        model=MODEL,
        image=[open(REF / f, "rb") for f in refs],
        prompt=BASE + prompt,
        size=SIZE,
        quality="medium",
    )
    return base64.b64decode(r.data[0].b64_json)


def main():
    args = sys.argv[1:]
    if args:
        names = [n for n in CUTS_BY_NAME if any(n == a or n.startswith(a) for a in args)]
        if not names:
            console.print(f"[red]매칭 없음: {args} — 가능: {list(CUTS_BY_NAME)}[/red]")
            raise SystemExit(1)
    else:
        names = list(CUTS_BY_NAME)

    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in names:
        refs, prompt = CUTS_BY_NAME[n]
        console.print(f"[bold]{n}[/bold] 생성 중… (ref: {refs})")
        try:
            (OUT / f"{n}.png").write_bytes(generate(refs, prompt))
            console.print(f"  [green]✓ {n}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:200]}[/red]")
            failed.append(n)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_cuts {' '.join(failed)}[/yellow]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
