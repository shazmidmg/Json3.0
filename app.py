import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="JSON 3.0 Chat", layout="centered")
st.title("🤖 JSON 3.0 Assistant")

# Initialize Chat History
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

# --- 3. THE AI BRAIN ---
HIDDEN_PROMPT = """
You are JSON 3.0, an intelligent data assistant.
1. If the user provides data (text or file), convert it to clean JSON.
2. If the user asks a question, answer normally.
3. If an image is provided, extract all text/data into JSON.
"""
model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=HIDDEN_PROMPT)

# --- 4. CHAT HISTORY DISPLAY ---
# We display history FIRST so the 'Attach' button appears after it (at the bottom)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 5. THE "ATTACH" BUTTON (Placed right above the chat bar) ---
# We use columns to make it small and align it to the left
col1, col2 = st.columns([0.15, 0.85]) 
with col1:
    # A small Popover that acts like a paperclip menu
    with st.popover("📎 Attach", use_container_width=True):
        uploaded_file = st.file_uploader("Upload Image/CSV", type=["png", "jpg", "csv", "txt"])
        
        # Preview Handling
        file_content = None
        file_type = ""
        if uploaded_file:
            file_type = uploaded_file.type
            st.caption("✅ File Attached")
            if "image" in file_type:
                st.image(uploaded_file, width=150)
                file_content = Image.open(uploaded_file)
            else:
                file_content = uploaded_file.getvalue().decode("utf-8")

# --- 6. CHAT INPUT (Stuck to bottom) ---
if prompt := st.chat_input("Type a message..."):
    
    # 1. Show User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded_file:
            st.markdown(f"*(Attached: {uploaded_file.name})*")

    # 2. Generate Response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                inputs = [prompt]
                if file_content:
                    inputs.append(file_content)
                    if "image" in file_type:
                        inputs.append("(Extract data from this image)")
                    else:
                        inputs.append(f"(Data: {file_content})")

                response = model.generate_content(inputs)
                ai_text = response.text
                
                st.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})

                # Log to Sheets
                if sheet:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([timestamp, prompt, ai_text])

            except Exception as e:
                st.error(f"Error: {e}")
