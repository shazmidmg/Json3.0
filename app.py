import streamlit as st
import google.generativeai as genai
import os

st.title("🛠️ Robot Diagnostic Tool")

# 1. Setup API
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        st.success("✅ API Key found.")
    else:
        st.error("❌ No API Key in secrets.")
        st.stop()
except Exception as e:
    st.error(f"Error configuring API: {e}")
    st.stop()

# 2. Check Library Version
import google.generativeai
st.write(f"**Library Version:** `{google.generativeai.__version__}`")

# 3. List Available Models
st.write("### 📋 Available Models:")
try:
    # We ask Google to list all models available to your key
    models = genai.list_models()
    found_any = False
    
    for m in models:
        # We only want models that can generate content (chat)
        if 'generateContent' in m.supported_generation_methods:
            st.code(f"Model Name: {m.name}")
            found_any = True
            
    if not found_any:
        st.warning("No chat models found. Check API Key permissions.")
        
except Exception as e:
    st.error(f"❌ Error listing models: {e}")
