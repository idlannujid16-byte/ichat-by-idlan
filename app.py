
import streamlit as st
from groq import Groq

# ==================================
# ichat by idlan - CLOUD VERSION
# ==================================

st.set_page_config(
    page_title="ichat by idlan",
    page_icon="🤖",
    layout="centered"
)

MODEL = "openai/gpt-oss-20b"

# ==================================
# SIDEBAR
# ==================================

with st.sidebar:
    st.title("⚙️ AI Settings")

    language = st.selectbox(
        "Language",
        ["Auto Detect", "Bahasa Melayu", "English"]
    )

    theme = st.selectbox(
        "Theme",
        ["Dark", "Light", "Ocean Blue"]
    )

    if st.button("➕ New Chat"):
        st.session_state.messages = []
        st.rerun()

    st.caption("ichat by idlan - Cloud Edition")


# ==================================
# THEME
# ==================================

colors = {
    "Dark": ("#0f172a", "#ffffff"),
    "Light": ("#ffffff", "#111827"),
    "Ocean Blue": ("#dbeafe", "#172554")
}

bg, fg = colors[theme]

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {bg};
        color: {fg};
    }}
    .stApp h1 {{
        color: {fg};
    }}
    </style>
    """,
    unsafe_allow_html=True
)


# ==================================
# AI SETTINGS
# ==================================

language_rules = {
    "Auto Detect":
        "Respond in the language used by the user.",
    "Bahasa Melayu":
        "Always respond in Bahasa Melayu.",
    "English":
        "Always respond in English."
}

system_prompt = (
    "Your name is ichat by idlan. "
    "Never introduce yourself by another name. "
    "You are a friendly and helpful AI assistant. "
    "You can explain programming including "
    "Python, Arduino and ESP32. "
    "Do not claim to execute code. "
    + language_rules[language]
)


# ==================================
# CHAT HISTORY
# ==================================

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("🤖 ichat by idlan")
st.caption("Your Personal AI Assistant | Cloud Edition")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ==================================
# GROQ CONNECTION
# ==================================

try:
    api_key = st.secrets["GROQ_API_KEY"]
except (KeyError, FileNotFoundError):
    st.warning(
        "GROQ_API_KEY belum dimasukkan. "
        "Kita akan buat pada Langkah 4."
    )
    st.stop()

client = Groq(api_key=api_key)


# ==================================
# CHAT INPUT
# ==================================

question = st.chat_input("Ask me anything...")

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.markdown(question)

    history = st.session_state.messages[-10:]

    messages = [
        {"role": "system", "content": system_prompt}
    ] + history

    with st.chat_message("assistant"):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.5,
                max_completion_tokens=700
            )

            answer = (
                response.choices[0].message.content
                or "Sorry, no response was generated."
            )

            st.markdown(answer)

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer
            })

        except Exception as error:
            st.error(
                "AI tidak dapat menjawab sekarang. "
                "Semak API key atau had penggunaan Groq."
            )
            st.caption(type(error).__name__)
