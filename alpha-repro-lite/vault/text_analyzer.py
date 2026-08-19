"""
====================================================================================================
MODULE: Deep Text Semantic Analyzer & Executive Summarizer
FILE: vault/text_analyzer.py
====================================================================================================
CHỨC NĂNG:
1. Đọc và phân tích TOÀN BỘ nội dung văn bản trích xuất (Full Text) sau khi đã thu thập được từ nguồn.
2. Tạo bản "Tóm Tắt Nội Dung Cốt Lõi (Key Insights & Findings)" chuyên sâu, có cấu trúc:
   - 🎯 1. Chủ Đề & Mục Tiêu Nghiên Cứu (Research Context & Objective)
   - 💡 2. Các Luận Điểm & Phát Hiện Cốt Lõi (Core Insights & Key Findings)
   - 📊 3. Dữ Liệu Định Lượng, Công Thức & Tham Số (Quantitative Metrics & Parameters)
   - 🚀 4. Kết Luận & Giá Trị Ứng Dụng Thực Tiễn (Actionable Takeaways & Conclusions)
3. Hỗ trợ 2 chế độ:
   - Chế độ AI (Gemini 1.5 Flash Vision / LLM) khi có API Key: phân tích ngữ nghĩa sâu sắc.
   - Chế độ Thuần Local NLP (100% Offline): Phân tích cấu trúc phân đoạn, chấm điểm câu quan trọng (Sentence Scoring) và trích xuất chỉ số định lượng.
====================================================================================================
"""

import os
import re
import math
from typing import Dict, Any, Optional, List, Tuple


class TextAnalyzer:
    """Module phân tích toàn văn và tạo tóm tắt nội dung cốt lõi."""

    @classmethod
    def _summarize_via_gemini(cls, title: str, full_text: str, source_type: str) -> Optional[str]:
        """Phân tích toàn văn bằng Gemini AI nếu có API Key."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            prompt = f"""Bạn là một chuyên gia nghiên cứu & phân tích dữ liệu định lượng (Quant / Finance) hàng đầu.
Nhiệm vụ: Hãy đọc TOÀN BỘ bản văn bản trích xuất (Full Text) dưới đây từ nguồn [{source_type}] với tiêu đề "{title}".

**QUAN TRỌNG NHẤT (BỘ LỌC CHỦ ĐỀ):**
Trước tiên, hãy đánh giá xem nội dung văn bản này CÓ LIÊN QUAN đến một trong các lĩnh vực sau hay không: Tài chính, Giao dịch định lượng (Quant Trading), Chứng khoán, Kinh tế học, Khoa học dữ liệu/AI ứng dụng trong tài chính, Toán học/Thống kê, hoặc Cryptocurrency.
Nếu NỘI DUNG HOÀN TOÀN KHÔNG LIÊN QUAN (ví dụ: công thức nấu ăn, ảnh phong cảnh, tin tức giải trí, meme...), bạn BẮT BUỘC chỉ trả về chính xác 1 dòng duy nhất là: "REJECT: Không liên quan đến tài chính". Không giải thích gì thêm.

Nếu nội dung hợp lệ và có liên quan, hãy tiến hành phân tích sâu và viết bản "Tóm Tắt Nội Dung Cốt Lõi (Key Insights & Findings)" theo cấu trúc chuẩn xác sau:

🎯 1. CHỦ ĐỀ & MỤC TIÊU CỐT LÕI:
(Tóm lược vấn đề chính, bối cảnh và mục tiêu được đề cập)

💡 2. CÁC PHÁT HIỆN & LUẬN ĐIỂM CHÍNH (Key Insights):
(Trình bày 3 - 5 điểm cốt lõi, phát hiện nổi bật hoặc lập luận mấu chốt)

📊 3. CHỈ SỐ, CÔNG THỨC & DỮ LIỆU ĐỊNH LƯỢNG:
(Trích xuất tất cả số liệu thống kê, tỷ lệ %, công thức, tham số mô hình/chiến lược)

🚀 4. KẾT LUẬN & ĐÚC KẾT THỰC TIỄN:
(Giá trị ứng dụng thực tế, bài học hoặc khuyến nghị then chốt)

--- VĂN BẢN TRÍCH XUẤT ĐẦY ĐỦ CẦN PHÂN TÍCH ---
{full_text[:35000]}
"""
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"[ANALYZER] Gemini summarization notice: {e}")
        return None

    @classmethod
    def _clean_sentences(cls, text: str) -> List[str]:
        """Tách văn bản thành danh sách các câu hoàn chỉnh sạch sẽ."""
        # Xóa các dòng header markdown thừa
        lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("---")]
        clean_doc = " ".join(lines)
        
        # Tách câu theo dấu chấm, chấm than, chấm hỏi, xuống dòng
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', clean_doc)
        valid_sentences = []
        for s in raw_sentences:
            s_clean = s.strip()
            # Giữ các câu có độ dài hợp lý từ 25 đến 350 ký tự
            if 25 <= len(s_clean) <= 400 and not s_clean.startswith("http") and not s_clean.startswith("#"):
                valid_sentences.append(s_clean)
        return valid_sentences

    @classmethod
    def _extract_quantitative_metrics(cls, text: str) -> List[str]:
        """Trích xuất tất cả các chỉ số, số liệu và công thức định lượng xuất hiện trong văn bản."""
        patterns = [
            # Chỉ số tài chính & định lượng (Sharpe, Drawdown, RSI, Win Rate, CAGR, Alpha, Beta...)
            r'(\b(?:Sharpe|Drawdown|RSI|EMA|SMA|MACD|Profit\s*Factor|Win\s*Rate|CAGR|Alpha|Beta|Loss|Return|Yield|Accuracy|F1|Loss|AUC|Precision|Recall)\b[^\n\.\;]{1,70})',
            # Các tỷ lệ phần trăm kèm ngữ cảnh
            r'([A-Za-z0-9\s]{2,20}\s*(?:tăng|giảm|đạt|is|was|increased|decreased|reached|equals?|=)\s*[\+\-]?\d+(?:\.\d+)?%)',
            # Các tham số dạng Key = Value
            r'(\b[A-Za-z_]{3,20}\s*=\s*[\d\.\+\-]+[^\n\,\;]{0,20})'
        ]
        found = []
        for p in patterns:
            matches = re.findall(p, text, re.IGNORECASE)
            for m in matches:
                clean_m = m.strip().replace("\n", " ")
                if len(clean_m) > 5 and clean_m not in found:
                    found.append(clean_m)
        return list(dict.fromkeys(found))[:8] # Lấy tối đa 8 chỉ số đặc sắc nhất

    @classmethod
    def _summarize_local_nlp(cls, title: str, full_text: str, source_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Thuật toán NLP Extractive & Heuristics phân tích sâu toàn bộ văn bản 100% offline.
        """
        metadata = metadata or {}
        sentences = cls._clean_sentences(full_text)
        
        # 1. Từ khóa trọng tâm và Marker nhận diện luận điểm
        insight_markers = [
            "kết quả", "phát hiện", "chỉ ra", "cho thấy", "đặc biệt", "quan trọng",
            "kết luận", "chứng minh", "thành công", "hiệu quả", "chiến lược", "mô hình",
            "results", "findings", "shows", "demonstrates", "indicates", "conclude",
            "crucial", "significant", "strategy", "achieves", "proposed", "performance",
            "improve", "optimal", "reveals", "highlights", "tối ưu", "phân tích"
        ]

        # 2. Chấm điểm từng câu trong toàn bộ văn bản
        scored_sentences = []
        for idx, s in enumerate(sentences):
            score = 0.0
            s_lower = s.lower()

            # Vị trí: Các câu ở đầu tài liệu và đầu các đoạn có trọng số cao hơn
            if idx < 5:
                score += 3.0
            elif idx < 15:
                score += 1.5

            # Chứa từ khóa insight
            for marker in insight_markers:
                if marker in s_lower:
                    score += 2.0

            # Chứa số liệu / tỷ lệ % / công thức
            if re.search(r'\d+(?:\.\d+)?%?', s):
                score += 1.5

            # Độ dài câu tối ưu (không quá ngắn, không quá dài)
            if 50 <= len(s) <= 220:
                score += 1.0

            scored_sentences.append((score, idx, s))

        # Sắp xếp lấy các câu có điểm số cao nhất
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        top_insights = [item[2] for item in scored_sentences[:4]]
        # Sắp xếp lại theo thứ tự xuất hiện ban đầu trong văn bản
        top_insights.sort(key=lambda s: sentences.index(s) if s in sentences else 0)

        # 3. Trích xuất chỉ số định lượng
        quant_metrics = cls._extract_quantitative_metrics(full_text)

        # 4. Trích xuất phần tóm tắt mở đầu hoặc Abstract nếu có
        abstract_match = re.search(r'(?:abstract|tóm tắt|executive summary|overview)[\s\:\-\_]{1,10}(.*?)(?:\n\n|\n\#|introduction|1\.)', full_text, re.IGNORECASE | re.DOTALL)
        if abstract_match:
            overview_text = abstract_match.group(1).strip().replace("\n", " ")[:350]
        elif sentences:
            overview_text = sentences[0][:350]
        else:
            overview_text = f"Tài liệu nghiên cứu trích xuất từ nguồn [{source_type}]: {title}."

        # 5. Tổng hợp thành bản phân tích có cấu trúc chuẩn
        summary_sections = []
        
        # Phần 1: Chủ đề & Bối cảnh
        summary_sections.append(f"🎯 1. CHỦ ĐỀ & MỤC TIÊU CỐT LÕI:\n• Nguồn dữ liệu: {source_type} | Tiêu đề: {title}")
        if metadata.get("author"):
            summary_sections.append(f"• Tác giả / Đơn vị: {metadata['author']}")
        if metadata.get("publish_date"):
            summary_sections.append(f"• Thời gian công bố: {metadata['publish_date']}")
        summary_sections.append(f"• Tóm lược bối cảnh: {overview_text}")

        # Phần 2: Các phát hiện & Luận điểm chính
        summary_sections.append("\n💡 2. CÁC PHÁT HIỆN & LUẬN ĐIỂM CỐT LÕI (Key Insights):")
        if top_insights:
            for s in top_insights:
                summary_sections.append(f"• {s}")
        else:
            summary_sections.append("• Toàn bộ văn bản đã được ghi nhận và phân loại thành công vào Vault.")

        # Phần 3: Số liệu & Tham số định lượng
        if quant_metrics:
            summary_sections.append("\n📊 3. CHỈ SỐ, CÔNG THỨC & THAM SỐ ĐỊNH LƯỢNG:")
            for m in quant_metrics:
                summary_sections.append(f"• {m}")

        # Phần 4: Đúc kết thực tiễn
        summary_sections.append("\n🚀 4. KẾT LUẬN & ĐÚC KẾT THỰC TIỄN:")
        # Lấy câu kết luận ở cuối bài nếu có
        last_sentences = [s for s in sentences[-5:] if any(m in s.lower() for m in ["kết luận", "conclude", "tóm lại", "summary", "tương lai", "khuyến nghị", "therefore", "thus"])]
        if last_sentences:
            summary_sections.append(f"• {last_sentences[0]}")
        else:
            summary_sections.append(f"• Dữ liệu từ {source_type} đã được bóc tách toàn diện với {len(full_text.split()):,} từ, sẵn sàng cho việc tra cứu và ứng dụng.")

        return "\n".join(summary_sections)

    @classmethod
    def analyze_full_text(cls, title: str, full_text: str, source_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Hàm điều phối trung tâm: Đọc toàn bộ full text và trả về bản tóm tắt cốt lõi hoàn chỉnh.
        1. Thử phân tích qua Gemini AI nếu có API Key.
        2. Tự động fallback sang thuật toán Deep Local NLP nếu chạy Offline.
        """
        if not full_text or len(full_text.strip()) < 20:
            return f"📌 Nguồn: {source_type} | Tiêu đề: {title}\n[Văn bản trích xuất quá ngắn hoặc chưa có nội dung để phân tích sâu.]"

        # 1. Thử AI Summarizer
        ai_summary = cls._summarize_via_gemini(title, full_text, source_type)
        if ai_summary:
            return ai_summary

        # Bộ lọc chủ đề (Topic Filter) Offline: Nếu không có API Key, dùng từ khóa
        finance_keywords = [
            "tài chính", "chứng khoán", "kinh tế", "cổ phiếu", "giao dịch", 
            "đầu tư", "tiền điện tử", "thị trường", "định lượng", "chiến lược", 
            "quant", "finance", "stock", "market", "trading", "investment", 
            "crypto", "blockchain", "economics", "thuật toán", "algorithm",
            "dữ liệu", "data", "machine learning", "trí tuệ nhân tạo", "ai"
        ]
        text_lower = full_text.lower()
        if not any(k in text_lower for k in finance_keywords):
            return "REJECT: Không liên quan đến tài chính"

        # 2. Fallback sang Thuật toán NLP Extractive
        return cls._summarize_local_nlp(title, full_text, source_type, metadata)
