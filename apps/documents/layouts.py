"""One function per document: the saved records in, PDF bytes out. Plain sync code: the view runs it in a
worker thread (documents/views.py), so it may use the ORM freely."""

from apps.core.models import CompanySettings
from apps.finance.models import Account

from .pdf import MUTED, DakdotPDF, num


def _date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


def billing_document(doc):
    """An issued quotation or invoice."""
    company = CompanySettings.load()
    is_invoice = doc._meta.model_name == "invoice"
    title = "INVOICE" if is_invoice else "QUOTATION"
    pdf = DakdotPDF(company, f"{title.title()} {doc.number}")
    pdf.void = doc.is_void

    right = [("Invoice No" if is_invoice else "Quotation No", doc.number)]
    if is_invoice and doc.due_date:
        right.append(("Due", _date(doc.due_date)))
    if not is_invoice and doc.valid_until:
        right.append(("Valid until", _date(doc.valid_until)))
    pdf.heading_block(
        [("Date:", _date(doc.date), False), ("Invoice To:" if is_invoice else "Quotation For:", doc.client.name, True)],
        title, right)

    pdf.lines_table(doc.lines.all())
    pdf.ln(2)
    rows = [("TOTAL", num(doc.total), True)]
    if is_invoice and doc.amount_paid:
        rows += [("Paid", num(doc.amount_paid), False), ("Balance Due", num(doc.balance), True)]
    pdf.totals(rows)

    if doc.notes:
        pdf.section_title("Notes")
        pdf.font(9)
        pdf.multi_cell(0, 4.5, doc.notes)
    pdf.ln(4)
    pdf.payment_methods(Account.objects.all())
    if doc.term_list:
        pdf.section_title("Terms and Conditions")
        pdf.numbered(doc.term_list)
    return pdf.bytes()


def receipt(rct):
    company = CompanySettings.load()
    pdf = DakdotPDF(company, f"Receipt {rct.number}")
    pdf.void = rct.status == "void"
    pdf.heading_block([("Date:", _date(rct.date), False), ("Received from:", rct.received_from, True)],
                      "RECEIPT", [("Receipt No", rct.number)])

    # the amount band
    pdf.set_fill_color(221, 232, 232)
    pdf.font(9, color=MUTED)
    pdf.cell(0, 7, "AMOUNT RECEIVED", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.font(20, bold=True)
    pdf.cell(0, 11, f"{rct.currency} {num(rct.amount)}", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.font(10, bold=True)
    pdf.cell(0, 6, "Being payment for", new_x="LMARGIN", new_y="NEXT")
    pdf.font(10)
    pdf.multi_cell(0, 5, rct.being_payment_for, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.font(10, bold=True)
    pdf.cell(pdf.get_string_width("Amount in words: ") + 1, 6, "Amount in words:")
    pdf.font(10)
    pdf.multi_cell(0, 6, rct.amount_in_words, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    w = pdf.width
    if rct.invoice_id:
        pdf.grid(("INVOICE REF", "PAYMENT METHOD", "TRANSACTION ID"),
                 [(rct.invoice.number, rct.account.name, rct.reference or "-")], (w * 0.3, w * 0.35, w * 0.35), ("L", "L", "L"))
        pdf.ln(4)
        rows = [("Invoice Total", num(rct.invoice_total), False), ("Previously Paid", num(rct.previously_paid), False),
                ("This Payment", num(rct.amount), False), ("Balance Due", num(rct.balance_due), True)]
        if rct.kept_as_credit:
            rows.append(("Held as Credit", num(rct.kept_as_credit), False))
        pdf.totals(rows)
    else:
        # a deposit: no invoice yet, so the money is held as the client's credit towards it
        towards = rct.quotation.number if rct.quotation_id else (rct.project.title if rct.project_id else "On account")
        pdf.grid(("DEPOSIT TOWARDS", "PAYMENT METHOD", "TRANSACTION ID"),
                 [(towards, rct.account.name, rct.reference or "-")], (w * 0.3, w * 0.35, w * 0.35), ("L", "L", "L"))
        pdf.ln(4)
        pdf.totals([("Deposit Received", num(rct.amount), True)])
        pdf.ln(1)
        pdf.font(9, color=MUTED)
        pdf.multi_cell(0, 4.5, "Held as credit and taken off the invoice when it is issued.", align="R",
                       new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.payment_methods(Account.objects.all())
    terms = [t.strip() for t in company.receipt_terms.splitlines() if t.strip()]
    if terms:
        pdf.section_title("Notes")
        pdf.numbered(terms)
    pdf.ln(4)
    pdf.font(11, bold=True)
    pdf.cell(0, 6, company.receipt_thank_you, align="C")
    return pdf.bytes()


def statement(client, rows, balance):
    from django.utils import timezone
    company = CompanySettings.load()
    pdf = DakdotPDF(company, f"Statement {client.name}")
    in_credit = balance < 0
    label, shown = ("In Credit", num(-balance)) if in_credit else ("Balance Due", num(balance))
    pdf.heading_block([("Date:", _date(timezone.localdate()), False), ("Statement For:", client.name, True)],
                      "STATEMENT", [(label, f"UGX {shown}")])
    w = pdf.width
    pdf.grid(("DATE", "REFERENCE", "DETAILS", "BILLED", "PAID", "BALANCE"),
             [(_date(r["date"]), r["ref"], r["what"][:38], num(r["debit"]) if r["debit"] else "",
               num(r["credit"]) if r["credit"] else "",
               f'{num(-r["balance"])} CR' if r["balance"] < 0 else num(r["balance"])) for r in rows]
             + [("", "", label, "", "", shown, True)],
             (w * 0.13, w * 0.17, w * 0.28, w * 0.14, w * 0.14, w * 0.14), ("L", "L", "L", "R", "R", "R"))
    pdf.ln(6)
    pdf.payment_methods(Account.objects.all())
    return pdf.bytes()
