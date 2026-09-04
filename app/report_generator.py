"""
Sehat Saathi - PDF Health Report Generator
============================================
Generates a downloadable PDF summary of a chat session.

Layout:
  - Cover section: title, date, session ID, disclaimer
  - Summary box: languages detected, query count, emergency alerts
  - Conversation transcript: each Q&A exchange, formatted cleanly
  - Important helplines footer on last page

Uses fpdf2 (pip install fpdf2) — pure Python, no system fonts needed.
Falls back gracefully if fpdf2 is not installed.
"""
from __future__ import annotations

import re
import io
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

# ── Strip markdown so PDF text stays clean ───────────────────────────────────
_MD_STRIP = re.compile(
    r"(\*{1,3}|_{1,3}|`{1,3})"   # bold / italic / code
    r"|!\[.*?\]\(.*?\)"           # images
    r"|\[([^\]]+)\]\([^)]+\)"    # links -> keep label
    r"|#+\s*"                     # headings
    r"|>\s*"                      # blockquotes
    r"|[-*+]\s+"                  # unordered list bullets
    r"|\d+\.\s+"                  # ordered list
)

# Characters outside latin-1 that we want to replace with ASCII equivalents
_UNICODE_SUBS = str.maketrans({
    "\u2014": "--",   # em dash
    "\u2013": "-",    # en dash
    "\u2019": "'",    # right single quote
    "\u2018": "'",    # left single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
    "\u2022": "-",    # bullet
    "\u2713": "[OK]", # checkmark
    "\u2715": "[X]",  # cross
    "\u00b0": " deg", # degree
    "\u20b9": "Rs.",  # rupee sign
    # Emoji / symbols used in our UI text
    "\U0001f3e5": "[Hospital]",
    "\U0001f489": "[Needle]",
    "\U0001f321": "[Thermometer]",
    "\U0001f6a8": "[Emergency]",
    "\U0001f4ac": "[Chat]",
    "\U0001f4ca": "[Chart]",
    "\u2764": "<3",
    "\u2714": "[OK]",
    "\u26a0": "[!]",
    "\u2705": "[OK]",
    "\u274c": "[X]",
    "\U0001f517": "[link]",
})


def _safe(text: str) -> str:
    """
    Make text safe for fpdf Helvetica (latin-1 encoding).
    1. Replace known Unicode chars with ASCII equivalents.
    2. Drop any remaining non-latin-1 characters.
    """
    text = text.translate(_UNICODE_SUBS)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def _strip_md(text: str) -> str:
    """Remove markdown syntax, keep readable text."""
    text = _MD_STRIP.sub(lambda m: m.group(2) or "", text)
    # collapse excess blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Colour palette ────────────────────────────────────────────────────────────
C_HEADER_BG   = (59, 130, 212)   # IBM blue
C_HEADER_TEXT = (255, 255, 255)
C_USER_BG     = (220, 248, 198)  # WhatsApp-style green bubble
C_BOT_BG      = (245, 245, 250)  # Light grey
C_EMRG_BG     = (254, 226, 226)  # Soft red
C_TEXT        = (31, 35, 40)
C_MUTED       = (87, 96, 106)
C_BORDER      = (229, 231, 235)
C_ACCENT      = (59, 130, 212)


def generate_pdf(
    messages: List[Dict],
    session_id: str = "unknown",
) -> bytes:
    """
    Build a PDF from a list of chat messages and return raw bytes.

    Each message dict must have:
      role        : "user" | "assistant"
      content     : str  (may contain markdown)
      timestamp   : str  (HH:MM)
      is_emergency: bool (optional)
      detected_language: str (optional)
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError(
            "fpdf2 is not installed. Run: pip install fpdf2"
        )

    # ── Summarise session ────────────────────────────────────────────────────
    user_msgs = [m for m in messages if m["role"] == "user"]
    bot_msgs  = [m for m in messages if m["role"] == "assistant"]
    has_emergency = any(m.get("is_emergency") for m in bot_msgs)
    languages = list({
        m.get("detected_language", "en")
        for m in bot_msgs
        if m.get("detected_language")
    })

    LANG_NAMES = {
        "en": "English", "hi": "Hindi", "kn": "Kannada",
        "ta": "Tamil", "te": "Telugu", "bn": "Bengali",
        "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "ml": "Malayalam",
    }
    lang_display = ", ".join(LANG_NAMES.get(l, l.upper()) for l in languages) or "English"

    now_str    = datetime.now().strftime("%d %B %Y, %H:%M")
    date_str   = datetime.now().strftime("%d %B %Y")
    sid_short  = session_id[:16] + ("..." if len(session_id) > 16 else "")

    # ── PDF setup ─────────────────────────────────────────────────────────────
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    W = pdf.w - 36   # usable width

    # ── Header bar ───────────────────────────────────────────────────────────
    pdf.set_fill_color(*C_HEADER_BG)
    pdf.rect(0, 0, pdf.w, 28, "F")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*C_HEADER_TEXT)
    pdf.set_xy(18, 8)
    pdf.cell(W, 8, _safe("Sehat Saathi - Health Conversation Report"), ln=False)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, 18)
    pdf.cell(W, 6, "Powered by IBM watsonx.ai (Granite) + LangChain", ln=True)

    pdf.ln(10)

    # ── Meta row ─────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(W / 3, 5, f"Date: {date_str}", ln=False)
    pdf.cell(W / 3, 5, f"Session: {sid_short}", ln=False)
    pdf.cell(W / 3, 5, f"Generated: {now_str}", ln=True)
    pdf.ln(3)

    # ── Disclaimer box ────────────────────────────────────────────────────────
    pdf.set_fill_color(255, 243, 205)   # amber tint
    pdf.set_draw_color(*C_BORDER)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 80, 0)
    pdf.multi_cell(
        W, 5,
        "DISCLAIMER: This report is an AI-generated health awareness summary only. "
        "It is NOT a medical diagnosis or prescription. Always consult a qualified "
        "healthcare professional for medical advice. For emergencies call 108.",
        border=1, fill=True,
    )
    pdf.ln(5)

    # ── Summary box ──────────────────────────────────────────────────────────
    pdf.set_fill_color(240, 248, 255)
    pdf.set_draw_color(*C_ACCENT)
    x0 = pdf.get_x(); y0 = pdf.get_y()
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(W, 6, "Session Summary", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_TEXT)

    summary_lines = [
        f"Total exchanges    : {len(user_msgs)} question(s)",
        f"Language(s) used   : {lang_display}",
        f"Emergency alerts   : {'YES - see transcript below' if has_emergency else 'None'}",
    ]
    for line in summary_lines:
        pdf.cell(W, 5, line, ln=True)
    pdf.ln(6)

    # ── Horizontal rule ───────────────────────────────────────────────────────
    pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.4)
    pdf.line(18, pdf.get_y(), 18 + W, pdf.get_y())
    pdf.ln(4)

    # ── Section heading ───────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(W, 6, "Conversation Transcript", ln=True)
    pdf.ln(3)

    # ── Transcript ────────────────────────────────────────────────────────────
    # Pair messages: user + following assistant reply
    pairs: List[tuple] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg["role"] == "user":
            nxt = messages[i + 1] if i + 1 < len(messages) and messages[i+1]["role"] == "assistant" else None
            pairs.append((msg, nxt))
            i += 2 if nxt else 1
        else:
            i += 1

    for idx, (user_msg, bot_msg) in enumerate(pairs, 1):
        ts = user_msg.get("timestamp", "")

        # ── Q label ──────────────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(W, 4, _safe(f"Q{idx}  {ts}"), ln=True)

        # ── User bubble ──────────────────────────────────────────────────────
        user_text = _safe(_strip_md(user_msg["content"]))
        pdf.set_fill_color(*C_USER_BG)
        pdf.set_draw_color(*C_BORDER)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*C_TEXT)
        pdf.multi_cell(W, 5, user_text, border="LRB", fill=True, align="L")
        pdf.ln(2)

        if bot_msg:
            is_emrg = bot_msg.get("is_emergency", False)
            bot_text = _safe(_strip_md(bot_msg["content"]))
            bot_ts   = bot_msg.get("timestamp", "")
            lang_tag = LANG_NAMES.get(bot_msg.get("detected_language", "en"), "")

            # ── A label ──────────────────────────────────────────────────────
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*C_MUTED)
            label_parts = [f"Sehat Saathi  {bot_ts}"]
            if lang_tag:
                label_parts.append(f"[{lang_tag}]")
            if is_emrg:
                label_parts.append("[!] EMERGENCY")
            pdf.cell(W, 4, _safe("   ".join(label_parts)), ln=True)

            # ── Bot bubble ───────────────────────────────────────────────────
            bg = C_EMRG_BG if is_emrg else C_BOT_BG
            pdf.set_fill_color(*bg)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*C_TEXT)
            pdf.multi_cell(W, 5, bot_text, border="LRB", fill=True, align="L")

        pdf.ln(5)

    # ── Helplines footer on last page ─────────────────────────────────────────
    pdf.ln(6)
    pdf.set_draw_color(*C_BORDER)
    pdf.line(18, pdf.get_y(), 18 + W, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(W, 6, "Important Emergency Helplines (India)", ln=True)
    helplines = [
        ("108", "Ambulance / Emergency"),
        ("104", "National Health Helpline"),
        ("1098", "Childline"),
        ("1091", "Women's Helpline"),
        ("9152987821", "iCall Mental Health"),
    ]
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_TEXT)
    col = W / len(helplines)
    for num, label in helplines:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*C_HEADER_BG)
        pdf.cell(col, 6, num, ln=False, align="C")
    pdf.ln(6)
    for num, label in helplines:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(col, 4, label, ln=False, align="C")
    pdf.ln(10)

    # ── Page-number footer ────────────────────────────────────────────────────
    pdf.set_y(-12)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(0, 4, _safe(f"Sehat Saathi - AI Health Awareness | Not a medical diagnostic tool | {now_str}"), align="C")

    return bytes(pdf.output())
