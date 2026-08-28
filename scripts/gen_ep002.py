"""
[생성] episode-002 — 유나 · 100배 맛있어지는 맥주잔

assets/yuna/episode-002.md의 컷 구성대로 Seedance에 태스크를 제출하고
output/ep002/cuts/ 에 내려받는다. CUT 4(택배 스틸)는 생성하지 않는다 — 조립에서 켄번즈 처리.

잔이 나오는 컷은 실물 제품 사진 기반이다 (product_photo.png → Gemini 편집 프레임):
- cut5·cut7: 실사 i2v — first/last frame 방식. 잔이 실물 그대로 유지된다.
- cut1·cut8a·cut8b: 애니 reference-to-video에 실물 프레임을 레퍼런스로 넣어 형태를 맞춘다.

개인 계정 동시 실행 한도(3)에 맞춰 3개씩 웨이브로 제출한다.

실행: python3 -m scripts.gen_ep002            # 전체
      python3 -m scripts.gen_ep002 cut1 cut7  # 지정 컷만 (재시도용)
"""

import sys
from pathlib import Path

from rich.console import Console

from src.providers import modelark_video as ark

console = Console()

# 2.5(dreamina-seedance-2-5-260628)는 계정 미활성화(잔액 USD 30 조건) — 활성화되면 되돌릴 것
MODEL = "dreamina-seedance-2-0-mini-260615"
OUT = Path("output/ep002/cuts")
YUNA = Path("assets/yuna")

# 공통 스타일(애니 컷 전용) — 캐릭터 시트 크롭이 레퍼런스로 함께 들어간다
STYLE = (
    "Soft warm anime style matching the reference character art, hand-drawn watercolor look, "
    "clean linework, warm cream and orange palette. Young woman with a messy brown hair bun "
    "and an orange t-shirt, same face as the reference images. Waist-up framing. "
    "Extremely exaggerated anime expressions. No text, no letters, no subtitles, no watermark. "
)

# 실물 잔 묘사 — 애니 컷에서도 형태·질감은 제품 사진을 따르게 한다
GLASS = (
    "The beer mug must match the product-photo reference exactly: a short cylindrical "
    "frosted glass mug with a clear frosted handle, translucent matte white when empty; "
    "when filled, the body shows bumpy golden liquid through the frost with a white "
    "foam-like frosted band at the top. Render it in the same anime style but keep its "
    "exact shape and frosted look. "
)

# (이름, 초, camera_fixed, 레퍼런스 파일들 | None, (첫,끝) 프레임 | None, 프롬프트)
CUTS = {
    "cut1": (4, False, ["exp_happy.png", "ref_front.png", "frame_empty.png"], None,
        GLASS +
        "In a department store glassware section, the woman gazes at the frosted glass beer mug "
        "displayed on a warmly lit shelf. Her eyes fill with huge anime sparkles, cheeks blushing, "
        "hands clasped in adoration. The camera tilts down to a small blank price tag below the mug, "
        "then back up to her face now frozen stiff like stone, vertical anime gloom shading over "
        "her forehead. One continuous gentle shot."),
    "cut2": (4, False, ["exp_hmm.png", "ref_front.png"], None,
        "The woman turns away from the display shelf, shoulders slumping heavily, head drooping, "
        "a small dark anime gloom cloud hovering above her head as she exhales a visible sigh. "
        "She glances back once at the shelf with longing, then trudges away. "
        "Department store interior, warm lighting."),
    "cut3": (4, False, ["exp_surprised.png", "exp_excited.png", "ref_front.png"], None,
        "At home, the woman suddenly perks up with a lightbulb-moment expression, grabs her "
        "smartphone and stares at it; her eyes go enormous with anime surprise, then she leaps up "
        "with an excited fist pump and a huge open-mouth grin, sparkles bursting around her. "
        "The phone screen is a soft blur with no readable text."),
    # 실사 i2v — 프롬프트에 STYLE을 붙이지 않는다
    "cut5": (4, False, None, ("frame_unbox.png", None),
        "Photorealistic. Starting from this exact frame: a gentle slow camera push-in toward "
        "the frosted glass mug nestled in the open cardboard box. Soft sparkling glints drift "
        "across the frosted surface as if the mug were treasure; the paper padding settles "
        "slightly. Warm cozy light. The mug itself does not change or move."),
    "cut6": (4, False, ["ref_front.png", "exp_excited.png"], None,
        "The woman comically dashes across her small cozy apartment toward the refrigerator, "
        "leaning forward at full speed with anime motion lines and afterimage blur, huge excited "
        "grin, and yanks the fridge door open. Comedic anime timing, energetic."),
    "cut7": (5, True, None, ("frame_empty.png", "frame_filled.png"),
        "Photorealistic, fixed camera, the mug stays exactly in place. A beer can enters from "
        "the top right and pours golden beer into the empty frosted mug in slow motion. The "
        "frosted body fills bottom-up, turning bumpy golden through the frost, and the top "
        "band becomes a white foam-like layer, ending exactly at the final frame's look. "
        "Condensation glistens. Appetizing, ASMR mood. Camera does not move."),
    "cut8a": (4, False, ["pose_glass.png", "exp_yummy.png", "frame_filled.png"], None,
        GLASS +
        "Waist-up: the woman lifts the frosted mug full of golden beer and drinks it all in one "
        "go, head tilting back, eyes squeezed shut, one comic sweat drop; then she lowers the mug "
        "with a huge refreshed exhale, cheeks flushed pink, blissful."),
    "cut8b": (4, False, ["pose_glass.png", "exp_excited.png", "frame_filled.png"], None,
        GLASS +
        "Waist-up: the woman thrusts the frosted beer mug toward the camera with a huge proud "
        "grin and a wink, sparkles filling the frame, slight wide-angle exaggeration as the mug "
        "nearly touches the lens. She holds the pose at the end, freeze-frame ready."),
}

WAVE = 3  # 개인 계정 동시 실행 한도

# camera_fixed는 모델·태스크 조합을 탄다 — 2.0 mini의 r2v에 보내면 HTTP 400이다.
# 컷 프롬프트에 "Camera does not move"가 들어 있어 의도 자체는 유지된다.
SUPPORTS_CAMERA_FIXED = "seedance-2-5" in MODEL


def main():
    names = sys.argv[1:] or list(CUTS)
    unknown = [n for n in names if n not in CUTS]
    if unknown:
        console.print(f"[red]알 수 없는 컷: {unknown} — 가능한 값: {list(CUTS)}[/red]")
        raise SystemExit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    results, failed = {}, []

    for i in range(0, len(names), WAVE):
        wave = names[i:i + WAVE]
        console.print(f"\n[bold]웨이브 {i // WAVE + 1}: {wave}[/bold]")

        tasks = {}
        for name in wave:
            dur, fixed, refs, frames, prompt = CUTS[name]
            kwargs = dict(
                model=MODEL, resolution="720p", ratio="9:16", duration=dur,
                camera_fixed=(fixed or None) if SUPPORTS_CAMERA_FIXED else None,
            )
            if frames:
                first, last = frames
                kwargs["first_frame"] = YUNA / first
                if last:
                    kwargs["last_frame"] = YUNA / last
                full_prompt = prompt          # 실사 컷 — STYLE 미적용
            else:
                kwargs["reference_images"] = [YUNA / r for r in refs]
                full_prompt = STYLE + prompt
            try:
                tasks[name] = ark.create_task(full_prompt, **kwargs)
            except ark.ModelArkError as exc:
                console.print(f"  [red]✗ {name} 제출 실패: {exc}[/red]")
                failed.append(name)

        for name, task_id in tasks.items():
            try:
                url = ark.wait_for_task(task_id, timeout=900)
                results[name] = ark.download_video(url, OUT / f"{name}.mp4")
            except ark.ModelArkError as exc:
                console.print(f"  [red]✗ {name} 실패: {exc}[/red]")
                failed.append(name)

    console.print(f"\n[bold]완료 {len(results)}/{len(names)}[/bold] → {OUT}")
    if failed:
        console.print(f"[yellow]재시도 필요: python3 -m scripts.gen_ep002 {' '.join(failed)}[/yellow]")


if __name__ == "__main__":
    main()
