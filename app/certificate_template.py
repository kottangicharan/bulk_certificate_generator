"""
Certificate PDF generation using ReportLab.

Produces a landscape-A4 certificate with:
  - Decorative double border
  - Certificate title
  - Recipient name
  - Event / course name
  - Organizer name
  - Issue date
  - Unique certificate ID
"""

import os

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    certificate_id: str,
    recipient_name: str,
    event_name: str,
    organizer_name: str,
    issue_date: str,
    output_dir: str = "certificates",
) -> str:
    """
    Render a single certificate and return the path to the saved PDF file.

    Raises on I/O or rendering errors so the caller can mark the certificate
    as failed.
    """
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{certificate_id}.pdf")

    width, height = landscape(A4)
    c = canvas.Canvas(file_path, pagesize=landscape(A4))

    # -- background ----------------------------------------------------------
    c.setFillColor(HexColor("#FFFFF0"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # -- decorative double border --------------------------------------------
    c.setStrokeColor(HexColor("#1a365d"))
    c.setLineWidth(3)
    c.rect(30, 30, width - 60, height - 60)
    c.setLineWidth(1)
    c.rect(40, 40, width - 80, height - 80)

    # -- corner accents (small gold squares) ---------------------------------
    gold = HexColor("#c9a84c")
    accent_size = 12
    for x, y in [
        (34, 34), (34, height - 34 - accent_size),
        (width - 34 - accent_size, 34),
        (width - 34 - accent_size, height - 34 - accent_size),
    ]:
        c.setFillColor(gold)
        c.rect(x, y, accent_size, accent_size, fill=1, stroke=0)

    # -- title ---------------------------------------------------------------
    c.setFillColor(HexColor("#1a365d"))
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width / 2, height - 120, "CERTIFICATE OF COMPLETION")

    # -- gold rule under title -----------------------------------------------
    c.setStrokeColor(gold)
    c.setLineWidth(2)
    c.line(width / 2 - 150, height - 138, width / 2 + 150, height - 138)

    # -- preamble text -------------------------------------------------------
    c.setFillColor(HexColor("#4a5568"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 180, "This is to certify that")

    # -- recipient name ------------------------------------------------------
    c.setFillColor(HexColor("#1a365d"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width / 2, height - 225, recipient_name)

    # -- gold rule under name ------------------------------------------------
    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.line(width / 2 - 200, height - 242, width / 2 + 200, height - 242)

    # -- completion text -----------------------------------------------------
    c.setFillColor(HexColor("#4a5568"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 278, "has successfully completed")

    # -- event name ----------------------------------------------------------
    c.setFillColor(HexColor("#2d3748"))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 315, event_name)

    # -- organizer -----------------------------------------------------------
    c.setFillColor(HexColor("#4a5568"))
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 350, f"Organized by {organizer_name}")

    # -- issue date ----------------------------------------------------------
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 390, f"Date of Issue: {issue_date}")

    # -- certificate ID footer -----------------------------------------------
    c.setFillColor(HexColor("#a0aec0"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 55, f"Certificate ID: {certificate_id}")

    c.save()
    return file_path
