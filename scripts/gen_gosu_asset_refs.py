"""
[생성] gosu-001 — BytePlus 자산 라이브러리 등록용 노고수 레퍼런스 2장

Private virtual portrait library 권장 구성(docs.byteplus.com/en/docs/ModelArk/2333565):
  - 전신 정면, 세로
  - 얼굴 클로즈업, 세로, 무표정, 어깨 위, 얼굴이 화면의 약 2/3

얼굴 동일성은 gosu_front.png를 입력으로 넣어 유지한다.
이 두 장은 공개 URL이 필요해 저장소에 커밋된다 (가상 인물이라 초상권 이슈 없음).

실행: python3 -m scripts.gen_gosu_asset_refs
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
    "Photorealistic studio photograph of EXACTLY the same elderly Korean swordsman as in "
    "the reference image: same face, same long white hair in a topknot with a black "
    "manggeon headband, same long white beard, same grey-white hanbok martial robe. Keep "
    "the identity perfectly consistent. Plain light grey seamless studio background, even "
    "soft lighting, natural skin texture, no text, no watermark. "
)

IMAGES = {
    "asset_gosu_full": BASE + (
        "FULL BODY shot from head to feet, standing straight and facing the camera "
        "directly, arms relaxed at his sides, neutral expression. Vertical framing with "
        "the whole body inside the frame."
    ),
    "asset_gosu_face": BASE + (
        "FACIAL CLOSE-UP from just above the shoulders, facing the camera directly with a "
        "completely neutral expression, mouth closed, eyes open looking at the lens. The "
        "face fills about two thirds of the vertical frame."
    ),
}


def generate(prompt: str) -> bytes:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    r = client.images.edit(
        model=MODEL, image=[open(ANCHOR, "rb")], prompt=prompt, size=SIZE, quality="medium"
    )
    return base64.b64decode(r.data[0].b64_json)


def main():
    names = sys.argv[1:] or list(IMAGES)
    failed = []
    for n in names:
        console.print(f"[bold]{n}[/bold] 생성 중…")
        try:
            (OUT / f"{n}.png").write_bytes(generate(IMAGES[n]))
            console.print(f"  [green]✓ {n}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:200]}[/red]")
            failed.append(n)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
