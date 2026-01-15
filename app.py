# --- 5. SIDEBAR UI (CUSTOM SESSION MANAGER) ---
with st.sidebar:
    st.header("🗄️ Tier 1 History")
    
    # Counter
    session_count = len(st.session_state.chat_sessions)
    st.caption(f"Active Memory: {session_count}/10 Sessions")
    
    # 1. NEW CHAT BUTTON
    if st.button("➕ New Chat", use_container_width=True):
        if session_count >= 10:
            oldest = list(st.session_state.chat_sessions.keys())[0]
            del st.session_state.chat_sessions[oldest]
            st.toast(f"♻️ Limit reached: Archived '{oldest}'")
            if st.session_state.active_session_id == oldest: 
                st.session_state.active_session_id = None 
        
        st.session_state.session_counter += 1
        new_name = f"Session {st.session_state.session_counter}"
        st.session_state.chat_sessions[new_name] = []
        st.session_state.active_session_id = new_name
        st.rerun()

    st.divider()

    # 2. SESSION LIST (The "3-Dot" Replacement)
    # We loop through sessions and create a row for each
    session_names = list(st.session_state.chat_sessions.keys())
    
    if not session_names:
        st.warning("No active chats.")
    else:
        # Show newest at top
        for session_name in session_names[::-1]:
            # Create 2 columns: [ 80% Name Button ] [ 20% Delete Button ]
            col1, col2 = st.columns([0.8, 0.2])
            
            # VISUAL TRICK: Add a "🟢" if it is the currently open session
            label = session_name
            type_style = "secondary"
            if session_name == st.session_state.active_session_id:
                label = f"🟢 {session_name}"
                type_style = "primary" # Makes the active button stand out
            
            # BUTTON 1: SWITCH SESSION
            if col1.button(label, key=f"btn_{session_name}", use_container_width=True, type=type_style):
                st.session_state.active_session_id = session_name
                st.rerun()
            
            # BUTTON 2: DELETE SESSION (The requested feature)
            if col2.button("🗑️", key=f"del_{session_name}"):
                # 1. Delete from memory
                del st.session_state.chat_sessions[session_name]
                
                # 2. If we deleted the one we are looking at, switch to another one
                if st.session_state.active_session_id == session_name:
                    remaining = list(st.session_state.chat_sessions.keys())
                    st.session_state.active_session_id = remaining[-1] if remaining else None
                
                st.rerun()

    st.divider()
    
    # 3. DOWNLOAD BUTTON (Only for the active chat)
    if st.session_state.active_session_id:
        curr = st.session_state.chat_sessions[st.session_state.active_session_id]
        st.download_button("📥 Download Log", format_chat_log(st.session_state.active_session_id, curr), f"Monin_{st.session_state.active_session_id}.txt", use_container_width=True)
    
    # 4. CLEAR ALL (Nuclear Option)
    if st.button("💣 Wipe Everything", type="primary", use_container_width=True):
        st.session_state.chat_sessions = {"Session 1": []}
        st.session_state.active_session_id = "Session 1"
        st.session_state.session_counter = 1
        st.rerun()
