import easyocr
import re
from datetime import datetime

reader = easyocr.Reader(['en'])

def extract_invoice_data(image_path):

    results = reader.readtext(image_path)

    text = " ".join([item[1] for item in results])

    # Invoice Number
    invoice_match = re.search(
        r'Invoice.*?([0-9]{6,})',
        text,
        re.IGNORECASE
    )

    invoice_number = (
        invoice_match.group(1)
        if invoice_match
        else None
    )

    # Vendor Name
    vendor_match = re.search(
        r'TAX INVOICE\s+(.*?)\s+Invoice',
        text,
        re.IGNORECASE
    )

    vendor_name = (
        vendor_match.group(1).strip()
        if vendor_match
        else None
    )

    # Invoice Date
    date_match = re.search(
        r'Invoice Date[:\s]*([0-9/.-]+)',
        text,
        re.IGNORECASE
    )

    invoice_date = None

    if date_match:
        try:
            invoice_date = datetime.strptime(
                date_match.group(1),
                "%m/%d/%Y"
            ).strftime("%Y-%m-%d")
        except:
            invoice_date = None

    # Total Amount
    total_match = re.search(
        r'TOTAL[:\s]*Rs\s*([0-9,.]+)',
        text,
        re.IGNORECASE
    )

    total_amount = (
        total_match.group(1)
        if total_match
        else None
    )

    # GST Amount
    sgst_match = re.search(
        r'SGST[:\s]*([0-9,.]+)',
        text,
        re.IGNORECASE
    )

    cgst_match = re.search(
        r'CGST[:\s]*([0-9,.]+)',
        text,
        re.IGNORECASE
    )

    gst_amount = 0.0

    if sgst_match:
        gst_amount += float(sgst_match.group(1))

    if cgst_match:
        gst_amount += float(cgst_match.group(1))

    return {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "invoice_date": invoice_date,
        "total_amount": total_amount,
        "gst_amount": gst_amount,
        "raw_text": text
    }
    allowed_extensions = [
    ".jpg",
    ".jpeg",
    ".png"
]

    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in allowed_extensions:
        return {
           "error": "Only JPG, JPEG and PNG supported currently"
    }