"""
[SEO 최적화 모듈] YouTube Shorts 메타데이터 검색 최적화

2025 YouTube Shorts SEO 알고리즘 기반:
- 제목: 55자 이하, 핵심 키워드 첫 배치, 끝에 이모지+해시태그
- 설명: 첫 150자에 주 키워드 포함, 키워드 2-3회 반복, CTA, 끝에 해시태그
- 태그: 주 키워드 첫 배치, 롱테일+광범위 혼합, 500자 제한

사용:
    from src.seo_optimizer import score_metadata, optimize_metadata, validate_and_fix
"""

import re
import json
from openai import OpenAI
from rich.console import Console

import config

console = Console()

# ─── 상수 ───────────────────────────────────────────────────────
TITLE_MAX_CHARS = 55       # Shorts 모바일 표시 기준
TITLE_SOFT_LIMIT = 60      # YouTube 공식 권고 (검색 결과에서 잘리기 전)
DESCRIPTION_KEYWORD_WINDOW = 150  # 첫 N자 안에 키워드가 있어야 함
TAGS_MAX_CHARS = 500
HASHTAGS_IN_TITLE_MAX = 2   # 제목 끝 해시태그 최대 수
HASHTAGS_IN_DESC_MAX = 5    # 설명 끝 해시태그 최대 수

# K-content 기본 해시태그 (항상 포함)
BASE_HASHTAGS = ["#Shorts", "#Kpop", "#Kdrama"]

# Broad 태그 (다양한 시청자 도달용)
BROAD_TAGS = [
    "kpop", "kdrama", "korean entertainment", "korean idol",
    "k-content", "korea", "korean celebrity"
]


# ─── 유효성 검사 & 자동 교정 ─────────────────────────────────────

def _extract_hashtags(text: str) -> list[str]:
    """텍스트에서 해시태그 추출 (순서 유지)"""
    return re.findall(r"#\w+", text)


def _remove_all_hashtags(text: str) -> str:
    """텍스트에서 해시태그 제거"""
    return re.sub(r"\s*#\w+", "", text).strip()


def validate_and_fix(meta: dict) -> dict:
    """
    메타데이터를 SEO 규칙에 맞게 자동 교정한다.

    규칙:
    1. 제목: 55자 초과 시 자르기, 해시태그는 끝으로 이동
    2. 설명: 해시태그를 끝으로 이동, 빈 설명 보완
    3. 태그: #Shorts 첫 배치, 중복 제거, 500자 제한
    """
    fixed = dict(meta)

    # ── 제목 교정 ──
    title = fixed.get("title", "")
    # 제목 중간의 해시태그를 끝으로 이동
    title_tags = _extract_hashtags(title)
    title_clean = _remove_all_hashtags(title).strip()
    # 제목에 #Shorts 태그가 없으면 추가 (Shorts 분류용)
    if "#Shorts" not in title_tags:
        title_tags = ["#Shorts"] + title_tags
    # 제목 길이 제한 (해시태그 제외한 텍스트 기준)
    if len(title_clean) > TITLE_SOFT_LIMIT:
        title_clean = title_clean[:TITLE_SOFT_LIMIT].rstrip()
    # 해시태그는 최대 2개만
    title_tags = title_tags[:HASHTAGS_IN_TITLE_MAX]
    fixed["title"] = f"{title_clean} {' '.join(title_tags)}".strip()

    # ── 설명 교정 ──
    description = fixed.get("description", "")
    desc_tags = _extract_hashtags(description)
    desc_clean = _remove_all_hashtags(description).strip()
    # 기본 해시태그 + 기존 해시태그 통합 (중복 제거)
    all_desc_tags = list(dict.fromkeys(BASE_HASHTAGS + desc_tags))[:HASHTAGS_IN_DESC_MAX]
    fixed["description"] = f"{desc_clean}\n\n{' '.join(all_desc_tags)}".strip()

    # ── 태그 교정 ──
    tags_str = fixed.get("tags", "")
    tags = [t.strip().lstrip("#") for t in tags_str.split(",") if t.strip()]
    # 중복 제거 (소문자 기준)
    seen = set()
    deduped = []
    for t in tags:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    # Shorts 태그가 없으면 맨 앞에 추가
    if "Shorts" not in deduped and "shorts" not in seen:
        deduped = ["Shorts"] + deduped
    # 500자 제한 적용
    result_tags, total = [], 0
    for tag in deduped:
        add_len = len(tag) + (2 if result_tags else 0)  # ", " 구분자
        if total + len(tag) > TAGS_MAX_CHARS:
            break
        result_tags.append(tag)
        total += add_len
    fixed["tags"] = ", ".join(result_tags)

    return fixed


# ─── SEO 점수 채점 ──────────────────────────────────────────────

def score_metadata(meta: dict) -> tuple[int, dict]:
    """
    메타데이터 SEO 점수를 0-100으로 채점한다.

    반환: (총점, 세부항목 dict)
    총점 기준:
        80-100: 🟢 최적화 완료
        60-79:  🟡 개선 권장
        0-59:   🔴 최적화 필요
    """
    details = {}
    total = 0

    title = meta.get("title", "")
    description = meta.get("description", "")
    tags = meta.get("tags", "")

    # ── 제목 평가 (40점) ──

    # 1. 제목 길이 (15점)
    title_clean_len = len(_remove_all_hashtags(title))
    if title_clean_len <= 45:
        details["title_length"] = ("✅ 완벽 (45자 이하)", 15)
        total += 15
    elif title_clean_len <= 55:
        details["title_length"] = (f"✅ 양호 ({title_clean_len}자)", 10)
        total += 10
    elif title_clean_len <= 60:
        details["title_length"] = (f"🟡 약간 김 ({title_clean_len}자, 55자 권장)", 6)
        total += 6
    else:
        details["title_length"] = (f"🔴 너무 김 ({title_clean_len}자, 55자 초과)", 0)

    # 2. 제목에 #Shorts 포함 (10점)
    if "#Shorts" in title or "#shorts" in title:
        details["title_shorts_hashtag"] = ("✅ #Shorts 포함", 10)
        total += 10
    else:
        details["title_shorts_hashtag"] = ("🔴 #Shorts 없음 (Shorts 피드 분류에 필요)", 0)

    # 3. 핵심 키워드 앞 배치 (15점) — 제목 첫 30자 안에 K-content 키워드가 있는지
    kpop_terms = ["kpop", "k-pop", "korean", "k-drama", "kdrama", "idol", "bts", "blackpink"]
    title_lower = _remove_all_hashtags(title[:35]).lower()
    if any(term in title_lower for term in kpop_terms):
        details["title_keyword_frontload"] = ("✅ 핵심 키워드 앞에 배치됨", 15)
        total += 15
    else:
        details["title_keyword_frontload"] = ("🟡 핵심 키워드를 제목 앞부분에 배치하세요", 5)
        total += 5

    # ── 설명 평가 (30점) ──

    # 4. 첫 150자 키워드 포함 (15점)
    desc_first_150 = description[:DESCRIPTION_KEYWORD_WINDOW].lower()
    if any(term in desc_first_150 for term in kpop_terms):
        details["desc_keyword_window"] = ("✅ 첫 150자에 키워드 포함", 15)
        total += 15
    else:
        details["desc_keyword_window"] = ("🔴 첫 150자에 키워드 없음 — 설명 시작을 키워드로 시작하세요", 0)

    # 5. 설명 끝 해시태그 (15점)
    desc_tags = _extract_hashtags(description)
    has_shorts = any(h.lower() == "#shorts" for h in desc_tags)
    has_kpop = any(h.lower() in ["#kpop", "#kdrama"] for h in desc_tags)
    if has_shorts and has_kpop:
        details["desc_hashtags"] = (f"✅ 해시태그 {len(desc_tags)}개 포함 (#Shorts, #Kpop 확인됨)", 15)
        total += 15
    elif has_shorts or has_kpop:
        details["desc_hashtags"] = ("🟡 #Shorts 또는 #Kpop 중 하나 누락", 8)
        total += 8
    else:
        details["desc_hashtags"] = ("🔴 #Shorts, #Kpop 해시태그 없음", 0)

    # ── 태그 평가 (30점) ──

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    tag_count = len(tag_list)
    tags_total_chars = len(tags)

    # 6. 태그 수 (10점)
    if 10 <= tag_count <= 20:
        details["tags_count"] = (f"✅ 태그 {tag_count}개 (최적)", 10)
        total += 10
    elif 5 <= tag_count < 10:
        details["tags_count"] = (f"🟡 태그 {tag_count}개 (10-20개 권장)", 6)
        total += 6
    elif tag_count > 20:
        details["tags_count"] = (f"🟡 태그 {tag_count}개 (20개 이하 권장)", 7)
        total += 7
    else:
        details["tags_count"] = (f"🔴 태그 {tag_count}개 (너무 적음)", 0)

    # 7. 태그 글자수 한도 (10점)
    if tags_total_chars <= 400:
        details["tags_chars"] = (f"✅ {tags_total_chars}/500자 (여유 있음)", 10)
        total += 10
    elif tags_total_chars <= 500:
        details["tags_chars"] = (f"✅ {tags_total_chars}/500자", 8)
        total += 8
    else:
        details["tags_chars"] = (f"🔴 {tags_total_chars}/500자 초과 — 태그 줄이세요", 0)

    # 8. 주 키워드가 첫 태그인지 (10점)
    first_tag = tag_list[0].lower() if tag_list else ""
    if any(term in first_tag for term in kpop_terms) or first_tag in ["kpop", "kdrama", "korean"]:
        details["tags_primary_first"] = ("✅ 주 키워드가 첫 번째 태그", 10)
        total += 10
    elif first_tag == "shorts":
        details["tags_primary_first"] = ("🟡 첫 태그가 'Shorts' — 주제 키워드를 더 앞에", 5)
        total += 5
    else:
        details["tags_primary_first"] = ("🟡 첫 태그에 주 키워드 권장", 5)
        total += 5

    return total, details


def get_score_badge(score: int) -> str:
    """점수에 따른 배지 반환"""
    if score >= 80:
        return f"🟢 SEO 점수: {score}/100"
    elif score >= 60:
        return f"🟡 SEO 점수: {score}/100"
    else:
        return f"🔴 SEO 점수: {score}/100"


# ─── GPT-4o SEO 최적화 ──────────────────────────────────────────

def optimize_metadata(
    meta: dict,
    topic: dict = None,
    script: str = "",
    model: str = None,
) -> dict:
    """
    GPT-4o로 현재 메타데이터를 YouTube Shorts SEO 규칙에 맞게 최적화.

    Args:
        meta: 현재 metadata.json 내용
        topic: trending_topics.json의 선택된 토픽 (옵션)
        script: 대본 텍스트 (옵션)
        model: 사용할 GPT 모델 (기본: config.LLM_MODEL)

    Returns:
        최적화된 메타데이터 dict
    """
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    model = model or config.LLM_MODEL

    current_title = meta.get("title", "")
    current_description = meta.get("description", "")
    current_tags = meta.get("tags", "")
    title_options = meta.get("title_options", [])

    topic_context = ""
    if topic:
        topic_context = f"""
TOPIC CONTEXT:
- Headline: {topic.get('headline', '')}
- Keywords: {', '.join(topic.get('keywords', []))}
- Why viral: {topic.get('why_viral', '')}
"""

    script_snippet = f"\nSCRIPT (first 300 chars): {script[:300]}" if script else ""

    prompt = f"""You are a YouTube Shorts SEO expert specializing in K-content for international audiences (2025 algorithm).

CURRENT METADATA TO OPTIMIZE:
- Title: {current_title}
- Description: {current_description}
- Tags: {current_tags}
- Title options available: {json.dumps(title_options, ensure_ascii=False)}
{topic_context}{script_snippet}

════════════════════════════════════════
STRICT SEO RULES FOR YOUTUBE SHORTS 2025:
════════════════════════════════════════

**TITLE RULES:**
1. MAX 55 characters (excluding hashtags at the end)
2. Primary keyword (Korean/K-pop/K-drama) within FIRST 35 characters
3. End with exactly: [space] #Shorts
4. Use ALL CAPS on 1-2 key emotionally-charged words
5. Add 1 emoji just before #Shorts
6. Make anyone click — even non-K-pop fans
7. Style: "SPECIFIC FACT + SHOCK/INTRIGUE"
   ✅ "Korean pop star SECRETLY married 😱 #Shorts"
   ✅ "K-drama star hid TWIN babies 9 months 😭 #Shorts"
   ❌ Long titles that get cut off on mobile

**DESCRIPTION RULES:**
1. START with the primary keyword naturally in the FIRST sentence (first 150 chars are most important)
2. Repeat the main keyword 2-3 times total (naturally, not spammy)
3. Include a CTA: "Follow for daily K-content you won't find anywhere else! 🔔"
4. END with hashtags on a new line: #Shorts #Kpop #[ArtistName or Topic] #KdramaLovers #KoreanEntertainment
5. Total length: 150-300 characters (before hashtags)
6. NO hashtags in the middle of the description

**TAGS RULES:**
1. FIRST tag: your most specific primary keyword (e.g., "Korean pop star pregnancy", "BTS Jimin announcement")
2. Include the artist/topic name specifically
3. Mix: 3-4 long-tail keywords + 3-4 broad keywords
4. Always include: kpop, kdrama OR both, Korean celebrity, Korean entertainment
5. NEVER start with generic "Shorts" — put your content keyword first
6. Total: 10-20 tags, max 500 characters
7. Separate with commas, NO # symbols in tags

Return ONLY valid JSON with these exact keys:
{{
  "title": "optimized title here #Shorts",
  "title_options": ["option 1 #Shorts", "option 2 #Shorts", "option 3 #Shorts"],
  "description": "optimized description here\\n\\n#Shorts #Kpop #ArtistName",
  "tags": "primary keyword, specific keyword, artist name, kpop, kdrama, korean celebrity, ...",
  "seo_notes": "Brief explanation of what was optimized and why"
}}"""

    try:
        console.print("  [dim]GPT-4o SEO 최적화 중...[/dim]")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)

        # 기존 메타데이터와 병합 (최적화된 필드만 덮어쓰기)
        optimized = dict(meta)
        for key in ["title", "title_options", "description", "tags"]:
            if key in result and result[key]:
                optimized[key] = result[key]

        optimized["seo_optimized"] = True
        optimized["seo_notes"] = result.get("seo_notes", "")

        console.print(f"  [green]✓ SEO 최적화 완료[/green]")
        if result.get("seo_notes"):
            console.print(f"  [dim]  → {result['seo_notes'][:100]}[/dim]")

        # 최종 유효성 교정
        return validate_and_fix(optimized)

    except Exception as e:
        console.print(f"  [red]SEO 최적화 실패: {e}[/red]")
        return validate_and_fix(meta)  # 실패 시 기본 교정만 적용


# ─── 메인 실행 (단독 테스트용) ──────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    print("=== SEO Optimizer 테스트 ===\n")

    # 테스트 메타데이터
    test_meta = {
        "title": "Korean pop star secretly hid her pregnancy from fans for 9 months - shocking reveal",
        "description": "This is an incredible story about a famous idol. She managed to hide it for months. Fans are shocked everywhere. #kpop #viral",
        "tags": "kpop, idol, pregnancy, secret, fans shocked, korea",
        "title_options": [
            "Korean pop star secretly hid pregnancy 9 months",
            "K-pop idol SHOCKED fans with secret baby reveal",
            "Korea is CRYING over this idol secret"
        ]
    }

    print("📋 원본 메타데이터:")
    print(f"  제목: {test_meta['title']} ({len(test_meta['title'])}자)")
    print(f"  태그: {test_meta['tags']}")
    print()

    # 점수 채점
    score, details = score_metadata(test_meta)
    print(f"📊 SEO 점수: {score}/100  {get_score_badge(score)}")
    for k, (msg, pts) in details.items():
        print(f"  [{pts:2d}pt] {msg}")
    print()

    # 자동 교정
    fixed = validate_and_fix(test_meta)
    print("🔧 자동 교정 결과:")
    print(f"  제목: {fixed['title']} ({len(fixed['title'])}자)")
    print(f"  태그: {fixed['tags'][:100]}...")
    print()

    # GPT 최적화 (API 키 있을 때만)
    if "--optimize" in sys.argv:
        print("🤖 GPT SEO 최적화 중...")
        optimized = optimize_metadata(test_meta)
        score2, _ = score_metadata(optimized)
        print(f"\n✅ 최적화 후 점수: {score2}/100")
        print(f"  제목: {optimized['title']}")
        print(f"  설명:\n{optimized['description']}")
        print(f"  태그: {optimized['tags']}")
