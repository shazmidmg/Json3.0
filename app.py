import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import os
import time
import pandas as pd

# --- 1. CONFIGURATION & MOBILE CSS FIX ---
st.set_page_config(page_title="Monin Innovation Lab", layout="wide")

# CSS HACK: 
# 1. Force sidebar columns to stay side-by-side (No wrapping).
# 2. Force the Trash Button (Column 2) to stay small and square.
st.markdown("""
<style>
    /* Force Sidebar columns to be side-by-side */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 5px !important;
    }
    
    /* Make the Trash Button Small & Square (prevent stretching) */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button[kind="secondary"] {
        width: 100% !important; /* The name button takes full space */
    }
    
    /* Target the trash button specifically based on column structure */
    [data-testid="stSidebar"] [data-testid="column"]:nth-of-type(2) button {
        width: 45px !important; /* FORCE SQUARE SIZE */
        padding: 0px !important;
        border: 1px solid #444 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION & CONNECTION ---
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

# --- 3. RESTORE HISTORY (DATABASE) ---
if "history_loaded" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.active_session_id = "Session 1"
    st.session_state.session_counter = 1
    
    if sheet:
        try:
            with st.spinner("🔄 Restoring History..."):
                data = sheet.get_all_values()
                if len(data) > 1:
                    rebuilt_sessions = {}
                    max_session_num = 1
                    for row in data[1:]: 
                        if len(row) >= 4:
                            ts, sess_id, role, content = row[0], row[1], row[2], row[3]
                            if sess_id not in rebuilt_sessions: 
                                rebuilt_sessions[sess_id] = []
                            rebuilt_sessions[sess_id].append({"role": role, "content": content})
                            try:
                                num = int(sess_id.replace("Session ", ""))
                                if num > max_session_num: max_session_num = num
                            except: pass
                    
                    if rebuilt_sessions:
                        st.session_state.chat_sessions = rebuilt_sessions
                        st.session_state.session_counter = max_session_num
                        st.session_state.active_session_id = list(rebuilt_sessions.keys())[-1]
            st.session_state.history_loaded = True
        except:
            st.session_state.history_loaded = True

# --- 4. HELPER FUNCTIONS ---
def format_chat_log(session_name, messages):
    log_text = f"--- MONIN LOG: {session_name} ---\nDate: {datetime.now()}\n\n"
    if not messages: return log_text + "(Empty)"
    for msg in messages:
        role = "MANAGER" if msg["role"] == "assistant" else "USER"
        log_text += f"[{role}]:\n{msg['content']}\n\n{'-'*40}\n\n"
    return log_text

def save_to_sheet(session_id, role, content):
    if sheet:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([timestamp, session_id, role, content])
        except: pass

# --- 5. SIDEBAR UI (CUSTOM SESSION MANAGER) ---
with st.sidebar:
    st.header("🗄️ Tier 1 History")
    
    # Counter
    session_count = len(st.session_state.chat_sessions)
    st.caption(f"Active Memory: {session_count}/10 Sessions")
    
    # 1. NEW CHAT BUTTON
    if st.button("➕ New Chat", use_container_width=True):
        if session_count >= 10:
            oldest = list(st.session_state.chat_sessions.keys())[0]
            del st.session_state.chat_sessions[oldest]
            st.toast(f"♻️ Limit reached: Archived '{oldest}'")
            if st.session_state.active_session_id == oldest: 
                st.session_state.active_session_id = None 
        
        st.session_state.session_counter += 1
        new_name = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[new_name] = []
        st.session_state.active_session_id = new_name
        st.rerun()

    st.divider()

    # 2. SESSION LIST (The Fixed Layout)
    session_names = list(st.session_state.chat_sessions.keys())
    
    if not session_names:
        st.warning("No active chats.")
    else:
        for session_name in session_names[::-1]:
            # Create columns: [Name Button] [Trash Button]
            # Use a tighter ratio for mobile: 0.85 vs 0.15
            col1, col2 = st.columns([0.85, 0.15])
            
            # Active Highlight Logic
            label = session_name
            type_style = "secondary"
            if session_name == st.session_state.active_session_id:
                label = f"🟢 {session_name}"
                type_style = "primary"
            
            # BUTTON 1: NAME
            if col1.button(label, key=f"btn_{session_name}", use_container_width=True, type=type_style):
                st.session_state.active_session_id = session_name
                st.rerun()
            
            # BUTTON 2: TRASH (Now forced to be small by CSS)
            if col2.button("🗑️", key=f"del_{session_name}", use_container_width=True):
                del st.session_state.chat_sessions[session_name]
                if st.session_state.active_session_id == session_name:
                    remaining = list(st.session_state.chat_sessions.keys())
                    st.session_state.active_session_id = remaining[-1] if remaining else None
                st.rerun()

    st.divider()
    
    # 3. DOWNLOAD BUTTON
    if st.session_state.active_session_id:
        curr = st.session_state.chat_sessions[st.session_state.active_session_id]
        st.download_button("📥 Download Log", format_chat_log(st.session_state.active_session_id, curr), f"Monin_{st.session_state.active_session_id}.txt", use_container_width=True)
    
    # 4. CLEAR ALL
    if st.button("💣 Wipe Everything", type="primary", use_container_width=True):
        st.session_state.chat_sessions = {"Session 1": []}
        st.session_state.active_session_id = "Session 1"
        st.session_state.session_counter = 1
        st.rerun()

# --- 6. MAIN UI ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try: st.image("logo.png", use_container_width=True) 
    except: st.header("🍹 Monin Lab")

st.markdown(f"<h3 style='text-align: center;'>Drink Innovation Manager ({st.session_state.active_session_id})</h3>", unsafe_allow_html=True)

# --- 7. TIER 1 TURBO LOADER ---
@st.cache_resource
def load_knowledge_base():
    files = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    loaded = []
    existing = [f for f in files if os.path.exists(f)]
    if not existing: return []
    
    for f in existing:
        try:
            ref = genai.upload_file(f)
            while ref.state.name == "PROCESSING":
                time.sleep(1)
                ref = genai.get_file(ref.name)
            loaded.append(ref)
        except Exception as e:
            print(f"Skipped {f}: {e}")
            
    return loaded

with st.spinner("⚡ Tier 1: Loading Knowledge Base Instantly..."):
    knowledge_base = load_knowledge_base()

HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia. 
CRITICAL: You have access to the Flavor Bible (Split), Case Studies, and Client Data.
CITATION RULE: You MUST cite your source (e.g., "According to the Flavor Bible...").

Discovery Protocol:
1. Ask the 3 standard questions (Name/Location, Direction, Category).
2. Wait for answer. Then ask follow-ups.

Output Rules:
- Provide ideas in 3 categories: Traditional, Modern Heritage, Crazy.
- Validate ingredients against the provided knowledge.
"""

try:
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=HIDDEN_PROMPT)
except:
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=HIDDEN_PROMPT)

# --- 8. CHAT DISPLAY & INPUT ---
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

if prompt := st.chat_input(f"Message {st.session_state.active_session_id}..."):
    st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if up_file: st.markdown(f"*(Attached: {up_file.name})*")
    save_to_sheet(st.session_state.active_session_id, "user", prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                inputs = [prompt]
                if knowledge_base: inputs.extend(knowledge_base)
                if up_content:
                    inputs.append(up_content)
                    if up_img: inputs.append("(Analyze image)")
                
                response = model.generate_content(inputs)
                st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "assistant", "content": response.text})
                st.markdown(response.text)
                save_to_sheet(st.session_state.active_session_id, "assistant", response.text)
            except Exception as e:
                st.error(f"Error: {e}")
