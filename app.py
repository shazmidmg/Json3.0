import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import os
import time
import threading

# =====================================================
# 1. PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Beverage Innovator 3.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# 2. CSS (UNCHANGED)
# =====================================================
st.markdown("""
<style>
#MainMenu, footer, .stDeployButton {display:none;}
h1,h2,h3{text-align:left!important;}
[data-testid="stSidebar"] .stButton>button{width:100%!important;justify-content:flex-start!important;}
div.stButton>button{border-radius:8px;}
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. SECURITY
# =====================================================
def check_password():
    if st.session_state.get("password_correct"):
        return True

    st.markdown("## 🔒 Innovator Access")
    pwd = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if pwd == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False

if not check_password():
    st.stop()

# =====================================================
# 4. GOOGLE SHEETS (CACHED)
# =====================================================
@st.cache_resource
def connect_to_db():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["gcp_service_account"]), scope
    )
    client = gspread.authorize(creds)
    return client.open("JSON 3.0 Logs").sheet1

sheet = connect_to_db()

def save_to_sheet_async(row):
    def task():
        try:
            sheet.append_row(row)
        except:
            pass
    threading.Thread(target=task, daemon=True).start()

# =====================================================
# 5. GEMINI SETUP (CACHED)
# =====================================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia.

- Use Monin products
- Commercially viable
- Trend-focused drink innovation

Formatting rules:
- Use ## headers for categories
- Numbered lists
- Bold drink names
"""

@st.cache_resource
def load_model():
    return genai.GenerativeModel(
        "gemini-3-flash-preview",
        system_instruction=HIDDEN_PROMPT
    )

model = load_model()

# =====================================================
# 6. KNOWLEDGE BASE (ATTACH ONCE)
# =====================================================
@st.cache_resource
def load_knowledge_base():
    files = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    uploaded = []
    existing = {f.display_name: f for f in genai.list_files()}

    for f in files:
        if not os.path.exists(f):
            continue
        if f in existing:
            uploaded.append(existing[f])
        else:
            ref = genai.upload_file(f, display_name=f)
            while ref.state.name == "PROCESSING":
                time.sleep(1)
                ref = genai.get_file(ref.name)
            uploaded.append(ref)
    return uploaded

knowledge_base = load_knowledge_base()

# =====================================================
# 7. SESSION STATE INIT
# =====================================================
if "sessions" not in st.session_state:
    st.session_state.sessions = {"Session 1": []}
    st.session_state.active_session = "Session 1"
    st.session_state.session_counter = 1
    st.session_state.chat = model.start_chat(
        history=[{
            "role": "user",
            "parts": knowledge_base + ["Use these files as reference for all answers."]
        }]
    )

# =====================================================
# 8. SIDEBAR
# =====================================================
with st.sidebar:
    st.header("🗂️ History")

    if st.button("➕ New Chat", type="primary", use_container_width=True):
        st.session_state.session_counter += 1
        sid = f"Session {st.session_state.session_counter}"
        st.session_state.sessions[sid] = []
        st.session_state.active_session = sid
        st.session_state.chat = model.start_chat(
            history=[{
                "role": "user",
                "parts": knowledge_base + ["Use these files as reference."]
            }]
        )
        st.rerun()

    st.divider()

    for sid in reversed(st.session_state.sessions):
        if st.button(
            ("🟢 " if sid == st.session_state.active_session else "") + sid,
            use_container_width=True
        ):
            st.session_state.active_session = sid
            st.rerun()

    st.divider()

    if st.button("🔒 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# =====================================================
# 9. MAIN UI
# =====================================================
st.markdown("## 🍹 Beverage Innovator 3.0")

for msg in st.session_state.sessions[st.session_state.active_session]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =====================================================
# 10. INPUT + RESPONSE (FAST PATH)
# =====================================================
uploaded_file = None
with st.popover("📎 Attach"):
    uploaded_file = st.file_uploader("Upload", type=["png", "jpg", "txt"])

if prompt := st.chat_input("Innovate here..."):

    # USER MESSAGE
    st.session_state.sessions[st.session_state.active_session].append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    save_to_sheet_async([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        st.session_state.active_session,
        "user",
        prompt
    ])

    # ASSISTANT RESPONSE
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        parts = [prompt]
        if uploaded_file:
            if "image" in uploaded_file.type:
                parts.append(Image.open(uploaded_file))
                parts.append("Analyze this image.")
            else:
                parts.append(uploaded_file.getvalue().decode())

        stream = st.session_state.chat.send_message(parts, stream=True)

        for chunk in stream:
            if chunk.text:
                full_response += chunk.text
                placeholder.markdown(full_response + "▌")

        placeholder.markdown(full_response)

    st.session_state.sessions[st.session_state.active_session].append({
        "role": "assistant",
        "content": full_response
    })

    save_to_sheet_async([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        st.session_state.active_session,
        "assistant",
        full_response
    ])
