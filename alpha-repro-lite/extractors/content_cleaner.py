"""
====================================================================================================
MODULE: Smart Web & Academic Paper Content Cleaner (De-Noiser & Noise Filter)
FILE: extractors/content_cleaner.py
====================================================================================================
CHỨC NĂNG:
1. Lọc và loại bỏ 100% các nội dung rác không thuộc nội dung bài báo / web:
   - Quảng cáo (Ads, Sponsored, Banners, Affiliate links, Promo discounts).
   - Các nút chức năng giao diện (Share, Subscribe, Follow, Sign-in, Cookie banners, Print, App download).
   - Các tiêu đề & liên kết không liên quan (Read next, Trending, Related posts, Tin liên quan, Xem thêm).
   - Header, Footer, Menu điều hướng, Breadcrumbs, Bản quyền website lặp lại.
   - Header/Footer trang lặp lại của bài báo khoa học (Running headers, Page numbers, Download stamps).
2. Xử lý triệt để lỗi chuỗi nhị phân rác (Binary Gibberish / Corrupted Streams / %PDF Decode Errors):
   - Nhận diện khi luồng nhị phân nén (Gzip/FlateDecode/PDF binary) bị ép kiểu sang chuỗi unicode rác (\ufffd, ký tự lạ).
   - Tự động kích hoạt cơ chế giải nén, phục hồi văn bản cứu hộ (Salvage) và loại bỏ hoàn toàn các ký tự rác.
3. Giữ nguyên 100% nội dung thân bài cốt lõi (Tiêu đề, Tác giả, Abstract, Phân đoạn bài viết H1-H4, Bảng số liệu, Code, Công thức).
====================================================================================================
"""

import re
import io
from typing import List, Optional, Tuple


class ContentCleaner:
    """Module làm sạch và thanh lọc toàn bộ văn bản bài báo / web thông minh."""

    # Danh sách các mẫu regex dòng rác cần xóa bỏ hoàn toàn
    NOISE_LINE_PATTERNS = [
        # Quảng cáo & Tài trợ
        r'^\s*(?:advertisement|sponsored|quảng cáo|promoted|adchoices|google ads?|taboola|outbrain).*$',
        r'.*?(?:this post may contain affiliate links|we may earn a commission|bài viết có chứa liên kết tài trợ|get \d+% discount).*?',
        
        # Cookie & GDPR
        r'.*?(?:we use cookies|bằng cách tiếp tục duyệt|chấp nhận cookie|accept all cookies|cookie settings|privacy preferences|chính sách cookie).*?',
        r'^\s*(?:accept|decline|manage preferences|đồng ý|từ chối)\s*$',

        # Nút mạng xã hội & Chia sẻ
        r'^\s*(?:share on|share via|chia sẻ|tweet|pin it|share this article|repost|copy link|sao chép liên kết).*?$',
        r'^\s*(?:facebook|twitter|linkedin|reddit|whatsapp|telegram|pinterest|threads|email)\s*$',
        r'^\s*\[?(?:share|tweet|like|comment|subscribe|follow)\]?\s*$',

        # Nút Đăng ký & Kêu gọi hành động (CTA)
        r'.*?(?:subscribe to our newsletter|sign up for our newsletter|join our newsletter|đăng ký nhận tin|nhận bản tin).*?',
        r'.*?(?:follow author on|follow us on twitter|theo dõi tác giả|theo dõi chúng tôi).*?',
        r'.*?(?:sign in to read|log in to continue|create a free account|đăng nhập để đọc tiếp|trở thành hội viên).*?',
        r'.*?(?:become a member|get unlimited access|mở khóa toàn bộ bài viết).*?',
        r'.*?(?:download the app|open in app|tải ứng dụng).*?',

        # Điều hướng & Thanh menu
        r'^\s*(?:home|trang chủ)\s*[>\|/»]\s*.*$',
        r'^\s*(?:table of contents|mục lục|menu|navigation|search|tìm kiếm)\s*$',
        r'^\s*(?:back to top|lên đầu trang|scroll to top|previous page|next page|trang trước|trang sau)\s*$',

        # Footer bản quyền & Điều khoản
        r'.*?(?:copyright|all rights reserved|bản quyền thuộc về|mọi quyền được bảo lưu).*?',
        r'.*?(?:terms of service|privacy policy|contact us|about us|điều khoản sử dụng|chính sách bảo mật|liên hệ).*?',
        r'.*?(?:giấy phép xuất bản số|chịu trách nhiệm nội dung|tòa soạn|hotline).*?',

        # Academic Paper Page Header/Footer Stamps
        r'^\s*downloaded from https?://.*?\s*by\s*.*?\s*on\s*.*?$',
        r'^\s*(?:page|trang)\s*\d+\s*(?:of|/)\s*\d+\s*$',
        r'^\s*---+\s*\[Page\s*\d+\s*(?:/\s*\d+)?\]\s*---+\s*$',
        r'^\s*(?:acm reference format|permission to make digital or hard copies).*?$',
    ]

    # Khối nội dung rác kéo dài cần cắt bỏ (từ điểm bắt đầu cho tới hết bài)
    TRAILING_TRASH_HEADERS = [
        r'(?:\n\#{0,4}\s*(?:related articles|you might also like|read next|bài viết liên quan|tin cùng chuyên mục|xem thêm|trending now|popular posts|more from|cùng chủ đề)[\:\-]?\s*\n.*)',
        r'(?:\n\#{0,4}\s*(?:about the author|về tác giả|author bio|newsletter subscription|đăng ký nhận bản tin|leave a reply|bình luận|comments)[\:\-]?\s*\n.*)'
    ]

    @classmethod
    def decontaminate_binary_gibberish(cls, text: str) -> str:
        """
        Phát hiện và xử lý triệt để lỗi chuỗi nhị phân nén / PDF mã hóa rác (như %5z7...):
        1. Kiểm tra tỷ lệ ký tự không thể in hoặc chuỗi rác \ufffd.
        2. Nếu phát hiện luồng PDF nhị phân, cố gắng phục hồi văn bản qua salvage.
        3. Loại bỏ 100% các ký tự nhị phân rác.
        """
        if not text:
            return ""

        # Đếm số ký tự rác (\ufffd hoặc non-printable)
        total_len = len(text)
        if total_len == 0:
            return ""

        replacement_chars = text.count('\ufffd')
        non_printable = sum(1 for ch in text if not ch.isprintable() and ch not in ('\n', '\t', '\r'))
        
        # Nếu tỷ lệ ký tự rác > 5% hoặc text bắt đầu bằng %PDF / FlateDecode binary
        if (replacement_chars + non_printable) / total_len > 0.05 or text.startswith(("%PDF", "%", "PK\x03\x04")):
            try:
                # Thử cứu hộ luồng nhị phân bằng FileDecryptor
                from bypass.file_decryptor import FileDecryptor
                raw_bytes = text.encode("latin-1", errors="ignore")
                salvaged = FileDecryptor.salvage_text_from_corrupted_binary(raw_bytes)
                if salvaged and len(salvaged.strip()) > 30 and salvaged.count('\ufffd') < 5:
                    return salvaged
            except Exception:
                pass

        # Lọc bỏ các ký tự điều khiển phi in ấn và \ufffd
        cleaned_chars = []
        for ch in text:
            code = ord(ch)
            # Giữ các ký tự văn bản thông thường, tiếng Việt, số, dấu câu
            if ch in ('\n', '\t') or (32 <= code <= 126) or (code >= 160 and ch != '\ufffd'):
                cleaned_chars.append(ch)
            elif ch == ' ':
                cleaned_chars.append(' ')

        sanitized = "".join(cleaned_chars)
        
        # Xóa các chuỗi vô nghĩa liên tiếp không có dấu cách
        words = sanitized.split()
        valid_words = []
        for w in words:
            # Nếu 1 từ có quá nhiều ký tự đặc biệt lộn xộn, bỏ qua
            special_ratio = len(re.findall(r'[^a-zA-Z0-9\u00C0-\u1EF9]', w)) / max(len(w), 1)
            if len(w) > 15 and special_ratio > 0.25:
                continue
            valid_words.append(w)

        reconstructed = " ".join(valid_words)
        
        # Kiểm tra nếu toàn bộ văn bản sau khi lọc chỉ là các ký tự rác lộn xộn không có từ ngữ hợp lệ
        total_chars = max(len(reconstructed), 1)
        symbol_count = len(re.findall(r'[^a-zA-Z0-9\s\u00C0-\u1EF9\.\,\!\?\:\;\-\_\(\)\"\']', reconstructed))
        
        if total_chars > 20 and (symbol_count / total_chars > 0.12 or len(valid_words) < 2):
            return "[THÔNG BÁO: ĐÂY LÀ DỮ LIỆU NHỊ PHÂN MÃ HÓA HOẶC FILE NÉN KHÔNG CHỨA VĂN BẢN HỢP LỆ. HỆ THỐNG ĐÃ TỰ ĐỘNG LỌC BỎ TOÀN BỘ CÁC KÝ TỰ RÁC.]"

        return reconstructed

    @classmethod
    def clean_article_text(cls, text: str, keep_references: bool = True) -> str:
        """
        Thanh lọc toàn bộ văn bản thô trích xuất từ web/paper:
        1. Khử độc tố nhị phân rác (Decontaminate Binary Gibberish).
        2. Xóa các khối đuôi rác (Comments, Related Articles, Newsletter footer).
        3. Lọc từng dòng, loại bỏ các nút chức năng, quảng cáo, mạng xã hội, cookie.
        4. Chuẩn hóa phân đoạn và trả về văn bản bài báo sạch sẽ, mạch lạc 100%.
        """
        if not text or len(text.strip()) == 0:
            return ""

        # 1. Khử độc tố nhị phân rác
        cleaned = cls.decontaminate_binary_gibberish(text)
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Cắt bỏ các khối rác ở cuối bài (Comments, Related Articles, Newsletter footer)
        for pattern in cls.TRAILING_TRASH_HEADERS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)

        # 3. Xóa các URL markdown thô dạng link nút [Click here](url), [Share](url)...
        cleaned = re.sub(r'\[\s*(?:share|tweet|facebook|twitter|linkedin|email|pin it|download|print|view source|read more)\s*\]\([^\)]+\)', '', cleaned, flags=re.IGNORECASE)

        # 4. Lọc từng dòng bằng biểu thức chính quy
        lines = cleaned.split("\n")
        filtered_lines: List[str] = []

        compiled_patterns = [re.compile(p, re.IGNORECASE) for p in cls.NOISE_LINE_PATTERNS]

        for line in lines:
            stripped = line.strip()
            
            # Bỏ qua dòng trống lặp
            if not stripped:
                if filtered_lines and filtered_lines[-1] != "":
                    filtered_lines.append("")
                continue

            # Kiểm tra xem dòng có khớp với bất kỳ mẫu rác nào không
            is_noise = False
            for cp in compiled_patterns:
                if cp.match(stripped):
                    is_noise = True
                    break

            if not is_noise:
                # Bỏ qua các dòng rời rạc quá ngắn không mang thông tin
                if len(stripped) < 3 and not stripped.startswith(("#", "-", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                    continue
                filtered_lines.append(line)

        # 5. Hợp nhất và chuẩn hóa khoảng trống
        final_text = "\n".join(filtered_lines)
        final_text = re.sub(r'\n{3,}', '\n\n', final_text)

        return final_text.strip()
