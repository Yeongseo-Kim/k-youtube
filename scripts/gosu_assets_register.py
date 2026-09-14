"""
[등록] gosu-001 — 로컬 레퍼런스를 BytePlus 자산 라이브러리에 올린다.

Seedance 2.x는 실사 얼굴이 담긴 이미지를 직접 넣으면 거부한다.
공개 URL(raw.githubusercontent) → CreateAsset → Active → `asset://<자산ID>` 로
참조해야 통과한다. 등록 결과는 assets/gosu/asset_ids.json에 캐시한다.

실행: python3 -m scripts.gosu_assets_register            # 미등록분만
      python3 -m scripts.gosu_assets_register --list     # 현황만
"""

import json
import sys
import time
from pathlib import Path

from rich.console import Console

import src.providers.byteplus_assets as ba

console = Console()
CACHE = Path("assets/gosu/asset_ids.json")
BRANCH = "claude/c-dance-video-production-d2huo8"
RAW = f"https://raw.githubusercontent.com/Yeongseo-Kim/k-youtube/{BRANCH}"

# 그룹은 인물 단위. 노고수와 악녀를 분리한다.
GROUPS = {
    "gosu": {"id": "group-20260914111106-jcdcp", "name": "gosu-무영"},
    "villain": {"id": None, "name": "gosu-악녀"},
}

# 자산명 → (그룹, 저장소 경로)
ASSETS = {
    "asset_gosu_full": ("gosu", "assets/gosu/asset_gosu_full.png"),
    "asset_gosu_face": ("gosu", "assets/gosu/asset_gosu_face.png"),
    "c1_slash": ("gosu", "assets/gosu/cuts/c1_slash.png"),
    "c1_hit": ("gosu", "assets/gosu/cuts/c1_hit.png"),
    "c1_juhwa": ("gosu", "assets/gosu/cuts/c1_juhwa.png"),
    "c1_fall": ("gosu", "assets/gosu/cuts/c1_fall.png"),
    "c1_portal": ("gosu", "assets/gosu/cuts/c1_portal.png"),
    "c1_villain": ("villain", "assets/gosu/cuts/c1_villain.png"),
}


def load() -> dict:
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def save(data: dict) -> None:
    CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def ensure_group(key: str, cache: dict) -> str:
    gid = GROUPS[key]["id"] or cache.get("_groups", {}).get(key)
    if gid:
        return gid
    gid = ba.create_group(GROUPS[key]["name"], "한의약 공모전 — AI 생성 가상 인물")
    cache.setdefault("_groups", {})[key] = gid
    save(cache)
    console.print(f"  [green]그룹 생성 {key} → {gid}[/green]")
    return gid


def main() -> None:
    cache = load()
    if "--list" in sys.argv:
        for k, v in cache.items():
            console.print(f"{k}: {v}")
        return

    for name, (gkey, path) in ASSETS.items():
        if name in cache:
            continue
        gid = ensure_group(gkey, cache)
        url = f"{RAW}/{path}"
        console.print(f"[bold]{name}[/bold] 등록 중…")
        time.sleep(25)  # 무료 등급 CreateAsset은 3 QPM — 간격을 둬야 429가 안 난다
        try:
            aid = ba.create_asset(gid, url, name)
            cache[name] = aid
            save(cache)
            console.print(f"  [green]✓ {aid}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {str(e)[:160]}[/red]")

    # Active 대기
    for name, aid in list(cache.items()):
        if name.startswith("_"):
            continue
        for _ in range(40):
            st = ba.get_asset(aid).get("Status", "")
            if st in ("Active", "Failed"):
                break
            time.sleep(8)
        console.print(f"{name}: {st}")


if __name__ == "__main__":
    main()
