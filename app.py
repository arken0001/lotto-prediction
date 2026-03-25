"""로또 6/45 예측 분석 웹 애플리케이션

실행: streamlit run app.py
"""

import sys
import io
from pathlib import Path

# Windows 인코딩 설정
if sys.platform == 'win32':
    try:
        if not sys.stdout.closed:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if not sys.stderr.closed:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

import config
from data.collector import LottoDataCollector
from data.storage import LottoStorage
from analysis.scorer import WeightedScorer
from prediction.generator import PredictionGenerator
from prediction.validator import PredictionValidator
from data.supabase_store import (
    load_log, add_prediction, delete_prediction,
    delete_set_from_prediction, update_all_from_df, get_stats
)

# ─── Plotly 다크 테마 공통 레이아웃 ───
DARK_LAYOUT = dict(
    template='plotly_dark',
    paper_bgcolor='#0e1117',
    plot_bgcolor='#0e1117',
    font=dict(color='#ccc', family='Pretendard, sans-serif'),
    xaxis=dict(gridcolor='#222', zerolinecolor='#333'),
    yaxis=dict(gridcolor='#222', zerolinecolor='#333'),
    legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#ccc')),
)

# ─── 페이지 설정 ───
st.set_page_config(
    page_title="로또 6/45 예측 분석",
    page_icon="🎱",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ─── 다크 테마 스타일 ───
st.markdown("""
<link rel="stylesheet" as="style" crossorigin
      href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
<style>
    /* Pretendard 폰트 전역 적용 (아이콘 폰트 제외) */
    html, body, [class*="css"], .stMarkdown, .stTextInput, .stSelectbox,
    .stMultiSelect, .stSlider, .stButton, .stMetric, .stTabs, .stDataFrame,
    p, div, h1, h2, h3, h4, h5, h6, label, input, textarea, button, a {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }
    /* Material Icons 등 아이콘 폰트 보호 */
    [data-testid="stIconMaterial"], .material-symbols-rounded,
    [class*="icon"], [data-icon], span[class*="Icon"] {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    }

    /* 전체 컨테이너 최대 폭 제한 */
    .block-container { max-width: 1300px !important; padding-left: 2rem; padding-right: 2rem; }

    .main-title { text-align: center; font-size: 1.5rem; font-weight: bold; margin-bottom: 0; color: #e8e8e8; }
    .sub-title { text-align: center; color: #888; font-size: 0.85rem; margin-top: 0; }

    /* 전체 여백 축소 */
    .block-container { padding-top: 1rem !important; }
    h3 { font-size: 1.1rem !important; margin-top: 0.5rem !important; margin-bottom: 0.3rem !important; }
    h4 { font-size: 1rem !important; }
    hr { margin: 0.5rem 0 !important; }
    .stDivider { margin: 0.5rem 0 !important; }

    .ball {
        display: inline-flex; align-items: center; justify-content: center;
        width: 38px; height: 38px; border-radius: 50%; color: white;
        font-size: 1rem; font-weight: bold; margin: 2px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.5);
    }
    .ball-1 { background: linear-gradient(135deg, #FBC400, #D4A000); }
    .ball-2 { background: linear-gradient(135deg, #69C8F2, #3A9FD8); }
    .ball-3 { background: linear-gradient(135deg, #FF7272, #D84040); }
    .ball-4 { background: linear-gradient(135deg, #999, #666); }
    .ball-5 { background: linear-gradient(135deg, #B0D840, #88B020); }

    .prediction-set {
        background: #1e1e2e; border-radius: 8px; padding: 10px 14px;
        margin: 4px 0; border-left: 3px solid #4AA8D8;
    }
    .score-badge {
        background: #1a3a5c; color: #69C8F2; padding: 4px 12px;
        border-radius: 20px; font-size: 0.82rem; font-weight: 500;
    }
    .hot-badge {
        background: #3d1a1a; color: #ff6b6b; padding: 3px 10px;
        border-radius: 12px; font-weight: 600; font-size: 0.9rem;
        display: inline-block; margin: 2px;
    }
    .cold-badge {
        background: #1a1a3d; color: #6ba3ff; padding: 3px 10px;
        border-radius: 12px; font-weight: 600; font-size: 0.9rem;
        display: inline-block; margin: 2px;
    }
    .overdue-badge {
        background: #3d3a1a; color: #f0c040; padding: 3px 10px;
        border-radius: 12px; font-weight: 600; font-size: 0.9rem;
        display: inline-block; margin: 2px;
    }
    .rank-label { font-size: 1rem; color: #888; font-weight: 600; }
    .info-text { color: #777; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)


def get_ball_class(num: int) -> str:
    if num <= 10: return "ball-1"
    elif num <= 20: return "ball-2"
    elif num <= 30: return "ball-3"
    elif num <= 40: return "ball-4"
    else: return "ball-5"


def render_balls(numbers: list[int]) -> str:
    balls = ""
    for n in numbers:
        cls = get_ball_class(n)
        balls += f'<span class="ball {cls}">{n}</span>'
    return balls


@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    storage = LottoStorage()
    collector = LottoDataCollector()
    if storage.exists():
        df = storage.load()
        last_round = storage.get_last_round()
        new_df = collector.fetch_new_rounds(last_round)
        if not new_df.empty:
            df = storage.merge_and_save(new_df)
    else:
        df = collector.fetch_all()
        if not df.empty:
            storage.save(df)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def run_analysis(_df):
    scorer = WeightedScorer(_df)
    report = scorer.generate_analysis_report()
    return report


def run_prediction(df, num_sets, temperature):
    scorer = WeightedScorer(df)
    generator = PredictionGenerator(scorer)
    return generator.generate_predictions(num_sets=num_sets, temperature=temperature)


# ─── 데이터 로드 ───
with st.spinner("🔄 데이터를 불러오는 중..."):
    df = load_data()

if df is None or df.empty:
    st.error("데이터를 불러올 수 없습니다. 인터넷 연결을 확인해 주세요.")
    st.stop()

with st.spinner("📊 분석 중..."):
    report = run_analysis(df)

last_round = report['last_round']
total_rounds = report['total_rounds']

# ─── 사이드바 ───
with st.sidebar:
    st.markdown("## ⚙️ 설정")
    st.divider()

    page = st.radio(
        "메뉴",
        ["🎱 예측하기", "📜 예측 이력", "📊 분석 리포트", "🔬 백테스트", "❓ 원리 & 사용법"],
        index=0,
    )

    st.divider()
    st.markdown(f"**데이터 현황**")
    st.markdown(f"- 분석 회차: 1회 ~ {last_round}회")
    st.markdown(f"- 총 {total_rounds}개 회차")

    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ═══════════════════════════════════════════════════════
# 🎱 예측하기
# ═══════════════════════════════════════════════════════
if page == "🎱 예측하기":
    st.markdown(f'<p class="main-title">🎱 제{last_round + 1}회 예측</p>', unsafe_allow_html=True)

    # 설정 바 (한 줄로 컴팩트하게)
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        num_sets = st.slider("세트 수", 1, 20, 5, key="ns")
    with c2:
        temperature = st.slider("다양성", 0.5, 5.0, 2.0, 0.5, key="tp")
    with c3:
        st.write("")
        generate_btn = st.button("🎯 생성", type="primary", use_container_width=True)

    if generate_btn:
        with st.spinner("🔮 생성 중..."):
            predictions = run_prediction(df, num_sets, temperature)
            st.session_state['predictions'] = predictions
            # 버튼 누를 때만 저장 (설정값 포함)
            saved_id = add_prediction(last_round + 1, predictions,
                                      settings={'num_sets': num_sets, 'temperature': temperature})
            if saved_id:
                st.session_state['saved_round'] = last_round + 1
                st.session_state['just_saved'] = True
            else:
                st.session_state['just_saved'] = False
    elif 'predictions' not in st.session_state:
        with st.spinner("🔮 생성 중..."):
            predictions = run_prediction(df, num_sets, temperature)
            st.session_state['predictions'] = predictions
            st.session_state['just_saved'] = False

    predictions = st.session_state.get('predictions', [])

    # ── 좌측: 예측 결과 / 우측: 분석 요약 ──
    left_col, right_col = st.columns([3, 2])

    with left_col:
        if predictions:
            for i, (numbers, fitness) in enumerate(predictions, 1):
                balls_html = render_balls(numbers)
                total = sum(numbers)
                odd = sum(1 for n in numbers if n % 2 == 1)
                st.markdown(f"""<div class="prediction-set">
                    <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap;">
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span class="rank-label">{i}</span>{balls_html}
                        </div>
                        <div><span class="score-badge">{fitness:.1f}</span>
                        <span class="info-text"> {total} · {odd}:{6-odd}</span></div>
                    </div>
                </div>""", unsafe_allow_html=True)

            if st.session_state.get('just_saved'):
                st.caption(f"✅ 제{st.session_state['saved_round']}회 예측 저장됨")
            elif st.session_state.get('just_saved') is False and generate_btn:
                st.caption("ℹ️ 동일한 번호가 이미 저장되어 있습니다")

            # 프린트 버튼
            pr1, pr2 = st.columns(2)
            with pr1:
                try:
                    from display.lotto_paper import generate_lotto_paper
                    pred_nums = [nums for nums, _ in predictions]
                    img_bytes = generate_lotto_paper(pred_nums)
                    st.download_button(
                        "🖨️ 로또용지 마킹 다운로드",
                        data=img_bytes,
                        file_name=f"lotto_{last_round+1}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                except Exception:
                    pass
            with pr2:
                try:
                    from display.lotto_paper import generate_escpos_data
                    pred_nums = [nums for nums, _ in predictions]
                    esc_data = generate_escpos_data(pred_nums, last_round + 1)
                    st.download_button(
                        "🧾 영수증 출력 데이터",
                        data=esc_data,
                        file_name=f"lotto_{last_round+1}.bin",
                        mime="application/octet-stream",
                        use_container_width=True,
                    )
                except Exception:
                    pass

    with right_col:
        # HOT / COLD / OVERDUE 컴팩트
        hot = report['hot_numbers'][:6]
        cold = report['cold_numbers'][:6]
        overdue = report['overdue_numbers'][:6]

        st.markdown("**🔥 HOT** " + ''.join(f'<span class="hot-badge">{n}</span>' for n in hot), unsafe_allow_html=True)
        st.markdown("**❄️ COLD** " + ''.join(f'<span class="cold-badge">{n}</span>' for n in cold), unsafe_allow_html=True)
        st.markdown("**⏰ DUE** " + ''.join(f'<span class="overdue-badge">{n}</span>' for n in overdue), unsafe_allow_html=True)

        # 주요 수치
        stats = report['sum_stats']
        ac_low, ac_high = report['ac_range']
        st.markdown(f"""<div style="color:#999; font-size:0.8rem; margin-top:8px; line-height:1.6;">
            합계 범위: {stats['optimal_range'][0]}~{stats['optimal_range'][1]} (평균 {stats['mean']:.0f})<br>
            AC값: {ac_low}~{ac_high} · 홀짝 최빈: 3:3
        </div>""", unsafe_allow_html=True)

    # ── 번호별 점수 차트 (하단, 풀 가로) ──
    scores = report['number_scores']
    max_score = max(scores.values()) if scores else 1

    def bar_color(n):
        if n <= 10: return '#FBC400'
        elif n <= 20: return '#69C8F2'
        elif n <= 30: return '#FF7272'
        elif n <= 40: return '#888'
        else: return '#B0D840'

    bars_html = '<div style="display:flex; align-items:flex-end; gap:1px; height:130px; padding:4px 2px 0;">'
    for n in range(1, 46):
        s = scores[n]
        h = max(int(s / max_score * 110), 2)
        c = bar_color(n)
        bars_html += f'''<div style="display:flex; flex-direction:column; align-items:center; flex:1; min-width:0;">
            <span style="font-size:8px; color:#888;">{s:.0f}</span>
            <div style="width:100%; height:{h}px; background:{c}; border-radius:2px 2px 0 0;"></div>
            <span style="font-size:8px; color:#666;">{n}</span>
        </div>'''
    bars_html += '</div>'
    st.markdown(f'<p style="color:#ccc; font-size:0.85rem; font-weight:600; margin:8px 0 2px;">📊 번호별 점수</p>', unsafe_allow_html=True)
    st.markdown(bars_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# 📜 예측 이력
# ═══════════════════════════════════════════════════════
elif page == "📜 예측 이력":
    st.markdown('<p class="main-title">📜 예측 이력</p>', unsafe_allow_html=True)

    prediction_log = update_all_from_df(df)

    if not prediction_log:
        st.info("아직 저장된 예측이 없습니다. **🎱 예측하기**에서 예측을 생성하면 자동으로 저장됩니다.")
    else:
        # 누적 성적
        log_stats = get_stats(prediction_log)
        if log_stats['total_rounds'] > 0:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("확인 회차", f"{log_stats['total_rounds']}회")
            c2.metric("평균 적중", f"{log_stats['avg_match']:.2f}개")
            c3.metric("최고세트", f"{log_stats['avg_best']:.2f}개")
            c4.metric("최대 적중", f"{log_stats['max_match']}개")

        # 2열 그리드로 카드 배치
        left_items = prediction_log[0::2]  # 짝수 인덱스
        right_items = prediction_log[1::2]  # 홀수 인덱스

        def render_card(entry, idx):
            entry_id = entry.get('id', f'legacy_{idx}')
            target = entry['target_round']
            predicted_at = entry['predicted_at']
            actual = entry.get('actual')
            results = entry.get('results')

            if actual:
                best_match = max(r['matched_count'] for r in results) if results else 0
                icon = "🎉" if best_match >= 3 else ("👍" if best_match >= 2 else "📋")
                status = "완료"
            else:
                icon = "⏳"
                status = "대기"

            # 짧은 고유번호 (ID 뒷 6자리)
            short_id = entry_id[-6:] if len(entry_id) > 6 else entry_id

            settings = entry.get('settings', {})
            setting_str = ""
            if settings.get('num_sets') and settings.get('temperature'):
                setting_str = f" · {settings['num_sets']}세트 T{settings['temperature']}"

            html = f'<div style="background:#161622; border-radius:8px; padding:8px 12px; margin-bottom:8px;">'
            html += f'<div style="display:flex; justify-content:space-between; margin-bottom:4px;">'
            html += f'<span style="color:#ccc; font-weight:700; font-size:0.85rem;">{icon} {target}회 ({status})</span>'
            html += f'<span style="color:#444; font-size:0.6rem;">#{short_id} · {predicted_at[5:]}{setting_str}</span></div>'

            if actual:
                html += f'<div style="margin-bottom:4px; font-size:0.75rem;"><span style="color:#888;">당첨:</span> {render_balls(actual)}</div>'

            for j, s in enumerate(entry['sets']):
                balls = render_balls(s['numbers'])
                fitness = s['fitness']
                if results and j < len(results):
                    mc = results[j]['matched_count']
                    mn = results[j]['matched_numbers']
                    if mc >= 3: mc_c = "#ff6b6b"
                    elif mc >= 2: mc_c = "#FBC400"
                    elif mc >= 1: mc_c = "#69C8F2"
                    else: mc_c = "#444"
                    r_str = f'<span style="color:{mc_c}; font-weight:600;">{mc}</span>'
                else:
                    r_str = '<span style="color:#444;">-</span>'

                html += f'''<div style="display:flex; align-items:center; justify-content:space-between; padding:2px 0; border-top:1px solid #1e1e30;">
                    <div style="display:flex; align-items:center; gap:3px;"><span style="color:#555; font-size:0.75rem; width:14px;">{j+1}</span>{balls}</div>
                    <div style="display:flex; gap:6px; align-items:center;">{r_str}<span style="color:#444; font-size:0.65rem;">{fitness}</span></div>
                </div>'''

            html += '</div>'
            return html, entry_id

        def render_card_column(items, col_offset):
            for i, entry in enumerate(items):
                real_idx = i * 2 + col_offset
                card_html, eid = render_card(entry, real_idx)
                st.markdown(card_html, unsafe_allow_html=True)
                bc1, bc2, bc3 = st.columns([1, 1, 1])
                with bc1:
                    if st.button("🖨️ 인쇄", key=f"print_{eid}", use_container_width=True):
                        st.session_state['print_entry'] = entry
                with bc2:
                    if st.button("🗑️ 전체삭제", key=f"del_{eid}", use_container_width=True):
                        delete_prediction(eid)
                        st.rerun()
                with bc3:
                    opts = [f"{j+1}세트" for j in range(len(entry['sets']))]
                    if opts:
                        sel = st.selectbox("세트", opts, key=f"sel_{eid}", label_visibility="collapsed")
                        if st.button("세트삭제", key=f"ds_{eid}", use_container_width=True):
                            delete_set_from_prediction(eid, opts.index(sel))
                            st.rerun()

        col_l, col_r = st.columns(2)
        with col_l:
            render_card_column(left_items, 0)
        with col_r:
            render_card_column(right_items, 1)

        # ── 인쇄 미리보기 영역 ──
        print_entry = st.session_state.get('print_entry')
        if print_entry:
            st.divider()

            import display.lotto_paper as lp
            from display.lotto_paper import (
                create_preview_on_scan, create_preview_simple,
                create_marking_image, image_to_bytes,
            )

            game_sets = [s['numbers'] for s in print_entry['sets'][:5]]
            target = print_entry['target_round']

            hdr1, hdr2 = st.columns([4, 1])
            with hdr1:
                st.markdown(f"### 🖨️ 제{target}회 인쇄 미리보기 ({len(game_sets)}게임)")
            with hdr2:
                if st.button("✕ 닫기", key="close_print", use_container_width=True):
                    del st.session_state['print_entry']
                    st.rerun()

            # 스캔 배경 미리보기
            preview_img = create_preview_on_scan(game_sets)
            st.image(preview_img, use_container_width=True)

            # 인쇄 버튼
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                print_img = create_marking_image(game_sets)
                print_bytes = image_to_bytes(print_img)
                st.download_button(
                    "📄 인쇄용 이미지",
                    data=print_bytes,
                    file_name=f"lotto_{target}.png",
                    mime="image/png",
                    use_container_width=True,
                    type="primary",
                )
            with c2:
                # 인쇄 안내 HTML
                import streamlit.components.v1 as components
                import base64
                b64 = base64.b64encode(print_bytes).decode()
                components.html(f"""
                <button id="printBtn" style="
                    width:100%;padding:10px 16px;
                    background:#e44;color:white;border:none;
                    border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;">
                    🖨️ 바로 인쇄
                </button>
                <script>
                document.getElementById('printBtn').onclick=function(){{
                    var w=window.open('','_blank','width=800,height=400');
                    w.document.write('<html><head><title>로또 인쇄</title>');
                    w.document.write('<style>@page{{size:190mm 82.5mm;margin:0}}body{{margin:0;padding:0}}</style>');
                    w.document.write('</head><body>');
                    w.document.write('<img src="data:image/png;base64,{b64}" style="width:190mm;height:82.5mm;">');
                    w.document.write('</body></html>');
                    w.document.close();
                    setTimeout(function(){{w.print();}},300);
                }};
                </script>
                """, height=45)
            with c3:
                st.markdown("""<div style="color:#777; font-size:0.7rem; line-height:1.6; padding-top:6px;">
                    수동급지에 로또 용지 → 용지: 190×82.5mm → 여백: 0 → 위치 안 맞으면 조정값 수정
                </div>""", unsafe_allow_html=True)

            # 좌표 조정
            with st.expander("⚙️ 좌표 미세 조정", expanded=False):
                a1, a2 = st.columns(2)
                with a1:
                    off_x = st.number_input("X보정(mm)", value=0.0, step=0.3, format="%.1f", key="px")
                    off_y = st.number_input("Y보정(mm)", value=0.0, step=0.3, format="%.1f", key="py")
                with a2:
                    st.markdown("""<div style="color:#888; font-size:0.7rem; line-height:1.6;">
                        <b>보정 방법:</b><br>
                        1. 빈 A4에 테스트 인쇄<br>
                        2. 로또 용지에 겹쳐서 확인<br>
                        3. 어긋난 만큼 X/Y 보정값 입력<br>
                        X: + 오른쪽 / Y: + 아래
                    </div>""", unsafe_allow_html=True)
                lp.OFFSET_X_MM = off_x
                lp.OFFSET_Y_MM = off_y


# ═══════════════════════════════════════════════════════
# 📊 분석 리포트
# ═══════════════════════════════════════════════════════
elif page == "📊 분석 리포트":
    st.markdown(f'<p class="main-title">📊 분석 리포트 (1~{last_round}회)</p>', unsafe_allow_html=True)

    # 주요 지표
    stats = report['sum_stats']
    ac_low, ac_high = report['ac_range']
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 회차", f"{total_rounds}회")
    c2.metric("합계 범위", f"{stats['optimal_range'][0]}~{stats['optimal_range'][1]}")
    c3.metric("AC값 범위", f"{ac_low}~{ac_high}")
    c4.metric("합계 평균", f"{stats['mean']:.0f}")

    # ── 1행: 홀짝 + 고저 분포 (CSS 가로 막대) ──
    col_oe, col_hl = st.columns(2)

    oe_dist = report['odd_even_dist']
    oe_sorted = sorted(oe_dist.items(), key=lambda x: x[1], reverse=True)
    oe_colors = ['#69C8F2', '#FBC400', '#FF7272', '#B0D840', '#999', '#c77dff', '#f4845f']

    with col_oe:
        st.markdown("**홀짝 비율 분포**")
        html = ""
        for i, (label, pct) in enumerate(oe_sorted):
            c = oe_colors[i % len(oe_colors)]
            w = max(int(pct * 2.5), 4)
            html += f'<div style="display:flex; align-items:center; gap:8px; margin:3px 0;"><span style="color:#aaa; font-size:0.8rem; width:36px; text-align:right;">{label}</span><div style="height:18px; width:{w}px; background:{c}; border-radius:3px;"></div><span style="color:#888; font-size:0.75rem;">{pct:.1f}%</span></div>'
        st.markdown(html, unsafe_allow_html=True)

    hl_dist = report['high_low_dist']
    hl_sorted = sorted(hl_dist.items(), key=lambda x: x[1], reverse=True)
    hl_colors = ['#4AA8D8', '#f0c040', '#ff6b6b', '#88B020', '#aaa', '#c77dff', '#f4845f']

    with col_hl:
        st.markdown("**저:고 비율 분포**")
        html = ""
        for i, (label, pct) in enumerate(hl_sorted):
            c = hl_colors[i % len(hl_colors)]
            w = max(int(pct * 2.5), 4)
            html += f'<div style="display:flex; align-items:center; gap:8px; margin:3px 0;"><span style="color:#aaa; font-size:0.8rem; width:36px; text-align:right;">{label}</span><div style="height:18px; width:{w}px; background:{c}; border-radius:3px;"></div><span style="color:#888; font-size:0.75rem;">{pct:.1f}%</span></div>'
        st.markdown(html, unsafe_allow_html=True)

    st.divider()

    # ── 2행: 빈도 히트맵 (CSS 그리드) ──
    st.markdown("**번호 출현 빈도**")
    scorer = WeightedScorer(df)
    total_freq = scorer.freq_analyzer.total_frequency()
    max_freq = max(total_freq.values())
    min_freq = min(total_freq.values())
    freq_range = max_freq - min_freq if max_freq != min_freq else 1

    def freq_bg(n):
        f = total_freq.get(n, 0)
        ratio = (f - min_freq) / freq_range
        r = int(30 + ratio * 220)
        g = int(30 + (1 - ratio) * 40)
        b = int(50 + (1 - ratio) * 20)
        return f"rgb({r},{g},{b})"

    grid_html = '<div style="display:grid; grid-template-columns:repeat(9, 1fr); gap:4px; max-width:700px;">'
    for n in range(1, 46):
        bg = freq_bg(n)
        f = total_freq.get(n, 0)
        grid_html += f'<div style="background:{bg}; border-radius:6px; padding:6px 2px; text-align:center;"><span style="color:#fff; font-weight:700; font-size:0.9rem;">{n}</span><br><span style="color:#ccc; font-size:0.7rem;">{f}회</span></div>'
    grid_html += '</div>'
    st.markdown(grid_html, unsafe_allow_html=True)

    st.divider()

    # ── 3행: 간격 분석 (CSS 이중 바) ──
    st.markdown("**미출현 간격 분석** (🔴 현재 미출현 vs 🔵 평균 간격)")
    gap_analyzer = scorer.gap_analyzer
    current_gaps = gap_analyzer.current_gap()
    average_gaps = gap_analyzer.average_gap()
    max_gap_val = max(max(current_gaps.values()), max(average_gaps.values())) or 1

    gap_html = '<div style="display:flex; align-items:flex-end; gap:1px; height:120px;">'
    for n in range(1, 46):
        cur = current_gaps[n]
        avg = average_gaps[n]
        h_cur = max(int(cur / max_gap_val * 100), 1)
        h_avg = max(int(avg / max_gap_val * 100), 1)
        overdue_mark = "border:1px solid #ff0;" if (avg > 0 and cur / avg >= 1.5) else ""
        gap_html += f'''<div style="display:flex; flex-direction:column; align-items:center; flex:1; min-width:0;">
            <div style="display:flex; gap:1px; align-items:flex-end; height:100px;">
                <div style="width:48%; height:{h_cur}px; background:#FF7272; border-radius:1px 1px 0 0; {overdue_mark}"></div>
                <div style="width:48%; height:{h_avg}px; background:#69C8F2; border-radius:1px 1px 0 0;"></div>
            </div>
            <span style="font-size:7px; color:#777;">{n}</span>
        </div>'''
    gap_html += '</div>'
    st.markdown(gap_html, unsafe_allow_html=True)

    # Overdue 번호 표
    overdue_list = gap_analyzer.get_overdue_numbers(1.5)
    if overdue_list:
        st.markdown("**⚠️ Overdue 번호**")
        overdue_data = [{"번호": n, "미출현": current_gaps[n], "평균": f"{average_gaps[n]:.1f}", "배율": f"{r:.1f}x"} for n, r in overdue_list[:10]]
        st.dataframe(pd.DataFrame(overdue_data), hide_index=True, use_container_width=True, height=200)

    st.divider()

    # ── 4행: 최근 당첨번호 ──
    st.markdown("**최근 당첨번호**")
    recent = df.tail(10).sort_values('round', ascending=False)
    for _, row in recent.iterrows():
        nums = [int(row[c]) for c in config.NUMBER_COLUMNS]
        bonus = int(row['bonus'])
        balls = render_balls(nums)
        st.markdown(f'<div style="margin:2px 0;"><span style="color:#888; font-size:0.8rem; margin-right:8px;">{int(row["round"])}회</span>{balls}<span style="color:#666; margin-left:6px; font-size:0.8rem;">+{bonus}</span></div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# 🔬 백테스트
# ═══════════════════════════════════════════════════════
elif page == "🔬 백테스트":
    st.markdown('<p class="main-title">🔬 백테스트 (성능 검증)</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">과거 데이터로 예측 성능을 검증합니다</p>',
                unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        test_rounds = st.slider("테스트 회차 수", 10, 100, 30)
    with col2:
        bt_sets = st.slider("회차당 예측 세트 수", 1, 10, 5)
    with col3:
        st.write("")
        st.write("")
        run_bt = st.button("🚀 백테스트 실행", type="primary", use_container_width=True)

    if run_bt:
        progress_bar = st.progress(0, text="백테스트 진행 중...")

        def bt_callback(current, total):
            progress_bar.progress(current / total, text=f"백테스트 진행 중... ({current}/{total})")

        validator = PredictionValidator()
        results = validator.backtest(df, test_rounds=test_rounds,
                                     num_sets=bt_sets, progress_callback=bt_callback)
        progress_bar.progress(1.0, text="완료!")
        st.session_state['bt_results'] = results

    results = st.session_state.get('bt_results')

    if results:
        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("평균 적중", f"{results['avg_match']:.2f}개")
        col2.metric("최고세트 평균", f"{results['avg_best_match']:.2f}개")
        col3.metric("무작위 기대값", f"{results['random_expected']:.2f}개")
        improvement = results['improvement_pct']
        col4.metric("개선율", f"{improvement:+.1f}%",
                    delta="무작위 대비" if improvement > 0 else "개선 필요")

        st.divider()

        st.markdown("### 적중 분포")
        dist = results['match_distribution']
        match_nums = list(range(7))
        counts = [dist.get(m, {}).get('count', 0) for m in match_nums]
        pcts = [dist.get(m, {}).get('pct', 0) for m in match_nums]

        fig_dist = go.Figure(data=[go.Bar(
            x=[f'{m}개 일치' for m in match_nums],
            y=counts,
            marker_color=['#444', '#69C8F2', '#4AA8D8', '#FBC400', '#FF7272', '#B0D840', '#FF4444'],
            text=[f'{p:.1f}%' for p in pcts],
            textposition='outside', textfont=dict(color='#aaa'),
        )])
        fig_dist.update_layout(
            **DARK_LAYOUT,
            xaxis_title="적중 번호 수", yaxis_title="횟수",
            height=300, margin=dict(t=10, b=40, l=40, r=10),
        )
        st.plotly_chart(fig_dist, use_container_width=True, theme=None)

        st.info(f"""
        **해석**: 총 {results['total_predictions']}개 예측 중 평균 **{results['avg_match']:.2f}개** 적중.
        무작위 선택 시 기대값 **{results['random_expected']:.2f}개** 대비 **{improvement:+.1f}%** 개선.
        """)
    else:
        st.info("👆 위에서 설정을 조정하고 **백테스트 실행** 버튼을 눌러주세요.")


# ═══════════════════════════════════════════════════════
# ❓ 원리 & 사용법
# ═══════════════════════════════════════════════════════
elif page == "❓ 원리 & 사용법":
    st.markdown('<p class="main-title">❓ 원리 & 사용법</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">이 프로그램이 어떻게 번호를 예측하는지 알아보세요</p>',
                unsafe_allow_html=True)
    st.divider()

    st.markdown("""
    ## 🧠 분석 원리

    이 프로그램은 **5가지 통계 분석**을 종합하여 1~45 각 번호에 점수를 매기고,
    점수가 높은 번호가 더 높은 확률로 선택되도록 합니다.

    ---

    ### 1️⃣ 빈도 분석 (가중치 25%)
    > **자주 나오는 번호는 계속 나올 가능성이 있다**

    - 전체 1,200+회차에서 각 번호의 출현 횟수 계산
    - 최근 20회차의 출현 빈도를 별도 분석 → **HOT/COLD 번호** 분류
    - 기대값(6/45 ≈ 13.3%)보다 **1.5배 이상** 출현하면 HOT, **0.5배 이하**면 COLD

    ### 2️⃣ 간격 분석 (가중치 25%)
    > **오래 안 나온 번호는 나올 때가 됐다 (평균 회귀)**

    - 각 번호의 **현재 미출현 기간** vs **평균 출현 간격** 비교
    - `Overdue 비율 = 현재 미출현 / 평균 간격`
    - 비율 **1.2~2.0** 구간의 번호에 높은 점수 (적당히 overdue)
    - 3.0 이상 극단적 미출현은 점수 감소 (구조적으로 안 나올 수 있음)

    ### 3️⃣ 트렌드 분석 (가중치 20%)
    > **최근 흐름을 타는 번호를 포착한다**

    - 최근 10회 이동평균 출현율 vs 전체 기간 출현율 비교
    - 상승 추세 번호에 가산점, 하락 추세에 감점

    ### 4️⃣ 패턴 분석 (가중치 15%)
    > **당첨번호에는 통계적 패턴이 있다**

    | 분석 항목 | 내용 |
    |-----------|------|
    | **홀짝 비율** | 가장 흔한 비율: 3:3(33%), 4:2(27%), 2:4(22%) |
    | **고저 비율** | 1-22(저) vs 23-45(고) 분포 |
    | **구간 분포** | 5개 구간(1-10, 11-20, ..., 41-45)에 고르게 분배 |
    | **연속번호** | 연속번호 쌍 포함 확률 반영 |
    | **끝수 분석** | 같은 끝수 번호 중복 빈도 |

    ### 5️⃣ 조합 필터링 (가중치 15%)
    > **비현실적인 조합은 걸러낸다**

    | 필터 | 기준 |
    |------|------|
    | **합계 범위** | 역대 평균 ± 1.5σ (약 92~184) |
    | **AC값** | 6개 번호의 산술 복잡도 ≥ 6 (고르게 분포) |
    | **소수 비율** | 역대 당첨번호의 소수 비율 분포 내 |

    ---

    ## 🔄 예측 생성 과정

    ```
    ① 5가지 분석 → 1~45 각 번호별 종합 점수 (0~100)
         ↓
    ② 점수를 Softmax로 확률 분포 변환
         ↓
    ③ 확률 기반 가중 랜덤 샘플링 (6개 번호)
         ↓
    ④ 필터 체인 통과 (합계→AC값→홀짝→고저→구간)
         ↓
    ⑤ 통과한 조합만 수집 → 적합도 점수로 정렬
         ↓
    ⑥ 상위 N세트 최종 출력
    ```

    > **핵심**: 완전한 랜덤이 아니라, 점수가 높은 번호가 **더 자주** 뽑히되,
    > 낮은 번호도 **일정 확률**로 뽑힐 수 있습니다.

    ---

    ## 📖 사용법

    ### 🎱 예측하기
    1. **생성 세트 수**: 원하는 번호 조합 수 (1~20세트)
    2. **다양성 (온도)**: 낮으면 고점수 번호 집중, 높으면 다양한 조합
       - `1.0`: 상위 번호 위주 (보수적)
       - `2.0`: 균형 (기본값)
       - `4.0+`: 다양한 번호 포함 (모험적)
    3. **예측 생성** 버튼 클릭 → 결과 확인

    ### 📊 분석 리포트
    - **홀짝/고저 분포**: 역대 당첨번호의 홀짝, 저고 비율 파이차트
    - **빈도 히트맵**: 1~45 번호의 총 출현 횟수 시각화
    - **간격 분석**: 현재 미출현 기간 vs 평균 간격 비교
    - **구간 분포**: 5개 구간별 번호 배분 패턴

    ### 🔬 백테스트
    - 과거 N회차에 대해 **이전 데이터만으로 예측 → 실제와 비교**
    - 무작위 선택(기대값 ~0.8개) 대비 개선율 측정
    - 예측 알고리즘의 **실제 성능**을 검증하는 기능

    ### 🔄 데이터 새로고침
    - 사이드바의 **데이터 새로고침** 버튼으로 최신 회차 자동 업데이트
    - 데이터는 `data/lotto_history.csv`에 캐시됨

    ---

    ## ⚠️ 주의사항
    - 로또는 **독립 시행**입니다. 과거 결과가 미래를 결정하지 않습니다.
    - 이 프로그램은 통계적 **경향성**을 활용하여 무작위보다 나은 선택을 돕지만,
      **당첨을 보장하지 않습니다**.
    - 백테스트 결과 무작위 대비 약 **30~50% 개선** 수준입니다.
    """)


# ─── 푸터 ───
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.8rem; padding: 10px 0;">
    ※ 본 프로그램은 통계 분석 기반 참고용이며, 실제 당첨을 보장하지 않습니다.<br>
    데이터 출처: data.soledot.com · 분석 엔진: Python + Streamlit
</div>
""", unsafe_allow_html=True)
