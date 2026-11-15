
import sys
from pathlib import Path
import streamlit as st

# Locate the AI_agent project folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from agent import MacotAgent

st.set_page_config(
    page_title="MACOT Clothing",
    page_icon="🛍️",
    layout="centered"
)

st.title("🛍️ MACOT")
st.caption("Your AI Shopping Assistant")

# Keep one agent instance across Streamlit reruns
@st.cache_resource
def load_agent():
    return MacotAgent()

agent = load_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "customer_id" not in st.session_state:
    st.session_state.customer_id = "demo_customer_001"

# Display conversation history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Handle customer messages
if prompt := st.chat_input("Ask about products or place an order..."):

    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("MACOT is typing..."):
            result = agent.chat(
                customer_id=st.session_state.customer_id,
                message=prompt
            )

            reply = result["reply"]
            st.write(reply)

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply
    })