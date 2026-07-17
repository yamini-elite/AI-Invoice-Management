from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

import shutil
import os
from io import BytesIO

from openpyxl import Workbook

from app.database.db import get_connection
#from app.ocr.extractor import extract_invoice_data

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# ==========================
# HOME
# ==========================

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


# ==========================
# UPLOAD PAGE
# ==========================

@app.get("/upload")
def upload_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="upload.html"
    )


# ==========================
# OCR + REVIEW PAGE
# ==========================

@app.post("/upload")
async def upload_invoice(
    request: Request,
    file: UploadFile = File(...)
):
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "message": "OCR is disabled in cloud deployment."
        }
    )

# ==========================
# CONFIRM & SAVE
# ==========================

@app.post("/confirm-upload")
async def confirm_upload(
    request: Request,
    file_name: str = Form(...),
    file_path: str = Form(...),
    invoice_number: str = Form(...),
    vendor_name: str = Form(...),
    invoice_date: str = Form(...),
    total_amount: str = Form(...),
    gst_amount: str = Form(...)
):

    conn = get_connection()
    cursor = conn.cursor()

    # Check duplicate invoice

    cursor.execute(
        """
        SELECT id
        FROM invoices
        WHERE invoice_number = %s
        """,
        (invoice_number,)
    )

    existing = cursor.fetchone()

    if invoice_number and existing:

        cursor.close()
        conn.close()

        return templates.TemplateResponse(
    request=request,
    name="error.html",
    context={
        "message": f"Duplicate invoice detected. Invoice Number {invoice_number} already exists."
    }
)

    # Insert only if unique

    sql = """
    INSERT INTO invoices
    (
        file_name,
        file_path,
        invoice_number,
        vendor_name,
        invoice_date,
        total_amount,
        gst_amount
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        file_name,
        file_path,
        invoice_number,
        vendor_name,
        invoice_date,
        total_amount,
        gst_amount
    )

    cursor.execute(sql, values)

    conn.commit()

    cursor.close()
    conn.close()

    return RedirectResponse(
        url="/repository",
        status_code=303
    )


# ==========================
# REPOSITORY
# ==========================
@app.get("/repository")
def repository(request: Request):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Statistics

    cursor.execute("SELECT COUNT(*) AS total FROM invoices")
    total_invoices = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS today_count
        FROM invoices
        WHERE DATE(uploaded_at) = CURDATE()
    """)
    today_uploads = cursor.fetchone()["today_count"]

    cursor.execute("""
        SELECT COUNT(*) AS ocr_count
        FROM invoices
        WHERE invoice_number IS NOT NULL
    """)
    ocr_processed = cursor.fetchone()["ocr_count"]

    cursor.execute("""
        SELECT COALESCE(SUM(total_amount),0) AS total_value
        FROM invoices
    """)
    total_value = cursor.fetchone()["total_value"]

    cursor.execute("""
        SELECT COALESCE(AVG(total_amount),0) AS avg_value
        FROM invoices
    """)
    avg_value = cursor.fetchone()["avg_value"]

    cursor.execute("""
        SELECT COALESCE(MAX(total_amount),0) AS max_value
        FROM invoices
    """)
    max_value = cursor.fetchone()["max_value"]

    cursor.execute("""
        SELECT COALESCE(MIN(total_amount),0) AS min_value
        FROM invoices
    """)
    min_value = cursor.fetchone()["min_value"]

    cursor.execute("""
        SELECT COUNT(DISTINCT vendor_name) AS vendor_count
        FROM invoices
        WHERE vendor_name IS NOT NULL
    """)
    vendor_count = cursor.fetchone()["vendor_count"]

    # Invoice Trend

    cursor.execute("""
        SELECT
            DATE(uploaded_at) AS day,
            COALESCE(SUM(total_amount),0) AS amount
        FROM invoices
        GROUP BY DATE(uploaded_at)
        ORDER BY day
    """)
    invoice_trend = cursor.fetchall()
    invoice_trend = [
    {
        "day": str(row["day"]),
        "amount": float(row["amount"])
    }
    for row in invoice_trend
]

    # Invoice List

    cursor.execute("""
        SELECT *
        FROM invoices
        ORDER BY id DESC
    """)
    invoices = cursor.fetchall()

    # Top Vendors

    cursor.execute("""
        SELECT
            vendor_name,
            COUNT(*) AS invoice_count,
            COALESCE(SUM(total_amount),0) AS total_spend
        FROM invoices
        WHERE vendor_name IS NOT NULL
        GROUP BY vendor_name
        ORDER BY total_spend DESC
        LIMIT 10
    """)
    top_vendors = cursor.fetchall()

    # Phase 6B
    top_vendor_spend = [
        {
            "vendor": row["vendor_name"],
            "spend": float(row["total_spend"])
        }
        for row in top_vendors
    ]

    cursor.execute("""
        SELECT
            vendor_name,
            COALESCE(SUM(total_amount),0) AS total_spend
        FROM invoices
        WHERE vendor_name IS NOT NULL
        GROUP BY vendor_name
        ORDER BY total_spend DESC
    """)

    vendor_spend = cursor.fetchall()

    vendor_spend = [
        {
            "vendor": row["vendor_name"],
            "spend": float(row["total_spend"])
        }
        for row in vendor_spend
    ]

    # Phase 6C
    cursor.execute("""
        SELECT
            COALESCE(SUM(gst_amount), 0) AS total_gst,
            COALESCE(AVG(gst_amount), 0) AS avg_gst,
            COALESCE(MAX(gst_amount), 0) AS max_gst,
            COALESCE(MIN(gst_amount), 0) AS min_gst
        FROM invoices
    """)
    gst_statistics = cursor.fetchone()

    # Phase 6D
    cursor.execute("""
        SELECT
            DATE(uploaded_at) AS day,
            COALESCE(SUM(gst_amount), 0) AS gst_amount
        FROM invoices
        GROUP BY DATE(uploaded_at)
        ORDER BY day
    """)
    gst_trend = [
        {
            "day": str(row["day"]),
            "gst_amount": float(row["gst_amount"])
        }
        for row in cursor.fetchall()
    ]

    # Phase 6E
    cursor.execute("""
        SELECT
            DATE_FORMAT(uploaded_at, '%Y-%m') AS month,
            COUNT(*) AS invoice_count
        FROM invoices
        GROUP BY DATE_FORMAT(uploaded_at, '%Y-%m')
        ORDER BY month
    """)
    monthly_upload_trend = [
        {
            "month": row["month"],
            "invoice_count": int(row["invoice_count"])
        }
        for row in cursor.fetchall()
    ]

    cursor.close()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="repository.html",
        context={
            "top_vendors": top_vendors,
            "top_vendor_spend": top_vendor_spend,
            "vendor_spend": vendor_spend,
            "invoice_trend": invoice_trend,
            "gst_trend": gst_trend,
            "monthly_upload_trend": monthly_upload_trend,
            "invoices": invoices,
            "total_invoices": total_invoices,
            "today_uploads": today_uploads,
            "ocr_processed": ocr_processed,
            "total_value": round(float(total_value), 2),
            "avg_value": round(float(avg_value), 2),
            "max_value": round(float(max_value), 2),
            "min_value": round(float(min_value), 2),
            "vendor_count": vendor_count,
            "total_gst": round(float(gst_statistics["total_gst"]), 2),
            "avg_gst": round(float(gst_statistics["avg_gst"]), 2),
            "max_gst": round(float(gst_statistics["max_gst"]), 2),
            "min_gst": round(float(gst_statistics["min_gst"]), 2)
        }
    )


# ==========================
# INVOICE DETAILS
# ==========================

@app.get("/invoice-details/{invoice_id}")
def invoice_details(request: Request, invoice_id: int):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            invoice_number,
            vendor_name,
            invoice_date,
            gst_amount,
            total_amount,
            uploaded_at
        FROM invoices
        WHERE id = %s
        """,
        (invoice_id,)
    )

    invoice = cursor.fetchone()

    cursor.close()
    conn.close()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return templates.TemplateResponse(
        request=request,
        name="invoice_details.html",
        context={"invoice": invoice}
    )


# ==========================
# EXCEL EXPORT
# ==========================

@app.get("/export-excel")
def export_excel():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            invoice_number,
            vendor_name,
            invoice_date,
            gst_amount,
            total_amount,
            uploaded_at
        FROM invoices
        ORDER BY id DESC
    """)

    invoices = cursor.fetchall()

    cursor.close()
    conn.close()

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Invoices"

    worksheet.append([
        "Invoice Number",
        "Vendor Name",
        "Invoice Date",
        "GST Amount",
        "Total Amount",
        "Upload Date"
    ])

    for invoice in invoices:
        worksheet.append([
            invoice["invoice_number"],
            invoice["vendor_name"],
            invoice["invoice_date"],
            float(invoice["gst_amount"]) if invoice["gst_amount"] is not None else None,
            float(invoice["total_amount"]) if invoice["total_amount"] is not None else None,
            invoice["uploaded_at"]
        ])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=invoices.xlsx"}
    )

# ==========================
# VIEW FILE
# ==========================

@app.get("/view/{invoice_id}")
def view_invoice(invoice_id: int):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT file_path FROM invoices WHERE id=%s",
        (invoice_id,)
    )

    invoice = cursor.fetchone()

    cursor.close()
    conn.close()

    if not invoice:
        return {"error": "Invoice not found"}

    return FileResponse(invoice["file_path"])


# ==========================
# DOWNLOAD FILE
# ==========================

@app.get("/download/{invoice_id}")
def download_invoice(invoice_id: int):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT file_name, file_path FROM invoices WHERE id=%s",
        (invoice_id,)
    )

    invoice = cursor.fetchone()

    cursor.close()
    conn.close()

    if not invoice:
        return {"error": "Invoice not found"}

    return FileResponse(
        path=invoice["file_path"],
        filename=invoice["file_name"],
        media_type="application/octet-stream"
    )


# ==========================
# DELETE FILE
# ==========================

@app.get("/delete/{invoice_id}")
def delete_invoice(invoice_id: int):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT file_path FROM invoices WHERE id=%s",
        (invoice_id,)
    )

    invoice = cursor.fetchone()

    if invoice:

        if os.path.exists(invoice["file_path"]):
            os.remove(invoice["file_path"])

        cursor.execute(
            "DELETE FROM invoices WHERE id=%s",
            (invoice_id,)
        )

        conn.commit()

    cursor.close()
    conn.close()

    return RedirectResponse(
        url="/repository",
        status_code=303
    )
