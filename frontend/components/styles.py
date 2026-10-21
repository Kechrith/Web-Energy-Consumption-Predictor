"""Design tokens and global CSS for EnergyIntel."""

import streamlit as st

COLORS = {
    "navy": "#10243A",
    "blue": "#2563EB",
    "green": "#16A34A",
    "bg": "#F8FAFC",
    "card": "#FFFFFF",
    "border": "#E2E8F0",
    "muted": "#64748B",
    "ink": "#10243A",
    "amber": "#D97706",
    "red": "#DC2626",
    "sky": "#93C5FD",
    "slate": "#94A3B8",
}

_CSS = """
<style>
:root {
  --ei-navy: #10243A; --ei-blue: #2563EB; --ei-green: #16A34A;
  --ei-bg: #F8FAFC; --ei-card: #FFFFFF; --ei-border: #E2E8F0; --ei-muted: #64748B;
  --ei-amber: #D97706; --ei-red: #DC2626;
  --ei-shadow: 0 1px 2px rgba(16,36,58,.04), 0 4px 14px rgba(16,36,58,.04);
}

/* ---------- Layout ---------- */
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1440px; }
h1, h2, h3, h4 { color: var(--ei-navy); letter-spacing: -0.02em; }
h1 { font-weight: 700 !important; }
[data-testid="stHeader"] { background: transparent; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { border-right: 1px solid #0B1A2B; }
[data-testid="stSidebarNavLink"] { border-radius: 8px; margin: 1px 0; padding: .45rem .7rem; transition: background .15s; }
[data-testid="stSidebarNavLink"]:hover { background: rgba(255,255,255,.06); }
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: rgba(37,99,235,.22);
  box-shadow: inset 3px 0 0 #60A5FA;
}
[data-testid="stSidebarNavLink"][aria-current="page"] span { color: #FFFFFF !important; font-weight: 600; }
[data-testid="stSidebarNavSeparator"] { border-color: #24405E; }
[data-testid="stSidebar"] [data-testid="stHeading"] h6,
[data-testid="stSidebarNav"] header { color: #7F95AE !important; }
.ei-side-label { color:#7F95AE; font-size:.7rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; margin:.4rem 0 .35rem; }
.ei-side-status { display:flex; align-items:center; gap:.5rem; font-size:.8rem; color:#CBD5E1; padding:.25rem 0; }
.ei-dot { width:8px; height:8px; border-radius:50%; display:inline-block; flex:none; }

/* ---------- Page header ---------- */
.ei-eyebrow { color: var(--ei-muted); text-transform: uppercase; letter-spacing: .12em; font-size: .7rem; font-weight: 600; margin-bottom: .2rem; }
.ei-title { font-size: 1.85rem; font-weight: 700; color: var(--ei-navy); letter-spacing: -0.025em; line-height: 1.15; margin: 0; }
.ei-subtitle { color: var(--ei-muted); font-size: .95rem; margin-top: .35rem; max-width: 760px; }

/* ---------- Cards ---------- */
.ei-card { background: var(--ei-card); border: 1px solid var(--ei-border); border-radius: 14px; padding: 1.05rem 1.15rem; box-shadow: var(--ei-shadow); height: 100%; }
.ei-kpi { display:flex; flex-direction:column; gap:.3rem; min-height: 138px; }
.ei-kpi-top { display:flex; align-items:center; justify-content:space-between; }
.ei-kpi-label { color: var(--ei-muted); font-size: .8rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ei-kpi-icon { width: 30px; height: 30px; border-radius: 8px; display:flex; align-items:center; justify-content:center; }
.ei-kpi-value { color: var(--ei-navy); font-size: clamp(1.15rem, 1.6vw, 1.45rem); white-space: nowrap; font-weight: 700; letter-spacing: -0.02em; line-height: 1.15; font-variant-numeric: tabular-nums; }
.ei-kpi-foot { font-size: .76rem; color: var(--ei-muted); display:flex; align-items:center; gap:.35rem; flex-wrap: wrap; }
.ei-delta { font-weight: 600; padding: .05rem .4rem; border-radius: 999px; font-size: .74rem; }
.ei-delta.good { color: #15803D; background: #DCFCE7; }
.ei-delta.bad { color: #B91C1C; background: #FEE2E2; }
.ei-delta.neutral { color: #475569; background: #F1F5F9; }

/* ---------- Badges & notes ---------- */
.ei-badge { display:inline-flex; align-items:center; gap:.3rem; font-size:.7rem; font-weight:600; padding:.15rem .55rem; border-radius:999px; letter-spacing:.02em; white-space:nowrap; vertical-align: middle; }
.ei-badge.demo { background:#FEF3C7; color:#92400E; border:1px solid #FDE68A; }
.ei-badge.real { background:#DCFCE7; color:#166534; border:1px solid #BBF7D0; }
.ei-badge.info { background:#DBEAFE; color:#1E40AF; border:1px solid #BFDBFE; }
.ei-badge.muted { background:#F1F5F9; color:#475569; border:1px solid #E2E8F0; }
.ei-badge.high { background:#FEE2E2; color:#991B1B; border:1px solid #FECACA; }
.ei-badge.medium { background:#FFEDD5; color:#9A3412; border:1px solid #FED7AA; }
.ei-badge.low { background:#FEF9C3; color:#854D0E; border:1px solid #FEF08A; }

.ei-banner { display:flex; gap:.75rem; align-items:flex-start; border-radius:12px; padding:.75rem 1rem; font-size:.86rem; margin:.25rem 0 1rem; border:1px solid; }
.ei-banner.demo { background:#FFFBEB; border-color:#FDE68A; color:#78350F; }
.ei-banner.info { background:#EFF6FF; border-color:#BFDBFE; color:#1E3A8A; }
.ei-banner.warn { background:#FFF7ED; border-color:#FED7AA; color:#7C2D12; }
.ei-banner svg { flex:none; margin-top:1px; }

.ei-section { display:flex; align-items:baseline; justify-content:space-between; gap:1rem; margin: 1.4rem 0 .5rem; }
.ei-section h3 { font-size: 1.05rem; font-weight: 650; margin: 0; padding: 0; }
.ei-section p { color: var(--ei-muted); font-size: .82rem; margin: .15rem 0 0; }

/* ---------- Lists ---------- */
.ei-list { display:flex; flex-direction:column; gap:.1rem; }
.ei-item { display:flex; gap:.7rem; align-items:flex-start; padding:.6rem 0; border-bottom:1px solid #F1F5F9; }
.ei-item:last-child { border-bottom: none; }
.ei-item-icon { width:30px; height:30px; border-radius:8px; flex:none; display:flex; align-items:center; justify-content:center; }
.ei-item-title { font-size:.86rem; font-weight:600; color:var(--ei-navy); }
.ei-item-body { font-size:.8rem; color:var(--ei-muted); margin-top:.1rem; line-height:1.45; }

/* ---------- Empty state ---------- */
.ei-empty { text-align:center; padding: 2.2rem 1rem; border: 1.5px dashed #CBD5E1; border-radius: 14px; background: #FFFFFF; }
.ei-empty-icon { width:44px; height:44px; margin:0 auto .7rem; border-radius:12px; background:#EFF6FF; display:flex; align-items:center; justify-content:center; }
.ei-empty h4 { margin:0 0 .25rem; font-size: 1rem; }
.ei-empty p { color: var(--ei-muted); font-size: .86rem; margin: 0 auto; max-width: 460px; }

/* ---------- Check list (validation) ---------- */
.ei-check { display:flex; gap:.6rem; align-items:flex-start; padding:.45rem 0; font-size:.85rem; }
.ei-check b { color: var(--ei-navy); font-weight: 600; }
.ei-check span.d { color: var(--ei-muted); }

/* ---------- Report preview ---------- */
.ei-report { background:#FFFFFF; border:1px solid var(--ei-border); border-radius:14px; padding: 2rem 2.2rem; box-shadow: var(--ei-shadow); }
.ei-report h2 { font-size:1.5rem; margin:.2rem 0 .3rem; }
.ei-report h4 { font-size:.95rem; margin:1.4rem 0 .5rem; padding-bottom:.35rem; border-bottom:1px solid var(--ei-border); }
.ei-report table { width:100%; border-collapse:collapse; font-size:.85rem; }
.ei-report td, .ei-report th { padding:.4rem .5rem; border-bottom:1px solid #F1F5F9; text-align:left; }
.ei-report th { color: var(--ei-muted); font-weight:600; font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; }
.ei-report .muted { color: var(--ei-muted); font-size:.82rem; }

/* ---------- Streamlit widgets ---------- */
div[data-testid="stMetric"] { background:#FFFFFF; border:1px solid var(--ei-border); padding:.8rem 1rem; border-radius:12px; box-shadow: var(--ei-shadow); }
div[data-testid="stMetricLabel"] p { color: var(--ei-muted); font-size: .8rem; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
.stButton button, .stDownloadButton button, .stFormSubmitButton button { font-weight: 600; }
[data-testid="stFileUploaderDropzone"] { background:#FFFFFF; border: 1.5px dashed #93C5FD; border-radius: 14px; padding: 1.6rem; }
[data-testid="stExpander"] details { border-radius: 12px; background: #FFFFFF; }
.stTabs [data-baseweb="tab-list"] { gap: .25rem; }
.stTabs [data-baseweb="tab"] { padding: .5rem .9rem; }

.ei-footer { color:#94A3B8; font-size:.75rem; text-align:center; margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--ei-border); }

@media (max-width: 768px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1.2rem; }
  .ei-title { font-size: 1.45rem; }
  .ei-kpi { min-height: auto; }
  .ei-report { padding: 1.2rem; }
}
</style>
"""


def inject_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
