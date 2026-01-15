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

# --- 3. KNOWLEDGE LOADER (Bible, Studies, Clients) ---
# This runs automatically to load your specific files
if not st.session_state.knowledge_base:
    with st.spinner("📚 Loading Knowledge Base (Bible, Studies, CSV)..."):
        try:
            # We look for these 3 specific files
            files_to_load = ["bible.pdf", "studies.pdf", "clients.csv"]
            loaded_files = []
            
            for filename in files_to_load:
                if os.path.exists(filename):
                    st.toast(f"Uploading {filename} to Brain...")
                    # Upload to Gemini File API
                    uploaded_ref = genai.upload_file(filename)
                    
                    # Wait for PDF processing (Images/PDFs take a few seconds)
                    while uploaded_ref.state.name == "PROCESSING":
                        time.sleep(1)
                        uploaded_ref = genai.get_file(uploaded_ref.name)
                        
                    loaded_files.append(uploaded_ref)
                    st.toast(f"✅ Active: {filename}")
                else:
                    st.warning(f"⚠️ File not found: {filename} (Did you upload it to GitHub?)")
            
            st.session_state.knowledge_base = loaded_files
        except Exception as e:
            st.error(f"Knowledge Load Error: {e}")

# --- 4. THE PERSONA PROMPT ---
HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia. 
Your Goal: Craft innovative drink ideas that are commercially suitable and make customers fall in love.

KNOWLEDGE BASE INSTRUCTION:
You have access to 3 key documents:
1. 'bible.pdf' (The Flavor Bible) - Use this for flavor pairing logic.
2. 'studies.pdf' (Case Studies) - Use this for style and presentation references.
3. 'clients.csv' (Client Data) - Use this to understand market segments.

Discovery Protocol:
1. Start by asking the user:
   - "What is the name of the cafe/business and location?"
   - "What is the direction/goal for this drink ideation?"
   - "Which category best describes it? (Artisanal, Multi-Chain, etc?)"

2. Follow up (Max 3 questions at a time):
   - Current flavors/drinks served?
   - Any specific new concept or occasion?
   - Operational capacity (Staff skill/Equipment)?

Output Rules:
- When generating ideas, provide 3 categories: Traditional, Modern Heritage, Crazy.
- Validate every ingredient against the provided knowledge.
- If the user finalizes ideas, provide Recipe, Preparation, and Garnish.
"""

# Initialize Model
try:
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=HIDDEN_PROMPT)
except:
    model = genai.GenerativeModel("gemini-flash-latest", system_instruction=HIDDEN_PROMPT)

# --- 5. CHAT HISTORY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. CHAT INPUT ---
if prompt := st.chat_input("Start the session..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # We feed the Prompt + The 3 Loaded Files + The User Message
                inputs = [prompt]
                
                if st.session_state.knowledge_base:
                    inputs.extend(st.session_state.knowledge_base)
                
                response = model.generate_content(inputs)
                ai_text = response.text
                
                st.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})

                if sheet:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([timestamp, prompt, ai_text])

            except Exception as e:
                st.error(f"Error: {e}")
