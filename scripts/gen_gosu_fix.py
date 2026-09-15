"""
[생성] gosu-001 한의원 고증 수정판 (Seedance 2.5, 1080×1920, 6초)

한의원 실제 절차 조사 결과를 반영한다 (조사 출처는 대화 기록 참조).
  1. 진맥: 두 손가락 → **세 손가락**(검지·중지·약지)으로 촌·관·척. 맥침 위에 손바닥이 위로
  2. 부항: 한 줄 → **척추 좌우 대칭**, 척추뼈 위에는 놓지 않는다
  3. 부항 복장: 탈의 → **환자복 유지** (침 컷과 연속성)
  4. 침: 장갑 → **손소독제**, **침관(guide tube)**을 대고 침병을 톡 튕겨 넣는다
  5. 추나: 양손 포개 정중선 압박 → **양 손목 밑동을 척추 좌우에** 교차로. 근육 이완 단계 먼저
  6. 한약: 스탠딩 파우치 → **납작한 플랫 파우치**
  7. 전침: 침 6개(3쌍) — 리드선 한 가닥이 침 두 개를 잇는다

실행: python3 -m scripts.gen_gosu_fix            # 전체
      python3 -m scripts.gen_gosu_fix t2_arrive  # 지정만
"""

import json
import sys
from pathlib import Path

from rich.console import Console

from src.providers import modelark_video as ark

console = Console()
MODEL = "dreamina-seedance-2-5-260628"
OUT = Path("output/gosu/cuts")
IDS = json.loads(Path("assets/gosu/asset_ids.json").read_text())

def A(k): return f"asset://{IDS[k]}"

OVERALL = """
[Overall]
Bright modern Korean clinic, white walls and pale ash wood, neutral daylight, no yellow cast.
Live-action film, shot on a 35mm cinema lens, shallow depth of field, fine film grain,
authentic skin texture, no beautification. HD, rich details.
Understated and natural: the reaction is small but unmistakable. No mugging, no bulging eyes,
no slapstick, no cartoonish expressions. Subject 1's face stays consistent with Image 1.

[Strictly exclude]
No subtitles. Do not generate a logo. Do not generate a watermark. No duplicate characters.
Nobody speaks. No blood, no wounds.
"""

BIND = """[Asset Bindings]
Image 1: facial reference of the old man (Subject 1).
Image 2: full-body reference of Subject 1.
Image 3: the young male doctor in a white coat (Subject 2).
Image 4: the clinic treatment room."""

REFS = [A("r2_face_b"), A("r2_full_b"), A("doctor_front"), A("clinic_bed")]

SHOTS = {
    # 1) 진맥 — 세 손가락
    "t2_arrive": (REFS, BIND + """

[One-Sentence Summary]
Subject 1 drops onto a clinic bed and Subject 2 is already taking his pulse with three fingers.

[Shot 1, 0-2s]
Locked camera on the treatment bed of Image 4. Subject 1 thuds down onto the white bed out of
thin air, the curtain still swinging, and he pushes himself up on one elbow, blinking.

[Shot 2, 2-4s]
Macro insert on his wrist. His forearm rests palm-up on a small pulse cushion. Subject 2 lays
THREE fingertips — index, middle and ring finger — in a row along the artery just below the
wrist crease, the middle finger settling first, and holds them still.

[Shot 3, 4-6s]
Cut to a close two-shot. Subject 1 stares at the three fingers on his wrist, then up at
Subject 2, frozen. A beat. His eyebrows lift.

Sound: a soft thud, swaying fabric, quiet room tone.""" + OVERALL),

    # 2) 침 — 손소독제 + 침관 + 6개(3쌍)
    "t3_needle": (REFS, BIND + """

[One-Sentence Summary]
Subject 2 places six needles with a guide tube and runs an electro stimulator, and something
lets go in Subject 1's body.

[Shot 1, 0-2s]
Macro close-up. Subject 2 pumps hand sanitiser and rubs his bare hands together, then takes a
small plastic guide tube with a hair-thin needle inside and stands it on Subject 1's gowned
shoulder.

[Shot 2, 2-4s]
Stay tight. He flicks the top of the needle handle with a fingernail — the needle drops in —
and lifts the tube away. He repeats it in quick rhythm until six needles stand in two rows of
three, then clips a fine red and black lead wire across each pair. Slow motion on one flick.

[Shot 3, 4-6s]
Cut to a close-up of Subject 1's face on the pillow. His shoulder twitches once and he holds
still, jaw set. A beat. Then his eyebrows lift, his eyes lose focus, and he lets out a slow
breath as his whole face loosens.

Sound: a sanitiser pump, small taps in rhythm, a faint electric hum, then a long breath out.""" + OVERALL),

    # 3) 부항 — 환자복 + 좌우 대칭
    "t4_cupping": ([A("cup_still2"), A("r2_face_b")], """[Asset Bindings]
Image 1: the exact scene reference — the old man in a clinic gown lying face down with clear
cupping cups on his back, his head turned toward the camera.
Image 2: facial reference of the old man (Subject 1).

[One-Sentence Summary]
The whole story is on Subject 1's face: he feels the pull take hold, and then he feels it all
drain away.

[Shot 1, 0-2s]
Match the framing of Image 1. A bare hand seats a white pump on the last clear cup and clicks
it twice. Stay on Subject 1's face: at the click his eyes widen and his mouth opens slightly,
his brow lifting, as if he can feel something being pulled out of his back.

[Shot 2, 2-4s]
Push in close on his face. He holds that look, breath caught. Then his eyelids flutter, his
brow smooths out and his jaw goes slack, one stage at a time.

[Shot 3, 4-6s]
Very close on his face. A long breath leaves him, his eyes half close, and his cheek settles
heavily onto the bed with a small satisfied expression.

Sound: two pump clicks, a deep suction pull, then a long slow breath out.""" + OVERALL),

    # 4) 추나 — 근육 이완 먼저, 양 수근부를 좌우에
    "t5_chuna": (REFS + [A("prop_chuna")], BIND + """
Image 5: chuna manual therapy on a treatment table.

[One-Sentence Summary]
Subject 2 loosens Subject 1's back, then presses once and his whole body resets.

[Shot 1, 0-2s]
Start tight on Subject 1's face, lying face down on the padded table in a clinic gown, head
turned toward the camera. The camera glides smoothly down along his body to his mid back,
where Subject 2's hands are kneading the muscle alongside his spine.

[Shot 2, 2-4s]
Subject 2 sets the heels of both hands on the muscle either side of the spine, not on the
bone, spreads his elbows, shifts his weight over his hands and drives one short controlled
thrust straight down. Slow motion on the thrust.

[Shot 3, 4-6s]
Cut to a close-up of Subject 1's face. His body jolts once and his eyes snap wide, breath
caught. He holds for a beat. Then his shoulders drop, his face loosens, and he sinks into the
table as his back settles flat.

Sound: cloth shifting, a single sharp crack, then a long breath out.""" + OVERALL),

    # 5) 한약 — 납작한 플랫 파우치
    "t6_herb": ([A("r2_face_b"), A("r2_full_b"), A("clinic_counter")], """[Asset Bindings]
Image 1: facial reference of the old man (Subject 1).
Image 2: full-body reference of Subject 1.
Image 3: the clinic reception counter.

[One-Sentence Summary]
Subject 1 downs a flat herbal medicine pouch at the counter and feels it go all the way down.

[Shot 1, 0-2s]
Macro close-up on the counter of Image 3. A Korean clinic herbal medicine pouch is lifted from
an open kraft box: a FLAT rectangular sealed pouch lying flat, not a standing pouch, printed
in plain cream with a small ink emblem and no readable lettering, the dark liquid shifting
inside. He tears the notched corner off cleanly.

[Shot 2, 2-4s]
He tips the pouch back and drinks the dark brown liquid down in one go, his throat working.
Hold on him from a low angle as he finishes and lowers the pouch.

[Shot 3, 4-6s]
Cut to a close-up of his face. He stands still, eyes unfocused, as if listening to something
inside him. A beat. Then he breathes out, his shoulders drop, and he nods once, slowly.

Sound: paper tearing, swallowing, then a long breath out.""" + OVERALL),
}


def main() -> None:
    names = sys.argv[1:] or list(SHOTS)
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in names:
        refs, prompt = SHOTS[n]
        path = OUT / f"{n}.mp4"
        console.print(f"[bold]{n}[/bold] (2.5 · 1080p · 6초)")
        try:
            ark.generate(prompt=prompt, output_path=path, reference_images=refs,
                         model=MODEL, resolution="1080p", ratio="9:16", duration=6,
                         generate_audio=True)
            console.print(f"  [green]✓ {path}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:150]}[/red]")
            failed.append(n)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_fix {' '.join(failed)}[/yellow]")


if __name__ == "__main__":
    main()
