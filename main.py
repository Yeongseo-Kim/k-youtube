"""
K-Content YouTube Shorts Automation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

사용법:
  python main.py                   # 전체 파이프라인 실행
  python main.py --dry-run         # 업로드 단계 스킵 (테스트)
  python main.py --interactive     # 체크포인트에서 승인 대기 (인력 모드)
  python main.py --step 2          # 특정 단계부터 재개
  streamlit run app.py             # 웹 대시보드 실행 (추천)

파이프라인:
  [1] 뉴스 리서치   → trending_topics.json
  [2] 대본 생성     → script.txt + assets_plan.json + metadata.json
      └─ AI 리뷰어: 편집자가 대본 품질 검수 후 기준 미달 시 재생성
  [✋] CHECKPOINT 1: 대본 첨삭후 주광/승인
  [3] 에셋 수집     → assets/ (yt-dlp 클립 + 이미지)   ┐ 병렬 실행
  [4] 미디어 생성   → audio.mp3 + subtitle.srt + thumbnail.png ┘
      └─ AI 리뷰어: SEO 전문가가 메타데이터 최적화
  [✋] CHECKPOINT 2: 수집된 에셋 확인/승인
  [✋] CHECKPOINT 3: 썬네일 확인/승인
  [5] 영상 편집     → final_video.mp4
  [✋] CHECKPOINT 4: 영상 미리보기 후 승인
  [6] 유튜브 업로드 → YouTube 게시 완료
"""

import argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

import config

console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold cyan]K-Content YouTube Shorts[/bold cyan]\n"
        "[dim]Automation Pipeline v1.0[/dim]",
        border_style="blue"
    ))


def step1_research(output_dir: Path) -> Path:
    """[1] 뉴스 리서치"""
    from src.research import run
    return run(output_dir)


def step2_generate(output_dir: Path, topics_path: Path) -> tuple:
    """[2] 대본 생성 + AI 리뷰 루프"""
    from src import generator, reviewer

    console.print("\n[bold blue]━━ [2/6] 대본/프롬프트 생성 시작 ━━[/bold blue]")

    import json
    topics = json.loads(topics_path.read_text(encoding="utf-8"))
    topic = max(topics, key=lambda t: t.get("virality_score", 0))
    console.print(f"  [cyan]선택된 토픽: {topic.get('headline', 'N/A')}[/cyan]")

    # AI 리뷰 루프: 작성자 → 편집자 → 기준 미달 시 재생성
    def generate_script(feedback: str = "") -> str:
        """피드백 반영하여 대본 재생성"""
        result = generator.generate_script_and_plan(
            topic,
            feedback=feedback  # 편집자 피드백 전달
        )
        # 파일 저장
        (output_dir / "script.txt").write_text(result.get("script", ""), encoding="utf-8")
        (output_dir / "assets_plan.json").write_text(
            json.dumps({"scenes": result.get("scenes", [])}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        (output_dir / "metadata.json").write_text(
            json.dumps(result.get("metadata", {}), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return result.get("script", "")

    # 생성 → 리뷰 → 재생성 루프 (최대 3회)
    final_script, review = reviewer.evaluate_with_retry(
        role="script_editor",
        content_fn=generate_script,
        context=f"Topic: {topic.get('headline')}",
        max_retries=3,
    )

    script_path = output_dir / "script.txt"
    assets_plan_path = output_dir / "assets_plan.json"
    metadata_path = output_dir / "metadata.json"

    word_count = len(final_script.split())
    console.print(f"  [green]✓ 최종 대본: {word_count} words (리뷰 점수: {review.get('score', 0)}/100)[/green]")

    return script_path, assets_plan_path, metadata_path


def step3_collect_assets(output_dir: Path, assets_plan_path: Path) -> Path:
    """[3] 에셋 수집"""
    from src.asset_collector import run
    return run(output_dir, assets_plan_path)


def step4_create_media(output_dir: Path, script_path: Path, metadata_path: Path) -> tuple:
    """[4] 미디어 생성 (TTS + 자막 + 썸네일)"""
    from src.media_creator import run
    return run(output_dir, script_path, metadata_path)


def step5_edit_video(output_dir: Path, audio_path: Path, assets_dir: Path, subtitle_path: Path) -> Path:
    """[5] 영상 편집"""
    from src.video_editor import run
    return run(output_dir, audio_path, assets_dir, subtitle_path)


def step6_upload(output_dir: Path, video_path: Path, thumbnail_path: Path, metadata_path: Path) -> str:
    """[6] 유튜브 업로드"""
    from src.uploader import run
    return run(output_dir, video_path, thumbnail_path, metadata_path)


def run_pipeline(start_step: int = 1, dry_run: bool = False, interactive: bool = False):
    """전체 파이프라인 실행"""
    print_banner()

    # 설정 검증
    errors = config.validate()
    if errors and not dry_run:
        console.print("\n[bold red]⚠ 설정 오류:[/bold red]")
        for e in errors:
            console.print(f"  [red]• {e}[/red]")
        console.print("\n.env 파일을 확인하고 다시 실행하세요.")
        return

    output_dir = config.get_today_output_dir()
    console.print(f"\n[dim]출력 폴더: {output_dir}[/dim]")

    # ── 인터랙티브 모드: pipeline_controller 사용 ──
    if interactive:
        from src.pipeline_controller import run_pipeline_interactive
        run_pipeline_interactive(
            output_dir=output_dir,
            start_step=start_step,
            dry_run=dry_run,
        )
        return

    # ── 기존 일괄 실행 모드 ──
    start_time = datetime.now()

    try:
        # ── Step 1: 뉴스 리서치 ──
        if start_step <= 1:
            topics_path = step1_research(output_dir)
        else:
            topics_path = output_dir / "trending_topics.json"

        # ── Step 2: 대본 생성 + AI 리뷰 ──
        if start_step <= 2:
            script_path, assets_plan_path, metadata_path = step2_generate(output_dir, topics_path)
        else:
            script_path = output_dir / "script.txt"
            assets_plan_path = output_dir / "assets_plan.json"
            metadata_path = output_dir / "metadata.json"

        # ── Step 3 & 4: 에셋 수집 + 미디어 생성 (병렬 실행) ──
        if start_step <= 3:
            console.print("\n[bold magenta]━━ [3+4/6] 에셋 수집 & 미디어 생성 병렬 실행 ━━[/bold magenta]")

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 두 작업 동시 시작
                future_assets = executor.submit(step3_collect_assets, output_dir, assets_plan_path)
                future_media = executor.submit(step4_create_media, output_dir, script_path, metadata_path)

                # 결과 수집
                assets_dir = future_assets.result()
                audio_path, subtitle_path, thumbnail_path = future_media.result()

        else:
            assets_dir = output_dir / "assets"
            audio_path = output_dir / "audio.mp3"
            subtitle_path = output_dir / "subtitle.srt"
            thumbnail_path = output_dir / "thumbnail.png"

        # ── Step 5: 영상 편집 ──
        if start_step <= 5:
            video_path = step5_edit_video(output_dir, audio_path, assets_dir, subtitle_path)
        else:
            video_path = output_dir / "final_video.mp4"

        # ── Step 6: 유튜브 업로드 ──
        if dry_run:
            console.print("\n[bold yellow]━━ [6/6] 업로드 스킵 (--dry-run 모드) ━━[/bold yellow]")
            console.print(f"  [dim]영상 위치: {video_path}[/dim]")
            video_id = "DRY_RUN"
        elif start_step <= 6:
            video_id = step6_upload(output_dir, video_path, thumbnail_path, metadata_path)

        # ── 완료 ──
        elapsed = (datetime.now() - start_time).total_seconds()
        console.print(Panel.fit(
            f"[bold green]✓ 파이프라인 완료![/bold green]\n"
            f"[dim]소요 시간: {elapsed:.0f}초[/dim]\n"
            f"[dim]영상: {video_path}[/dim]\n"
            + (f"[cyan]YouTube: https://youtube.com/shorts/{video_id}[/cyan]"
               if video_id != "DRY_RUN" else "[yellow]업로드 스킵됨[/yellow]"),
            border_style="green"
        ))

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ 파이프라인이 중단되었습니다.[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]✗ 오류 발생: {e}[/bold red]")
        console.print("[dim]  --step 옵션으로 실패한 단계부터 재시작할 수 있습니다.[/dim]")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="K-Content YouTube Shorts 자동화 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py                # 전체 실행
  python main.py --dry-run      # 업로드 없이 테스트
  python main.py --step 3       # 에셋 수집 단계부터 재개
  python main.py --step 5       # 영상 편집부터 재개
        """
    )
    parser.add_argument("--dry-run", action="store_true", help="업로드 단계 스킵")
    parser.add_argument("--step", type=int, default=1, help="시작 단계 (1~6)")
    parser.add_argument("--interactive", action="store_true", help="체크포인트에서 승인 대기 (인터랙티브 모드)")
    args = parser.parse_args()

    run_pipeline(start_step=args.step, dry_run=args.dry_run, interactive=args.interactive)
