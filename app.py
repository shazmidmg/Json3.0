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
# 1. CONFIGURATION
# =====================================================
st.set_page_config(
    page_title="Beverage Innovator 3.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# 2. SECURITY GATE
# =====================================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.markdown("<h1>🔒 Innovator Access</h1>", unsafe_allow_html=True)
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect Password")
    return False

if not check_password():
    st.stop()

# =====================================================
# 3. GOOGLE SHEETS CONNECTION
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

    threading.Thread(target=task).start()

# =====================================================
# 4. GEMINI CONFIG
# =====================================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia.

Context:
- Attached in your knowledgebase is the flavour bible, and a few past case studies, keep these in mind.
- You are very good at crafting creative drinks that are also commercially suitable for the cafe's/business' audience.
- During the discover session, the user will share a catalog containing all of Monin's products.

Intent:
- To help the user achieve a certain objective for the cafe/business through crafting innovative drink ideas that will trend instantly.

Discovery Session (Proactive Mode):
- **STEP 1: ANALYZE.** Look at the user's input.
- **STEP 2: CHECK MISSING INFO.**
  - Cafe Name/Location?
  - Objective/Direction?
  - Category (Artisanal, Chain, Restaurant)?
- **STEP 3: HYBRID RESPONSE.**
  - Acknowledge enthusiasm.
  - Ask missing questions.
  - Provide "Immediate Inspiration" (5 ideas for ALL 3 categories).
  - Provide "Next Step" prompts.

VISUAL FORMATTING PROTOCOL (STRICT):
1. **HUGE TITLES:** Use Markdown Header 2 (`##`) for every Category Title.
2. **CLEAN LISTS:** Use standard numbered lists (`1. `, `2. `).
3. **SPACING:** Ensure every numbered item is on its own line.
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

End every response by offering to:
- expand ideas
- combine flavours
- or provide full recipes
"""

model = genai.GenerativeModel(
    "gemini-3-flash-preview",
    system_instruction=HIDDEN_PROMPT
)

# =====================================================
# 5. SESSION STATE
# =====================================================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.active_session_id = "Session 1"

# =====================================================
# 6. DISPLAY CHAT HISTORY
# =====================================================
for msg in st.session_state.chat_sessions[
    st.session_state.active_session_id
]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =====================================================
# 7. FILE UPLOAD
# =====================================================
up_file = st.file_uploader(
    "Attach file (optional)",
    type=["png", "jpg", "csv", "txt"]
)

up_content, up_img = None, False
if up_file:
    if "image" in up_file.type:
        up_content = Image.open(up_file)
        up_img = True
    else:
        up_content = up_file.getvalue().decode("utf-8")

# =====================================================
# 8. CHAT INPUT + STREAMING RESPONSE
# =====================================================
if prompt := st.chat_input("Innovate here..."):

    # USER MESSAGE
    st.session_state.chat_sessions[
        st.session_state.active_session_id
    ].append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    save_to_sheet_background(
        st.session_state.active_session_id,
        "user",
        prompt
    )

    # ASSISTANT MESSAGE
    with st.chat_message("assistant"):

        # ---------- PHASE 1: THINKING ----------
        thinking_placeholder = st.empty()
        thinking_steps = [
            "🧠 Thinking…",
            "🔍 Reviewing flavour bible…",
            "📊 Analysing café objectives…",
            "✨ Crafting drink concepts…"
        ]

        thinking_placeholder.markdown(thinking_steps[0])
        for step in thinking_steps[1:]:
            time.sleep(0.6)
            thinking_placeholder.markdown(step)

        # ---------- PREPARE INPUT ----------
        messages_for_api = [{"role": "user", "parts": [prompt]}]

        if up_content:
            messages_for_api[0]["parts"].append(up_content)
            if up_img:
                messages_for_api[0]["parts"].append("Analyse this image.")

        # ---------- CALL GEMINI ----------
        response_stream = model.generate_content(
            messages_for_api,
            stream=True
        )

        # ---------- PHASE 2: LINE-BY-LINE STREAM ----------
        thinking_placeholder.empty()

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

        # ---------- SAVE ----------
        st.session_state.chat_sessions[
            st.session_state.active_session_id
        ].append({"role": "assistant", "content": full_response})

        save_to_sheet_background(
            st.session_state.active_session_id,
            "assistant",
            full_response
        )
