"""Presentation only: local fonts, decorative graphics and escaped HTML components."""
import base64
from datetime import datetime
from html import escape
from pathlib import Path
import streamlit as st

ASSETS = Path(__file__).resolve().parents[1] / "assets"
FONTS = (("Apex Display", "barlow-condensed-bold.ttf", "700"),
         ("Apex Sans", "space-grotesk.ttf", "300 700"),
         ("Apex Mono", "jetbrains-mono.ttf", "100 800"))


@st.cache_data(show_spinner=False)
def _styles(signature):
    css = (ASSETS / "theme.css").read_text(encoding="utf-8")
    for family, filename, weight in FONTS:
        path = ASSETS / "fonts" / filename
        if path.is_file():
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            css += f"@font-face{{font-family:'{family}';src:url(data:font/ttf;base64,{encoded}) format('truetype');font-weight:{weight};font-display:swap;}}"
    return css


def apply_theme():
    paths = [ASSETS / "theme.css", *(ASSETS / "fonts" / name for _, name, _ in FONTS)]
    signature = tuple(path.stat().st_mtime_ns if path.exists() else 0 for path in paths)
    st.html(f"<style>{_styles(signature)}</style>")


def brand():
    st.html('<div class="apex-brand"><div class="apex-brandmark"><span class="apex-slashes" aria-hidden="true"><i></i><i></i><i></i></span><span class="apex-wordmark">APEX</span></div><p>RACE INTELLIGENCE / AI2002</p></div>')


def sidebar_note():
    st.html('<div class="sidebar-note"><span class="apex-pill">DEMO ENVIRONMENT</span><p>Synthetic session data. Illustrative predictions. No live inputs or trained models connected.</p><div class="sidebar-signature">BUILT BY THE TEAM<br>M1 / SHAYAN · INTERFACE &amp; INTEGRATION</div></div>')


def topline(page):
    st.html(f'<div class="apex-topline"><div class="apex-breadcrumb">PADDOCK &nbsp;/&nbsp; <strong>{escape(page.upper())}</strong></div><span class="apex-pill">OFFLINE DEMO</span></div>')


def hero(eyebrow, first, second, description):
    graphic = (ASSETS / "racecar.svg").read_text(encoding="utf-8")
    st.html(f'<section class="apex-hero"><div><div class="apex-eyebrow">{escape(eyebrow)}</div><h1>{escape(first)}<br><span>{escape(second)}</span></h1><p>{escape(description)}</p></div><div class="hero-art">{graphic}<span class="hero-art-label">APEX / CONCEPT RACE CAR</span></div></section>')


def section(title, note=""):
    st.html(f'<div class="apex-section"><h2>{escape(title)}</h2><small>{escape(note)}</small></div>')


def race_banner(race):
    date = datetime.fromisoformat(race.local_date).strftime("%d %b %Y").upper()
    start = datetime.fromisoformat(race.start_utc.replace("Z", "+00:00")).strftime("%d %b / %H:%M UTC")
    name = race.name.removesuffix(" Grand Prix")
    st.html(f'<div class="race-banner"><div><div class="apex-eyebrow">SELECTED RACE WEEKEND</div><div class="race-name">{escape(name)}</div><div class="race-venue">{escape(race.circuit)} · Grand Prix · Static calendar</div></div><div class="race-date"><strong>{escape(date)}</strong><span>VENUE-LOCAL DATE</span><span>START {escape(start)}</span></div></div>')


def readiness_cards(inputs):
    cards = []
    for label, available, optional in (
        ("Q / QUALIFYING", inputs.qualifying_available_utc, False),
        ("FP / PRACTICE", inputs.practice_available_utc, True),
        ("WX / QUALIFYING WEATHER", inputs.weather_available_utc, False),
        ("GRID / FINAL START", inputs.grid_available_utc, False),
    ):
        state = "READY" if available else "NOT INCLUDED" if optional else "WAITING"
        detail = "Demo input available" if available else "Optional input" if optional else "Input not available"
        cards.append(f'<div class="readiness-item {"is-ready" if available else ""}"><small>{label}</small><strong>{state}</strong><span>{detail}</span></div>')
    st.html('<div class="readiness-grid" aria-label="Demo data readiness">' + "".join(cards) + '</div>')


def picks_cards(picks, names):
    cards = []
    for code in sorted(picks, key=lambda value: names[value]):
        first, _, last = names[code].rpartition(" ")
        cards.append(f'<article class="driver-card" aria-label="Demo podium pick: {escape(names[code], quote=True)}"><div class="driver-watermark" aria-hidden="true">{escape(code)}</div><small>DEMO PODIUM PICK / UNORDERED</small><div class="driver-first">{escape(first)}</div><div class="driver-last">{escape(last)}</div><div class="driver-bottom"><b>{escape(code)}</b><span>TOP-THREE SET</span></div></article>')
    st.html('<div class="driver-grid">' + "".join(cards) + '</div>')


def empty_forecast(ready):
    title = "Inputs ready. Your call." if ready else "Waiting for the green light."
    detail = "Generate a demo forecast to reveal the three-driver set." if ready else "Qualifying and its session weather are required. Explore a ready scenario using the demo controls."
    st.html(f'<div class="forecast-empty"><div class="start-lights" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div><div><h3>{title}</h3><p>{detail}</p></div></div>')


def compound_legend():
    st.html('<div class="compound-legend"><span><i></i>SOFT</span><span><i></i>MEDIUM</span><span><i></i>HARD</span><span>DEMO COMPOUNDS</span></div>')


def pipeline_cards(rows):
    cards = []
    for row in rows:
        state = "Files not supplied" if row["Status"].startswith("Missing:") else "Files present · validation pending"
        cards.append(f'<article class="pipeline-card"><small>MODEL DELIVERY</small><h3>{escape(row["Task"])}</h3><p>{state}</p></article>')
    st.html('<div class="pipeline-grid">' + "".join(cards) + '</div>')


def footer():
    st.html('<footer class="apex-footer"><span><strong>APEX</strong> &nbsp; / &nbsp; AI2002</span><span>QUALIFYING → GRID → PODIUM</span><span>DEMO INPUTS &amp; OUTPUTS · NOT LIVE</span></footer>')
