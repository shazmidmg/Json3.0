import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Monin Assistant", layout="centered")

# Display Logo
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.png", use_container_width=True) 
    except:
        st.header("🤖 Monin Assistant")

st.markdown("<h3 style='text-align: center;'>Your Data Automation Partner</h3>", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

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

# --- 3. THE AI BRAIN (UNIVERSAL MODE) ---
# We load TWO brains. One for text, one for images.
# This works on ALL server versions, old and new.
try:
    model_text = genai.GenerativeModel("gemini-pro")
    model_vision = genai.GenerativeModel("gemini-pro-vision")
except:
    st.error("Error loading models. Please reboot.")

HIDDEN_PROMPT = """
You are the Monin Data Assistant.
1. If the user provides data (text or file), convert it to clean JSON.
2. If the user asks a question, answer normally.
"""

# --- 4. CHAT HISTORY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 5. THE "ATTACH" BUTTON ---
col1, col2 = st.columns([0.15, 0.85]) 
with col1:
    with st.popover("📎 Attach", use_container_width=True):
        uploaded_file = st.file_uploader("Upload File", type=["png", "jpg", "csv", "txt"])
        file_content = None
        file_type = ""
        is_image = False
        
        if uploaded_file:
            file_type = uploaded_file.type
            st.caption("✅ File Attached")
            if "image" in file_type:
                st.image(uploaded_file, width=150)
                file_content = Image.open(uploaded_file)
                is_image = True
            else:
                file_content = uploaded_file.getvalue().decode("utf-8")

# --- 6. CHAT INPUT (SMART SWITCHING) ---
if prompt := st.chat_input("Type a message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded_file:
            st.markdown(f"*(Attached: {uploaded_file.name})*")

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                ai_text = ""
                
                # SCENARIO A: Image + Text (Use Vision Brain)
                if is_image and file_content:
                    # The old Vision model needs [prompt, image]
                    response = model_vision.generate_content([prompt, file_content])
                    ai_text = response.text
                
                # SCENARIO B: Text Only (Use Text Brain)
                else:
                    # We manually add the system prompt for the old brain
                    full_prompt = f"{HIDDEN_PROMPT}\n\nUser Input: {prompt}"
                    if file_content and not is_image:
                        full_prompt += f"\n\nFile Data: {file_content}"
                        
                    response = model_text.generate_content(full_prompt)
                    ai_text = response.text
                
                st.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})

                if sheet:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([timestamp, prompt, ai_text])

            except Exception as e:
                st.error(f"Error: {e}")
