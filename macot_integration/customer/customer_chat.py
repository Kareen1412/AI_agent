import streamlit as st

# github is a bitch literally

# Page configuration
st.set_page_config(
    page_title="MACOT Cookies",
    page_icon="🍪",
    layout="centered"
)

# Chat header
st.title("🍪 MACOT Cookies")
st.caption("Your AI Cookie Ordering Assistant")

# Initialize conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Customer message input
if prompt := st.chat_input("Type your message..."):

    # Display customer's message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.write(prompt)

    # Temporary response (we'll connect Gemini later)
    reply = "Ahla! 🍪 Welcome to MACOT! How can I help you?"

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply
    })

    with st.chat_message("assistant"):
        st.write(reply)
