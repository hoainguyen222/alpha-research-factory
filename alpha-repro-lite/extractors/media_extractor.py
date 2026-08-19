"""
====================================================================================================
MODULE: Image Full-Text Transcriber & Visual OCR Extractor
FILE: extractors/media_extractor.py
====================================================================================================
CHỨC NĂNG (THEO YÊU CẦU ĐỌC NGUỒN => TEXT 100%):
1. Đọc và trích xuất TOÀN BỘ văn bản xuất hiện trong hình ảnh (Đoạn văn, bài báo, tài liệu scan, biểu đồ, công thức):
   - Engine 1 (Mặc định & 100% Offline): RapidOCR (ONNX Neural OCR) - nhận diện chính xác từng từ, dòng, đoạn văn.
   - Engine 2 (Tùy chọn khi có API Key): Gemini 1.5 Flash Vision API (trích xuất văn bản có cấu trúc cao).
   - Engine 3 (Fallback): Tesseract OCR.
2. Tự động nâng cao chất lượng ảnh qua MediaEnhancer trước khi nhận diện (Super-scaling, Auto-contrast, Unsharp Mask).
3. Sắp xếp các khối văn bản theo tọa độ không gian (Top-to-Bottom, Left-to-Right) đảm bảo tính liền mạch của đoạn văn.
====================================================================================================
"""

import io
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Tuple
from PIL import Image
import numpy as np

from bypass.media_enhancer import MediaEnhancer


class MediaExtractor:
    """Module trích xuất toàn bộ văn bản từ hình ảnh (Verbatim Full-Text OCR)."""

    _rapid_ocr_engine = None

    @classmethod
    def _get_rapid_ocr(cls):
        """Khởi tạo một lần (Singleton) cho engine RapidOCR."""
        if cls._rapid_ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                cls._rapid_ocr_engine = RapidOCR()
            except Exception as e:
                print(f"[OCR] RapidOCR initialization warning: {e}")
        return cls._rapid_ocr_engine

    @classmethod
    def _extract_via_gemini_vision(cls, image_bytes: bytes, mime_type: str = "image/png") -> Optional[str]:
        """Trích xuất toàn bộ văn bản qua Gemini Vision nếu có API Key."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = (
                "You are an expert OCR transcription assistant. "
                "Transcribe ALL visible text, paragraphs, numbers, tables, formulas, and labels in this image EXACTLY and COMPLETELY. "
                "Do not summarize. Do not skip any sentence or word. Output the verbatim extracted text."
            )
            response = model.generate_content([
                prompt,
                {"mime_type": mime_type, "data": image_bytes}
            ])
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"[OCR] Gemini Vision error: {e}")
        return None

    @classmethod
    def _extract_via_rapid_ocr(cls, img_pil: Image.Image) -> Tuple[str, Dict[str, Any]]:
        """Trích xuất toàn văn bản qua RapidOCR."""
        engine = cls._get_rapid_ocr()
        if not engine:
            return "", {"engine": "RapidOCR not available"}

        img_np = np.array(img_pil)
        ocr_result, elapse_list = engine(img_np)

        if not ocr_result:
            return "", {"detected_boxes": 0, "engine": "RapidOCR (No text detected)"}

        # ocr_result có dạng: [[[box_coords], "text", confidence], ...]
        # Sắp xếp các khối văn bản theo tọa độ Y (từ trên xuống dưới) rồi theo X (từ trái sang phải)
        sorted_blocks = sorted(ocr_result, key=lambda item: (item[0][0][1], item[0][0][0]))

        lines = []
        confidences = []
        for box, text_str, score in sorted_blocks:
            clean_t = text_str.strip()
            if clean_t:
                lines.append(clean_t)
                confidences.append(score)

        full_text = "\n".join(lines)
        avg_conf = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

        return full_text, {
            "engine": "RapidOCR ONNX Engine",
            "detected_lines": len(lines),
            "average_confidence": avg_conf,
            "elapse_seconds": sum(elapse_list) if isinstance(elapse_list, list) else elapse_list
        }

    @classmethod
    def extract_from_image(cls, image_input: Union[str, Path, bytes], filename: str = "image.png") -> Dict[str, Any]:
        """
        Đọc và trích xuất TOÀN BỘ văn bản từ file ảnh hoặc bytes.
        """
        try:
            if isinstance(image_input, Image.Image):
                raw_img = image_input
                buf = io.BytesIO()
                raw_img.save(buf, format="PNG")
                raw_bytes = buf.getvalue()
            elif isinstance(image_input, bytes):
                raw_bytes = image_input
                raw_img = Image.open(io.BytesIO(image_input))
            else:
                with open(image_input, "rb") as f:
                    raw_bytes = f.read()
                raw_img = Image.open(str(image_input))

            orig_w, orig_h = raw_img.size
            title = Path(filename).stem

            # 1. Nâng cao chất lượng ảnh thông qua MediaEnhancer
            enhanced_img = MediaEnhancer.enhance_image_for_ocr(raw_img)

            # 2. Thử OCR thông qua Gemini Vision (nếu có API Key)
            extracted_text = cls._extract_via_gemini_vision(raw_bytes)
            ocr_method = "Gemini 1.5 Flash Vision (Verbatim OCR)"

            # 3. Nếu không có Gemini API, sử dụng RapidOCR cục bộ
            if not extracted_text:
                extracted_text, ocr_meta = cls._extract_via_rapid_ocr(enhanced_img)
                ocr_method = ocr_meta.get("engine", "RapidOCR Engine")

            # 4. Nếu vẫn trống, thử Tesseract OCR
            if not extracted_text:
                try:
                    import pytesseract
                    tess_text = pytesseract.image_to_string(enhanced_img, lang="eng+vie")
                    if tess_text.strip():
                        extracted_text = tess_text.strip()
                        ocr_method = "Tesseract OCR Engine"
                except Exception:
                    pass

            # 5. Định dạng văn bản hoàn chỉnh
            if not extracted_text:
                extracted_text = "[IMAGE OCR COMPLETED - NO TEXT OR CHARACTERS DETECTED IN THE PROVIDED IMAGE]"

            return {
                "title": f"Image Document: {title}",
                "text": extracted_text,
                "metadata": {
                    "filename": filename,
                    "resolution": f"{orig_w}x{orig_h}",
                    "enhanced_resolution": f"{enhanced_img.size[0]}x{enhanced_img.size[1]}",
                    "ocr_engine": ocr_method,
                    "character_count": len(extracted_text),
                    "word_count": len(extracted_text.split())
                },
                "extraction_method": ocr_method,
                "bypass_status": "Enhanced (LANCZOS + AutoContrast + Neural OCR)"
            }

        except Exception as e:
            return {
                "title": Path(filename).stem,
                "text": f"[IMAGE TEXT EXTRACTION ERROR]: {str(e)}",
                "metadata": {"error": str(e)},
                "extraction_method": "Image Extraction Error",
                "bypass_status": "Failed"
            }
