"""Reusable presentational components: headers, KPI cards, banners, empty states."""

from html import escape

import streamlit as st

from components.icons import icon

_TONES = {
    "blue": ("#2563EB", "#EFF6FF"),
    "green": ("#16A34A", "#F0FDF4"),
    "navy": ("#10243A", "#F1F5F9"),
    "amber": ("#D97706", "#FFFBEB"),
    "red": ("#DC2626", "#FEF2F2"),
}


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def badge(text: str, kind: str = "muted") -> str:
    """Return badge HTML. kind: demo | real | info | muted | high | medium | low."""
    return f'<span class="ei-badge {kind}">{escape(text)}</span>'


def page_header(title: str, subtitle: str = "", eyebrow: str = "", badges: list[str] | None = None) -> None:
    badge_html = " ".join(badges or [])
    _html(
        f"""
        <div style="margin-bottom:1.1rem;">
          {f'<div class="ei-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ''}
          <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;">
            <h1 class="ei-title">{escape(title)}</h1>{badge_html}
          </div>
          {f'<div class="ei-subtitle">{escape(subtitle)}</div>' if subtitle else ''}
        </div>
        """
    )


def section_header(title: str, caption: str = "", right_badge: str = "") -> None:
    _html(
        f"""<div class="ei-section"><div><h3>{escape(title)}</h3>
        {f'<p>{escape(caption)}</p>' if caption else ''}</div>{right_badge}</div>"""
    )


def kpi_card(label: str, value: str, foot: str = "", delta: str = "", delta_tone: str = "neutral",
             icon_name: str = "zap", tone: str = "blue", help_text: str = "") -> None:
    fg, bg = _TONES.get(tone, _TONES["blue"])
    delta_html = f'<span class="ei-delta {delta_tone}">{escape(delta)}</span>' if delta else ""
    title_attr = f' title="{escape(help_text)}"' if help_text else ""
    _html(
        f"""
        <div class="ei-card ei-kpi"{title_attr}>
          <div class="ei-kpi-top">
            <span class="ei-kpi-label">{escape(label)}</span>
            <span class="ei-kpi-icon" style="background:{bg};">{icon(icon_name, fg, 16)}</span>
          </div>
          <div class="ei-kpi-value">{escape(value)}</div>
          <div class="ei-kpi-foot">{delta_html}<span>{escape(foot)}</span></div>
        </div>
        """
    )


def banner(text: str, kind: str = "info", title: str = "") -> None:
    """Inline notice. kind: demo | info | warn. Text may contain simple <b> markup from trusted code."""
    color = {"demo": "#B45309", "info": "#2563EB", "warn": "#C2410C"}.get(kind, "#2563EB")
    icon_name = {"demo": "flask", "info": "info", "warn": "alert"}.get(kind, "info")
    title_html = f"<b>{escape(title)}</b> " if title else ""
    _html(f'<div class="ei-banner {kind}">{icon(icon_name, color, 18)}<div>{title_html}{text}</div></div>')


def demo_banner(what: str = "This page uses a synthetic demonstration dataset.") -> None:
    if st.session_state.get("settings", {}).get("show_demo_labels", True):
        banner(f"{escape(what)} Upload your own meter data on the <b>Datasets</b> page to analyse real consumption.",
               kind="demo", title="Demo data.")


def empty_state(title: str, body: str, icon_name: str = "inbox") -> None:
    _html(
        f"""<div class="ei-empty"><div class="ei-empty-icon">{icon(icon_name, "#2563EB", 22)}</div>
        <h4>{escape(title)}</h4><p>{escape(body)}</p></div>"""
    )


def item_list(items: list[dict]) -> None:
    """Render a list of {title, body, icon, tone} rows inside a card."""
    rows = []
    for it in items:
        fg, bg = _TONES.get(it.get("tone", "blue"), _TONES["blue"])
        rows.append(
            f"""<div class="ei-item"><div class="ei-item-icon" style="background:{bg};">{icon(it.get('icon', 'info'), fg, 15)}</div>
            <div><div class="ei-item-title">{escape(it['title'])}</div>
            <div class="ei-item-body">{escape(it.get('body', ''))}</div></div></div>"""
        )
    _html(f'<div class="ei-card"><div class="ei-list">{"".join(rows)}</div></div>')


def check_list(checks: list[dict]) -> None:
    """Render validation checks: {status: ok|warn|error, title, detail}."""
    colors = {"ok": ("check", "#16A34A"), "warn": ("alert", "#D97706"), "error": ("x", "#DC2626")}
    rows = []
    for c in checks:
        name, color = colors.get(c["status"], colors["warn"])
        rows.append(
            f'<div class="ei-check">{icon(name, color, 18)}<div><b>{escape(c["title"])}</b><br>'
            f'<span class="d">{escape(c.get("detail", ""))}</span></div></div>'
        )
    _html(f'<div class="ei-card">{"".join(rows)}</div>')


def footer() -> None:
    _html(
        '<div class="ei-footer">EnergyIntel · Energy Intelligence Platform · Frontend v1.0 · '
        'Demonstration data and placeholder results are labelled. Validate models before operational use.</div>'
    )
