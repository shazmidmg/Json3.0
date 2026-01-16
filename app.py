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
st.set_page_config(page_title="Monin Innovation Lab", layout="wide", initial_sidebar_state="expanded")

# --- HIDE STREAMLIT BRANDING (Fixed) ---
# We keep the header visible so you can see the sidebar arrow!
hide_st_style = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- CUSTOM BUTTON STYLING ---
st.markdown("""
<style>
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        text-align: left !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
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

# --- 3. RESTORE HISTORY & TITLES ---
if "history_loaded" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.session_titles = {"Session 1": "New Chat"}
    st.session_state.active_session_id = "Session 1"
    st.session_state.session_counter = 1
    
    if sheet:
        try:
            with st.spinner("🔄 Restoring History..."):
                data = sheet.get_all_values()
                if len(data) > 1:
                    rebuilt = {}
                    titles = {}
                    max_num = 1
                    for row in data[1:]: 
                        if len(row) >= 4:
                            ts, sid, role, txt = row[0], row[1], row[2], row[3]
                            if sid not in rebuilt: 
                                rebuilt[sid] = []
                                # Default title based on first user message
                                if role == "user":
                                    titles[sid] = (txt[:25] + "..") if len(txt) > 25 else txt
                            rebuilt[sid].append({"role": role, "content": txt})
                            
                            # Keep updating title if still default
                            if role == "user" and titles.get(sid) == "New Chat":
                                titles[sid] = (txt[:25] + "..") if len(txt) > 25 else txt

                            try:
                                n = int(sid.replace("Session ", ""))
                                if n > max_num: max_num = n
                            except: pass
                    if rebuilt:
                        st.session_state.chat_sessions = rebuilt
                        st.session_state.session_titles = titles
                        st.session_state.session_counter = max_num
                        st.session_state.active_session_id = list(rebuilt.keys())[-1]
            st.session_state.history_loaded = True
        except: st.session_state.history_loaded = True

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

def get_smart_title(user_text):
    """Generates a smart 3-5 word title using the lightweight 1.5-flash model"""
    try:
        # We use 1.5-flash here because it is fast and cheap
        titler = genai.GenerativeModel("gemini-1.5-flash")
        res = titler.generate_content(f"Summarize this into a 3-5 word chat title. No quotes. Input: {user_text}")
        clean_title = res.text.strip().replace('"', '').replace("Title:", "")
        return clean_title
    except:
        return (user_text[:25] + "..") if len(user_text) > 25 else user_text

# --- 5. SIDEBAR UI ---
with st.sidebar:
    st.header("🗄️ Tier 1 History")
    count = len(st.session_state.chat_sessions)
    st.caption(f"Active Memory: {count}/10 Sessions")
    
    if "confirm_overwrite" not in st.session_state:
        st.session_state.confirm_overwrite = False

    # NEW CHAT (With Safety Check)
    if st.session_state.confirm_overwrite:
        st.warning("⚠️ Limit Reached (10/10)")
        col_conf1, col_conf2 = st.columns(2)
        if col_conf1.button("✅ Confirm"):
            oldest = list(st.session_state.chat_sessions.keys())[0]
            del st.session_state.chat_sessions[oldest]
            if st.session_state.active_session_id == oldest: st.session_state.active_session_id = None
            
            st.session_state.session_counter += 1
            new_name = f"Session {st.session_state.session_counter}"
            st.session_state.chat_sessions[new_name] = []
            st.session_state.session_titles[new_name] = "New Chat"
            st.session_state.active_session_id = new_name
            st.session_state.confirm_overwrite = False
            st.rerun()
        if col_conf2.button("❌ Cancel"):
            st.session_state.confirm_overwrite = False
            st.rerun()
    else:
        if st.button("➕ New Chat", type="primary", use_container_width=True):
            if count >= 10:
                st.session_state.confirm_overwrite = True
                st.rerun()
            else:
                st.session_state.session_counter += 1
                new_name = f"Session {st.session_state.session_counter}"
                st.session_state.chat_sessions[new_name] = []
                st.session_state.session_titles[new_name] = "New Chat"
                st.session_state.active_session_id = new_name
                st.rerun()

    st.divider()

    # SMART TITLE LIST
    names = list(st.session_state.chat_sessions.keys())
    if not names:
        st.warning("No active chats.")
    else:
        for name in names[::-1]:
            # Use the smart title, fallback to ID
            display = st.session_state.session_titles.get(name, name)
            
            style = "secondary"
            icon = "📄 "
            if name == st.session_state.active_session_id:
                style = "primary"
                icon = "🟢 "
            
            if st.button(f"{icon}{display}", key=f"btn_{name}", use_container_width=True, type=style):
                st.session_state.active_session_id = name
                st.rerun()

    st.divider()
    
    if st.session_state.active_session_id:
        curr = st.session_state.chat_sessions[st.session_state.active_session_id]
        st.download_button("📥 Download Log", format_chat_log(st.session_state.active_session_id, curr), f"Monin_{st.session_state.active_session_id}.txt", use_container_width=True)
        
        if st.button("🗑️ Delete Current Session", use_container_width=True):
            del st.session_state.chat_sessions[st.session_state.active_session_id]
            remaining = list(st.session_state.chat_sessions.keys())
            st.session_state.active_session_id = remaining[-1] if remaining else None
            if not remaining:
                 st.session_state.chat_sessions = {"Session 1": []}
                 st.session_state.session_titles = {"Session 1": "New Chat"}
                 st.session_state.active_session_id = "Session 1"
                 st.session_state.session_counter = 1
            st.rerun()
    
    if st.button("💣 Wipe Everything", type="primary", use_container_width=True):
        st.session_state.chat_sessions = {"Session 1": []}
        st.session_state.session_titles = {"Session 1": "New Chat"}
        st.session_state.active_session_id = "Session 1"
        st.session_state.session_counter = 1
        st.rerun()

# --- 6. MAIN UI ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try: st.image("logo.png", use_container_width=True) 
    except: st.header("🍹 Monin Lab")

st.markdown(f"<h3 style='text-align: center;'>Drink Innovation Manager</h3>", unsafe_allow_html=True)

# --- 7. TIER 1 LOADER ---
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
            time.sleep(1) # Safe pause
        except: time.sleep(2)
    return loaded

with st.spinner("⚡ Tier 1: Loading Knowledge Base..."):
    knowledge_base = load_knowledge_base()

HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia. 
CRITICAL: You have access to the Flavor Bible (Split), Case Studies, and Client Data.
CITATION RULE: You MUST cite your source (e.g., "According to the Flavor Bible...").
Discovery Protocol: Ask 3 questions (Name, Direction, Category).
"""

# --- 8. MODEL: STABLE 2.0 (Falls back to 1.5 if needed) ---
try:
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=HIDDEN_PROMPT)
except:
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=HIDDEN_PROMPT)

# --- 9. CHAT LOGIC ---
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

if prompt := st.chat_input(f"Type here..."):
    
    # 1. Update UI
    st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if up_file: st.markdown(f"*(Attached: {up_file.name})*")
    save_to_sheet(st.session_state.active_session_id, "user", prompt)

    # 2. GENERATE SMART TITLE (Triggers only on the first exchange)
    # We check if this session is "New Chat" and this is the first real message
    if st.session_state.session_titles.get(st.session_state.active_session_id) == "New Chat":
        new_title = get_smart_title(prompt)
        st.session_state.session_titles[st.session_state.active_session_id] = new_title
        st.rerun() # Refresh immediately to show the new title

    # 3. GENERATE RESPONSE
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
