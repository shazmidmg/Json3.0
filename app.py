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
st.set_page_config(page_title="Monin Innovation Lab", layout="wide")

# --- 2. AUTHENTICATION & CONNECTION ---
# We move this up so we can load history BEFORE the UI starts
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

# --- 3. THE "TIME MACHINE" (LOAD HISTORY) ---
# This runs once on startup to restore your memories
if "history_loaded" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []}
    st.session_state.active_session_id = "Session 1"
    st.session_state.session_counter = 1
    
    if sheet:
        try:
            with st.spinner("🔄 Restoring History from Database..."):
                # Get all records
                data = sheet.get_all_values()
                
                # Check if we have data (and skip header if needed)
                if len(data) > 1:
                    # We expect columns: [Timestamp, Session_ID, Role, Content]
                    # We iterate through rows and rebuild the dictionary
                    rebuilt_sessions = {}
                    max_session_num = 1
                    
                    for row in data[1:]: # Skip header row
                        if len(row) >= 4:
                            ts, sess_id, role, content = row[0], row[1], row[2], row[3]
                            
                            if sess_id not in rebuilt_sessions:
                                rebuilt_sessions[sess_id] = []
                            
                            rebuilt_sessions[sess_id].append({"role": role, "content": content})
                            
                            # Track the highest session number to continue counting correctly
                            try:
                                num = int(sess_id.replace("Session ", ""))
                                if num > max_session_num: max_session_num = num
                            except:
                                pass

                    # Apply to App State
                    if rebuilt_sessions:
                        st.session_state.chat_sessions = rebuilt_sessions
                        st.session_state.session_counter = max_session_num
                        # Set active to the most recent one found
                        st.session_state.active_session_id = list(rebuilt_sessions.keys())[-1]
                        
            st.session_state.history_loaded = True
        except Exception as e:
            print(f"Restore Failed: {e}")
            st.session_state.history_loaded = True # Fail safe

# --- 4. HELPER FUNCTIONS ---
def format_chat_log(session_name, messages):
    log_text = f"--- MONIN INNOVATION LAB: {session_name} ---\n"
    log_text += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    if not messages: return log_text + "(No messages)"
    for msg in messages:
        role = "MANAGER" if msg["role"] == "assistant" else "USER"
        log_text += f"[{role}]:\n{msg['content']}\n\n{'-'*40}\n\n"
    return log_text

def save_to_sheet(session_id, role, content):
    """Saves a single message to the cloud immediately"""
    if sheet:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Columns: Timestamp | Session ID | Role | Content
            sheet.append_row([timestamp, session_id, role, content])
        except Exception as e:
            st.error(f"Save Error: {e}")

# --- 5. SIDEBAR UI (10-SESSION LIMIT) ---
with st.sidebar:
    st.header("🗄️ Database History")
    
    session_count = len(st.session_state.chat_sessions)
    st.caption(f"Active Memory: {session_count}/10 Sessions")
    
    # NEW CHAT
    if st.button("➕ New Chat", use_container_width=True):
        if session_count >= 10:
            oldest_key = list(st.session_state.chat_sessions.keys())[0]
            del st.session_state.chat_sessions[oldest_key]
            st.toast(f"♻️ Limit reached: Archived '{oldest_key}'")
            if st.session_state.active_session_id == oldest_key:
                st.session_state.active_session_id = None 

        st.session_state.session_counter += 1
        new_session_name = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[new_session_name] = []
        st.session_state.active_session_id = new_session_name
        st.rerun()

    st.divider()

    # SESSION SWITCHER
    session_names = list(st.session_state.chat_sessions.keys())
    if st.session_state.active_session_id not in session_names:
        st.session_state.active_session_id = session_names[-1] if session_names else None

    if session_names:
        selected_session = st.radio(
            "Select Conversation:",
            session_names[::-1], 
            index=session_names[::-1].index(st.session_state.active_session_id)
        )
        if selected_session != st.session_state.active_session_id:
            st.session_state.active_session_id = selected_session
            st.rerun()
    
    st.divider()

    # DOWNLOAD
    if st.session_state.active_session_id:
        current_data = st.session_state.chat_sessions[st.session_state.active_session_id]
        log_data = format_chat_log(st.session_state.active_session_id, current_data)
        st.download_button("📥 Download Log", log_data, file_name=f"Monin_{st.session_state.active_session_id}.txt")

    # CLEAR (Does not delete from Google Sheets, only local view)
    if st.button("🗑️ Clear Local View", type="primary"):
        st.session_state.chat_sessions = {"Session 1": []}
        st.session_state.active_session_id = "Session 1"
        st.session_state.session_counter = 1
        st.rerun()

# --- 6. MAIN APP UI ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.png", use_container_width=True) 
    except:
        st.header("🍹 Monin Lab")

st.markdown(f"<h3 style='text-align: center;'>Drink Innovation Manager ({st.session_state.active_session_id})</h3>", unsafe_allow_html=True)

# --- 7. KNOWLEDGE LOADER ---
@st.cache_resource
def load_knowledge_base():
    files_to_load = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    loaded_refs = []
    existing_files = [f for f in files_to_load if os.path.exists(f)]
    if not existing_files: return []
    try:
        for i, filename in enumerate(existing_files):
            ref = genai.upload_file(filename)
            while ref.state.name == "PROCESSING":
                time.sleep(1)
                ref = genai.get_file(ref.name)
            loaded_refs.append(ref)
            if i < len(existing_files) - 1: time.sleep(10)
        return loaded_refs
    except Exception as e:
        print(f"Load Error: {e}")
        return []

with st.spinner("📚 Syncing Knowledge Base..."):
    knowledge_base = load_knowledge_base()

HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia. 
CRITICAL: Use Bible, Studies, Client Data. CITE SOURCES.
Discovery Protocol: Ask 3 questions (Name, Direction, Category).
"""

try:
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=HIDDEN_PROMPT)
except:
    model = genai.GenerativeModel("gemini-flash-latest", system_instruction=HIDDEN_PROMPT)

# --- 8. CHAT DISPLAY & INPUT ---
current_messages = st.session_state.chat_sessions[st.session_state.active_session_id]

for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

col1, col2 = st.columns([0.15, 0.85]) 
with col1:
    with st.popover("📎 Attach", use_container_width=True):
        user_uploaded_file = st.file_uploader("Upload", type=["png", "jpg", "csv", "txt"])
        user_file_content = None
        user_is_image = False
        if user_uploaded_file:
            st.caption("✅ Ready")
            if "image" in user_uploaded_file.type:
                st.image(user_uploaded_file, width=150)
                user_file_content = Image.open(user_uploaded_file)
                user_is_image = True
            else:
                user_file_content = user_uploaded_file.getvalue().decode("utf-8")

if prompt := st.chat_input(f"Message {st.session_state.active_session_id}..."):
    
    # 1. Update UI
    st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if user_uploaded_file: st.markdown(f"*(Attached: {user_uploaded_file.name})*")

    # 2. SAVE USER MSG TO CLOUD (Permanent)
    save_to_sheet(st.session_state.active_session_id, "user", prompt)

    # 3. Generate AI Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                inputs = [prompt]
                if knowledge_base: inputs.extend(knowledge_base)
                if user_file_content:
                    inputs.append(user_file_content)
                    if user_is_image: inputs.append("(Analyze this image)")
                
                response = model.generate_content(inputs)
                
                # 4. Update UI & SAVE AI MSG TO CLOUD
                st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "assistant", "content": response.text})
                st.markdown(response.text)
                
                save_to_sheet(st.session_state.active_session_id, "assistant", response.text)

            except Exception as e:
                st.error(f"Error: {e}")
