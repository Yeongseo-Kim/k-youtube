"""
[모듈 3] 에셋 수집

흐름:
  1. 네이버 뉴스 기사에서 이미지 전부 크롤링 → 이미지 풀 생성
  2. GPT-4o Vision이 씬 설명 보고 배치 (중복 없이)
  3. 빈 씬만 yt-dlp로 짧은 한국어 키워드 검색 (e.g. "초아 쌍둥이")
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


# ── 1. 네이버 뉴스 이미지 크롤링 ────────────────────────────

def _is_valid_img_url(src: str) -> bool:
    """이미지 URL 유효성 체크 — 확장자 또는 신뢰 도메인 기반"""
    if not src.startswith("http"):
        return False
    has_ext = any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"])
    trusted_domain = any(d in src for d in ["imgnews.pstatic.net", "mimgnews.pstatic.net", "scs-phinf.pstatic.net"])
    return has_ext or trusted_domain


def scrape_naver_article_images(article_url: str) -> list[str]:
    """네이버 뉴스 기사 본문 + 관련 썸네일에서 이미지 URL 추출"""
    if not article_url:
        return []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    try:
        resp = requests.get(article_url, headers=headers, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        seen: set[str] = set()
        urls: list[str] = []

        def _collect_imgs(container):
            for img in container.find_all("img"):
                src = (
                    img.get("data-src")
                    or img.get("data-lazy-src")
                    or img.get("src")
                    or ""
                )
                # 로고/아이콘 제외 (comp_feed_source_thumb 클래스)
                parent_class = " ".join(img.parent.get("class") or [])
                if "source_thumb" in parent_class or "logo" in parent_class:
                    continue
                if _is_valid_img_url(src) and src not in seen:
                    seen.add(src)
                    urls.append(src)

        # ① 본문 영역 (대표 이미지)
        for selector in ["#dic_area", "#newsct_article", ".newsct_article", "article"]:
            body = soup.select_one(selector)
            if body:
                _collect_imgs(body)
                break

        # ② .image_area / figure 추가 탐색
        for area in soup.select(".image_area, .article_body figure"):
            _collect_imgs(area)

        console.print(f"    [dim]이미지 URL 수집: {len(urls)}개[/dim]")
        return urls

    except Exception as e:
        console.print(f"    [yellow]⚠ 기사 이미지 크롤링 실패: {e}[/yellow]")
    return []


def collect_all_news_images(news_articles: list[dict], tmp_dir: Path) -> list[dict]:
    """모든 뉴스 기사 이미지를 임시 폴더에 다운로드 → [{path, article_title, url}]"""
    import re as _re
    headers = {"User-Agent": "Mozilla/5.0"}
    pool = []

    for article in news_articles:
        # 한국어 비율 40% 미만 기사 건너뛰기 (영문 기사 이미지 차단)
        title = article.get("title", "")
        body = article.get("body", "")
        text = title + body
        korean_chars = len(_re.findall(r'[\uAC00-\uD7A3]', text))
        if len(text) > 0 and korean_chars / len(text) < 0.4:
            console.print(f"  [dim]기사 {article.get('index')}: 영문 기사 건너뜀[/dim]")
            continue
        img_urls = scrape_naver_article_images(article.get("url", ""))
        console.print(f"  [dim]기사 {article.get('index')}: {len(img_urls)}개 이미지 발견[/dim]")

        for idx, img_url in enumerate(img_urls):
            try:
                resp = requests.get(img_url, headers=headers, timeout=10)
                resp.raise_for_status()
                if len(resp.content) < 5000:   # 아이콘/광고 제외
                    continue

                tmp_path = tmp_dir / f"article{article.get('index', 0)}_img{idx}.jpg"
                tmp_path.write_bytes(resp.content)

                # PIL로 열 수 있는지 검증
                try:
                    img = Image.open(tmp_path).convert("RGB")
                    w, h = img.size
                    if w < 100 or h < 100:   # 너무 작은 이미지 제외
                        tmp_path.unlink(missing_ok=True)
                        continue
                    img.save(tmp_path, "JPEG", quality=90)
                except Exception:
                    tmp_path.unlink(missing_ok=True)
                    continue

                pool.append({
                    "path": tmp_path,
                    "url": img_url,
                    "article_title": article.get("title", ""),
                })
            except Exception:
                continue

    console.print(f"  [cyan]총 {len(pool)}개 뉴스 이미지 수집 완료[/cyan]")
    return pool


def fetch_article_urls_from_naver(query: str, max_articles: int = 15) -> list[str]:
    """네이버 뉴스 검색 결과에서 data-url 속성으로 기사 URL 수집"""
    import urllib.parse
    from bs4 import BeautifulSoup

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://search.naver.com/search.naver?where=news&sort=1&query={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        urls: list[str] = []
        seen: set[str] = set()
        # 네이버 검색은 JS 렌더링 → a href 대신 data-url 속성에 원본 URL
        for el in soup.find_all(attrs={"data-url": True}):
            url = el.get("data-url", "").strip()
            if url.startswith("http") and url not in seen:
                seen.add(url)
                urls.append(url)
                if len(urls) >= max_articles:
                    break

        console.print(f"  [dim]네이버 검색 '{query}': 기사 {len(urls)}개 URL 수집[/dim]")
        return urls
    except Exception as e:
        console.print(f"  [yellow]⚠ 네이버 검색 URL 수집 실패: {e}[/yellow]")
        return []


def collect_images_from_search(query: str, tmp_dir: Path, max_articles: int = 15) -> list[dict]:
    """네이버 검색 결과 기사들에서 og:image 대표 이미지 크롤링 → [{path, url, article_title}]"""
    article_urls = fetch_article_urls_from_naver(query, max_articles=max_articles)
    if not article_urls:
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    dl_headers = {"User-Agent": "Mozilla/5.0"}
    pool: list[dict] = []

    for art_idx, article_url in enumerate(article_urls):
        try:
            resp = requests.get(article_url, headers=headers, timeout=10, allow_redirects=True)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            # og:image 우선 (언론사 대표 이미지)
            og = soup.find("meta", property="og:image")
            img_url = og.get("content", "").strip() if og else ""

            if not img_url or not img_url.startswith("http"):
                continue

            img_resp = requests.get(img_url, headers=dl_headers, timeout=10)
            img_resp.raise_for_status()
            if len(img_resp.content) < 5000:
                continue

            tmp_path = tmp_dir / f"search{art_idx}.jpg"
            tmp_path.write_bytes(img_resp.content)

            try:
                img = Image.open(tmp_path).convert("RGB")
                w, h = img.size
                if w < 100 or h < 100:
                    tmp_path.unlink(missing_ok=True)
                    continue
                img.save(tmp_path, "JPEG", quality=90)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                continue

            pool.append({"path": tmp_path, "url": img_url, "article_title": article_url})
        except Exception:
            continue

    console.print(f"  [cyan]검색 기반 이미지: {len(pool)}개 수집[/cyan]")
    return pool


# ── 2. GPT-4o Vision 씬 배치 ─────────────────────────────────

def ai_assign_images(image_pool: list[dict], scenes: list[dict]) -> dict[int, Path]:
    """
    GPT-4o Vision으로 이미지 풀을 씬에 배치.
    Returns: {scene_id: image_path}  (배치된 씬만 포함)
    """
    if not image_pool:
        return {}

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    scenes_text = "\n".join(
        f"scene_{s['scene_id']}: {s['description']}" for s in scenes
    )

    # 메시지 구성 — 이미지들 + 지시문
    content = [{
        "type": "text",
        "text": (
            f"You have {len(image_pool)} images (Image_1 ~ Image_{len(image_pool)}) "
            f"and {len(scenes)} scenes below.\n\n"
            f"Scenes:\n{scenes_text}\n\n"
            "Assign each image to the most relevant scene. "
            "Each scene can receive at most ONE image. "
            "If an image is not relevant to any scene, assign 'none'.\n"
            "Return ONLY valid JSON like: "
            "{\"assignments\": {\"Image_1\": \"scene_2\", \"Image_2\": \"none\", ...}}"
        ),
    }]

    for i, img_info in enumerate(image_pool, 1):
        try:
            with open(img_info["path"], "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
            })
            content.append({"type": "text", "text": f"Image_{i}"})
        except Exception:
            continue

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        result = json.loads(resp.choices[0].message.content)
        assignments = result.get("assignments", {})

        assigned: dict[int, Path] = {}
        used_img_indices: set[int] = set()
        for img_key, scene_key in assignments.items():
            if scene_key == "none":
                continue
            try:
                img_idx = int(img_key.split("_")[1]) - 1
                scene_id = int(scene_key.split("_")[1])
                # 씬당 1개 + 이미지당 1회만 사용 (중복 방지)
                if scene_id not in assigned and img_idx not in used_img_indices:
                    assigned[scene_id] = image_pool[img_idx]["path"]
                    used_img_indices.add(img_idx)
            except (ValueError, IndexError):
                continue

        console.print(f"  [green]✓ AI 이미지 배치: {len(assigned)}개 씬 매칭[/green]")
        return assigned

    except Exception as e:
        console.print(f"  [yellow]⚠ AI 배치 실패: {e}[/yellow]")
        return {}


# ── 3. yt-dlp 유튜브 검색 (짧은 한국어 키워드) ──────────────

def get_topic_keywords(output_dir: Path) -> list[str]:
    """trending_topics.json에서 짧은 한국어 YouTube 검색 키워드 추출"""
    import re
    state_path = output_dir / "pipeline_state.json"
    topics_path = output_dir / "trending_topics.json"

    keywords = []
    try:
        # 선택된 토픽 가져오기
        if state_path.exists() and topics_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            topics = json.loads(topics_path.read_text(encoding="utf-8"))
            idx = state.get("results", {}).get("selected_topic_index", 0)
            topic = topics[idx] if 0 <= idx < len(topics) else topics[0]
        elif topics_path.exists():
            topics = json.loads(topics_path.read_text(encoding="utf-8"))
            topic = max(topics, key=lambda t: t.get("virality_score", 0))
        else:
            return []

        headline_ko = topic.get("headline_ko", "")
        words = re.sub(r'[!?,.\[\]()「」『』【】…~·]', ' ', headline_ko).split()

        # 2단어씩 슬라이딩 (e.g. "크레용팝 초아", "초아 쌍둥이")
        for i in range(len(words) - 1):
            kw = f"{words[i]} {words[i+1]}"
            if kw not in keywords:
                keywords.append(kw)
        # 단독 단어도 추가 (이름 등)
        for w in words:
            if len(w) >= 2 and w not in keywords:
                keywords.append(w)

    except Exception as e:
        console.print(f"  [yellow]⚠ 키워드 추출 실패: {e}[/yellow]")

    return keywords


def download_youtube_clip(query: str, output_path: Path, duration: int = None) -> bool:
    """yt-dlp로 유튜브 검색 → 클립 다운로드"""
    duration = duration or config.YTDLP_CLIP_DURATION
    try:
        cmd = [
            "yt-dlp",
            f"ytsearch1:{query}",
            "--format", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best[height<=1080]",
            "--merge-output-format", "mp4",
            "--download-sections", f"*0-{duration}",
            "--output", str(output_path),
            "--no-playlist",
            "--quiet",
            "--no-warnings",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            console.print(f"    [green]✓ yt-dlp 성공: {query}[/green]")
            return True
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ── 이미지 후처리 ─────────────────────────────────────────────

def crop_to_portrait(image_path: Path):
    """이미지를 9:16 비율로 center crop"""
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        target_ratio = 9 / 16
        current_ratio = w / h

        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        elif abs(current_ratio - target_ratio) > 0.05:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        img = img.resize(config.VIDEO_RESOLUTION, Image.LANCZOS)
        img.save(image_path, "JPEG", quality=90)
    except Exception as e:
        console.print(f"    [yellow]크롭 오류: {e}[/yellow]")


# ── 메인 실행 ─────────────────────────────────────────────────

def run(output_dir: Path, assets_plan_path: Path) -> Path:
    """에셋 수집 모듈 실행"""
    console.print("\n[bold blue]━━ [3/6] 에셋 수집 시작 ━━[/bold blue]")

    plan = json.loads(assets_plan_path.read_text(encoding="utf-8"))
    scenes = plan.get("scenes", [])
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    # 이전 실행에서 남은 mp4 정리 (jpg로 대체됐을 수 있으므로)
    import shutil as _shutil
    for mp4 in assets_dir.glob("scene_*.mp4"):
        jpg = mp4.with_suffix(".jpg")
        if jpg.exists():
            mp4.unlink()
            console.print(f"  [dim]이전 mp4 제거: {mp4.name} (jpg 있음)[/dim]")

    # 뉴스 기사 로드
    news_articles_path = output_dir / "news_articles.json"
    news_articles = []
    if news_articles_path.exists():
        try:
            news_articles = json.loads(news_articles_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # ── STEP 1: 뉴스 기사 이미지 수집 ──
    # 1-A: 기존 news_articles (최대 3개) + 1-B: 검색 결과 전체 기사 이미지
    assigned: dict[int, Path] = {}
    console.print("\n  [bold]📰 뉴스 기사 이미지 수집 중...[/bold]")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1-A: 기존 news_articles 이미지
        image_pool = collect_all_news_images(news_articles, tmp_path) if news_articles else []

        # 1-B: 토픽 키워드로 네이버 추가 검색 → 더 많은 기사 이미지
        try:
            import re as _re
            topics_path = output_dir / "trending_topics.json"
            state_path = output_dir / "pipeline_state.json"
            if topics_path.exists():
                topics = json.loads(topics_path.read_text(encoding="utf-8"))
                if state_path.exists():
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    idx = state.get("results", {}).get("selected_topic_index", 0)
                    topic = topics[idx] if 0 <= idx < len(topics) else topics[0]
                else:
                    topic = max(topics, key=lambda t: t.get("virality_score", 0))

                headline_ko = topic.get("headline_ko", "")
                summary_ko = topic.get("summary_ko", "")
                words = _re.sub(r'[!?,.[\]()「」『』【】…~·]', ' ', headline_ko).split()

                # 검색 쿼리 변형: 첫 3단어 / 첫 2단어 / summary_ko 첫 3단어
                queries: list[str] = []
                if len(words) >= 3:
                    queries.append(' '.join(words[:3]))
                if len(words) >= 2:
                    q2 = ' '.join(words[:2])
                    if q2 not in queries:
                        queries.append(q2)
                if summary_ko:
                    sw = _re.sub(r'[!?,.[\]()「」『』【】…~·]', ' ', summary_ko).split()
                    qs = ' '.join(sw[:3])
                    if qs and qs not in queries:
                        queries.append(qs)

                existing_urls = {a.get("url", "") for a in news_articles}
                collected_img_urls: set[str] = {p["url"] for p in image_pool}

                for q in queries:
                    console.print(f"  [dim]검색 키워드: '{q}'[/dim]")
                    extra_pool = collect_images_from_search(q, tmp_path, max_articles=30)
                    for p in extra_pool:
                        if p["article_title"] not in existing_urls and p["url"] not in collected_img_urls:
                            image_pool.append(p)
                            collected_img_urls.add(p["url"])
        except Exception as e:
            console.print(f"  [yellow]⚠ 추가 이미지 검색 실패: {e}[/yellow]")

        console.print(f"  [cyan]최종 이미지 풀: {len(image_pool)}개[/cyan]")

        if image_pool:
            # ── STEP 2: AI 씬 배치 ──
            console.print("\n  [bold]🤖 GPT-4o Vision 씬 배치 중...[/bold]")
            assigned = ai_assign_images(image_pool, scenes)

            # 배치된 이미지 → assets/ 로 복사 + 크롭
            import shutil
            for scene_id, src_path in assigned.items():
                dest = assets_dir / f"scene_{scene_id:02d}.jpg"
                shutil.copy2(src_path, dest)
                crop_to_portrait(dest)


    # ── STEP 3: 빈 씬만 yt-dlp 한국어 키워드 검색 ──
    # 이미 파일이 있는 씬은 assigned에 추가 (이전 실행 결과 재사용)
    for s in scenes:
        sid = s["scene_id"]
        if sid not in assigned:
            for ext in ["jpg", "jpeg", "png", "mp4"]:
                existing = assets_dir / f"scene_{sid:02d}.{ext}"
                if existing.exists() and existing.stat().st_size > 10000:
                    assigned[sid] = existing
                    console.print(f"  [dim]씬 {sid}: 기존 파일 재사용 ({existing.name})[/dim]")
                    break

    missing_scenes = [s for s in scenes if s["scene_id"] not in assigned]
    if missing_scenes:
        console.print(f"\n  [bold]🎬 빈 씬 {len(missing_scenes)}개 — YouTube 검색 시도[/bold]")
        topic_keywords = get_topic_keywords(output_dir)
        console.print(f"  [dim]키워드: {topic_keywords}[/dim]")

        used_keywords: set[str] = set()
        kw_iter = iter(topic_keywords)

        for scene in missing_scenes:
            sid = scene["scene_id"]
            video_path = assets_dir / f"scene_{sid:02d}.mp4"
            found = False

            # 씬별로 사용하지 않은 키워드 순서대로 시도
            for kw in topic_keywords:
                if kw in used_keywords:
                    continue
                if download_youtube_clip(kw, video_path):
                    assigned[sid] = video_path
                    used_keywords.add(kw)
                    found = True
                    break

            if not found:
                console.print(f"    [red]✗ 씬 {sid}: 에셋 없음 — 수동 추가 필요[/red]")

    collected = len(assigned)
    console.print(f"\n  [green]✓ {collected}/{len(scenes)}개 에셋 수집 완료 → {assets_dir}[/green]")
    return assets_dir


if __name__ == "__main__":
    output_dir = config.get_today_output_dir()
    assets_plan_path = output_dir / "assets_plan.json"
    if not assets_plan_path.exists():
        console.print("[red]assets_plan.json이 없습니다.[/red]")
    else:
        run(output_dir, assets_plan_path)
