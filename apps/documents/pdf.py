"""The Dakdot document look, drawn with fpdf2: the centred logo, a teal accent, Inter Tight (the app's font), narrow
margins, and the contact line at the foot of every page. Layouts (layouts.py) use these helpers and never touch fpdf2 directly
for styling, so restyling happens here."""

from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts" / "intertight"
FONT = "InterTight"
LOGO = HERE / "assets" / "dakdot-logo.svg"  # includes "Digital Solutions. Design Excellence."
LOGO_WIDTH = 46  # mm; the logo is 172 x 79, so about 21 mm tall
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 9, 7, 14
ACCENT = (98, 153, 150)      # #629996, the teal on the paper invoices
ACCENT_SOFT = (221, 232, 232)
INK = (24, 24, 27)
MUTED = (110, 110, 110)
GOLD = (232, 190, 92)
NEXT = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
RIGHT = {"new_x": XPos.RIGHT, "new_y": YPos.TOP}


def num(value):
    return f"{Decimal(value or 0):,.0f}"


class DakdotPDF(FPDF):
    def __init__(self, company, title):
        super().__init__(format="A4", unit="mm")
        self.company, self.doc_title = company, title
        self.add_font(FONT, "", FONTS / "InterTight-Regular.ttf")
        self.add_font(FONT, "B", FONTS / "InterTight-Bold.ttf")
        self.set_margins(MARGIN_X, MARGIN_TOP, MARGIN_X)
        self.set_auto_page_break(True, margin=MARGIN_BOTTOM)
        self.set_title(title)
        self.set_author(company.legal_name)
        self.set_creator(company.name)
        self.void = False
        self.add_page()

    # ---------------------------------------------------------------- page furniture
    def header(self):
        """The logo, centred, on the first page only. A logo uploaded in the company settings replaces the bundled
        one; the bundled SVG already carries the tagline, so no tagline text is printed."""
        if self.page_no() > 1:
            self.set_y(MARGIN_TOP)
            return
        x, top = (self.w - LOGO_WIDTH) / 2, MARGIN_TOP
        try:
            self.image(self.company.logo.path if self.company.logo else LOGO, x=x, y=top, w=LOGO_WIDTH)
        except (OSError, ValueError):
            self.image(LOGO, x=x, y=top, w=LOGO_WIDTH)
        self.set_y(top + LOGO_WIDTH * 79 / 172 + 6)

    def footer(self):
        if self.void:
            self._stamp("VOID")
        self.set_y(-10)
        self.font(8.5, color=MUTED)
        self.cell(0, 5, self.company.footer_line, align="C")
        if self.page_no() > 1:
            self.set_y(-10)
            self.cell(0, 5, f"{self.page_no()}/{{nb}}", align="R")

    def _stamp(self, text):
        with self.rotation(30, self.w / 2, self.h / 2):
            self.set_text_color(220, 60, 60)
            self.set_font(FONT, "B", 90)
            with self.local_context(fill_opacity=0.15, stroke_opacity=0.15):
                self.text(self.w / 2 - 45, self.h / 2 + 10, text)

    # ---------------------------------------------------------------- text helpers
    def font(self, size=10, bold=False, color=INK):
        self.set_font(FONT, "B" if bold else "", size)
        self.set_text_color(*color)

    @property
    def width(self):
        return self.w - self.l_margin - self.r_margin

    def heading_block(self, left_rows, title, right_rows):
        """Date / "Invoice To" on the left, the big title and number on the right, on one band."""
        top = self.get_y()
        self.font(26, bold=True)
        self.set_x(self.l_margin)
        self.cell(0, 11, title, align="R", **NEXT)
        for label, value in right_rows:
            self.font(10)
            self.cell(0, 5, f"{label}: {value}", align="R", **NEXT)
        bottom = self.get_y()
        self.set_y(top + 2)
        for label, value, boxed in left_rows:
            self.font(10.5, color=(255, 255, 255) if boxed else INK)
            if boxed:
                self.set_fill_color(*ACCENT)
                self.cell(self.get_string_width(label) + 6, 6, label, fill=True, **RIGHT)
                self.font(10.5, bold=True)
                self.cell(4, 6, "", **RIGHT)
                self.multi_cell(self.width / 2, 6, value, **NEXT)
            else:
                self.cell(0, 6, f"{label} {value}".strip(), **NEXT)
            self.ln(1)
        self.set_y(max(bottom, self.get_y()) + 6)

    def rule(self, color=ACCENT, width=0.4):
        self.set_draw_color(*color)
        self.set_line_width(width)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())

    def section_title(self, text):
        self.ln(3)
        self.font(11, bold=True)
        self.cell(0, 7, text, **NEXT)

    def numbered(self, items, size=8.5):
        self.font(size)
        for i, item in enumerate(items, 1):
            self.multi_cell(0, 4.2, f"{i}. {item}", **NEXT)

    # ---------------------------------------------------------------- tables
    def lines_table(self, lines):
        """Description (with its small note), Price, Qty, Total: the Dakdot invoice table."""
        w = self.width
        cols = (w * 0.52, w * 0.17, w * 0.11, w * 0.20)
        self.font(12)
        for text, width, align in zip(("Description", "Price", "Qty", "Total"), cols, ("L", "R", "C", "R")):
            self.cell(width, 9, text, align=align, **RIGHT)
        self.ln(9)
        self.rule()
        self.ln(3)
        for line in lines:
            desc_lines = self.multi_cell(cols[0] - 2, 5, line.description, dry_run=True, output="LINES")
            height = 5 * len(desc_lines) + (4 if line.note else 0) + 4
            if self.get_y() + height > self.page_break_trigger:
                self.add_page()
            y = self.get_y()
            self.font(10.5)
            self.multi_cell(cols[0] - 2, 5, line.description, **NEXT)
            if line.note:
                self.font(7, color=MUTED)
                self.cell(cols[0], 3.5, line.note, **NEXT)
            self.set_xy(self.l_margin + cols[0], y)
            self.font(10.5)
            self.cell(cols[1], 5, "-" if line.is_lump_sum else num(line.unit_price), align="R", **RIGHT)
            self.cell(cols[2], 5, "-" if line.is_lump_sum else line.quantity_label, align="C", **RIGHT)
            self.cell(cols[3], 5, num(line.amount), align="R", **RIGHT)
            self.set_y(y + height)

    def totals(self, rows):
        """Right-hand summary rows: (label, value, bold?)."""
        w = self.width
        for label, value, bold in rows:
            self.set_x(self.l_margin + w * 0.52)
            self.font(10.5, bold=bold)
            self.cell(w * 0.28, 7, label, align="C" if bold else "R", **RIGHT)
            self.font(11 if bold else 10.5, bold=bold)
            self.cell(w * 0.20, 7, value, align="R", **NEXT)

    def grid(self, headers, rows, widths, aligns, header_fill=ACCENT):
        """A plain table: teal header band, light rules between rows."""
        self.font(9, bold=True, color=(255, 255, 255))
        self.set_fill_color(*header_fill)
        for text, width, align in zip(headers, widths, aligns):
            self.cell(width, 7, text, align=align, fill=True, **RIGHT)
        self.ln(7)
        self.set_draw_color(*ACCENT_SOFT)
        self.set_line_width(0.2)
        for row in rows:
            if self.get_y() + 7 > self.page_break_trigger:
                self.add_page()
            bold = row[-1] is True
            cells = row[:-1] if isinstance(row[-1], bool) else row
            self.font(9.5, bold=bold)
            for text, width, align in zip(cells, widths, aligns):
                self.cell(width, 7, str(text), align=align, border="B", **RIGHT)
            self.ln(7)

    def payment_methods(self, accounts):
        """Each account shown on documents, side by side: name, then number / name / SWIFT."""
        accounts = [a for a in accounts if a.show_on_documents and a.is_active]
        if not accounts:
            return
        self.section_title("Payment Methods")
        col = self.width / min(len(accounts), 2)
        for start in range(0, len(accounts), 2):
            pair = accounts[start:start + 2]
            top = self.get_y()
            bottom = top
            for i, account in enumerate(pair):
                x = self.l_margin + i * col
                self.set_xy(x, top)
                self.font(8.5, bold=True)
                self.cell(col, 5, account.name, **NEXT)
                details = [("Account Number:", account.account_number), ("Account Name:", account.account_name),
                           ("SWIFT CODE:", account.swift_code)]
                for label, value in details:
                    if not value:
                        continue
                    self.set_x(x)
                    self.font(8)
                    self.cell(28, 4.2, label, **RIGHT)
                    self.cell(col - 28, 4.2, value, **NEXT)
                bottom = max(bottom, self.get_y())
            self.set_y(bottom + 2)

    def bytes(self):
        return bytes(self.output())
