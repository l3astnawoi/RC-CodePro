"""RC CodePro — shared UI foundation (STEP 2).

Presentation-only helpers used across every page so the whole app reads as
one program.  Nothing in this module performs an engineering calculation:

* utilisation ratios are a plain ``demand / capacity`` division used **only**
  to size a progress bar and pick a colour; they never feed a PASS/FAIL
  decision — callers pass their own ``ok`` flag from the calculation engine.
* every value shown comes straight from the caller.

Design tokens live in ``assets/rc_theme.css`` (``:root`` custom properties);
``TOKENS`` below mirrors the few needed when building inline HTML.
"""

from __future__ import annotations

import html as _html
import math
import os
from contextlib import contextmanager

import streamlit as st

from utils.project import get_project_info

__all__ = [
    "TOKENS",
    "inject_theme",
    "top_header",
    "breadcrumb",
    "page_header",
    "section_card",
    "status_badge",
    "status_badge_html",
    "utilization",
    "result_card",
    "engineering_table",
    "kpi",
    "project_card",
    "project_summary",
    "nav_card",
]

_CSS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "rc_theme.css",
)

# Python mirror of the CSS :root tokens (for inline-HTML components only).
TOKENS = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "surface_2": "#1c2230",
    "border": "#2a3441",
    "border_strong": "#3a4553",
    "primary": "#2f81f7",
    "success": "#238636", "success_text": "#3fb950",
    "warning": "#9e6a03", "warning_text": "#d29922",
    "danger": "#da3633", "danger_text": "#f85149",
    "text": "#e6edf3",
    "text_secondary": "#adbac7",
    "text_muted": "#8b949e",
}


def _esc(value) -> str:
    return _html.escape("" if value is None else str(value))


# ---------------------------------------------------------------------------
# Theme injection
# ---------------------------------------------------------------------------
def inject_theme() -> None:
    """Inject ``assets/rc_theme.css`` once for the current rerun.

    Call once near the top of the app (after ``st.set_page_config``).  Safe
    to call every rerun — Streamlit rebuilds the DOM each time, so the style
    tag must be re-emitted.
    """
    try:
        with open(_CSS_PATH, "r", encoding="utf-8") as fh:
            css = fh.read()
    except OSError:
        return
    st.html(f"<style>\n{css}\n</style>")


# ---------------------------------------------------------------------------
# Chrome — top header, breadcrumb, page header
# ---------------------------------------------------------------------------
def top_header(module_name: str = "", *, project_name: str | None = None,
               code: str = "ACI 318M-08", units: str = "MKS") -> None:
    """Slim application header bar (informational only — no action buttons).

    left   : ``RC CodePro / <module>``
    right  : ``<project name> · <code> · <units>`` — only fields that exist.
    """
    if project_name is None:
        project_name = get_project_info().get("project_name", "")
    mod = (f'<span class="rc-sep">/</span>'
           f'<span class="rc-topbar-module">{_esc(module_name)}</span>'
           if module_name else "")
    right_bits = []
    if project_name:
        right_bits.append(f'<span class="rc-topbar-proj">'
                          f'{_esc(project_name)}</span>')
    if code:
        right_bits.append(f'<span class="rc-topbar-tag">{_esc(code)}</span>')
    if units:
        right_bits.append(f'<span class="rc-topbar-tag">{_esc(units)}</span>')
    right_html = '<span class="rc-sep">·</span>'.join(right_bits)
    st.html(
        '<div class="rc-topbar">'
        f'<div class="rc-topbar-left"><span class="rc-topbar-brand">'
        f'RC CodePro</span>{mod}</div>'
        f'<div class="rc-topbar-right">{right_html}</div>'
        '</div>'
    )


def breadcrumb(*parts: str) -> None:
    """Small muted trail, e.g. ``breadcrumb("Member Design", "Beam")``."""
    items = ' <span class="rc-sep">/</span> '.join(
        _esc(p) for p in parts if p)
    st.html(f'<nav class="rc-breadcrumb">{items}</nav>')


def page_header(title: str, subtitle: str | None = None, *,
                crumbs: "tuple[str, ...] | list[str] | None" = None,
                status: "tuple[str, str] | tuple[str] | str | None" = None
                ) -> None:
    """Breadcrumb + H1 + subtitle, with an optional trailing status badge.

    ``status`` accepts ``"pass"`` / ``("fail", "OVER")`` / etc.
    """
    if crumbs:
        breadcrumb(*crumbs)
    badge = ""
    if status is not None:
        if isinstance(status, str):
            badge = status_badge_html(status)
        else:
            badge = status_badge_html(*status)
    sub = (f'<p class="rc-page-subtitle">{_esc(subtitle)}</p>'
           if subtitle else "")
    st.html(
        '<div class="rc-page-header">'
        f'<div class="rc-page-title-row">'
        f'<h1 class="rc-page-title">{_esc(title)}</h1>{badge}</div>'
        f'{sub}</div>'
    )


# ---------------------------------------------------------------------------
# Section card
# ---------------------------------------------------------------------------
@contextmanager
def section_card(title: str | None = None):
    """Bordered surface with an uppercase header — the standard wrapper for
    'Section & Material', 'Loads', 'Reinforcement', 'Grid Setup', ...

    Usage::

        with ui.section_card("Section & Material"):
            b = st.number_input(...)
    """
    box = st.container(border=True)
    with box:
        if title:
            st.html(f'<div class="rc-card-title">{_esc(title)}</div>')
        yield box


# ---------------------------------------------------------------------------
# Status badge
# ---------------------------------------------------------------------------
_BADGE = {
    "pass": ("✓", "PASS", "rc-badge-pass"),
    "ok": ("✓", "PASS", "rc-badge-pass"),
    "fail": ("✕", "FAIL", "rc-badge-fail"),
    "warn": ("⚠", "WARNING", "rc-badge-warn"),
    "warning": ("⚠", "WARNING", "rc-badge-warn"),
    # First-class "REVIEW" verdict state (limitation / unresolved condition —
    # distinct from a design FAIL and from a plain non-verdict warning).
    "review": ("⚠", "REVIEW", "rc-badge-warn"),
    "info": ("ⓘ", "INFO", "rc-badge-info"),
}


def status_badge_html(state, text: str | None = None) -> str:
    """Return the badge HTML.  ``state`` may be a key
    (``pass|fail|warn|info``) or a bool (True->pass, False->fail).
    Colour is never the only signal — icon + label are always present."""
    if isinstance(state, bool):
        state = "pass" if state else "fail"
    icon, default_label, cls = _BADGE.get(str(state).lower(), _BADGE["info"])
    label = default_label if text is None else str(text)
    return (f'<span class="rc-badge {cls}">'
            f'<span class="rc-badge-ico">{icon}</span>{_esc(label)}</span>')


def status_badge(state, text: str | None = None) -> None:
    st.html(status_badge_html(state, text))


# ---------------------------------------------------------------------------
# Utilisation bar  (display-only demand/capacity ratio)
# ---------------------------------------------------------------------------
def _ratio(demand, capacity) -> float:
    try:
        d, c = float(demand), float(capacity)
    except (TypeError, ValueError):
        return math.inf
    if c == 0.0:
        return math.inf if d > 0.0 else 0.0
    return d / c


def _util_state(ratio: float) -> str:
    if not math.isfinite(ratio) or ratio > 1.0:
        return "fail"
    if ratio >= 0.90:
        return "near"
    return "ok"


def utilization(label: str, demand, capacity, *, ratio: float | None = None
                ) -> None:
    """Render one utilisation row: label, ratio value, and a bar.

    Pass ``ratio`` directly if the engine already computed it; otherwise it
    is derived as ``demand / capacity`` purely for the bar length / colour.
    Thresholds: ``< 0.90`` normal · ``0.90–1.00`` near limit · ``> 1.00`` fail.
    """
    r = _ratio(demand, capacity) if ratio is None else float(ratio)
    state = _util_state(r)
    pct = 100.0 if not math.isfinite(r) else max(0.0, min(r, 1.0)) * 100.0
    val = "N/A" if not math.isfinite(r) else f"{r:.2f}"
    st.html(
        f'<div class="rc-util rc-util--{state}">'
        f'<div class="rc-util-head"><span class="rc-util-label">'
        f'{_esc(label)}</span><span class="rc-util-val">{val}</span></div>'
        f'<div class="rc-util-track"><div class="rc-util-fill" '
        f'style="width:{pct:.1f}%"></div></div></div>'
    )


# ---------------------------------------------------------------------------
# Result card
# ---------------------------------------------------------------------------
def result_card(title: str, demand, capacity, unit: str, ok: bool, *,
                ratio: float | None = None,
                demand_fmt: str = ",.0f", capacity_fmt: str = ",.0f") -> None:
    """Demand / Capacity + utilisation bar + PASS/FAIL badge.

    ``ok`` is the engineering verdict supplied by the caller — this helper
    never decides pass/fail.
    """
    def _fmt(v, spec):
        try:
            return format(float(v), spec)
        except (TypeError, ValueError):
            return _esc(v)

    badge = status_badge_html(bool(ok))
    st.html(
        f'<div class="rc-result-card">'
        f'<div class="rc-result-title">{_esc(title)}</div>'
        f'<div class="rc-result-dc">{_fmt(demand, demand_fmt)} / '
        f'{_fmt(capacity, capacity_fmt)}<span class="rc-unit">'
        f'{_esc(unit)}</span></div></div>'
    )
    utilization("Utilization", demand, capacity, ratio=ratio)
    st.html(f'<div class="rc-result-foot">{badge}</div>')


# ---------------------------------------------------------------------------
# KPI  (compact metric alternative)
# ---------------------------------------------------------------------------
def kpi(label: str, value, sub: str | None = None) -> None:
    sub_html = f'<div class="rc-kpi-sub">{_esc(sub)}</div>' if sub else ""
    st.html(
        f'<div class="rc-kpi"><div class="rc-kpi-label">{_esc(label)}</div>'
        f'<div class="rc-kpi-value">{_esc(value)}</div>{sub_html}</div>'
    )


# ---------------------------------------------------------------------------
# Engineering table
# ---------------------------------------------------------------------------
def engineering_table(headers, rows, *, right_from: int = 1,
                      emphasize_last: bool = False) -> None:
    """Dark, dense, right-aligned-numeric table.

    ``headers`` : list of column titles.
    ``rows``    : list of row sequences (values are stringified as-is).
    ``right_from`` : first column index that is right-aligned.
    ``emphasize_last`` : shade + bold the final row (totals).
    """
    def cls(k):
        return ' class="rc-num"' if k >= right_from else ""

    head = "".join(f"<th{cls(k)}>{_esc(h)}</th>" for k, h in enumerate(headers))
    body = []
    n = len(rows)
    for i, row in enumerate(rows):
        tr_cls = ' class="rc-eng-total"' if emphasize_last and i == n - 1 else ""
        cells = "".join(f"<td{cls(k)}>{_esc(c)}</td>"
                        for k, c in enumerate(row))
        body.append(f"<tr{tr_cls}>{cells}</tr>")
    st.html(
        '<table class="rc-eng-table">'
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table>'
    )


# ---------------------------------------------------------------------------
# Project summary — read-only key/value card (editing lives on the
# Project page).  The Project page is the single source of truth.
# ---------------------------------------------------------------------------
def project_summary(rows, *, title: str = "PROJECT") -> None:
    """Render a titled read-only card from ``rows`` = ``[(label, value), ...]``."""
    meta = "".join(
        f'<div><dt>{_esc(lbl)}</dt><dd>{_esc(val)}</dd></div>'
        for lbl, val in rows
    )
    st.html(
        '<div class="rc-project-card">'
        f'<div class="rc-project-card-head">{_esc(title)}</div>'
        f'<dl class="rc-project-meta">{meta}</dl>'
        '</div>'
    )


def project_card() -> None:
    """Compact project summary for the sidebar (name + engineer/location/date).
    Reads the current values via ``get_project_info()`` — never edits state.
    """
    info = get_project_info()
    project_summary(
        [
            ("Project", info.get("project_name", "-")),
            ("Engineer", info.get("engineer", "-")),
            ("Location", info.get("location", "-")),
            ("Date", info.get("date", "-")),
        ],
        title="PROJECT",
    )


# ---------------------------------------------------------------------------
# Navigation card — bordered tile + native st.page_link to an existing page
# ---------------------------------------------------------------------------
def nav_card(page, title: str, subtitle: str = "", *,
             open_label: str | None = None,
             icon: str = ":material/arrow_forward:") -> None:
    """A compact card that links to an existing ``st.Page`` via
    ``st.page_link`` (native routing — no workaround).  ``page`` is the
    ``st.Page`` object from ``main.py``.
    """
    with st.container(border=True):
        st.markdown(f"**{_esc(title)}**")
        if subtitle:
            st.caption(subtitle)
        st.page_link(page, label=open_label or f"Open {title}", icon=icon)
