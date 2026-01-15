import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import os
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Monin Innovation Lab", layout="centered")

# Display Logo
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.png", use_container_width=True) 
    except:
        st.header("🍹 Monin Lab")

st.markdown("<h3 style='text-align: center;'>Drink Innovation Manager</h3>", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "knowledge_base" not in st.session_state:
    st.session_state.knowledge_base = [] 

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

# --- 3. KNOWLEDGE LOADER (SPLIT BIBLES) ---
# We now load bible1, bible2, studies, and clients
if not st.session_state.knowledge_base:
    with st.spinner("📚 Loading Knowledge Base (Bible Pt 1 & 2, Studies, CSV)..."):
        try:
            # UPDATED LIST: We look for the split files
            files_to_load = ["bible1.pdf", "bible2.pdf", "studies.pdf", "clients.csv"]
            loaded_files = []
            
            for filename in files_to_load:
                if os.path.exists(filename):
                    st.toast(f"Uploading {filename} to Brain...")
                    uploaded_ref = genai.upload_file(filename)
                    
                    # Wait for processing
                    while uploaded_ref.state.name == "PROCESSING":
                        time.sleep(1)
                        uploaded_ref = genai.get_file(uploaded_ref.name)
                        
                    loaded_files.append(uploaded_ref)
                    st.toast(f"✅ Active: {filename}")
                else:
                    # Optional warning if a file is missing, but app keeps running
                    print(f"File skipped: {filename}")
            
            st.session_state.knowledge_base = loaded_files
        except Exception as e:
            st.error(f"Knowledge Load Error: {e}")

# --- 4. THE PERSONA PROMPT (STRICT CITATION) ---
HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia. 

CRITICAL KNOWLEDGE INSTRUCTION:
You have access to:
1. 'bible1.pdf' & 'bible2.pdf' (The Flavor Bible Split) - Use these for flavor pairing.
2. 'studies.pdf' (Case Studies) - Use for trends.
3. 'clients.csv' (Client Data) - Use for segmentation.

CITATION RULE:
When you suggest a pairing or trend, you MUST mention which document it came from.
Example: "Based on the Flavor Bible (Part 1)..." or "According to client data..."

Discovery Protocol:
1. Ask the 3 standard questions (Name/Location, Direction, Category).
2. Then ask follow-ups (Current flavors, operational capacity).

Output Rules:
- Provide ideas in 3 categories: Traditional, Modern Heritage, Crazy.
- Validate ingredients against the provided knowledge.
"""

try:
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=HIDDEN_PROMPT)
except:
    model = genai.GenerativeModel("gemini-flash-latest", system_instruction=HIDDEN_PROMPT)

# --- 5. CHAT HISTORY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. USER ATTACHMENT BUTTON ---
col1, col2 = st.columns([0.15, 0.85]) 
with col1:
    with st.popover("📎 Attach", use_container_width=True):
        user_uploaded_file = st.file_uploader("Upload Image/Menu", type=["png", "jpg", "jpeg", "csv", "txt"])
        user_file_content = None
        user_is_image = False
        
        if user_uploaded_file:
            st.caption("✅ Ready to send")
            if "image" in user_uploaded_file.type:
                st.image(user_uploaded_file, width=150)
                user_file_content = Image.open(user_uploaded_file)
                user_is_image = True
            else:
                user_file_content = user_uploaded_file.getvalue().decode("utf-8")

# --- 7. CHAT INPUT ---
if prompt := st.chat_input("Start the session..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if user_uploaded_file:
            st.markdown(f"*(User Attached: {user_uploaded_file.name})*")

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                inputs = [prompt]
                
                # Add Knowledge Base
                if st.session_state.knowledge_base:
                    inputs.extend(st.session_state.knowledge_base)
                
                # Add User Upload
                if user_file_content:
                    inputs.append(user_file_content)
                    if user_is_image:
                        inputs.append("(Analyze this specific user-uploaded image)")
                
                response = model.generate_content(inputs)
                ai_text = response.text
                
                st.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})

                if sheet:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([timestamp, prompt, ai_text])

            except Exception as e:
                st.error(f"Error: {e}")
