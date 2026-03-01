"""
[공통] 파이프라인 상태 머신 — 체크포인트 기반 Human-in-the-Loop 제어

pipeline_state.json 구조:
{
  "date": "2026-03-01",
  "current_step": 2,
  "step_status": {
    "1": "done",        # pending | running | done | failed
    "2": "waiting_review",  # waiting_review: 사람 승인 대기
    "3": "pending",
    ...
  },
  "checkpoints": {
    "script": false,    # 대본 승인 여부
    "assets": false,    # 에셋 확인 승인 여부
    "video": false,     # 영상 승인 여부
    "thumbnail": false  # 썸네일 승인 여부
  },
  "results": {
    "topics_path": "...",
    "script_path": "...",
    ...
  },
  "error": null
}
"""

import json
import threading
from pathlib import Path
from datetime import date
from typing import Callable
from rich.console import Console

import config

console = Console()

# 체크포인트 정의: 어느 단계 완료 후 승인이 필요한지
CHECKPOINTS = {
    2: "script",      # 대본 생성 후 → 대본 승인
    3: "assets",      # 에셋 수집 후 → 에셋 확인 승인
    5: "video",       # 영상 편집 후 → 영상 승인
    4: "thumbnail",   # 미디어(썸네일) 생성 후 → 썸네일 승인
}

STEP_NAMES = {
    1: "뉴스 리서치",
    2: "대본 생성",
    3: "에셋 수집",
    4: "미디어 생성 (TTS/자막/썸네일)",
    5: "영상 편집",
    6: "유튜브 업로드",
}


# ── 상태 파일 관리 ──────────────────────────────────────────

def get_state_path(output_dir: Path) -> Path:
    return output_dir / "pipeline_state.json"


def load_state(output_dir: Path) -> dict:
    """pipeline_state.json 로드. 없거나 손상됐으면 초기 상태 반환."""
    path = get_state_path(output_dir)
    if path.exists():
        try:
            content = path.read_text(encoding="utf-8").strip()
            if content:
                return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            console.print("[yellow]⚠ pipeline_state.json 손상됨 → 초기화[/yellow]")
    return _initial_state(output_dir)


def save_state(output_dir: Path, state: dict) -> None:
    """pipeline_state.json 저장."""
    get_state_path(output_dir).write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _initial_state(output_dir: Path) -> dict:
    return {
        "date": date.today().isoformat(),
        "output_dir": str(output_dir),
        "current_step": 0,
        "step_status": {str(i): "pending" for i in range(1, 7)},
        "checkpoints": {
            "script": False,
            "assets": False,
            "video": False,
            "thumbnail": False,
        },
        "results": {},
        "error": None,
    }


def update_step(output_dir: Path, step: int, status: str, **kwargs) -> dict:
    """특정 단계의 상태를 업데이트하고 저장."""
    state = load_state(output_dir)
    state["step_status"][str(step)] = status
    state["current_step"] = step
    state["error"] = None
    if kwargs:
        state["results"].update(kwargs)
    save_state(output_dir, state)
    return state


def approve_checkpoint(output_dir: Path, checkpoint: str) -> dict:
    """체크포인트 승인 처리."""
    state = load_state(output_dir)
    if checkpoint not in state["checkpoints"]:
        raise ValueError(f"알 수 없는 체크포인트: {checkpoint}")
    state["checkpoints"][checkpoint] = True
    # 해당 단계를 waiting_review → done 으로 변경
    for step, cp in CHECKPOINTS.items():
        if cp == checkpoint:
            if state["step_status"].get(str(step)) == "waiting_review":
                state["step_status"][str(step)] = "done"
    save_state(output_dir, state)
    return state


def is_approved(output_dir: Path, checkpoint: str) -> bool:
    """체크포인트 승인 여부 확인."""
    state = load_state(output_dir)
    return state["checkpoints"].get(checkpoint, False)


def get_next_pending_step(output_dir: Path) -> int | None:
    """다음 실행 가능한 단계 번호 반환. 없으면 None."""
    state = load_state(output_dir)
    for step in range(1, 7):
        status = state["step_status"].get(str(step), "pending")
        if status == "pending":
            return step
        if status in ("running", "waiting_review", "failed"):
            return None  # 진행 중이거나 승인 대기 중
    return None  # 모두 완료


# ── 단계별 실행 함수 ──────────────────────────────────────────

def run_step(step: int, output_dir: Path) -> None:
    """단일 단계를 실행하고 상태를 업데이트한다."""
    update_step(output_dir, step, "running")
    console.print(f"\n[bold blue]▶ [{step}/6] {STEP_NAMES[step]} 시작[/bold blue]")

    try:
        if step == 1:
            _run_step1(output_dir)
        elif step == 2:
            _run_step2(output_dir)
        elif step == 3:
            _run_step3(output_dir)
        elif step == 4:
            _run_step4(output_dir)
        elif step == 5:
            _run_step5(output_dir)
        elif step == 6:
            _run_step6(output_dir)

        # 체크포인트가 있으면 waiting_review, 없으면 done
        checkpoint = CHECKPOINTS.get(step)
        if checkpoint:
            update_step(output_dir, step, "waiting_review")
            console.print(f"\n[bold yellow]✋ [{step}/6] {STEP_NAMES[step]} 완료 — 검토 후 승인 필요[/bold yellow]")
        else:
            update_step(output_dir, step, "done")

    except Exception as e:
        state = load_state(output_dir)
        state["step_status"][str(step)] = "failed"
        state["error"] = str(e)
        save_state(output_dir, state)
        console.print(f"\n[bold red]✗ [{step}/6] {STEP_NAMES[step]} 실패: {e}[/bold red]")
        raise


def _run_step1(output_dir: Path) -> None:
    from src.research import run
    result = run(output_dir)
    update_step(output_dir, 1, "running", topics_path=str(result))


def _run_step2(output_dir: Path) -> None:
    import json
    from src import generator, reviewer

    state = load_state(output_dir)
    topics_path = Path(state["results"].get("topics_path", output_dir / "trending_topics.json"))
    topics = json.loads(topics_path.read_text(encoding="utf-8"))

    # 사용자가 선택한 토픽 우선, 없으면 virality_score 최고값
    selected_idx = state["results"].get("selected_topic_index")
    if selected_idx is not None and 0 <= selected_idx < len(topics):
        topic = topics[selected_idx]
        console.print(f"  [cyan]사용자 선택 토픽: {topic.get('headline', 'N/A')}[/cyan]")
    else:
        topic = max(topics, key=lambda t: t.get("virality_score", 0))
        console.print(f"  [cyan]자동 선택 토픽 (최고 점수): {topic.get('headline', 'N/A')}[/cyan]")

    def generate_script(feedback: str = "") -> str:
        result = generator.generate_script_and_plan(topic, feedback=feedback)
        
        # 기사 원문 저장
        news_context = result.pop("_news_context", "뉴스 조회를 하지 않았습니다.")
        news_articles = result.pop("_news_articles", [])
        (output_dir / "news_context.txt").write_text(news_context, encoding="utf-8")
        (output_dir / "news_articles.json").write_text(
            json.dumps(news_articles, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        
        (output_dir / "script.txt").write_text(result.get("script", ""), encoding="utf-8")
        (output_dir / "assets_plan.json").write_text(
            json.dumps({"scenes": result.get("scenes", [])}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        # title_options는 최상위 키 → metadata dict에 병합해서 저장
        meta = result.get("metadata", {})
        meta["title_options"] = result.get("title_options", [])
        (output_dir / "metadata.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return result.get("script", "")

    final_script, review = reviewer.evaluate_with_retry(
        role="script_editor",
        content_fn=generate_script,
        context=f"Topic: {topic.get('headline')}",
        max_retries=3,
    )
    update_step(
        output_dir, 2, "running",
        script_path=str(output_dir / "script.txt"),
        assets_plan_path=str(output_dir / "assets_plan.json"),
        metadata_path=str(output_dir / "metadata.json"),
        review_score=review.get("score", 0),
    )


def _run_step3(output_dir: Path) -> None:
    import concurrent.futures
    from src.asset_collector import run as collect_assets
    from src.media_creator import run as create_media

    state = load_state(output_dir)
    script_path = Path(state["results"].get("script_path", output_dir / "script.txt"))
    assets_plan_path = Path(state["results"].get("assets_plan_path", output_dir / "assets_plan.json"))
    metadata_path = Path(state["results"].get("metadata_path", output_dir / "metadata.json"))

    console.print("[bold magenta]━━ 에셋 수집 & 미디어 생성 병렬 실행 ━━[/bold magenta]")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_assets = executor.submit(collect_assets, output_dir, assets_plan_path)
        future_media = executor.submit(create_media, output_dir, script_path, metadata_path)
        assets_dir = future_assets.result()
        audio_path, subtitle_path, thumbnail_path = future_media.result()

    update_step(
        output_dir, 3, "running",
        assets_dir=str(assets_dir),
        audio_path=str(audio_path),
        subtitle_path=str(subtitle_path),
        thumbnail_path=str(thumbnail_path),
    )


def _run_step4(output_dir: Path) -> None:
    """Step 4는 Step 3와 병렬로 이미 처리됨 — 썸네일 승인 체크포인트 단계."""
    # 실제 미디어 생성은 _run_step3에서 병렬로 완료됨
    # step4는 체크포인트(thumbnail 승인)를 위한 별도 단계로만 사용
    state = load_state(output_dir)
    thumbnail_path = state["results"].get("thumbnail_path", str(output_dir / "thumbnail.png"))
    if not Path(thumbnail_path).exists():
        raise FileNotFoundError(f"썸네일 파일 없음: {thumbnail_path}")
    update_step(output_dir, 4, "running", thumbnail_path=thumbnail_path)


def _run_step5(output_dir: Path) -> None:
    from src.video_editor import run
    state = load_state(output_dir)
    audio_path = Path(state["results"].get("audio_path", output_dir / "audio.mp3"))
    assets_dir = Path(state["results"].get("assets_dir", output_dir / "assets"))
    subtitle_path = Path(state["results"].get("subtitle_path", output_dir / "subtitle.srt"))
    video_path = run(output_dir, audio_path, assets_dir, subtitle_path)
    update_step(output_dir, 5, "running", video_path=str(video_path))


def _run_step6(output_dir: Path) -> None:
    from src.uploader import run
    state = load_state(output_dir)
    video_path = Path(state["results"].get("video_path", output_dir / "final_video.mp4"))
    thumbnail_path = Path(state["results"].get("thumbnail_path", output_dir / "thumbnail.png"))
    metadata_path = Path(state["results"].get("metadata_path", output_dir / "metadata.json"))
    video_id = run(output_dir, video_path, thumbnail_path, metadata_path)
    update_step(output_dir, 6, "running", video_id=video_id)


# ── 인터랙티브 터미널 모드 ───────────────────────────────────

def run_pipeline_interactive(
    output_dir: Path,
    start_step: int = 1,
    dry_run: bool = False,
    on_checkpoint: Callable[[str, Path], bool] | None = None,
) -> None:
    """
    체크포인트에서 승인을 기다리는 인터랙티브 파이프라인.

    Args:
        on_checkpoint: (checkpoint_name, output_dir) → bool
            True를 반환하면 승인, False면 중단.
            None이면 터미널 input()으로 대화형 처리.
    """
    # 상태 초기화 (start_step > 1이면 이전 단계는 done으로 마킹)
    state = load_state(output_dir)
    if state["current_step"] == 0:
        state = _initial_state(output_dir)
        for s in range(1, start_step):
            state["step_status"][str(s)] = "done"
        save_state(output_dir, state)

    # 순서 정의 (3→4 병렬 구조 반영)
    step_order = [1, 2, 3, 5, 6]  # 4는 3과 병렬 처리됨

    for step in step_order:
        if step < start_step:
            continue

        # 이전 체크포인트 승인 확인
        # step 3 실행 전: assets 체크포인트 (step 3 완료 후 필요)
        # step 5 실행 전: assets 체크가 됐는지 (assets 승인 → step 5 진행)
        prior_checkpoint = {
            3: None,   # 에셋 수집 전엔 승인 불필요
            5: "assets",   # 영상 편집 전엔 에셋 승인 필요
            6: "video",    # 업로드 전엔 영상 승인 필요
        }.get(step)

        if prior_checkpoint and not is_approved(output_dir, prior_checkpoint):
            console.print(f"\n[yellow]⚠ '{prior_checkpoint}' 체크포인트 승인 필요[/yellow]")
            break

        if step == 6 and dry_run:
            console.print("\n[bold yellow]━━ [6/6] 업로드 스킵 (dry-run 모드) ━━[/bold yellow]")
            break

        # 단계 실행
        run_step(step, output_dir)

        # 체크포인트 처리
        checkpoint = CHECKPOINTS.get(step)
        if checkpoint:
            approved = _handle_checkpoint(checkpoint, output_dir, on_checkpoint)
            if not approved:
                console.print(f"\n[yellow]파이프라인 일시 중지. 나중에 재개하려면 --step {step}을 사용하세요.[/yellow]")
                return
            approve_checkpoint(output_dir, checkpoint)


def _handle_checkpoint(
    checkpoint: str,
    output_dir: Path,
    on_checkpoint: Callable | None,
) -> bool:
    """체크포인트 처리 — 콜백 없으면 터미널 입력으로 처리."""
    label_map = {
        "script": "📝 대본을 확인하세요",
        "assets": "🎬 에셋 수집 결과를 확인하세요",
        "video": "🎥 영상을 확인하세요",
        "thumbnail": "🖼 썸네일을 확인하세요",
    }
    console.print(f"\n[bold cyan]{'='*50}[/bold cyan]")
    console.print(f"[bold cyan]✋ 체크포인트: {label_map.get(checkpoint, checkpoint)}[/bold cyan]")
    console.print(f"[dim]   결과물 위치: {output_dir}[/dim]")
    console.print(f"[bold cyan]{'='*50}[/bold cyan]")

    if on_checkpoint:
        return on_checkpoint(checkpoint, output_dir)

    # 터미널 대화형
    while True:
        answer = input("\n계속 진행하시겠습니까? [y/n/r(재생성)]: ").strip().lower()
        if answer in ("y", "yes", ""):
            return True
        elif answer in ("n", "no"):
            return False
        elif answer in ("r", "retry"):
            console.print("[yellow]재생성 기능은 Streamlit UI에서 사용하세요.[/yellow]")
        else:
            console.print("[dim]y(진행), n(중지) 중 하나를 입력하세요.[/dim]")
