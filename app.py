import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Sleep Timeline",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────
BG      = '#16213e'
GRID    = '#2a3a5e'
TEXT    = '#dce8f5'
SUBTEXT = '#8aaac8'

SLEEP_COLORS = {
    'deep':  '#1e3a6e',
    'light': '#7a9cc4',
    'rem':   '#9b3f7e',
    'awake': '#e07b39',
}
STAGE_LABEL = {
    'deep':  'Deep Sleep',
    'light': 'Light Sleep',
    'rem':   'REM Sleep',
    'awake': 'Awake',
}
STAGE_Y  = {'deep': 0, 'light': 1, 'rem': 2, 'awake': 3}
SEG_H    = 0.80
ROW_H    = 4.8
EX_Y_OFF = 4.1
EX_BAR_H = 0.55   # increased from original 0.35 (user study feedback)
EX_COLOR  = '#4CAF50'
CAF_COLOR = '#FFD600'  # changed from orange → yellow (user study: conflict with Awake)

# ── Helpers ───────────────────────────────────────────────────────
def time_to_x(time_str):
    if pd.isna(time_str) or str(time_str).strip() == "":
        return np.nan
    try:
        h, m = map(int, str(time_str).strip().split(':'))
        val = h + m / 60.0
        return val + 24 if val < 12 else val
    except Exception:
        return np.nan

def dt_to_x(dt):
    val = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    return val + 24 if val < 12 else val

def compute_score(row):
    try:
        return round(row['deep_sleep_percentage'] * 0.4 +
                     row['rem_sleep_percentage']  * 0.6, 1)
    except Exception:
        return np.nan

# ── Data loading ──────────────────────────────────────────────────
@st.cache_data
def load_data(summary_file, detail_file=None):
    df = pd.read_csv(summary_file)
    df['date'] = pd.to_datetime(df['date'])

    if 'light_sleep_percentage' not in df.columns:
        df['light_sleep_percentage'] = (
            100 - df['deep_sleep_percentage'] - df['rem_sleep_percentage']
        )
    if 'awake_percentage' not in df.columns:
        df['awake_percentage'] = 0.0

    df['caffeine_mg']       = pd.to_numeric(df['caffeine_mg'],       errors='coerce').fillna(0)
    df['exercise_duration'] = pd.to_numeric(df['exercise_duration'], errors='coerce').fillna(0)
    df['sleep_score']       = df.apply(compute_score, axis=1)

    detail_df = None
    if detail_file is not None:
        detail_df = pd.read_csv(detail_file)
        detail_df['date']     = pd.to_datetime(detail_df['date'])
        detail_df['start_dt'] = pd.to_datetime(detail_df['start_dt'])
        detail_df['end_dt']   = pd.to_datetime(detail_df['end_dt'])

    return df, detail_df

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.title("🌙 Sleep Timeline")
    st.caption("Personal Sleep Analysis — Coros Watch × Apple Health")
    st.divider()

    # File upload fallback (for deployment without bundled data)
    base = Path(__file__).parent
    summary_path = base / "sleep_data.csv"
    detail_path  = base / "sleep_data_detail.csv"

    if not summary_path.exists():
        st.subheader("Upload data")
        summary_upload = st.file_uploader("sleep_data.csv", type="csv")
        detail_upload  = st.file_uploader("sleep_data_detail.csv (optional)", type="csv")
        if summary_upload is None:
            st.info("Please upload sleep_data.csv to begin.")
            st.stop()
        summary_src = summary_upload
        detail_src  = detail_upload
    else:
        summary_src = summary_path
        detail_src  = detail_path if detail_path.exists() else None

    df, detail_df = load_data(summary_src, detail_src)
    has_detail = detail_df is not None

    # Date filter
    st.subheader("Date range")
    min_d = df['date'].min().date()
    max_d = df['date'].max().date()
    date_range = st.date_input(
        "Select range",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        label_visibility="collapsed",
    )

    st.divider()
    st.subheader("Layers")
    show_exercise = st.toggle("Exercise", value=True)
    show_caffeine = st.toggle("Caffeine", value=True)

    st.divider()
    st.subheader("Legend")
    for stage, color in SLEEP_COLORS.items():
        st.markdown(
            f'<span style="background:{color};padding:2px 8px;border-radius:3px;">'
            f'&nbsp;</span>&nbsp;{STAGE_LABEL[stage]}',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<span style="background:{EX_COLOR};padding:2px 8px;border-radius:3px;">'
        f'&nbsp;</span>&nbsp;Exercise',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<span style="background:{CAF_COLOR};padding:2px 8px;'
        f'border-radius:3px;color:#000;">&nbsp;</span>&nbsp;Caffeine',
        unsafe_allow_html=True,
    )

# ── Filter ────────────────────────────────────────────────────────
if len(date_range) == 2:
    s_date = pd.Timestamp(date_range[0])
    e_date = pd.Timestamp(date_range[1])
    fdf = df[(df['date'] >= s_date) & (df['date'] <= e_date)].reset_index(drop=True)
else:
    fdf = df.reset_index(drop=True)

n_days = len(fdf)
if n_days == 0:
    st.warning("No data in selected date range.")
    st.stop()

# ── Build Plotly figure ───────────────────────────────────────────
fig_h = max(500, n_days * 28 + 120)

fig = go.Figure()
fig.update_layout(
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    height=fig_h,
    margin=dict(l=110, r=130, t=60, b=60),
    showlegend=False,
    hovermode='closest',
    xaxis=dict(
        range=[12, 37.5],
        tickvals=list(range(12, 37)),
        ticktext=[f"{h}:00" if h < 24 else f"{h-24}:00" for h in range(12, 37)],
        tickfont=dict(color=SUBTEXT, size=9),
        gridcolor=GRID, gridwidth=0.5,
        showline=False, zeroline=False,
        title=dict(
            text="Time of Day  (12:00 PM → next 12:00 PM)",
            font=dict(color=SUBTEXT, size=10),
        ),
    ),
    yaxis=dict(
        range=[-0.5, n_days * ROW_H],
        autorange='reversed',
        showgrid=False, showline=False, zeroline=False,
        tickfont=dict(color=TEXT, size=9),
    ),
    title=dict(
        text="Sleep Hypnogram & Exercise  —  each row: Deep / Light / REM / Awake (bottom→top)",
        font=dict(color=TEXT, size=13, family="sans-serif"),
        x=0.5,
    ),
)

shapes   = []
y_ticks  = []
y_labels = []

# Hover scatter accumulators
hover_acc = {stage: {'x': [], 'y': [], 'text': []} for stage in SLEEP_COLORS}
ex_acc   = {'x': [], 'y': [], 'text': []}
caf_acc  = {'x': [], 'y': [], 'text': []}

for i, (idx, row) in enumerate(fdf.iterrows()):
    row_base = i * ROW_H
    date     = row['date']
    dstr     = date.strftime('%m/%d (%a)')

    y_ticks.append(row_base + 1.5)
    y_labels.append(dstr)

    # Alternating row highlight
    if i % 2 == 0:
        shapes.append(dict(
            type='rect', x0=12, x1=37.5,
            y0=row_base - 0.2, y1=row_base + ROW_H - 0.4,
            fillcolor='rgba(30,45,80,0.25)',
            line=dict(width=0), layer='below',
        ))

    # ── Sleep stage rectangles ────────────────────────────────────
    if has_detail:
        day_segs = detail_df[detail_df['date'] == date]
        for _, seg in day_segs.iterrows():
            stage = seg['stage']
            if stage not in STAGE_Y:
                continue
            x0 = dt_to_x(seg['start_dt'])
            x1 = dt_to_x(seg['end_dt'])
            if x1 <= x0:
                x1 += 24
            w = x1 - x0
            if w < 0.005:
                continue
            # Skip unrealistically long awake segments (> 60 min = 1h)
            if stage == 'awake' and w > 1.0:
                continue
            yp = row_base + STAGE_Y[stage]

            shapes.append(dict(
                type='rect', x0=x0, x1=x1,
                y0=yp, y1=yp + SEG_H,
                fillcolor=SLEEP_COLORS[stage],
                line=dict(width=0.3, color=BG),
                layer='above',
            ))
            dur = seg['duration_min']
            hover_acc[stage]['x'].append((x0 + x1) / 2)
            hover_acc[stage]['y'].append(yp + SEG_H / 2)
            hover_acc[stage]['text'].append(
                f"<b>{dstr}</b><br>"
                f"Stage: {STAGE_LABEL[stage]}<br>"
                f"Duration: {dur:.0f} min<br>"
                f"{seg['start_dt'].strftime('%H:%M')} → {seg['end_dt'].strftime('%H:%M')}"
            )
    else:
        # Percentage fallback
        sx = time_to_x(row.get('sleep_start', ''))
        ex = time_to_x(row.get('sleep_end', ''))
        if np.isnan(sx) or np.isnan(ex):
            ex = 31.0
            sx = ex - row['sleep_duration']
        total = ex - sx
        cx = sx
        for stage, col in [
            ('light', 'light_sleep_percentage'),
            ('deep',  'deep_sleep_percentage'),
            ('rem',   'rem_sleep_percentage'),
            ('awake', 'awake_percentage'),
        ]:
            pct = row.get(col, 0)
            w   = total * pct / 100
            if w > 0.01:
                yp = row_base + STAGE_Y[stage]
                shapes.append(dict(
                    type='rect', x0=cx, x1=cx + w,
                    y0=yp, y1=yp + SEG_H,
                    fillcolor=SLEEP_COLORS[stage],
                    line=dict(width=0.3, color=BG), layer='above',
                ))
                hover_acc[stage]['x'].append(cx + w / 2)
                hover_acc[stage]['y'].append(yp + SEG_H / 2)
                hover_acc[stage]['text'].append(
                    f"<b>{dstr}</b><br>"
                    f"Stage: {STAGE_LABEL[stage]}<br>"
                    f"Share: {pct:.1f}%<br>"
                    f"~{row['sleep_duration'] * pct / 100:.1f}h"
                )
                cx += w

    # Duration + quality score annotation
    score = row.get('sleep_score', np.nan)
    label = f"{row['sleep_duration']:.1f}h"
    if not pd.isna(score):
        label += f"  ★{score:.0f}"
    fig.add_annotation(
        x=37.3, y=row_base + 1.5,
        text=label,
        showarrow=False,
        font=dict(color=SUBTEXT, size=8),
        xanchor='left', yanchor='middle',
    )

    # ── Exercise bar ──────────────────────────────────────────────
    if show_exercise:
        ex_dur = row['exercise_duration']
        if ex_dur > 0 and pd.notna(row.get('exercise_timing')):
            e_x = time_to_x(str(row['exercise_timing']))
            if not np.isnan(e_x):
                e_w = ex_dur / 60.0
                yp  = row_base + EX_Y_OFF
                shapes.append(dict(
                    type='rect', x0=e_x, x1=e_x + e_w,
                    y0=yp, y1=yp + EX_BAR_H,
                    fillcolor=EX_COLOR, opacity=0.9,
                    line=dict(width=0.3, color=BG), layer='above',
                ))
                ex_type = str(row.get('exercise_type') or 'Exercise')
                ex_acc['x'].append(e_x + e_w / 2)
                ex_acc['y'].append(yp + EX_BAR_H / 2)
                ex_acc['text'].append(
                    f"<b>{dstr}</b><br>"
                    f"🏃 {ex_type}<br>"
                    f"Duration: {int(ex_dur)} min<br>"
                    f"Start: {row['exercise_timing']}"
                )

    # ── Caffeine dot ──────────────────────────────────────────────
    if show_caffeine:
        caf_mg = row['caffeine_mg']
        if caf_mg > 0 and pd.notna(row.get('last_caffeine_time')):
            c_x = time_to_x(str(row['last_caffeine_time']))
            if not np.isnan(c_x):
                caf_acc['x'].append(c_x)
                caf_acc['y'].append(row_base + 2.5)
                caf_acc['text'].append(
                    f"<b>{dstr}</b><br>"
                    f"☕ Caffeine: {caf_mg:.0f} mg<br>"
                    f"Last intake: {row['last_caffeine_time']}"
                )

# Midnight line
shapes.append(dict(
    type='line', x0=24, x1=24,
    y0=-0.5, y1=n_days * ROW_H,
    line=dict(color='#556688', width=1.0, dash='dash'),
    layer='above',
))

fig.update_layout(shapes=shapes)
fig.update_yaxes(tickvals=y_ticks, ticktext=y_labels)
fig.add_annotation(
    x=24.05, y=-0.3, text='0:00',
    showarrow=False,
    font=dict(color='#556688', size=7.5),
    xanchor='left', yanchor='top',
)

# ── Invisible hover traces ────────────────────────────────────────
for stage, acc in hover_acc.items():
    if acc['x']:
        fig.add_trace(go.Scatter(
            x=acc['x'], y=acc['y'],
            mode='markers',
            marker=dict(size=14, opacity=0, color=SLEEP_COLORS[stage]),
            hovertemplate='%{text}<extra></extra>',
            text=acc['text'],
            name=STAGE_LABEL[stage],
            showlegend=False,
        ))

if ex_acc['x'] and show_exercise:
    fig.add_trace(go.Scatter(
        x=ex_acc['x'], y=ex_acc['y'],
        mode='markers',
        marker=dict(size=16, opacity=0, color=EX_COLOR),
        hovertemplate='%{text}<extra></extra>',
        text=ex_acc['text'],
        name='Exercise', showlegend=False,
    ))

if caf_acc['x'] and show_caffeine:
    fig.add_trace(go.Scatter(
        x=caf_acc['x'], y=caf_acc['y'],
        mode='markers',
        marker=dict(
            size=12, opacity=1,
            color=CAF_COLOR, symbol='circle',
            line=dict(color='white', width=1),
        ),
        hovertemplate='%{text}<extra></extra>',
        text=caf_acc['text'],
        name='Caffeine', showlegend=False,
    ))

# ── Render chart ──────────────────────────────────────────────────
st.plotly_chart(fig, use_container_width=True, config={
    'displayModeBar': True,
    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    'toImageButtonOptions': {'format': 'png', 'filename': 'sleep_timeline'},
})

# ── Summary stats ─────────────────────────────────────────────────
st.divider()
st.subheader("Summary Statistics")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg Sleep Duration",  f"{fdf['sleep_duration'].mean():.1f} h")
c2.metric("Avg Deep Sleep",      f"{fdf['deep_sleep_percentage'].mean():.1f} %")
c3.metric("Avg REM Sleep",       f"{fdf['rem_sleep_percentage'].mean():.1f} %")
c4.metric("Avg Quality Score ★", f"{fdf['sleep_score'].mean():.1f}")