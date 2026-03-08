"""
[모듈 1] 트렌딩 리서치 — RSS 뉴스 대신 소셜/실시간 데이터 기반

소스 우선순위:
  1순위: Reddit r/kpop, r/kdrama, r/koreanvariety — Hot 포스트 (실시간 커뮤니티 반응)
  2순위: YouTube 트렌딩 — yt-dlp로 K-content 관련 트렌딩 영상 제목 수집
  3순위: Google Trends — K-pop/K-drama 연관 검색어 급상승
  폴백:  Soompi RSS (기존 방식)

GPT-4o로 위 소스를 분석해 가장 바이럴 가능성 높은 토픽 3개를 선정한다.
"""

import json
import subprocess
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from openai import OpenAI
from rich.console import Console

import config

console = Console()


# ─────────────────────────────────────────────────────
# 소스 1: Reddit (인증 없이 JSON 엔드포인트 사용)
# ─────────────────────────────────────────────────────

REDDIT_SUBREDDITS = [
    "kpop",
    "kdrama",
    "koreanvariety",
    "koreanfood",
    "koreatravel",
]

def fetch_reddit_trending(hours: int = 24, limit: int = 10) -> list[dict]:
    """Reddit 핫 포스트 수집 (인증 없음, JSON API)"""
    posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    headers = {
        "User-Agent": "python:k-content-shorts-bot:v1.0 (by /u/eldrac)"
    }

    for sub in REDDIT_SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                created_utc = post.get("created_utc", 0)
                post_time = datetime.fromtimestamp(created_utc, tz=timezone.utc)

                if post_time < cutoff:
                    continue

                posts.append({
                    "title": post.get("title", ""),
                    "selftext": post.get("selftext", "")[:300],
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "source": f"r/{sub}",
                    "upvote_ratio": post.get("upvote_ratio", 0),
                })

            console.print(f"  [dim]Reddit r/{sub}: {len(posts)}개 수집[/dim]")

        except Exception as e:
            console.print(f"  [yellow]⚠ Reddit r/{sub} 오류: {e}[/yellow]")

    # 점수순 정렬
    posts.sort(key=lambda x: x["score"] * x["upvote_ratio"], reverse=True)
    console.print(f"  [green]Reddit 총 {len(posts)}개 포스트 수집[/green]")
    return posts


# ─────────────────────────────────────────────────────
# 소스 2: YouTube 트렌딩 (yt-dlp 활용)
# ─────────────────────────────────────────────────────

YOUTUBE_TRENDING_QUERIES = [
    "kpop",
    "kdrama",
    "korean food",
    "korea travel",
]

def fetch_youtube_trending(max_results: int = 5) -> list[dict]:
    """yt-dlp로 YouTube 트렌딩 K-content 영상 제목 수집"""
    from src.asset_collector import _get_yt_cookies_args

    videos = []
    cookies_args = _get_yt_cookies_args()

    for query in YOUTUBE_TRENDING_QUERIES:
        try:
            cmd = [
                "yt-dlp",
                f"ytsearch{max_results}:{query}",
                "--print", "%(title)s|%(view_count)s|%(like_count)s|%(webpage_url)s",
                "--no-download",
                "--quiet",
                "--no-warnings",
            ] + cookies_args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = line.split("|")
                    if len(parts) >= 2:
                        videos.append({
                            "title": parts[0],
                            "view_count": int(parts[1]) if parts[1].isdigit() else 0,
                            "url": parts[3] if len(parts) > 3 else "",
                            "source": f"YouTube:{query}",
                        })
        except Exception as e:
            console.print(f"  [yellow]⚠ YouTube 트렌딩 오류 ({query}): {e}[/yellow]")

    videos.sort(key=lambda x: x["view_count"], reverse=True)
    console.print(f"  [green]YouTube 트렌딩 {len(videos)}개 수집[/green]")
    return videos


# ─────────────────────────────────────────────────────
# 소스 3: Google Trends (pytrends)
# ─────────────────────────────────────────────────────

GTRENDS_KEYWORDS = ["kpop", "kdrama", "korean food", "korea travel", "korean culture"]

def fetch_google_trends() -> list[dict]:
    """Google Trends에서 K-content 관련 급상승 검색어 수집"""
    trends = []
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload(GTRENDS_KEYWORDS[:5], cat=0, timeframe="now 1-d", geo="")
        related = pytrends.related_queries()

        for kw in GTRENDS_KEYWORDS[:5]:
            top_df = related.get(kw, {}).get("top")
            rising_df = related.get(kw, {}).get("rising")

            if rising_df is not None and not rising_df.empty:
                for _, row in rising_df.head(3).iterrows():
                    trends.append({
                        "keyword": row.get("query", ""),
                        "value": row.get("value", 0),
                        "base_keyword": kw,
                        "source": "Google Trends (Rising)",
                    })

        console.print(f"  [green]Google Trends {len(trends)}개 급상승 키워드 수집[/green]")
    except Exception as e:
        console.print(f"  [yellow]⚠ Google Trends 오류: {e}[/yellow]")

    return trends


# ─────────────────────────────────────────────────────
# 폴백: Soompi RSS (기존 방식)
# ─────────────────────────────────────────────────────

def fetch_rss_fallback(hours: int = 48) -> list[dict]:
    """RSS 피드 폴백 (다른 소스 실패 시)"""
    import feedparser
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    articles = []

    for feed_url in config.RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6])
                    if pub_dt < cutoff:
                        continue
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "url": entry.get("link", ""),
                    "source": feed.feed.get("title", feed_url),
                })
        except Exception as e:
            console.print(f"  [yellow]⚠ RSS 오류 ({feed_url}): {e}[/yellow]")

    return articles


# ─────────────────────────────────────────────────────
# GPT-4o 분석 — 토픽 선정
# ─────────────────────────────────────────────────────

def rank_and_summarize(
    reddit_posts: list[dict],
    yt_videos: list[dict],
    google_trends: list[dict],
    rss_articles: list[dict],
    top_n: int = 3,
) -> list[dict]:
    """GPT-4o로 멀티소스 데이터를 분석해 상위 N개 핫토픽 선정"""
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    # 데이터 요약 구성
    reddit_text = "\n".join(
        f"[{p['source']}] {p['title']} (점수:{p['score']}, 댓글:{p['num_comments']})"
        for p in reddit_posts[:15]
    )
    yt_text = "\n".join(
        f"[YouTube] {v['title']} (조회:{v['view_count']:,})"
        for v in yt_videos[:10]
    )
    trends_text = "\n".join(
        f"[Google Trends↑] {t['keyword']} (관련:{t['base_keyword']})"
        for t in google_trends[:10]
    )
    rss_text = "\n".join(
        f"[뉴스] {a['title']}"
        for a in rss_articles[:5]
    ) if rss_articles else ""

    combined = f"""=== REDDIT COMMUNITY HOT POSTS (실시간 팬 반응) ===
{reddit_text or '데이터 없음'}

=== YOUTUBE TRENDING (트렌딩 영상) ===
{yt_text or '데이터 없음'}

=== GOOGLE TRENDS RISING (급상승 검색어) ===
{trends_text or '데이터 없음'}

=== NEWS (보조) ===
{rss_text or '데이터 없음'}"""

    prompt = f"""You are a viral K-content strategist for YouTube Shorts targeting international audiences.

Analyze the following real-time trending data from multiple sources and identify the TOP {top_n} hottest topics RIGHT NOW.

{combined}

For each topic provide:
1. "headline": Catchy English headline (max 15 words) — focus on what will make international fans CLICK
2. "headline_ko": 위 헤드라인의 자연스러운 한국어 번역 (15자 이내)
3. "summary": 2-3 sentence English hook that teases the story
4. "summary_ko": 위 요약의 한국어 번역 (2-3문장)
5. "keywords": 5-7 English search keywords for finding video assets
6. "source_urls": relevant URLs from the data
7. "virality_score": 1-10 (consider: Reddit engagement, YouTube views, Google Trends spike, emotional hook)
8. "why_viral": 1 sentence explaining WHY this will go viral internationally
9. "why_viral_ko": 위 이유의 한국어 번역

Prioritize topics that:
- Have HIGH Reddit engagement (upvotes + comments)
- Are trending on MULTIPLE platforms simultaneously
- Have strong emotional hooks (drama, comeback, scandal, achievement, romance)
- Are understandable and interesting to non-Korean fans

Return a JSON object with key "topics" containing an array of {top_n} objects. No markdown."""

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    try:
        result = json.loads(response.choices[0].message.content)
        topics = result.get("topics", result if isinstance(result, list) else [])
        return topics[:top_n]
    except (json.JSONDecodeError, KeyError) as e:
        console.print(f"[red]GPT 응답 파싱 실패: {e}[/red]")
        return []


# ─────────────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────────────

def run(output_dir: Path) -> Path:
    """트렌딩 리서치 모듈 실행 — trending_topics.json 생성"""
    console.print("\n[bold blue]━━ [1/6] 트렌딩 리서치 시작 (Reddit + YouTube + Google Trends) ━━[/bold blue]")

    # 1. 소스별 데이터 수집
    console.print("  [dim]📡 Reddit 수집 중...[/dim]")
    reddit_posts = fetch_reddit_trending(hours=24)

    console.print("  [dim]📺 YouTube 트렌딩 수집 중...[/dim]")
    yt_videos = fetch_youtube_trending()

    console.print("  [dim]📈 Google Trends 수집 중...[/dim]")
    google_trends = fetch_google_trends()

    # 데이터가 부족하면 RSS 폴백
    rss_articles = []
    total_signals = len(reddit_posts) + len(yt_videos) + len(google_trends)
    if total_signals < 5:
        console.print("  [yellow]⚠ 소셜 데이터 부족 — RSS 폴백 사용[/yellow]")
        rss_articles = fetch_rss_fallback()

    console.print(
        f"\n  [cyan]데이터 수집 완료: Reddit {len(reddit_posts)}개, "
        f"YouTube {len(yt_videos)}개, Trends {len(google_trends)}개[/cyan]"
    )

    # 2. GPT-4o 분석
    if total_signals == 0 and not rss_articles:
        console.print("[red]수집된 데이터가 없습니다. 네트워크 연결을 확인하세요.[/red]")
        return output_dir / "trending_topics.json"

    topics = rank_and_summarize(reddit_posts, yt_videos, google_trends, rss_articles, top_n=3)

    if not topics:
        console.print("[red]토픽 분석 실패. 수동으로 trending_topics.json을 작성하세요.[/red]")
        topics = []

    # 3. 결과 저장
    output_path = output_dir / "trending_topics.json"
    output_path.write_text(json.dumps(topics, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"\n  [green]✓ {len(topics)}개 토픽 저장: {output_path}[/green]")
    for i, t in enumerate(topics, 1):
        score = t.get("virality_score", "?")
        why = t.get("why_viral", "")
        console.print(f"    {i}. [{score}/10] {t.get('headline', 'N/A')}")
        if why:
            console.print(f"       → {why}")

    return output_path


if __name__ == "__main__":
    output_dir = config.get_today_output_dir()
    run(output_dir)
