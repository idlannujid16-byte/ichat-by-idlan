
"""NOVA V17 - AI Whiteboard and SPM Academy. Developed by Idlan."""

import asyncio
import base64
import io
import json
import re
import uuid

from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from groq import Groq
from edge_tts import Communicate
from PIL import Image
from pypdf import PdfReader
from docx import Document
from ddgs import DDGS


# ==========================================
# NOVA SETTINGS
# ==========================================

ROOT = Path(__file__).parent

st.set_page_config(
    page_title="NOVA V17",
    page_icon="🤖",
    layout="wide"
)

MODES = [
    "AI Chat",
    "Robot Voice",
    "SPM Academy"
]

SUBJECTS = [
    "Biologi",
    "Fizik",
    "Kimia",
    "Sejarah",
    "Add Math",
    "Matematik"
]

TOPICS = {
    "Biologi": [
        "Struktur sel",
        "Mitosis",
        "Fotosintesis"
    ],

    "Fizik": [
        "Hukum Ohm",
        "Gerakan",
        "Gelombang"
    ],

    "Kimia": [
        "Struktur atom",
        "Ikatan kimia",
        "Asid dan alkali"
    ],

    "Sejarah": [
        "Kemerdekaan",
        "Pembentukan Malaysia",
        "Nasionalisme"
    ],

    "Add Math": [
        "Persamaan kuadratik",
        "Fungsi kuadratik",
        "Pembezaan"
    ],

    "Matematik": [
        "Pecahan",
        "Persamaan linear",
        "Statistik"
    ]
}


# ==========================================
# SESSION STATE
# ==========================================

S = st.session_state

initial = {
    "mode": "AI Chat",
    "nav_mode": None,

    "rooms": {
        "Chat 1": []
    },

    "room": "Chat 1",

    "busy": False,

    "subject": "Add Math",

    "topic": "Persamaan kuadratik",

    "plan": None,

    "plan_id": "",

    "whiteboard_event": "",

    "interruption_reply": None,

    "notes": [],

    "answers": [],

    "voice_session": uuid.uuid4().hex,

    "voice_ack": "",

    "voice_reply": "",

    "voice_audio": "",

    "voice_error": "",

    "tool": "Home",

    "tool_nonce": 0,

    "search": False,

    "assistant_type": "General",

    "language": "Bahasa Melayu"
}

for key, value in initial.items():

    if key not in S:
        S[key] = value


# ==========================================
# GROQ API
# ==========================================

try:

    client = Groq(
        api_key=st.secrets["GROQ_API_KEY"],
        timeout=75
    )

except Exception:

    st.error(
        "Masukkan GROQ_API_KEY dalam "
        "Streamlit Cloud → App settings → Secrets."
    )

    st.stop()


MODEL = st.secrets.get(
    "CHAT_MODEL",
    "openai/gpt-oss-20b"
)

VISION = st.secrets.get(
    "VISION_MODEL",
    "meta-llama/llama-4-scout-17b-16e-instruct"
)


# ==========================================
# AI TEXT GENERATION
# ==========================================

def ask_ai(prompt, system="", image=None):

    content = prompt

    if image:

        content = [
            {
                "type": "text",
                "text": prompt
            },
            {
                "type": "image_url",
                "image_url": {
                    "url":
                        "data:image/jpeg;base64,"
                        + image
                }
            }
        ]

    reply = client.chat.completions.create(

        model=VISION if image else MODEL,

        messages=[
            {
                "role": "system",

                "content":
                    system or (
                        "You are NOVA, a helpful "
                        "assistant developed by Idlan."
                    )
            },

            {
                "role": "user",
                "content": content
            }
        ],

        max_completion_tokens=1900

    )

    return (
        reply.choices[0].message.content
        or ""
    ).strip()


# ==========================================
# TEXT TO SPEECH
# ==========================================

async def tts_async(text, language):

    voice = (
        "ms-MY-YasminNeural"

        if language == "Bahasa Melayu"

        else "en-US-JennyNeural"
    )

    data = bytearray()

    speaker = Communicate(
        text[:1100],
        voice
    )

    async for segment in speaker.stream():

        if segment["type"] == "audio":
            data.extend(segment["data"])

    return base64.b64encode(
        data
    ).decode()


def voice_for(text):

    try:

        return asyncio.run(
            tts_async(
                text,
                S.language
            )
        )

    except Exception:

        return ""


# ==========================================
# SPEECH TO TEXT
# ==========================================

def speech_to_text(
    raw,
    mime="audio/webm"
):

    if not raw or len(raw) > 10_000_000:

        raise ValueError(
            "Rakaman tiada atau terlalu besar"
        )

    if "mp4" in mime:
        extension = "m4a"

    elif "wav" in mime:
        extension = "wav"

    elif "ogg" in mime:
        extension = "ogg"

    else:
        extension = "webm"

    hints = {}

    if S.language != "Auto":

        hints["language"] = (
            "ms"

            if S.language == "Bahasa Melayu"

            else "en"
        )

    result = client.audio.transcriptions.create(

        model="whisper-large-v3-turbo",

        file=(
            "speech." + extension,
            raw
        ),

        **hints

    )

    return (
        result.text or ""
    ).strip()


# ==========================================
# IMAGE AND DOCUMENTS
# ==========================================

def image_data(upload):

    if len(upload.getvalue()) > 5_000_000:

        raise ValueError(
            "Gambar maksimum 5 MB"
        )

    with Image.open(
        io.BytesIO(upload.getvalue())
    ) as img:

        img.thumbnail((1024, 1024))

        buf = io.BytesIO()

        img.convert("RGB").save(
            buf,
            "JPEG",
            quality=82
        )

    return base64.b64encode(
        buf.getvalue()
    ).decode()


def file_text(upload):

    raw = upload.getvalue()

    if len(raw) > 10_000_000:

        raise ValueError(
            "Dokumen maksimum 10 MB"
        )

    suffix = Path(
        upload.name
    ).suffix.lower()

    if suffix == ".pdf":

        out = "\n".join(
            p.extract_text() or ""

            for p in PdfReader(
                io.BytesIO(raw)
            ).pages[:25]
        )

    elif suffix == ".docx":

        document = Document(
            io.BytesIO(raw)
        )

        out = "\n".join(
            p.text

            for p in document.paragraphs
        )

    else:

        out = raw.decode(
            "utf-8",
            errors="replace"
        )

    return out[:14000]


# ==========================================
# INTERNET SEARCH
# ==========================================

def search_web(q):

    try:

        matches = DDGS(
            timeout=12
        ).text(
            q,
            max_results=4
        ) or []

        return "\n".join(

            f"{x.get('title', '')}: "
            f"{x.get('body', '')} "
            f"({x.get('href', '')})"

            for x in matches

        )

    except Exception:

        return (
            "Carian internet tidak berjaya."
        )


# ==========================================
# NOTES STORAGE
# ==========================================

def add_note(text):

    if text.strip():

        S.notes.append(
            text.strip()
        )


# ==========================================
# LESSON PLAN VALIDATION
# ==========================================

def normalize_plan(
    result,
    subject,
    topic
):

    raw = result.strip()

    raw = raw.removeprefix(
        "```json"
    ).removesuffix(
        "```"
    ).strip()

    data = json.loads(raw)

    steps = data.get(
        "steps", []
    )

    if (
        not isinstance(steps, list)
        or not 2 <= len(steps) <= 6
    ):

        raise ValueError(
            "Bilangan langkah tidak sah"
        )

    clean = []

    for s in steps:

        if not isinstance(s, dict):

            raise ValueError(
                "Format langkah tidak sah"
            )

        kind = s.get(
            "kind", "text"
        )

        if kind not in (
            "text",
            "graph",
            "timeline",
            "atom",
            "cell",
            "circuit"
        ):

            kind = "text"

        clean.append({

            "title": str(
                s.get("title", "Langkah")
            )[:75],

            "write": str(
                s.get("write", "")
            )[:350],

            "say": str(
                s.get("say", "")
            )[:650],

            "kind": kind
        })

        if (
            not clean[-1]["write"]
            or not clean[-1]["say"]
        ):

            raise ValueError(
                "Langkah tidak lengkap"
            )

    return {
        "subject": subject,

        "topic": topic,

        "title": str(
            data.get("title", topic)
        )[:95],

        "steps": clean
    }


# ==========================================
# GENERATE LIVE WHITEBOARD LESSON
# ==========================================

def make_lesson(subject, topic):

    system = (
        "You create accurate, small SPM "
        "teaching storyboard lessons for "
        "Malaysian secondary students. "

        "Return valid JSON ONLY. "

        "Object keys: title and steps. "

        "Steps must be 3 to 5 objects, "
        "each with keys title, write, say, kind. "

        "write is 1-3 short whiteboard lines "
        "using plain Unicode text, no HTML. "

        "say is a 1-3 sentence Malay explanation "
        "of THAT SAME step. "

        "kind is text, graph, timeline, "
        "atom, cell or circuit. "

        "Math must be internally correct. "

        "For quadratic equations use "
        "x²−5x+6=0 and show correct factorization. "

        "End with a check-for-understanding "
        "question without its answer. "

        "Avoid markdown fences."
    )

    prompt = (
        "Create a short interactive "
        "voice-and-whiteboard lesson. "

        f"Subject: {subject}. "

        f"Topic: {topic}. "

        "Language: Malay."
    )

    try:

        raw = client.chat.completions.create(

            model=MODEL,

            response_format={
                "type": "json_object"
            },

            messages=[
                {
                    "role": "system",
                    "content": system
                },

                {
                    "role": "user",
                    "content": prompt
                }
            ],

            max_completion_tokens=1800

        ).choices[0].message.content

        plan = normalize_plan(
            raw,
            subject,
            topic
        )

    except Exception:

        # Fallback if the AI storyboard fails.

        plan = {

            "subject": subject,

            "topic": topic,

            "title": topic,

            "steps": [

                {
                    "title": "Pengenalan",

                    "write":
                        f"{subject} — {topic}",

                    "say":
                        f"Hai! Hari ini kita belajar "
                        f"{topic}. Kita mulakan "
                        "dengan idea paling asas.",

                    "kind": "text"
                },

                {
                    "title": "Idea utama",

                    "write":
                        "Fahami konsep → "
                        "cuba contoh → semak jawapan",

                    "say":
                        "Tengok konsep dulu. "
                        "Kemudian cuba contoh "
                        "dan semak bersama-sama.",

                    "kind": "text"
                },

                {
                    "title": "Semak faham",

                    "write":
                        "Apa perkara utama "
                        "yang awak faham?",

                    "say":
                        "Cuba jelaskan semula "
                        "menggunakan ayat sendiri. "
                        "Awak boleh hentikan "
                        "saya untuk bertanya.",

                    "kind": "text"
                }
            ]
        }

    # Generate narration for EACH teaching step.

    for step in plan["steps"]:

        step["audio"] = voice_for(
            step["say"]
        )

    return plan


# ==========================================
# EVALUATE STUDENT WORKING
# ==========================================

def grade_step(answer):

    plan = S.plan

    if not plan:

        return (
            "Mulakan pelajaran dahulu."
        )

    subject = plan["subject"]

    topic = plan["topic"]

    # Deterministic check for standard
    # quadratic equation example.

    if (
        subject == "Add Math"
        and topic == "Persamaan kuadratik"
    ):

        match = re.search(
            r"(?:x\s*=\s*)?"
            r"(-?\d+(?:\.\d+)?)"
            r"\s*(?:,|dan|atau|&)\s*"
            r"(?:x\s*=\s*)?"
            r"(-?\d+(?:\.\d+)?)",

            answer.lower()
        )

        if match:

            roots = {
                float(match[1]),
                float(match[2])
            }

            if roots == {2.0, 3.0}:

                return (
                    "✅ Jawapan akhir betul. "
                    "Bagi x² − 5x + 6 = 0, "
                    "kedua-dua punca ialah "
                    "x = 2 dan x = 3. "
                    "Pastikan langkah pemfaktoran "
                    "juga ditunjukkan."
                )

    prompt = (

        f"Subject = {subject}. "
        f"Topic = {topic}. "

        "Whiteboard steps = "

        + json.dumps(

            [
                {
                    "write": s["write"],
                    "say": s["say"]
                }

                for s in plan["steps"]
            ],

            ensure_ascii=False
        )

        + "\nStudent working:\n"

        + answer

        + "\nEvaluate each meaningful step, "
        "not only the final number. "

        "Reply in Malay with: "
        "formative score 0-4, "
        "correct steps, first incorrect step, "
        "correction with reasoning, "
        "and one follow-up hint. "

        "If insufficient work is shown, "
        "ask for the missing steps. "

        "Do not automatically award full marks."
    )

    return ask_ai(

        prompt,

        "You are a careful Malaysian SPM "
        "teacher. Evaluate consistently, "
        "explain uncertainty and never present "
        "these marks as official SPM grading."

    )


# ==========================================
# NOVA DARK THEME
# ==========================================

st.markdown("""
<style>

.stApp {
    background:
        radial-gradient(
            ellipse at 50% -15%,
            #193149,
            #0a111b 65%
        );
    color: #eaf4ff;
}

.block-container {
    max-width: 1020px;
    padding-top: 1.2rem;
}

[data-testid=stHeader] {
    background: transparent;
}

[data-testid=stSidebar] {
    background: #121d2a;
}

.stButton > button {
    border-radius: 13px;
}

[data-testid=stPopoverBody] {
    background: #172436 !important;
    border: 1px solid #364d62 !important;
    border-radius: 20px !important;
    max-height: 74vh;
    overflow-y: auto;
}

.st-key-plus .stButton button {
    min-height: 58px;
    white-space: pre-line;
    background: #20324a;
    border: 1px solid #33526e;
}

.st-key-plus .stButton button:hover {
    border-color: #7cdfff;
    background: #294763;
}

.focus-hero {
    padding: 18px 0 12px;
}

.focus-hero h2 {
    font-size: clamp(27px, 4vw, 40px);
    margin: 10px 0;
}

.focus-hero p {
    color: #96aec3;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:

    if S.nav_mode:

        S.mode = S.nav_mode
        S.nav_mode = None

    st.title("✦ NOVA")

    st.caption(
        "V17 • Developed by Idlan"
    )

    st.radio(
        "Space",
        MODES,
        key="mode"
    )

    st.selectbox(
        "Language",

        [
            "Bahasa Melayu",
            "English",
            "Auto"
        ],

        key="language"
    )

    if st.button("＋ New Chat"):

        i = 1

        while f"Chat {i}" in S.rooms:
            i += 1

        S.room = f"Chat {i}"

        S.rooms[S.room] = []

        S.voice_session = uuid.uuid4().hex

        st.rerun()

    choice = st.selectbox(

        "Chat history",

        list(S.rooms),

        index=list(S.rooms).index(
            S.room
        )
    )

    if choice != S.room:

        S.room = choice

        S.voice_session = uuid.uuid4().hex

        st.rerun()

    st.caption(
        "Voice recordings, lesson plans and "
        "history are session-only until exported."
    )


robot_mode = S.mode == "Robot Voice"

academy_mode = S.mode == "SPM Academy"


if S.get("previous_mode") != S.mode:

    S.voice_session = uuid.uuid4().hex

    S.voice_ack = ""
    S.voice_audio = ""
    S.voice_reply = ""
    S.voice_error = ""

    S.previous_mode = S.mode


st.title("✦ NOVA")

st.caption(
    "Intelligent learning companion "
    "• Developed by Idlan"
)


# ==========================================
# MODE 2 — ROBOT VOICE
# ==========================================

if robot_mode:

    robot_dir = ROOT / "voice_hologram"

    if (
        robot_dir / "index.html"
    ).is_file():

        robot = components.declare_component(

            "nova_v17_robot",

            path=str(robot_dir)
        )

        event = robot(

            audio=S.voice_audio,

            reply_id=S.voice_reply,

            ack_id=S.voice_ack,

            error=S.voice_error,

            busy=S.busy,

            session_id=S.voice_session,

            silence_ms=1500,

            threshold=0.018,

            key="nova_v17_robot_ui",

            default=None
        )

        if (
            isinstance(event, dict)

            and event.get("type") == "voice"

            and event.get("session_id")
                == S.voice_session

            and event.get("id") != S.voice_ack
        ):

            S.voice_ack = event.get(
                "id", ""
            )

            try:

                raw = base64.b64decode(

                    event.get("audio", ""),

                    validate=True
                )

                msg = speech_to_text(

                    raw,

                    event.get(
                        "mime", "audio/webm"
                    )
                )

                if not msg:

                    raise ValueError(
                        "Tiada percakapan dikesan"
                    )

                S.rooms[S.room].append({

                    "role": "user",

                    "content": msg
                })

                answer = ask_ai(

                    msg,

                    "You are NOVA, a helpful "
                    "friendly Malaysian voice "
                    "assistant. Respond naturally."
                )

                S.rooms[S.room].append({

                    "role": "assistant",

                    "content": answer
                })

                S.voice_audio = voice_for(
                    answer
                )

                S.voice_reply = (
                    uuid.uuid4().hex
                )

            except Exception as ex:

                S.voice_error = str(ex)[:120]

            st.rerun()

    else:

        st.warning(
            "Folder voice_hologram/index.html "
            "V16 diperlukan untuk Robot Voice."
        )


# ==========================================
# MODE 3 — SPM ACADEMY
# ==========================================

if academy_mode:

    st.markdown("""

    <div class="focus-hero">

        <div style="
            color:#8de2ff;
            letter-spacing:2px;
            font-size:11px;
        ">

            NOVA SPM ACADEMY
            • LIVE WHITEBOARD

        </div>

        <h2>
            What are we learning today?
        </h2>

        <p>
            Choose a subject, listen and
            work out each step with NOVA.
        </p>

    </div>

    """, unsafe_allow_html=True)

    subject = st.selectbox(

        "Subject",

        SUBJECTS,

        index=SUBJECTS.index(
            S.subject
        )
    )

    if subject != S.subject:

        S.subject = subject

        S.topic = TOPICS[subject][0]

        S.plan = None

    topic = st.selectbox(

        "Topic",

        TOPICS[S.subject],

        index=TOPICS[S.subject].index(
            S.topic
        )
    )

    if topic != S.topic:

        S.topic = topic

        S.plan = None


    # START NEW LESSON

    if st.button(

        "▶ Start Live Whiteboard",

        type="primary",

        disabled=S.busy,

        use_container_width=True
    ):

        with st.spinner(
            "Preparing lesson and "
            "step-by-step narration..."
        ):

            S.plan = make_lesson(

                S.subject,

                S.topic
            )

            S.plan_id = (
                uuid.uuid4().hex
            )

            S.whiteboard_event = ""

            S.interruption_reply = None

            S.answers = []

            lesson_note = (

                f"# {S.subject}: {S.topic}\n\n"

                + "\n\n".join(

                    f"## {i+1}. {x['title']}\n"

                    f"{x['write']}\n\n"

                    f"{x['say']}"

                    for i, x in enumerate(
                        S.plan["steps"]
                    )
                )
            )

            add_note(lesson_note)

        st.rerun()


    # DISPLAY WHITEBOARD

    if S.plan:

        st.markdown(
            "#### ✍️ NOVA Live Whiteboard"
        )

        board_dir = ROOT / "whiteboard"

        if (
            board_dir / "index.html"
        ).is_file():

            board = components.declare_component(

                "nova_v17_whiteboard",

                path=str(board_dir)
            )

            ev = board(

                plan=S.plan,

                plan_id=S.plan_id,

                language=S.language,

                reply=S.get(
                    "interruption_reply"
                ),

                key="nova_whiteboard",

                default=None
            )

            # HANDLE STUDENT INTERRUPTION

            if (
                isinstance(ev, dict)

                and ev.get("id")

                and ev["id"] != S.whiteboard_event

                and ev.get("plan_id") == S.plan_id
            ):

                S.whiteboard_event = ev["id"]

                if ev.get("type") == "question":

                    try:

                        prompt = (
                            ev.get("text") or ""
                        ).strip()

                        if not prompt:

                            voice_bytes = (
                                base64.b64decode(

                                    ev.get(
                                        "audio", ""
                                    ),

                                    validate=True
                                )
                            )

                            prompt = speech_to_text(

                                voice_bytes,

                                ev.get(
                                    "mime",
                                    "audio/webm"
                                )
                            )

                        if prompt:

                            with st.spinner(
                                "NOVA menjawab "
                                "soalan pelajar..."
                            ):

                                response = ask_ai(

                                    (
                                        f"SPM {S.subject}, "
                                        f"topic {S.topic}. "

                                        "Student interrupted "
                                        "at whiteboard step "

                                        f"{ev.get('step', 0)+1} "

                                        "and asked: "

                                        + prompt

                                        + ". Explain briefly "
                                        "and clearly in Malay."
                                    ),

                                    "You are an encouraging "
                                    "SPM teacher. Answer "
                                    "accurately and allow "
                                    "the student to resume."
                                )

                                add_note(

                                    "### Soalan pelajar\n"

                                    + prompt

                                    + "\n\n**NOVA:** "

                                    + response
                                )

                                S.interruption_reply = {

                                    "text": response,

                                    "audio": voice_for(
                                        response
                                    ),

                                    "id": uuid.uuid4().hex
                                }

                        else:

                            S.interruption_reply = {

                                "text":
                                    "Tiada suara dikesan. "
                                    "Cuba sekali lagi.",

                                "audio": "",

                                "id": uuid.uuid4().hex
                            }

                    except Exception as ex:

                        S.interruption_reply = {

                            "text":
                                "Rakaman gagal: "

                                + str(ex)[:90],

                            "audio": "",

                            "id": uuid.uuid4().hex
                        }

                    st.rerun()

        else:

            st.warning(
                "Sila cipta fail "
                "whiteboard/index.html."
            )


        # EVALUATE STUDENT WORK

        st.markdown(
            "#### 🧮 Check My Working"
        )

        work = st.text_area(

            "Tulis langkah pengiraan "
            "atau jawapan awak",

            placeholder=(
                "Contoh: x² - 5x + 6 = 0 "
                "→ (x-2)(x-3)=0 "
                "→ x=2 atau x=3"
            ),

            height=110
        )

        if st.button(

            "Evaluate My Steps",

            disabled=not work.strip()
        ):

            with st.spinner(
                "NOVA menyemak langkah..."
            ):

                feedback = grade_step(
                    work
                )

            S.answers.append(
                (work, feedback)
            )

            add_note(

                "### Kerja pelajar\n"

                + work

                + "\n\n**Maklum balas NOVA:**\n"

                + feedback
            )

        recent_answers = list(
            reversed(S.answers[-3:])
        )

        for i, (attempt, feedback) in enumerate(
            recent_answers,
            1
        ):

            with st.expander(

                f"Feedback {i}",

                expanded=i == 1
            ):

                st.write(
                    "**Your working:**",
                    attempt
                )

                st.write(
                    "**NOVA:**",
                    feedback
                )

        st.caption(
            "Pemarkahan AI ialah maklum balas "
            "formatif, bukan markah rasmi SPM."
        )


# ==========================================
# MODE 1 — STANDARD CHAT
# ==========================================

if S.mode == "AI Chat":

    for msg in S.rooms[S.room]:

        with st.chat_message(
            msg["role"]
        ):

            st.markdown(
                msg["content"]
            )


# ==========================================
# UNIVERSAL PLUS MENU
# ==========================================

with st.container(key="plus"):

    with st.popover(
        "＋",
        disabled=S.busy
    ):

        st.markdown(
            "**✦ NOVA Smart Hub**"
        )

        st.caption(
            "ADD TO NOVA"
        )

        cols = st.columns(3)

        attachments = [
            ("📷 Camera", "Camera"),
            ("🖼 Photos", "Photos"),
            ("📄 Files", "Files")
        ]

        for col, (label, slug) in zip(
            cols,
            attachments
        ):

            if col.button(

                label,

                use_container_width=True,

                key="select_" + slug
            ):

                S.tool = slug

        st.divider()

        tools = [
            [
                "🌐 Deep Search",
                "🧠 Research"
            ],

            [
                "💻 Coding",
                "🤖 Robotics"
            ],

            [
                "🎓 SPM Academy",
                "🎙 Voice Input"
            ]
        ]

        for row in tools:

            columns = st.columns(2)

            for col, label in zip(
                columns,
                row
            ):

                if col.button(

                    label,

                    use_container_width=True,

                    key="hub_" + label
                ):

                    S.tool = (
                        label.split(" ", 1)[-1]
                    )

        if S.tool != "Home":

            st.divider()

            st.markdown(
                "**" + S.tool + "**"
            )


        # CAMERA, PHOTOS, DOCUMENTS

        if S.tool in (
            "Camera",
            "Photos",
            "Files"
        ):

            if S.tool == "Camera":

                up = st.camera_input(

                    "Take photo",

                    key=(
                        f"camera{S.tool_nonce}"
                    )
                )

            else:

                up = st.file_uploader(

                    "Upload",

                    type=(
                        [
                            "jpg",
                            "png",
                            "jpeg",
                            "webp"
                        ]

                        if S.tool == "Photos"

                        else [
                            "pdf",
                            "docx",
                            "txt"
                        ]
                    ),

                    key=(
                        f"file{S.tool_nonce}"
                    )
                )

            if (
                up is not None

                and st.button(
                    "Analyze with NOVA"
                )
            ):

                with st.spinner(
                    "Reading attachment..."
                ):

                    q = (
                        "Explain this learning "
                        "material clearly in Malay."
                    )

                    if S.tool == "Files":

                        response = ask_ai(

                            q + "\n" + file_text(up)
                        )

                    else:

                        response = ask_ai(

                            q,

                            image=image_data(up)
                        )

                    S.rooms[S.room].extend([

                        {
                            "role": "user",
                            "content": q
                        },

                        {
                            "role": "assistant",
                            "content": response
                        }
                    ])

                    add_note(

                        "### Attachment analysis\n"

                        + response
                    )

                S.tool_nonce += 1

                S.tool = "Home"

                st.rerun()


        # DEEP SEARCH

        elif S.tool == "Deep Search":

            st.toggle(

                "Use web search in chat",

                key="search"
            )


        # RESEARCH / CODING / ROBOTICS

        elif S.tool in (
            "Research",
            "Coding",
            "Robotics"
        ):

            S.assistant_type = S.tool

            st.caption(
                "Active assistant: "

                + S.assistant_type
            )


        # SPM ACADEMY

        elif S.tool == "SPM Academy":

            if st.button(
                "Open SPM Academy"
            ):

                S.nav_mode = "SPM Academy"

                S.tool = "Home"

                st.rerun()


        # MANUAL VOICE INPUT

        elif S.tool == "Voice Input":

            rec = st.audio_input(

                "Record voice",

                key=(
                    f"manual{S.tool_nonce}"
                )
            )

            if (
                rec is not None

                and st.button("Send voice")
            ):

                prompt = speech_to_text(

                    rec.getvalue(),

                    "audio/wav"
                )

                if prompt:

                    answer = ask_ai(

                        prompt,

                        "You are NOVA. "
                        "Answer in Malay, simply."
                    )

                    S.rooms[S.room].extend([

                        {
                            "role": "user",
                            "content": prompt
                        },

                        {
                            "role": "assistant",
                            "content": answer
                        }
                    ])

                    add_note(

                        "### Voice question\n"

                        + prompt

                        + "\n\n" + answer
                    )

                    S.tool_nonce += 1

                    S.tool = "Home"

                    st.rerun()


        # BACK

        if S.tool != "Home":

            if st.button(
                "← Back to tools"
            ):

                S.tool = "Home"

                st.rerun()


# ==========================================
# MODE 1 MESSAGE INPUT
# ==========================================

if S.mode == "AI Chat":

    prompt = st.chat_input(
        "Message NOVA..."
    )

    if prompt:

        with st.spinner(
            "NOVA is answering..."
        ):

            system = (

                "You are NOVA, a friendly "
                "AI assistant developed by Idlan. "

                "Specialty: "

                + S.assistant_type
            )

            if S.search:

                system += (

                    "\nSearch excerpts: "

                    + search_web(prompt)
                )

            answer = ask_ai(

                prompt,

                system
            )

            S.rooms[S.room].extend([

                {
                    "role": "user",
                    "content": prompt
                },

                {
                    "role": "assistant",
                    "content": answer
                }
            ])

        st.rerun()


# ==========================================
# SAVE LESSON NOTES
# ==========================================

if S.notes:

    st.divider()

    st.subheader(
        "📒 My NOVA Notes"
    )

    notes = "\n\n---\n\n".join(
        S.notes
    )

    filename = (

        "NOVA_notes_"

        + datetime.now().strftime(
            "%Y%m%d_%H%M"
        )

        + ".md"
    )

    st.download_button(

        "⬇ Save Lesson Notes (.md)",

        data=notes.encode("utf-8"),

        file_name=filename,

        mime="text/markdown",

        use_container_width=True
    )

    with st.expander(
        "Preview saved notes"
    ):

        st.markdown(
            notes[:18000]
        )

    if st.button("Clear Notes"):

        S.notes = []

        st.rerun()


st.caption(
    "NOVA V17 • Developed by Idlan "
    "• AI teaching feedback is formative."
)
