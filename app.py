import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import os
import time
import pandas as pd

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Beverage Innovator 3.0", layout="wide", initial_sidebar_state="expanded")

# --- 2. CSS STYLING ---
st.markdown("""
<style>
    /* HIDE STREAMLIT UI */
    #MainMenu {visibility: hidden; display: none;}
    footer {visibility: hidden; display: none;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* TITLES */
    h1, h2, h3 {
        text-align: left !important;
    }

    /* --- SIDEBAR BUTTONS: FORCE LEFT ALIGNMENT --- */
    
    /* Target the button element inside the Sidebar */
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        display: flex !important; 
        justify-content: flex-start !important; /* This forces items to the left */
        text-align: left !important;
        padding-left: 15px !important;
        align-items: center !important;
    }

    /* Ensure the internal text container also aligns left */
    [data-testid="stSidebar"] .stButton > button > div {
        text-align: left !important;
    }

    /* GREEN BUTTONS (Default - History Items) */
    div.stButton > button {
        background-color: #e8f5e9 !important;
        color: #2e7d32 !important;
        border: 1px solid #2e7d32 !important;
        border-radius: 8px;
    }
    div.stButton > button:hover {
        background-color: #c8e6c9 !important;
        border-color: #1b5e20 !important;
    }

    /* RED BUTTONS (Logout/Wipe) */
    div.stButton > button[kind="primary"] {
        background-color: #ffebee !important;
        color: #c62828 !important;
        border: 1px solid #c62828 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #ffcdd2 !important;
        border-color: #b71c1c !important;
    }
    
    /* CENTER LOGO IN MAIN AREA */
    div[data-testid="stImage"] {
        display: block;
        margin-left: auto;
        margin-right: auto;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SECURITY GATE ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.markdown("<h1>🔒 Innovator Access</h1>", unsafe_allow_html=True) # Left aligned
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

# ==========================================
#  ✅ APP LOGIC STARTS HERE
# ==========================================

# --- 4. DATABASE CONNECTION ---
sheet = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    if "gcp_service_account" in st.secrets:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            sheet = client.open("JSON 3.0 Logs").sheet1
except Exception as e:
    st.warning(f"⚠️ Database Offline: {e}")

# --- 5. SMART TITLE GENERATOR ---
def get_smart_title(user_text):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(f"Generate a 3-4 word title. No quotes. Input: {user_text}")
        return response.text.strip().replace('"', '').replace("Title:", "")
    except:
        return (user_text[:25] + "..") if len(user_text) > 25 else user_text

# --- 6. RESTORE HISTORY ---
if "history_loaded" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.session_titles = {"Session 1": "New Chat"}
    st.session_state.active_session_id = "Session 1"
    st.session_state.session_counter = 1
    
    if sheet:
        try:
            with st.spinner("🔄 Syncing Database..."):
                data = sheet.get_all_values()
                if len(data) > 1:
                    rebuilt = {}
                    titles = {}
                    max_num = 1
                    temp_first_msgs = {} 

                    for row in data[1:]: 
                        if len(row) >= 4:
                            ts, sid, role, txt = row[0], row[1], row[2], row[3]
                            if sid not in rebuilt: rebuilt[sid] = []
                            rebuilt[sid].append({"role": role, "content": txt})
                            
                            if role == "user" and sid not in temp_first_msgs:
                                temp_first_msgs[sid] = txt
                            
                            try:
                                n = int(sid.replace("Session ", ""))
                                if n > max_num: max_num = n
                            except: pass
                    
                    for sid, first_msg in temp_first_msgs.items():
                        titles[sid] = get_smart_title(first_msg)

                    if rebuilt:
                        st.session_state.chat_sessions = rebuilt
                        st.session_state.session_titles = titles
                        st.session_state.session_counter = max_num
                        st.session_state.active_session_id = list(rebuilt.keys())[-1]
            st.session_state.history_loaded = True
        except: st.session_state.history_loaded = True

# --- 7. HELPER FUNCTIONS ---
def format_chat_log(session_name, messages):
    log_text = f"--- LOG: {session_name} ---\nDate: {datetime.now()}\n\n"
    if not messages: return log_text + "(Empty)"
    for msg in messages:
        role = "AI" if msg["role"] == "assistant" else "USER"
        log_text += f"[{role}]:\n{msg['content']}\n\n{'-'*40}\n\n"
    return log_text

def save_to_sheet(session_id, role, content):
    if sheet:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([timestamp, session_id, role, content])
        except: pass

def clear_google_sheet():
    if sheet:
        try:
            sheet.clear()
            sheet.append_row(["Timestamp", "Session ID", "Role", "Content"])
        except Exception as e:
            st.error(f"Failed to clear database: {e}")

# --- 8. SIDEBAR ---
with st.sidebar:
    st.header("🗄️ History")
    
    if "confirm_wipe" not in st.session_state: st.session_state.confirm_wipe = False

    # 1. NEW CHAT
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.session_counter += 1
        new_name = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[new_name] = []
        st.session_state.session_titles[new_name] = "New Chat"
        st.session_state.active_session_id = new_name
        st.rerun()

    st.divider()

    # 2. SESSION LIST (Cleaned up - No "Sheet" Logo)
    names = list(st.session_state.chat_sessions.keys())
    if not names:
        st.caption("No history found.")
    else:
        for name in names[::-1]:
            display = st.session_state.session_titles.get(name, name)
            
            # Logic: Only show '🟢' if active. Otherwise, show nothing (clean text).
            prefix = "🟢 " if name == st.session_state.active_session_id else "" 
            
            if st.button(f"{prefix}{display}", key=f"btn_{name}", use_container_width=True):
                st.session_state.active_session_id = name
                st.rerun()

    st.divider()
    
    # 3. CONTROLS
    if st.session_state.active_session_id:
        curr = st.session_state.chat_sessions[st.session_state.active_session_id]
        st.download_button("📥 Download Log", format_chat_log(st.session_state.active_session_id, curr), f"Log_{st.session_state.active_session_id}.txt", use_container_width=True)

    if st.button("🔄 Refresh Memory", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()
        
    if st.button("🔒 Logout", use_container_width=True, type="primary"):
        st.session_state.password_correct = False
        st.rerun()

    # 4. WIPE EVERYTHING
    if st.session_state.confirm_wipe:
        st.warning("⚠️ PERMANENTLY DELETE DATABASE?")
        col1, col2 = st.columns(2)
        if col1.button("✅ Yes", type="primary"): 
            clear_google_sheet()
            st.session_state.chat_sessions = {"Session 1": []}
            st.session_state.session_titles = {"Session 1": "New Chat"}
            st.session_state.active_session_id = "Session 1"
            st.session_state.session_counter = 1
            st.session_state.confirm_wipe = False
            st.rerun()
        if col2.button("❌ No"):
            st.session_state.confirm_wipe = False
            st.rerun()
    else:
        if st.button("💣 Wipe Everything", type="primary", use_container_width=True):
            st.session_state.confirm_wipe = True
            st.rerun()

# --- 9. MAIN INTERFACE ---

# Create two columns: A narrow one for the Logo, a wide one for the Title
col_logo, col_title = st.columns([0.15, 0.85]) 

with col_logo:
    try: 
        # Display Logo (width adjusted to sit nicely next to text)
        st.image("logo.png", width=150) 
    except: 
        st.header("🍹")

# Title Left Aligned
st.markdown("<h3>Beverage Innovator 3.0</h3>", unsafe_allow_html=True)

# --- 10. KNOWLEDGE BASE ---
@st.cache_resource
def load_knowledge_base():
    files = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    loaded = []
    for filename in files:
        if not os.path.exists(filename): continue
        try:
            ref = genai.upload_file(filename)
            while ref.state.name == "PROCESSING":
                time.sleep(1)
                ref = genai.get_file(ref.name)
            loaded.append(ref)
        except: pass
    return loaded

with st.spinner("⚡ Starting Engine 3.0..."):
    knowledge_base = load_knowledge_base()

HIDDEN_PROMPT = """
You are the Beverage Innovator 3.0.
CRITICAL: You have access to the Flavor Bible (Split), Case Studies, and Client Data.
CITATION RULE: You MUST cite your source (e.g., "According to the Flavor Bible...").
Discovery Protocol: Ask 3 questions (Name, Direction, Category).
"""

# --- 11. MODEL SELECTOR (GEMINI 3 FLASH PREVIEW) ---
try:
    model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=HIDDEN_PROMPT)
    st.toast("🚀 Running on Gemini 3 Flash Preview!")
except:
    try:
        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=HIDDEN_PROMPT)
        st.toast("⚡ Running on Gemini 2.0 Flash")
    except:
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=HIDDEN_PROMPT)

# --- 12. CHAT LOGIC ---
curr_msgs = st.session_state.chat_sessions[st.session_state.active_session_id]
for m in curr_msgs:
    with st.chat_message(m["role"]): st.markdown(m["content"])

col1, col2 = st.columns([0.15, 0.85]) 
with col1:
    with st.popover("📎 Attach", use_container_width=True):
        up_file = st.file_uploader("Upload", type=["png", "jpg", "csv", "txt"])
        up_content, up_img = None, False
        if up_file:
            st.caption("✅ Ready")
            if "image" in up_file.type:
                st.image(up_file, width=150)
                up_content = Image.open(up_file)
                up_img = True
            else: up_content = up_file.getvalue().decode("utf-8")

if prompt := st.chat_input(f"Innovate here..."):
    
    # User Message
    st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if up_file: st.markdown(f"*(Attached: {up_file.name})*")
    save_to_sheet(st.session_state.active_session_id, "user", prompt)

    # Response
    with st.chat_message("assistant"):
        status = st.status("🧠 Innovator 3.0 Thinking...", expanded=True)
        try:
            # Full Context Loop
            messages_for_api = []
            
            # 1. Knowledge Base
            if knowledge_base:
                parts = list(knowledge_base)
                parts.append("System Context: Reference materials attached. Use them.")
                messages_for_api.append({"role": "user", "parts": parts})
                messages_for_api.append({"role": "model", "parts": ["Acknowledged."]})

            # 2. History
            for msg in st.session_state.chat_sessions[st.session_state.active_session_id]:
                role = "model" if msg["role"] == "assistant" else "user"
                
                if msg["content"] == prompt and msg == st.session_state.chat_sessions[st.session_state.active_session_id][-1]:
                     current_parts = [prompt]
                     if up_content:
                         current_parts.append(up_content)
                         if up_img: current_parts.append("Analyze this image.")
                     messages_for_api.append({"role": role, "parts": current_parts})
                else:
                     messages_for_api.append({"role": role, "parts": [msg["content"]]})

            status.write("⚡ Generating Solution...")
            response = model.generate_content(messages_for_api)
            
            status.update(label="✅ Ready", state="complete", expanded=False)
            
            st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "assistant", "content": response.text})
            st.markdown(response.text)
            save_to_sheet(st.session_state.active_session_id, "assistant", response.text)
            
        except Exception as e:
            status.update(label="❌ Connection Lost", state="error", expanded=True)
            if "403" in str(e) or "404" in str(e):
                st.error("⚠️ Connection Reset. Please click 'Refresh Memory' on the left.")
            else:
                st.error(f"Error: {e}")

    # Title Update
    if st.session_state.session_titles.get(st.session_state.active_session_id) == "New Chat":
        new_title = get_smart_title(prompt)
        st.session_state.session_titles[st.session_state.active_session_id] = new_title





