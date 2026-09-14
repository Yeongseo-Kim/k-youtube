"""
[생성] gosu-001 — 노고수 표정 시트 (gpt-image-1, images.edit: gosu_front.png을 얼굴 앵커로)

assets/gosu/contest-nikom-2026.md 생성 매핑 0단계 후반.
얼굴·수염·망건·옷은 gosu_front.png 그대로 두고 표정만 바꾼다.
실사라 만화적 데포르메 없이 "배우 연기 수준"의 과장으로.

실행: python3 -m scripts.gen_gosu_expr            # 전체
      python3 -m scripts.gen_gosu_expr expr_killing  # 지정만
"""

import base64
import sys
from pathlib import Path

from openai import OpenAI
from rich.console import Console

import config

console = Console()
MODEL = "gpt-image-1"
OUT = Path("assets/gosu")
ANCHOR = OUT / "gosu_front.png"
SIZE = "1024x1536"

BASE = (
    "Photorealistic cinematic still of EXACTLY the same elderly Korean swordsman as in "
    "the reference image: same face, same long white hair in a topknot with black "
    "manggeon headband, same long white beard, same grey-white hanbok martial robe. "
    "Keep identity perfectly consistent. Chest-up, 85mm lens, shallow depth of field, "
    "natural skin texture, film grain, no text, no watermark. Change ONLY the expression, "
    "pose and setting as described: "
)

IMAGES = {
    "expr_killing": "Fierce killing intent, eyes narrowed and burning, jaw clenched, "
        "gripping a sword hilt raised toward the camera. Misty night cliff, cold blue light. (CUT 1)",
    "expr_hit": "Shock of being struck: eyes wide, mouth open in a gasp, head snapped back, "
        "orange firelight on his face and embers in the air. Night cliff. (CUT 1)",
    "expr_collapse": "Kneeling and slumping forward, eyes half-closed and unfocused, "
        "exhausted, faint red glow leaking from his skin. Night cliff, low angle. (CUT 1)",
    "expr_dazed": "Lying on his back on a white clinic bed just after waking, eyes wide "
        "and confused, looking up. Bright white clinic room, neutral daylight. (CUT 2)",
    "expr_caught": "Startled guilty look, eyebrows raised, eyes darting sideways, lips "
        "pressed — the look of someone whose secret was just read. Bright white clinic. (CUT 2)",
    "expr_flinch": "Lying face down on a clinic bed, head turned to camera, sharp wince "
        "with one eye shut and teeth bared at the prick of a hair-thin stainless acupuncture "
        "needle (NOT a syringe, no injection) placed on his shoulder by a gloved hand. Bright white clinic. (CUT 3)",
    "expr_alarm": "Lying face down on a clinic bed, head whipped toward camera in alarm, "
        "eyes wide, mouth open mid-shout. Bright white clinic. (CUT 4)",
    "expr_relief": "Lying face down on a clinic bed, cheek on the pillow, eyes closed, "
        "deeply relaxed melting smile of relief. Bright white clinic. (CUT 4)",
    "expr_bliss": "Eyes closed, face tilted slightly up, blissful serene smile as if "
        "feeling energy flow, soft golden rim light. Bright white clinic. (CUT 3/5)",
    "expr_fresh": "Standing tall and refreshed, back straight, bright clear eyes, beard "
        "and hair neatly groomed, warm confident smile, soft flattering beauty light. "
        "Bright white clinic reception. (CUT 6/7)",
}


def generate(prompt: str) -> bytes:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    r = client.images.edit(
        model=MODEL, image=[open(ANCHOR, "rb")], prompt=BASE + prompt,
        size=SIZE, quality="medium",
    )
    return base64.b64decode(r.data[0].b64_json)


def main():
    names = sys.argv[1:] or list(IMAGES)
    bad = [n for n in names if n not in IMAGES]
    if bad:
        console.print(f"[red]알 수 없는 이름: {bad}[/red]"); raise SystemExit(1)
    failed = []
    for n in names:
        console.print(f"[bold]{n}[/bold] 생성 중…")
        try:
            (OUT / f"{n}.png").write_bytes(generate(IMAGES[n]))
            console.print(f"  [green]✓ {n}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:200]}[/red]"); failed.append(n)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_expr {' '.join(failed)}[/yellow]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
