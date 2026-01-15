import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import os
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Monin Innovation Lab", layout="wide") # Changed to 'wide' for better sidebar view

# Initialize Session State for Multiple Chats
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {"Session 1": []} # Default first chat
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = "Session 1"
if "session_counter" not in st.session_state:
    st.session_state.session_counter = 1

# --- SIDEBAR LOGIC (THE NEW HISTORY) ---
with st.sidebar:
    st.header("🗄️ Chat History")
    
    # 1. New Chat Button
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.session_counter += 1
        new_session_name = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[new_session_name] = []
        st.session_state.active_session_id = new_session_name
        st.rerun() # Force reload to show new empty chat

    st.divider()

    # 2. Session Switcher (Radio Button looks like a menu)
    # We list sessions in reverse order (newest on top)
    session_names = list(st.session_state.chat_sessions.keys())[::-1]
    
    selected_session = st.radio(
        "Select Conversation:",
        session_names,
        index=session_names.index(st.session_state.active_session_id)
    )
    
    # Update active session if user clicks a different one
    if selected_session != st.session_state.active_session_id:
        st.session_state.active_session_id = selected_session
        st.rerun()

    st.divider()
    
    # Debug/Clear Button
    if st.button("🗑️ Clear All History", type="primary"):
        st.session_state.chat_sessions = {"Session 1": []}
        st.session_state.active_session_id = "Session 1"
        st.session_state.session_counter = 1
        st.rerun()

# --- MAIN APP UI ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.png", use_container_width=True) 
    except:
        st.header("🍹 Monin Lab")

st.markdown(f"<h3 style='text-align: center;'>Drink Innovation Manager ({st.session_state.active_session_id})</h3>", unsafe_allow_html=True)

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
    st.warning(f"⚠️ Logger Offline: {e}")

# --- 3. SMART HYBRID LOADER ---
@st.cache_resource
def load_knowledge_base():
    files_to_load = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
    loaded_refs = []
    existing_files = [f for f in files_to_load if os.path.exists(f)]
    
    if not existing_files: return []

    try:
        for i, filename in enumerate(existing_files):
            print(f"Uploading {filename}...")
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

with st.spinner("📚 Checking Knowledge Base..."):
    knowledge_base = load_knowledge_base()

# --- 4. PERSONA ---
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
    model = genai.GenerativeModel("gemini-flash-latest", system_instruction=HIDDEN_PROMPT)

# --- 5. CHAT HISTORY DISPLAY ---
# IMPORTANT: We only display messages from the ACTIVE session
current_messages = st.session_state.chat_sessions[st.session_state.active_session_id]

for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. ATTACH BUTTON ---
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

# --- 7. INPUT ---
if prompt := st.chat_input(f"Message {st.session_state.active_session_id}..."):
    
    # Save User Message to specific session
    st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
        if user_uploaded_file:
            st.markdown(f"*(Attached: {user_uploaded_file.name})*")

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                inputs = [prompt]
                if knowledge_base: inputs.extend(knowledge_base)
                if user_file_content:
                    inputs.append(user_file_content)
                    if user_is_image: inputs.append("(Analyze this image)")
                
                response = model.generate_content(inputs)
                
                # Save AI Message to specific session
                st.session_state.chat_sessions[st.session_state.active_session_id].append({"role": "assistant", "content": response.text})
                
                st.markdown(response.text)
                
                if sheet:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([timestamp, prompt, response.text])
            except Exception as e:
                st.error(f"Error: {e}")
