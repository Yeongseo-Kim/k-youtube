"""
[생성] gosu-001 — 노고수 실사 레퍼런스 v2 (사진처럼)

v1(gpt-image-1 기본 프롬프트)은 피부가 매끈하고 옷이 새 옷이라 CG처럼 보였다.
이 자산이 모든 컷의 기준이 되므로 여기서 실사감을 잡아야 한다.

핵심 지시
- "일러스트/3D 렌더가 아니라 실사 영화의 한 프레임"
- 피부: 모공·검버섯·잔주름·실핏줄·건조한 입술, 보정 금지
- 수염·머리: 고르지 않게, 잔털과 삐친 머리
- 의상: 손으로 짠 거친 삼베, 빛바램·먼지·해진 단, 눌린 주름
- 조명: 흐린 날 자연광, 부드러운 그림자. 스타일 단어(아나모픽/시네마틱 그레이딩) 배제

실행: python3 -m scripts.gen_gosu_real_refs            # 후보 3장
      python3 -m scripts.gen_gosu_real_refs r2_face_a  # 지정만
"""

import base64
import sys
from pathlib import Path

from openai import OpenAI
from rich.console import Console

import config

console = Console()
MODEL = "gpt-image-1"
OUT = Path("assets/gosu/real")
SIZE = "1024x1536"

PHOTO = (
    "A real photograph — a single frame from a live-action historical film. NOT an "
    "illustration, NOT a 3D render, NOT digital art, NOT CGI. Shot on 35mm motion picture "
    "film with an 85mm lens, visible film grain, natural depth of field. "
    "SKIN: realistic elderly skin with visible pores, fine wrinkles, age spots, tiny "
    "broken capillaries on the cheeks and nose, dry lips, uneven tone. Absolutely no "
    "smoothing or retouching. "
    "HAIR AND BEARD: coarse, uneven, with stray hairs escaping and slightly messy texture. "
    "WARDROBE: a real film-production costume — coarse hand-woven hemp hanbok in faded "
    "off-white, dust and dirt worked into the fabric, frayed hem, deep set creases, "
    "visible weave. Not clean, not new. "
    "LIGHTING: soft overcast daylight, natural falloff, no studio beauty light. "
    "No text, no watermark. "
)

SUBJECT = (
    "A Korean man in his early 70s, a veteran swordsman: long white hair pulled into a "
    "Korean sangtu topknot with a thin black manggeon headband, long uneven white beard, "
    "weathered deeply lined face, calm hard eyes. "
)

IMAGES = {
    "r2_face_a": PHOTO + SUBJECT + (
        "FACIAL CLOSE-UP from just above the shoulders, facing the camera, completely "
        "neutral expression, mouth closed. The face fills about two thirds of the vertical "
        "frame. Plain weathered grey stone wall behind him, thrown out of focus."
    ),
    "r2_face_b": PHOTO + SUBJECT + (
        "FACIAL CLOSE-UP from just above the shoulders, facing the camera, neutral "
        "expression. Outdoors on a misty mountain at dawn, cold damp air, background "
        "heavily out of focus. The face fills about two thirds of the vertical frame."
    ),
    "r2_face_c": PHOTO + SUBJECT + (
        "FACIAL CLOSE-UP from just above the shoulders, three-quarter angle turning to "
        "face the camera, neutral expression, a few strands of hair across his forehead. "
        "Plain dark grey background. The face fills about two thirds of the frame."
    ),
}


def generate(prompt: str) -> bytes:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    r = client.images.generate(model=MODEL, prompt=prompt, size=SIZE, quality="high", n=1)
    return base64.b64decode(r.data[0].b64_json)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for n in sys.argv[1:] or list(IMAGES):
        console.print(f"[bold]{n}[/bold] 생성 중…")
        try:
            (OUT / f"{n}.png").write_bytes(generate(IMAGES[n]))
            console.print(f"  [green]✓ {n}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:180]}[/red]")


if __name__ == "__main__":
    main()
