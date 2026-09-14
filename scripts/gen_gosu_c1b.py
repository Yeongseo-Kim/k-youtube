"""
[생성] gosu-001 CUT 1 확장 — 전투 시퀀스를 영화적으로 (Seedance 2.0-mini, 720p, 오디오 포함)

문제: 4초 한 컷씩 여섯 개를 붙이니 앵글이 단조롭고 속도감이 없다.
해법: **짧은 샷을 많이** 만들고 편집에서 0.6~1.5초로 잘라 빠르게 붙인다.
샷마다 렌즈·앵글·카메라 무빙을 명시한다 (와이드 → 로우앵글 → 익스트림 클로즈업 →
POV → 슬로우모션 → 크레인). 인물 동일성은 등록된 자산(asset://)이 잡는다.

실행: python3 -m scripts.gen_gosu_c1b            # 전체
      python3 -m scripts.gen_gosu_c1b b_wide     # 지정만
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
    "Photorealistic live-action wuxia film, vertical 9:16, anamorphic cinematic look, "
    "high contrast teal-and-orange night grade, volumetric mist, practical firelight. "
    "The people must look exactly like the reference assets. Film grain, no text, no "
    "letters, no subtitles, no watermark. "
)
G = lambda: f"asset://{IDS['asset_gosu_face']}"
GF = lambda: f"asset://{IDS['asset_gosu_full']}"
V = lambda: f"asset://{IDS['c1_villain']}"

# 이름: (초, 참조, 프롬프트) — 편집에서 0.6~1.5초로 트림
SHOTS = {
    # ── 재작업 2차: 컷 연결(좌=노고수, 우=악녀 고정) + 샷 안에서 카메라가 움직인다
    "d_face": (4, [GF(), V()], STYLE +
        "MID-AIR STANDOFF above a misty cliff at night. The OLD MASTER hovers on the LEFT "
        "side of the frame, the VILLAINESS on the RIGHT, both facing each other in profile, "
        "robes snapping in the wind. The camera starts tight between them and PULLS BACK "
        "FAST to reveal both. Sound: a rising wind roar. No music, no speech."),
    "d_clash": (4, [GF(), V()], STYLE +
        "Same mid-air night cliff, OLD MASTER on the LEFT, VILLAINESS on the RIGHT. They "
        "collide and trade blindingly fast strikes, white impact flashes and shockwave "
        "rings bursting between them, the camera ARCS AROUND them rapidly. Everything moves "
        "at extreme speed, no injuries shown. Sound: rapid cracking impacts. No music, no speech."),
    "d_fire": (4, [V()], STYLE +
        "The VILLAINESS is centered in frame in mid-air, close to the lens. The camera "
        "RUSHES BACKWARD away from her as she rears back, both palms sweeping together — "
        "then she THRUSTS them forward and a huge fireball ERUPTS toward the camera, "
        "filling the frame. Fast, violent, one continuous move. "
        "Sound: a whoosh then a massive fire blast. No music, no speech."),
    "d_hit": (4, [GF()], STYLE +
        "The OLD MASTER, mid-air on the LEFT, is struck by the fireball head on. He is "
        "blasted violently to the RIGHT and away from camera, spinning through the night "
        "sky trailing fire and embers. The camera WHIP PANS right to follow him, then he "
        "shrinks into the distance. Sound: an explosion and rushing wind. No music, no speech."),
    # ── 공중 대치 → 파바방 → 격추 → 포탈 (사용자 지시: 준비 샷 빼고 임팩트만)
    "c_air_face": (4, [GF(), V()], STYLE +
        "MID-AIR STANDOFF, wuxia wire-fu: the old master and the villainess hover in the "
        "air high above the misty cliff, facing each other, robes and hair billowing "
        "violently, dust and leaves swirling below them. The camera ORBITS around the two "
        "of them fast. Sound: deep wind roar and a low tension rumble. No music, no speech."),
    "c_air_clash": (4, [GF(), V()], STYLE +
        "RAPID MID-AIR EXCHANGE: the master and the villainess trade a flurry of sword and "
        "palm strikes while suspended in the air, blinding white impact flashes and "
        "shockwave rings bursting at each contact, debris flying. Fast whip pans and hard "
        "camera shakes between blows. Sound: rapid sharp impacts, cracking shockwaves. "
        "No music, no speech."),
    "c_blast": (4, [GF(), V()], STYLE +
        "She unleashes a massive fireball point blank. It EXPLODES against the master's "
        "chest in mid-air and he is blasted backward across the sky, spinning, trailing "
        "fire and embers, robe shredding in the wind. Camera whips to follow him. "
        "Sound: a huge fiery explosion and rushing wind. No music, no speech."),
    "c_crash": (4, [GF()], STYLE +
        "The master SLAMS down into the rocky cliff ground from a great height, cratering "
        "the stone, a ring of dust and debris blasting outward toward the camera. Ground "
        "level lens, violent impact shake, then he lies still. "
        "Sound: a massive ground impact and falling rubble. No music, no speech."),
    "c_portal_suck": (4, [GF()], STYLE +
        "A blinding blue-white portal RIPS OPEN in the ground directly beneath his body, "
        "spinning violently, its light beaming upward. The vortex sucks him downward fast "
        "and he vanishes, then the portal snaps shut leaving darkness. Camera looks "
        "straight down, then jolts. Sound: a deep rising vortex whoosh that snaps shut. "
        "No music, no speech."),
    "b_wide": (4, [GF(), V()], STYLE +
        "EXTREME WIDE establishing shot: the old white-bearded master and the young "
        "villainess stand far apart facing each other on a narrow misty cliff top at night, "
        "tiny against huge mountains. Slow aerial drone push-in toward them. "
        "Sound: howling wind. No music, no speech."),
    "b_feet": (4, [GF()], STYLE +
        "LOW ANGLE ground-level shot of the master's feet planted on wet rock, his robe "
        "hem and the tip of his sword in frame. The camera TILTS UP FAST along his body to "
        "his face as he raises the blade. Sound: gravel crunch and a metallic ring."),
    "b_eyes": (4, [G()], STYLE +
        "EXTREME CLOSE-UP on the master's eyes only, filling the frame, narrowing with "
        "killing intent. Rapid snap zoom in, slight handheld shake. "
        "Sound: a low rising tension whoosh."),
    "b_villain_cu": (4, [V()], STYLE +
        "EXTREME CLOSE-UP of the villainess: her red lips curl into a cold smirk, the "
        "silver hairpin glints, rack focus from the hairpin to her eyes. "
        "Sound: a soft metallic shimmer and wind."),
    "b_ignite": (4, [V()], STYLE +
        "CLOSE-UP on her open palms from below as fire ignites and swells between them, "
        "embers streaming upward. Fast dolly in, the flames flare and light her face from "
        "underneath. Sound: fire igniting with a deep whoosh."),
    "b_dash": (4, [GF()], STYLE +
        "SIDE TRACKING SHOT: the master dashes forward along the cliff, robe and white "
        "hair streaming, camera races alongside him handheld. SPEED RAMP — slow motion "
        "then snapping to fast. Sound: cloth flapping and running footsteps."),
    "b_fireball_pov": (4, [V()], STYLE +
        "POV OF THE FIREBALL: the camera IS the fireball, flying fast and low straight "
        "toward the old master across the cliff, flames licking the edges of the frame, "
        "motion blur streaking past. Sound: roaring fire rushing forward."),
    "b_impact_side": (4, [GF()], STYLE +
        "SIDE VIEW in SLOW MOTION: the fireball slams into the master's chest, his body "
        "lifts off the ground and arcs backward, robe billowing, sparks and embers "
        "exploding outward. Camera pushes in slowly. Sound: a deep fiery impact boom."),
    "b_sword_drop": (4, [GF()], STYLE +
        "INSERT SHOT, slow motion: the sword spins out of his hand through the air and "
        "clatters onto wet rock, sparks skittering. Shallow focus, camera low. "
        "Sound: metal clattering on stone."),
    "b_ground": (4, [GF()], STYLE +
        "GROUND-LEVEL SHOT, lens almost touching the rock: the master crashes down in "
        "front of the camera and dust bursts toward the lens. Handheld impact shake. "
        "Sound: a heavy body hitting gravel."),
}


def main() -> None:
    names = sys.argv[1:] or list(SHOTS)
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for n in names:
        dur, refs, prompt = SHOTS[n]
        path = OUT / f"{n}.mp4"
        if path.exists() and not sys.argv[1:]:
            console.print(f"[dim]{n} 건너뜀[/dim]")
            continue
        console.print(f"[bold]{n}[/bold] ({dur}초)")
        try:
            ark.generate(prompt=prompt, output_path=path, reference_images=refs,
                         model=MODEL, resolution="720p", ratio="9:16", duration=dur,
                         generate_audio=True)
            console.print(f"  [green]✓ {path}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {n}: {str(e)[:160]}[/red]")
            failed.append(n)
    if failed:
        console.print(f"[yellow]재시도: python3 -m scripts.gen_gosu_c1b {' '.join(failed)}[/yellow]")


if __name__ == "__main__":
    main()
