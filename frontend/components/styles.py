"""Design tokens and global aesthetic CSS for EnergyIntel."""

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
/* =========================================================================
   DESIGN TOKENS & SYSTEM VARIABLES
   ========================================================================= */
:root {
  --ei-navy: #10243A;
  --ei-navy-dark: #0B1524;
  --ei-blue: #2563EB;
  --ei-blue-light: #3B82F6;
  --ei-blue-glow: rgba(37, 99, 235, 0.25);
  --ei-green: #16A34A;
  --ei-green-light: #22C55E;
  --ei-bg: #F8FAFC;
  --ei-card: #FFFFFF;
  --ei-border: #E2E8F0;
  --ei-border-light: rgba(226, 232, 240, 0.85);
  --ei-muted: #64748B;
  --ei-amber: #D97706;
  --ei-red: #DC2626;

  /* Layered elevation shadows */
  --ei-shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
  --ei-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  --ei-shadow-md: 0 4px 14px -2px rgba(15, 23, 42, 0.07), 0 2px 6px -1px rgba(15, 23, 42, 0.04);
  --ei-shadow-lg: 0 12px 28px -6px rgba(15, 23, 42, 0.09), 0 6px 12px -3px rgba(15, 23, 42, 0.04);
  --ei-shadow-hover: 0 12px 26px -4px rgba(37, 99, 235, 0.12), 0 6px 12px -2px rgba(16, 36, 58, 0.05);

  --ei-radius-sm: 8px;
  --ei-radius-md: 12px;
  --ei-radius-lg: 16px;
  --ei-transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

/* =========================================================================
   BASE LAYOUT & TYPOGRAPHY
   ========================================================================= */
html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
}

.block-container {
  padding-top: 2rem !important;
  padding-bottom: 3.5rem !important;
  max-width: 1440px !important;
}

h1, h2, h3, h4, h5, h6 {
  color: var(--ei-navy) !important;
  letter-spacing: -0.025em !important;
}

h1 { font-weight: 750 !important; }
h2 { font-weight: 700 !important; }
h3 { font-weight: 650 !important; }

[data-testid="stHeader"] {
  background: transparent !important;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 7px;
  height: 7px;
}
::-webkit-scrollbar-track {
  background: #F8FAFC;
}
::-webkit-scrollbar-thumb {
  background: #CBD5E1;
  border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94A3B8;
}

/* =========================================================================
   SIDEBAR AESTHETICS
   ========================================================================= */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0F172A 0%, #09101D 100%) !important;
  border-right: 1px solid #1E293B !important;
}

[data-testid="stSidebarNavLink"] {
  border-radius: 10px !important;
  margin: 2px 0 !important;
  padding: 0.52rem 0.8rem !important;
  transition: var(--ei-transition) !important;
}

[data-testid="stSidebarNavLink"]:hover {
  background: rgba(255, 255, 255, 0.08) !important;
  transform: translateX(2px) !important;
}

[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.28) 0%, rgba(37, 99, 235, 0.12) 100%) !important;
  box-shadow: inset 3.5px 0 0 #38BDF8 !important;
}

[data-testid="stSidebarNavLink"][aria-current="page"] span {
  color: #FFFFFF !important;
  font-weight: 600 !important;
}

[data-testid="stSidebarNavSeparator"] {
  border-color: #1E293B !important;
  margin: 0.8rem 0 !important;
}

.ei-side-label {
  color: #64748B;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 0.6rem 0 0.35rem;
}

.ei-side-status {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.8rem;
  color: #94A3B8;
  padding: 0.28rem 0;
}

.ei-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex: none;
  box-shadow: 0 0 8px currentColor;
}

@keyframes pulse-dot {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
  70% { transform: scale(1.05); box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

.ei-dot.pulse {
  animation: pulse-dot 2.2s infinite cubic-bezier(0.4, 0, 0.6, 1);
}

/* =========================================================================
   PAGE HEADER
   ========================================================================= */
.ei-eyebrow {
  color: var(--ei-blue);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.72rem;
  font-weight: 700;
  margin-bottom: 0.3rem;
  display: inline-block;
  background: rgba(37, 99, 235, 0.08);
  padding: 2px 8px;
  border-radius: 6px;
}

.ei-title {
  font-size: 2rem;
  font-weight: 800;
  color: var(--ei-navy);
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin: 0;
}

.ei-subtitle {
  color: var(--ei-muted);
  font-size: 0.96rem;
  margin-top: 0.4rem;
  max-width: 780px;
  line-height: 1.5;
}

/* =========================================================================
   CARD & KPI STYLING (ELEVATED & AESTHETIC)
   ========================================================================= */
.ei-card {
  background: var(--ei-card);
  border: 1px solid var(--ei-border-light);
  border-radius: var(--ei-radius-lg);
  padding: 1.15rem 1.25rem;
  box-shadow: var(--ei-shadow-sm);
  transition: var(--ei-transition);
  height: 100%;
}

.ei-card:hover {
  border-color: #CBD5E1;
  box-shadow: var(--ei-shadow-hover);
  transform: translateY(-2px);
}

.ei-kpi {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.45rem;
  min-height: 138px;
  position: relative;
  overflow: hidden;
}

.ei-kpi::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: transparent;
  border-top-left-radius: var(--ei-radius-lg);
  border-top-right-radius: var(--ei-radius-lg);
  transition: var(--ei-transition);
}

.ei-tone-blue::before { background: linear-gradient(90deg, #2563EB, #60A5FA); }
.ei-tone-green::before { background: linear-gradient(90deg, #16A34A, #4ADE80); }
.ei-tone-amber::before { background: linear-gradient(90deg, #D97706, #FBBF24); }
.ei-tone-red::before { background: linear-gradient(90deg, #DC2626, #F87171); }
.ei-tone-navy::before { background: linear-gradient(90deg, #1E293B, #475569); }

.ei-help-dot {
  font-size: 0.72rem;
  color: #94A3B8;
  cursor: help;
  margin-left: 4px;
  vertical-align: middle;
  transition: var(--ei-transition);
}

.ei-help-dot:hover {
  color: var(--ei-blue);
}

.ei-kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ei-kpi-label {
  color: var(--ei-muted);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ei-kpi-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--ei-shadow-xs);
  transition: var(--ei-transition);
}

.ei-card:hover .ei-kpi-icon {
  transform: scale(1.08);
}

.ei-kpi-value {
  color: var(--ei-navy);
  font-size: clamp(1.3rem, 1.7vw, 1.65rem);
  white-space: nowrap;
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
  margin: 0.2rem 0;
}

.ei-kpi-foot {
  font-size: 0.78rem;
  color: var(--ei-muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.ei-delta {
  font-weight: 600;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  font-size: 0.74rem;
  letter-spacing: -0.01em;
}

.ei-delta.good { color: #15803D; background: #DCFCE7; border: 1px solid #BBF7D0; }
.ei-delta.bad { color: #B91C1C; background: #FEE2E2; border: 1px solid #FECACA; }
.ei-delta.neutral { color: #475569; background: #F1F5F9; border: 1px solid #E2E8F0; }

/* =========================================================================
   BADGES & BANNERS
   ========================================================================= */
.ei-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  letter-spacing: 0.02em;
  white-space: nowrap;
  vertical-align: middle;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}

.ei-badge.demo { background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }
.ei-badge.real { background: #DCFCE7; color: #166534; border: 1px solid #BBF7D0; }
.ei-badge.info { background: #DBEAFE; color: #1E40AF; border: 1px solid #BFDBFE; }
.ei-badge.muted { background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; }
.ei-badge.high { background: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; }
.ei-badge.medium { background: #FFEDD5; color: #9A3412; border: 1px solid #FED7AA; }
.ei-badge.low { background: #FEF9C3; color: #854D0E; border: 1px solid #FEF08A; }

.ei-banner {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
  border-radius: var(--ei-radius-md);
  padding: 0.85rem 1.15rem;
  font-size: 0.88rem;
  margin: 0.35rem 0 1.1rem;
  border: 1px solid;
  box-shadow: var(--ei-shadow-xs);
}

.ei-banner.demo { background: #FFFBEB; border-color: #FDE68A; color: #78350F; }
.ei-banner.info { background: #EFF6FF; border-color: #BFDBFE; color: #1E3A8A; }
.ei-banner.warn { background: #FFF7ED; border-color: #FED7AA; color: #7C2D12; }
.ei-banner svg { flex: none; margin-top: 2px; }

.ei-section {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin: 1.5rem 0 0.6rem;
}

.ei-section h3 {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0;
  padding: 0;
}

.ei-section p {
  color: var(--ei-muted);
  font-size: 0.84rem;
  margin: 0.2rem 0 0;
}

/* =========================================================================
   BUTTONS (MODERN SLEEK DESIGN)
   ========================================================================= */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  letter-spacing: -0.01em !important;
  transition: var(--ei-transition) !important;
  padding: 0.5rem 1.15rem !important;
}

/* Primary Button with Gradient and Glow */
button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stFormSubmitButton > button[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
  color: #FFFFFF !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25) !important;
}

button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover,
.stFormSubmitButton > button[data-testid="stBaseButton-primary"]:hover {
  transform: translateY(-1.5px) !important;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.35) !important;
  filter: brightness(1.04) !important;
}

/* Secondary Button */
button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"],
.stDownloadButton > button {
  background: #FFFFFF !important;
  border: 1px solid #CBD5E1 !important;
  color: #1E293B !important;
  box-shadow: var(--ei-shadow-xs) !important;
}

button[kind="secondary"]:hover,
.stButton > button[data-testid="stBaseButton-secondary"]:hover,
.stDownloadButton > button:hover {
  background: #F8FAFC !important;
  border-color: #94A3B8 !important;
  transform: translateY(-1px) !important;
  box-shadow: var(--ei-shadow-sm) !important;
}

/* =========================================================================
   PILL TABS (MODERN CAPSULE STYLE)
   ========================================================================= */
.stTabs [data-baseweb="tab-list"] {
  background: #F1F5F9 !important;
  padding: 5px !important;
  border-radius: 12px !important;
  gap: 4px !important;
  border: 1px solid #E2E8F0 !important;
}

.stTabs [data-baseweb="tab"] {
  border-radius: 8px !important;
  padding: 0.48rem 1rem !important;
  font-size: 0.88rem !important;
  font-weight: 500 !important;
  color: #64748B !important;
  border-bottom: none !important;
  transition: var(--ei-transition) !important;
  background: transparent !important;
}

.stTabs [data-baseweb="tab"]:hover {
  color: #1E293B !important;
  background: rgba(255, 255, 255, 0.6) !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
  background: #FFFFFF !important;
  color: #1D4ED8 !important;
  font-weight: 650 !important;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08) !important;
}

.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
  display: none !important;
}

/* =========================================================================
   FORM INPUTS, SELECTBOXES & SLIDERS
   ========================================================================= */
div[data-baseweb="input"],
div[data-baseweb="select"] > div {
  border-radius: 10px !important;
  border-color: #CBD5E1 !important;
  transition: var(--ei-transition) !important;
}

div[data-baseweb="input"]:focus-within,
div[data-baseweb="select"]:focus-within > div {
  border-color: #2563EB !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16) !important;
}

div[data-testid="stSegmentedControl"] {
  background: #F1F5F9 !important;
  border-radius: 10px !important;
  padding: 3px !important;
}

/* =========================================================================
   DATA TABLES, TOASTS & RELIABILITY
   ========================================================================= */
.ei-kpi-value,
[data-testid="stMetricValue"],
div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"] {
  font-variant-numeric: tabular-nums lining-nums !important;
  font-feature-settings: "tnum" 1, "zero" 1 !important;
}

button:disabled, [aria-disabled="true"] {
  opacity: 0.55 !important;
  cursor: not-allowed !important;
  box-shadow: none !important;
}

div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"] {
  border: 1px solid #E2E8F0 !important;
  border-radius: var(--ei-radius-md) !important;
  box-shadow: var(--ei-shadow-xs) !important;
  overflow: hidden !important;
  background: #FFFFFF !important;
}

div[data-testid="stDataFrame"] th,
div[data-testid="stDataEditor"] th {
  background-color: #F8FAFC !important;
  color: #475569 !important;
  font-weight: 650 !important;
  letter-spacing: 0.02em !important;
}

div[data-testid="stToast"] {
  background: #0F172A !important;
  color: #FFFFFF !important;
  border-radius: 12px !important;
  border: 1px solid #334155 !important;
  box-shadow: var(--ei-shadow-lg) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid #E2E8F0 !important;
  border-radius: var(--ei-radius-lg) !important;
  background: #FFFFFF !important;
  box-shadow: var(--ei-shadow-xs) !important;
  transition: var(--ei-transition) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color: #CBD5E1 !important;
}

[data-testid="stExpander"] details {
  border: 1px solid #E2E8F0 !important;
  border-radius: var(--ei-radius-md) !important;
  background: #FFFFFF !important;
  box-shadow: var(--ei-shadow-xs) !important;
  transition: var(--ei-transition) !important;
}

[data-testid="stExpander"] details:hover {
  border-color: #CBD5E1 !important;
}

[data-testid="stFileUploaderDropzone"] {
  background: #FFFFFF !important;
  border: 1.5px dashed #93C5FD !important;
  border-radius: var(--ei-radius-lg) !important;
  padding: 1.8rem !important;
  transition: var(--ei-transition) !important;
}

[data-testid="stFileUploaderDropzone"]:hover {
  border-color: #2563EB !important;
  background: #F8FAFC !important;
}

/* =========================================================================
   EMPTY STATE & LISTS
   ========================================================================= */
.ei-empty {
  text-align: center;
  padding: 2.6rem 1.2rem;
  border: 1.5px dashed #CBD5E1;
  border-radius: var(--ei-radius-lg);
  background: #FFFFFF;
  box-shadow: var(--ei-shadow-xs);
}

.ei-empty-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 0.8rem;
  border-radius: 12px;
  background: #EFF6FF;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ei-blue);
}

.ei-empty h4 {
  margin: 0 0 0.3rem;
  font-size: 1.05rem;
}

.ei-empty p {
  color: var(--ei-muted);
  font-size: 0.88rem;
  margin: 0 auto;
  max-width: 480px;
  line-height: 1.5;
}

.ei-list { display: flex; flex-direction: column; gap: 0.15rem; }
.ei-item { display: flex; gap: 0.8rem; align-items: flex-start; padding: 0.7rem 0; border-bottom: 1px solid #F1F5F9; }
.ei-item:last-child { border-bottom: none; }
.ei-item-icon { width: 32px; height: 32px; border-radius: 9px; flex: none; display: flex; align-items: center; justify-content: center; }
.ei-item-title { font-size: 0.88rem; font-weight: 650; color: var(--ei-navy); }
.ei-item-body { font-size: 0.82rem; color: var(--ei-muted); margin-top: 0.12rem; line-height: 1.45; }

/* =========================================================================
   REPORT PREVIEW
   ========================================================================= */
.ei-report {
  background: #FFFFFF;
  border: 1px solid var(--ei-border);
  border-radius: var(--ei-radius-lg);
  padding: 2.2rem 2.4rem;
  box-shadow: var(--ei-shadow-sm);
}

.ei-report h2 { font-size: 1.55rem; margin: 0.25rem 0 0.4rem; }
.ei-report h4 { font-size: 0.98rem; margin: 1.5rem 0 0.55rem; padding-bottom: 0.4rem; border-bottom: 1px solid var(--ei-border); }
.ei-report table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.ei-report td, .ei-report th { padding: 0.45rem 0.55rem; border-bottom: 1px solid #F1F5F9; text-align: left; }
.ei-report th { color: var(--ei-muted); font-weight: 650; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.ei-report .muted { color: var(--ei-muted); font-size: 0.82rem; }

.ei-footer {
  color: #94A3B8;
  font-size: 0.76rem;
  text-align: center;
  margin-top: 3rem;
  padding-top: 1.2rem;
  border-top: 1px solid var(--ei-border);
}

/* =========================================================================
   RESPONSIVENESS
   ========================================================================= */
@media (max-width: 768px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1.2rem; }
  .ei-title { font-size: 1.5rem; }
  .ei-kpi { min-height: auto; }
  .ei-report { padding: 1.2rem; }
}
</style>
"""


def inject_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
