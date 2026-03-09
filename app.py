"""
K-Content YouTube Shorts — Streamlit 미션 컨트롤 대시보드

실행:
    streamlit run app.py

탭 구성:
    📋 대시보드   — 파이프라인 상태 + 실행 버튼
    📝 대본       — 대본 읽기/수정/승인
    🎬 에셋       — 수집된 에셋 확인 + 승인
    🖼 썸네일     — 썸네일 확인 + 재생성 + 승인
    🎥 영상       — 영상 미리보기 + 승인
    📤 업로드     — 메타데이터 편집 + 업로드 실행
"""

import json
import threading
import time
from pathlib import Path
from datetime import date

import streamlit as st

import config
from src.pipeline_controller import (
    load_state, save_state, approve_checkpoint, is_approved,
    run_step, STEP_NAMES, CHECKPOINTS, get_next_pending_step, _initial_state
)
from src.seo_optimizer import score_metadata, optimize_metadata, get_score_badge

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="K-Content Mission Control",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 로그인 게이트 ────────────────────────────────────────────
def _check_login() -> bool:
    """비밀번호 로그인 게이트. session_state + bcrypt 기반 커스텀 구현."""

    # 이미 로그인된 경우
    if st.session_state.get("authenticated"):
        if st.sidebar.button("🚪 로그아웃"):
            st.session_state["authenticated"] = False
            st.rerun()
        return True

    # 로그인 UI
    st.markdown("## 🎬 K-Content Mission Control")
    st.markdown("---")
    col, _ = st.columns([1, 2])
    with col:
        st.markdown("### 🔒 로그인")
        password = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", type="primary", use_container_width=True):
            # Secrets 또는 기본값에서 해시 읽기
            try:
                pw_hash = st.secrets.get(
                    "AUTH_PASSWORD_HASH",
                    "$2b$12$T2LBSAUwBwqe04QxeF18QO5OMZZdSRYg0Ux8mv5xT3T/rg0hKOlym"
                )
            except Exception:
                pw_hash = "$2b$12$T2LBSAUwBwqe04QxeF18QO5OMZZdSRYg0Ux8mv5xT3T/rg0hKOlym"

            try:
                import bcrypt
                ok = bcrypt.checkpw(password.encode(), pw_hash.encode())
            except Exception:
                # bcrypt 없으면 평문 비교 (fallback)
                ok = (password == st.secrets.get("AUTH_PASSWORD", "admin123"))

            if ok:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀렸습니다.")

    st.stop()
    return False

if not _check_login():
    st.stop()


# ── CSS 커스텀 스타일 ─────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] {background: #0d0d1a;}
    .step-done   {color: #22c55e; font-weight: bold;}
    .step-running{color: #3b82f6; font-weight: bold; animation: pulse 1s infinite;}
    .step-wait   {color: #f59e0b; font-weight: bold;}
    .step-fail   {color: #ef4444; font-weight: bold;}
    .step-pend   {color: #6b7280;}
    @keyframes pulse {0%,100%{opacity:1} 50%{opacity:.4}}
    .checkpoint-badge {
        background: #f59e0b22; border: 1px solid #f59e0b;
        border-radius: 8px; padding: 12px 16px; margin: 8px 0;
    }
    .metric-card {
        background: #1e1e2e; border-radius: 12px;
        padding: 16px; text-align: center;
    }
    .step-card-done { border: 2px solid #22c55e; background: #22c55e18; border-radius: 10px; padding: 10px; margin: 4px 0; }
    .step-card-running { border: 2px solid #3b82f6; background: #3b82f618; border-radius: 10px; padding: 10px; margin: 4px 0; animation: pulse 1.5s infinite; }
    .step-card-waiting_review { border: 2px solid #f59e0b; background: #f59e0b18; border-radius: 10px; padding: 10px; margin: 4px 0; }
    .step-card-failed { border: 2px solid #ef4444; background: #ef444418; border-radius: 10px; padding: 10px; margin: 4px 0; }
    .step-card-pending { border: 2px solid #4b5563; background: #1f293722; border-radius: 10px; padding: 10px; margin: 4px 0; }
    .step-status-badge { font-size: 0.7em; font-weight: bold; padding: 2px 6px; border-radius: 4px; }
    .step-status-done { color: #22c55e; }
    .step-status-running { color: #3b82f6; }
    .step-status-waiting_review { color: #f59e0b; }
    .step-status-failed { color: #ef4444; }
    .step-status-pending { color: #9ca3af; }
</style>
""", unsafe_allow_html=True)


# ── 유틸리티 ─────────────────────────────────────────────────

def get_output_dir() -> Path:
    selected = st.session_state.get("selected_date", date.today().isoformat())
    d = config.OUTPUT_DIR / selected
    d.mkdir(parents=True, exist_ok=True)
    (d / "assets").mkdir(exist_ok=True)
    return d


def get_log_path(output_dir: Path) -> Path:
    return output_dir / "pipeline_log.txt"


def _render_next_step_button(output_dir: Path, key: str) -> None:
    """실제 다음 단계가 있을 때만 실행 버튼 표시. 승인 대기 시 비활성화."""
    state = load_state(output_dir)
    statuses = state.get("step_status", {})
    running = any(v == "running" for v in statuses.values())
    next_step = get_next_pending_step(output_dir)
    if next_step is not None:
        if st.button(f"▶ [{next_step}/6] {STEP_NAMES[next_step]} 실행", type="primary", use_container_width=True, disabled=running, key=key):
            _trigger_step_run(next_step, output_dir)
            st.rerun()
    else:
        if running:
            st.caption("⏳ 다른 단계 실행 중...")
        else:
            st.info("✋ 승인 후 진행 — 위 탭에서 검토 후 승인해주세요.")


def _trigger_step_run(step_num: int, output_dir: Path) -> None:
    """단계 실행 트리거: 상태 저장 후 run_step_async 호출."""
    state_w = load_state(output_dir)
    state_w["step_status"][str(step_num)] = "running"
    state_w["error"] = None
    from src.pipeline_controller import CHECKPOINTS
    for s, cp in CHECKPOINTS.items():
        if s == step_num:
            state_w["checkpoints"][cp] = False
    for s in range(1, step_num):
        if state_w["step_status"].get(str(s)) == "pending":
            state_w["step_status"][str(s)] = "done"
    save_state(output_dir, state_w)
    cache_keys = {
        2: ["script_editor", "script_ko_display", "_script_mtime", "_pending_script_en",
            "news_combined"] + [f"article_body_{j}" for j in range(10)],
    }
    for k in cache_keys.get(step_num, []):
        st.session_state.pop(k, None)
    run_step_async(step_num, output_dir)


def run_step_async(step: int, output_dir: Path):
    """Streamlit에서 단계를 백그라운드 스레드로 실행. 로그를 파일에 기록."""
    import io
    from rich.console import Console as RichConsole

    # 이미 실행 중인 스레드가 있으면 중복 실행 방지
    thread_name = f"step_{step}"
    for t in threading.enumerate():
        if t.name == thread_name and t.is_alive():
            return  # 이미 실행 중

    log_path = get_log_path(output_dir)

    def _run():
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n{'='*50}\n[단계 {step}] 시작 ({time.strftime('%H:%M:%S')})\n{'='*50}\n")
            log_file.flush()

            # rich 출력을 파일로 리디렉션
            file_console = RichConsole(file=log_file, highlight=False, markup=False)
            import src.pipeline_controller as pc
            original_console = pc.console
            pc.console = file_console

            # 각 src 모듈 console도 교체
            import src.asset_collector, src.research, src.generator, src.media_creator, src.video_editor
            for mod in [src.asset_collector, src.research, src.generator, src.media_creator, src.video_editor]:
                if hasattr(mod, 'console'):
                    setattr(mod, '_orig_console', mod.console)
                    setattr(mod, 'console', file_console)

            try:
                run_step(step, output_dir)
                log_file.write(f"\n[단계 {step}] ✅ 완료 ({time.strftime('%H:%M:%S')})\n")
            except Exception as e:
                log_file.write(f"\n[단계 {step}] ❌ 오류: {e}\n")
                import traceback
                log_file.write(traceback.format_exc())
                # running 상태로 멈추지 않도록 failed로 강제 설정
                from src.pipeline_controller import load_state, save_state
                s = load_state(output_dir)
                if s["step_status"].get(str(step)) == "running":
                    s["step_status"][str(step)] = "failed"
                    s["error"] = str(e)
                    save_state(output_dir, s)
            finally:
                pc.console = original_console
                for mod in [src.asset_collector, src.research, src.generator, src.media_creator, src.video_editor]:
                    if hasattr(mod, '_orig_console'):
                        mod.console = mod._orig_console
                log_file.flush()

    t = threading.Thread(target=_run, daemon=True, name=thread_name)
    t.start()


def step_icon(status: str) -> str:
    return {
        "done": "✅",
        "running": "⏳",
        "waiting_review": "✋",
        "failed": "❌",
        "pending": "⬜",
    }.get(status, "⬜")


def step_color_class(status: str) -> str:
    return {
        "done": "step-done",
        "running": "step-running",
        "waiting_review": "step-wait",
        "failed": "step-fail",
        "pending": "step-pend",
    }.get(status, "step-pend")


# ── 사이드바 ─────────────────────────────────────────────────

def render_sidebar(state: dict, output_dir: Path):
    with st.sidebar:
        st.markdown("## 🎬 Mission Control")
        st.divider()

        # 날짜 선택
        available_dates = sorted(
            [d.name for d in config.OUTPUT_DIR.iterdir() if d.is_dir()],
            reverse=True
        ) if config.OUTPUT_DIR.exists() else []
        today_str = date.today().isoformat()
        if today_str not in available_dates:
            available_dates = [today_str] + available_dates

        selected = st.selectbox(
            "날짜 선택",
            available_dates,
            index=0,
            key="selected_date",
        )

        st.divider()

        # 파이프라인 진행 상태
        st.markdown("### 진행 상황")
        statuses = state.get("step_status", {})

        step_display = [1, 2, "cp_script", 3, "cp_assets", 4, "cp_thumbnail", 5, "cp_video", 6]
        for item in step_display:
            if isinstance(item, str) and item.startswith("cp_"):
                cp = item[3:]
                approved = state.get("checkpoints", {}).get(cp, False)
                icon = "✅" if approved else "✋"
                label = {
                    "script": "대본 승인",
                    "assets": "에셋 승인",
                    "thumbnail": "썸네일 승인",
                    "video": "영상 승인",
                }.get(cp, cp)
                color = "#22c55e" if approved else "#f59e0b"
                st.markdown(
                    f'<span style="color:{color};font-size:0.85em">&nbsp;&nbsp;&nbsp;{icon} {label}</span>',
                    unsafe_allow_html=True
                )
            else:
                s = str(item)
                status = statuses.get(s, "pending")
                icon = step_icon(status)
                name = STEP_NAMES.get(item, "")
                st.markdown(
                    f'<span style="font-size:0.9em">{icon} [{item}/6] {name}</span>',
                    unsafe_allow_html=True
                )

        st.divider()

        # 실시간 로그
        log_path = get_log_path(output_dir)
        running = any(v == "running" for v in statuses.values())
        if log_path.exists():
            with st.expander("📋 실행 로그", expanded=running):
                log_text = log_path.read_text(encoding="utf-8")
                # 마지막 60줄만 표시
                lines = log_text.strip().splitlines()
                st.code("\n".join(lines[-60:]), language=None)
                if st.button("🗑 로그 지우기", key="clear_log"):
                    log_path.unlink()
                    st.rerun()

        # 에러 표시
        if state.get("error"):
            st.error(f"오류: {state['error']}")

        # 실행 중 표시
        if any(v == "running" for v in statuses.values()):
            st.caption("⏳ 실행 중...")


# ── 탭 1: 대시보드 ───────────────────────────────────────────

def render_dashboard(state: dict, output_dir: Path):
    st.header("📋 파이프라인 대시보드")

    # 메트릭 카드
    statuses = state.get("step_status", {})
    done_count = sum(1 for v in statuses.values() if v == "done")
    waiting_count = sum(1 for v in statuses.values() if v == "waiting_review")
    failed_count = sum(1 for v in statuses.values() if v == "failed")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("완료 단계", f"{done_count}/6", help="완료된 파이프라인 단계 수")
    with col2:
        st.metric("승인 대기", waiting_count, help="사람 검토가 필요한 단계")
    with col3:
        st.metric("오류", failed_count, help="실패한 단계 수")
    with col4:
        approved_count = sum(1 for v in state.get("checkpoints", {}).values() if v)
        st.metric("체크포인트 승인", f"{approved_count}/4", help="승인된 체크포인트 수")

    st.divider()

    # 실행 컨트롤 — 단계별 실행만 (상단 배너에서 전체 상태 확인)
    running = any(v == "running" for v in statuses.values())
    col_reset, _ = st.columns([1, 3])
    with col_reset:
        if st.button("🔄 전체 초기화", use_container_width=True):
            save_state(output_dir, _initial_state(output_dir))
            # 모든 위젯 캐시 초기화
            for k in list(st.session_state.keys()):
                if k != "selected_date":
                    del st.session_state[k]
            st.rerun()

    # 단계별 개별 실행
    st.subheader("▶ 단계별 실행")
    st.caption("클릭 시 해당 단계 실행/재실행 | ✅완료 ⏳실행중 ✋승인대기 ❌실패 ⬜대기")
    step_cols = st.columns(6)
    STATUS_LABELS = {"done": "완료", "running": "실행중", "waiting_review": "승인대기", "failed": "실패", "pending": "대기"}
    for i, (col, (step_num, step_name)) in enumerate(zip(step_cols, STEP_NAMES.items())):
        with col:
            status = statuses.get(str(step_num), "pending")
            icon = {"done": "✅", "running": "⏳", "waiting_review": "✋", "failed": "❌", "pending": "⬜"}.get(status, "⬜")
            status_text = STATUS_LABELS.get(status, "대기")
            card_class = f"step-card-{status}"
            st.markdown(
                f'<div class="{card_class}" style="text-align:center;">'
                f'<div class="step-status-{status}" style="font-size:0.75em;margin-bottom:4px;">{icon} {status_text}</div>'
                f'<div style="font-weight:bold;font-size:0.9em;">[{step_num}/6] {step_name[:14]}{"…" if len(step_name)>14 else ""}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            label = "재실행" if status in ("done", "waiting_review", "failed") else "실행"
            if st.button(f"{label}", key=f"step_btn_{step_num}", use_container_width=True, disabled=running, type="secondary"):
                _trigger_step_run(step_num, output_dir)
                st.rerun()

    st.divider()

    # ── 토픽 선택 섹션 ──────────────────────────────────────────
    topics_path = output_dir / "trending_topics.json"
    step1_done = statuses.get("1") == "done"

    if step1_done and topics_path.exists():
        try:
            topics = json.loads(topics_path.read_text(encoding="utf-8"))
        except Exception:
            topics = []

        if topics:
            st.subheader("📊 수집된 트렌딩 토픽 — 주제를 선택하세요")
            st.caption("GPT가 Reddit·YouTube·Google Trends에서 분석한 결과입니다. 마음에 드는 주제를 선택하면 해당 주제로 대본을 생성합니다.")

            selected_idx = state.get("results", {}).get("selected_topic_index", None)

            cols = st.columns(len(topics))
            for i, (col, topic) in enumerate(zip(cols, topics)):
                with col:
                    score = topic.get("virality_score", 0)
                    score_color = "#22c55e" if score >= 8 else "#f59e0b" if score >= 6 else "#6b7280"
                    is_selected = selected_idx == i

                    border_color = "#3b82f6" if is_selected else "#2d2d3d"
                    bg_color = "#1a2540" if is_selected else "#1a1a2e"

                    st.markdown(
                        f"""<div style='border:2px solid {border_color};border-radius:12px;
                        padding:14px;background:{bg_color};min-height:220px;margin-bottom:8px;'>
                        <div style='font-size:0.75em;color:{score_color};font-weight:bold;'>
                            🔥 바이럴 점수 {score}/10
                        </div>
                        <div style='font-size:0.9em;font-weight:bold;margin:6px 0;line-height:1.4;'>
                            {topic.get('headline','N/A')}
                        </div>
                        <div style='font-size:0.82em;color:#a78bfa;font-weight:600;margin-bottom:6px;'>
                            {topic.get('headline_ko','') or ''}
                        </div>
                        <div style='font-size:0.78em;color:#9ca3af;line-height:1.5;'>
                            {topic.get('summary','')[:100]}...
                        </div>
                        <div style='font-size:0.76em;color:#7c8fa0;line-height:1.5;margin-top:4px;'>
                            {topic.get('summary_ko','')[:100] or ''}
                        </div>
                        <div style='border-top:1px solid #2d2d3d;margin-top:8px;padding-top:6px;'>
                        <div style='font-size:0.72em;color:#6b7280;'>
                            {topic.get('why_viral','')}
                        </div>
                        <div style='font-size:0.71em;color:#5b6670;margin-top:2px;'>
                            {topic.get('why_viral_ko','') or ''}
                        </div>
                        </div>
                        </div>""",
                        unsafe_allow_html=True
                    )

                    btn_label = "✅ 선택됨" if is_selected else f"이 주제로 진행"
                    btn_type = "primary" if not is_selected else "secondary"
                    if st.button(btn_label, key=f"topic_select_{i}",
                                 use_container_width=True, type=btn_type,
                                 disabled=is_selected):
                        state_w = load_state(output_dir)
                        state_w["results"]["selected_topic_index"] = i
                        # step2가 이미 실행됐으면 리셋
                        if state_w["step_status"].get("2") in ("done", "waiting_review", "failed"):
                            state_w["step_status"]["2"] = "pending"
                            state_w["checkpoints"]["script"] = False
                        save_state(output_dir, state_w)
                        st.rerun()

            if selected_idx is not None:
                selected_topic = topics[selected_idx]
                st.success(
                    f"✅ 선택됨: **{selected_topic.get('headline', '')}** "
                    f"— 대본 생성 버튼을 눌러 계속 진행하세요."
                )
            else:
                st.info("☝️ 위에서 주제를 선택한 후 대본 생성을 진행하세요.")

            # 한국어 번역 없으면 번역 추가 버튼 표시
            has_ko = all(t.get("headline_ko") for t in topics)
            if not has_ko:
                if st.button("🌐 토픽 한국어 번역 추가", type="secondary"):
                    with st.spinner("GPT로 한국어 번역 추가 중..."):
                        try:
                            from openai import OpenAI
                            client = OpenAI(api_key=config.OPENAI_API_KEY)
                            for t in topics:
                                if not t.get("headline_ko"):
                                    resp = client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=[{"role": "user", "content":
                                            f"Translate these to natural Korean (JSON only, no explanation):\n"
                                            f"headline: {t.get('headline','')}\n"
                                            f"summary: {t.get('summary','')}\n"
                                            f"why_viral: {t.get('why_viral','')}\n\n"
                                            f"Return JSON with keys: headline_ko, summary_ko, why_viral_ko"}],
                                        response_format={"type": "json_object"},
                                        temperature=0.3,
                                    )
                                    import json as _json
                                    ko = _json.loads(resp.choices[0].message.content)
                                    t.update(ko)
                            topics_path.write_text(
                                __import__('json').dumps(topics, indent=2, ensure_ascii=False),
                                encoding="utf-8"
                            )
                            st.success("✅ 한국어 번역 추가 완료!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"번역 실패: {e}")


    # 결과물 파일 목록
    st.subheader("📁 생성된 파일")
    result_files = [
        ("trending_topics.json", "📊 트렌딩 토픽"),
        ("script.txt", "📝 대본"),
        ("assets_plan.json", "🗂 에셋 플랜"),
        ("metadata.json", "🏷 메타데이터"),
        ("audio.mp3", "🎵 음성"),
        ("subtitle.srt", "💬 자막"),
        ("thumbnail.png", "🖼 썸네일"),
        ("final_video.mp4", "🎬 최종 영상"),
    ]

    for filename, label in result_files:
        fpath = output_dir / filename
        if fpath.exists():
            size = fpath.stat().st_size
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
            st.markdown(f"✅ **{label}** — `{filename}` ({size_str})")
        else:
            st.markdown(f"<span style='color:#6b7280'>⬜ {label} — {filename}</span>",
                        unsafe_allow_html=True)


# ── 탭 2: 대본 검토 ──────────────────────────────────────────

def translate_to_korean(text: str) -> str:
    """OpenAI로 대본을 한국어로 번역 (내용 파악용, 실제 영상은 영어로 사용)"""
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",  # 번역은 비용 절감을 위해 mini 사용
        messages=[
            {"role": "system", "content": "당신은 전문 번역가입니다. 영어 대본을 자연스러운 한국어로 번역하세요. 번역만 출력하고 설명은 하지 마세요."},
            {"role": "user", "content": f"다음 영어 유튜브 쇼츠 대본을 한국어로 번역해주세요:\n\n{text}"},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def translate_to_english(text: str) -> str:
    """OpenAI로 한국어 대본 초안을 매끄럽게 다듬고 영어로 번역"""
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system", 
                "content": "You are an expert scriptwriter and translator for viral K-content YouTube Shorts. The user will provide a Korean draft, which might be rough or fragmented. Your task is to connect the ideas smoothly, clear up the context, and translate it into a highly engaging, natural, and tension-filled English script. Ensure the flow is perfect for a fast-paced YouTube Shorts video. Output ONLY the final English text, no explanations."
            },
            {"role": "user", "content": f"다음 한국어 대본 초안의 문맥을 매끄럽게 다듬어서, 자연스럽고 긴장감 있는 영어 유튜브 쇼츠 대본으로 완성해주세요:\n\n{text}"},
        ],
        temperature=0.5,
    )
    return resp.choices[0].message.content.strip()


def render_script_review(state: dict, output_dir: Path):
    st.header("📝 대본 검토")
    _render_next_step_button(output_dir, "next_step_script")
    st.divider()

    script_path = output_dir / "script.txt"
    script_ko_path = output_dir / "script_ko.txt"
    news_context_path = output_dir / "news_context.txt"

    if not script_path.exists():
        st.warning("대본이 아직 생성되지 않았습니다. 파이프라인을 실행하세요.")
        return

    # ── 파일 변경 감지: script.txt가 외부(재생성)에서 바뀌면 세션 캐시 무효화 ──
    current_mtime = script_path.stat().st_mtime
    prev_mtime = st.session_state.get("_script_mtime")
    if prev_mtime is not None and current_mtime != prev_mtime:
        # 파일이 변경됨 → 캐시된 위젯 값 제거
        for k in ["script_editor", "script_ko_display", "_pending_script_en"]:
            st.session_state.pop(k, None)
    st.session_state["_script_mtime"] = current_mtime

    # 위젯 렌더 전에 pending 값 적용 (역적용 버튼용)
    if "_pending_script_en" in st.session_state:
        st.session_state["script_editor"] = st.session_state.pop("_pending_script_en")

    # 크롤링한 뉴스 기사 원문 보기
    news_articles_path = output_dir / "news_articles.json"
    if news_articles_path.exists() or news_context_path.exists():
        with st.expander("📰 대본 생성에 사용된 실제 뉴스 기사 확인", expanded=False):
            # 개별 기사 탭
            if news_articles_path.exists():
                try:
                    articles = json.loads(news_articles_path.read_text(encoding="utf-8"))
                except Exception:
                    articles = []
            else:
                articles = []

            if articles:
                tab_labels = [f"기사 {a['index']}" for a in articles] + ["📋 통합본 (GPT 입력)"]
                tabs = st.tabs(tab_labels)
                for i, article in enumerate(articles):
                    with tabs[i]:
                        st.markdown(f"**제목:** {article['title']}")
                        if article.get("url"):
                            st.markdown(f"[🔗 원문 보기]({article['url']})")
                        st.text_area(
                            "본문",
                            value=article["body"],
                            height=200,
                            disabled=False,
                            label_visibility="collapsed",
                            key=f"article_body_{i}",
                        )
                with tabs[-1]:
                    combined = news_context_path.read_text(encoding="utf-8") if news_context_path.exists() else ""
                    st.text_area(
                        "통합본",
                        value=combined,
                        height=300,
                        disabled=False,
                        label_visibility="collapsed",
                        key="news_combined",
                    )
            elif news_context_path.exists():
                st.text_area(
                    "뉴스 원문",
                    value=news_context_path.read_text(encoding="utf-8"),
                    height=250,
                    disabled=False,
                    label_visibility="collapsed",
                )

    # 리뷰 점수
    review_score = state.get("results", {}).get("review_score")
    if review_score:
        color = "#22c55e" if review_score >= 75 else "#f59e0b"
        st.markdown(
            f'<span style="color:{color};font-size:1.2em">AI 리뷰 점수: <b>{review_score}/100</b></span>',
            unsafe_allow_html=True
        )

    current_script = script_path.read_text(encoding="utf-8")
    word_count = len(current_script.split())
    st.markdown(f"**단어 수:** {word_count} / 목표: 150-160 단어")

    st.divider()

    # ── 2컬럼 레이아웃: 영어 | 한국어 ──
    col_en, col_ko = st.columns(2)

    with col_en:
        st.markdown("#### 🇺🇸 영어 원문 (실제 영상에 사용)")
        edited_script = st.text_area(
            "영어 대본 (수정 가능)",
            value=current_script,
            height=450,
            key="script_editor",
            label_visibility="collapsed",
        )

        if st.button("🌐 영어 대본을 한국어로 번역 (우측에 표시)", use_container_width=True, type="secondary"):
            with st.spinner("한국어로 번역 중..."):
                try:
                    translated = translate_to_korean(edited_script)
                    script_ko_path.write_text(translated, encoding="utf-8")
                    st.session_state["script_ko_display"] = translated
                    st.rerun()
                except Exception as e:
                    st.error(f"번역 실패: {e}")

    with col_ko:
        st.markdown("#### 🇰🇷 한국어 번역 (수정해서 영어로 역적용 가능)")
        ko_text = script_ko_path.read_text(encoding="utf-8") if script_ko_path.exists() else ""

        edited_ko_script = st.text_area(
            "한국어 번역 (수정 가능)",
            value=ko_text,
            height=450,
            key="script_ko_display",
            label_visibility="collapsed",
        )

        if st.button("🔄 한국어 수정을 영어 대본에 역적용", use_container_width=True, type="primary"):
            if edited_ko_script.strip():
                with st.spinner("영어로 치환 중..."):
                    try:
                        translated_en = translate_to_english(edited_ko_script)
                        script_path.write_text(translated_en, encoding="utf-8")
                        script_ko_path.write_text(edited_ko_script, encoding="utf-8")
                        st.session_state["_pending_script_en"] = translated_en
                        st.rerun()
                    except Exception as e:
                        st.error(f"번역 실패: {e}")
            else:
                st.warning("한국어 대본이 비어있습니다.")

    st.divider()

    # 액션 버튼
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("💾 수정사항 저장", use_container_width=True):
            script_path.write_text(edited_script, encoding="utf-8")
            # 원문 수정 시 번역 초기화
            if script_ko_path.exists():
                script_ko_path.unlink()
            st.success("저장 완료! (번역은 다시 생성하세요)")

    with col2:
        approved = is_approved(output_dir, "script")
        if not approved:
            if st.button("✅ 승인하고 다음 단계로", type="primary", use_container_width=True):
                # 1. 파일 저장
                script_path.write_text(edited_script, encoding="utf-8")
                
                # 2. 대본이 변경되었을 수 있으므로 유튜브 검색어(assets_plan.json)를 새 대본에 맞게 다시 추출 (토픽 불일치 방지)
                with st.spinner("새 대본에 맞춰 검색 키워드를 다시 추출 중입니다..."):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=config.OPENAI_API_KEY)
                        prompt = f"""Based on the following YouTube Shorts script, generate a JSON plan for visual media assets (images/videos) to display.
The script is about K-pop or K-content.
Return exactly 5-7 scenes.

Script:
{edited_script}

Format requirements:
Return JSON: {{"scenes": [{{"scene_id": 1, "description": "...", "youtube_query": "specific english search term", "youtube_query_ko": "한국어 검색어", "image_query": "fallback image term", "duration_hint": "3-5 seconds"}}, ...]}}
"""
                        resp = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt}],
                            response_format={"type": "json_object"},
                            temperature=0.7,
                        )
                        new_plan = resp.choices[0].message.content
                        assets_plan_path = output_dir / "assets_plan.json"
                        assets_plan_path.write_text(new_plan, encoding="utf-8")
                    except Exception as e:
                        st.error(f"검색어 재생성 실패 (기존 플랜 사용): {e}")

                # 3. 승인 처리 (다음 단계 자동 실행 방지, 수동 실행 유도)
                approve_checkpoint(output_dir, "script")
                st.success("✅ 대본 승인 완료! [파이프라인 대시보드]로 돌아가서 [3/6 에셋 수집]을 실행하세요.")
                time.sleep(1)
                st.rerun()
        else:
            st.success("✅ 이미 승인됨")

    with col3:
        if st.button("🔄 대본 재생성", use_container_width=True):
            state_w = load_state(output_dir)
            state_w["step_status"]["2"] = "running"
            state_w["checkpoints"]["script"] = False
            save_state(output_dir, state_w)
            if script_ko_path.exists():
                script_ko_path.unlink()
            # 세션 캐시 무효화 → 재생성 후 새 내용 표시
            for k in ["script_editor", "script_ko_display", "_script_mtime",
                      "news_combined"] + [f"article_body_{i}" for i in range(10)]:
                st.session_state.pop(k, None)
            run_step_async(2, output_dir)
            st.info("대본 재생성 중...")
            st.rerun()

    st.divider()

    # 메타데이터 — 제목 선택 + 미리보기
    metadata_path = output_dir / "metadata.json"
    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))

        st.divider()
        st.subheader("🔊 음성(TTS) 설정")
        import config
        current_speed = meta.get("tts_speed", config.TTS_SPEED)
        new_speed = st.slider(
            "영어 내레이션 속도", 
            min_value=0.5, max_value=2.0, value=float(current_speed), step=0.05,
            help="기본값은 .env의 TTS_SPEED입니다. 저장 후 [4/6 미디어 생성] 시 반영됩니다."
        )
        if new_speed != current_speed:
            meta["tts_speed"] = new_speed
            metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            
        title_options = meta.get("title_options", [])

        if title_options:
            st.subheader("🎬 YouTube 제목 선택 (3개 옵션)")
            st.caption("선택 후 아래에서 바로 수정하거나 재생성할 수 있습니다.")
            current_title = meta.get("title", title_options[0])

            try:
                default_idx = title_options.index(current_title)
            except ValueError:
                default_idx = 0

            chosen = st.radio(
                "제목 옵션",
                title_options,
                index=default_idx,
                label_visibility="collapsed",
            )

            # 선택된 제목 직접 수정
            edited_title = st.text_input(
                "✏️ 선택 후 직접 수정 가능",
                value=chosen,
                max_chars=80,
                key="title_edit_after_select",
            )

            col_t1, col_t2 = st.columns([1, 1])
            with col_t1:
                if st.button("💾 제목 저장", use_container_width=True, key="save_edited_title"):
                    meta["title"] = edited_title
                    metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                    st.success(f"✅ 저장: {edited_title}")
            with col_t2:
                if st.button("🔄 제목 3개 재생성", use_container_width=True, key="regen_titles"):
                    script_text2 = (output_dir / "script.txt").read_text(encoding="utf-8") if (output_dir / "script.txt").exists() else ""
                    news_context_path = output_dir / "news_context.txt"
                    news_articles_path = output_dir / "news_articles.json"
                    news_snippet = ""
                    if news_context_path.exists():
                        news_snippet = news_context_path.read_text(encoding="utf-8")[:800]
                    elif news_articles_path.exists():
                        try:
                            arts = json.loads(news_articles_path.read_text(encoding="utf-8"))
                            news_snippet = "\n".join(f"[{a.get('title','')}] {a.get('body','')[:200]}" for a in arts[:3])
                        except Exception:
                            pass
                    title_prompt_base = (
                        f"Generate 3 DIFFERENT YouTube Shorts title options.\n"
                        f"Rules: ONE word ALL CAPS. Max 60 chars. Specific detail. Avoid repeating: {edited_title}\n"
                        f"Script: {script_text2[:300]}\n"
                    )
                    if news_snippet:
                        title_prompt_base += (
                            f"\nNEWS CONTEXT (use the most click-worthy fact from this for your titles):\n{news_snippet}\n\n"
                            "The best title often comes FROM the news. What line would make YOU click? Avoid generic templates.\n"
                        )
                    title_prompt_base += 'Return JSON: {"title_options": ["...", "...", "..."]}'
                    with st.spinner("새 제목 생성 중..."):
                        try:
                            from openai import OpenAI as _OAI2
                            _c2 = _OAI2(api_key=config.OPENAI_API_KEY)
                            _r2 = _c2.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": title_prompt_base}],
                                response_format={"type": "json_object"},
                                temperature=1.0,
                            )
                            import json as _j2
                            new_opts = _j2.loads(_r2.choices[0].message.content).get("title_options", [])
                            if new_opts:
                                meta["title_options"] = new_opts
                                meta["title"] = new_opts[0]
                                metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                                st.rerun()
                        except Exception as e:
                            st.error(f"재생성 실패: {e}")
        else:
            st.subheader("🎬 YouTube 제목")

            # 편집 가능한 제목 input
            new_title = st.text_input(
                "제목 (직접 수정 가능)",
                value=meta.get("title", ""),
                max_chars=80,
                key="title_direct_edit",
            )
            col_save_title, col_gen = st.columns([1, 1])
            with col_save_title:
                if st.button("💾 제목 저장", use_container_width=True):
                    meta["title"] = new_title
                    metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                    st.success(f"저장: {new_title}")

            with col_gen:
                if st.button("✨ 제목 3개 자동생성", type="primary", use_container_width=True):
                    script_path2 = output_dir / "script.txt"
                    topic_data = state.get("results", {})
                    script_text = script_path2.read_text(encoding="utf-8") if script_path2.exists() else ""
                    news_context_path = output_dir / "news_context.txt"
                    news_articles_path = output_dir / "news_articles.json"
                    news_snippet = ""
                    if news_context_path.exists():
                        news_snippet = news_context_path.read_text(encoding="utf-8")[:800]
                    elif news_articles_path.exists():
                        try:
                            arts = json.loads(news_articles_path.read_text(encoding="utf-8"))
                            news_snippet = "\n".join(f"[{a.get('title','')}] {a.get('body','')[:200]}" for a in arts[:3])
                        except Exception:
                            pass
                    title_auto_prompt = (
                        f"Generate 3 DIFFERENT YouTube Shorts title options for this script.\n"
                        f"Rules: ONE word ALL CAPS. Max 60 chars. Specific detail.\n"
                        f"Current title: {meta.get('title', '')}\n"
                        f"Script (first 300 chars): {script_text[:300]}\n\n"
                    )
                    if news_snippet:
                        title_auto_prompt += (
                            f"NEWS CONTEXT (use the most click-worthy fact from this for your titles):\n{news_snippet}\n\n"
                            "The best title often comes FROM the news. What line would make YOU click? Avoid generic templates.\n"
                        )
                    title_auto_prompt += 'Return JSON: {"title_options": ["...", "...", "..."]}'
                    with st.spinner("GPT로 제목 3개 생성 중..."):
                        try:
                            from openai import OpenAI as _OAI
                            _client = _OAI(api_key=config.OPENAI_API_KEY)
                            _r = _client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": title_auto_prompt}],
                                response_format={"type": "json_object"},
                                temperature=0.9,
                            )
                            import json as _j
                            opts = _j.loads(_r.choices[0].message.content).get("title_options", [])
                            if opts:
                                meta["title_options"] = opts
                                meta["title"] = opts[0]
                                metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                                st.success("✅ 제목 3개 생성 완료! 페이지 새로고침...")
                                st.rerun()
                        except Exception as e:
                            st.error(f"생성 실패: {e}")

        # 단어수 / 예상 시간
        st.caption(f"📊 단어 수: {word_count}개 · 예상 낭독 시간: **약 {round(word_count/135*60)}초** (135wpm 기준)")
        st.text_area("설명", value=meta.get("description", ""), height=80, disabled=True)
        st.text_input("태그", value=meta.get("tags", ""), disabled=True)


# ── 탭 3: 에셋 확인 ──────────────────────────────────────────

def render_asset_review(state: dict, output_dir: Path):
    st.header("🎬 에셋 확인 및 배치")
    _render_next_step_button(output_dir, "next_step_asset")
    st.divider()

    assets_dir = output_dir / "assets"
    assets_plan_path = output_dir / "assets_plan.json"
    pool_json_path = output_dir / "asset_pool.json"

    if not assets_dir.exists():
        st.warning("에셋이 아직 수집되지 않았습니다. 파이프라인을 실행하세요.")
        return

    # 에셋 플랜 로드
    plan_scenes = []
    if assets_plan_path.exists():
        plan = json.loads(assets_plan_path.read_text(encoding="utf-8"))
        plan_scenes = plan.get("scenes", [])

    # 에셋 풀 로드
    pool_data = {}
    asset_pool = []
    assignments = {}
    if pool_json_path.exists():
        try:
            pool_data = json.loads(pool_json_path.read_text(encoding="utf-8"))
            asset_pool = pool_data.get("pool", [])
            assignments = pool_data.get("assignments", {})
        except Exception:
            pass

    # ═══ 섹션 1: 에셋 풀 — 영상/이미지 분리 표시 ═══
    video_pool = [a for a in asset_pool if a.get("type") == "video"]
    image_pool = [a for a in asset_pool if a.get("type") == "image"]
    st.markdown(f"**에셋 풀:** 🎬 영상 {len(video_pool)}개 + 📷 이미지 {len(image_pool)}개 = **총 {len(asset_pool)}개**")

    def _render_asset_grid(pool_subset, label):
        if not pool_subset:
            st.info(f"{label} 에셋이 없습니다.")
            return
        cols_per_row = 5
        rows = [pool_subset[i:i+cols_per_row] for i in range(0, len(pool_subset), cols_per_row)]
        for row in rows:
            grid_cols = st.columns(cols_per_row)
            for col, asset in zip(grid_cols, row):
                with col:
                    pool_idx = asset_pool.index(asset)
                    is_video = asset.get("type") == "video"
                    score = asset.get("score", 0)
                    ch_type = asset.get("channel_type", "")
                    type_icon = {"official": "🏢", "media": "📰", "fan": "👤"}.get(ch_type, "")
                    score_color = "#22c55e" if score >= 7 else "#f59e0b" if score >= 4 else "#6b7280"

                    asset_path = Path(asset.get("path", ""))
                    if is_video and asset_path.exists():
                        st.video(str(asset_path))
                    elif asset_path.exists():
                        st.image(str(asset_path), use_container_width=True)
                    else:
                        st.warning("파일 없음")

                    channel_display = asset.get("channel", "") or asset.get("reason", "")
                    st.markdown(
                        f"<div style='font-size:0.72em;line-height:1.3;'>"
                        f"<b>#{pool_idx+1}</b> {type_icon} "
                        f"<span style='color:{score_color}'>[{score}/10]</span><br>"
                        f"{asset.get('title','')[:30]}<br>"
                        f"<span style='color:#888'>{channel_display[:25]}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

    if asset_pool:
        asset_tabs = st.tabs(["🎬 영상 에셋", "📷 이미지 에셋"])
        with asset_tabs[0]:
            _render_asset_grid(video_pool, "영상")
        with asset_tabs[1]:
            _render_asset_grid(image_pool, "이미지")

    st.divider()

    # ═══ 섹션 3: 씬별 배치 (드롭다운) ═══
    st.subheader("🎯 씬별 에셋 배치")
    st.caption("AI가 자동 배치한 결과입니다. 드롭다운으로 변경할 수 있습니다.")

    pool_options = ["(없음)"] + [
        f"#{i+1} {('🎬' if a.get('type')=='video' else '📷')} [{a.get('score',0)}/10] {a.get('title','')[:40]}"
        for i, a in enumerate(asset_pool)
    ]

    new_assignments = {}
    for scene in plan_scenes:
        sid = scene.get("scene_id", 0)
        current_idx = assignments.get(str(sid))

        if current_idx is not None and 0 <= current_idx < len(asset_pool):
            default_select = current_idx + 1
        else:
            default_select = 0

        col_scene, col_select, col_preview = st.columns([2, 3, 2])
        with col_scene:
            st.markdown(f"**씬 {sid}**")
            st.caption(scene.get("description", "")[:60])

        with col_select:
            selected = st.selectbox(
                f"씬 {sid} 에셋",
                range(len(pool_options)),
                index=min(default_select, len(pool_options) - 1),
                format_func=lambda x: pool_options[x],
                key=f"scene_assign_{sid}",
                label_visibility="collapsed",
            )
            if selected > 0:
                new_assignments[str(sid)] = selected - 1

        with col_preview:
            if selected > 0 and (selected - 1) < len(asset_pool):
                asset = asset_pool[selected - 1]
                asset_path = Path(asset.get("path", ""))
                if asset.get("type") == "video" and asset_path.exists():
                    st.video(str(asset_path))
                elif asset_path.exists():
                    st.image(str(asset_path), use_container_width=True)
            else:
                for ext in [".mp4", ".jpg", ".jpeg", ".png"]:
                    f = assets_dir / f"scene_{sid:02d}{ext}"
                    if f.exists():
                        if ext == ".mp4":
                            st.video(str(f))
                        else:
                            st.image(str(f), use_container_width=True)
                        break

    # 배치 저장 버튼
    if st.button("💾 배치 저장 및 적용", use_container_width=True, type="primary"):
        pool_data["assignments"] = new_assignments
        pool_json_path.write_text(json.dumps(pool_data, indent=2, ensure_ascii=False), encoding="utf-8")

        import shutil
        for sid_str, pool_idx in new_assignments.items():
            if 0 <= pool_idx < len(asset_pool):
                src = Path(asset_pool[pool_idx].get("path", ""))
                ext = src.suffix
                sid = int(sid_str)
                for old_ext in [".mp4", ".jpg", ".jpeg", ".png"]:
                    old = assets_dir / f"scene_{sid:02d}{old_ext}"
                    if old.exists():
                        old.unlink()
                dest = assets_dir / f"scene_{sid:02d}{ext}"
                if src.exists():
                    shutil.copy2(src, dest)

        st.success("✅ 배치 저장 완료!")
        st.rerun()

    st.divider()

    # ═══ 섹션 4: 수동 파일 업로드 ═══
    with st.expander("📁 수동 파일 업로드 (에셋 교체)", expanded=False):
        all_scene_ids = [s.get("scene_id", 0) for s in plan_scenes]
        if all_scene_ids:
            target_scene = st.selectbox(
                "교체할 씬 번호", all_scene_ids,
                format_func=lambda sid: f"씬 {sid}: {next((s.get('description','')[:40] for s in plan_scenes if s.get('scene_id')==sid), '')}",
                key="upload_target_scene",
            )
            uploaded = st.file_uploader(
                f"씬 {target_scene} 파일",
                type=["mp4", "jpg", "jpeg", "png", "avif", "webp"],
                key="asset_uploader",
            )
            if uploaded and st.button("업로드 / 교체", type="primary", key="do_upload"):
                suffix = Path(uploaded.name).suffix.lower()
                for ext in [".jpg", ".jpeg", ".png", ".mp4", ".mov", ".avif", ".webp"]:
                    old = assets_dir / f"scene_{target_scene:02d}{ext}"
                    if old.exists():
                        old.unlink()
                dest = assets_dir / f"scene_{target_scene:02d}{suffix}"
                dest.write_bytes(uploaded.read())
                if suffix in [".avif", ".webp"]:
                    try:
                        from PIL import Image as _PIL
                        img = _PIL.open(dest).convert("RGB")
                        dest_jpg = dest.with_suffix(".jpg")
                        img.save(dest_jpg, "JPEG", quality=90)
                        dest.unlink()
                    except Exception as e:
                        st.warning(f"변환 실패, 원본 유지: {e}")
                st.success(f"✅ 저장 완료!")
                st.rerun()

    st.divider()

    # ═══ 섹션 5: 승인 ═══
    approved = is_approved(output_dir, "assets")
    if not approved:
        if st.button("✅ 에셋 확인 완료 — 승인", type="primary", use_container_width=True):
            approve_checkpoint(output_dir, "assets")
            st.success("✅ 에셋 승인! 영상 편집으로 진행하세요.")
            st.rerun()
    else:
        st.success("✅ 에셋 확인 완료")


# ── 탭 4: 썸네일 ─────────────────────────────────────────────

def _gpt_generate_thumb_texts(metadata: dict, script_text: str) -> list[str]:
    """GPT로 썸네일 문구 3개 생성"""
    from openai import OpenAI as _OAI
    client = _OAI(api_key=config.OPENAI_API_KEY)
    title = metadata.get("title", "")
    tags = metadata.get("tags", "")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content":
            f"Generate 3 short, impactful YouTube Shorts thumbnail text overlays for this K-content video.\n"
            f"Title: {title}\nTags: {tags}\nScript preview: {script_text[:200]}\n\n"
            f"Rules:\n"
            f"- English only\n"
            f"- 3-6 words max per option\n"
            f"- ALL CAPS for 1-2 key punch words (e.g. 'She KNEW all along')\n"
            f"- Emotionally charged: shock, curiosity, drama\n"
            f"- No hashtags, no punctuation except '...'\n"
            f"- Can include 1 emoji per option\n\n"
            f'Return JSON: {{"text_options": ["...", "...", "..."]}}'}],
        response_format={"type": "json_object"},
        temperature=1.0,
    )
    import json as _j
    return _j.loads(resp.choices[0].message.content).get("text_options", [])


def render_thumbnail_review(state: dict, output_dir: Path):
    st.header("🖼 썸네일 검토")
    _render_next_step_button(output_dir, "next_step_thumb")
    st.divider()

    thumbnail_path = output_dir / "thumbnail.png"
    assets_dir = output_dir / "assets"
    metadata_path = output_dir / "metadata.json"

    # ── 현재 썸네일 미리보기 (존재하면) ──
    if thumbnail_path.exists():
        col_prev, col_info = st.columns([1, 2])
        with col_prev:
            try:
                from PIL import Image as _PILImg
                import io as _io
                _img_data = thumbnail_path.read_bytes()
                _PILImg.open(_io.BytesIO(_img_data)).verify()  # 유효성 검사
                st.image(str(thumbnail_path), caption="현재 썸네일", use_container_width=True)
                size_kb = thumbnail_path.stat().st_size / 1024
                st.caption(f"{size_kb:.1f} KB")
            except Exception:
                st.warning("⚠️ 썸네일 파일이 손상되었습니다. 아래에서 다시 생성해주세요.")
                thumbnail_path.unlink(missing_ok=True)

        with col_info:
            approved = is_approved(output_dir, "thumbnail")
            if not approved:
                if st.button("✅ 썸네일 승인", type="primary", use_container_width=True, key="thumb_approve_top"):
                    approve_checkpoint(output_dir, "thumbnail")
                    st.success("✅ 승인 완료!")
                    st.rerun()
            else:
                st.success("✅ 이미 승인됨")

            # 수동 업로드
            uploaded_thumb = st.file_uploader("직접 업로드 (png/jpg)", type=["png", "jpg", "jpeg"], key="thumb_upload")
            if uploaded_thumb and st.button("썸네일 교체", key="thumb_replace"):
                thumbnail_path.write_bytes(uploaded_thumb.read())
                st.success("✅ 교체 완료!")
                st.rerun()
        st.divider()

    # ════════════════════════════════════════════
    # STEP 1 — 에셋 이미지 선택
    # ════════════════════════════════════════════
    st.subheader("📸 Step 1 · 베이스 이미지 선택")
    st.caption("수집된 에셋 중 썸네일 배경으로 사용할 이미지를 선택하세요.")

    # 에셋 이미지 파일 수집
    asset_images = []
    if assets_dir.exists():
        asset_images = sorted([
            f for f in assets_dir.iterdir()
            if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
        ])

    selected_asset = st.session_state.get("thumb_selected_asset")

    if not asset_images:
        st.warning("수집된 이미지 에셋이 없습니다. 에셋 수집을 먼저 진행하거나 수동으로 업로드하세요.")
    else:
        # 4열 그리드
        cols_per_row = 4
        rows = [asset_images[i:i+cols_per_row] for i in range(0, len(asset_images), cols_per_row)]
        for row in rows:
            grid_cols = st.columns(cols_per_row)
            for col, img_path in zip(grid_cols, row):
                with col:
                    is_sel = (selected_asset == str(img_path))
                    border = "3px solid #a78bfa" if is_sel else "2px solid #2d2d3d"
                    st.markdown(
                        f"<div style='border:{border};border-radius:8px;overflow:hidden;margin-bottom:4px;'>",
                        unsafe_allow_html=True,
                    )
                    st.image(str(img_path), use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    btn_label = "✅ 선택됨" if is_sel else "선택"
                    btn_type = "secondary" if is_sel else "primary"
                    if st.button(btn_label, key=f"asset_sel_{img_path.name}", use_container_width=True, type=btn_type):
                        st.session_state["thumb_selected_asset"] = str(img_path)
                        # 이미지 바꾸면 문구 초기화
                        st.session_state.pop("thumb_text_options", None)
                        st.session_state.pop("thumb_overlay_text", None)
                        st.rerun()

    if selected_asset:
        st.success(f"✅ 선택된 이미지: `{Path(selected_asset).name}`")

    # ════════════════════════════════════════════
    # STEP 2 — 문구 생성 및 선택
    # ════════════════════════════════════════════
    st.divider()
    st.subheader("✍️ Step 2 · 썸네일 문구 선택")
    st.caption("GPT가 3개의 임팩트 있는 문구를 생성합니다. 라디오로 선택하거나 직접 수정하세요.")

    text_options = st.session_state.get("thumb_text_options", [])

    col_gen1, col_gen2 = st.columns([1, 3])
    with col_gen1:
        if st.button("🤖 GPT 문구 3개 생성", type="primary", use_container_width=True):
            if not metadata_path.exists():
                st.error("metadata.json이 없습니다.")
            else:
                meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                script_path = output_dir / "script.txt"
                script_text = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
                with st.spinner("GPT 문구 생성 중..."):
                    try:
                        opts = _gpt_generate_thumb_texts(meta, script_text)
                        st.session_state["thumb_text_options"] = opts
                        if opts:
                            st.session_state["thumb_overlay_text"] = opts[0]
                        st.rerun()
                    except Exception as e:
                        st.error(f"생성 실패: {e}")

    if text_options:
        current_overlay = st.session_state.get("thumb_overlay_text", text_options[0])
        try:
            radio_idx = text_options.index(current_overlay)
        except ValueError:
            radio_idx = 0

        chosen = st.radio(
            "문구 옵션 (선택 시 아래 입력창에 반영됨)",
            text_options,
            index=radio_idx,
            key="thumb_radio",
        )
        
        # 라디오 선택이 바뀌면 text_input 입력값도 업데이트
        if chosen != current_overlay and getattr(st.session_state, "_last_radio", None) != chosen:
            st.session_state["thumb_overlay_text"] = chosen
            st.session_state["_last_radio"] = chosen
            st.rerun()

        edited_text = st.text_input(
            "✏️ 직접 수정 (수정 후 엔터)",
            value=st.session_state.get("thumb_overlay_text", chosen),
            max_chars=60,
        )
        
        if edited_text != st.session_state.get("thumb_overlay_text"):
            st.session_state["thumb_overlay_text"] = edited_text

    else:
        # GPT 생성 없이 직접 입력도 가능
        manual_text = st.text_input(
            "문구 직접 입력 (엔터 필수)",
            value=st.session_state.get("thumb_overlay_text", ""),
            max_chars=60,
        )
        if manual_text != st.session_state.get("thumb_overlay_text"):
            st.session_state["thumb_overlay_text"] = manual_text

    if st.button("✅ 현재 문구로 확정"):
        st.success(f"문구가 확정되었습니다: **{st.session_state.get('thumb_overlay_text', '')}**")


    # ════════════════════════════════════════════
    # STEP 3 — Gemini 썸네일 합성
    # ════════════════════════════════════════════
    st.divider()
    st.subheader("🎨 Step 3 · Gemini 썸네일 생성")

    overlay_text_final = st.session_state.get("thumb_overlay_text", "")
    asset_final = st.session_state.get("thumb_selected_asset")

    # 상태 요약
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if asset_final:
            st.info(f"🖼 베이스: `{Path(asset_final).name}`")
        else:
            st.warning("🖼 베이스 이미지: 미선택 (선택 없이 생성 가능)")
    with col_s2:
        if overlay_text_final:
            st.info(f"✍️ 문구: **{overlay_text_final}**")
        else:
            st.warning("✍️ 문구: 미입력 (Gemini가 자동 생성)")

    if st.button("🚀 Gemini로 썸네일 생성", type="primary", use_container_width=True):
        if not metadata_path.exists():
            st.error("metadata.json이 없습니다.")
        else:
            from src.media_creator import generate_thumbnail
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            with st.spinner("Gemini 썸네일 생성 중... (수 초 소요)"):
                try:
                    generate_thumbnail(
                        meta,
                        thumbnail_path,
                        base_image_path=Path(asset_final) if asset_final else None,
                        overlay_text=overlay_text_final if overlay_text_final else None,
                    )
                    # 승인 초기화 (새 썸네일 생성)
                    state_w = load_state(output_dir)
                    state_w["checkpoints"]["thumbnail"] = False
                    save_state(output_dir, state_w)
                    st.success("✅ 썸네일 생성 완료!")
                    st.rerun()
                except Exception as thumb_err:
                    st.error(f"❌ Gemini 썸네일 생성 실패:\n\n```\n{thumb_err}\n```")


# ── 탭 5: 영상 미리보기 ──────────────────────────────────────

def render_video_review(state: dict, output_dir: Path):
    st.header("🎥 영상 검토")
    _render_next_step_button(output_dir, "next_step_video")
    st.divider()

    assets_approved = is_approved(output_dir, "assets")
    thumbnail_approved = is_approved(output_dir, "thumbnail")

    if not assets_approved or not thumbnail_approved:
        missing = []
        if not assets_approved: missing.append("에셋")
        if not thumbnail_approved: missing.append("썸네일")
        st.warning(f"먼저 {', '.join(missing)} 체크포인트를 승인해주세요.")
        return

    # 영상 편집 버튼
    video_path = output_dir / "final_video.mp4"
    step5_status = state.get("step_status", {}).get("5", "pending")

    if step5_status in ("pending", "failed") or not video_path.exists():
        if step5_status == "failed":
            st.error("❌ 이전 영상 편집 실패. 로그를 확인하고 재시도하세요.")
        if st.button("▶ 영상 편집 시작" if step5_status != "failed" else "🔄 영상 편집 재시도", type="primary"):
            state_w = load_state(output_dir)
            state_w["step_status"]["5"] = "running"
            save_state(output_dir, state_w)
            run_step_async(5, output_dir)
            st.rerun()
        return
    elif step5_status == "running":
        st.info("⏳ 영상 편집 중...")
        time.sleep(3)
        st.rerun()
        return

    if not video_path.exists():
        st.error("영상 파일을 찾을 수 없습니다.")
        return

    # 영상 미리보기
    st.video(str(video_path))

    size_mb = video_path.stat().st_size / 1024 / 1024
    st.caption(f"파일 크기: {size_mb:.1f} MB | 경로: {video_path}")

    col1, col2 = st.columns(2)
    with col1:
        approved = is_approved(output_dir, "video")
        if not approved:
            if st.button("✅ 영상 승인 — 업로드 준비", type="primary", use_container_width=True):
                approve_checkpoint(output_dir, "video")
                st.success("✅ 영상 승인! 업로드 탭으로 이동하세요.")
                st.rerun()
        else:
            st.success("✅ 이미 승인됨")

    with col2:
        if st.button("🔄 영상 재렌더링", use_container_width=True):
            state_w = load_state(output_dir)
            state_w["step_status"]["5"] = "running"
            state_w["checkpoints"]["video"] = False
            save_state(output_dir, state_w)
            run_step_async(5, output_dir)
            st.info("재렌더링 시작...")
            st.rerun()


# ── 탭 6: 업로드 ─────────────────────────────────────────────

def render_upload(state: dict, output_dir: Path):
    st.header("📤 YouTube 업로드")
    _render_next_step_button(output_dir, "next_step_upload")
    st.divider()

    video_approved = is_approved(output_dir, "video")
    if not video_approved:
        st.warning("영상을 먼저 승인해주세요.")
        return

    metadata_path = output_dir / "metadata.json"
    video_path = output_dir / "final_video.mp4"
    thumbnail_path = output_dir / "thumbnail.png"

    if not metadata_path.exists():
        st.error("metadata.json이 없습니다.")
        return

    meta = json.loads(metadata_path.read_text(encoding="utf-8"))

    st.subheader("메타데이터 최종 편집")

    # SEO 최적화 점수 및 UI
    score, details = score_metadata(meta)
    st.markdown(f"### {get_score_badge(score)}")
    
    with st.expander("SEO 상세 리포트"):
        for k, (msg, pts) in details.items():
            color = "green" if "✅" in msg else ("orange" if "🟡" in msg else "red")
            st.markdown(f"- :{color}[{msg}]")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔍 GPT SEO 최적화", use_container_width=True):
            with st.spinner("SEO 최적화 중..."):
                topic = state.get("results", {}).get("selected_topic")
                script_path = output_dir / "script.txt"
                script_text = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
                
                meta = optimize_metadata(meta, topic=topic, script=script_text)
                metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("✅ 메타데이터 최적화 완료!")
            time.sleep(1)
            st.rerun()

    st.divider()

    title_len = len(meta.get("title", ""))
    title = st.text_input(f"제목 ({title_len}/55자 권장)", value=meta.get("title", ""))
    
    desc_str = meta.get("description", "")
    description = st.text_area("설명", value=desc_str, height=150)
    
    tags_str = meta.get("tags", "")
    st.text_input(f"태그 ({len(tags_str)}/500자)", value=tags_str, key="tags")
    privacy = st.selectbox(
        "공개 설정",
        ["private", "unlisted", "public"],
        index=["private", "unlisted", "public"].index(
            meta.get("privacy", config.UPLOAD_PRIVACY)
        ),
    )

    # 저장
    if st.button("💾 메타데이터 저장"):
        # UI에서 수정된 태그 가져오기
        updated_tags = st.session_state.tags
        meta.update({"title": title, "description": description, "tags": updated_tags})
        metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        st.success("저장 완료!")
        st.rerun()

    st.divider()

    # 업로드 결과 확인
    upload_result_path = output_dir / "upload_result.json"
    if upload_result_path.exists():
        result = json.loads(upload_result_path.read_text(encoding="utf-8"))
        st.success(f"✅ 이미 업로드됨!")
        video_id = result.get("video_id", "")
        url = result.get("url", f"https://youtube.com/shorts/{video_id}")
        st.markdown(f"[🔗 YouTube에서 보기]({url})")

        # 썸네일 + 다국어 적용
        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("🖼 썸네일 적용")
            if thumbnail_path.exists():
                st.image(str(thumbnail_path), width=180)
                if st.button("📤 썸네일 적용", type="primary", use_container_width=True):
                    with st.spinner("썸네일 적용 중..."):
                        try:
                            from src.uploader import get_authenticated_service, set_thumbnail
                            youtube = get_authenticated_service()
                            set_thumbnail(youtube, video_id, thumbnail_path)
                            st.success("✅ 썸네일 적용 완료!")
                        except Exception as e:
                            st.error(f"❌ 실패: {e}")
            else:
                st.warning("thumbnail.png 없음")

        with col_b:
            st.subheader("🌏 다국어 제목/설명")
            st.caption("일본·중국·동남아 7개 언어 자동 번역 등록")
            if st.button("🤖 GPT 번역 → YouTube 등록", type="primary", use_container_width=True):
                with st.spinner("번역 및 등록 중... (수 초 소요)"):
                    try:
                        from src.uploader import get_authenticated_service, translate_and_localize
                        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                        youtube = get_authenticated_service()
                        translate_and_localize(youtube, video_id, meta)
                        st.success("✅ 7개 언어 등록 완료! (ja·zh-Hans·zh-TW·fil·id·th·vi)")
                    except Exception as e:
                        st.error(f"❌ 실패: {e}")
        return

    # 업로드 버튼
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 YouTube 업로드", type="primary", use_container_width=True):
            updated_tags = st.session_state.tags
            meta.update({"title": title, "description": description, "tags": updated_tags})
            metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            state_w = load_state(output_dir)
            state_w["step_status"]["6"] = "running"
            save_state(output_dir, state_w)
            run_step_async(6, output_dir)
            st.rerun()

    with col2:
        if st.button("🧪 Dry Run (업로드 없이 체크)", use_container_width=True):
            st.info("✅ 모든 파일 준비 완료. 실제 업로드는 위 버튼을 사용하세요.")
            st.json({
                "video": str(video_path),
                "thumbnail": str(thumbnail_path),
                "title": title[:80] + "...",
                "privacy": privacy,
            })


# ── 메인 앱 ──────────────────────────────────────────────────

def _render_global_status_banner(state: dict, output_dir: Path) -> None:
    """상단 전역 상태 배너 — 실행중/승인대기/실패/완료 한눈에 표시."""
    statuses = state.get("step_status", {})
    running = any(v == "running" for v in statuses.values())
    waiting = any(v == "waiting_review" for v in statuses.values())
    failed = any(v == "failed" for v in statuses.values())
    all_done = all(v in ("done", "waiting_review") for v in statuses.values())

    if running:
        step = next((s for s, v in statuses.items() if v == "running"), None)
        name = STEP_NAMES.get(int(step), "") if step else ""
        st.info(f"⏳ **실행 중** — [{step}/6] {name} (자동 새로고침)")
    elif waiting:
        step = next((s for s, v in statuses.items() if v == "waiting_review"), None)
        name = STEP_NAMES.get(int(step), "") if step else ""
        st.warning(f"✋ **승인 대기** — [{step}/6] {name} 검토 후 승인 필요")
    elif failed:
        step = next((s for s, v in statuses.items() if v == "failed"), None)
        name = STEP_NAMES.get(int(step), "") if step else ""
        err = (state.get("error") or "")[:60]
        st.error(f"❌ **실패** — [{step}/6] {name} {err}")
    elif all_done:
        st.success("✅ **모든 단계 완료**")
    else:
        next_step = get_next_pending_step(output_dir)
        if next_step:
            st.caption(f"⬜ 대기 중 — 다음: [{next_step}/6] {STEP_NAMES[next_step]} 실행 가능")
        else:
            st.caption("⬜ 승인 후 진행 가능")


def main():
    output_dir = get_output_dir()
    state = load_state(output_dir)

    # 사이드바
    render_sidebar(state, output_dir)

    # 전역 상태 배너 (탭 위에 항상 표시)
    _render_global_status_banner(state, output_dir)
    st.divider()

    # 탭
    tabs = st.tabs(["📋 대시보드", "📝 대본", "🎬 에셋", "🖼 썸네일", "🎥 영상", "📤 업로드"])

    with tabs[0]:
        render_dashboard(state, output_dir)
    with tabs[1]:
        render_script_review(state, output_dir)
    with tabs[2]:
        render_asset_review(state, output_dir)
    with tabs[3]:
        render_thumbnail_review(state, output_dir)
    with tabs[4]:
        render_video_review(state, output_dir)
    with tabs[5]:
        render_upload(state, output_dir)

    # 자동 새로고침 — running 상태일 때만, 스레드 생존 체크 포함
    statuses = state.get("step_status", {})
    running_steps = [s for s, v in statuses.items() if v == "running"]
    if running_steps:
        # 스레드가 실제로 살아있는지 체크
        alive_threads = {t.name for t in threading.enumerate() if t.is_alive()}
        for step_s in running_steps:
            thread_name = f"step_{step_s}"
            if thread_name not in alive_threads:
                # 스레드가 죽음 → 파일에서 최신 상태 재로드 (정상 완료 시 done으로 이미 저장됨)
                state_w = load_state(output_dir)
                current_status = state_w["step_status"].get(step_s, "running")
                if current_status == "running":
                    # 파이프라인이 아직 업데이트 안 함 → 예기치 않은 종료로 간주
                    state_w["step_status"][step_s] = "failed"
                    state_w["error"] = state_w.get("error") or "스레드가 예기치 않게 종료됨 — 로그를 확인하세요"
                    save_state(output_dir, state_w)
                # done/waiting_review면 그대로 두고 새로고침만
                st.rerun()
                return
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()
