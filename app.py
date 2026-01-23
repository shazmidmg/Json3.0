import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import os
import time
import pandas as pd
import threading

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Beverage Innovator 3.0", layout="wide", initial_sidebar_state="expanded")

# --- 2. CSS STYLING (CLEAN UI) ---
st.markdown("""
<style>
    /* HIDE STREAMLIT FOOTER & WATERMARK */
    footer {visibility: hidden !important; height: 0px !important;}
    #MainMenu {visibility: hidden !important; display: none !important;}
    
    /* HIDE TOP RIGHT MENU */
    [data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
    [data-testid="stDecoration"] {visibility: hidden !important; display: none !important;}
    .stDeployButton {visibility: hidden !important; display: none !important;}
    
    /* HEADER TRANSPARENCY */
    header {visibility: visible !important; background-color: transparent !important;}

    /* TYPOGRAPHY */
    h1, h2, h3 { text-align: left !important; }

    /* SIDEBAR BUTTONS */
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        display: flex !important; 
        justify-content: flex-start !important;
        text-align: left !important;
        padding-left: 15px !important;
        align-items: center !important;
    }
    [data-testid="stSidebar"] .stButton > button > div { text-align: left !important; }

    /* BUTTON COLORS */
    div.stButton > button {
        background-color: transparent !important;
        color: #e0e0e0 !important;
        border: 1px solid #4a4a4a !important;
        border-radius: 8px;
    }
    div.stButton > button:hover {
        border-color: #808080 !important;
        color: #ffffff !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #e8f5e9 !important;
        color: #2e7d32 !important;
        border: 1px solid #2e7d32 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #c8e6c9 !important;
    }
    /* DANGER BUTTONS */
    [data-testid="stSidebar"] div.stButton:nth-last-of-type(2) button,
    [data-testid="stSidebar"] div.stButton:nth-last-of-type(3) button {
        background-color: #ffebee !important;
        color: #c62828 !important;
        border: 1px solid #c62828 !important;
    }

    /* CENTER LOGO */
    div[data-testid="stImage"] { display: block; margin-left: auto; margin-right: auto; }
</style>
""", unsafe_allow_html=True)

# --- 3. SECURITY GATE ---
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

# ==========================================
#  ✅ APP LOGIC STARTS HERE
# ==========================================

# --- 4. OPTIMIZED DATABASE CONNECTION ---
@st.cache_resource
def connect_to_db():
    try:
        if "gcp_service_account" in st.secrets:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            client = gspread.authorize(creds)
            return client.open("JSON 3.0 Logs").sheet1
    except: return None

sheet = connect_to_db()

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 5. SMART TITLE GENERATOR ---
def get_smart_title(user_text):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash") 
        response = model.generate_content(f"Generate a 3-4 word title. No quotes. Input: {user_text}")
        return response.text.strip().replace('"', '').replace("Title:", "")
    except:
        return (user_text[:25] + "..") if len(user_text) > 25 else user_text

# --- 6. HISTORY LOADER ---
if "history_loaded" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.session_titles = {"Session 1": "New Chat"}
    st.session_state.active_session_id = "Session 1"
    st.session_state.session_counter = 1
    
    if sheet:
        try:
            with st.spinner("🔄 Syncing History..."):
                data = sheet.get_all_values()
                if len(data) > 1:
                    rebuilt = {}
                    titles = {}
                    max_num = 1
                    temp_first_msgs = {} 
                    for row in data[1:]: 
                        if len(row) >= 4:
                            sid, role, txt = row[1], row[2], row[3]
                            if sid not in rebuilt: rebuilt[sid] = []
                            rebuilt[sid].append({"role": role, "content": txt})
                            if role == "user" and sid not in temp_first_msgs: temp_first_msgs[sid] = txt
                            try:
                                n = int(sid.replace("Session ", ""))
                                if n > max_num: max_num = n
                            except: pass
                    for sid, first_msg in temp_first_msgs.items(): titles[sid] = get_smart_title(first_msg)
                    if rebuilt:
                        st.session_state.chat_sessions = rebuilt
                        st.session_state.session_titles = titles
                        st.session_state.session_counter = max_num
                        st.session_state.active_session_id = list(rebuilt.keys())[-1]
            st.session_state.history_loaded = True
        except: st.session_state.history_loaded = True
    else: st.session_state.history_loaded = True

# --- 7. HELPER FUNCTIONS ---
def format_chat_log(session_name, messages):
    log_text = f"--- LOG: {session_name} ---\nDate: {datetime.now()}\n\n"
    if not messages: return log_text + "(Empty)"
    for msg in messages:
        role = "AI" if msg["role"] == "assistant" else "USER"
        log_text += f"[{role}]:\n{msg['content']}\n\n{'-'*40}\n\n"
    return log_text

# --- ⚡ BACKGROUND SAVE ---
def _save_task(session_id, role, content):
    if sheet:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([timestamp, session_id, role, content])
        except: pass

def save_to_sheet_background(session_id, role, content):
    thread = threading.Thread(target=_save_task, args=(session_id, role, content))
    thread.start()

def clear_google_sheet():
    if sheet:
        try:
            sheet.clear()
            sheet.append_row(["Timestamp", "Session ID", "Role", "Content"])
        except Exception as e: st.error(f"DB Error: {e}")

def delete_session_from_db(session_id):
    if sheet:
        try:
            all_rows = sheet.get_all_values()
            if not all_rows: return
            header = all_rows[0]
            new_rows = [row for row in all_rows[1:] if len(row) > 1 and row[1] != session_id]
            sheet.clear()
            sheet.append_row(header)
            if new_rows: sheet.update(range_name='A2', values=new_rows)
        except Exception as e: st.error(f"DB Error: {e}")

# --- 8. SIDEBAR ---
with st.sidebar:
    st.header("🗄️ History")
    if "confirm_wipe" not in st.session_state: st.session_state.confirm_wipe = False
    if "confirm_del_chat" not in st.session_state: st.session_state.confirm_del_chat = False

    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        st.session_state.session_counter += 1
        new_name = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[new_name] = []
        st.session_state.session_titles[new_name] = "New Chat"
        st.session_state.active_session_id = new_name
        st.rerun()

    st.divider()

    names = list(st.session_state.chat_sessions.keys())
    if not names: st.caption("No history found.")
    else:
        for name in names[::-1]:
            display = st.session_state.session_titles.get(name, name)
            btn_type = "primary" if name == st.session_state.active_session_id else "secondary"
            prefix = "🟢 " if name == st.session_state.active_session_id else ""
            if st.button(f"{prefix}{display}", key=f"btn_{name}", use_container_width=True, type=btn_type):
                st.session_state.active_session_id = name
                st.rerun()

    st.divider()
    
    if st.session_state.active_session_id:
        curr = st.session_state.chat_sessions[st.session_state.active_session_id]
        st.download_button("📥 Download Log", format_chat_log(st.session_state.active_session_id, curr), f"Log_{st.session_state.active_session_id}.txt", use_container_width=True)

    if st.button("🔄 Refresh Memory", use_container_width=True):
        st.cache_resource.clear()
        st.session_state.pop("history_loaded", None)
        st.rerun()

    disable_del = st.session_state.active_session_id is None
    if st.session_state.confirm_del_chat:
         st.warning("⚠️ Delete this chat?")
         c1, c2 = st.columns(2)
         if c1.button("✅ Yes"):
             sid = st.session_state.active_session_id
             delete_session_from_db(sid)
             del st.session_state.chat_sessions[sid]
             if sid in st.session_state.session_titles: del st.session_state.session_titles[sid]
             remaining = list(st.session_state.chat_sessions.keys())
             if remaining: st.session_state.active_session_id = remaining[-1]
             else:
                 st.session_state.session_counter += 1
                 new_name = f"Session {st.session_state.session_counter}"
                 st.session_state.chat_sessions[new_name] = []
                 st.session_state.session_titles[new_name] = "New Chat"
                 st.session_state.active_session_id = new_name
             st.session_state.confirm_del_chat = False
             st.rerun()
         if c2.button("❌ Cancel"):
             st.session_state.confirm_del_chat = False
             st.rerun()
    else:
         if st.button("🗑️ Delete Chat", use_container_width=True, disabled=disable_del):
             st.session_state.confirm_del_chat = True
             st.rerun()

    if st.session_state.confirm_wipe:
        st.warning("⚠️ DELETE DATABASE?")
        c1, c2 = st.columns(2)
        if c1.button("✅ Yes"): 
            clear_google_sheet()
            st.session_state.chat_sessions = {"Session 1": []}
            st.session_state.session_titles = {"Session 1": "New Chat"}
            st.session_state.active_session_id = "Session 1"
            st.session_state.session_counter = 1
            st.session_state.confirm_wipe = False
            st.rerun()
        if c2.button("❌ No"):
            st.session_state.confirm_wipe = False
            st.rerun()
    else:
        if st.button("💣 Wipe Everything", use_container_width=True):
            st.session_state.confirm_wipe = True
            st.rerun()

    if st.button("🔒 Logout", use_container_width=True):
        st.session_state.password_correct = False
        st.rerun()

# --- 9. MAIN INTERFACE ---
col_logo, col_title = st.columns([0.15, 0.85]) 
with col_logo:
    try: st.image("logo.png", width=150) 
    except: st.header("🍹")
st.markdown("<h3>Beverage Innovator 3.0</h3>", unsafe_allow_html=True)

# --- 10. KNOWLEDGE BASE (ROBUST UPLOAD) ---
@st.cache_resource
def load_knowledge_base():
    files = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    loaded = []
    
    try:
        # Get list of existing files
        existing_files = {f.display_name: f for f in genai.list_files()}
    except:
        existing_files = {}

    for filename in files:
        if not os.path.exists(filename): continue
        
        # LOGIC: If exists, try to get it. If 403 error, Re-Upload it.
        if filename in existing_files:
            try:
                # Try accessing the file to check permissions
                file_ref = genai.get_file(existing_files[filename].name)
                loaded.append(file_ref)
            except Exception:
                # Permission denied (403) or missing -> Re-upload
                try:
                    print(f"Re-uploading {filename} due to permission error...")
                    ref = genai.upload_file(filename, display_name=filename)
                    while ref.state.name == "PROCESSING":
                        time.sleep(1)
                        ref = genai.get_file(ref.name)
                    loaded.append(ref)
                except: pass
        else:
            # New upload
            try:
                ref = genai.upload_file(filename, display_name=filename)
                while ref.state.name == "PROCESSING":
                    time.sleep(1)
                    ref = genai.get_file(ref.name)
                loaded.append(ref)
            except: pass
            
    return loaded

with st.spinner("⚡ Starting Engine 3.0..."):
    knowledge_base = load_knowledge_base()

# --- 11. SMART PROMPT (BIG HEADERS + CLEAN LISTS) ---
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

# --- 12. MODEL SELECTOR (GEMINI 3 PRIORITY) ---
try:
    # PRIORITY 1: The New Gemini 3 Flash Preview
    model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=HIDDEN_PROMPT)
    st.toast("🚀 Running on Gemini 3 Flash Preview!")
except:
    try:
        # PRIORITY 2: The Fast Gemini 2.0 Flash
        model = genai.GenerativeModel("gemini-2.0-flash-exp", system_instruction=HIDDEN_PROMPT)
        st.toast("⚡ Running on Gemini 2.0 Flash")
    except:
        # FALLBACK: Gemini 1.5 Flash (Stable)
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=HIDDEN_PROMPT)

# --- 13. CHAT LOGIC (NATIVE STREAMLIT STREAMING) ---
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

# --- GENERATOR HELPER FOR ST.WRITE_STREAM ---
def stream_parser(stream):
    """Yields text from the Gemini response stream safely."""
    for chunk in stream:
        try:
            # We explicitly check and yield to play nice with st.write_stream
            if chunk.text:
                yield chunk.text
        except:
            pass

if prompt := st.chat_input(f"Innovate here..."):
    
    # User Message
    st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if up_file: st.markdown(f"*(Attached: {up_file.name})*")
    
    # --- NON-BLOCKING SAVE (INSTANT) ---
    save_to_sheet_background(st.session_state.active_session_id, "user", prompt)

    # Response with NATIVE STREAMING
    with st.chat_message("assistant"):
        try:
            messages_for_api = []
            if knowledge_base:
                parts = list(knowledge_base)
                parts.append("System Context: Reference materials attached. Use them.")
                messages_for_api.append({"role": "user", "parts": parts})
                messages_for_api.append({"role": "model", "parts": ["Acknowledged."]})

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

            # --- 1. SHOW SPINNER (Only until first token) ---
            with st.spinner("🧠 Thinking..."):
                response_stream = model.generate_content(messages_for_api, stream=True)
            
            # --- 2. NATIVE STREAMLIT STREAMING (The Fix) ---
            # st.write_stream handles the visual typing effect automatically and perfectly.
            # It also returns the full string at the end for us to save.
            full_response = st.write_stream(stream_parser(response_stream))
            
            # --- 3. SAVE ---
            st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "assistant", "content": full_response})
            save_to_sheet_background(st.session_state.active_session_id, "assistant", full_response)
            
        except Exception as e:
            st.error(f"Error: {e}")

    # Title Update
    if st.session_state.session_titles.get(st.session_state.active_session_id) == "New Chat":
        new_title = get_smart_title(prompt)
        st.session_state.session_titles[st.session_state.active_session_id] = new_title
