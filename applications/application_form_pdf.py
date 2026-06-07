"""
Fill APPLICATION-FORM-THA.pdf by overlaying applicant/application data.

Coordinates are tuned for ``static/forms/APPLICATION-FORM-THA.pdf`` (Letter 612×792 pt).
Use only ASCII in overlays where possible (built-in Helvetica lacks bullets / em-dash).

If the city replaces the PDF, re-measure with PyMuPDF ``page.get_text('dict')`` or ``search_for``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF
from django.conf import settings
from django.utils import timezone


TEMPLATE_RELATIVE = Path('static') / 'forms' / 'APPLICATION-FORM-THA.pdf'


def _template_path() -> Path:
    return Path(settings.BASE_DIR) / TEMPLATE_RELATIVE


def _safe_str(value, empty: str = '') -> str:
    if value is None:
        return empty
    if isinstance(value, Decimal):
        s = format(value, 'f').rstrip('0').rstrip('.')
        return s if s else '0'
    return str(value).strip()


def _overlay_ascii(text: str, max_len: int | None = None) -> str:
    """Helvetica overlay: strip/replace chars outside printable ASCII (avoids stray '?')."""
    s = _safe_str(text)
    s = ''.join(c if 32 <= ord(c) < 127 else ' ' for c in s)
    s = ' '.join(s.split())
    if max_len is not None:
        s = s[:max_len]
    return s


def _fmt_date(d) -> str:
    if not d:
        return ''
    return d.strftime('%m/%d/%Y')


def _insert_after(page, needle: str, text: str, *, dx: float = 3, dy: float = 2, fontsize: float = 8.5):
    rects = page.search_for(needle)
    if not rects or not text:
        return
    r = rects[0]
    page.insert_text(
        fitz.Point(r.x1 + dx, r.y1 + dy),
        text,
        fontsize=fontsize,
        fontname='helv',
        color=(0, 0, 0),
    )


def _insert_box(page, rect: tuple[float, float, float, float], text: str, fontsize: float = 8):
    if not text:
        return
    r = fitz.Rect(rect)
    rc = page.insert_textbox(
        r,
        text,
        fontsize=fontsize,
        fontname='helv',
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_LEFT,
    )
    if rc < 0:
        page.insert_text(fitz.Point(rect[0], rect[1] + fontsize), text[:120], fontsize=fontsize, fontname='helv')


def _baseline(page, x: float, y: float, text: str, *, fontsize: float = 8.5):
    """Draw single-line text sitting on a ruled baseline (PDF y grows downward)."""
    text = _overlay_ascii(text)
    if not text:
        return
    page.insert_text(
        fitz.Point(x, y),
        text,
        fontsize=fontsize,
        fontname='helv',
        color=(0, 0, 0),
    )


def _baseline_after_needle(
    page,
    needle: str,
    text: str,
    *,
    dx: float = 3,
    baseline_y: float,
    fontsize: float = 8.5,
):
    """Place text after ``needle`` at fixed baseline (keeps wide fields off row-1 labels)."""
    text = _overlay_ascii(text)
    if not text:
        return
    rects = page.search_for(needle)
    if not rects:
        return
    r = rects[0]
    page.insert_text(
        fitz.Point(r.x1 + dx, baseline_y),
        text,
        fontsize=fontsize,
        fontname='helv',
        color=(0, 0, 0),
    )


def _wrap_two_lines(text: str, first_max: int = 52, second_max: int = 62):
    """Split address-ish text onto two lines without breaking mid-word when possible."""
    t = _safe_str(text)
    if len(t) <= first_max:
        return t, ''
    cut = t.rfind(' ', 0, first_max + 1)
    if cut <= 0:
        cut = first_max
    line1 = t[:cut].strip()
    rest = t[cut:].strip()
    if len(rest) > second_max:
        rest = rest[: second_max - 3].rstrip() + '...'
    return line1, rest


def _formal_name_for_sections(applicant) -> str:
    """
    Section D/F/G display format:
    First Middle LAST [EXT]
    Example: "Trix Justin Aurelio AGUILAR"
    """
    first = _safe_str(getattr(applicant, 'first_name', ''))
    middle = _safe_str(getattr(applicant, 'middle_name', ''))
    last = _safe_str(getattr(applicant, 'last_name', '')).upper()
    ext = _safe_str(getattr(applicant, 'extension_name', ''))

    parts = [p for p in (first, middle, last) if p]
    display = ' '.join(parts).strip()
    if ext:
        display = f'{display} {ext}'.strip()
    return display


def _endorsement_name_band(page, full_name: str):
    """Section D: fill gap between 'hereby endorsing' and 'qualified to avail'."""
    endo = page.search_for('hereby endorsing')
    qual = page.search_for('qualified to avail')
    if not full_name or not endo or not qual:
        return
    left, right = endo[0].x1 + 3, qual[0].x0 - 4
    top, bot = min(endo[0].y0, qual[0].y0) - 0.5, max(endo[0].y1, qual[0].y1) + 2.5
    if right - left < 36:
        return
    _insert_box(page, (left, top, right, bot), _overlay_ascii(full_name, 34), fontsize=7.4)


def _section_f_applicant_line(page, full_name: str):
    """Underscore line: '______________________________ to avail' (recommend approval)."""
    hits = page.search_for('______________________________ to avail')
    if not full_name or not hits:
        return
    r = hits[0]
    pad = 2
    _insert_box(
        page,
        (r.x0 + pad, r.y0 + 0.9, r.x1 - pad, r.y1 + 0.7),
        _overlay_ascii(full_name, 34),
        fontsize=7.4,
    )


def _section_g_applicant_line(page, full_name: str):
    """Blank between trailing 'Application of' clause and ' is hereby'."""
    needles = (
        'Board, the Application of',
        'City Housing Board, the Application of',
    )
    start_rect = None
    for nd in needles:
        hit = page.search_for(nd)
        if hit:
            start_rect = hit[0]
            break
    hereby = page.search_for(' is hereby')
    if not full_name or not start_rect or not hereby:
        return
    left = start_rect.x1 + 3
    right = hereby[0].x0 - 2
    top = hereby[0].y0 - 1
    bot = hereby[0].y1 + 2
    if right - left < 40:
        return
    _insert_box(page, (left, top + 0.4, right, bot - 0.2), _overlay_ascii(full_name, 34), fontsize=7.4)


def build_filled_application_pdf(applicant, application) -> bytes:
    """Return PDF bytes for the filled THA application form."""
    path = _template_path()
    if not path.is_file():
        raise FileNotFoundError(f'Missing application form template: {path}')

    doc = fitz.open(path)
    gen_local = timezone.localtime(application.form_generated_at)

    # --- Page 1 (identity / household / income) ---
    p0 = doc[0]

    _insert_after(p0, 'Date:', gen_local.strftime('%m/%d/%Y'), fontsize=9)

    header_note = _safe_str(application.application_number)
    ref = _safe_str(applicant.reference_number)
    if ref:
        header_note = f'{header_note}  |  Ref {ref}'
    _insert_box(p0, (74, 96, 430, 112), header_note, fontsize=7.5)

    # Section A baselines measured from APPLICATION-FORM-THA underscore spans (insert_textbox sat too high).
    LX = 188
    FS = 8.5

    # Name-of-applicant lanes (Last / First / Middle) — slightly re-anchored so
    # values sit cleaner above each printed lane without drifting into each other.
    _baseline(p0, 188, 288.95, _overlay_ascii(applicant.last_name, 16), fontsize=FS)
    _baseline(p0, 326, 288.95, _overlay_ascii(applicant.first_name, 18), fontsize=FS)
    middle_with_ext = _safe_str(applicant.middle_name)
    ext = _safe_str(applicant.extension_name)
    if ext:
        middle_with_ext = f'{middle_with_ext} {ext}'.strip()
    _baseline(p0, 432, 288.95, _overlay_ascii(middle_with_ext, 14), fontsize=FS)

    sex_display = applicant.get_sex_display() if applicant.sex else ''
    _baseline(p0, LX, 309.45, sex_display[:22], fontsize=FS)
    age_val = applicant.age if applicant.age is not None else ''
    _baseline(p0, 392, 309.45, _safe_str(age_val), fontsize=FS)

    _baseline(p0, LX, 323.9, _fmt_date(applicant.date_of_birth), fontsize=FS)
    _baseline(p0, 428, 323.9, _safe_str(applicant.place_of_birth), fontsize=FS)

    _baseline(p0, LX, 336.0, 'Filipino', fontsize=FS)
    civ_display = applicant.get_civil_status_display() if applicant.civil_status else ''
    _baseline(p0, 392, 336.0, _overlay_ascii(civ_display, 22), fontsize=FS)

    barangay_name = getattr(applicant.barangay, 'name', None) or ''
    addr = ', '.join(x for x in (_safe_str(applicant.current_address), barangay_name) if x)
    line1, line2 = _wrap_two_lines(addr)
    # Present address spans two rules — lift further so rules don't bisect glyphs.
    _baseline(p0, LX, 346.2, line1, fontsize=FS)
    if line2:
        _baseline(p0, LX, 358.4, line2, fontsize=FS)

    _baseline(p0, LX, 372.5, _safe_str(applicant.years_residing), fontsize=FS)

    _baseline(p0, LX, 396.8, _safe_str(applicant.spouse_name), fontsize=FS)
    _baseline(p0, LX, 408.9, _safe_str(applicant.phone_number), fontsize=FS)

    members = list(applicant.household_members.all()[:4])
    # Household rows — align slightly above each underscore (same tuning idea as Section A).
    hb_lines = (479.85, 492.0, 504.1, 516.2)
    for i, bl in enumerate(hb_lines):
        if i >= len(members):
            break
        m = members[i]
        rel = m.get_relationship_display() if m.relationship else ''
        civ = m.get_civil_status_display() if m.civil_status else ''
        _baseline(p0, 78, bl, _overlay_ascii(m.full_name, 34), fontsize=7.8)
        _baseline(p0, 225, bl, _overlay_ascii(rel, 22), fontsize=7.8)
        _baseline(p0, 332, bl, _overlay_ascii(str(m.age), 8), fontsize=7.8)
        _baseline(p0, 442, bl, _overlay_ascii(civ, 22), fontsize=7.8)

    # Section C — lift slightly so occupation / employment / income sit above the rule (not struck through).
    row1_bl = 553.92
    row2_bl = 565.62

    occ = _overlay_ascii(applicant.occupation, 42)
    emp_status = (
        _overlay_ascii(applicant.get_employment_status_display(), 34)
        if applicant.employment_status
        else ''
    )
    _baseline(p0, 147, row1_bl, occ, fontsize=FS)
    _baseline_after_needle(
        p0,
        'Status of Employment  :',
        emp_status,
        dx=2,
        baseline_y=row1_bl,
        fontsize=FS,
    )

    employer_txt = ''
    inc = applicant.monthly_income
    inc_txt = _overlay_ascii(_safe_str(inc) if inc is not None else '', 22)
    _baseline(p0, 147, row2_bl, employer_txt, fontsize=FS)
    _baseline_after_needle(
        p0,
        'Monthly Income :',
        inc_txt,
        dx=3,
        baseline_y=row2_bl,
        fontsize=FS,
    )

    # --- Page 2 ---
    if len(doc) > 1:
        p1 = doc[1]
        full = _formal_name_for_sections(applicant)
        _endorsement_name_band(p1, full)
        _section_f_applicant_line(p1, full)
        _section_g_applicant_line(p1, full)

    pdf_bytes = doc.tobytes(deflate=True, garbage=4, clean=True)
    doc.close()
    return pdf_bytes
