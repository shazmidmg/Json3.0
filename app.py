import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import os

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
    st.session_state.knowledge_base = [] # Stores the uploaded PDF references

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

# --- 3. KNOWLEDGE LOADER (The "Option B" Magic) ---
# This runs once to load your PDFs into the AI's brain
if not st.session_state.knowledge_base:
    with st.spinner("📚 Loading Monin Knowledge Base (Bible & Catalogs)..."):
        try:
            files_to_load = ["bible.pdf", "catalog.pdf", "studies.pdf"] # Must match GitHub filenames
            loaded_files = []
            
            for filename in files_to_load:
                if os.path.exists(filename):
                    # Upload to Gemini File API (Temporary cloud storage for analysis)
                    uploaded_ref = genai.upload_file(filename)
                    loaded_files.append(uploaded_ref)
                    st.toast(f"✅ Loaded: {filename}")
            
            st.session_state.knowledge_base = loaded_files
        except Exception as e:
            st.error(f"Knowledge Load Error: {e}")

# --- 4. THE PERSONA PROMPT ---
HIDDEN_PROMPT = """
You are the Talented Drink Innovation Manager at Monin Malaysia. 
Your Goal: Craft innovative drink ideas that are commercially suitable and make customers fall in love.

KNOWLEDGE BASE INSTRUCTION:
You have been provided with Monin PDF documents (Flavor Bible, Catalog, etc). 
ALWAYS refer to these documents for available flavors, trends, and application techniques.
Do NOT invent Monin products that do not exist in the provided catalog.

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
- Validate every ingredient against the provided Catalog/Bible.
- If the user finalizes ideas, provide Recipe, Preparation, and Garnish.
"""

# Initialize Model (Gemini 2.0 Flash is best for heavy PDF reading)
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
        with st.spinner("Consulting the Flavor Bible..."):
            try:
                # We feed the Prompt + The PDF Knowledge Base + The User Message
                inputs = [prompt]
                
                # Attach the Pre-loaded Knowledge Base (PDFs) to this request
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
