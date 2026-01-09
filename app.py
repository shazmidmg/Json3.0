import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="JSON 3.0 Chat", layout="centered")
st.title("🤖 JSON 3.0 Assistant")

# Initialize Chat History in Memory
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. AUTHENTICATION (The "Safety Box") ---
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
1. If the user provides data, convert it to clean JSON.
2. If the user asks a question, answer normally and helpfully.
3. If an image is provided, extract all relevant data from it into JSON.
"""
model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=HIDDEN_PROMPT)

# --- 4. SIDEBAR (File Uploads) ---
with st.sidebar:
    st.header("Upload Files")
    uploaded_file = st.file_uploader("Attach an image (Receipt, Screenshot)", type=["png", "jpg", "jpeg", "webp"])
    image_data = None
    if uploaded_file:
        image_data = Image.open(uploaded_file)
        st.image(image_data, caption="Attached Image", use_container_width=True)

# --- 5. CHAT INTERFACE ---

# A. Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# B. Waiting for new input
if prompt := st.chat_input("Paste text or ask a question..."):
    
    # 1. Show User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. Generate AI Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Prepare the input (Text + Image if available)
                inputs = [prompt]
                if image_data:
                    inputs.append(image_data)
                    st.markdown("*(Analyzing image...)*")

                # Call Gemini
                response = model.generate_content(inputs)
                ai_text = response.text
                
                # Show Response
                st.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})

                # Log to Google Sheet (Text only for now)
                if sheet:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([timestamp, prompt, ai_text])

            except Exception as e:
                st.error(f"Error: {e}")
