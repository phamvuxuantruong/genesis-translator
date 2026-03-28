import streamlit as st
from docx import Document
from docx.text.paragraph import Paragraph
from openai import OpenAI
import io
import time

# --- BẢO MẬT API KEY BẰNG KÉT SẮT CLOUD ---
try:
    api_key = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)
except KeyError:
    st.error("❌ CẢNH BÁO BẢO MẬT: Chưa cấu hình API Key trong Két sắt (Secrets) của Streamlit.")
    st.stop()

def auto_detect_domain(doc):
    """CONTEXT SNIFFER: Đọc lướt tài liệu để tự nhận diện chuyên ngành."""
    sample_text = ""
    # Lấy mẫu văn bản từ các đoạn đầu tiên (khoảng 1000 ký tự là đủ để AI đoán)
    for p in doc.paragraphs:
        if p.text.strip():
            sample_text += p.text.strip() + " \n"
        if len(sample_text) > 1000:
            break
            
    if not sample_text: return "Tài liệu kỹ thuật tổng hợp"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia phân tích dữ liệu. Đọc đoạn văn bản sau và trả lời bằng MỘT CỤM TỪ DUY NHẤT chỉ định lĩnh vực chuyên môn sâu của nó (Ví dụ: 'Quản lý dự án (PMP)', 'Kỹ thuật Cơ khí', 'Y khoa', 'Luật Thương mại'). KHÔNG giải thích thêm."},
                {"role": "user", "content": sample_text}
            ],
            temperature=0.2
        )
        domain = response.choices[0].message.content.strip()
        # Lọc bỏ dấu ngoặc kép nếu AI trả về
        return domain.replace('"', '').replace("'", "")
    except:
        return "Tài liệu kỹ thuật tổng hợp"

def autonomous_translate(text, detected_domain):
    """Máy dịch thuật Tự trị: Dùng Domain tự nhận diện để kích hoạt từ vựng."""
    clean_text = text.strip()
    if not clean_text or len(clean_text) <= 2: 
        return text

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"""Bạn là cỗ máy biên dịch cấp cao.
                LĨNH VỰC TỰ ĐỘNG NHẬN DIỆN: {detected_domain}. 
                Hãy tự động sử dụng hệ thống thuật ngữ chuyên sâu, học thuật và chuẩn xác nhất của lĩnh vực này (Ví dụ nếu là PMP thì 'Baseline' giữ nguyên, 'Coordinator' là Điều phối viên...).
                
                QUY TẮC TỬ THẦN (VI PHẠM SẼ BỊ HỦY DIỆT):
                1. CHỈ trả về bản dịch. KHÔNG giải thích, KHÔNG định nghĩa, KHÔNG tự sáng tác thêm nội dung.
                2. Nếu văn bản gốc là một cụm từ ngắn (VD: "Definition", "Overview"), CHỈ dịch đúng chữ đó. Tuyệt đối cấm giải thích ý nghĩa.
                3. Không chào hỏi, không chứa dấu ngoặc kép bọc ngoài kết quả."""},
                {"role": "user", "content": clean_text}
            ],
            temperature=0 # Ép tuân thủ luật, không sáng tạo ảo giác
        )
        
        translated = response.choices[0].message.content.strip()

        # Chatter Guard
        forbidden_words = ["xin chào", "giúp đỡ", "ngữ cảnh", "cung cấp", "hỗ trợ", "đây là bản dịch"]
        if len(clean_text.split()) <= 2 and any(word in translated.lower() for word in forbidden_words):
            return text
            
        return translated
    except Exception:
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
        # BẢO VỆ TUYỆT ĐỐI HÌNH KHỐI VÀ ẢNH
        if ('w:drawing' in xml_str or 'w:pict' in xml_str or 'v:shape' in xml_str or 'w:object' in xml_str):
            continue 
            
        r.text = ""

def process_document(file):
    doc = Document(file)
    
    # BƯỚC 1: TỰ ĐỘNG NHẬN DIỆN NGỮ CẢNH (CONTEXT SNIFFER)
    with st.spinner("🤖 Mũi ngửi AI đang phân tích chuyên ngành của tài liệu..."):
        detected_domain = auto_detect_domain(doc)
        st.success(f"🎯 AI xác nhận lĩnh vực tài liệu: **{detected_domain}**")
        st.info("Đã tự động tải hệ thống từ vựng chuyên sâu tương ứng!")

    # BƯỚC 2: OMNI-SCANNER QUÉT VÀ DỊCH TÀI LIỆU
    all_p_xml = doc._element.xpath('.//w:p')
    total_parts = len(all_p_xml)
    progress_bar = st.progress(0)
    current_step = 0

    st.write("Đang dịch thuật và bảo toàn sơ đồ khối...")
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
st.title("🧠 Genesis Autonomous Agent v36.0")
st.markdown("Hệ thống biên dịch AI Tự trị: **Tự động nhận diện chuyên ngành** & **Bảo toàn Sơ đồ vật lý**.")

uploaded_file = st.file_uploader("Tải lên file Word (.docx) bất kỳ", type="docx")

if uploaded_file:
    if st.button("🚀 BẮT ĐẦU XỬ LÝ TỰ ĐỘNG", use_container_width=True):
        start_time = time.time()
        result = process_document(uploaded_file)
        
        if result:
            duration = time.time() - start_time
            st.balloons()
            st.success(f"✅ Hoàn thành xuất sắc trong {duration:.2f} giây!")
            st.download_button(
                label="📥 TẢI FILE CHUẨN XUẤT BẢN",
                data=result,
                file_name=f"Auto_Translated_{uploaded_file.name}",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )