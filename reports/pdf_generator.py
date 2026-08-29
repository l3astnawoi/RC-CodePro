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

Thai text needs a Unicode TrueType font.  Place THSarabunNew.ttf (and,
optionally, "THSarabunNew Bold.ttf" / "THSarabunNew Italic.ttf") in the
project-level ``fonts/`` folder.  If the font is missing the sheets are
still produced with a Latin core font (Thai glyphs will not render).
"""

import os
import tempfile
from datetime import date

from fpdf import FPDF

# ---------------------------------------------------------------------------
# Thai Unicode font
# ---------------------------------------------------------------------------

FONT_NAME = "ThaiFont"
FONT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts"
)
FONT_REGULAR = os.path.join(FONT_DIR, "THSarabunNew.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "THSarabunNew Bold.ttf")
FONT_ITALIC = os.path.join(FONT_DIR, "THSarabunNew Italic.ttf")
FONT_BOLDITALIC = os.path.join(FONT_DIR, "THSarabunNew BoldItalic.ttf")

FONT_AVAILABLE = os.path.isfile(FONT_REGULAR)

# Active font family: the Thai font when installed, otherwise a Latin core font.
_FONT = FONT_NAME if FONT_AVAILABLE else "Arial"

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
        pdf.set_font(_FONT, "B", 10)
        pdf.cell(42, 5.5, _t(label))
        pdf.set_font(_FONT, "", 10)
        pdf.cell(0, 5.5, _t(f":  {value}"), ln=1)
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
        self.set_font(_FONT, "B", 18)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 9, _t(self.report_title), align="C")
        self.set_draw_color(60, 60, 60)
        self.set_line_width(0.4)
        y = self.get_y() + 1
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(_FONT, "I", 10)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            _t(f"จัดทำเมื่อ {date.today().isoformat()}  -  "
               f"ACI 318M-08 (หน่วยเมตริก)  -  หน้า {self.page_no()}"),
            align="C",
        )


def _section(pdf, title):
    pdf.ln(2)
    pdf.set_font(_FONT, "B", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(228, 228, 228)
    pdf.cell(0, 8, _t(title), ln=1, fill=True)
    pdf.ln(1)


def _row(pdf, label, value, unit="", nd=2):
    pdf.set_font(_FONT, "", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(108, 7, _t(f"   {label}"))
    pdf.set_font(_FONT, "B", 12)
    text = _fmt(value, nd) if not unit else f"{_fmt(value, nd)} {unit}"
    pdf.cell(0, 7, _t(text), ln=1)


def _new_sheet(title, project=None):
    pdf = _Sheet(orientation="P", unit="mm", format="A4")
    pdf.project_info = project
    if FONT_AVAILABLE:
        pdf.add_font(FONT_NAME, "", FONT_REGULAR, uni=True)
        pdf.add_font(FONT_NAME, "B",
                     FONT_BOLD if os.path.isfile(FONT_BOLD) else FONT_REGULAR,
                     uni=True)
        pdf.add_font(FONT_NAME, "I",
                     FONT_ITALIC if os.path.isfile(FONT_ITALIC) else FONT_REGULAR,
                     uni=True)
        pdf.add_font(
            FONT_NAME, "BI",
            FONT_BOLDITALIC if os.path.isfile(FONT_BOLDITALIC)
            else (FONT_BOLD if os.path.isfile(FONT_BOLD) else FONT_REGULAR),
            uni=True,
        )
    pdf.report_title = title
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    return pdf


def _result_block(pdf, passed, status_text, summary=None):
    pdf.ln(4)
    pdf.set_font(_FONT, "B", 16)
    pdf.set_text_color(*((0, 130, 0) if passed else (190, 0, 0)))
    pdf.cell(0, 10, _t(f"ผลสรุป:  {_status_thai(passed)}"), ln=1)
    pdf.set_text_color(0, 0, 0)
    if summary:
        pdf.set_font(_FONT, "", 11)
        pdf.multi_cell(0, 6, _t(summary))


def _to_bytes(pdf):
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1")
    return bytes(out)


def _image_section(pdf, buf, title="รายละเอียดหน้าตัด", width_mm=80):
    """Insert a titled section holding a PNG image taken from a BytesIO buffer.

    Does nothing when `buf` is missing or empty.  The buffer is written to a
    temporary .png file (fpdf needs a path), embedded, then removed.
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

    _section(pdf, title)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        pdf.image(tmp.name, w=width_mm)
        pdf.ln(3)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
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
COLUMN_TITLE = "การออกแบบเสาคอนกรีตเสริมเหล็ก (ACI 318M-08)"
SLAB_TITLE = "การออกแบบพื้นทางเดียวคอนกรีตเสริมเหล็ก (ACI 318M-08)"
FOOTING_TITLE = "การออกแบบฐานรากเดี่ยวคอนกรีตเสริมเหล็ก (ACI 318M-08)"
STAIR_TITLE = "การออกแบบบันไดคอนกรีตเสริมเหล็ก (ACI 318M-08)"
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
    _row(pdf, "โมเมนต์ประลัย Mu", g("Mu"), "kN.m")
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
# Column
# ---------------------------------------------------------------------------


def generate_column_report(inputs, results):
    """สร้างใบคำนวณการออกแบบเสาและคืนค่าเป็นสตริงไบต์ (bytes)."""
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    Pu = r("Pu") if r("Pu") is not None else g("Pu")

    pdf = _new_sheet(COLUMN_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "น้ำหนักบรรทุกตามแนวแกนประลัย Pu", g("Pu"), "kN")
    _row(pdf, "ความกว้างหน้าตัด b", _cm(g("b")), "cm", nd=2)
    _row(pdf, "ความลึกหน้าตัด h", _cm(g("h")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)
    _row(pdf, "ประเภทเสา", g("col_type"))

    _section(pdf, _S_STEPS)
    _row(pdf, "พื้นที่หน้าตัดรวม Ag = b x h", _cm2(r("Ag")), "cm2", nd=2)
    _row(pdf, "ขนาดเหล็กเสริมที่เลือก", r("rebar_size"))
    _row(pdf, "จำนวนเส้นทั้งหมด", r("qty"))
    _row(pdf, "พื้นที่เหล็กที่จัดให้ Ast", _cm2(r("As_prov")), "cm2", nd=2)
    _row(pdf, "อัตราส่วนเหล็กเสริม rho = Ast / Ag", r("rho"), nd=4)
    _row(pdf, "ช่วง rho ที่ยอมให้",
         f"{_fmt(r('rho_min'), 2)} ถึง {_fmt(r('rho_max'), 2)}")
    _row(pdf, "ตัวคูณลดกำลัง phi", r("phi_c"), nd=2)
    _row(pdf, "ตัวคูณกำลังสูงสุด alpha", r("alpha"), nd=2)
    _row(pdf, "กำลังรับแรงตามแนวแกนออกแบบ phi_Pn", r("phi_Pn"), "kN")

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "กำลังรับแรงตามแนวแกนออกแบบ phi_Pn", r("phi_Pn"), "kN")
    _row(pdf, "น้ำหนักบรรทุกตามแนวแกนประลัย Pu", Pu, "kN")
    if r("phi_Pn") is not None and Pu is not None:
        rel = ">=" if passed else "<"
        _row(pdf, "การตรวจสอบ", f"phi_Pn {rel} Pu")

    summary = None
    if r("phi_Pn") is not None and Pu is not None:
        summary = (
            f"phi_Pn = {_fmt(r('phi_Pn'))} kN เทียบกับ Pu = {_fmt(Pu)} kN; "
            f"อัตราส่วนเหล็กเสริม rho = {_fmt(r('rho'), 4)} "
            f"(ขีดจำกัด {_fmt(r('rho_min'), 2)} ถึง {_fmt(r('rho_max'), 2)})."
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
    _row(pdf, "โมเมนต์ประลัย Mu", g("Mu"), "kN.m/m")
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
         f"{_fmt(r('main_size'))} @ {_fmt(r('main_spacing'))} mm")
    _row(pdf, "As หลักที่จัดให้", _cm2(r("As_prov_main")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (หลัก) = min(3t, 450)", r("max_sp_main"), "mm")
    _row(pdf, "เหล็กเสริมกันร้าว",
         f"{_fmt(r('temp_size'))} @ {_fmt(r('temp_spacing'))} mm")
    _row(pdf, "As กันร้าวที่จัดให้", _cm2(r("As_prov_temp")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (กันร้าว) = min(5t, 450)", r("max_sp_temp"), "mm")

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
    _row(pdf, "น้ำหนักบรรทุกตามแนวแกนใช้งาน P", _ton(g("P")), "ตัน", nd=2)
    _row(pdf, "น้ำหนักบรรทุกตามแนวแกนประลัย Pu", _ton(g("Pu")), "ตัน", nd=2)
    _row(pdf, "กำลังแบกทานดินที่ยอมให้ qa", _ton(g("q_a")), "ตัน/ตารางเมตร", nd=2)
    _row(pdf, "ขนาดเสาสี่เหลี่ยมจัตุรัส c", _cm(g("c")), "cm", nd=2)
    _row(pdf, "ความกว้างฐานราก B (สี่เหลี่ยมจัตุรัส)", _cm(g("B")), "cm", nd=2)
    _row(pdf, "ความหนาฐานราก h", _cm(g("h")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล d = h - covering - db", _cm(r("d")), "cm", nd=2)
    _row(pdf, "หน่วยแรงดินที่เกิดขึ้น q = P / B^2",
         _ton(r("q_applied")), "ตัน/ตารางเมตร", nd=2)
    _row(pdf, "หน่วยแรงดินที่ยอมให้ qa",
         _ton(r("q_a", g("q_a"))), "ตัน/ตารางเมตร", nd=2)
    _row(pdf, "หน่วยแรงดินประลัยสุทธิ qu = Pu / B^2", r("qu_kPa"), "kN/m2")
    _row(pdf, "แรงเฉือนทะลุ สองทาง Vu", r("Vup_kN"), "kN")
    _row(pdf, "แรงเฉือนทะลุ สองทาง phi*Vc", r("phiVc_punch_kN"), "kN")
    _row(pdf, "แรงเฉือนคาน ทางเดียว Vu", r("Vub_kN"), "kN")
    _row(pdf, "แรงเฉือนคาน ทางเดียว phi*Vc", r("phiVc_beam_kN"), "kN")
    _row(pdf, "โมเมนต์ที่ผิวเสา Mu", r("Mu_face"), "kN.m")
    _row(pdf, "พื้นที่เหล็กจากการดัด As,required", _cm2(r("As_req")), "cm2", nd=2)
    _row(pdf, "เหล็กเสริมขั้นต่ำ As,min", _cm2(r("As_min")), "cm2", nd=2)
    _row(pdf, "As ที่ต้องการที่ควบคุม", _cm2(gov), "cm2", nd=2)
    _row(pdf, "เหล็กเสริมหลัก", f"{_fmt(r('qty'))} - {_fmt(r('main_size'))}")
    _row(pdf, "พื้นที่เหล็กที่จัดให้ As,provided", _cm2(r("As_prov")), "cm2", nd=2)

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "กำลังแบกทานดิน (q <= q_a)", _chk(r("bearing_ok")))
    _row(pdf, "แรงเฉือนคาน ทางเดียว (Vu <= phi*Vc)", _chk(r("beam_ok")))
    _row(pdf, "แรงเฉือนทะลุ สองทาง (Vu <= phi*Vc)", _chk(r("punch_ok")))
    _row(pdf, "การดัด (As,provided >= As,required)", _chk(r("flexure_ok")))
    _row(pdf, "เหล็กเสริมขั้นต่ำ (As,provided >= As,min)", _chk(r("as_min_ok")))

    summary = None
    if gov is not None and r("As_prov") is not None:
        summary = (
            f"As ที่จัดให้ = {_f2(_cm2(r('As_prov')))} cm2 เทียบกับ "
            f"As ที่ต้องการที่ควบคุม = {_f2(_cm2(gov))} cm2. "
            f"กำลังแบกทานดิน {_chk(r('bearing_ok'))}, "
            f"แรงเฉือนทางเดียว {_chk(r('beam_ok'))}, แรงเฉือนสองทาง "
            f"{_chk(r('punch_ok'))}, การดัด {_chk(r('flexure_ok'))}."
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
    _row(pdf, "น้ำหนักบรรทุกคงที่เพิ่มเติม SDL", g("SDL"), "kN/m2")
    _row(pdf, "น้ำหนักบรรทุกจร LL", g("LL"), "kN/m2")
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)
    _row(pdf, "ความกว้างแถบออกแบบ b", _cm(g("b", 1000)), "cm", nd=2)

    _section(pdf, _S_LOADS)
    _row(pdf, "มุมลาดเอียง theta = atan(R/T)", r("theta_deg"), "deg")
    _row(pdf, "น้ำหนักตัวเอง SW = 24*(t/cos(theta) + R/2)", r("SW"), "kN/m2")
    _row(pdf, "น้ำหนักบรรทุกคงที่รวม DL = SW + SDL", r("DL"), "kN/m2")
    _row(pdf, "น้ำหนักบรรทุกประลัย wu = 1.2 DL + 1.6 LL", r("wu"), "kN/m")
    _row(pdf, "โมเมนต์ประลัย Mu = wu L^2 / 8", r("Mu"), "kN.m/m")

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล d = t - covering - db/2", _cm(r("d")), "cm", nd=2)
    _row(pdf, "พื้นที่เหล็กจากการดัด As,required", _cm2(r("As_req")), "cm2/m", nd=2)
    _row(pdf, "เหล็กกันร้าว/อุณหภูมิ As,min", _cm2(r("As_min")), "cm2/m", nd=2)
    _row(pdf, "As หลักที่ต้องการที่ควบคุม", _cm2(gov), "cm2/m", nd=2)
    _row(pdf, "เหล็กเสริมหลัก",
         f"{_fmt(r('main_size'))} @ {_fmt(r('main_spacing'))} mm")
    _row(pdf, "As หลักที่จัดให้", _cm2(r("As_prov_main")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (หลัก) = min(3t, 450)", r("max_sp_main"), "mm")
    _row(pdf, "เหล็กเสริมกันร้าว",
         f"{_fmt(r('temp_size'))} @ {_fmt(r('temp_spacing'))} mm")
    _row(pdf, "As กันร้าวที่จัดให้", _cm2(r("As_prov_temp")), "cm2/m", nd=2)
    _row(pdf, "ระยะเรียงสูงสุด (กันร้าว) = min(5t, 450)", r("max_sp_temp"), "mm")

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
            f"โมเมนต์ประลัย Mu = {_fmt(r('Mu'))} kN.m/m."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)


# ---------------------------------------------------------------------------
# Pile cap (F2 / F4)
# ---------------------------------------------------------------------------


def generate_pile_cap_report(inputs, results):
    """สร้างใบคำนวณการออกแบบฐานรากเสาเข็มและคืนค่าเป็นสตริงไบต์ (bytes).

    Expected keys
        inputs  : P, Pu, pile_cap, n_piles, Dp, c, h, covering, fc, fy,
                  ex, ey   (SI; ex/ey shown only when non-zero)
        results : d, R_serv, R_max, Ru_kN, Ru_max_kN, S, edge, cap_W, cap_L,
                  n_inside,
                  Vup_kN, phiVc_punch_kN, phiVc_pile_kN, n_beyond, Vub_kN,
                  phiVc_beam_kN, Mu_face, As_req, As_min, main_size, qty,
                  As_prov, reaction_ok, punch_ok, pile_punch_ok, beam_ok,
                  flexure_ok, as_min_ok, section_img, status
    """
    g = inputs.get
    r = results.get

    status_text = _status_text(results)
    passed = status_text == "PASS"
    gov = _governing_as(r)

    pdf = _new_sheet(PILECAP_TITLE, inputs.get("project"))

    _section(pdf, _S_INPUT)
    _row(pdf, "จำนวนเสาเข็ม", g("n_piles"), "ต้น")
    _row(pdf, "น้ำหนักบรรทุกตามแนวแกนใช้งาน P", _ton(g("P")), "ตัน", nd=2)
    _row(pdf, "น้ำหนักบรรทุกตามแนวแกนประลัย Pu", _ton(g("Pu")), "ตัน", nd=2)
    _row(pdf, "กำลังรับน้ำหนักปลอดภัยของเสาเข็ม", _ton(g("pile_cap")), "ตัน/ต้น", nd=2)
    _row(pdf, "ขนาด/เส้นผ่านศูนย์กลางเสาเข็ม Dp", _cm(g("Dp")), "cm", nd=2)
    _row(pdf, "ขนาดเสาสี่เหลี่ยมจัตุรัส c", _cm(g("c")), "cm", nd=2)
    _row(pdf, "ความหนาฐานราก h", _cm(g("h")), "cm", nd=2)
    _row(pdf, "ระยะหุ้มคอนกรีต", _cm(g("covering")), "cm", nd=2)
    _row(pdf, "กำลังอัดคอนกรีต f'c", _ksc(g("fc")), "ksc", nd=0)
    _row(pdf, "กำลังครากเหล็กเสริม fy", _ksc(g("fy")), "ksc", nd=0)
    if g("ex"):
        _row(pdf, "ระยะเยื้องศูนย์ของเสา ex", _cm(g("ex")), "cm", nd=2)
    if g("ey"):
        _row(pdf, "ระยะเยื้องศูนย์ของเสา ey", _cm(g("ey")), "cm", nd=2)

    _section(pdf, _S_STEPS)
    _row(pdf, "ความลึกประสิทธิผล d = h - covering - db", _cm(r("d")), "cm", nd=2)
    _row(pdf, "แรงในเสาเข็มเฉลี่ย (ใช้งาน) R = P / n", _ton(r("R_serv")), "ตัน/ต้น", nd=2)
    _row(pdf, "แรงในเสาเข็มสูงสุด (ใช้งาน) Rmax", _ton(r("R_max")), "ตัน/ต้น", nd=2)
    _row(pdf, "แรงในเสาเข็มสูงสุด (ประลัย) Ru,max", r("Ru_max_kN", r("Ru_kN")),
         "kN/ต้น", nd=1)
    _row(pdf, "ระยะห่างเสาเข็ม S = 3 x Dp", _cm(r("S")), "cm", nd=2)
    _row(pdf, "ระยะขอบ (ศูนย์กลางเข็มถึงขอบ)", _cm(r("edge")), "cm", nd=2)
    _row(pdf, "ขนาดฐานราก (กว้าง x ยาว)",
         f"{_fmt(_cm(r('cap_W')), 0)} x {_fmt(_cm(r('cap_L')), 0)} cm")
    _row(pdf, "แรงเฉือนทะลุ สองทาง Vu = Pu - Ru(ใน)", r("Vup_kN"), "kN", nd=1)
    _row(pdf, "แรงเฉือนทะลุ สองทาง phi*Vc", r("phiVc_punch_kN"), "kN", nd=1)
    _row(pdf, "แรงเฉือนทะลุหัวเข็ม phi*Vc", r("phiVc_pile_kN"), "kN", nd=1)
    _row(pdf, "แรงเฉือนคาน ทางเดียว Vu = n x Ru", r("Vub_kN"), "kN", nd=1)
    _row(pdf, "แรงเฉือนคาน ทางเดียว phi*Vc", r("phiVc_beam_kN"), "kN", nd=1)
    _row(pdf, "โมเมนต์ที่ผิวเสา Mu", r("Mu_face"), "kN.m", nd=2)
    _row(pdf, "พื้นที่เหล็กจากการดัด As,required", _cm2(r("As_req")), "cm2", nd=2)
    _row(pdf, "เหล็กเสริมขั้นต่ำ As,min", _cm2(r("As_min")), "cm2", nd=2)
    _row(pdf, "As ที่ต้องการที่ควบคุม", _cm2(gov), "cm2", nd=2)
    _row(pdf, "เหล็กเสริมหลัก", f"{_fmt(r('qty'))} - {_fmt(r('main_size'))}")
    _row(pdf, "พื้นที่เหล็กที่จัดให้ As,provided", _cm2(r("As_prov")), "cm2", nd=2)

    _image_section(pdf, r("section_img"))

    _section(pdf, _S_CONCL)
    _row(pdf, "แรงในเสาเข็มสูงสุด Rmax", _ton(r("R_max")), "ตัน/ต้น", nd=2)
    _row(pdf, "Rmax <= กำลังปลอดภัยของเสาเข็ม", _chk(r("reaction_ok")))
    _row(pdf, "แรงเฉือนทะลุ สองทาง (Vu <= phi*Vc)", _chk(r("punch_ok")))
    _row(pdf, "แรงเฉือนทะลุหัวเข็ม (Ru <= phi*Vc)", _chk(r("pile_punch_ok")))
    _row(pdf, "แรงเฉือนคาน ทางเดียว (Vu <= phi*Vc)", _chk(r("beam_ok")))
    _row(pdf, "การดัด (As,provided >= As,required)", _chk(r("flexure_ok")))
    _row(pdf, "เหล็กเสริมขั้นต่ำ (As,provided >= As,min)", _chk(r("as_min_ok")))

    summary = None
    if gov is not None and r("As_prov") is not None:
        summary = (
            f"ฐานรากเสาเข็ม {_fmt(g('n_piles'))} ต้น: As ที่จัดให้ = "
            f"{_f2(_cm2(r('As_prov')))} cm2 เทียบกับ As ที่ต้องการที่ควบคุม = "
            f"{_f2(_cm2(gov))} cm2. แรงในเสาเข็ม {_chk(r('reaction_ok'))}, "
            f"แรงเฉือนทะลุ {_chk(r('punch_ok'))}, แรงเฉือนคาน {_chk(r('beam_ok'))}, "
            f"การดัด {_chk(r('flexure_ok'))}."
        )
    _result_block(pdf, passed, status_text, summary)

    return _to_bytes(pdf)
