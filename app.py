import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import pandas as pd

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="JSON 3.0 Chat", layout="centered")
st.title("🤖 Json 3.0 Assistant")

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. AUTHENTICATION (Safety Box) ---
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
4. If a CSV/Excel is provided, summarize it or convert row-by-row to JSON.
"""
model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=HIDDEN_PROMPT)

# --- 4. THE "PAPERCLIP" ATTACHMENT MENU ---
# We use a Popover to mimic a 'clip' menu
with st.popover("📎 Attach File", use_container_width=True):
    uploaded_file = st.file_uploader(
        "Upload Image, CSV, or Text", 
        type=["png", "jpg", "jpeg", "webp", "csv", "txt"]
    )
    
    # Process the file immediately if uploaded
    file_content = None
    file_type = ""
    
    if uploaded_file:
        file_type = uploaded_file.type
        if "image" in file_type:
            st.image(uploaded_file, caption="Ready to analyze", use_container_width=True)
            file_content = Image.open(uploaded_file)
        elif "text" in file_type or "csv" in file_type:
            string_data = uploaded_file.getvalue().decode("utf-8")
            st.text_area("File Preview", string_data, height=100)
            file_content = string_data

# --- 5. CHAT INTERFACE ---

# A. Display History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# B. Chat Input
if prompt := st.chat_input("Type a message..."):
    
    # 1. Add User Message to Chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded_file:
            st.markdown(f"*(Attached file: {uploaded_file.name})*")

    # 2. Generate AI Response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                # Prepare Inputs
                inputs = [prompt]
                
                # If file exists, add it to the AI's inputs
                if file_content:
                    inputs.append(file_content)
                    if "image" in file_type:
                        inputs.append("(Analyze this image)")
                    else:
                        inputs.append(f"(Data from file: {file_content})")

                # Call Gemini
                response = model.generate_content(inputs)
                ai_text = response.text
                
                st.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})

                # Log to Sheets (Text only)
                if sheet:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([timestamp, prompt, ai_text])

            except Exception as e:
                st.error(f"Error: {e}")


