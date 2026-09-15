"""
[생성] gosu-001 — 시술 절차 레퍼런스 스틸 (고증 반영)

실제 한의원 사진은 저작권이 있고 공모 요강이 제3자 권리 침해를 금지하므로,
조사로 확인한 절차를 근거로 **우리가 직접 만든 레퍼런스**를 자산으로 등록해 쓴다.

근거(조사 결과)
- 진맥: 검지·중지·약지 세 손가락으로 촌·관·척. 팔은 맥침 위에 손바닥이 위로
- 침: 일회용 침은 스프링 침관에 끼워져 있다. 침관을 혈 위에 세우고 침병을 손톱으로 톡 튕긴 뒤 침관을 뺀다
- 전침: 리드선 한 가닥이 침 두 개를 잇는다 (쌍으로 물림)
- 추나: 양 손목 밑동을 척추 좌우 근육에 얹는다. 정중선(뼈) 위를 누르지 않는다
- 한약: 납작한 플랫 파우치, 모서리 tear notch

실행: python3 -m scripts.gen_gosu_procrefs
"""

import base64
import sys
from pathlib import Path

from openai import OpenAI
from rich.console import Console

import config

console = Console()
OUT = Path("assets/gosu/proc")
PHOTO = (
    "A real photograph — a documentary frame from a Korean clinic. NOT an illustration, NOT "
    "CGI. Shot on 35mm film, natural grain, shallow depth of field. Bright modern Korean "
    "clinic, white walls, pale ash wood, neutral daylight. Realistic skin texture. "
    "No text, no watermark, no faces in frame. "
)

IMAGES = {
    "proc_pulse": PHOTO + (
        "Macro close-up of a Korean medicine pulse reading: an elderly patient's forearm rests "
        "palm-up on a small firm pulse cushion. The doctor lays exactly THREE fingertips in a "
        "row along the radial artery just below the wrist crease — index, middle and ring "
        "finger, touching lightly side by side. Only hands and forearms in frame."
    ),
    "proc_needle": PHOTO + (
        "Macro close-up of Korean acupuncture being placed with a guide tube: a short clear "
        "plastic guide tube stands upright on the skin of a patient's upper back, a hair-thin "
        "stainless needle inside it with its handle protruding from the top, and the doctor's "
        "bare fingertip is about to flick the needle handle. A small bottle of hand sanitiser "
        "and a sealed needle packet lie on a stainless tray beside. Only hands in frame."
    ),
    "proc_electro": PHOTO + (
        "Macro close-up of electro-acupuncture on a patient's upper back: six thin needles "
        "stand in two rows of three, and three fine lead wires each clip across a PAIR of "
        "needles, red and black alligator clips on the needle handles, wires running off to a "
        "white stimulator unit at the edge of frame. Only the back and wires in frame."
    ),
    "proc_chuna": PHOTO + (
        "Documentary photo of Korean chuna manual therapy: a patient lies face down in a pale "
        "clinic gown on a padded treatment table. The doctor stands beside and places the "
        "HEELS of both hands on the muscle either side of the spine — not on the spine itself "
        "— elbows spread, leaning his weight over his hands. Shot from the side at table "
        "height. The patient's face is not visible."
    ),
    "proc_pouch": PHOTO + (
        "Product macro on a clinic counter: Korean herbal medicine pouches — FLAT rectangular "
        "sealed pouches lying flat in an open kraft box, plain cream matte film with a small "
        "ink emblem and no readable lettering, a small tear notch at one corner, dark liquid "
        "visible shifting inside one of them. Not standing pouches."
    ),
}


def generate(prompt: str) -> bytes:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    r = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1536",
                               quality="high", n=1)
    return base64.b64decode(r.data[0].b64_json)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for n in sys.argv[1:] or list(IMAGES):
        console.print(f"[bold]{n}[/bold] 생성 중…")
        try:
            (OUT / f"{n}.png").write_bytes(generate(IMAGES[n]))
            console.print(f"  [green]✓ {n}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:160]}[/red]")


if __name__ == "__main__":
    main()
