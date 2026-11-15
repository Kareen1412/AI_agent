import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'agent'))
from agent import MacotAgent

st.set_page_config(page_title='MACOT Clothing', page_icon='🛍️', layout='centered')

st.markdown('''
<style>
/* Selected customer chat: green instead of Streamlit's default red. */
[data-testid="stSidebar"] button[kind="primary"] {
    background-color: #287447 !important;
    border-color: #287447 !important;
    color: white !important;
}
[data-testid="stSidebar"] button[kind="primary"]:hover {
    background-color: #1c5a35 !important;
    border-color: #1c5a35 !important;
    color: white !important;
}
</style>
''', unsafe_allow_html=True)

@st.cache_resource
def load_agent():
    return MacotAgent()

agent = load_agent()

if 'chats' not in st.session_state:
    st.session_state.chats = {}
if 'active_phone' not in st.session_state:
    st.session_state.active_phone = None


def open_chat(phone):
    phone = phone.strip()
    if not phone or not phone.isascii() or not phone.isdecimal():
        st.warning('Enter a phone number using digits 0–9 only.')
        return
    if phone not in st.session_state.chats:
        st.session_state.chats[phone] = []
    st.session_state.active_phone = phone


with st.sidebar:
    st.title('💬 Customer chats')
    with st.form('new_chat_form', clear_on_submit=True):
        phone_input = st.text_input('Customer phone number', placeholder='96170123456', help='Digits 0–9 only; no +, spaces, or dashes.')
        submitted = st.form_submit_button('Open chat', use_container_width=True)
    if submitted:
        open_chat(phone_input)
        if st.session_state.active_phone == phone_input.strip():
            st.rerun()

    st.divider()
    if not st.session_state.chats:
        st.caption('No chats yet. Enter a phone number to begin.')
    for phone in st.session_state.chats:
        label = f'📱 {phone}'
        if st.button(label, key=f'chat_{phone}', use_container_width=True,
                     type='primary' if phone == st.session_state.active_phone else 'secondary'):
            st.session_state.active_phone = phone
            st.rerun()
    if st.session_state.chats and st.button('Clear all chats', use_container_width=True):
        st.session_state.chats = {}
        st.session_state.active_phone = None
        st.rerun()

st.title('🛍️ MACOT')
st.caption('Your AI Shopping Assistant')

phone = st.session_state.active_phone
if phone is None:
    st.info('Enter a customer phone number in the sidebar to start chatting.')
    st.stop()

st.caption(f'Chatting as: {phone}')
messages = st.session_state.chats[phone]
for message in messages:
    with st.chat_message(message['role']):
        st.write(message['content'])

if prompt := st.chat_input('Ask about products or place an order...'):
    messages.append({'role': 'user', 'content': prompt})
    with st.chat_message('user'):
        st.write(prompt)
    with st.chat_message('assistant'):
        with st.spinner('MACOT is typing...'):
            try:
                result = agent.chat(customer_id=phone, message=prompt)
                reply = result.get('reply', 'Sorry, I could not generate a reply.')
            except Exception:
                reply = 'Sorry, something went wrong. Please try again.'
            st.write(reply)
    messages.append({'role': 'assistant', 'content': reply})
