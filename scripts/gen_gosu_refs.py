"""
[생성] gosu-001 (한의약 공모전) — 실사 인물·장소 레퍼런스 (gpt-image-1, text-to-image)

assets/gosu/contest-nikom-2026.md 생성 매핑 0단계.
실사는 얼굴이 컷마다 흔들리기 쉬워서 인물 레퍼런스를 먼저 고정하고,
본 컷은 이 이미지들을 입력으로 넣어(images.edit) 만든다.

  gosu_front       — 고수 정면 상반신, 백발 노인 (모든 컷의 얼굴 앵커)
  doctor_front     — 한의사 정면 상반신, 남성 (미소) — 여성 버전은 doctor_front_f.png
  enemy_fire       — 적, 흑발 여성, 손바닥 화염 (CUT 1 전용) — 남성 버전은 enemy_fire_m.png
  clinic_bed       — 한의원 실내: 베드·커튼 (CUT 2~5 배경)
  clinic_counter   — 한의원 실내: 카운터·파우치 박스 (CUT 6~7 배경)
  prop_electro     — 전침 클로즈업: 호침+클립 리드선+저주파 패드 (사용자 제공 사진 구성)
  prop_cupping     — 부항: 투명 플라스틱 펌프식 컵
  prop_chuna       — 추나: 드롭 테이블 위 수기

한의원 인테리어는 큐플레이스·굿테리어 시공 사례(아치·간접조명·템바보드·테라조) 기준이되 **톤은 밝은 흰색+연한 애쉬 우드, 5000K 주광색** (사용자 결정: 노란 베이지 톤 금지).

실행: python3 -m scripts.gen_gosu_refs               # 전체
      python3 -m scripts.gen_gosu_refs gosu_front    # 지정만 (재시도용)
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
SIZE = "1024x1536"

PHOTO = (
    "Photorealistic cinematic still, shot on a full-frame camera with an 85mm lens, "
    "shallow depth of field, natural skin texture, film grain, no text, no letters, "
    "no watermark, no logo. "
)

IMAGES = {
    "gosu_front": PHOTO + (
        "Portrait of a Korean man in his early 70s, a legendary elder swordsman from a "
        "Korean Joseon-era martial-arts drama (not Japanese samurai): long pure white hair "
        "in a Korean sangtu topknot held with a thin black manggeon headband, long white "
        "beard and white eyebrows, deeply lined dignified face, sharp clear eyes still full "
        "of fighting spirit. Wearing a light grey-white Korean hanbok-style martial robe "
        "(durumagi) with a dark cloth belt, a Korean hwando sword hilt visible over his "
        "shoulder. Front-facing, chest-up, neutral serious expression, looking straight at "
        "camera. Plain misty grey background, soft overcast daylight."
    ),
    "doctor_front": PHOTO + (
        "Portrait of a Korean man in his early 30s, a doctor of traditional Korean "
        "medicine at a neighborhood clinic: white doctor's coat over a light shirt, "
        "thin-rimmed glasses, neat short hair, a warm calm gentle smile. Front-facing, "
        "chest-up, looking at camera. Background: bright clinic interior with a beige "
        "curtain, slightly out of focus, soft natural window light."
    ),
    "enemy_fire": PHOTO + (
        "A strikingly beautiful young Korean woman in her mid 20s, the classic wuxia "
        "femme-fatale villainess: flawless porcelain skin, elegant sharp features, deep "
        "red lips, long glossy jet-black hair half pinned up with an ornate silver hairpin "
        "and the rest flowing in the wind, a seductive cold smirk with one eyebrow raised. "
        "Wearing a luxurious black and deep-crimson silk wuxia gown with gold embroidery "
        "and wide flowing sleeves. Both palms extended gracefully toward the camera with "
        "real fire blooming from her hands, embers floating. Night cliff-top with mist, "
        "flames giving warm orange rim light against cool blue darkness, glamorous "
        "beauty-lighting on her face. Medium shot."
    ),
    "clinic_bed": PHOTO + (
        "Interior of a newly opened, stylish modern Korean traditional-medicine clinic "
        "treatment room, bright clean premium interior: crisp white walls, very pale ash "
        "wood accents, a low partition wall between beds with light off-white linen "
        "curtains on a slim silver curtain rail, bright neutral white LED cove lighting "
        "(daylight 5000K, not warm yellow), light grey carpet tile floor, a "
        "treatment bed with a clean white sheet and a small pillow, a slim white "
        "electro-acupuncture stimulator unit with a small screen and red/yellow/black lead "
        "cables on a wooden side cart, a tray of thin stainless acupuncture needles. "
        "Airy, bright, modern, cool-neutral white balance, no yellow cast. No people. Wide "
        "shot, eye level."
    ),
    "clinic_counter": PHOTO + (
        "Reception area of a newly opened, stylish modern Korean traditional-medicine "
        "clinic, bright clean premium interior: curved reception desk finished in vertical "
        "slat panels in very pale whitewashed ash wood, white and light grey palette, white "
        "terrazzo accent wall, a soft arch doorway, bright neutral white indirect lighting "
        "under wall shelves (daylight 5000K, not warm yellow), a pale wood bench, a "
        "potted olive tree. On the counter, a neat kraft-paper box of herbal-medicine "
        "liquid pouches with a few brown pouches beside it. Framed abstract ink mountain "
        "painting (absolutely no characters, letters or calligraphy anywhere). Airy, bright, "
        "cool-neutral white balance, no yellow cast. No people. Medium wide shot."
    ),
    "prop_electro": PHOTO + (
        "Close-up of a real electro-acupuncture treatment on a patient's bare upper back "
        "lying face down on a clinic bed: five or six very thin stainless acupuncture "
        "needles inserted in the back, small metal alligator clips attached to the needle "
        "handles with thin red and black lead wires, plus two round black adhesive "
        "low-frequency electrode pads stuck on the skin nearby, wires running to a white "
        "electro-stimulator unit with a small screen and dials at the edge of frame. "
        "Off-white curtain background, bright neutral clinic light, no yellow cast. Only the back and a doctor's gloved "
        "hand visible, no face."
    ),
    "prop_cupping": PHOTO + (
        "Clinical medical documentation photo of cupping therapy in a modern Korean clinic: "
        "an elderly male patient lying face down wearing a clinic treatment top pulled down "
        "to expose only the upper back, six clear transparent plastic pump-type cupping cups with valve "
        "tops attached to the back, skin gently drawn up inside the cups, a white manual "
        "suction pump gun held by a doctor's hand attaching the last cup. Off-white curtain "
        "background, bright neutral clinic light, no yellow cast. No face visible."
    ),
    "prop_chuna": PHOTO + (
        "Real chuna manual therapy scene in a modern Korean traditional-medicine clinic: "
        "a patient lying face down on a beige chiropractic drop table with a face hole, a "
        "male doctor in a white coat standing beside, both hands stacked on the patient's "
        "mid back applying a controlled thrust. White walls, pale ash wood, bright neutral "
        "light, no yellow cast. Patient's face not visible. Medium shot from the side."
    ),
}


def generate(prompt: str) -> bytes:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    result = client.images.generate(
        model=MODEL, prompt=prompt, size=SIZE, quality="medium", n=1
    )
    return base64.b64decode(result.data[0].b64_json)


def main():
    names = sys.argv[1:] or list(IMAGES)
    unknown = [n for n in names if n not in IMAGES]
    if unknown:
        console.print(f"[red]알 수 없는 이름: {unknown} — 가능한 값: {list(IMAGES)}[/red]")
        raise SystemExit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for name in names:
        console.print(f"[bold]{name}[/bold] 생성 중…")
        try:
            path = OUT / f"{name}.png"
            path.write_bytes(generate(IMAGES[name]))
            console.print(f"  [green]✓ {path} ({path.stat().st_size // 1024}KB)[/green]")
        except Exception as exc:
            console.print(f"  [red]✗ {name}: {exc}[/red]")
            failed.append(name)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_refs {' '.join(failed)}[/yellow]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
