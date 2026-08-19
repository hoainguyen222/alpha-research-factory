"""
====================================================================================================
MODULE: Low-Quality Media Enhancer & OCR Optimizer
FILE: bypass/media_enhancer.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 4 - PHẦN 4):
1. Xử lý phục hồi hình ảnh kém chất lượng, mờ nhòe, thiếu tương phản:
   - Super-Resolution Upscaling (LANCZOS 2x/3x interpolation).
   - Auto-Contrast & Histogram Equalization (kéo dãn dải tương phản).
   - Unsharp Masking & Edge Sharpening (làm nét viền chữ và ký tự).
   - Binarization (tách chữ khỏi nền nhiều nhiễu).
2. Trích xuất và tối ưu hóa khung hình Video (Video Keyframe Enhancer) phục vụ OCR.
====================================================================================================
"""

import io
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np


class MediaEnhancer:
    """Tác tử nâng cao chất lượng hình ảnh và khung hình video phục vụ trích xuất dữ liệu."""

    @classmethod
    def enhance_image_for_ocr(cls, image_input: Any) -> Image.Image:
        """
        Quy trình xử lý ảnh đa tầng giúp phục hồi ảnh chất lượng kém trước khi OCR:
        1. Chuyển đổi RGB / Grayscale
        2. Phóng đại kích thước (Upscaling) nếu kích thước quá nhỏ
        3. Cân bằng tương phản (Auto-contrast)
        4. Tăng độ nét (Sharpening & Unsharp Mask)
        """
        if isinstance(image_input, (str, Path)):
            img = Image.open(image_input)
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, Image.Image):
            img = image_input.copy()
        else:
            raise ValueError("Unsupported image input type")

        # Đảm bảo hệ màu RGB
        if img.mode != "RGB":
            img = img.convert("RGB")

        # 1. Phóng đại nếu chiều rộng hoặc chiều cao nhỏ hơn 1200px
        width, height = img.size
        if width < 1200 or height < 1200:
            scale_factor = max(2.0, 1600.0 / max(width, height))
            new_size = (int(width * scale_factor), int(height * scale_factor))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # 2. Chuyển sang Grayscale (ảnh mức xám)
        gray = ImageOps.grayscale(img)

        # 3. Tự động cân bằng và mở rộng tương phản (Auto-contrast)
        gray = ImageOps.autocontrast(gray, cutoff=2)

        # 4. Tăng cường độ tương phản bổ sung
        enhancer = ImageEnhance.Contrast(gray)
        gray = enhancer.enhance(1.8)

        # 5. Làm nét viền chữ (Unsharp Mask filter)
        sharpened = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))

        return sharpened

    @classmethod
    def create_binary_image(cls, gray_image: Image.Image, threshold: int = 140) -> Image.Image:
        """Tạo ảnh nhị phân đen trắng (Binarization) giúp tách triệt để văn bản khỏi nền mờ."""
        return gray_image.point(lambda p: 255 if p > threshold else 0, mode='1')

    @classmethod
    def extract_image_bytes(cls, image: Image.Image, format: str = "PNG") -> bytes:
        """Xuất ảnh sang bytes phục vụ gửi API hoặc lưu file."""
        buf = io.BytesIO()
        image.save(buf, format=format)
        return buf.getvalue()
