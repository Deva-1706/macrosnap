import json

import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
)


MODEL_NAME = "gemini-3.5-flash"


st.set_page_config(
    page_title="MacroSnap",
    page_icon="🥗",
    layout="centered",
)


# -----------------------------
# API KEYS / TWILIO SETTINGS
# -----------------------------

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]


# -----------------------------
# CLIENTS
# -----------------------------

@st.cache_resource
def get_gemini_client():
    return genai.Client(
        api_key=GEMINI_API_KEY
    )


@st.cache_resource
def get_twilio_client():
    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
    )


gemini_client = get_gemini_client()
twilio_client = get_twilio_client()


# -----------------------------
# CHAT DISPLAY
# -----------------------------

def render_message(message):
    with st.chat_message(message["role"]):

        if message["kind"] == "text":
            st.write(message["content"])

        elif message["kind"] == "image":
            st.image(
                message["content"],
                use_container_width=True,
            )


def add_message(role, kind, content):
    message = {
        "role": role,
        "kind": kind,
        "content": content,
    }

    st.session_state.messages.append(message)

    render_message(message)


# -----------------------------
# GEMINI
# -----------------------------

def ask_gemini(parts):
    try:
        response = st.session_state.chat.send_message(parts)
        return response.text

    except Exception as error:
        return (
            "Sorry, something went wrong while analyzing "
            f"your meal: {error}"
        )


# -----------------------------
# WHATSAPP
# -----------------------------

def clean_whatsapp_text(text):
    if not text:
        return "No nutrition summary available."

    text = " ".join(text.split())

    if len(text) > 1500:
        return text[:1500] + "..."

    return text


def send_whatsapp(to_number, user_name, summary):
    try:
        content_variables = json.dumps(
            {
                "1": user_name,
                "2": clean_whatsapp_text(summary),
            },
            ensure_ascii=False,
        )

        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            content_sid=TWILIO_CONTENT_SID,
            content_variables=content_variables,
        )

        return True, message.sid

    except Exception as error:
        return False, str(error)

# -----------------------------
# ONBOARDING
# -----------------------------

if "onboarded" not in st.session_state:

    st.title("🥗 MacroSnap")

    st.caption(
        "Snap it. Track it. Understand it."
    )

    st.subheader("Let's get started!")

    name = st.text_input(
        "What's your name?",
        value="Devanath N",
    )

    whatsapp_number = st.text_input(
        "What's your WhatsApp number?",
        placeholder="+91XXXXXXXXXX",
    )

    if st.button(
        "Start chatting 🚀",
        use_container_width=True,
    ):

        if not name.strip():

            st.warning(
                "Please enter your name."
            )

        elif not whatsapp_number.strip():

            st.warning(
                "Please enter your WhatsApp number."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.whatsapp_number = (
                whatsapp_number.strip()
            )

            st.session_state.chat = (
                gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# -----------------------------
# MAIN HEADER
# -----------------------------

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center",
)


with header_col:

    st.title("🥗 MacroSnap")


with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 2
    )

    if st.button(
        "📤 Send to WhatsApp",
        disabled=send_disabled,
        use_container_width=True,
    ):

        with st.spinner(
            "Summarizing your day..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        success, info = send_whatsapp(
            st.session_state.whatsapp_number,
            st.session_state.name,
            summary,
        )

        if success:

            st.success(
                "Sent! Check your WhatsApp 📲"
            )

        else:

            st.error(
                f"Couldn't send that: {info}"
            )


# -----------------------------
# LOGIN INFORMATION
# -----------------------------

st.caption(
    f"Logged in as {st.session_state.name} - "
    f"updates go to {st.session_state.whatsapp_number}"
)


# -----------------------------
# WELCOME / CHAT HISTORY
# -----------------------------

if not st.session_state.messages:

    welcome_message = (
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )

    add_message(
        "assistant",
        "text",
        welcome_message,
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# -----------------------------
# CHAT INPUT + IMAGE UPLOAD
# -----------------------------

user_input = st.chat_input(
    "Ask a question, or attach a photo of your meal",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png",
    ],
)


if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text.strip()

    parts = []


    # -------------------------
    # PHOTO
    # -------------------------

    if photo is not None:

        photo_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            photo_bytes,
        )

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type,
            )
        )


    # -------------------------
    # TEXT
    # -------------------------

    if text:

        add_message(
            "user",
            "text",
            text,
        )

        parts.append(text)


    # -------------------------
    # PHOTO ONLY
    # -------------------------

    elif photo is not None:

        parts.append(
            "What is this meal? "
            "Give me the estimated calories "
            "and protein, carbs, and fat."
        )


    # -------------------------
    # GEMINI RESPONSE
    # -------------------------

    if parts:

        with st.spinner(
            "🥗 Crunching the numbers..."
        ):

            answer = ask_gemini(parts)

        add_message(
            "assistant",
            "text",
            answer,
        )