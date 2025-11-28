import streamlit as st
import requests, base64, io
from PIL import Image  # pillow is already a dependency for pdf2image

# Data extracted from the IBM Watsonx.ai service
# Make sure to replace these with your actual credentials
API_KEY         = "NJLshxQ69XRcK_BpAIQHKiWllkZtGUK3eh2uUt16q-Rd" # Add the credentials mentioned in IBM watsonx.ai platform
PROJECT_ID      = "6344e97c-4a5a-4585-af06-e379c55b855b" # Add the credentials mentioned in IBM watsonx.ai platform
MODEL_ID        = "meta-llama/llama-3-2-90b-vision-instruct" # Add the model that you want to use from IBM watsonx.ai platform
IAM_URL         = "https://iam.cloud.ibm.com/identity/token" # Add the credentials mentioned in IBM watsonx.ai platform
WATSONX_API_URL = "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-03-29" # Add the credentials mentioned in IBM watsonx.ai platform

# Setup for Streamlit app
st.set_page_config(page_title="Handwriting Extractor", layout="centered")
st.title("📝 Invoice OCR Extractor")

uploaded_file = st.file_uploader(
    "Upload an image or PDF of the invoice",
    type=["png", "jpg", "jpeg", "pdf"],
)

# Prompt for Watsonx.ai powered Application running on Streamlit
# This is the instruction set for the AI model to extract structured data from invoices
PROMPT = """
You are **Invoice‑Vision**, a highly intelligent document parser trained to extract structured information from **both images and PDFs** of invoices — whether digitally printed or handwritten.

Your task is to return a clean, structured **Markdown-formatted output** that mirrors the logical and visual structure of the invoice, regardless of whether the input is a scanned PDF, a photographed page, or a digital image file.

---

##  OUTPUT INSTRUCTIONS

Always return the extracted data in the following **5-part format**:

---

### 1. Invoice Headers and Titles

- Use `#`, `##`, and line breaks to preserve the visual layout and grouping.
- Identify **handwritten content** using `**[HW] ... **`, e.g., `**[HW] June 6, 1950**`.
- If text is illegible or missing, write `[Unreadable]`.

---

### 2. Line Item Table

Render all invoice line items as a **Markdown table**.  
Use the following standard columns if present:

`Description | Qty | Unit Price | Subtotal | Tax | Total`

- Preserve the order, spacing, and numeric alignment of all rows and columns.
- If any column is missing (e.g., Tax or Total), include only the available ones.
- If multiple dates or entries are grouped, reflect that visually using empty cells or date rows.

Example:

---

### 3. Totals Summary

Below the table, group and display:
- Subtotal
- Tax
- Discount
- Grand Total
- Currency (if shown)
- Amount Paid / Due

Use the same layout and alignment as seen in the document.

---

### 4. Additional Key Fields

Accurately extract and label:

- **Invoice Number** (or Rx / Reference)
- **PO Number** (if present)
- **Invoice Date** / **Due Date**
- **Sender / Receiver Name and Address**
- **Payment Instructions** (Bank details, etc.)
- **Seal, Stamp or Signature** presence:
  - Format as: `**Seal/Signature:** Present` or `Absent`
  - If a visual indicator (e.g., logo) acts as a stamp, say: `**Stamp Detected**`

---

### 5. Metadata & Accuracy Report (always required)
Include this block **Return ‘OCR Confidence Score’ as an INTEGER from 0 to 100 (no % sign needed).
 **
 ### 5. Metadata & Accuracy Report (always required)

Include this block **Document Type: Prescription invoice <-- Invoice / Receipt / etc.
Language: English <-- primary language detected
Image Quality: Fair <-- Excellent / Good / Fair / Poor
Handwriting Legibility: Mostly legible <-- Clear / Mostly legible / Illegible
Confidence Level: Medium <-- High / Medium / Low
Detected Handwriting Regions: 5 <-- integer count
Printed Text Accuracy: High <-- High / Moderate / Low
Table Parsing Accuracy: Moderate <-- High / Moderate / Low
Formatting Retention Accuracy: High <-- High / Moderate / Low
Seal/Stamp Presence: Yes <-- Yes / No
Notes: Some handwritten sections are difficult to read, but most information is clear.** at the end of every response.
Fill each field with your best estimate, replacing the sample values.OCR Confidence Score: 88 <-- integer 0‑100 (no % sign)
 **
---

## IMPORTANT GUIDELINES

- Input can be a **PDF or image** — process both equally.
- Distinguish **handwritten** vs **printed** wherever possible.
- DO NOT add commentary, instructions, or extra explanations — return only the Markdown output.
- For **illegible sections**, use `[Unreadable]` to maintain clarity.
- For **multilingual invoices**, show original with translation in brackets if needed.

---

Your output must be professional, structured, and compatible with Markdown viewers — suitable for humans and automated post-processing alike.

"""

# ── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3000)
def get_iam_token(apikey: str) -> str:
    r = requests.post(
        IAM_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": apikey},
    )
    if r.status_code != 200:
        raise Exception("IAM token error: " + r.text)
    return r.json()["access_token"]


def pdf_first_page_to_png(pdf_bytes: bytes, dpi: int = 300) -> bytes:
    """
    Convert the first page of a PDF to PNG bytes.
    Tries pdf2image+Poppler first; falls back to PyMuPDF (fitz).
    """
    # 1️⃣ Attempt with pdf2image
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(
            pdf_bytes, dpi=dpi, fmt="png", first_page=1, last_page=1
        )
        if images:
            buf = io.BytesIO()
            images[0].save(buf, format="PNG")
            return buf.getvalue()
    except Exception as e:
        print("pdf2image path failed:", e)

    # 2️⃣ Fallback to PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    except Exception as e:
        raise RuntimeError(
            "Could not convert PDF to image.\n"
            "Install either pdf2image + Poppler or PyMuPDF (fitz).\n"
            f"Underlying error: {e}"
        )


def extract_text(image_bytes: bytes, token: str, mime_type: str) -> str:
    """Send image bytes to watsonx.ai and return extracted markdown text."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{b64}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "model_id": MODEL_ID,
        "project_id": PROJECT_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
    }

    resp = requests.post(WATSONX_API_URL, headers=headers, json=body)
    if resp.status_code != 200:
        raise Exception(f"Watsonx.ai error {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]

import re

def parse_confidence(markdown_text: str) -> int | None:
    """
    Look for '**OCR Confidence Score:** <number>' and return it as int (0‑100).
    Returns None if not found or out of range.
    """
    match = re.search(r"\*\*OCR Confidence Score:\*\*\s*([0-9]{1,3})", markdown_text)
    if match:
        val = int(match.group(1))
        if 0 <= val <= 100:
            return val
    return None


# ── Main flow ────────────────────────────────────────────────────────────────
if uploaded_file:
    file_bytes = uploaded_file.read()
    is_pdf = uploaded_file.type == "application/pdf"

    if is_pdf:
        # Convert first PDF page to PNG for preview and OCR
        try:
            preview_bytes = pdf_first_page_to_png(file_bytes)
        except RuntimeError as err:
            st.error(str(err))
            st.stop()

        st.image(
            preview_bytes,
            caption="📄 PDF preview (page 1)",
            use_container_width=True,
        )
        img_bytes = preview_bytes
        mime_type = "image/png"
    else:
        st.image(file_bytes, caption="📷 Uploaded image", use_container_width=True)
        img_bytes = file_bytes
        mime_type = uploaded_file.type  # png / jpeg

    with st.spinner("Running OCR…"):
        try:
            token = get_iam_token(API_KEY)
            extracted = extract_text(img_bytes, token, mime_type)
            st.success("✅ Done!")
            st.markdown("### Extracted Text")
            st.markdown(extracted)
            st.download_button("Download .txt", extracted, "handwritten.txt")
        except Exception as e:
            st.error(str(e))