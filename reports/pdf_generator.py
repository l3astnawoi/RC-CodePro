"""One-page A4 PDF calculation sheets for RC design (ACI 318M-08) — Thai.

Public API
----------
generate_beam_report(inputs, results)    -> bytes
generate_column_report(inputs, results)  -> bytes
generate_slab_report(inputs, results)    -> bytes
generate_footing_report(inputs, results) -> bytes
generate_stair_report(inputs, results)   -> bytes

`inputs` / `results` are always passed in SI calculation units
(mm, mm^2, kN).  This module converts them for display:

    * section dimensions      -> cm   (2 decimals)
    * structural spans (L)     -> m    (3 decimals)
    * reinforcement areas      -> cm^2 (2 decimals)
    * footing axial loads P/Pu -> ตัน  (2 decimals, 1 ton = 9.80665 kN)

Missing dictionary keys render as "-".  `status` may be a bool or the
string "PASS" / "FAIL".

Rendered with **fpdf2** + **uharfbuzz** complex-text layout (``set_text_shaping``)
so Thai vowels and tone marks are positioned correctly.  Place
``THSarabunNew.ttf`` (optionally also "THSarabunNew Bold.ttf" /
"THSarabunNew Italic.ttf") in the project-level ``fonts/`` folder.  If the
font is missing the sheets are still produced with an fpdf2 core font
(Thai glyphs are stripped in that degraded mode).
"""

import os
from datetime import date
from io import BytesIO

from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ---------------------------------------------------------------------------
# Thai Unicode font
# ---------------------------------------------------------------------------

FONT_NAME = "THSarabun"
FONT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts"
)
FONT_REGULAR = os.path.join(FONT_DIR, "THSarabunNew.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "THSarabunNew Bold.ttf")
FONT_ITALIC = os.path.join(FONT_DIR, "THSarabunNew Italic.ttf")
FONT_BOLDITALIC = os.path.join(FONT_DIR, "THSarabunNew BoldItalic.ttf")

FONT_AVAILABLE = os.path.isfile(FONT_REGULAR)

# Active family: the Thai TrueType face when present, else an fpdf2 core font
# (Latin only — Thai glyphs are stripped by _t() in that degraded mode).
_FONT = FONT_NAME if FONT_AVAILABLE else "Helvetica"

# Point sizes — THSarabunNew is a tall, narrow face, so it must run large.
SZ_TITLE = 22
SZ_SECTION = 16
SZ_ROW = 15
SZ_META = 13
SZ_SMALL = 13
SZ_RESULT = 19
SZ_FOOTER = 11

# Vertical rhythm / column geometry (mm)
LH_ROW = 7.6
LABEL_W = 112.0

# Unit conversion
TON_TO_KN = 9.80665


def font_status_message():
    """Return a short status string about the Thai PDF font."""
    if FONT_AVAILABLE:
        return f"พบฟอนต์ภาษาไทยแล้ว: {FONT_REGULAR}"
    return (
        "ยังไม่พบไฟล์ฟอนต์ภาษาไทย — วางไฟล์ 'THSarabunNew.ttf' ไว้ในโฟลเดอร์ "
        f"'{FONT_DIR}' เพื่อให้รายงาน PDF แสดงภาษาไทยได้ถูกต้อง"
    )


# ---------------------------------------------------------------------------
# Formatting / unit helpers
# ---------------------------------------------------------------------------


def _t(text):
    """Coerce text to something the active font can render.

    The Thai Unicode font renders everything; the Latin core-font fallback
    (used when THSarabunNew.ttf is missing) cannot encode Thai, so replace
    any non-latin-1 character rather than let fpdf raise at output time.
    """
    s = str(text)
    if FONT_AVAILABLE:
        return s
    return s.encode("latin-1", "replace").decode("latin-1")


def _fmt(value, nd=2):
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "ผ่าน" if value else "ไม่ผ่าน"
    if isinstance(value, (int, float)):
        return f"{value:,.{nd}f}"
    return str(value)


def _cm(v):
    """mm -> cm."""
    return None if v is None else v / 10.0


def _cm2(v):
    """mm^2 -> cm^2."""
    return None if v is None else v / 100.0


def _ton(v):
    """kN -> metric ton."""
    return None if v is None else v / TON_TO_KN


KN_TO_KGF = 1000.0 / 9.80665      # 101.9716...


def _kgf(v):
    """kN -> kgf."""
    return None if v is None else v * KN_TO_KGF


def _kgfm(v):
    """kN.m -> kgf-m  (same numeric factor as kN -> kgf)."""
    return None if v is None else v * KN_TO_KGF


def _ksc(v):
    """MPa (N/mm^2) -> ksc (kgf/cm^2)."""
    return None if v is None else v / 0.0980665


def _f2(v):
    """cm^2 value already converted -> '#.##' string."""
    return _fmt(v, 2)


def _chk(ok):
    if ok is None:
        return "-"
    return "ผ่าน" if ok else "ไม่ผ่าน"


def _status_text(results):
    raw = results.get("status", results.get("passed"))
    if isinstance(raw, bool):
        return "PASS" if raw else "FAIL"
    return str(raw or "-").upper()


def _status_thai(passed):
    return "ผ่านมาตรฐาน (PASS)" if passed else "ไม่ผ่าน (FAIL)"


# ---------------------------------------------------------------------------
# PDF sheet
# ---------------------------------------------------------------------------


def _project_header(pdf, info):
    """Official calculation-sheet header: project name / location / engineer
    / date in an aligned two-column layout, closed with a horizontal rule."""
    if not info:
        return
    rows = [
        ("ชื่อโครงการ", info.get("project_name", "-")),
        ("สถานที่ก่อสร้าง", info.get("location", "-")),
        ("วิศวกรผู้ออกแบบ", info.get("engineer", "-")),
        ("วันที่", info.get("date", "-")),
    ]
    pdf.set_text_color(0, 0, 0)
    for label, value in rows:
        pdf.set_font(_FONT, "B", SZ_META)
        pdf.cell(46, 6.5, _t(label))
        pdf.set_font(_FONT, "", SZ_META)
        pdf.cell(0, 6.5, _t(f":  {value}"),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    y = pdf.get_y() + 1.5
    pdf.set_draw_color(120, 120, 120)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(3)


class _Sheet(FPDF):
    report_title = "ใบคำนวณการออกแบบ"
    project_info = None

    def header(self):
        _project_header(self, self.project_info)
        self.set_font(_FONT, "B", SZ_TITLE)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 10, _t(self.report_title), align="C")
        self.set_draw_color(60, 60, 60)
        self.set_line_width(0.5)
        y = self.get_y() + 1
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font(_FONT, "I", SZ_FOOTER)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            _t(f"จัดทำเมื่อ {date.today().isoformat()}   ·   "
               f"ACI 318M-08 (หน่วยเมตริก)   ·   หน้า {self.page_no()}"),
            align="C",
        )


def _section(pdf, title):
    pdf.ln(2.5)
    pdf.set_font(_FONT, "B", SZ_SECTION)
    pdf.set_text_color(20, 20, 20)
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(0, 9, _t(f"  {title}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(1.5)


def _row(pdf, label, value, unit="", nd=2):
    text = _fmt(value, nd) if not unit else f"{_fmt(value, nd)} {unit}"
    y0 = pdf.get_y()
    pdf.set_font(_FONT, "", SZ_ROW)
    pdf.set_text_color(45, 45, 45)
    pdf.cell(LABEL_W, LH_ROW, _t(f"   {label}"))
    pdf.set_font(_FONT, "B", SZ_ROW)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, LH_ROW, _t(text),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(226, 226, 226)
    pdf.set_line_width(0.15)
    pdf.line(pdf.l_margin, y0 + LH_ROW, pdf.w - pdf.r_margin, y0 + LH_ROW)


def _register_fonts(pdf):
    """Register THSarabunNew under every style key so ``set_font(.., 'B'|'I'|'BI')``
    never raises even though only the regular face ships with the project.
    fpdf2 does not synthesise bold/italic for TrueType, so when the dedicated
    files are absent the regular file is reused and visual hierarchy relies on
    size, colour and fills instead."""
    reg = FONT_REGULAR
    bold = FONT_BOLD if os.path.isfile(FONT_BOLD) else reg
    ital = FONT_ITALIC if os.path.isfile(FONT_ITALIC) else reg
    bolditalic = FONT_BOLDITALIC if os.path.isfile(FONT_BOLDITALIC) else bold
    pdf.add_font(FONT_NAME, "", reg)
    pdf.add_font(FONT_NAME, "B", bold)
    pdf.add_font(FONT_NAME, "I", ital)
    pdf.add_font(FONT_NAME, "BI", bolditalic)


def _new_sheet(title, project=None):
    pdf = _Sheet(orientation="P", unit="mm", format="A4")
    pdf.project_info = project
    pdf.report_title = title
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=18)
    if FONT_AVAILABLE:
        _register_fonts(pdf)
        # uharfbuzz complex-text layout — mandatory for correct Thai vowel /
        # tone-mark placement.
        pdf.set_text_shaping(True)
    pdf.add_page()
    return pdf


def _result_block(pdf, passed, status_text, summary=None):
    pdf.ln(5)
    pdf.set_font(_FONT, "B", SZ_RESULT)
    pdf.set_text_color(*((0, 130, 0) if passed else (190, 0, 0)))
    pdf.cell(0, 11, _t(f"ผลสรุป:  {_status_thai(passed)}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    if summary:
        pdf.set_font(_FONT, "", SZ_SMALL)
        pdf.multi_cell(0, 6.5, _t(summary), align="L")


def _to_bytes(pdf):
    return bytes(pdf.output())


def _image_section(pdf, buf, title="รายละเอียดหน้าตัด"):
    """Insert a titled section holding a PNG image taken from a BytesIO buffer.

    Does nothing when `buf` is missing or empty.  fpdf2 embeds the PNG straight
    from an in-memory stream, so no temporary file is needed.  The drawing is
    sized by aspect ratio (wide P-M / plan grids get more width than a single
    portrait cross-section), centred, and kept on one page with its heading.
    """
    if buf is None:
        return
    try:
        buf.seek(0)
        data = buf.read()
    except Exception:
        return
    if not data:
        return

    # Pick a display width from the image aspect ratio.
    avail = pdf.w - pdf.l_margin - pdf.r_margin
    ratio = 1.0
    try:
        from PIL import Image
        with Image.open(BytesIO(data)) as im:
            iw, ih = im.size
        ratio = iw / ih if ih else 1.0
    except Exception:
        pass

    a4_sheet = 0.55 <= ratio <= 0.95          # the true-scale A4 detail sheets
    if ratio >= 1.25:                          # landscape: P-M diagram, strip
        width_mm = min(avail, 168.0)
    elif ratio <= 0.55:                        # thin & tall: narrow pile-cap
        width_mm = 92.0
    elif a4_sheet:                             # portrait dual-view detail sheet
        width_mm = avail
    else:
        width_mm = min(avail, 152.0)
    height_mm = width_mm / ratio if ratio else width_mm

    # A full-height detail sheet gets its own page; everything else keeps the
    # heading with its image by breaking first when they will not fit.
    if a4_sheet:
        pdf.add_page()
    elif pdf.get_y() + 12.0 + height_mm > pdf.page_break_trigger:
        pdf.add_page()

    _section(pdf, title)

    # Clamp to the space that is actually left on this page so fpdf2 never
    # pushes the image onto a new page and orphans the heading.
    room = pdf.page_break_trigger - pdf.get_y() - 3.0
    if height_mm > room > 0:
        height_mm = room
        width_mm = height_mm * ratio
    try:
        x = pdf.l_margin + max(0.0, (avail - width_mm) / 2.0)
        pdf.image(BytesIO(data), x=x, w=width_mm, h=height_mm)
        pdf.ln(3)
    except Exception:
        pass


def _governing_as(r):
    if r("As_req") is not None and r("As_min") is not None:
        return max(r("As_req"), r("As_min"))
    if r("As_req") is not None:
        return r("As_req")
    if r("As_min") is not None:
        return r("As_min")
    return None


# Section titles (shared)
_S_INPUT = "ข้อมูลป้อนเข้า"
_S_STEPS = "ขั้นตอนการคำนวณ"
_S_LOADS = "การวิเคราะห์น้ำหนักบรรทุก"
_S_CONCL = "สรุปผล"


# ---------------------------------------------------------------------------
# Titles
# ---------------------------------------------------------------------------

BEAM_TITLE = "การออกแบบคานคอนกรีตเสริมเหล็ก (ACI 318M-08)"
BEAM_3SECT_TITLE = "การออกแบบคาน 3 หน้าตัด คอนกรีตเสริมเหล็ก (ACI 318M-08)"
COLUMN_TITLE = "การออกแบบเสาคอนกรีตเสริมเหล็ก (ACI 318M-08)"
SLAB_TITLE = "การออกแบบพื้นทางเดียวคอนกรีตเสริมเหล็ก (ACI 318M-08)"
TWOWAY_SLAB_TITLE = "การออกแบบพื้นสองทางคอนกรีตเสริมเหล็ก (ACI 318M-08)"
FOOTING_TITLE = "การออกแบบฐานรากเดี่ยวคอนกรีตเสริมเหล็ก (ACI 318M-08)"
STAIR_TITLE = "การออกแบบบันไดคอนกรีตเสริมเหล็ก (ACI 318M-08)"
U_STAIR_TITLE = "การออกแบบบันไดหักกลับ (U-Shape) คอนกรีตเสริมเหล็ก (ACI 318M-08)"
PILECAP_TITLE = "การออกแบบฐานรากเสาเข็มคอนกรีตเสริมเหล็ก (ACI 318M-08)"


# ---------------------------------------------------------------------------
# Beam
# ---------------------------------------------------------------------------


def generate_beam_report(inputs, results):
    """สร้างใบคำนวณการออกแบบคานและคืนค่าเป็นสตริงไบต์ (bytes)."""
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    gov = _governing_as(r)

    pdf = _new_sheet(BEAM_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "โมเมนต์ประลัย Mu", _kgfm(g("Mu")), "kgf-m", nd=0)
    _row(pdf, "ความกว้างหน้าตัด b", _cm(g("b")), "cm", nd=2)
    _row(pdf, "ความลึกหน้าตัด h", _cm(g("h")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล d", _cm(r("d")), "cm", nd=2)
    _row(pdf, "พื้นที่เหล็กที่ต้องการ As,required", _cm2(r("As_req")), "cm2", nd=2)
    _row(pdf, "พื้นที่เหล็กขั้นต่ำ As,min", _cm2(r("As_min")), "cm2", nd=2)
    _row(pdf, "As ที่ต้องการที่ควบคุม", _cm2(gov), "cm2", nd=2)
    _row(pdf, "ขนาดเหล็กเสริมที่เลือก", r("rebar_size"))
    _row(pdf, "จำนวนเส้น", r("qty"))

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "พื้นที่เหล็กที่จัดให้ As,provided", _cm2(r("As_prov")), "cm2", nd=2)
    if gov is not None and r("As_prov") is not None:
        rel = ">=" if passed else "<"
        _row(pdf, "การตรวจสอบ", f"As ที่จัดให้ {rel} As ที่ต้องการที่ควบคุม")

    summary = None
    if gov is not None and r("As_prov") is not None:
        summary = (
            f"As ที่จัดให้ = {_f2(_cm2(r('As_prov')))} cm2 เทียบกับ "
            f"As ที่ต้องการที่ควบคุม = {_f2(_cm2(gov))} cm2 "
            f"(As,required = {_f2(_cm2(r('As_req')))} cm2, "
            f"As,min = {_f2(_cm2(r('As_min')))} cm2)."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# Beam — 3 critical sections (Left Support / Mid Span / Right Support)
# ---------------------------------------------------------------------------


def generate_beam_3_sect_report(inputs, results):
    """สร้างใบคำนวณคาน 3 หน้าตัด และคืนค่าเป็น bytes.

    Expected keys
        inputs  : b, h, covering (mm), fc, fy (MPa), project
        results : sections (list of per-section dicts from the module),
                  section_img, status
    Each section dict carries: label, d_top, d_bot, As_min, As_top_req,
    As_top_prov, As_bot_req, As_bot_prov, Mu_top, Mu_bot, top_size/top_qty,
    bot_size/bot_qty, stirrup_size/stirrup_sp_cm, Vu_kN, phiVc_kN, phiVs_kN,
    phiVn_kN, s_max_mm, top_req_ok, bot_req_ok, top_min_ok, bot_min_ok,
    shear_ok, passed   (areas mm2, depths mm).
    """
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    secs = r("sections") or []

    pdf = _new_sheet(BEAM_3SECT_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "ความกว้างคาน b", _cm(g("b")), "cm", nd=2)
    _row(pdf, "ความลึกคาน h", _cm(g("h")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)

    for s in secs:
        sg = s.get
        _section(pdf, sg("label", "-"))
        _row(pdf, "ความลึกประสิทธิผล d (บน / ล่าง)",
             f"{_fmt(_cm(sg('d_top')), 2)} / {_fmt(_cm(sg('d_bot')), 2)} cm")
        _row(pdf, "As,min", _cm2(sg("As_min")), "cm2", nd=2)
        _row(pdf,
             f"Mu- (บน) = {_fmt(_kgfm(sg('Mu_top')), 0)} kgf-m -> As ที่ต้องการ",
             _cm2(sg("As_top_req")), "cm2", nd=2)
        _row(pdf,
             f"As บน ที่จัดให้ ({_fmt(sg('top_qty'), 0)} x {_fmt(sg('top_size'))})",
             _cm2(sg("As_top_prov")), "cm2", nd=2)
        _row(pdf,
             f"Mu+ (ล่าง) = {_fmt(_kgfm(sg('Mu_bot')), 0)} kgf-m -> As ที่ต้องการ",
             _cm2(sg("As_bot_req")), "cm2", nd=2)
        _row(pdf,
             f"As ล่าง ที่จัดให้ ({_fmt(sg('bot_qty'), 0)} x {_fmt(sg('bot_size'))})",
             _cm2(sg("As_bot_prov")), "cm2", nd=2)
        _row(pdf, "Vu", _kgf(sg("Vu_kN")), "kgf", nd=0)
        _row(pdf,
             f"phiVc / phiVs ({_fmt(sg('stirrup_size'))} @ "
             f"{_fmt(sg('stirrup_sp_cm'), 1)} cm)",
             f"{_fmt(_kgf(sg('phiVc_kN')), 0)} / {_fmt(_kgf(sg('phiVs_kN')), 0)} kgf")
        _row(pdf, "phiVn = phiVc + phiVs", _kgf(sg("phiVn_kN")), "kgf", nd=0)
        _row(pdf, "ผลตรวจ บน / ล่าง / As,min / แรงเฉือน",
             f"{_chk(sg('top_req_ok'))} / {_chk(sg('bot_req_ok'))} / "
             f"{_chk(bool(sg('top_min_ok')) and bool(sg('bot_min_ok')))} / "
             f"{_chk(sg('shear_ok'))}")
        _row(pdf, "สรุปหน้าตัดนี้", _chk(sg("passed")))

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    for s in secs:
        _row(pdf, s.get("label", "-"), _chk(s.get("passed")))

    summary = None
    if secs:
        if passed:
            summary = "ผ่านการตรวจสอบครบทั้ง 3 หน้าตัด (ริมซ้าย / กลางช่วง / ริมขวา)."
        else:
            bad = ", ".join(s.get("label", "-").split(" (")[0]
                            for s in secs if not s.get("passed"))
            summary = f"หน้าตัดที่ไม่ผ่าน: {bad}."
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# Column
# ---------------------------------------------------------------------------


def generate_column_report(inputs, results):
    """สร้างใบคำนวณการออกแบบเสา (แผนภาพปฏิสัมพันธ์ P-M สองแกน) และคืนค่าเป็น bytes.

    Expected keys
        inputs  : Pu, Mux, Muy (kN, kN.m), b, h, covering (mm), fc, fy (MPa),
                  main_size, n_x, n_y, total_bars, stirrup_size, stirrup_sp_cm,
                  project
        results : Ag, Ast (mm2), rho_g, Po_kN, phiPn_max_kN, phiMn_x_kNm,
                  phiMn_y_kNm, biaxial (dict|None), ratio_ok, axial_max_ok,
                  uniax_x_ok, uniax_y_ok, biaxial_ok, section_img, status
    """
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    Pu = g("Pu")
    Mux = g("Mux") or 0.0
    Muy = g("Muy") or 0.0

    pdf = _new_sheet(COLUMN_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "แรงตามแนวแกนประลัย Pu", _kgf(Pu), "kgf", nd=0)
    _row(pdf, "โมเมนต์ดัดรอบแกน X, Mux", _kgfm(Mux), "kgf-m", nd=0)
    _row(pdf, "โมเมนต์ดัดรอบแกน Y, Muy", _kgfm(Muy), "kgf-m", nd=0)
    _row(pdf, "ความกว้าง b (แกน X)", _cm(g("b")), "cm", nd=2)
    _row(pdf, "ความลึก h (แกน Y)", _cm(g("h")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)

    _section(pdf, "เหล็กเสริม")
    _row(pdf, "ขนาดเหล็กเสริมหลัก", g("main_size"))
    _row(pdf, "จำนวนเหล็กด้านกว้าง / ด้านลึก (n_x / n_y)",
         f"{_fmt(g('n_x'), 0)} / {_fmt(g('n_y'), 0)}")
    _row(pdf, "จำนวนเหล็กเสริมทั้งหมด = 2(n_x + n_y - 2)", g("total_bars"), nd=0)
    _row(pdf, "พื้นที่เหล็กเสริมทั้งหมด Ast", _cm2(r("Ast")), "cm2", nd=2)
    _row(pdf, "พื้นที่หน้าตัดรวม Ag = b x h", _cm2(r("Ag")), "cm2", nd=2)
    _row(pdf, "อัตราส่วนเหล็กเสริม rho_g = Ast / Ag",
         (None if r("rho_g") is None else r("rho_g") * 100.0), "%", nd=2)
    _row(pdf, "เหล็กปลอก",
         f"{_fmt(g('stirrup_size'))} @ {_fmt(g('stirrup_sp_cm'), 1)} cm")

    _section(pdf, _S_STEPS)
    _row(pdf, "กำลังรับแรงตามแนวแกนล้วน Po = 0.85f'c(Ag-Ast) + fy Ast",
         _kgf(r("Po_kN")), "kgf", nd=0)
    _row(pdf, "ขีดจำกัดแรงตามแนวแกน phiPn,max = 0.80 phi Po",
         _kgf(r("phiPn_max_kN")), "kgf", nd=0)
    _row(pdf, "กำลังโมเมนต์ออกแบบที่ Pu รอบแกน X, phiMn,x",
         _kgfm(r("phiMn_x_kNm")), "kgf-m", nd=0)
    _row(pdf, "กำลังโมเมนต์ออกแบบที่ Pu รอบแกน Y, phiMn,y",
         _kgfm(r("phiMn_y_kNm")), "kgf-m", nd=0)

    bi = r("biaxial")
    if bi:
        bg = bi.get
        _section(pdf, "Bresler Reciprocal Load")
        _row(pdf, "ระยะเยื้องศูนย์ ex = Mux/Pu", _cm(bg("ex_mm")), "cm", nd=2)
        _row(pdf, "ระยะเยื้องศูนย์ ey = Muy/Pu", _cm(bg("ey_mm")), "cm", nd=2)
        _row(pdf, "Pnx (ดัดรอบแกน X ที่ ex)", _kgf(bg("Pnx_kN")), "kgf", nd=0)
        _row(pdf, "Pny (ดัดรอบแกน Y ที่ ey)", _kgf(bg("Pny_kN")), "kgf", nd=0)
        _row(pdf, "1/Pn,biaxial = 1/Pnx + 1/Pny - 1/Po",
             _kgf(bg("Pn_bi_kN")), "kgf", nd=0)
        _row(pdf, "phiPn,biaxial", _kgf(bg("phiPn_bi_kN")), "kgf", nd=0)

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "อัตราส่วนเหล็กเสริม 1% <= rho_g <= 8%", _chk(r("ratio_ok")))
    _row(pdf, "ขีดจำกัดแรงตามแนวแกน Pu <= phiPn,max", _chk(r("axial_max_ok")))
    if Mux > 1e-9 and Muy > 1e-9:
        _row(pdf, "การตรวจสอบสองแกน (Bresler) phiPn,biaxial >= Pu",
             _chk(r("biaxial_ok")))
    elif Mux > 1e-9:
        _row(pdf, "การตรวจสอบรอบแกน X: phiMn,x >= Mux", _chk(r("uniax_x_ok")))
    elif Muy > 1e-9:
        _row(pdf, "การตรวจสอบรอบแกน Y: phiMn,y >= Muy", _chk(r("uniax_y_ok")))
    else:
        _row(pdf, "แรงตามแนวแกนล้วน", _chk(True))

    if bi:
        summary = (
            f"phiPn,biaxial = {_fmt(_kgf(bi.get('phiPn_bi_kN')), 0)} kgf เทียบกับ "
            f"Pu = {_fmt(_kgf(Pu), 0)} kgf. rho_g = "
            f"{_fmt((r('rho_g') or 0.0) * 100.0, 2)}%."
        )
    else:
        summary = (
            f"phiPn,max = {_fmt(_kgf(r('phiPn_max_kN')), 0)} kgf, "
            f"phiMn,x = {_fmt(_kgfm(r('phiMn_x_kNm')), 0)} / phiMn,y = "
            f"{_fmt(_kgfm(r('phiMn_y_kNm')), 0)} kgf-m. rho_g = "
            f"{_fmt((r('rho_g') or 0.0) * 100.0, 2)}%."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# One-way slab
# ---------------------------------------------------------------------------


def generate_slab_report(inputs, results):
    """สร้างใบคำนวณการออกแบบพื้นทางเดียวและคืนค่าเป็นสตริงไบต์ (bytes)."""
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    gov = _governing_as(r)

    pdf = _new_sheet(SLAB_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "โมเมนต์ประลัย Mu", _kgfm(g("Mu")), "kgf-m/m", nd=0)
    _row(pdf, "ความหนาพื้น t", _cm(g("t")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)
    _row(pdf, "ความกว้างแถบออกแบบ b", _cm(g("b", 1000)), "cm", nd=2)

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล d", _cm(r("d")), "cm", nd=2)
    _row(pdf, "พื้นที่เหล็กจากการดัด As,required", _cm2(r("As_req")), "cm2/m", nd=2)
    _row(pdf, "เหล็กกันร้าว/อุณหภูมิ As,min", _cm2(r("As_min")), "cm2/m", nd=2)
    _row(pdf, "As หลักที่ต้องการที่ควบคุม", _cm2(gov), "cm2/m", nd=2)
    _row(pdf, "เหล็กเสริมหลัก",
         f"{_fmt(r('main_size'))} @ {_fmt(_cm(r('main_spacing')), 1)} cm")
    _row(pdf, "As หลักที่จัดให้", _cm2(r("As_prov_main")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (หลัก) = min(3t, 450)", _cm(r("max_sp_main")), "cm", nd=1)
    _row(pdf, "เหล็กเสริมกันร้าว",
         f"{_fmt(r('temp_size'))} @ {_fmt(_cm(r('temp_spacing')), 1)} cm")
    _row(pdf, "As กันร้าวที่จัดให้", _cm2(r("As_prov_temp")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (กันร้าว) = min(5t, 450)", _cm(r("max_sp_temp")), "cm", nd=1)

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "As หลักที่จัดให้", _cm2(r("As_prov_main")), "cm2/m", nd=2)
    if gov is not None and r("As_prov_main") is not None:
        rel = ">=" if passed else "<"
        _row(pdf, "การตรวจสอบ", f"As หลักที่จัดให้ {rel} As ที่ต้องการที่ควบคุม")

    summary = None
    if gov is not None and r("As_prov_main") is not None:
        summary = (
            f"As หลักที่จัดให้ = {_f2(_cm2(r('As_prov_main')))} cm2/m เทียบกับ "
            f"As ที่ต้องการที่ควบคุม = {_f2(_cm2(gov))} cm2/m "
            f"(การดัด As,required = {_f2(_cm2(r('As_req')))} cm2/m, "
            f"เหล็กกันร้าว/อุณหภูมิ As,min = {_f2(_cm2(r('As_min')))} cm2/m)."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# Two-way slab
# ---------------------------------------------------------------------------


def generate_twoway_slab_report(inputs, results):
    """สร้างใบคำนวณการออกแบบพื้นสองทางและคืนค่าเป็นสตริงไบต์ (bytes).

    Expected keys
        inputs  : Lx, Ly (m), t, covering (mm), SDL_kgm2, LL_kgm2,
                  fc, fy (MPa), project
        results : m_ratio, sw_kg, DL_kg, Wu_kg, Wu_kN, db, Mux, Muy,
                  dx, dy (mm), As_x, As_y, As_min (mm2/m),
                  size_x, sp_x_cm, As_prov_x, size_y, sp_y_cm, As_prov_y,
                  max_sp, x_req_ok, x_min_ok, y_req_ok, y_min_ok,
                  sp_x_ok, sp_y_ok, section_img, status
    """
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"

    pdf = _new_sheet(TWOWAY_SLAB_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "ช่วงสั้น Lx", g("Lx"), "m", nd=3)
    _row(pdf, "ช่วงยาว Ly", g("Ly"), "m", nd=3)
    _row(pdf, "ความหนาพื้น t", _cm(g("t")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "น้ำหนักบรรทุกคงที่เพิ่มเติม SDL", g("SDL_kgm2"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกจร LL", g("LL_kgm2"), "kgf/m2", nd=1)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)

    _section(pdf, _S_STEPS)
    _row(pdf, "อัตราส่วน m = Lx / Ly", r("m_ratio"), nd=3)
    _row(pdf, "น้ำหนักตัวเอง SW = t x 2400", r("sw_kg"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกคงที่รวม DL = SW + SDL", r("DL_kg"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกประลัย Wu = 1.2DL + 1.6LL", r("Wu_kg"), "kgf/m2", nd=1)
    _row(pdf, "โมเมนต์ทิศทางสั้น Mux", _kgfm(r("Mux")), "kgf-m/m", nd=0)
    _row(pdf, "โมเมนต์ทิศทางยาว Muy", _kgfm(r("Muy")), "kgf-m/m", nd=0)
    _row(pdf, "d_b (สมมติสำหรับออกแบบ)", r("db"), "mm", nd=1)
    _row(pdf, "ความลึกประสิทธิผล dx = t - covering - db/2", _cm(r("dx")), "cm", nd=2)
    _row(pdf, "ความลึกประสิทธิผล dy = dx - db", _cm(r("dy")), "cm", nd=2)

    _section(pdf, "เหล็กเสริมทิศทางสั้น (X)")
    _row(pdf, "As ที่ต้องการ (การดัด)", _cm2(r("As_x")), "cm2/m", nd=2)
    _row(pdf, "As,min", _cm2(r("As_min")), "cm2/m", nd=2)
    _row(pdf, "เหล็กที่จัดให้",
         f"{_fmt(r('size_x'))} @ {_fmt(r('sp_x_cm'), 1)} cm")
    _row(pdf, "As ที่จัดให้", _cm2(r("As_prov_x")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด min(2t, 450)", _cm(r("max_sp")), "cm", nd=1)

    _section(pdf, "เหล็กเสริมทิศทางยาว (Y)")
    _row(pdf, "As ที่ต้องการ (การดัด)", _cm2(r("As_y")), "cm2/m", nd=2)
    _row(pdf, "As,min", _cm2(r("As_min")), "cm2/m", nd=2)
    _row(pdf, "เหล็กที่จัดให้",
         f"{_fmt(r('size_y'))} @ {_fmt(r('sp_y_cm'), 1)} cm")
    _row(pdf, "As ที่จัดให้", _cm2(r("As_prov_y")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด min(2t, 450)", _cm(r("max_sp")), "cm", nd=1)

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "As,x >= As,required", _chk(r("x_req_ok")))
    _row(pdf, "As,x >= As,min", _chk(r("x_min_ok")))
    _row(pdf, "As,y >= As,required", _chk(r("y_req_ok")))
    _row(pdf, "As,y >= As,min", _chk(r("y_min_ok")))
    _row(pdf, "ระยะเรียง X <= ขีดจำกัด", _chk(r("sp_x_ok")))
    _row(pdf, "ระยะเรียง Y <= ขีดจำกัด", _chk(r("sp_y_ok")))

    summary = None
    if r("As_prov_x") is not None:
        summary = (
            f"Mux = {_fmt(_kgfm(r('Mux')), 0)} kgf-m/m, "
            f"Muy = {_fmt(_kgfm(r('Muy')), 0)} kgf-m/m. "
            f"ทิศทางสั้น X: As ที่จัดให้ {_f2(_cm2(r('As_prov_x')))} "
            f"เทียบกับที่ต้องการ {_f2(_cm2(r('As_x')))} cm2/m. ทิศทางยาว Y: "
            f"As ที่จัดให้ {_f2(_cm2(r('As_prov_y')))} เทียบกับที่ต้องการ "
            f"{_f2(_cm2(r('As_y')))} cm2/m."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# Isolated square footing
# ---------------------------------------------------------------------------


def generate_footing_report(inputs, results):
    """สร้างใบคำนวณการออกแบบฐานรากเดี่ยวและคืนค่าเป็นสตริงไบต์ (bytes)."""
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    gov = _governing_as(r)

    pdf = _new_sheet(FOOTING_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "น้ำหนักบรรทุกคงที่จากเสา P_DL", g("P_DL_kgf"), "kgf", nd=0)
    _row(pdf, "น้ำหนักบรรทุกจรจากเสา P_LL", g("P_LL_kgf"), "kgf", nd=0)
    _row(pdf, "กำลังแบกทานดินที่ยอมให้ qa", g("q_a_kgf"), "kgf/m2", nd=0)
    if g("col_shape") == "circ" and g("Dc") is not None:
        _row(pdf, "หน้าตัดเสา (กลม) Dia Dc",
             f"{_fmt(_cm(g('Dc')), 1)} cm  ->  c_eq = "
             f"{_fmt(_cm(g('cx')), 2)} cm (ACI 15.3)")
    else:
        _row(pdf, "หน้าตัดเสา (สี่เหลี่ยม) cx x cy",
             f"{_fmt(_cm(g('cx')), 1)} x {_fmt(_cm(g('cy')), 1)} cm")
    _row(pdf, "ความกว้างฐานราก B", g("B_m"), "m", nd=2)
    _row(pdf, "ความยาวฐานราก L", g("L_m"), "m", nd=2)
    _row(pdf, "ความหนาฐานราก h", _cm(g("h")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)

    _section(pdf, _S_STEPS)
    _row(pdf, "น้ำหนักฐานรากเอง Wf = B x L x h x 2400", g("Wf_kgf"), "kgf", nd=1)
    _row(pdf, "น้ำหนักบรรทุกคงที่รวม Total DL = P_DL + Wf", g("Total_DL_kgf"), "kgf", nd=1)
    _row(pdf, "แรงประลัยรวม Pu = 1.2 Total DL + 1.6 P_LL", g("Pu_kgf"), "kgf", nd=1)
    _row(pdf, "ความลึกประสิทธิผล ด้านยาว d_long", _cm(r("d_long")), "cm", nd=2)
    _row(pdf, "ความลึกประสิทธิผล ด้านสั้น d_short = d_long - db", _cm(r("d_short")),
         "cm", nd=2)
    _row(pdf, "หน่วยแรงดินที่เกิดขึ้น (ใช้งาน) q = (P_DL+P_LL+Wf)/(B x L)",
         r("q_service_kgf"), "kgf/m2", nd=1)
    _row(pdf, "หน่วยแรงดินที่ยอมให้ qa", g("q_a_kgf"), "kgf/m2", nd=0)
    _row(pdf, "หน่วยแรงประลัยสุทธิ qu,net = (1.2 P_DL + 1.6 P_LL)/(B x L)",
         r("qu_net_kgf"), "kgf/m2", nd=1)
    _row(pdf, "แรงเฉือนทะลุ สองทาง Vu (ใช้ qu,net)", _kgf(r("Vup_kN")), "kgf", nd=0)
    _row(pdf, "แรงเฉือนทะลุ สองทาง phi*Vc (d = d_avg)", _kgf(r("phiVc_punch_kN")),
         "kgf", nd=0)

    _image_section(pdf, r("section_img"))

    _section(pdf, "การออกแบบการดัด / แรงเฉือนคาน — ด้านยาว (Long Direction)")
    _row(pdf, "โมเมนต์ที่ผิวเสา Mu,long (ใช้ qu,net)", _kgfm(r("Mu_long_kNm")),
         "kgf-m", nd=0)
    _row(pdf, "แรงเฉือนคาน Vu,long / phi*Vc",
         f"{_fmt(_kgf(r('Vu_long_kN')), 0)} / {_fmt(_kgf(r('phiVc_long_kN')), 0)} kgf")
    _row(pdf, "พื้นที่เหล็กที่ต้องการ As,req (long)", _cm2(r("As_req_long")),
         "cm2", nd=2)
    _row(pdf, "เหล็กเสริมขั้นต่ำ As,min (long)", _cm2(r("As_min_long")), "cm2", nd=2)
    _row(pdf, "เหล็กที่จัดให้ (long) — จำนวน x ขนาด",
         f"{_fmt(r('n_long'), 0)} - {_fmt(r('size_long'))}")
    _row(pdf, "ระยะเรียงที่คำนวณได้ S (long) [<= s_max]",
         f"{_fmt(r('s_long_cm'), 1)} cm  [{_fmt(r('s_max_cm'), 1)}]  "
         f"{_chk(r('sp_long_ok'))}")
    _row(pdf, "พื้นที่เหล็กที่จัดให้ As,prov (long) = n x Ab", _cm2(r("As_prov_long")),
         "cm2", nd=2)

    _section(pdf, "การออกแบบการดัด / แรงเฉือนคาน — ด้านสั้น (Short Direction)")
    _row(pdf, "โมเมนต์ที่ผิวเสา Mu,short (ใช้ qu,net)", _kgfm(r("Mu_short_kNm")),
         "kgf-m", nd=0)
    _row(pdf, "แรงเฉือนคาน Vu,short / phi*Vc",
         f"{_fmt(_kgf(r('Vu_short_kN')), 0)} / {_fmt(_kgf(r('phiVc_short_kN')), 0)} kgf")
    _row(pdf, "พื้นที่เหล็กที่ต้องการ As,req (short)", _cm2(r("As_req_short")),
         "cm2", nd=2)
    _row(pdf, "เหล็กเสริมขั้นต่ำ As,min (short)", _cm2(r("As_min_short")), "cm2",
         nd=2)
    _row(pdf, "เหล็กที่จัดให้ (short) — จำนวน x ขนาด",
         f"{_fmt(r('n_short'), 0)} - {_fmt(r('size_short'))}")
    _row(pdf, "ระยะเรียงที่คำนวณได้ S (short) [<= s_max]",
         f"{_fmt(r('s_short_cm'), 1)} cm  [{_fmt(r('s_max_cm'), 1)}]  "
         f"{_chk(r('sp_short_ok'))}")
    _row(pdf, "พื้นที่เหล็กที่จัดให้ As,prov (short) = n x Ab", _cm2(r("As_prov_short")),
         "cm2", nd=2)

    _section(pdf, _S_CONCL)
    _row(pdf, "กำลังแบกทานดิน (q <= q_a)", _chk(r("bearing_ok")))
    _row(pdf, "แรงเฉือนทะลุ สองทาง (Vu <= phi*Vc)", _chk(r("punch_ok")))
    _row(pdf, "แรงเฉือนคาน — ด้านยาว (Vu <= phi*Vc)", _chk(r("beam_long_ok")))
    _row(pdf, "แรงเฉือนคาน — ด้านสั้น (Vu <= phi*Vc)", _chk(r("beam_short_ok")))
    _row(pdf, "การดัด — ด้านยาว (As,prov >= As,req)", _chk(r("flex_long_ok")))
    _row(pdf, "การดัด — ด้านสั้น (As,prov >= As,req)", _chk(r("flex_short_ok")))
    _row(pdf, "เหล็กขั้นต่ำ — ด้านยาว", _chk(r("asmin_long_ok")))
    _row(pdf, "เหล็กขั้นต่ำ — ด้านสั้น", _chk(r("asmin_short_ok")))
    _row(pdf, "ระยะเรียง — ด้านยาว (S <= s_max)", _chk(r("sp_long_ok")))
    _row(pdf, "ระยะเรียง — ด้านสั้น (S <= s_max)", _chk(r("sp_short_ok")))

    summary = (
        f"ด้านยาว: As ที่จัดให้ {_f2(_cm2(r('As_prov_long')))} เทียบกับที่ต้องการ "
        f"{_f2(_cm2(r('As_req_long')))} cm2  ·  ด้านสั้น: As ที่จัดให้ "
        f"{_f2(_cm2(r('As_prov_short')))} เทียบกับที่ต้องการ "
        f"{_f2(_cm2(r('As_req_short')))} cm2. "
        f"กำลังแบกทานดิน {_chk(r('bearing_ok'))}, แรงเฉือนทะลุ "
        f"{_chk(r('punch_ok'))}, การดัด (ยาว {_chk(r('flex_long_ok'))} / สั้น "
        f"{_chk(r('flex_short_ok'))})."
    )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# Straight stair flight
# ---------------------------------------------------------------------------


def generate_stair_report(inputs, results):
    """สร้างใบคำนวณการออกแบบบันไดและคืนค่าเป็นสตริงไบต์ (bytes)."""
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    gov = _governing_as(r)

    pdf = _new_sheet(STAIR_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "ช่วงพาดในแนวราบ L", g("L"), "m", nd=3)
    _row(pdf, "ลูกนอน T", _cm(g("T")), "cm", nd=2)
    _row(pdf, "ลูกตั้ง R", _cm(g("R")), "cm", nd=2)
    _row(pdf, "ความหนาท้องบันได t", _cm(g("t")), "cm", nd=2)
    _row(pdf, "น้ำหนักบรรทุกคงที่เพิ่มเติม SDL", g("SDL_kgf"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกจร LL", g("LL_kgf"), "kgf/m2", nd=1)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)
    _row(pdf, "ความกว้างแถบออกแบบ b", _cm(g("b", 1000)), "cm", nd=2)

    _section(pdf, _S_LOADS)
    _row(pdf, "มุมลาดเอียง theta = atan(R/T)", r("theta_deg"), "deg")
    _row(pdf, "น้ำหนักตัวเอง SW = 2400*(t/cos(theta) + R/2)", r("SW_kgf"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกคงที่รวม DL = SW + SDL", r("DL_kgf"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกประลัย wu = 1.2 DL + 1.6 LL", r("wu_kgf"), "kgf/m", nd=1)
    _row(pdf, "โมเมนต์ประลัย Mu = wu L^2 / 8", _kgfm(r("Mu")), "kgf-m/m", nd=0)

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล d = t - covering - db/2", _cm(r("d")), "cm", nd=2)
    _row(pdf, "พื้นที่เหล็กจากการดัด As,required", _cm2(r("As_req")), "cm2/m", nd=2)
    _row(pdf, "เหล็กกันร้าว/อุณหภูมิ As,min", _cm2(r("As_min")), "cm2/m", nd=2)
    _row(pdf, "As หลักที่ต้องการที่ควบคุม", _cm2(gov), "cm2/m", nd=2)
    _row(pdf, "เหล็กเสริมหลัก",
         f"{_fmt(r('main_size'))} @ {_fmt(_cm(r('main_spacing')), 1)} cm")
    _row(pdf, "As หลักที่จัดให้", _cm2(r("As_prov_main")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (หลัก) = min(3t, 450)", _cm(r("max_sp_main")), "cm", nd=1)
    _row(pdf, "เหล็กเสริมกันร้าว",
         f"{_fmt(r('temp_size'))} @ {_fmt(_cm(r('temp_spacing')), 1)} cm")
    _row(pdf, "As กันร้าวที่จัดให้", _cm2(r("As_prov_temp")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (กันร้าว) = min(5t, 450)", _cm(r("max_sp_temp")), "cm", nd=1)

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "As หลักที่จัดให้", _cm2(r("As_prov_main")), "cm2/m", nd=2)
    if gov is not None and r("As_prov_main") is not None:
        rel = ">=" if passed else "<"
        _row(pdf, "การตรวจสอบ", f"As หลักที่จัดให้ {rel} As ที่ต้องการที่ควบคุม")

    summary = None
    if gov is not None and r("As_prov_main") is not None:
        summary = (
            f"As หลักที่จัดให้ = {_f2(_cm2(r('As_prov_main')))} cm2/m เทียบกับ "
            f"As ที่ต้องการที่ควบคุม = {_f2(_cm2(gov))} cm2/m "
            f"(การดัด As,required = {_f2(_cm2(r('As_req')))} cm2/m, "
            f"เหล็กกันร้าว/อุณหภูมิ As,min = {_f2(_cm2(r('As_min')))} cm2/m). "
            f"โมเมนต์ประลัย Mu = {_fmt(_kgfm(r('Mu')), 0)} kgf-m/m."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# U-shape stair (one flight)
# ---------------------------------------------------------------------------


def generate_u_stair_report(inputs, results):
    """สร้างใบคำนวณการออกแบบบันไดหักกลับ (U-Shape) และคืนค่าเป็น bytes.

    Expected keys
        inputs  : T_cm, R_cm, N, L_land (m), W (m), t, covering (mm),
                  SDL_kgm2, LL_kgm2, fc, fy (MPa), project
        results : L_flight, L, theta_deg, t_avg_cm, flight_DL, landing_DL,
                  max_DL, Wu_kg, Wu_kN, Mu, d (mm), As_req, As_min (mm2/m),
                  main_size, main_sp_cm, As_prov_main, max_sp_main,
                  temp_size, temp_sp_cm, As_prov_temp, max_sp_temp,
                  main_req_ok, main_min_ok, temp_min_ok, sp_main_ok,
                  sp_temp_ok, section_img, status
    """
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"

    pdf = _new_sheet(U_STAIR_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "ลูกนอน T", g("T_cm"), "cm", nd=1)
    _row(pdf, "ลูกตั้ง R", g("R_cm"), "cm", nd=1)
    _row(pdf, "จำนวนขั้น N", g("N"), "ขั้น", nd=0)
    _row(pdf, "ความยาวชานพักแนวนอน Lland", g("L_land"), "m", nd=3)
    _row(pdf, "ความกว้างบันได W", g("W"), "m", nd=3)
    _row(pdf, "ความหนาพื้นบันได t", _cm(g("t")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "น้ำหนักบรรทุกคงที่เพิ่มเติม SDL", g("SDL_kgm2"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกจร LL", g("LL_kgm2"), "kgf/m2", nd=1)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)

    _section(pdf, _S_LOADS)
    _row(pdf, "ช่วงพาดส่วนเอียง L_flight = N x T / 100", r("L_flight"), "m", nd=3)
    _row(pdf, "ช่วงพาดรวม L = L_flight + L_land", r("L"), "m", nd=3)
    _row(pdf, "มุมเอียง theta = atan(R/T)", r("theta_deg"), "deg", nd=2)
    _row(pdf, "ความหนาเฉลี่ยส่วนเอียง t_avg = t/cos(theta) + R/2",
         r("t_avg_cm"), "cm", nd=2)
    _row(pdf, "น้ำหนักคงที่ส่วนเอียง Flight DL", r("flight_DL"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักคงที่ชานพัก Landing DL", r("landing_DL"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักคงที่ออกแบบ (max DL)", r("max_DL"), "kgf/m2", nd=1)
    _row(pdf, "น้ำหนักบรรทุกประลัย Wu = 1.2 max DL + 1.6 LL",
         r("Wu_kg"), "kgf/m2", nd=1)
    _row(pdf, "โมเมนต์ประลัย Mu = Wu L^2 / 8", _kgfm(r("Mu")), "kgf-m/m", nd=0)

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล d = t - covering - db/2", _cm(r("d")), "cm", nd=2)

    _section(pdf, "เหล็กเสริมหลัก")
    _row(pdf, "As ที่ต้องการ (การดัด)", _cm2(r("As_req")), "cm2/m", nd=2)
    _row(pdf, "As,min", _cm2(r("As_min")), "cm2/m", nd=2)
    _row(pdf, "เหล็กที่จัดให้",
         f"{_fmt(r('main_size'))} @ {_fmt(r('main_sp_cm'), 1)} cm")
    _row(pdf, "As ที่จัดให้", _cm2(r("As_prov_main")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด min(3t, 450)", _cm(r("max_sp_main")), "cm", nd=1)

    _section(pdf, "เหล็กเสริมกันร้าว/อุณหภูมิ")
    _row(pdf, "As,min", _cm2(r("As_min")), "cm2/m", nd=2)
    _row(pdf, "เหล็กที่จัดให้",
         f"{_fmt(r('temp_size'))} @ {_fmt(r('temp_sp_cm'), 1)} cm")
    _row(pdf, "As ที่จัดให้", _cm2(r("As_prov_temp")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด min(5t, 450)", _cm(r("max_sp_temp")), "cm", nd=1)

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "As หลัก >= As,required", _chk(r("main_req_ok")))
    _row(pdf, "As หลัก >= As,min", _chk(r("main_min_ok")))
    _row(pdf, "As กันร้าว >= As,min", _chk(r("temp_min_ok")))
    _row(pdf, "ระยะเรียงหลัก <= ขีดจำกัด", _chk(r("sp_main_ok")))
    _row(pdf, "ระยะเรียงกันร้าว <= ขีดจำกัด", _chk(r("sp_temp_ok")))

    summary = None
    if r("As_prov_main") is not None:
        summary = (
            f"L = {_fmt(r('L'), 3)} m, Mu = {_fmt(_kgfm(r('Mu')), 0)} kgf-m/m. "
            f"As หลักที่จัดให้ {_f2(_cm2(r('As_prov_main')))} cm2/m เทียบกับ "
            f"ที่ต้องการ {_f2(_cm2(r('As_req')))} cm2/m "
            f"(As,min {_f2(_cm2(r('As_min')))} cm2/m)."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# Pile cap (F2 / F4)
# ---------------------------------------------------------------------------


def generate_pile_cap_report(inputs, results):
    """สร้างใบคำนวณการออกแบบฐานรากเสาเข็มและคืนค่าเป็นสตริงไบต์ (bytes).

    Expected keys
        inputs  : P_serv_kgf, Pu_net_kgf, pile_cap_kgf, n_piles, pile_shape,
                  pile_perim_txt, Dp, c, h, covering, fc, fy (SI mm/MPa),
                  ex_cm, ey_cm, Muy_kgfm, Mux_kgfm
        results : d, R_serv_kgf, R_max_kgf, R_min_kgf, Ru_avg_kgf, Ru_max_kgf,
                  S, edge, cap_W, cap_L, n_inside,
                  Vup_kN, phiVc_punch_kN, phiVc_pile_kN, n_beyond, Vub_kN,
                  phiVc_beam_kN, Mu_face, As_req, As_min, main_size, qty,
                  As_prov, reaction_ok, uplift_ok, punch_ok, pile_punch_ok,
                  beam_ok, flexure_ok, as_min_ok, section_img, status
    """
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    gov = _governing_as(r)
    ex_cm = g("ex_cm") or 0.0
    ey_cm = g("ey_cm") or 0.0

    pdf = _new_sheet(PILECAP_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "จำนวนเสาเข็ม", g("n_piles"), "ต้น")
    _row(pdf, "รูปร่างเสาเข็ม", _fmt(g("pile_shape")))
    _row(pdf, "ขนาดเสาเข็ม D_pile", _cm(g("Dp")), "cm", nd=1)
    _row(pdf, "น้ำหนักบรรทุกใช้งานรวม (P_DL+P_LL+Wf)", g("P_serv_kgf"), "kgf", nd=0)
    _row(pdf, "น้ำหนักบรรทุกประลัยสุทธิ Pu,net = 1.2 P_DL + 1.6 P_LL",
         g("Pu_net_kgf"), "kgf", nd=0)
    _row(pdf, "กำลังรับน้ำหนักปลอดภัยของเสาเข็ม", g("pile_cap_kgf"), "kgf/ต้น", nd=0)
    _row(pdf, "ขนาดเสาสี่เหลี่ยมจัตุรัส c", _cm(g("c")), "cm", nd=2)
    _row(pdf, "ความหนาฐานราก h", _cm(g("h")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีตด้านข้าง", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "ระยะฝังเข็ม (Pile Embedment)", g("pile_embed_cm"), "cm", nd=1)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)
    _row(pdf, "ระยะเยื้องศูนย์ของเสา ex , ey",
         f"{_fmt(ex_cm, 2)} , {_fmt(ey_cm, 2)} cm")
    if ex_cm or ey_cm:
        _row(pdf, "โมเมนต์เยื้องศูนย์ Muy = Pu,net x (ex/100)",
             g("Muy_kgfm"), "kgf-m", nd=0)
        _row(pdf, "โมเมนต์เยื้องศูนย์ Mux = Pu,net x (ey/100)",
             g("Mux_kgfm"), "kgf-m", nd=0)

    _section(pdf, "แรงปฏิกิริยาในเสาเข็ม (Pile Reactions)")
    _row(pdf, "แรงเฉลี่ยต่อเสาเข็ม (ใช้งาน รวม Wf) R = ΣP / n",
         r("R_serv_kgf"), "kgf/ต้น", nd=0)
    _row(pdf, "แรงในเสาเข็มสูงสุด (ใช้งาน รวม Wf) Rmax",
         r("R_max_kgf"), "kgf/ต้น", nd=0)
    _row(pdf, "แรงในเสาเข็มต่ำสุด (ใช้งาน รวม Wf) Rmin",
         r("R_min_kgf"), "kgf/ต้น", nd=0)
    _row(pdf, "Rmax <= กำลังปลอดภัยของเสาเข็ม", _chk(r("reaction_ok")))
    _row(pdf, "Rmin >= 0 (ไม่มีแรงถอน)", _chk(r("uplift_ok")))
    _row(pdf, "แรงในเสาเข็มสูงสุด (ประลัยสุทธิ) Ru,max",
         r("Ru_max_kgf"), "kgf/ต้น", nd=0)

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล ด้านยาว d_long / ด้านสั้น d_short",
         f"{_fmt(_cm(r('d_long')), 2)} / {_fmt(_cm(r('d_short')), 2)} cm")
    _row(pdf, "ระยะห่างเสาเข็ม S = 3 x Dp", _cm(r("S")), "cm", nd=2)
    _row(pdf, "ระยะขอบ (ศูนย์กลางเข็มถึงขอบ)", _cm(r("edge")), "cm", nd=2)
    _row(pdf, "ขนาดฐานราก (กว้าง x ยาว)",
         f"{_fmt(_cm(r('cap_W')), 0)} x {_fmt(_cm(r('cap_L')), 0)} cm"
         + ("  (กำหนดโดยผู้ใช้)" if g("manual_cap") else "  (อัตโนมัติ)"))
    _row(pdf, "แรงเฉือนทะลุ สองทาง Vu = Pu,net - Σ Ru,i(ในเขตวิกฤต)",
         _kgf(r("Vup_kN")), "kgf", nd=0)
    _row(pdf, "แรงเฉือนทะลุ สองทาง phi*Vc (d = d_avg)",
         _kgf(r("phiVc_punch_kN")), "kgf", nd=0)
    _row(pdf, "เส้นรอบรูปวิกฤตหัวเข็ม b0,pile", _fmt(g("pile_perim_txt") or "-"))
    _row(pdf, "แรงเฉือนทะลุหัวเข็ม phi*Vc", _kgf(r("phiVc_pile_kN")), "kgf", nd=0)

    _image_section(pdf, r("section_img"),
                   title="รายละเอียดหน้าตัด (Plan + Side View)")

    _section(pdf, "การดัด / แรงเฉือนคาน — ด้านยาว (Long Direction)")
    _row(pdf, "โมเมนต์ที่ผิวเสา Mu,long", _kgfm(r("Mu_long_kNm")),
         "kgf-m", nd=0)
    _row(pdf, "แรงเฉือนคาน Vu,long / phi*Vc",
         f"{_fmt(_kgf(r('Vu_long_kN')), 0)} / {_fmt(_kgf(r('phiVc_long_kN')), 0)} kgf")
    _row(pdf, "As,req (long)", _cm2(r("As_req_long")), "cm2", nd=2)
    _row(pdf, "As,min (long)", _cm2(r("As_min_long")), "cm2", nd=2)
    _row(pdf, "เหล็กที่จัดให้ (long) — จำนวน x ขนาด",
         f"{_fmt(r('n_long'), 0)} - {_fmt(r('size_long'))}")
    _row(pdf, "ระยะเรียงที่คำนวณได้ S (long) [<= s_max]",
         f"{_fmt(r('s_long_cm'), 1)} cm  [{_fmt(r('s_max_cm'), 1)}]  "
         f"{_chk(r('sp_long_ok'))}")
    _row(pdf, "As,prov (long) = n x Ab", _cm2(r("As_prov_long")), "cm2", nd=2)

    _section(pdf, "การดัด / แรงเฉือนคาน — ด้านสั้น (Short Direction)")
    _row(pdf, "โมเมนต์ที่ผิวเสา Mu,short", _kgfm(r("Mu_short_kNm")),
         "kgf-m", nd=0)
    _row(pdf, "แรงเฉือนคาน Vu,short / phi*Vc",
         f"{_fmt(_kgf(r('Vu_short_kN')), 0)} / {_fmt(_kgf(r('phiVc_short_kN')), 0)} kgf")
    _row(pdf, "As,req (short)", _cm2(r("As_req_short")), "cm2", nd=2)
    _row(pdf, "As,min (short)", _cm2(r("As_min_short")), "cm2", nd=2)
    _row(pdf, "เหล็กที่จัดให้ (short) — จำนวน x ขนาด",
         f"{_fmt(r('n_short'), 0)} - {_fmt(r('size_short'))}")
    _row(pdf, "ระยะเรียงที่คำนวณได้ S (short) [<= s_max]",
         f"{_fmt(r('s_short_cm'), 1)} cm  [{_fmt(r('s_max_cm'), 1)}]  "
         f"{_chk(r('sp_short_ok'))}")
    _row(pdf, "As,prov (short) = n x Ab", _cm2(r("As_prov_short")), "cm2", nd=2)

    _section(pdf, _S_CONCL)
    _row(pdf, "แรงในเสาเข็มสูงสุด Rmax", r("R_max_kgf"), "kgf/ต้น", nd=0)
    _row(pdf, "Rmax <= กำลังปลอดภัยของเสาเข็ม", _chk(r("reaction_ok")))
    _row(pdf, "Rmin >= 0 (ไม่มีแรงถอน)", _chk(r("uplift_ok")))
    _row(pdf, "แรงเฉือนทะลุ สองทาง (Vu <= phi*Vc)", _chk(r("punch_ok")))
    _row(pdf, "แรงเฉือนทะลุหัวเข็ม (Ru <= phi*Vc)", _chk(r("pile_punch_ok")))
    _row(pdf, "แรงเฉือนคาน — ด้านยาว (Vu <= phi*Vc)", _chk(r("beam_long_ok")))
    _row(pdf, "แรงเฉือนคาน — ด้านสั้น (Vu <= phi*Vc)", _chk(r("beam_short_ok")))
    _row(pdf, "การดัด — ด้านยาว (As,prov >= As,req)", _chk(r("flex_long_ok")))
    _row(pdf, "การดัด — ด้านสั้น (As,prov >= As,req)", _chk(r("flex_short_ok")))
    _row(pdf, "เหล็กขั้นต่ำ — ด้านยาว", _chk(r("asmin_long_ok")))
    _row(pdf, "เหล็กขั้นต่ำ — ด้านสั้น", _chk(r("asmin_short_ok")))
    _row(pdf, "ระยะเรียง — ด้านยาว (S <= s_max)", _chk(r("sp_long_ok")))
    _row(pdf, "ระยะเรียง — ด้านสั้น (S <= s_max)", _chk(r("sp_short_ok")))

    summary = (
        f"ฐานรากเสาเข็ม {_fmt(g('n_piles'))} ต้น. "
        f"ด้านยาว: As ที่จัดให้ {_f2(_cm2(r('As_prov_long')))} / ที่ต้องการ "
        f"{_f2(_cm2(r('As_req_long')))} cm2  ·  ด้านสั้น: As ที่จัดให้ "
        f"{_f2(_cm2(r('As_prov_short')))} / ที่ต้องการ "
        f"{_f2(_cm2(r('As_req_short')))} cm2. แรงในเสาเข็ม "
        f"{_chk(r('reaction_ok'))}, แรงเฉือนทะลุ {_chk(r('punch_ok'))}, "
        f"การดัด (ยาว {_chk(r('flex_long_ok'))} / สั้น {_chk(r('flex_short_ok'))})."
    )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)
