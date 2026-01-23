import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
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
# 2. SECURITY
# =====================================================
def check_password():
    if st.session_state.get("password_correct"):
        return True

    st.markdown("<h1>🔒 Innovator Access</h1>", unsafe_allow_html=True)
    password = st.text_input("Enter Password", type="password")

    if st.button("Login"):
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("❌ Incorrect Password")
    return False

if not check_password():
    st.stop()

# =====================================================
# 3. GOOGLE SHEETS
# =====================================================
@st.cache_resource
def connect_to_db():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gcp_service_account"]), scope
        )
        client = gspread.authorize(creds)
        return client.open("JSON 3.0 Logs").sheet1
    except:
        return None

sheet = connect_to_db()

def save_to_sheet_background(session_id, role, content):
    if not sheet:
        return

    def task():
        try:
            sheet.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                session_id,
                role,
                content
            ])
        except:
            pass

    threading.Thread(target=task, daemon=True).start()

# =====================================================
# 4. GEMINI SETUP
# =====================================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia.

Context:
- Attached in your knowledgebase is the flavour bible, and a few past case studies, keep these in mind.
- You are very good at crafting creative drinks that are also commercially suitable for the cafe's/business' audience.

Intent:
- To help the user achieve a certain objective for the cafe/business through crafting innovative drink ideas that will trend instantly.

Discovery Session:
- Analyze input
- Check missing info
- Provide inspiration + next steps

VISUAL FORMAT:
- Use ## headers
- Numbered lists
- Bold drink names
"""

model = genai.GenerativeModel(
    "gemini-3-flash-preview",
    system_instruction=HIDDEN_PROMPT
)

# =====================================================
# 5. SESSION STATE INIT
# =====================================================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.active_session = "Session 1"
    st.session_state.session_counter = 1

# =====================================================
# 6. SIDEBAR (HISTORY)
# =====================================================
with st.sidebar:
    st.header("🗂️ Chat History")

    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.session_counter += 1
        sid = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[sid] = []
        st.session_state.active_session = sid
        st.rerun()

    st.divider()

    for sid in reversed(st.session_state.chat_sessions.keys()):
        active = sid == st.session_state.active_session
        if st.button(
            ("🟢 " if active else "") + sid,
            use_container_width=True
        ):
            st.session_state.active_session = sid
            st.rerun()

# =====================================================
# 7. MAIN CHAT DISPLAY
# =====================================================
for msg in st.session_state.chat_sessions[
    st.session_state.active_session
]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =====================================================
# 8. FILE UPLOAD
# =====================================================
up_file = st.file_uploader(
    "Attach file (optional)",
    type=["png", "jpg", "txt", "csv"]
)

up_content, up_img = None, False
if up_file:
    if "image" in up_file.type:
        up_content = Image.open(up_file)
        up_img = True
    else:
        up_content = up_file.getvalue().decode("utf-8")

# =====================================================
# 9. CHAT INPUT + STREAMING
# =====================================================
if prompt := st.chat_input("Innovate here..."):

    # ---- USER MESSAGE ----
    st.session_state.chat_sessions[
        st.session_state.active_session
    ].append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    save_to_sheet_background(
        st.session_state.active_session,
        "user",
        prompt
    )

    # ---- ASSISTANT MESSAGE ----
    with st.chat_message("assistant"):

        # PHASE 1 — THINKING
        thinking = st.empty()
        steps = [
            "🧠 Thinking…",
            "🔍 Reviewing flavour bible…",
            "📊 Analysing objectives…",
            "✨ Crafting drink concepts…"
        ]

        thinking.markdown(steps[0])
        for s in steps[1:]:
            time.sleep(0.6)
            thinking.markdown(s)

        # PREPARE INPUT
        parts = [prompt]
        if up_content:
            parts.append(up_content)
            if up_img:
                parts.append("Analyse this image.")

        response_stream = model.generate_content(
            [{"role": "user", "parts": parts}],
            stream=True
        )

        # PHASE 2 — LINE-BY-LINE STREAM
        thinking.empty()

        placeholder = st.empty()
        full_response = ""
        buffer = ""

        for chunk in response_stream:
            try:
                if chunk.text:
                    buffer += chunk.text
                    lines = buffer.split("\n")
                    buffer = lines.pop()

                    for line in lines:
                        full_response += line + "\n"
                        placeholder.markdown(full_response)
                        time.sleep(0.03)
            except:
                pass

        if buffer:
            full_response += buffer
            placeholder.markdown(full_response)

        # SAVE
        st.session_state.chat_sessions[
            st.session_state.active_session
        ].append({"role": "assistant", "content": full_response})

        save_to_sheet_background(
            st.session_state.active_session,
            "assistant",
            full_response
        )
