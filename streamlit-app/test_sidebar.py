"""Test script for sidebar component."""

import streamlit as st
from components.sidebar import render_sidebar

# Initialize session state
if 'gateway_url' not in st.session_state:
    st.session_state.gateway_url = 'localhost:3000'

if 'gateway_health' not in st.session_state:
    st.session_state.gateway_health = True

# Render sidebar and get selected page
selected_page = render_sidebar()

# Display selected page in main content area
st.title(f"{selected_page} Page")
st.write(f"You selected: **{selected_page}**")

# Display session state for debugging
st.subheader("Session State")
st.json({
    "gateway_url": st.session_state.gateway_url,
    "gateway_health": st.session_state.gateway_health,
    "selected_page": selected_page
})

# Test controls
st.subheader("Test Controls")
col1, col2 = st.columns(2)

with col1:
    new_url = st.text_input("Gateway URL", value=st.session_state.gateway_url)
    if st.button("Update URL"):
        st.session_state.gateway_url = new_url
        st.rerun()

with col2:
    health = st.checkbox("Gateway Online", value=st.session_state.gateway_health)
    if st.button("Update Status"):
        st.session_state.gateway_health = health
        st.rerun()
