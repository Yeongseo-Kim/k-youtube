"""
[모듈 2] 대본/프롬프트 생성 — GPT-4o 기반

트렌딩 토픽을 입력받아:
1. script.txt — 150~160단어 영문 내레이션 대본 (Hook→Context→Detail→CTA)
2. assets_plan.json — 씬별 yt-dlp 검색어 + 이미지 폴백 키워드
3. metadata.json — 유튜브 제목, 설명(#Shorts), 태그
를 동시에 생성한다.
"""

import json
from pathlib import Path
from openai import OpenAI
from rich.console import Console

import config

import urllib.parse
from bs4 import BeautifulSoup

console = Console()


def fetch_korean_news_context(query: str, max_articles: int = 3) -> tuple[str, list[dict]]:
    """네이버 뉴스 검색을 통해 실제 기사 본문 전문을 추출한다.

    Returns:
        (combined_str, articles_list)
        - combined_str: GPT 프롬프트에 넣을 통합 텍스트
        - articles_list: [{index, title, body, url}, ...] 개별 기사 목록
    """
    if not query:
        return "검색어가 없습니다.", []

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://search.naver.com/search.naver?where=news&sort=1&query={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        import requests
        import re
        resp = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # '네이버뉴스' 링크(n.news.naver.com)만 골라내기 — 모든 <a> 태그에서 href 검색
        naver_news_links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            if "n.news.naver.com" in href and href not in naver_news_links:
                naver_news_links.append(href)

        articles = []  # [{index, title, body, url}]
        for idx, link in enumerate(naver_news_links[:max_articles]):
            try:
                article_resp = requests.get(link, headers=headers, timeout=5)
                article_soup = BeautifulSoup(article_resp.text, "html.parser")

                title_elem = article_soup.select_one("#title_area")
                body_elem = (
                    article_soup.select_one("#dic_area")
                    or article_soup.select_one("#newsct_article")
                    or article_soup.select_one(".newsct_article")
                    or article_soup.select_one("article")
                )

                if title_elem and body_elem:
                    title = title_elem.get_text(separator=" ", strip=True)
                    body_text = body_elem.get_text(separator="\n", strip=True)
                    body_text = re.sub(r'\n+', ' ', body_text)[:1200]

                    # 한글 비율 체크 — 영어 기사 제외
                    korean_chars = len(re.findall(r'[\uAC00-\uD7A3]', title + body_text))
                    total_chars = max(len(title + body_text), 1)
                    if len(body_text) > 100 and korean_chars / total_chars >= 0.4:
                        articles.append({"index": idx + 1, "title": title, "body": body_text, "url": link})
            except Exception as e:
                console.print(f"[yellow]⚠ 네이버 기사 URL({link}) 스크래핑 실패: {e}[/yellow]")

        if articles:
            combined = "\n\n".join(
                f"[기사 {a['index']}]\n제목: {a['title']}\n내용(전문 요약):\n{a['body']}"
                for a in articles
            )
            return combined, articles

        # 폴백: 스니펫만 제공
        titles = (
            soup.select(".news_tit")
            or soup.select("a.news_tit")
            or soup.select(".title_link")
        )
        dscs = (
            soup.select(".api_txt_lines.dsc_txt_wrap")
            or soup.select(".dsc_wrap")
            or soup.select(".api_txt_lines")
        )
        fallback_articles = []
        for idx, (t, d) in enumerate(zip(titles[:max_articles], dscs[:max_articles])):
            fallback_articles.append({
                "index": idx + 1,
                "title": t.get_text(strip=True),
                "body": d.get_text(strip=True),
                "url": "",
            })
        if fallback_articles:
            combined = "\n\n".join(
                f"[기사 {a['index']}]\n제목: {a['title']}\n내용: {a['body']}"
                for a in fallback_articles
            )
            return combined, fallback_articles

        return "관련 뉴스를 찾을 수 없습니다.", []
    except Exception as e:
        console.print(f"[yellow]⚠ 네이버 검색 오류: {e}[/yellow]")
        return f"뉴스 검색 실패: {e}", []


def fetch_web_snippets_context(query: str, max_articles: int = 4) -> str:
    """DuckDuckGo HTML 검색 결과의 URL을 순회하며 각 페이지의 본문 전문을 수집한다.
    
    스니펫 대신 실제 페이지에 접속해 본문을 추출하므로, 잡지·공식 보도자료·SNS 링크 등에서
    충분한 팩트를 가져올 수 있다.
    """
    import re
    if not query:
        return ""

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # ── 차단할 도메인 (SNS 로그인 장벽, 광고 등)
    BLOCKED_DOMAINS = {
        "instagram.com", "twitter.com", "x.com", "facebook.com",
        "tiktok.com", "youtube.com", "youtu.be",
        "duckduckgo.com", "google.com", "naver.com",
    }

    try:
        import requests
        resp = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # DuckDuckGo 결과에서 실제 외부 URL 추출 (//duckduckgo.com/l/?uddg=... 우회)
        raw_links = soup.select(".result__url")
        result_links = soup.select("a.result__a")
        
        urls = []
        for a in result_links:
            href = a.get("href", "")
            # DuckDuckGo redirect URL에서 실제 URL 파싱
            if "uddg=" in href:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                real = parsed.get("uddg", [""])[0]
                if real:
                    href = urllib.parse.unquote(real)
            if href.startswith("http"):
                domain = urllib.parse.urlparse(href).netloc.replace("www.", "")
                if not any(blocked in domain for blocked in BLOCKED_DOMAINS):
                    if href not in urls:
                        urls.append(href)

        console.print(f"  [dim]🌐 웹 전문 수집 대상 URL {len(urls)}개[/dim]")

        # ── 각 URL 방문해서 본문 추출
        articles = []
        for url in urls[:max_articles]:
            try:
                ar = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
                ar.raise_for_status()
                asoup = BeautifulSoup(ar.text, "html.parser")

                # 노이즈 제거
                for tag in asoup.select("script, style, nav, footer, header, aside, .ad, .advertisement, .popup"):
                    tag.decompose()

                # 본문 후보 선정 (넓->좁 순서)
                body_elem = (
                    asoup.select_one("article")
                    or asoup.select_one("main")
                    or asoup.select_one(".article-body, .article_body, .content, .post-content, .entry-content")
                    or asoup.select_one("#content, #article, #main")
                    or asoup.select_one("body")
                )

                if not body_elem:
                    continue

                raw_text = body_elem.get_text(separator="\n", strip=True)
                # 빈 줄 압축
                cleaned = re.sub(r'\n{3,}', '\n\n', raw_text).strip()[:2500]

                if len(cleaned) < 100:
                    continue

                domain_label = urllib.parse.urlparse(url).netloc.replace("www.", "")
                articles.append(f"[출처: {domain_label}]\n{cleaned}")
                console.print(f"  [green]  ✓ 전문 수집: {domain_label} ({len(cleaned)}자)[/green]")

            except Exception as e:
                console.print(f"  [yellow]  ⚠ URL 접근 실패 ({url[:60]}...): {e}[/yellow]")

        if articles:
            return "\n\n".join(f"[웹 글 전문 {i+1}]\n{a}" for i, a in enumerate(articles))

        return ""
    except Exception as e:
        console.print(f"[yellow]⚠ 덕덕고 검색 오류: {e}[/yellow]")
        return ""


def generate_script_and_plan(topic: dict, feedback: str = "") -> dict:
    """GPT-4o로 대본 + 에셋 플랜 + 메타데이터를 한 번에 생성"""
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    min_words, max_words = config.SCRIPT_WORD_COUNT
    
    # 한국어 기사 팩트 수집 — 검색어 정제 후 부족하면 키워드로 추가 검색
    import re as _re

    def _clean_query(raw: str) -> str:
        q = _re.sub(r'[!?,.\[\]()「」『』【】…~·]', ' ', raw)
        return ' '.join(q.split()[:3])

    primary_query = _clean_query(
        topic.get('headline_ko') or topic.get('headline') or ""
    )
    news_context, news_articles = fetch_korean_news_context(primary_query, max_articles=3)

    # 기사가 3개 미만이면 한국어 필드에서 추출한 쿼리로 추가 수집
    if len(news_articles) < 3:
        # headline_ko 첫 2단어를 앵커(주인공/주제)로 고정
        primary_words = _re.sub(r'[!?,.\[\]()「」『』【】…~·]', ' ', topic.get('headline_ko', '')).split()
        anchor = ' '.join(primary_words[:2]) if len(primary_words) >= 2 else primary_words[0] if primary_words else ''

        # summary_ko / why_viral_ko 에서 앵커와 함께 쓸 추가 단어 수집
        extra_words = []
        for src in [topic.get('summary_ko', ''), topic.get('why_viral_ko', '')]:
            if not src:
                continue
            words = _re.sub(r'[!?,.\[\]()「」『』【】…~·]', ' ', src).split()
            extra_words.extend(words)

        # 앵커 + 추가단어 조합으로 후보 생성 (항상 주제가 포함됨)
        ko_candidates = []
        for w in extra_words:
            if len(w) < 2:
                continue
            candidate = f"{anchor} {w}"
            if candidate not in ko_candidates and candidate != primary_query:
                ko_candidates.append(candidate)

        existing_urls = {a['url'] for a in news_articles}
        for candidate in ko_candidates:
            if len(news_articles) >= 3:
                break
            _, extra_articles = fetch_korean_news_context(candidate, max_articles=3)
            for a in extra_articles:
                if a['url'] not in existing_urls and len(news_articles) < 3:
                    a['index'] = len(news_articles) + 1
                    news_articles.append(a)
                    existing_urls.add(a['url'])

    # 통합본 재구성
    if news_articles:
        news_context = "\n\n".join(
            f"[기사 {a['index']}]\n제목: {a['title']}\n내용(전문 요약):\n{a['body']}"
            for a in news_articles
        )

    # + 추가: 웹/소셜 글 (잡지, 인스타 PR 등) 스니펫 수집
    web_context = fetch_web_snippets_context(primary_query, max_articles=6)
    if web_context:
        news_context += f"\n\n{web_context}"

    prompt = f"""You are a viral YouTube Shorts creator who has 5M+ subscribers covering K-pop and K-drama.
Your audience is passionate international K-fans aged 15-28. They're deeply invested in idol culture.

TOPIC:
Headline: {topic.get('headline', '')}
Summary: {topic.get('summary', '')}
Keywords: {', '.join(topic.get('keywords', []))}
Why it's viral: {topic.get('why_viral', '')}

════════════════════════════════════════
REAL KOREAN NEWS & WEB CONTEXT (Must base facts on this):
════════════════════════════════════════
{news_context}

════════════════════════════════════════
CONTENT GUIDELINES — READ CAREFULLY:
════════════════════════════════════════

✅ TONE: You are a friendly, genuine K-pop fan sharing news with other fans.
   Speak naturally and conversationally, but with ZERO FILLER. Every single sentence MUST contain a hard fact.
   Show brief, natural empathy (e.g., "She overcame cervical cancer, which makes this even more amazing!").
   Do NOT sound like a rigid news reporter. Keep it heartfelt but purely informational.
   [CTA]: End exactly with this or a close variation: "Follow and leave a supportive comment!"

✅ CONTENT: Base everything STRICTLY on the "REAL KOREAN NEWS & WEB CONTEXT":
   - Weave the facts together into a single, logical, and chronological story.
   - FATAL ERROR if you include generic filler sentences like "Fans are taking to social media to celebrate." or "The K-pop community is sending love."
   - DO NOT include ANY sentence that does not contain a specific proper noun, date, number, or direct quote from the news.
   - If the news says fans reacted, quote EXACTLY what the reaction was. Do not just say "fans reacted warmly."

 ❌ DO NOT:
    - Include any generic, empty filler sentences that add zero new information.
    - Hallucinate, invent, or create fake rumors. Assume nothing outside the provided news text.

════════════════════════════════════════
════════════════════════════════════════
OUTPUT FORMAT (JSON):
════════════════════════════════════════

1. "script": Exactly {min_words}-{max_words} words (MINIMUM {min_words} words — never shorter). Structure:
   [HOOK - 1-2 sentences] MUST BE INCREDIBLY STRONG, DRAMATIC, OR EMOTIONAL. Grab the viewer instantly with a shocking, surprising, or heartwarming fact. Do NOT just state the news; make it a "you won't believe this" moment.
   [DETAIL 1 - 2-3 sentences] Next hard fact/chronological event from the news. NO FILLER.
   [DETAIL 2 - 2-3 sentences] Additional details (quotes, numbers, specific context) from the news. NO FILLER.
   [CTA - 1 sentence] "Follow and leave a supportive comment!"


2. "title_options": Array of 3 YouTube title candidates.
   SHORTS RULE: MAX 55 CHARACTERS each (excluding hashtags at the end).
   CRITICAL: Make ANYONE click — even people who have NEVER heard of K-pop.
   Primary keyword (Korean/K-pop/K-drama) MUST be within FIRST 35 characters.
   Style guide — combine SPECIFIC FACT + SHOCK/INTRIGUE like these examples:
     ✅ "Korean pop star SECRET pregnancy 🤫 #Shorts"
     ✅ "K-pop star hid TWIN babies 9 months 😱 #Shorts"
     ✅ "She was a K-pop idol—then THIS happened 😭 #Shorts"
   Rules:
   - Use "Korean pop star" / "K-pop star" / "Korean singer" — NOT the idol's name alone
   - Put the SPECIFIC FACT (twins, secret, hidden, viral moment) front and center
   - ALL CAPS 1-2 key words. 1 emoji at the very end.
   - End EVERY title exactly with " #Shorts"
   - Option 1: Specific fact + shock
   - Option 2: Duration/scale
   - Option 3: Reaction hook

3. "scenes": Array of 5-7 scene objects, each with:
   - "scene_id": number (1-based)
   - "description": what should appear on screen (be specific)
   - "youtube_query": yt-dlp search term — VERY specific (e.g. "Crayon Pop Choa twin pregnancy reveal 2026")
   - "youtube_query_ko": 같은 내용의 한국어 YouTube 검색어 (e.g. "크레용팝 초아 쌍둥이 임신 공개")
   - "image_query": fallback image search term
   - "duration_hint": "3-5 seconds"

4. "metadata":
   - "title": Pick the BEST of your 3 title options (copy it exactly)
   - "description": START with the primary keyword in the FIRST sentence. Repeat it 2-3 times naturally. Add a CTA. End with hashtags on a new line: #Shorts #Kpop #[Artist/Topic] #KdramaLovers
   - "tags": comma-separated tags (max 500 chars). RULE: Put the most specific primary keyword FIRST. Include artist name, long-tail, and broad tags (kpop, kdrama, korean celebrity). NO "#" symbol here.

{f'''
EDITOR FEEDBACK (from previous attempt — you MUST address ALL points):
{feedback}
''' if feedback else ''}
Return ONLY valid JSON. No markdown, no explanation."""

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        response_format={"type": "json_object"},
    )

    try:
        result_json = json.loads(response.choices[0].message.content)
        result_json["_news_context"] = news_context
        result_json["_news_articles"] = news_articles
        return result_json
    except json.JSONDecodeError as e:
        console.print(f"[red]GPT 응답 파싱 실패: {e}[/red]")
        return {"_news_context": news_context}


def run(output_dir: Path, topics_path: Path) -> tuple[Path, Path, Path]:
    """대본 생성 모듈 실행"""
    console.print("\n[bold blue]━━ [2/6] 대본/프롬프트 생성 시작 ━━[/bold blue]")

    # 1. 토픽 로드 (가장 높은 virality_score 선택)
    topics = json.loads(topics_path.read_text(encoding="utf-8"))
    if not topics:
        raise ValueError("trending_topics.json이 비어있습니다.")

    # virality_score가 있으면 그 기준, 없으면 첫 번째
    topic = max(topics, key=lambda t: t.get("virality_score", 0))
    console.print(f"  [cyan]선택된 토픽: {topic.get('headline', 'N/A')}[/cyan]")

    # 2. GPT-4o 생성
    result = generate_script_and_plan(topic)
    if not result:
        raise RuntimeError("대본 생성에 실패했습니다.")

    # 3. 파일 저장
    script_path = output_dir / "script.txt"
    script_path.write_text(result.get("script", ""), encoding="utf-8")

    assets_plan_path = output_dir / "assets_plan.json"
    assets_plan_path.write_text(
        json.dumps({"scenes": result.get("scenes", [])}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(result.get("metadata", {}), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # 4. 결과 요약
    word_count = len(result.get("script", "").split())
    scene_count = len(result.get("scenes", []))
    console.print(f"  [green]✓ 대본: {word_count} words → {script_path}[/green]")
    console.print(f"  [green]✓ 에셋 플랜: {scene_count}개 씬 → {assets_plan_path}[/green]")
    console.print(f"  [green]✓ 메타데이터 → {metadata_path}[/green]")
    console.print(f"  [dim]  제목: {result.get('metadata', {}).get('title', 'N/A')}[/dim]")

    return script_path, assets_plan_path, metadata_path


if __name__ == "__main__":
    output_dir = config.get_today_output_dir()
    topics_path = output_dir / "trending_topics.json"
    if not topics_path.exists():
        console.print("[red]trending_topics.json이 없습니다. research.py를 먼저 실행하세요.[/red]")
    else:
        run(output_dir, topics_path)
