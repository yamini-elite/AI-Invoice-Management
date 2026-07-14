from app.ocr.extractor import extract_invoice_data

result = extract_invoice_data("invoice.png")

print("Invoice Number:", result["invoice_number"])
print("Vendor Name:", result["vendor_name"])
print("Invoice Date:", result["invoice_date"])
print("Total Amount:", result["total_amount"])
print("GST Amount:", result["gst_amount"])