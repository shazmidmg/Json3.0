import streamlit as st
import google.generativeai as genai
from datetime import datetime
from PIL import Image
import os
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Beverage Innovator 3.0", layout="wide", initial_sidebar_state="expanded")

# --- 2. CSS STYLING ---
st.markdown("""
<style>
    /* HIDE STREAMLIT UI */
    #MainMenu {visibility: hidden; display: none;}
    footer {visibility: hidden; display: none;}
    .stDeployButton {display: none;}
    
    /* TITLES */
    h1, h2, h3 { text-align: left !important; }

    /* --- SIDEBAR BUTTONS --- */
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        display: flex !important; 
        justify-content: flex-start !important;
        text-align: left !important;
        padding-left: 15px !important;
        align-items: center !important;
    }

    [data-testid="stSidebar"] .stButton > button > div {
        text-align: left !important;
    }

    /* === BUTTON COLOR SYSTEM === */
    /* 1. DEFAULT (GREY) */
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

    /* 2. PRIMARY (GREEN) */
    div.stButton > button[kind="primary"] {
        background-color: #e8f5e9 !important;
        color: #2e7d32 !important;
        border: 1px solid #2e7d32 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #c8e6c9 !important;
        border-color: #1b5e20 !important;
    }

    /* 3. DANGER (RED) */
    [data-testid="stSidebar"] div.stButton:nth-last-of-type(2) button {
        background-color: #ffebee !important;
        color: #c62828 !important;
        border: 1px solid #c62828 !important;
    }
    [data-testid="stSidebar"] div.stButton:nth-last-of-type(3) button {
        background-color: #ffebee !important;
        color: #c62828 !important;
        border: 1px solid #c62828 !important;
    }

    /* CENTER LOGO */
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

# --- 4. API CONFIGURATION (NO SHEETS!) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 5. INITIALIZE RAM MEMORY ---
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.session_titles = {"Session 1": "New Chat"}
    st.session_state.active_session_id = "Session 1"
    st.session_state.session_counter = 1

# --- 6. SMART TITLE GENERATOR ---
def get_smart_title(user_text):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(f"Generate a 3-4 word title. No quotes. Input: {user_text}")
        return response.text.strip().replace('"', '').replace("Title:", "")
    except:
        return (user_text[:25] + "..") if len(user_text) > 25 else user_text

# --- 7. HELPER FUNCTIONS ---
def format_chat_log(session_name, messages):
    log_text = f"--- LOG: {session_name} ---\nDate: {datetime.now()}\n\n"
    if not messages: return log_text + "(Empty)"
    for msg in messages:
        role = "AI" if msg["role"] == "assistant" else "USER"
        log_text += f"[{role}]:\n{msg['content']}\n\n{'-'*40}\n\n"
    return log_text

# --- 8. SIDEBAR ---
with st.sidebar:
    st.header("🗄️ History")
    
    # State Managers
    if "confirm_wipe" not in st.session_state: st.session_state.confirm_wipe = False
    if "confirm_del_chat" not in st.session_state: st.session_state.confirm_del_chat = False

    # 1. NEW CHAT (Green - Primary)
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        st.session_state.session_counter += 1
        new_name = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[new_name] = []
        st.session_state.session_titles[new_name] = "New Chat"
        st.session_state.active_session_id = new_name
        st.rerun()

    st.divider()

    # 2. SESSION LIST
    names = list(st.session_state.chat_sessions.keys())
    if not names:
        st.caption("No history found.")
    else:
        # We reverse the list so newest is on top
        for name in names[::-1]:
            display = st.session_state.session_titles.get(name, name)
            
            # Logic: Active = Primary (Green), Inactive = Secondary (Grey)
            btn_type = "primary" if name == st.session_state.active_session_id else "secondary"
            prefix = "🟢 " if name == st.session_state.active_session_id else ""
            
            if st.button(f"{prefix}{display}", key=f"btn_{name}", use_container_width=True, type=btn_type):
                st.session_state.active_session_id = name
                st.rerun()

    st.divider()
    
    # 3. CONTROLS
    
    # [1] DOWNLOAD LOG
    if st.session_state.active_session_id:
        curr = st.session_state.chat_sessions[st.session_state.active_session_id]
        st.download_button("📥 Download Log", format_chat_log(st.session_state.active_session_id, curr), f"Log_{st.session_state.active_session_id}.txt", use_container_width=True)

    # [2] REFRESH (Resets connection to Gemini)
    if st.button("🔄 Refresh Memory", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    # [3] DELETE CHAT (Red)
    disable_del = st.session_state.active_session_id is None
    
    if st.session_state.confirm_del_chat:
         st.warning("⚠️ Delete this chat?")
         c1, c2 = st.columns(2)
         if c1.button("✅ Yes"):
             sid_to_del = st.session_state.active_session_id
             
             # RAM DELETE
             if sid_to_del in st.session_state.chat_sessions:
                 del st.session_state.chat_sessions[sid_to_del]
             if sid_to_del in st.session_state.session_titles:
                 del st.session_state.session_titles[sid_to_del]
             
             # Switch Session
             remaining = list(st.session_state.chat_sessions.keys())
             if remaining:
                 st.session_state.active_session_id = remaining[-1]
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

    # [4] WIPE EVERYTHING (Red)
    if st.session_state.confirm_wipe:
        st.warning("⚠️ Clear All?")
        col1, col2 = st.columns(2)
        if col1.button("✅ Yes"): 
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
        if st.button("💣 Wipe Everything", use_container_width=True):
            st.session_state.confirm_wipe = True
            st.rerun()

    # [5] LOGOUT
    if st.button("🔒 Logout", use_container_width=True):
        st.session_state.password_correct = False
        st.rerun()

# --- 9. MAIN INTERFACE ---
col_logo, col_title = st.columns([0.15, 0.85]) 
with col_logo:
    try: st.image("logo.png", width=150) 
    except: st.header("🍹")

st.markdown("<h3>Beverage Innovator 3.0</h3>", unsafe_allow_html=True)

# --- 10. KNOWLEDGE BASE (SMART CACHING) ---
@st.cache_resource
def load_knowledge_base():
    files = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    loaded = []
    
    # 1. Fetch existing files from Gemini Cloud to avoid re-uploading
    try:
        existing_files = {f.display_name: f for f in genai.list_files()}
    except:
        existing_files = {}

    for filename in files:
        if not os.path.exists(filename): continue
        
        # 2. Check if file is already online
        if filename in existing_files:
            loaded.append(existing_files[filename])
        else:
            # 3. If not, upload it (Only happens once per 48h)
            try:
                ref = genai.upload_file(filename, display_name=filename)
                while ref.state.name == "PROCESSING":
                    time.sleep(1)
                    ref = genai.get_file(ref.name)
                loaded.append(ref)
            except Exception as e:
                pass
                
    return loaded

with st.spinner("⚡ Starting Engine 3.0..."):
    knowledge_base = load_knowledge_base()

# --- NEW: INSTANT IDEATION PROMPT ---
HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia.

Context:
- Attached in your knowledgebase is the flavour bible, and a few past case studies, keep these in mind.
- You are very good at crafting creative drinks that are also commercially suitable for the cafe's/business' audience by combining different flavours, tastes, scents, etc (Which you can understand more from the flavour bible).
- During the discover session, the user will share a catalog containing all of Monin's products.

Intent:
- To help the user achieve a certain objective for the cafe/business through crafting innovative drink ideas that will trend instantly when the idea is presented to the audience.

**CRITICAL PROTOCOL (INSTANT MODE):**
1. **CHECK INPUT:** Does the user's message contain a specific **Ingredient** (e.g., "Earl Grey", "Yuzu") OR a **Theme**?
2. **IF YES:** STOP. DO NOT ASK QUESTIONS.
   - **Assume Context:** If the cafe name or type is missing, assume it is a standard "Trendy/Modern Cafe" in Malaysia.
   - **ACTION:** IMMEDIATELY generate the list of drink ideas.
   
3. **IF NO (Request is Vague):** Only then, ask: "What flavor or product would you like to focus on?"

**OUTPUT FORMAT (When Generating Ideas):**
- Start immediately: "Here are 15 innovative [Flavor] concepts for [Cafe Name/General]:"
- List the ideas directly (5 Traditional, 5 Modern Heritage, 5 Crazy).
- **AT THE END** of the list, add this footer:
  "Would you like recipes for any of these? Or should we tweak the direction?"

**Idea Creation Rules:**
- Identify the flavours & ingredients available.
- Come out with 5 drink ideas for each of 3 categories:
  - **Traditional** (Safe, familiar tastes)
  - **Modern Heritage** (Classic with a twist, fits modern audiences)
  - **Crazy** (Extremely creative/Instagrammable)
- Use the right ingredient for the correct drink type (e.g., Frappe powder for blended drinks).
- Ensure names fit the cafe vibe.

**Presentation:**
- **DO NOT** show your thinking steps.
- **DO NOT** ask clarifying questions if you have enough info to make a good guess.
- Present the final output (The List of Ideas) immediately.
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
    
    # Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
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

            # STREAMING REQUEST
            response_stream = model.generate_content(messages_for_api, stream=True)
            
            for chunk in response_stream:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
            st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error: {e}")

    # Title Update
    if st.session_state.session_titles.get(st.session_state.active_session_id) == "New Chat":
        new_title = get_smart_title(prompt)
        st.session_state.session_titles[st.session_state.active_session_id] = new_title
