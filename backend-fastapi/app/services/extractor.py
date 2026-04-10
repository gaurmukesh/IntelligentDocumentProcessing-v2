import base64
import json
from pathlib import Path
from typing import Optional
from openai import OpenAI
import io

from app.core.config import settings
from app.models.document import DocumentType

client = OpenAI(api_key=settings.openai_api_key)


# ── File → base64 image ───────────────────────────────────────────

def file_to_base64(file_path: str) -> tuple[str, str]:
    """
    Returns (base64_string, media_type).
    For PDFs, converts first page to PNG image.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _pdf_first_page_to_base64(file_path)
    else:
        return _image_to_base64(file_path, ext)


def _image_to_base64(file_path: str, ext: str) -> tuple[str, str]:
    """
    Resize large phone/scanner images to max 2048px on longest side before encoding.
    GPT-4o Vision detail='high' tiles at 512px — oversized images waste tokens without
    improving accuracy, and can actually hurt OCR on small text.
    """
    from PIL import Image as PILImage
    import io
    img = PILImage.open(file_path)
    # Rotate based on EXIF orientation (phone photos are often sideways)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    # Resize if larger than 2048px on longest side
    max_side = 2048
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/png"


def _pdf_first_page_to_base64(file_path: str) -> tuple[str, str]:
    """Extract first page of PDF and convert to PNG base64 using PyMuPDF."""
    import fitz  # PyMuPDF — no system deps required
    doc = fitz.open(file_path)
    if doc.page_count == 0:
        raise ValueError("PDF has no pages")
    page = doc[0]
    # 3x zoom ≈ 216 DPI — sharper digits, reduces OCR misreads
    mat = fitz.Matrix(3, 3)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(png_bytes).decode("utf-8"), "image/png"


# ── GPT-4o Vision call ────────────────────────────────────────────

def _call_vision(system_prompt: str, user_prompt: str,
                 image_b64: str, media_type: str) -> dict:
    """Call GPT-4o with an image and return parsed JSON."""

    # GPT-4o supports PDF natively if media_type is application/pdf
    if media_type == "application/pdf":
        image_content = {
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{image_b64}"}
        }
    else:
        image_content = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{image_b64}",
                "detail": "high"
            }
        }

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                image_content
            ]}
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=2500,
    )
    content = response.choices[0].message.content
    if content is None:
        finish_reason = response.choices[0].finish_reason
        raise ValueError(f"OpenAI returned no content (finish_reason={finish_reason!r}). "
                         "Response may have been truncated or filtered.")
    return json.loads(content)


# ── 10th Marksheet extractor ──────────────────────────────────────

SYSTEM_10TH = """You are an expert at extracting structured data from Indian 10th grade (Class 10/SSC/SSLC/Matriculation) marksheets and certificates.
Extract all fields accurately. For each field, provide a confidence score (0.0 to 1.0) based on how clearly the information is visible.
If a field is not visible or unclear, set value to null and confidence to 0.0.
IMPORTANT for dates: CBSE marksheets print the date in both numeric form (e.g. 20/01/2004) AND spelled out in words (e.g. 20TH JANUARY TWO THOUSAND FOUR).
Always read the spelled-out words version first to determine the correct month, then confirm against the numeric form.
JANUARY=01, FEBRUARY=02, MARCH=03, APRIL=04, MAY=05, JUNE=06, JULY=07, AUGUST=08, SEPTEMBER=09, OCTOBER=10, NOVEMBER=11, DECEMBER=12.
If the spelled-out words say JANUARY, the month must be 01 — even if the numeric digits look ambiguous.
Always respond with valid JSON only."""

USER_10TH = """Extract the following information from this 10th marksheet image and return as JSON:
{
  "student_name": {"value": "<full name>", "confidence": 0.0},
  "date_of_birth_raw": {"value": "<exact string as printed on the document, e.g. '20-01-2004' or '20/01/2004'>", "confidence": 0.0},
  "date_of_birth": {"value": "<DD/MM/YYYY — parsed from date_of_birth_raw, do not change the digits>", "confidence": 0.0},
  "school_name": {"value": "<school name>", "confidence": 0.0},
  "board": {"value": "<CBSE|ICSE|State Board name>", "confidence": 0.0},
  "exam_year": {"value": "<YYYY>", "confidence": 0.0},
  "roll_number": {"value": "<roll number>", "confidence": 0.0},
  "subjects": [
    {"name": "<subject>", "marks_obtained": "<marks>", "max_marks": "<max>", "confidence": 0.0}
  ],
  "total_marks_obtained": {"value": "<total>", "confidence": 0.0},
  "total_max_marks": {"value": "<max>", "confidence": 0.0},
  "percentage": {"value": "<XX.XX>", "confidence": 0.0},
  "result": {"value": "<PASS|FAIL>", "confidence": 0.0},
  "grade": {"value": "<grade if available>", "confidence": 0.0}
}"""


def extract_10th_marksheet(file_path: str) -> dict:
    image_b64, media_type = file_to_base64(file_path)
    return _call_vision(SYSTEM_10TH, USER_10TH, image_b64, media_type)


# ── 12th Marksheet extractor ──────────────────────────────────────

SYSTEM_12TH = """You are an expert at extracting structured data from Indian 12th grade (Class 12/HSC/Intermediate/Plus Two) marksheets and certificates.
Extract all fields accurately. For each field, provide a confidence score (0.0 to 1.0) based on how clearly the information is visible.
If a field is not visible or unclear, set value to null and confidence to 0.0.
For stream: infer from subjects if not printed (Physics/Chemistry/Maths/Biology → Science; Accountancy/Business Studies/Economics → Commerce; History/Geography/Political Science → Arts).
For total_marks_obtained and total_max_marks: sum only the main theory subjects (exclude internal assessments like Work Experience, Health Education, General Studies).
For percentage: use the printed value if available; otherwise calculate from total_marks_obtained/total_max_marks × 100.
CBSE marksheets may not print date_of_birth — set to null with confidence 0.0 if absent.
Always respond with valid JSON only."""

USER_12TH = """Extract the following information from this 12th marksheet image and return as JSON:
{
  "student_name": {"value": "<full name>", "confidence": 0.0},
  "date_of_birth": {"value": "<DD/MM/YYYY or null if not on marksheet>", "confidence": 0.0},
  "school_name": {"value": "<school name>", "confidence": 0.0},
  "board": {"value": "<CBSE|ICSE|State Board name>", "confidence": 0.0},
  "stream": {"value": "<Science|Commerce|Arts|Vocational — infer from subjects if not printed>", "confidence": 0.0},
  "exam_year": {"value": "<YYYY>", "confidence": 0.0},
  "roll_number": {"value": "<roll number>", "confidence": 0.0},
  "subjects": [
    {"name": "<subject>", "marks_obtained": "<marks>", "max_marks": "<max>", "confidence": 0.0}
  ],
  "total_marks_obtained": {"value": "<sum of main theory subject marks>", "confidence": 0.0},
  "total_max_marks": {"value": "<sum of main theory subject max marks>", "confidence": 0.0},
  "percentage": {"value": "<XX.XX — printed or calculated>", "confidence": 0.0},
  "result": {"value": "<PASS|FAIL>", "confidence": 0.0},
  "grade": {"value": "<grade if available>", "confidence": 0.0}
}"""


def extract_12th_marksheet(file_path: str) -> dict:
    image_b64, media_type = file_to_base64(file_path)
    return _call_vision(SYSTEM_12TH, USER_12TH, image_b64, media_type)


# ── Aadhar Card extractor ─────────────────────────────────────────

SYSTEM_AADHAR = """You are an expert at extracting structured data from Indian Aadhar cards (UIDAI identity documents).
Extract all visible fields accurately. For the Aadhar number, only capture the last 4 digits (mask the rest as XXXX-XXXX-).
For each field, provide a confidence score (0.0 to 1.0).
If a field is not visible or unclear, set value to null and confidence to 0.0.
Always respond with valid JSON only."""

USER_AADHAR = """Extract the following information from this Aadhar card image and return as JSON:
{
  "full_name": {"value": "<full name as printed>", "confidence": 0.0},
  "date_of_birth": {"value": "<DD/MM/YYYY>", "confidence": 0.0},
  "gender": {"value": "<Male|Female|Other>", "confidence": 0.0},
  "aadhar_last4": {"value": "<last 4 digits only>", "confidence": 0.0},
  "address": {
    "value": "<full address as printed>",
    "confidence": 0.0
  },
  "is_front_side": {"value": "<true|false — whether this is the front side of Aadhar>", "confidence": 0.0}
}"""


def extract_aadhar(file_path: str) -> dict:
    image_b64, media_type = file_to_base64(file_path)
    return _call_vision(SYSTEM_AADHAR, USER_AADHAR, image_b64, media_type)


# ── Unified extractor ─────────────────────────────────────────────

def extract_document(file_path: str, doc_type: DocumentType) -> tuple[dict, float]:
    """
    Extract data from a document.
    Returns (extracted_data, overall_confidence_score).
    """
    if doc_type == DocumentType.MARKSHEET_10TH:
        data = extract_10th_marksheet(file_path)
    elif doc_type == DocumentType.MARKSHEET_12TH:
        data = extract_12th_marksheet(file_path)
    elif doc_type == DocumentType.AADHAR:
        data = extract_aadhar(file_path)
    else:
        raise ValueError(f"Unsupported document type: {doc_type}")

    confidence = _calculate_overall_confidence(data)
    return data, confidence


def _calculate_overall_confidence(data: dict) -> float:
    """Average confidence across all top-level fields (excluding lists)."""
    scores = []
    for key, val in data.items():
        if isinstance(val, dict) and "confidence" in val:
            scores.append(float(val["confidence"]))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "confidence" in item:
                    scores.append(float(item["confidence"]))
    return round(sum(scores) / len(scores), 3) if scores else 0.0
