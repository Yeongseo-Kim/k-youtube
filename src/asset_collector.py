"""
[모듈 3] 에셋 수집 — 3층 필터 + 영상10/이미지10 분리 수집

3층 필터:
  1층: 범용 키워드 차단 (reaction, cover, FMV 등 → 검색 단계에서 즉시 제외)
  2층: GPT 채널 분류 (official/media/fan → fan 제외)
  3층: 이미지 안전 폴백 (공식 영상 부족 시 뉴스 이미지로 대체)

흐름:
  ① YouTube 검색 → 메타데이터 수집 (다운로드 없이)
  ② 1층 키워드 필터 → 2층 GPT 채널/적합성 판단
  ③ official/media만 다운로드 (최대 10개)
  ④ 뉴스/검색 이미지 별도 수집 (최대 10개)
  ⑤ 전체 풀 asset_pool.json 저장 + AI 씬 자동 배치
"""

import json
import subprocess
import requests
import base64
import tempfile
from pathlib import Path
from PIL import Image
from rich.console import Console
from openai import OpenAI

import config

console = Console()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1층 필터: 범용 차단 키워드 (모든 토픽에 적용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BLOCKED_TITLE_KEYWORDS = [
    "reaction", "react", "cover", "dance cover", "fmv", "edit",
    "compilation", "tutorial", "fan", "fanmade", "fan made",
    "ranking", "tier list", "unpacking", "unboxing",
    "리액션", "커버", "팬메이드", "가사해석", "해석", "자막",
    "언박싱", "따라하기", "커버댄스",
]


import re

def _is_blocked_by_keywords(title: str, description: str) -> bool:
    """1층 필터: 제목/설명에 차단 키워드가 있으면 True"""
    text = (title + " " + description).lower()
    for kw in BLOCKED_TITLE_KEYWORDS:
        if re.match(r"^[a-z\s]+$", kw):
            if re.search(rf"\b{kw}\b", text):
                return True
        else:
            if kw in text:
                return True
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# YouTube 메타데이터 수집
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_youtube_metadata(queries: list[str], max_per_query: int = 5) -> list[dict]:
    """yt-dlp로 YouTube 검색 → 다운로드 없이 메타데이터만 수집 + 1층 필터 적용"""
    seen_urls: set[str] = set()
    results: list[dict] = []

    for query in queries:
        try:
            cmd = [
                "yt-dlp",
                f"ytsearch{max_per_query}:{query}",
                "--replace-in-metadata", "description", r"[\n\r]+", " ",
                "--print", "%(title)s|||%(description).200s|||%(channel)s|||%(view_count)s|||%(duration)s|||%(webpage_url)s",
                "--no-download",
                "--quiet",
                "--no-warnings",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                continue

            for line in proc.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|||")
                if len(parts) < 6:
                    continue
                url = parts[5].strip()
                if url in seen_urls:
                    continue

                title = parts[0].strip()
                desc = parts[1].strip()

                # ── 1층 필터: 키워드 차단 ──
                if _is_blocked_by_keywords(title, desc):
                    console.print(f"  [dim]  ✗ 키워드 차단: {title[:50]}[/dim]")
                    continue

                seen_urls.add(url)

                try:
                    view_count = int(parts[3].strip()) if parts[3].strip().isdigit() else 0
                except ValueError:
                    view_count = 0
                try:
                    duration = int(parts[4].strip()) if parts[4].strip().isdigit() else 0
                except ValueError:
                    duration = 0

                results.append({
                    "title": title,
                    "description": desc,
                    "channel": parts[2].strip(),
                    "view_count": view_count,
                    "duration": duration,
                    "url": url,
                    "query": query,
                })

            console.print(f"  [dim]YouTube '{query}': {sum(1 for r in results if r['query']==query)}개 통과[/dim]")

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            console.print(f"  [yellow]⚠ YouTube 검색 실패 ({query}): {e}[/yellow]")

    console.print(f"  [cyan]YouTube 메타데이터 총 {len(results)}개 (1층 필터 통과)[/cyan]")
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2층 필터: GPT 채널 분류 + 적합성 판단
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def score_and_classify_videos(videos_meta: list[dict], topic: dict, scenes: list[dict]) -> list[dict]:
    """GPT-4o-mini로 채널 유형 분류 + 적합성 점수.
    
    채널 유형:
      - official: 소속사, 아티스트 본인, 방송사 공식 채널
      - media: 뉴스/언론사 채널
      - fan: 팬 채널, 개인 채널, 리뷰어
    
    fan 채널은 자동으로 낮은 점수를 받아 제외됨.
    """
    if not videos_meta:
        return []

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    scenes_text = "\n".join(
        f"  scene_{s['scene_id']}: {s['description']}" for s in scenes
    )

    videos_text = "\n".join(
        f"  V{i+1}: title=\"{v['title']}\", channel=\"{v['channel']}\", "
        f"views={v['view_count']:,}, duration={v['duration']}s, "
        f"desc=\"{v['description'][:80]}\""
        for i, v in enumerate(videos_meta)
    )

    prompt = f"""You are a K-content video asset curator. Classify and score YouTube videos.

TOPIC: {topic.get('headline', '')}
TOPIC_KO: {topic.get('headline_ko', '')}

SCENES:
{scenes_text}

VIDEOS:
{videos_text}

For each video, determine:
1. channel_type: "official" (agency, broadcaster, artist) | "media" (news channel) | "fan" (personal, fan channel, reviewer)
2. score (1-10):
   - official channels: base 7-10
   - media channels: base 5-8
   - fan channels: base 3-6 (We avoid reaction content, but curated info is okay)
   - Perfect topic match → higher score
   - Reaction/commentary → score 1
3. best matching scene_id (int or null)

Return JSON: {{"scores": [{{"idx": 1, "channel_type": "official", "score": 9, "reason": "...", "scene_id": 2}}, ...]}}"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        result = json.loads(resp.choices[0].message.content)
        scores = result.get("scores", [])

        for score_info in scores:
            idx = score_info.get("idx", 0) - 1
            if 0 <= idx < len(videos_meta):
                videos_meta[idx]["relevance_score"] = score_info.get("score", 0)
                videos_meta[idx]["channel_type"] = score_info.get("channel_type", "fan")
                videos_meta[idx]["relevance_reason"] = score_info.get("reason", "")
                videos_meta[idx]["recommended_scene"] = score_info.get("scene_id", None)

        for v in videos_meta:
            v.setdefault("relevance_score", 0)
            v.setdefault("channel_type", "unknown")
            v.setdefault("relevance_reason", "미분류")
            v.setdefault("recommended_scene", None)

        # fan 채널은 강제 4점 이하로 제한하지만 유용한 경우 4점까지는 허용
        for v in videos_meta:
            if v["channel_type"] == "fan" and v["relevance_score"] > 4:
                v["relevance_score"] = 4
                v["relevance_reason"] += " (fan 채널 감점)"

        # 점수 내림차순 정렬
        videos_meta.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        top = videos_meta[0] if videos_meta else {}
        console.print(
            f"  [green]✓ GPT 분류 완료 — "
            f"official: {sum(1 for v in videos_meta if v['channel_type']=='official')}, "
            f"media: {sum(1 for v in videos_meta if v['channel_type']=='media')}, "
            f"fan: {sum(1 for v in videos_meta if v['channel_type']=='fan')}[/green]"
        )
        if top:
            console.print(f"  [green]  상위: [{top.get('channel_type','')}] {top['title'][:40]} = {top['relevance_score']}/10[/green]")

        return videos_meta

    except Exception as e:
        console.print(f"  [yellow]⚠ GPT 분류 실패: {e} — 조회수 기준 폴백[/yellow]")
        videos_meta.sort(key=lambda x: x.get("view_count", 0), reverse=True)
        for v in videos_meta:
            v["relevance_score"] = 5
            v["channel_type"] = "unknown"
            v["relevance_reason"] = "폴백"
            v["recommended_scene"] = None
        return videos_meta


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 영상 다운로드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def download_official_videos(
    scored_videos: list[dict],
    assets_dir: Path,
    min_score: int = 4,
    max_count: int = 10,
) -> list[dict]:
    """official/media 채널 영상만 점수 순으로 다운로드."""
    downloaded: list[dict] = []
    duration = config.YTDLP_CLIP_DURATION

    for v in scored_videos:
        if len(downloaded) >= max_count:
            break
        if v.get("relevance_score", 0) < min_score:
            console.print(f"  [dim]  ✗ 다운로드 제외 (점수 미달 {v.get('relevance_score', 0)}/10): {v['title'][:40]}[/dim]")
            continue
        if v.get("channel_type") == "fan" and v.get("relevance_score", 0) < 4:
            console.print(f"  [dim]  ✗ 다운로드 제외 (팬 채널 점수 미달): {v['title'][:40]}[/dim]")
            continue

        idx = len(downloaded) + 1
        output_path = assets_dir / f"pool_video_{idx:02d}.mp4"

        try:
            cmd = [
                "yt-dlp", v["url"],
                "--format", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best[height<=1080]",
                "--merge-output-format", "mp4",
                "--download-sections", f"*0-{duration}",
                "--output", str(output_path),
                "--no-playlist", "--quiet", "--no-warnings",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 10000:
                downloaded.append({
                    "path": str(output_path),
                    "type": "video",
                    "title": v["title"],
                    "channel": v["channel"],
                    "channel_type": v.get("channel_type", "unknown"),
                    "score": v.get("relevance_score", 0),
                    "reason": v.get("relevance_reason", ""),
                    "recommended_scene": v.get("recommended_scene"),
                    "url": v["url"],
                })
                type_icon = {"official": "🏢", "media": "📰"}.get(v.get("channel_type"), "❓")
                console.print(f"  [green]  ✓ {type_icon} [{v.get('relevance_score',0)}/10] {v['channel']}: {v['title'][:45]}[/green]")
            else:
                output_path.unlink(missing_ok=True)
                err_hint = (result.stderr or result.stdout or "")[:150].replace("\n", " ")
                size_hint = ""
                if output_path.exists():
                    try:
                        size_hint = f" (파일크기:{output_path.stat().st_size}B)"
                    except OSError:
                        pass
                console.print(f"  [red]  ✗ 다운로드 실패: {v['title'][:35]} (코드:{result.returncode}{size_hint})[/red]")
                if err_hint:
                    console.print(f"  [dim]    → {err_hint}[/dim]")
        except subprocess.TimeoutExpired:
            output_path.unlink(missing_ok=True)
            console.print(f"  [red]  ✗ 다운로드 실패 (90초 시간초과): {v['title'][:40]}[/red]")
        except FileNotFoundError:
            output_path.unlink(missing_ok=True)
            console.print(f"  [red]  ✗ yt-dlp 또는 ffmpeg 미설치 — pip install yt-dlp, 시스템에 ffmpeg 설치 필요[/red]")
        except Exception as e:
            output_path.unlink(missing_ok=True)
            console.print(f"  [red]  ✗ 다운로드 실패: {v['title'][:40]} ({type(e).__name__}: {e})[/red]")

    console.print(f"  [cyan]영상 {len(downloaded)}개 다운로드 완료[/cyan]")
    if len(downloaded) == 0 and len([v for v in scored_videos if v.get("channel_type") in ("official", "media") and v.get("relevance_score", 0) >= 4]) > 0:
        console.print(f"  [yellow]  ⚠ 영상 0개: yt-dlp/ffmpeg 확인, Streamlit Cloud는 네트워크 제한 있을 수 있음[/yellow]")
    return downloaded


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 이미지 수집 (뉴스 + 검색)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _is_valid_img_url(src: str) -> bool:
    if not src.startswith("http"):
        return False
    has_ext = any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"])
    trusted = any(d in src for d in ["imgnews.pstatic.net", "mimgnews.pstatic.net", "scs-phinf.pstatic.net"])
    return has_ext or trusted


def scrape_naver_article_images(article_url: str) -> list[str]:
    if not article_url:
        return []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
    try:
        resp = requests.get(article_url, headers=headers, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        seen, urls = set(), []
        def _collect(container):
            for img in container.find_all("img"):
                src = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
                pc = " ".join(img.parent.get("class") or [])
                if "source_thumb" in pc or "logo" in pc:
                    continue
                if _is_valid_img_url(src) and src not in seen:
                    seen.add(src)
                    urls.append(src)
        for sel in ["#dic_area", "#newsct_article", ".newsct_article", "article"]:
            body = soup.select_one(sel)
            if body:
                _collect(body)
                break
        for area in soup.select(".image_area, .article_body figure"):
            _collect(area)
        return urls
    except Exception:
        return []


def fetch_article_urls_from_naver(query: str, max_articles: int = 15) -> list[str]:
    import urllib.parse
    from bs4 import BeautifulSoup
    encoded = urllib.parse.quote(query)
    url = f"https://search.naver.com/search.naver?where=news&sort=1&query={encoded}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        urls, seen = [], set()
        for el in soup.find_all(attrs={"data-url": True}):
            u = el.get("data-url", "").strip()
            if u.startswith("http") and u not in seen:
                seen.add(u)
                urls.append(u)
                if len(urls) >= max_articles:
                    break
        return urls
    except Exception:
        return []


def collect_all_images(news_articles: list[dict], search_queries: list[str], assets_dir: Path, max_count: int = 10) -> list[dict]:
    """뉴스 기사 + 네이버 검색에서 이미지 수집 (최대 max_count개)"""
    import re as _re
    headers_dl = {"User-Agent": "Mozilla/5.0"}
    headers_page = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
    pool: list[dict] = []
    seen_urls: set[str] = set()
    img_idx = 0

    # A: 뉴스 기사 이미지
    for article in news_articles:
        if len(pool) >= max_count:
            break
        title = article.get("title", "")
        body = article.get("body", "")
        text = title + body
        ko_chars = len(_re.findall(r'[\uAC00-\uD7A3]', text))
        if len(text) > 0 and ko_chars / max(len(text), 1) < 0.4:
            continue
        for img_url in scrape_naver_article_images(article.get("url", "")):
            if len(pool) >= max_count or img_url in seen_urls:
                continue
            try:
                resp = requests.get(img_url, headers=headers_dl, timeout=10)
                resp.raise_for_status()
                if len(resp.content) < 5000:
                    continue
                img_idx += 1
                path = assets_dir / f"pool_image_{img_idx:02d}.jpg"
                path.write_bytes(resp.content)
                try:
                    img = Image.open(path).convert("RGB")
                    w, h = img.size
                    if w < 100 or h < 100:
                        path.unlink(missing_ok=True)
                        continue
                    img.save(path, "JPEG", quality=90)
                except Exception:
                    path.unlink(missing_ok=True)
                    continue
                seen_urls.add(img_url)
                pool.append({
                    "path": str(path), "type": "image",
                    "title": title, "channel": "", "channel_type": "media",
                    "score": 6, "reason": "뉴스 기사 이미지",
                    "recommended_scene": None, "url": img_url,
                })
            except Exception:
                continue

    # B: 네이버 검색 추가 이미지
    for query in search_queries:
        if len(pool) >= max_count:
            break
        for art_url in fetch_article_urls_from_naver(query, max_articles=10):
            if len(pool) >= max_count:
                break
            try:
                resp = requests.get(art_url, headers=headers_page, timeout=10, allow_redirects=True)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                og = soup.find("meta", property="og:image")
                img_url = og.get("content", "").strip() if og else ""
                if not img_url or not img_url.startswith("http") or img_url in seen_urls:
                    continue
                img_resp = requests.get(img_url, headers=headers_dl, timeout=10)
                img_resp.raise_for_status()
                if len(img_resp.content) < 5000:
                    continue
                img_idx += 1
                path = assets_dir / f"pool_image_{img_idx:02d}.jpg"
                path.write_bytes(img_resp.content)
                try:
                    img = Image.open(path).convert("RGB")
                    if img.size[0] < 100 or img.size[1] < 100:
                        path.unlink(missing_ok=True)
                        continue
                    img.save(path, "JPEG", quality=90)
                except Exception:
                    path.unlink(missing_ok=True)
                    continue
                seen_urls.add(img_url)
                pool.append({
                    "path": str(path), "type": "image",
                    "title": art_url[:60], "channel": "", "channel_type": "media",
                    "score": 5, "reason": "검색 이미지",
                    "recommended_scene": None, "url": img_url,
                })
            except Exception:
                continue

    console.print(f"  [cyan]이미지 {len(pool)}개 수집 완료[/cyan]")
    return pool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI 씬 자동 배치
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def ai_assign_pool_to_scenes(asset_pool: list[dict], scenes: list[dict]) -> dict[int, int]:
    """에셋 풀을 씬에 자동 배치. Returns: {scene_id: pool_index}"""
    if not asset_pool or not scenes:
        return {}

    assignments: dict[int, int] = {}
    used_pool: set[int] = set()

    # 1차: recommended_scene 기반 (영상 우선, 점수 높은 순)
    sorted_pool = sorted(enumerate(asset_pool), key=lambda x: x[1].get("score", 0), reverse=True)
    for pool_idx, asset in sorted_pool:
        rec = asset.get("recommended_scene")
        if rec and isinstance(rec, int) and rec not in assignments and pool_idx not in used_pool:
            assignments[rec] = pool_idx
            used_pool.add(pool_idx)

    # 2차: GPT 텍스트 매칭
    missing = [s for s in scenes if s["scene_id"] not in assignments]
    remaining = [(i, a) for i, a in enumerate(asset_pool) if i not in used_pool]

    if missing and remaining:
        try:
            client = OpenAI(api_key=config.OPENAI_API_KEY)
            scenes_text = "\n".join(f"scene_{s['scene_id']}: {s['description']}" for s in missing)
            pool_text = "\n".join(
                f"A{i}: [{a['type']}] {a['title'][:50]} (score:{a.get('score',0)})"
                for i, a in remaining
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content":
                    f"Match scenes to assets. Prefer video over image when scores are similar.\n\n"
                    f"Scenes:\n{scenes_text}\n\nAssets:\n{pool_text}\n\n"
                    f"Return JSON: {{\"assignments\": {{\"scene_ID\": \"A_IDX\", ...}}}}. Use 'none' if no match."}],
                response_format={"type": "json_object"}, temperature=0.2,
            )
            result = json.loads(resp.choices[0].message.content)
            for sk, ak in result.get("assignments", {}).items():
                if ak == "none":
                    continue
                try:
                    sid = int(str(sk).split("_")[-1]) if "_" in str(sk) else int(sk)
                    aidx = int(str(ak).split("_")[-1]) if "_" in str(ak) else int(ak)
                    if sid not in assignments and aidx not in used_pool:
                        assignments[sid] = aidx
                        used_pool.add(aidx)
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            console.print(f"  [yellow]⚠ AI 배치 실패: {e}[/yellow]")

    console.print(f"  [green]✓ AI 배치: {len(assignments)}/{len(scenes)}개 씬[/green]")
    return assignments


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 이미지 후처리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def crop_to_portrait(image_path: Path):
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        tr = 9 / 16
        cr = w / h
        if cr > tr:
            nw = int(h * tr)
            left = (w - nw) // 2
            img = img.crop((left, 0, left + nw, h))
        elif abs(cr - tr) > 0.05:
            nh = int(w / tr)
            top = (h - nh) // 2
            img = img.crop((0, top, w, top + nh))
        img = img.resize(config.VIDEO_RESOLUTION, Image.LANCZOS)
        img.save(image_path, "JPEG", quality=90)
    except Exception as e:
        console.print(f"    [yellow]크롭 오류: {e}[/yellow]")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 검색어 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_search_queries(topic: dict, scenes: list[dict]) -> list[str]:
    import re
    queries: list[str] = []
    for s in scenes:
        q = s.get("youtube_query_ko", "")
        if q and q not in queries:
            queries.append(q)
    headline_ko = topic.get("headline_ko", "")
    words = re.sub(r'[!?,.\\[\]()「」『』【】…~·]', ' ', headline_ko).split()
    if len(words) >= 3:
        q = ' '.join(words[:3])
        if q not in queries:
            queries.append(q)
    if len(words) >= 2:
        q = ' '.join(words[:2])
        if q not in queries:
            queries.append(q)
    for s in scenes:
        q = s.get("youtube_query", "")
        if q and q not in queries:
            queries.append(q)
    return queries


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run(output_dir: Path, assets_plan_path: Path) -> Path:
    """에셋 수집 — 3층 필터 + 영상10/이미지10 분리 수집"""
    console.print("\n[bold blue]━━ [3/6] 에셋 수집 (3층 필터 · 영상10 + 이미지10) ━━[/bold blue]")

    plan = json.loads(assets_plan_path.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    # 토픽 로드
    topics_path = output_dir / "trending_topics.json"
    state_path = output_dir / "pipeline_state.json"
    topic = {}
    try:
        if topics_path.exists():
            topics = json.loads(topics_path.read_text(encoding="utf-8"))
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                idx = state.get("results", {}).get("selected_topic_index", 0)
                topic = topics[idx] if 0 <= idx < len(topics) else topics[0]
            else:
                topic = max(topics, key=lambda t: t.get("virality_score", 0))
    except Exception:
        pass

    # 이전 풀 정리
    for old in assets_dir.glob("pool_*"):
        old.unlink(missing_ok=True)

    queries = build_search_queries(topic, scenes)
    console.print(f"  [dim]검색어: {queries[:6]}[/dim]")

    import re as _re
    headline_ko = topic.get("headline_ko", "")
    words = _re.sub(r'[!?,.\[\]()「」『』【】…~·]', ' ', headline_ko).split()
    image_queries = []
    if len(words) >= 3:
        image_queries.append(' '.join(words[:3]))
    if len(words) >= 2:
        q2 = ' '.join(words[:2])
        if q2 not in image_queries:
            image_queries.append(q2)

    # ═══ STEP 1: YouTube 메타데이터 + 1층 키워드 필터 ═══
    console.print("\n  [bold]📺 YouTube 검색 + 키워드 필터...[/bold]")
    video_metas = search_youtube_metadata(queries, max_per_query=5)

    # ═══ STEP 2: GPT 채널 분류 + 적합성 (2층 필터) ═══
    if video_metas:
        console.print("\n  [bold]🤖 GPT 채널 분류 + 적합성 판단...[/bold]")
        video_metas = score_and_classify_videos(video_metas, topic, scenes)

    # ═══ STEP 3: official/media만 다운로드 (최대 10개) ═══
    video_pool = []
    if video_metas:
        candidates = [v for v in video_metas if v.get("channel_type") in ("official", "media") and v.get("relevance_score", 0) >= 4]
        console.print(f"\n  [bold]⬇️ 공식/미디어 영상 다운로드 (최대 {config.ASSET_VIDEO_TARGET}개)...[/bold]")
        console.print(f"  [dim]  다운로드 대상: {len(candidates)}개 (official+media, 점수≥4)[/dim]")
        video_pool = download_official_videos(video_metas, assets_dir, min_score=4, max_count=config.ASSET_VIDEO_TARGET)

    # ═══ STEP 4: 이미지 수집 (최대 10개) ═══
    console.print(f"\n  [bold]📷 이미지 수집 (최대 {config.ASSET_IMAGE_TARGET}개)...[/bold]")
    news_articles = []
    news_path = output_dir / "news_articles.json"
    if news_path.exists():
        try:
            news_articles = json.loads(news_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    image_pool = collect_all_images(news_articles, image_queries, assets_dir, max_count=config.ASSET_IMAGE_TARGET)

    # ═══ 이미지 크롭 ═══
    for asset in image_pool:
        crop_to_portrait(Path(asset["path"]))

    # ═══ 전체 풀 합치기 ═══
    asset_pool = video_pool + image_pool

    # ═══ AI 씬 자동 배치 ═══
    console.print("\n  [bold]🎯 AI 씬 자동 배치...[/bold]")
    assignments = ai_assign_pool_to_scenes(asset_pool, scenes)

    # ═══ 씬별 파일 복사 ═══
    import shutil
    for scene_id, pool_idx in assignments.items():
        if 0 <= pool_idx < len(asset_pool):
            src = Path(asset_pool[pool_idx]["path"])
            dest = assets_dir / f"scene_{scene_id:02d}{src.suffix}"
            if src.exists():
                shutil.copy2(src, dest)

    # ═══ 결과 저장 ═══
    pool_data = {
        "pool": asset_pool,
        "assignments": {str(k): v for k, v in assignments.items()},
        "scenes": scenes,
    }
    pool_path = output_dir / "asset_pool.json"
    pool_path.write_text(json.dumps(pool_data, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"\n  [green]✓ 에셋 풀 총 {len(asset_pool)}개[/green]")
    console.print(f"  [green]  🎬 영상: {len(video_pool)}개 (공식/미디어만)[/green]")
    console.print(f"  [green]  📷 이미지: {len(image_pool)}개[/green]")
    console.print(f"  [green]  🎯 AI 배치: {len(assignments)}/{len(scenes)}개 씬[/green]")

    return assets_dir


if __name__ == "__main__":
    output_dir = config.get_today_output_dir()
    assets_plan_path = output_dir / "assets_plan.json"
    if not assets_plan_path.exists():
        console.print("[red]assets_plan.json이 없습니다.[/red]")
    else:
        run(output_dir, assets_plan_path)
