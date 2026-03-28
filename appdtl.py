import streamlit as st
from docx import Document
from docx.text.paragraph import Paragraph
import google.generativeai as genai
import io
import time

# --- BẢO MẬT API KEY BẰNG KÉT SẮT CLOUD ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
except KeyError:
    st.error("❌ CẢNH BÁO BẢO MẬT: Chưa cấu hình GEMINI_API_KEY trong Két sắt (Secrets) của Streamlit.")
    st.stop()

# Tắt bộ lọc an toàn để tránh việc Gemini từ chối dịch tài liệu kỹ thuật
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

def auto_detect_domain(doc):
    """CONTEXT SNIFFER: Đọc lướt tài liệu để tự nhận diện chuyên ngành."""
    sample_text = ""
    for p in doc.paragraphs:
        if p.text.strip():
            sample_text += p.text.strip() + " \n"
        if len(sample_text) > 1000:
            break
            
    if not sample_text: return "Tài liệu kỹ thuật tổng hợp"

    prompt = f"""Bạn là chuyên gia phân tích dữ liệu. Đọc đoạn văn bản sau và trả lời bằng MỘT CỤM TỪ DUY NHẤT chỉ định lĩnh vực chuyên môn sâu của nó (Ví dụ: 'Quản lý dự án (PMP)', 'Kỹ thuật Cơ khí', 'Y khoa'). KHÔNG giải thích thêm.
    
    VĂN BẢN:
    {sample_text}"""

    try:
        # Sửa lại cú pháp generation_config thành dictionary an toàn
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2},
            safety_settings=SAFETY_SETTINGS
        )
        domain = response.text.strip()
        return domain.replace('"', '').replace("'", "")
    except:
        return "Tài liệu kỹ thuật tổng hợp"

def autonomous_translate(text, detected_domain):
    """Máy dịch thuật Tự trị: Dùng Domain tự nhận diện để kích hoạt từ vựng."""
    clean_text = text.strip()
    if not clean_text or len(clean_text) <= 2: 
        return text

    # Prompt ép buộc Tiếng Việt mạnh mẽ nhất
    prompt = f"""Bạn là chuyên gia dịch thuật kỹ thuật cấp cao.
Ngữ cảnh tài liệu: {detected_domain}

LỆNH BẮT BUỘC: DỊCH ĐOẠN VĂN BẢN SAU SANG TIẾNG VIỆT.

Yêu cầu khắt khe:
1. Trả về DUY NHẤT bản dịch tiếng Việt, KHÔNG giải thích, KHÔNG bình luận, KHÔNG thêm dấu ngoặc kép.
2. Giữ nguyên các thuật ngữ chuyên ngành tiếng Anh nếu nó là chuẩn mực quốc tế (Ví dụ: BIM, CAD, Baseline).
3. Tuyệt đối bám sát nghĩa gốc, hành văn chuyên nghiệp.

VĂN BẢN GỐC (CẦN DỊCH SANG TIẾNG VIỆT):
{clean_text}"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.0},
            safety_settings=SAFETY_SETTINGS
        )
        translated = response.text.strip()

        # Chatter Guard
        forbidden_words = ["xin chào", "giúp đỡ", "ngữ cảnh", "cung cấp", "hỗ trợ", "đây là bản dịch", "văn bản gốc"]
        if len(clean_text.split()) <= 2 and any(word in translated.lower() for word in forbidden_words):
            return text
            
        return translated
    except Exception as e:
        # Nếu lỗi vẫn xảy ra, in ngầm ra console để debug chứ không crash web
        print(f"Lỗi dịch: {e}") 
        return text

def safe_replace_text(p, translated_text):
    """KHIÊN TITAN: Ghi đè text an toàn tuyệt đối, bảo vệ ảnh và shape."""
    runs = p.runs
    if not runs: return
    
    anchor_run = None
    for r in runs:
        if r.text.strip():
            anchor_run = r; break
            
    if not anchor_run: anchor_run = runs[0]

    anchor_run.text = translated_text
    
    for r in runs:
        if r == anchor_run: continue
            
        xml_str = r._element.xml
        if ('w:drawing' in xml_str or 'w:pict' in xml_str or 'v:shape' in xml_str or 'w:object' in xml_str):
            continue 
            
        r.text = ""

def process_document(file):
    doc = Document(file)
    
    with st.spinner("🤖 Mũi ngửi AI (Gemini Engine) đang phân tích chuyên ngành của tài liệu..."):
        detected_domain = auto_detect_domain(doc)
        st.success(f"🎯 AI xác nhận lĩnh vực tài liệu: **{detected_domain}**")
        st.info("Đã tự động tải hệ thống từ vựng chuyên sâu tương ứng!")

    all_p_xml = doc._element.xpath('.//w:p')
    total_parts = len(all_p_xml)
    progress_bar = st.progress(0)
    current_step = 0

    st.write("Đang dịch thuật sang Tiếng Việt và bảo toàn sơ đồ khối...")
    for p_xml in all_p_xml:
        p = Paragraph(p_xml, doc)
        full_text = p.text.strip()
        
        if full_text:
            translated = autonomous_translate(full_text, detected_domain)
            safe_replace_text(p, translated)
            
        current_step += 1
        progress_bar.progress(min(current_step / total_parts, 1.0))

    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()

# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="Autonomous Agent v36.0", layout="wide")
st.title("🧠 Genesis Autonomous Agent v36.0 (Gemini Powered)")
st.markdown("Hệ thống biên dịch AI Tự trị: **Tự động nhận diện chuyên ngành** & **Bảo toàn Sơ đồ vật lý**.")

uploaded_file = st.file_uploader("Tải lên file Word (.docx) Tiếng Anh bất kỳ", type="docx")

if uploaded_file:
    if st.button("🚀 BẮT ĐẦU DỊCH SANG TIẾNG VIỆT", use_container_width=True):
        start_time = time.time()
        result = process_document(uploaded_file)
        
        if result:
            duration = time.time() - start_time
            st.balloons()
            st.success(f"✅ Hoàn thành xuất sắc trong {duration:.2f} giây!")
            st.download_button(
                label="📥 TẢI FILE CHUẨN XUẤT BẢN",
                data=result,
                file_name=f"Translated_VI_{uploaded_file.name}",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
