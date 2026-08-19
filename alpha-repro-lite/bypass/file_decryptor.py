"""
====================================================================================================
MODULE: Encrypted & Restricted File Decryptor
FILE: bypass/file_decryptor.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 4 - PHẦN 3):
1. Tự động xử lý các file bị mã hóa, cài đặt mật khẩu hoặc bị khóa quyền (Permissions):
   - PDF Encrypted / Restricted: Thử danh sách mật khẩu mặc định/rỗng, gỡ bỏ khóa Copy/Print.
   - Word/Excel Protected: Bỏ qua khóa bảo vệ Read-Only bằng cách giải nén trực tiếp XML gốc.
2. Phục hồi văn bản thô từ file nhị phân bị hỏng (Corrupted File Text Salvage):
   - Quét luồng nhị phân (Binary Stream Salvage) tìm các khối văn bản UTF-8 / ASCII có nghĩa.
   - Tách lọc chuỗi `BT ... ET` (PDF text operators) và `xml` node nội dung.
====================================================================================================
"""

import io
import re
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import pypdf


class FileDecryptor:
    """Tác tử giải mã và phục hồi dữ liệu từ file bị mã hóa hoặc hạn chế."""

    # Danh mục mật khẩu phổ biến thường được đặt mặc định
    COMMON_PASSWORDS = [
        "", "123456", "1234", "admin", "password", "default", "guest", "user",
        "0000", "1111", "12345678", "test", "demo"
    ]

    @classmethod
    def unlock_pdf(cls, file_bytes: bytes) -> Tuple[Optional[pypdf.PdfReader], str, Dict[str, Any]]:
        """
        Tự động mở khóa file PDF bị mã hóa hoặc hạn chế quyền sao chép.
        """
        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)
            
            # Nếu file không bị mã hóa
            if not reader.is_encrypted:
                return reader, "Direct (Not Encrypted)", {"is_encrypted": False}

            # Nếu file bị mã hóa, thử danh sách mật khẩu
            for pwd in cls.COMMON_PASSWORDS:
                try:
                    res = reader.decrypt(pwd)
                    if res != 0: # 1: user password, 2: owner password
                        return reader, f"Password Dictionary Match ('{pwd if pwd else '<Empty>'}')", {
                            "is_encrypted": True,
                            "decrypted": True,
                            "password_used": pwd
                        }
                except Exception:
                    continue

        except Exception as e:
            pass

        return None, "Decryption Failed", {"is_encrypted": True, "decrypted": False}

    @classmethod
    def salvage_text_from_corrupted_binary(cls, file_bytes: bytes, min_length: int = 15) -> str:
        """
        Chiến lược cứu hộ: Quét trực tiếp các luồng văn bản ASCII và UTF-8 trong file bị hỏng.
        """
        salvaged_chunks = []

        # 1. Thử tìm kiếm luồng XML bên trong (dành cho file DOCX/XLSX/PPTX bị lỗi)
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for name in z.namelist():
                    if name.endswith(".xml"):
                        xml_content = z.read(name).decode("utf-8", errors="ignore")
                        # Trích xuất nội dung giữa các thẻ XML
                        clean_xml_text = re.sub(r'<[^>]+>', ' ', xml_content)
                        clean_xml_text = re.sub(r'\s+', ' ', clean_xml_text).strip()
                        if len(clean_xml_text) > 30:
                            salvaged_chunks.append(f"--- [Salvaged XML Stream: {name}] ---\n{clean_xml_text}")
        except Exception:
            pass

        # 2. Nếu là PDF hỏng, trích xuất text operators (chuỗi nằm trong dấu ngoặc đơn hoặc ngoặc nhọn)
        pdf_text_matches = re.findall(rb'\(([^\)\\]{4,})\)\s*T[jJ]', file_bytes)
        if pdf_text_matches:
            pdf_texts = []
            for b in pdf_text_matches:
                try:
                    txt = b.decode("utf-8", errors="ignore").strip()
                    if len(txt) > 3:
                        pdf_texts.append(txt)
                except Exception:
                    continue
            if pdf_texts:
                salvaged_chunks.append("--- [Salvaged PDF Text Streams] ---\n" + " ".join(pdf_texts))

        # 3. Quét chuỗi ký tự UTF-8 thông thường (chỉ giữ chuỗi có từ ngữ hợp lệ)
        if not salvaged_chunks:
            pattern = re.compile(rb'[\x20-\x7E\xC2-\xFD]{' + str(min_length).encode() + rb',}')
            matches = pattern.findall(file_bytes)
            extracted = []
            for m in matches:
                try:
                    s = m.decode("utf-8", errors="ignore").strip()
                    # Kiểm tra: Phải có ít nhất 2 từ hợp lệ và tỷ lệ ký tự đặc biệt thấp
                    words = [w for w in s.split() if len(w) >= 2 and re.match(r'^[a-zA-Z0-9\u00C0-\u1EF9\.\,\!\?\-\_]+$', w)]
                    special_ratio = len(re.findall(r'[^a-zA-Z0-9\s\u00C0-\u1EF9\.\,\!\?\:\;\-\_]', s)) / max(len(s), 1)
                    if len(words) >= 2 and special_ratio < 0.15:
                        extracted.append(s)
                except Exception:
                    continue
            if extracted:
                salvaged_chunks.append("--- [Salvaged Text Streams] ---\n" + "\n".join(extracted[:100]))

        return "\n\n".join(salvaged_chunks) if salvaged_chunks else "[NO RECOVERABLE TEXT FOUND IN CORRUPTED BINARY]"
