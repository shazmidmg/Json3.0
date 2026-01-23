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
# 2. CSS
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
            st.error("❌ Incorrect password")
    return False

if not check_password():
    st.stop()

# =====================================================
# 4. GOOGLE SHEETS (ASYNC)
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
# 5. GEMINI SETUP
# =====================================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# =====================================================
# 6. 🔥 FULL SYSTEM PROMPT (UNCHANGED LOGIC)
# =====================================================
HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia.

Context:
- Attached in your knowledgebase is the flavour bible, and a few past case studies, keep these in mind.
- You are very good at crafting creative drinks that are also commercially suitable.
- Use Monin products.

Intent:
- To help the user achieve a certain objective for the cafe/business through crafting innovative drink ideas that will trend instantly.

Discovery Session (Proactive Mode):
- **STEP 1: ANALYZE.** Look at the user's input.
- **STEP 2: CHECK MISSING INFO.** (Location, Objective, Category)
- **STEP 3: HYBRID RESPONSE.**
  - Acknowledge enthusiasm.
  - Ask missing questions.
  - Provide "Immediate Inspiration" (5 ideas for ALL 3 categories).
  - Provide "Next Step" prompts.

VISUAL FORMATTING PROTOCOL (STRICT):
1. **HUGE TITLES:** Use Markdown Header 2 (`##`) for every Category Title.
2. **CLEAN LISTS:** Use standard numbered lists (`1. `, `2. `).
3. **SPACING:** Ensure every numbered item is on its own line. Do NOT combine them into a paragraph.
4. **BOLDING:** Bold the Drink Name.

Correct Visual Output Example:

## Category 1: Traditional (Refined & Timeless)
1. **Idea One**: Description here.
2. **Idea Two**: Description here.
3. **Idea Three**: Description here.
4. **Idea Four**: Description here.
5. **Idea Five**: Description here.

## Category 2: Modern Heritage (Malaysian Soul, Modern Twist)
6. **Idea Six**: Description here.
7. **Idea Seven**: Description here.
8. **Idea Eight**: Description here.
9. **Idea Nine**: Description here.
10. **Idea Ten**: Description here.

## Category 3: Crazy (Avant-Garde & Experimental)
11. **Idea Eleven**: Description here.
12. **Idea Twelve**: Description here.
13. **Idea Thirteen**: Description here.
14. **Idea Fourteen**: Description here.
15. **Idea Fifteen**: Description here.

Would you like me to expand on any ideas, combine any flavors, or provide the recipe of some ideas? Example prompts:

1. I like Idea 6, Idea 7 and Idea 13, kindly give me more drink ideas like these.

2. I like Idea 2 and Idea 8, kindly combine these two drink ideas together.

3. I want to finalise Idea 1, Idea 6 and Idea 12 as my drink ideas, kindly give me the recipe for these ideas.
"""

# =====================================================
# 7. MODEL (CACHED)
# =====================================================
@st.cache_resource
def load_model():
    return genai.GenerativeModel(
        "gemini-3-flash-preview",
        system_instruction=HIDDEN_PROMPT
    )

model = load_model()

# =====================================================
# 8. KNOWLEDGE BASE (ATTACHED ONCE)
# =====================================================
@st.cache_resource
def load_knowledge_base():
    files = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    uploaded = []
    try:
        existing = {f.display_name: f for f in genai.list_files()}
    except:
        existing = {}

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
# 9. SESSION INIT (STATEFUL CHAT)
# =====================================================
if "sessions" not in st.session_state:
    st.session_state.sessions = {"Session 1": []}
    st.session_state.active_session = "Session 1"
    st.session_state.session_counter = 1

    st.session_state.chat = model.start_chat(
        history=[{
            "role": "user",
            "parts": knowledge_base + [
                "These are reference documents. Use them silently in all future answers."
            ]
        }]
    )

# =====================================================
# 10. SIDEBAR
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
                "parts": knowledge_base + [
                    "These are reference documents. Use them silently."
                ]
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
# 11. MAIN UI
# =====================================================
st.markdown("## 🍹 Beverage Innovator 3.0")

for msg in st.session_state.sessions[st.session_state.active_session]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =====================================================
# 12. INPUT + RESPONSE (FAST PATH)
# =====================================================
uploaded_file = None
with st.popover("📎 Attach"):
    uploaded_file = st.file_uploader("Upload", type=["png", "jpg", "txt"])

if prompt := st.chat_input("Innovate here..."):

    # USER
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

    # ASSISTANT
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
