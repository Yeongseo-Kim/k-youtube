"""
[공통] AI 리뷰어 — 각 모듈 결과물을 GPT-4o가 평가하고 피드백 반환

사용 패턴:
  result = reviewer.evaluate(role="script_editor", content=script_text)
  if result["score"] < 75:
      # 재생성 트리거
"""

import json
from openai import OpenAI
from rich.console import Console

import config

console = Console()

# ── 역할별 평가 프롬프트 정의 ──
REVIEW_PROMPTS = {

    "script_editor": {
        "system": "You are a senior YouTube Shorts scriptwriter specializing in viral K-content for international audiences.",
        "criteria": """Evaluate this YouTube Shorts script on:
1. HOOK strength (1-25): Does the opening sentence stop scrolling?
2. CLARITY (1-25): Is it understandable for non-Korean viewers?
3. PACING (1-25): Right word count (70-110), good flow?
4. ENGAGEMENT (1-25): Emotional pull, curiosity gap, CTA?

Total: 100 points. Pass threshold: 70.""",
        "output": "Return JSON: {score: int, passed: bool, feedback: str (2-3 specific improvement points in English)}"
    },

    "asset_reviewer": {
        "system": "You are a video editor reviewing visual assets for YouTube Shorts quality.",
        "criteria": """Evaluate the asset collection plan:
1. RELEVANCE (1-25): Do the search queries match the script scenes?
2. VARIETY (1-25): Enough different visual types?
3. SPECIFICITY (1-25): Are yt-dlp queries specific enough to find real clips?
4. FALLBACK (1-25): Good image fallback queries?

Total: 100 points. Pass threshold: 70.""",
        "output": "Return JSON: {score: int, passed: bool, feedback: str, improved_queries: [{scene_id: int, youtube_query: str, image_query: str}]}"
    },

    "seo_optimizer": {
        "system": "You are a YouTube SEO expert specializing in K-pop and K-drama content.",
        "criteria": """Evaluate this YouTube metadata:
1. TITLE click-worthiness (1-25): Curiosity, emoji use, length ≤100 chars?
2. DESCRIPTION quality (1-25): #Shorts included, relevant hashtags?
3. TAGS coverage (1-25): Mix of broad and niche K-content tags?
4. OVERALL virality (1-25): Will this rank in K-content search?

Total: 100 points. Pass threshold: 70.""",
        "output": "Return JSON: {score: int, passed: bool, feedback: str, improved_title: str, improved_tags: str}"
    },

    "video_qa": {
        "system": "You are a QA engineer reviewing YouTube Shorts technical quality.",
        "criteria": """Evaluate the video production plan:
1. TIMING logic (1-25): Audio duration split evenly across scenes?
2. SUBTITLE quality (1-25): Font size, positioning, readability?
3. TRANSITION smoothness (1-25): Crossfade timing appropriate?
4. TECHNICAL specs (1-25): 9:16, H.264, 30fps, ≤60 seconds?

Total: 100 points. Pass threshold: 80.""",
        "output": "Return JSON: {score: int, passed: bool, feedback: str}"
    },
}


def evaluate(role: str, content: str, context: str = "") -> dict:
    """
    AI 리뷰어 실행

    Args:
        role: 리뷰어 역할 (REVIEW_PROMPTS의 키)
        content: 평가할 콘텐츠 (대본, JSON 등)
        context: 추가 컨텍스트 (선택)

    Returns:
        {score: int, passed: bool, feedback: str, ...역할별 추가 필드}
    """
    if role not in REVIEW_PROMPTS:
        raise ValueError(f"알 수 없는 리뷰어 역할: {role}. 가능한 역할: {list(REVIEW_PROMPTS.keys())}")

    prompt_config = REVIEW_PROMPTS[role]
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    user_message = f"""
{prompt_config['criteria']}

{"CONTEXT: " + context if context else ""}

CONTENT TO EVALUATE:
{content}

{prompt_config['output']}
""".strip()

    console.print(f"    [dim]🤖 {role} 리뷰 중...[/dim]")

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": prompt_config["system"]},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,  # 평가는 일관성 중요하므로 낮게
        response_format={"type": "json_object"},
    )

    try:
        result = json.loads(response.choices[0].message.content)
        score = result.get("score", 0)
        passed = result.get("passed", score >= 75)
        feedback = result.get("feedback", "")

        status_icon = "✓" if passed else "✗"
        status_color = "green" if passed else "yellow"
        console.print(
            f"    [{status_color}]{status_icon} {role}: {score}/100 "
            f"({'통과' if passed else '재시도 필요'})[/{status_color}]"
        )
        if not passed:
            console.print(f"    [dim]  피드백: {feedback[:100]}...[/dim]")

        return result

    except json.JSONDecodeError:
        console.print(f"    [red]리뷰 응답 파싱 실패[/red]")
        return {"score": 0, "passed": False, "feedback": "리뷰 파싱 실패"}


def evaluate_with_retry(
    role: str,
    content_fn,       # 콘텐츠 생성 함수 (재시도 시 재호출)
    context: str = "",
    max_retries: int = 3,
) -> tuple[str, dict]:
    """
    생성 → 리뷰 → 실패 시 재생성 루프

    Args:
        role: 리뷰어 역할
        content_fn: content 생성 함수. (feedback: str) → str 시그니처
        context: 추가 컨텍스트
        max_retries: 최대 재시도 횟수

    Returns:
        (최종 콘텐츠, 리뷰 결과)
    """
    feedback = ""
    for attempt in range(1, max_retries + 1):
        console.print(f"    [dim]시도 {attempt}/{max_retries}[/dim]")
        content = content_fn(feedback)
        review = evaluate(role, content, context)

        if review.get("passed"):
            return content, review

        feedback = review.get("feedback", "")
        if attempt < max_retries:
            console.print(f"    [yellow]재생성 중... (피드백 반영)[/yellow]")

    console.print(f"    [yellow]⚠ 최대 재시도 도달. 마지막 결과 사용.[/yellow]")
    return content, review
