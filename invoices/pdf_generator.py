"""
Invoice Generator PDF Generator
Creates professional PDF invoices using ReportLab.
"""

import os
from datetime import datetime
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from loguru import logger

from backend.config import settings


class InvoicePDFGenerator:
    """
    Generates professional PDF invoices for construction contractors.
    Includes contractor info, customer info, itemized list, and totals.
    """

    def __init__(self):
        self.output_dir = settings.INVOICE_OUTPUT_DIR
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Define custom paragraph styles for the invoice."""
        self.styles.add(ParagraphStyle(
            name="InvoiceTitle",
            parent=self.styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1a365d"),
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="InvoiceSubtitle",
            parent=self.styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#4a5568"),
            spaceAfter=2,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#2d3748"),
            spaceBefore=12,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="InfoText",
            parent=self.styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#4a5568"),
            leading=14,
        ))

    def generate(self, invoice_data: dict) -> str:
        """
        Generate a PDF invoice.

        Args:
            invoice_data: Dictionary containing invoice details:
                - invoice_number: str
                - date: str
                - contractor: dict (company_name, owner_name, address, phone, email)
                - customer: dict (name, address, phone, email)
                - project_location: str
                - items: list of dicts (item_name, description, quantity, unit, unit_price, total)
                - subtotal: float
                - tax_rate: float
                - tax_amount: float
                - total: float
                - payment_terms: str
                - notes: str

        Returns:
            Path to generated PDF file
        """
        invoice_num = invoice_data.get("invoice_number", "INV-0000")
        filename = f"{invoice_num}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.75 * inch,
        )

        elements = []

        # ---- Header Section (centered) ----
        elements.append(Paragraph(
            "INVOICE",
            ParagraphStyle(
                name="InvoiceTitleCenter",
                parent=self.styles["InvoiceTitle"],
                alignment=1,  # Center
            ),
        ))
        elements.append(Spacer(1, 12))

        # ---- Bill To (left) & From (right) ----
        contractor = invoice_data.get("contractor", {})
        customer = invoice_data.get("customer", {})
        date_str = invoice_data.get("date", datetime.now().strftime("%B %d, %Y"))
        location = invoice_data.get("project_location", "")

        # Left side: Bill To + invoice meta + project location
        bill_to_parts = [
            f"<b>Bill To:</b><br/>"
            f"{customer.get('name', 'N/A')}<br/>"
            f"{customer.get('address', '')}<br/>"
            f"{customer.get('phone', '')}",
        ]
        bill_to_text = bill_to_parts[0]

        bill_to_text += (
            f"<br/><br/>"
            f"<b>Invoice Number:</b> {invoice_num}<br/>"
            f"<b>Date:</b> {date_str}<br/>"
            f"<b>Payment Terms:</b> {invoice_data.get('payment_terms', 'Due on Receipt')}"
        )

        if location:
            bill_to_text += f"<br/><b>Project Location:</b> {location}"

        # Right side: From (contractor)
        from_info = (
            f"<b>From:</b><br/>"
            f"{contractor.get('company_name', 'N/A')}<br/>"
            f"{contractor.get('owner_name', '')}<br/>"
            f"{contractor.get('address', '')}<br/>"
            f"{contractor.get('phone', '')} | {contractor.get('email', '')}"
        )

        info_table = Table(
            [[
                Paragraph(bill_to_text, self.styles["InfoText"]),
                Paragraph(from_info, self.styles["InfoText"]),
            ]],
            colWidths=[3.5 * inch, 3.5 * inch],
        )
        info_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(info_table)

        elements.append(Spacer(1, 16))

        # ---- Items Table ----
        elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor("#1a365d"),
        ))
        elements.append(Spacer(1, 8))

        # Table header
        items = invoice_data.get("items", [])
        table_data = [["#", "Item", "Category", "Qty", "Unit", "Unit Price", "Total"]]

        for i, item in enumerate(items, 1):
            qty = item.get("quantity", 0)
            qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"
            table_data.append([
                str(i),
                item.get("item_name", "N/A"),
                item.get("category", ""),
                qty_str,
                item.get("unit", "each"),
                f"${item.get('unit_price', 0):.2f}",
                f"${item.get('total', 0):.2f}",
            ])

        item_table = Table(
            table_data,
            colWidths=[0.4 * inch, 2.2 * inch, 1.0 * inch, 0.6 * inch, 0.7 * inch, 0.9 * inch, 1.0 * inch],
        )

        item_table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            # Body
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            # Alternating rows
            *[
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7fafc"))
                for i in range(2, len(table_data), 2)
            ],
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 12))

        # ---- Totals Section ----
        subtotal = invoice_data.get("subtotal", 0.0)
        tax_rate = invoice_data.get("tax_rate", 0.0)
        tax_amount = invoice_data.get("tax_amount", 0.0)
        total = invoice_data.get("total", 0.0)

        totals_data = [
            ["", "", "Subtotal:", f"${subtotal:.2f}"],
            ["", "", f"Tax ({tax_rate:.1f}%):", f"${tax_amount:.2f}"],
            ["", "", "TOTAL:", f"${total:.2f}"],
        ]

        totals_table = Table(
            totals_data,
            colWidths=[2.5 * inch, 2 * inch, 1.2 * inch, 1.1 * inch],
        )
        totals_table.setStyle(TableStyle([
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            # Total row highlight
            ("BACKGROUND", (2, 2), (-1, 2), colors.HexColor("#1a365d")),
            ("TEXTCOLOR", (2, 2), (-1, 2), colors.white),
            ("FONTNAME", (2, 2), (-1, 2), "Helvetica-Bold"),
            ("FONTSIZE", (2, 2), (-1, 2), 12),
            ("TOPPADDING", (2, 2), (-1, 2), 6),
            ("BOTTOMPADDING", (2, 2), (-1, 2), 6),
        ]))
        elements.append(totals_table)

        # ---- Notes Section ----
        notes = invoice_data.get("notes", "")
        if notes:
            elements.append(Spacer(1, 20))
            elements.append(Paragraph("Notes:", self.styles["SectionHeader"]))
            elements.append(Paragraph(notes, self.styles["InfoText"]))

        # ---- Footer ----
        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(
            width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"),
        ))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(
            "Generated by Invoice Generator – AI-Powered Smart Invoice System",
            ParagraphStyle(
                name="Footer",
                parent=self.styles["Normal"],
                fontSize=7,
                textColor=colors.HexColor("#a0aec0"),
                alignment=1,  # Center
            ),
        ))

        # Build PDF
        doc.build(elements)
        logger.info(f"Invoice PDF generated: {filepath}")
        return filepath


# Global PDF generator instance
pdf_generator = InvoicePDFGenerator()
