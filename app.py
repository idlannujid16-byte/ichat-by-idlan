
import asyncio
import base64
import html
import io
import re
import tempfile
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import streamlit as st
from streamlit.components.v1 import declare_component

from groq import Groq
from ddgs import DDGS
from edge_tts import Communicate
from pypdf import PdfReader
from docx import Document
from PIL import Image


# =====================================================
# E.D.I.T.H - AI COMMAND HUB
# =====================================================
# MODE 1: CHAT ONLY
# MODE 2: HOLOGRAPHIC VOICE CORE
# MODE 3: RADIAL SMART APP + AI BUBBLE NETWORK
#
# Features:
# - ChatGPT Style
# - Quantum Energy Flow
# - Groq Chat
# - Real Web Audio API Analyser
# - Clickable App & AI Bubbles
# - 8 App Launchers + 47 AI Skills
# - Voice Commands
# - AI Memory & Chat History
# - Internet Search
# - PDF / DOCX / TXT / Image Upload
# - AI Actions
# - Copy / Edit / Regenerate
# =====================================================


st.set_page_config(
    page_title="E.D.I.T.H",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

CHAT_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
VOICE_MODEL = "whisper-large-v3-turbo"


# =====================================================
# 1. SESSION STATE
# =====================================================

if "rooms" not in st.session_state:
    st.session_state.rooms = {
        "Chat 1": []
    }

DEFAULT_STATE = {
    "room": "Chat 1",
    "memory": "",
    "pending": False,
    "editing": None,
    "last_hub_event": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def messages():
    return st.session_state.rooms[
        st.session_state.room
    ]


def assistant_template():
    return {
        "role": "assistant",
        "content": "",
        "audio": None,
        "emotion": "neutral",
        "sources": [],
        "action": None
    }


def ask_ai(question, search=False):
    messages().append({
        "role": "user",
        "content": question,
        "force_search": search
    })

    messages().append(
        assistant_template()
    )

    st.session_state.pending = True


def new_chat():
    number = 1

    while f"Chat {number}" in st.session_state.rooms:
        number += 1

    room = f"Chat {number}"

    st.session_state.rooms[room] = []
    st.session_state.room = room
    st.session_state.editing = None


def regenerate():
    items = messages()

    if items and items[-1]["role"] == "assistant":
        items.pop()

    if items and items[-1]["role"] == "user":
        items.append(
            assistant_template()
        )

        st.session_state.pending = True


# =====================================================
# 2. LANGUAGE
# =====================================================

def detect_language(text, setting):
    if setting == "Bahasa Melayu":
        return "ms"

    if setting == "English":
        return "en"

    malay_words = {
        "saya", "awak", "boleh", "tolong",
        "apa", "macam", "mana", "nak",
        "tak", "buat", "cari", "ajar",
        "belajar", "terangkan", "projek",
        "bagaimana", "kenapa", "telefon",
        "lokasi", "berikan", "bantu",
        "tunjukkan", "dengan", "untuk"
    }

    words = set(
        re.findall(r"\w+", text.lower())
    )

    return (
        "ms"
        if words.intersection(malay_words)
        else "en"
    )


def emotion_for(text):
    value = text.lower()

    if any(word in value for word in [
        "sedih", "takziah", "sorry",
        "dukacita"
    ]):
        return "sad"

    if any(word in value for word in [
        "tahniah", "bagus", "gembira",
        "excellent", "congratulations"
    ]):
        return "happy"

    if any(word in value for word in [
        "wow", "wah", "amazing",
        "menakjubkan"
    ]):
        return "surprised"

    return "neutral"


# =====================================================
# 3. TEXT TO SPEECH
# =====================================================

async def generate_speech(text, lang):
    voice = (
        "ms-MY-YasminNeural"
        if lang == "ms"
        else "en-US-JennyNeural"
    )

    communicate = Communicate(
        text=text[:1800],
        voice=voice
    )

    result = bytearray()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            result.extend(chunk["data"])

    return bytes(result)


# =====================================================
# 4. DOCUMENT READER
# =====================================================

def read_document(upload):
    raw = upload.getvalue()

    if len(raw) > 8 * 1024 * 1024:
        raise ValueError(
            "Dokumen melebihi 8 MB."
        )

    filename = upload.name.lower()

    if filename.endswith(".pdf"):
        pdf = PdfReader(
            io.BytesIO(raw)
        )

        text = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages[:20]
        )

    elif filename.endswith(".docx"):
        document = Document(
            io.BytesIO(raw)
        )

        parts = [
            p.text
            for p in document.paragraphs
        ]

        for table in document.tables:
            for row in table.rows:
                parts.append(
                    " | ".join(
                        cell.text
                        for cell in row.cells
                    )
                )

        text = "\n".join(parts)

    else:
        text = raw.decode(
            "utf-8",
            errors="replace"
        )

    return text[:12000]


# =====================================================
# 5. INTERNET SEARCH
# =====================================================

def search_web(query):
    results = DDGS(
        timeout=12
    ).text(
        query,
        max_results=4
    ) or []

    sources = []

    for result in results:
        url = str(
            result.get("href", "")
        )

        if urlparse(url).scheme not in (
            "http",
            "https"
        ):
            continue

        sources.append({
            "title": str(
                result.get("title", "")
            )[:120],

            "url": url,

            "snippet": str(
                result.get("body", "")
            )[:450]
        })

    return sources


# =====================================================
# 6. AI ACTIONS
# =====================================================

def get_action(command):
    command = command.strip()

    # Phone
    phone = re.search(
        r"(?:telefon|panggil|call|dial)"
        r"\s+(?:nombor\s+|number\s+)?"
        r"(\+?[\d][\d\s\-()]{6,}[\d])",
        command,
        re.I
    )

    if phone:
        number = re.sub(
            r"[^\d+]",
            "",
            phone.group(1)
        )

        if re.fullmatch(
            r"\+?\d{7,15}",
            number
        ):
            return {
                "type": "dial",
                "label": "📞 Buka Phone: " + number,
                "url": "tel:" + number
            }

    # Maps
    location = re.search(
        r"(?:lokasi|pergi ke|maps? ke|"
        r"arah ke|navigate to|directions to)"
        r"\s+(.+)",
        command,
        re.I
    )

    if location:
        destination = location.group(1).strip(
            " .?!"
        )[:120]

        if destination:
            return {
                "type": "maps",
                "label": "📍 Buka Google Maps",
                "url": (
                    "https://www.google.com/maps/"
                    "search/?api=1&query="
                    + quote_plus(destination)
                )
            }

    # Search
    google = re.search(
        r"^(?:cari di google|cari web|"
        r"google|search web)"
        r"\s+(.+)",
        command,
        re.I
    )

    if google:
        keyword = google.group(1).strip()[:150]

        if keyword:
            return {
                "type": "search",
                "label": "🔎 Buka Google",
                "url": (
                    "https://www.google.com/search?q="
                    + quote_plus(keyword)
                )
            }

    return None


# =====================================================
# 7. APP LAUNCHERS
# =====================================================
# These open actual URLs in the user's browser.
# Installed native apps may open where supported.
# =====================================================

APP_BUBBLES = [
    {
        "name": "Facebook",
        "symbol": "f",
        "color": "#4e8cff",
        "url": "https://www.facebook.com"
    },
    {
        "name": "Google",
        "symbol": "G",
        "color": "#69dfff",
        "url": "https://www.google.com"
    },
    {
        "name": "ChatGPT",
        "symbol": "✳",
        "color": "#5ce5b6",
        "url": "https://chatgpt.com"
    },
    {
        "name": "Arduino IDE",
        "symbol": "∞",
        "color": "#6ceafa",
        "url": "https://www.arduino.cc/en/software"
    },
    {
        "name": "WhatsApp",
        "symbol": "✆",
        "color": "#4ce28c",
        "url": "https://web.whatsapp.com"
    },
    {
        "name": "TikTok",
        "symbol": "♪",
        "color": "#fc8db6",
        "url": "https://www.tiktok.com"
    },
    {
        "name": "YouTube",
        "symbol": "▶",
        "color": "#ff646c",
        "url": "https://www.youtube.com"
    },
    {
        "name": "Instagram",
        "symbol": "◎",
        "color": "#da8dff",
        "url": "https://www.instagram.com"
    }
]


# =====================================================
# 8. AI CHAT BUBBLES
# 47 functional AI commands
# =====================================================

AI_SKILLS = [

    ("AI Chat",
     "Perkenalkan E.D.I.T.H dan mulakan perbualan.", False),

    ("Study",
     "Bantu saya belajar topik baharu secara berperingkat.", False),

    ("Quiz",
     "Berikan 5 soalan kuiz pengetahuan am.", False),

    ("Math",
     "Ajar saya matematik dengan contoh langkah demi langkah.", False),

    ("Science",
     "Terangkan konsep sains yang menarik.", False),

    ("English",
     "Bantu saya berlatih bahasa Inggeris.", False),

    ("Translator",
     "Bantu saya menterjemah antara Melayu dan English.", False),

    ("History",
     "Terangkan satu peristiwa sejarah penting.", False),

    ("Physics",
     "Ajar saya asas fizik dengan contoh.", False),

    ("Chemistry",
     "Terangkan asas kimia secara mudah.", False),

    ("Python",
     "Ajar saya Python dengan contoh kod.", False),

    ("Arduino",
     "Cadangkan projek Arduino dengan coding dan wiring.", False),

    ("ESP32",
     "Ajar saya projek ESP32 dengan coding.", False),

    ("Debug",
     "Ajar saya cara debugging kod dan mencari error.", False),

    ("HTML",
     "Ajar saya HTML untuk membina website.", False),

    ("CSS",
     "Ajar saya CSS dan reka bentuk website.", False),

    ("JavaScript",
     "Ajar saya asas JavaScript dengan contoh.", False),

    ("C++",
     "Ajar saya asas C++.", False),

    ("IoT",
     "Cadangkan projek Internet of Things.", False),

    ("Robotics",
     "Bantu saya merancang projek robotik.", False),

    ("Sensors",
     "Terangkan jenis sensor elektronik dan kegunaannya.", False),

    ("Servo",
     "Ajar saya mengawal servo motor dengan Arduino.", False),

    ("Circuit",
     "Terangkan asas litar elektronik.", False),

    ("Wiring",
     "Berikan contoh wiring Arduino bersama sensor.", False),

    ("FYP",
     "Cadangkan projek Final Year Project teknologi.", False),

    ("AI Project",
     "Cadangkan projek AI untuk pemula.", False),

    ("Planner",
     "Buat pelan belajar selama seminggu.", False),

    ("Writing",
     "Ajar saya cara menulis dengan lebih baik.", False),

    ("Business",
     "Cadangkan idea perniagaan teknologi.", False),

    ("Prompt",
     "Ajar saya menulis prompt AI yang bagus.", False),

    ("AI News",
     "Cari berita AI terkini dengan sumber.", True),

    ("Tech News",
     "Cari berita teknologi terkini dengan sumber.", True),

    ("Research",
     "Cari perkembangan robotik terkini dengan sumber.", True),

    ("Open Source",
     "Cari projek AI open source untuk pemula.", True),

    ("Malaysia Tech",
     "Cari perkembangan teknologi Malaysia dengan sumber.", True),

    ("AI Vision",
     "Terangkan cara AI mengenali objek dalam gambar.", False),

    ("Computer",
     "Ajar saya asas komputer dan sistem operasi.", False),

    ("Database",
     "Terangkan asas SQL dan database.", False),

    ("Cybersecurity",
     "Ajar saya asas keselamatan siber yang beretika.", False),

    ("Project Ideas",
     "Berikan 10 idea projek teknologi yang kreatif.", False),

    ("Presentation",
     "Ajar saya membuat slide pembentangan profesional.", False),

    ("Resume",
     "Ajar saya menulis resume profesional.", False),

    ("Interview",
     "Latih saya menghadapi temuduga.", False),

    ("Finance",
     "Terangkan cara membuat bajet peribadi.", False),

    ("Mind Map",
     "Buat peta minda teks tentang artificial intelligence.", False),

    ("Study Test",
     "Uji pengetahuan saya dalam elektronik.", False),

    ("About E.D.I.T.H",
     "Terangkan fungsi dan kelebihan E.D.I.T.H.", False),
]

assert len(APP_BUBBLES) == 8
assert len(AI_SKILLS) == 47


# =====================================================
# 9. HTML / JS VISUAL COMPONENT
# =====================================================
# Main display:
# - 1 large E.D.I.T.H core
# - 8 golden application bubbles
# - 12 pink orbital AI bubbles
# - 47 AI skills accessible via pink node popup
# - Real Web Audio API analyser
# - Animated selected bubble
# - External clickable app links
# - AI prompt event sent to Streamlit
# =====================================================

VISUAL_HTML = r"""
<!DOCTYPE html>
<html>
<head>

<meta charset="utf-8">

<meta name="viewport"
content="width=device-width,initial-scale=1">

<style>

* {
    box-sizing:border-box;
}

html, body {
    margin:0;
    padding:0;
    background:transparent;
    color:#e8f8ff;
    font-family:system-ui,Arial,sans-serif;
    overflow-x:hidden;
}

.hub {
    width:100%;
    text-align:center;
    padding:8px 4px 12px;
    background:
        radial-gradient(
            ellipse at 50% 40%,
            rgba(20,89,182,.14),
            transparent 70%
        );
}

.heading {
    font-size:17px;
    font-weight:800;
    letter-spacing:4px;
    color:#e5faff;
    text-shadow:0 0 14px #4be7ff;
}

.subheading {
    color:#88bedf;
    font:10px monospace;
    letter-spacing:2px;
    margin:6px 0;
}

#scene {
    width:100%;
    display:block;
    cursor:pointer;
    touch-action:manipulation;
}

.status {
    font:11px monospace;
    letter-spacing:2px;
    color:#8feaff;
    margin:10px 0;
}

.legend {
    font-size:11px;
    color:#b4cae6;
    line-height:1.8;
}

.panel {
    display:none;
    text-align:left;
    background:
        linear-gradient(
            140deg,
            rgba(18,39,78,.98),
            rgba(15,20,48,.98)
        );

    border:1px solid #59bfff99;
    border-radius:16px;
    padding:14px;
    margin:10px 6px;
    box-shadow:0 0 18px #287dff22;
}

.panel h3 {
    margin:0 0 9px;
    font-size:15px;
    color:#e1f8ff;
}

.panel p {
    color:#b9c9e7;
    font-size:12px;
    line-height:1.6;
}

.action {
    display:inline-block;
    text-decoration:none;
    color:white;
    font-weight:700;
    font-size:13px;
    border:0;
    border-radius:12px;
    padding:10px 16px;
    margin:5px 5px 5px 0;

    background:
        linear-gradient(
            110deg,
            #1286d6,
            #8155dc
        );

    cursor:pointer;
}

.secondary {
    background:#263955;
    border:1px solid #6c86b5;
}

#skillGrid {
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:7px;
    max-height:235px;
    overflow-y:auto;
}

.skillBtn {
    border:1px solid #df90ff66;
    border-radius:12px;
    background:#202347;
    color:#e4d7ff;
    padding:9px 5px;
    font-size:11px;
    cursor:pointer;
    min-height:42px;
}

.skillBtn:hover {
    background:#43306d;
}

#audioPlayer {
    width:94%;
    max-width:365px;
    display:none;
    margin:12px auto 0;
}

</style>

</head>

<body>

<div class="hub">

    <div class="heading">
        E.D.I.T.H
    </div>

    <div class="subheading" id="subtitle">
        MODE 3 • AI COMMAND HUB
    </div>

    <canvas id="scene"></canvas>

    <div class="status" id="status">
        STANDBY
    </div>

    <div class="legend" id="legend">
        🟡 App / Website &nbsp; • &nbsp;
        🩷 AI Chat
    </div>

    <div id="appPanel" class="panel">
        <h3 id="appTitle"></h3>

        <p id="appDescription">
            Buka aplikasi atau website.
        </p>

        <a
            id="appLink"
            class="action"
            href="#"
            target="_blank"
            rel="noopener noreferrer"
        >
            Buka aplikasi
        </a>

        <button
            id="closeApp"
            class="action secondary"
            type="button"
        >
            Tutup
        </button>
    </div>

    <div id="skillPanel" class="panel">
        <h3 id="skillTitle">
            AI Chat
        </h3>

        <p>
            Pilih satu fungsi untuk dihantar
            kepada E.D.I.T.H.
        </p>

        <div id="skillGrid"></div>

        <button
            id="closeSkill"
            class="action secondary"
            type="button"
        >
            Tutup
        </button>
    </div>

    <audio
        id="audioPlayer"
        controls
        preload="metadata"
    ></audio>

</div>

<script>

"use strict";

// ==================================================
// STREAMLIT CUSTOM COMPONENT BRIDGE
// ==================================================

function send(type, extra = {}) {
    window.parent.postMessage(
        {
            isStreamlitMessage:true,
            type:type,
            ...extra
        },
        "*"
    );
}

function sendHeight() {
    send(
        "streamlit:setFrameHeight",
        {
            height:
                document.body.scrollHeight + 12
        }
    );
}

send(
    "streamlit:componentReady",
    {
        apiVersion:1
    }
);


// ==================================================
// DOM
// ==================================================

const canvas =
    document.getElementById("scene");

const ctx =
    canvas.getContext("2d");

const audio =
    document.getElementById("audioPlayer");

const statusEl =
    document.getElementById("status");

const appPanel =
    document.getElementById("appPanel");

const skillPanel =
    document.getElementById("skillPanel");

const skillGrid =
    document.getElementById("skillGrid");

const appTitle =
    document.getElementById("appTitle");

const appLink =
    document.getElementById("appLink");

const skillTitle =
    document.getElementById("skillTitle");

let apps = [];
let skills = [];

let mode = "neural";

let emotion = "neutral";
let busy = false;

let audioValue = "";
let speaking = false;

let analyser = null;
let audioContext = null;
let sourceNode = null;

let freq = null;
let wave = null;

let energy = 0;
let bass = 0;
let mid = 0;
let treble = 0;

let selected = null;

let w = 380;
let h = 430;

let cx = 190;
let cy = 210;

let zoom = 1;
let tick = 0;

let hitItems = [];

const APP_COUNT = 8;
const PINK_COUNT = 12;


// ==================================================
// AUDIO ANALYSER
// ==================================================

function setupAnalyser() {

    if (analyser) return;

    try {

        const AudioContextClass =
            window.AudioContext ||
            window.webkitAudioContext;

        audioContext =
            new AudioContextClass();

        analyser =
            audioContext.createAnalyser();

        analyser.fftSize = 1024;

        analyser.smoothingTimeConstant = .76;

        sourceNode =
            audioContext.createMediaElementSource(
                audio
            );

        sourceNode.connect(analyser);

        analyser.connect(
            audioContext.destination
        );

        freq =
            new Uint8Array(
                analyser.frequencyBinCount
            );

        wave =
            new Uint8Array(
                analyser.fftSize
            );

    } catch(error) {

        console.warn(
            "Audio API:",
            error
        );
    }
}

function resumeAudio() {

    setupAnalyser();

    if (
        audioContext &&
        audioContext.state === "suspended"
    ) {
        audioContext.resume();
    }
}

audio.addEventListener(
    "play",
    () => {
        resumeAudio();
        speaking = true;
        updateStatus();
    }
);

audio.addEventListener(
    "pause",
    () => {
        speaking = false;
        updateStatus();
    }
);

audio.addEventListener(
    "ended",
    () => {
        speaking = false;
        updateStatus();
    }
);

function updateStatus() {

    statusEl.textContent =
        busy
            ? "THINKING"
            : speaking
                ? "SPEAKING"
                : "STANDBY";
}

function avg(array, from, to) {

    if (!array) return 0;

    let sum = 0;
    let count = 0;

    for (let i = from; i < to; i++) {
        sum += array[i] / 255;
        count++;
    }

    return count ? sum / count : 0;
}

function updateAudio() {

    let e = 0;
    let b = 0;
    let m = 0;
    let t = 0;

    if (speaking && analyser) {

        analyser.getByteFrequencyData(freq);

        analyser.getByteTimeDomainData(wave);

        const n = freq.length;

        b = avg(
            freq,
            1,
            Math.floor(n * .10)
        );

        m = avg(
            freq,
            Math.floor(n * .10),
            Math.floor(n * .35)
        );

        t = avg(
            freq,
            Math.floor(n * .35),
            Math.floor(n * .85)
        );

        let sum = 0;

        for (let i = 0; i < wave.length; i++) {

            const value =
                (wave[i] - 128) / 128;

            sum += value * value;
        }

        e = Math.min(
            1,
            Math.sqrt(sum / wave.length) * 4
        );
    }

    const smoothing =
        speaking ? .24 : .09;

    energy += (e - energy) * smoothing;
    bass += (b - bass) * smoothing;
    mid += (m - mid) * smoothing;
    treble += (t - treble) * smoothing;
}


// ==================================================
// CANVAS SIZING
// ==================================================

function resize() {

    const rect =
        canvas.getBoundingClientRect();

    w = rect.width || 380;

    // Wider display = landscape-style dashboard.
    // Smaller display = compressed radial hub.

    if (mode === "holo") {

        h = 300;

    } else {

        h = Math.max(
            395,
            Math.min(
                610,
                w * 1.05
            )
        );
    }

    canvas.style.height =
        h + "px";

    const dpr = Math.min(
        window.devicePixelRatio || 1,
        2
    );

    canvas.width = w * dpr;
    canvas.height = h * dpr;

    ctx.setTransform(
        dpr,0,0,dpr,0,0
    );

    cx = w / 2;
    cy = h / 2;

    zoom = Math.min(
        w / 720,
        h / 600
    );

    if (mode === "holo") {
        zoom = Math.min(
            w / 420,
            1
        );
    }

    sendHeight();
}

window.addEventListener(
    "resize",
    resize
);


// ==================================================
// DRAWING HELPERS
// ==================================================

function circle(
    x, y, radius,
    fill, stroke,
    glow = 0
) {

    ctx.beginPath();

    ctx.arc(
        x,
        y,
        Math.max(1,radius),
        0,
        Math.PI * 2
    );

    if (fill) {
        ctx.fillStyle = fill;
        ctx.fill();
    }

    if (stroke) {

        ctx.strokeStyle = stroke;
        ctx.lineWidth = 2;

        ctx.shadowColor = stroke;
        ctx.shadowBlur = glow;

        ctx.stroke();

        ctx.shadowBlur = 0;
    }
}

function line(
    x1,y1,x2,y2,
    color,width=1.4
) {

    ctx.beginPath();

    ctx.moveTo(x1,y1);
    ctx.lineTo(x2,y2);

    ctx.strokeStyle = color;
    ctx.lineWidth = width;

    ctx.stroke();
}

function drawText(
    value,
    x,y,
    size,
    color="#ffffff",
    weight="bold"
) {

    ctx.fillStyle = color;

    ctx.font =
        weight + " " +
        size + "px Arial";

    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.fillText(
        value,
        x,
        y
    );
}


// ==================================================
// BUBBLE POSITIONS
// ==================================================

function appPosition(index) {

    // First app at top, clockwise.
    const angle =
        -Math.PI / 2 +
        index * Math.PI / 4;

    const radius =
        Math.min(
            w * .355,
            h * .35
        );

    return {
        x:
            cx +
            Math.cos(angle) * radius,

        y:
            cy +
            Math.sin(angle) * radius,

        a:angle
    };
}

function pinkPosition(index) {

    const angle =
        -Math.PI / 2 -
        .22 +
        index * (Math.PI * 2 / PINK_COUNT);

    const radius =
        Math.min(
            w * .465,
            h * .465
        );

    return {
        x:
            cx +
            Math.cos(angle) * radius,

        y:
            cy +
            Math.sin(angle) * radius,

        a:angle
    };
}


// ==================================================
// COLOR BASED ON EMOTION
// ==================================================

function emotionColor() {

    if (emotion === "happy") {
        return "#57f6b8";
    }

    if (emotion === "sad") {
        return "#719bff";
    }

    if (emotion === "surprised") {
        return "#e09aff";
    }

    return "#59dcff";
}


// ==================================================
// NEURAL LINES
// ==================================================

function drawConnections() {

    for (let i = 0; i < APP_COUNT; i++) {

        const p = appPosition(i);

        line(
            cx,
            cy,
            p.x,
            p.y,
            "rgba(83,176,255," +
            (.55 + energy * .4) +
            ")",
            1.7 + bass * 2
        );
    }

    for (let i = 0; i < PINK_COUNT; i++) {

        const p = pinkPosition(i);

        line(
            cx,
            cy,
            p.x,
            p.y,
            "rgba(255,178,80," +
            (.35 + energy * .5) +
            ")",
            1.2 + bass * 2
        );
    }
}


// ==================================================
// CENTRAL E.D.I.T.H CORE
// ==================================================

function drawCore() {

    const coreRadius =
        Math.max(
            35,
            Math.min(w * .14, 78)
        );

    const ringRadius =
        coreRadius +
        energy * 16 +
        Math.sin(tick * 2) * 1.2;

    for (let i = 0; i < 3; i++) {

        ctx.save();

        ctx.translate(cx,cy);

        ctx.rotate(
            tick *
            (i % 2 ? -.34 : .42)
        );

        ctx.beginPath();

        ctx.setLineDash(
            i === 1
                ? [5,9]
                : [20,12]
        );

        ctx.arc(
            0,0,
            ringRadius + i * 6,
            0,
            Math.PI * 2
        );

        ctx.strokeStyle = [
            "#59e4ff",
            "#627aff",
            "#ad86ff"
        ][i];

        ctx.lineWidth = 2;

        ctx.shadowBlur = 12;
        ctx.shadowColor = "#36cfff";

        ctx.stroke();

        ctx.restore();
    }

    const gradient =
        ctx.createRadialGradient(
            cx - 13,
            cy - 15,
            1,
            cx,
            cy,
            coreRadius
        );

    gradient.addColorStop(
        0,
        "#2aa6e9"
    );

    gradient.addColorStop(
        .45,
        "#0b427d"
    );

    gradient.addColorStop(
        1,
        "#09142b"
    );

    circle(
        cx,
        cy,
        coreRadius,
        gradient,
        "#43d8ff",
        22 + energy * 24
    );

    drawText(
        "E.D.I.T.H",
        cx,
        cy,
        Math.max(
            10,
            coreRadius * .30
        ),
        "#d8faff"
    );
}


// ==================================================
// APP BUBBLES
// ==================================================

function drawApp(index) {

    if (!apps[index]) return;

    const app = apps[index];
    const p = appPosition(index);

    const chosen =
        selected &&
        selected.kind === "app" &&
        selected.index === index;

    const baseRadius =
        Math.max(
            16,
            Math.min(
                w * .075,
                45
            )
        );

    const radius =
        baseRadius *
        (
            1 +
            energy * .15 +
            bass * .11 +
            (chosen ? .22 : 0)
        );

    const gradient =
        ctx.createRadialGradient(
            p.x - radius * .25,
            p.y - radius * .25,
            1,
            p.x,
            p.y,
            radius
        );

    gradient.addColorStop(
        0,
        "#1c2742"
    );

    gradient.addColorStop(
        1,
        "#070e20"
    );

    circle(
        p.x,
        p.y,
        radius,
        gradient,
        "#ffc463",
        chosen ? 29 : 13
    );

    drawText(
        app.symbol,
        p.x,
        p.y - radius * .22,
        Math.max(
            11,
            radius * .66
        ),
        app.color
    );

    drawText(
        app.name,
        p.x,
        p.y + radius * .43,
        Math.max(
            6,
            radius * .27
        ),
        "#ffffff"
    );

    hitItems.push({
        kind:"app",
        index:index,
        x:p.x,
        y:p.y,
        r:radius + 7
    });
}


// ==================================================
// SMALL PINK AI CHAT NODES
// ==================================================

function drawPink(index) {

    const p = pinkPosition(index);

    const chosen =
        selected &&
        selected.kind === "skill" &&
        selected.index === index;

    const radius =
        Math.max(
            8,
            Math.min(w * .024, 16)
        ) *
        (chosen ? 1.5 : 1) *
        (1 + energy * .24);

    circle(
        p.x,
        p.y,
        radius,
        "rgba(62,12,64,.70)",
        "#ff80bc",
        chosen ? 25 : 14
    );

    if (chosen) {
        drawText(
            "AI",
            p.x,
            p.y,
            Math.max(
                7,
                radius * .55
            )
        );
    }

    hitItems.push({
        kind:"skill",
        index:index,
        x:p.x,
        y:p.y,
        r:Math.max(
            15,
            radius + 7
        )
    });
}


// ==================================================
// AUDIO BARS
// ==================================================

function drawBars() {

    for (let i = 0; i < 17; i++) {

        let value = 0;

        if (
            speaking &&
            freq
        ) {
            value =
                freq[
                    Math.min(
                        freq.length - 1,
                        i * 4
                    )
                ] / 255;
        }

        const barHeight =
            3 + value * 25;

        ctx.fillStyle =
            i % 3 === 0
                ? "#b49dff"
                : "#63e7ff";

        ctx.fillRect(
            cx - 71 + i * 8.7,
            h - 7 - barHeight,
            3,
            barHeight
        );
    }
}


// ==================================================
// MODE 2 HOLOGRAM
// ==================================================

function drawHolo() {

    for (let i = 0; i < 3; i++) {

        ctx.save();

        ctx.translate(cx,cy);

        ctx.rotate(
            tick * (
                i % 2 ? -.5 : .7
            )
        );

        ctx.beginPath();

        ctx.setLineDash(
            i === 1
                ? [5,8]
                : [22,12]
        );

        ctx.arc(
            0,0,
            65 + i * 22 +
            energy * 12,
            0,
            Math.PI * 2
        );

        ctx.strokeStyle = [
            "#68eaff",
            "#b18aff",
            "#4c8eff"
        ][i];

        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.restore();
    }

    const radius =
        53 + energy * 20;

    const gradient =
        ctx.createRadialGradient(
            cx - 16,
            cy - 18,
            2,
            cx,
            cy,
            radius
        );

    gradient.addColorStop(
        0,
        "#efffff"
    );

    gradient.addColorStop(
        .28,
        "#6ceaff"
    );

    gradient.addColorStop(
        .63,
        "#5868ee"
    );

    gradient.addColorStop(
        1,
        "#171447"
    );

    circle(
        cx,
        cy,
        radius,
        gradient,
        "#51dcff",
        25 + energy * 20
    );

    drawBars();
}


// ==================================================
// FRAME LOOP
// ==================================================

function frame() {

    requestAnimationFrame(frame);

    if (document.hidden) return;

    tick += speaking ? .032 : .009;

    updateAudio();

    ctx.clearRect(
        0,0,w,h
    );

    hitItems = [];

    if (mode === "holo") {
        drawHolo();
        return;
    }

    // Background rings
    circle(
        cx,
        cy,
        Math.min(w * .36, h * .36),
        null,
        "rgba(39,116,212,.18)"
    );

    circle(
        cx,
        cy,
        Math.min(w * .46, h * .46),
        null,
        "rgba(69,122,210,.12)"
    );

    drawConnections();

    for (let i = 0; i < APP_COUNT; i++) {
        drawApp(i);
    }

    for (let i = 0; i < PINK_COUNT; i++) {
        drawPink(i);
    }

    drawCore();
    drawBars();
}


// ==================================================
// INTERACTION
// ==================================================

function pointerLocation(event) {

    const rect =
        canvas.getBoundingClientRect();

    return {
        x:event.clientX - rect.left,
        y:event.clientY - rect.top
    };
}

function findNode(event) {

    const pointer =
        pointerLocation(event);

    let best = null;
    let bestDistance = Infinity;

    for (const node of hitItems) {

        const distance =
            Math.hypot(
                pointer.x - node.x,
                pointer.y - node.y
            );

        if (
            distance <= node.r &&
            distance < bestDistance
        ) {
            best = node;
            bestDistance = distance;
        }
    }

    return best;
}

function hidePanels() {

    appPanel.style.display = "none";
    skillPanel.style.display = "none";

    sendHeight();
}


// ==================================================
// APP BUBBLE
// ==================================================

function openAppPanel(index) {

    const app = apps[index];

    if (!app) return;

    appTitle.textContent =
        app.name;

    document.getElementById(
        "appDescription"
    ).textContent =
        "Tekan butang di bawah untuk " +
        "membuka " + app.name +
        " melalui browser atau aplikasi " +
        "yang disokong.";

    appLink.href = app.url;

    appLink.textContent =
        "Buka " + app.name + " ↗";

    hidePanels();

    appPanel.style.display = "block";

    sendHeight();
}


// ==================================================
// PINK AI CHAT BUBBLE
// ==================================================

function openSkillPanel(index) {

    hidePanels();

    skillGrid.innerHTML = "";

    skillTitle.textContent =
        "AI Chat • Neural Node " +
        (index + 1);

    // 47 skills are split across 12
    // pink orbital nodes.
    //
    // Every AI skill is accessible.
    const groupCount = 12;

    skills.forEach(
        (skill, i) => {

            if (
                i % groupCount !== index
            ) {
                return;
            }

            const button =
                document.createElement(
                    "button"
                );

            button.type = "button";
            button.className = "skillBtn";

            button.textContent =
                skill.name;

            button.addEventListener(
                "click",
                () => {

                    selected = {
                        kind:"skill",
                        index:index
                    };

                    // Python owns the command.
                    send(
                        "streamlit:setComponentValue",
                        {
                            value:{
                                id:
                                    Date.now().toString() +
                                    "-" +
                                    Math.random().toString(36),

                                skill_index:i
                            }
                        }
                    );

                    skillPanel.style.display =
                        "none";

                    sendHeight();
                }
            );

            skillGrid.appendChild(
                button
            );
        }
    );

    skillPanel.style.display =
        "block";

    sendHeight();
}


// ==================================================
// CLICK
// ==================================================

canvas.addEventListener(
    "click",
    event => {

        if (mode === "holo" || busy) {
            return;
        }

        const node = findNode(event);

        if (!node) return;

        selected = {
            kind:node.kind,
            index:node.index
        };

        if (node.kind === "app") {

            openAppPanel(
                node.index
            );

        } else {

            openSkillPanel(
                node.index
            );
        }
    }
);

canvas.addEventListener(
    "pointermove",
    event => {

        if (mode === "holo") {
            return;
        }

        const node = findNode(event);

        canvas.style.cursor =
            node ? "pointer" : "default";
    }
);

document.getElementById(
    "closeApp"
).addEventListener(
    "click",
    hidePanels
);

document.getElementById(
    "closeSkill"
).addEventListener(
    "click",
    hidePanels
);


// ==================================================
// STREAMLIT RENDER
// ==================================================

window.addEventListener(
    "message",
    event => {

        if (
            !event.data ||
            event.data.type !== "streamlit:render"
        ) {
            return;
        }

        const args =
            event.data.args || {};

        apps = Array.isArray(args.apps)
            ? args.apps
            : [];

        skills = Array.isArray(args.skills)
            ? args.skills
            : [];

        mode = args.mode || "neural";

        emotion =
            args.emotion || "neutral";

        busy = !!args.busy;

        const nextAudio =
            args.audio || "";

        if (nextAudio !== audioValue) {

            audioValue = nextAudio;

            audio.pause();

            if (audioValue) {

                audio.src =
                    "data:audio/mpeg;base64," +
                    audioValue;

                audio.style.display =
                    "block";

            } else {

                audio.removeAttribute(
                    "src"
                );

                audio.style.display =
                    "none";
            }
        }

        document.getElementById(
            "subtitle"
        ).textContent =
            mode === "holo"
                ? "MODE 2 • HOLOGRAPHIC VOICE CORE"
                : "MODE 3 • AI COMMAND HUB";

        document.getElementById(
            "legend"
        ).style.display =
            mode === "holo"
                ? "none"
                : "block";

        hidePanels();
        updateStatus();
        resize();
    }
);

resize();
frame();
sendHeight();

</script>
</body>
</html>
"""


# =====================================================
# 10. REGISTER CUSTOM COMPONENT
# =====================================================

@st.cache_resource
def build_component():
    directory = (
        Path(tempfile.gettempdir())
        / "edith_radial_command_hub_v1"
    )

    directory.mkdir(
        parents=True,
        exist_ok=True
    )

    (directory / "index.html").write_text(
        VISUAL_HTML,
        encoding="utf-8"
    )

    return declare_component(
        "edith_radial_command_hub_v1",
        path=str(directory)
    )


radial_component = build_component()


def show_command_hub(
    view,
    audio=None,
    emotion="neutral"
):
    encoded = (
        base64.b64encode(audio).decode("ascii")
        if audio
        else ""
    )

    frontend_skills = [
        {
            "name": item[0]
        }
        for item in AI_SKILLS
    ]

    return radial_component(
        mode=view,
        audio=encoded,
        emotion=emotion,
        apps=APP_BUBBLES,
        skills=frontend_skills,
        busy=st.session_state.pending,
        default=None,
        key="edith_mode_3_hub"
    )


# =====================================================
# 11. SIDEBAR
# =====================================================

with st.sidebar:

    st.header(
        "⚙️ E.D.I.T.H Settings"
    )

    mode = st.radio(
        "AI Mode",
        [
            "Mode 1 - Chat Only",
            "Mode 2 - Holographic Voice Core",
            "Mode 3 - AI Command Hub"
        ]
    )

    language = st.selectbox(
        "Language",
        [
            "Auto Detect",
            "Bahasa Melayu",
            "English"
        ]
    )

    theme = st.selectbox(
        "Theme",
        [
            "Dark",
            "Light",
            "Ocean Blue"
        ]
    )

    ai_tool = st.selectbox(
        "AI Tools",
        [
            "General Chat",
            "Coding Assistant",
            "Study & Quiz",
            "Translator"
        ]
    )

    internet = st.checkbox(
        "🌐 Internet Search"
    )

    st.divider()

    st.subheader(
        "🧠 AI Memory"
    )

    st.text_area(
        "Apa E.D.I.T.H perlu ingat?",
        key="memory",
        height=100
    )

    if st.button(
        "Clear Memory"
    ):
        st.session_state.memory = ""
        st.rerun()

    st.caption(
        "Memory disimpan untuk "
        "sesi ini sahaja."
    )

    st.divider()

    if st.button(
        "➕ New Chat",
        use_container_width=True,
        disabled=st.session_state.pending
    ):
        new_chat()
        st.rerun()

    room_names = list(
        st.session_state.rooms
    )

    selected_room = st.selectbox(
        "Chat History",
        room_names,
        index=room_names.index(
            st.session_state.room
        ),
        disabled=st.session_state.pending
    )

    if selected_room != st.session_state.room:
        st.session_state.room = selected_room
        st.session_state.editing = None
        st.rerun()


# =====================================================
# 12. QUANTUM ENERGY FLOW CSS
# =====================================================

if theme == "Light":

    background = "#f6f9ff"
    foreground = "#18233c"

    user_background = "#dceafe"
    user_foreground = "#14213d"

    sidebar_background = (
        "rgba(245,249,255,.96)"
    )

    input_background = (
        "rgba(255,255,255,.96)"
    )

elif theme == "Ocean Blue":

    background = "#07162d"
    foreground = "#e7f7ff"

    user_background = "#174574"
    user_foreground = "#ffffff"

    sidebar_background = (
        "rgba(5,23,47,.96)"
    )

    input_background = (
        "rgba(15,47,84,.96)"
    )

else:

    background = "#080f20"
    foreground = "#edf6ff"

    user_background = "#354b72"
    user_foreground = "#ffffff"

    sidebar_background = (
        "rgba(9,16,33,.96)"
    )

    input_background = (
        "rgba(22,34,60,.96)"
    )


st.markdown(
    f"""
<style>

.stApp {{
    background:
        radial-gradient(
            ellipse at 18% 17%,
            rgba(48,145,245,.15),
            transparent 42%
        ),
        radial-gradient(
            ellipse at 85% 64%,
            rgba(146,68,230,.15),
            transparent 42%
        ),
        {background};

    color:{foreground};
}}

.stApp::before {{

    content:"";

    position:fixed;
    inset:-15%;
    pointer-events:none;

    background:
        radial-gradient(
            ellipse at 20% 42%,
            rgba(38,188,255,.16),
            transparent 35%
        ),
        radial-gradient(
            ellipse at 80% 35%,
            rgba(167,85,247,.15),
            transparent 36%
        );

    animation:
        quantumEnergy 19s
        ease-in-out infinite alternate;
}}

@keyframes quantumEnergy {{

    from {{
        transform:
            translate(-2%,0%) scale(1);
    }}

    to {{
        transform:
            translate(2%,-2%) scale(1.06);
    }}
}}

[data-testid="stHeader"] {{
    background:transparent;
}}

[data-testid="stSidebar"] > div:first-child {{
    background:{sidebar_background};
}}

.stApp h1,
.stApp h2,
.stApp h3 {{
    color:{foreground};
}}

[data-testid="stChatMessage"] {{
    background:transparent;
    border:0;
    box-shadow:none;
    border-radius:0;
    padding:14px 4px;
    margin-bottom:6px;
}}

[data-testid="stChatMessageContent"] {{
    line-height:1.7;
}}

[data-testid="stChatInput"] > div {{
    background:{input_background};
    border-radius:22px;
    border:
        1px solid rgba(128,171,246,.25);
}}

.stButton > button {{
    border-radius:12px;
}}

@media(max-width:600px) {{

    .block-container {{
        padding-left:.7rem;
        padding-right:.7rem;
        padding-top:1rem;
    }}
}}

@media(prefers-reduced-motion:reduce) {{

    .stApp::before {{
        animation:none;
    }}
}}

</style>
""",
    unsafe_allow_html=True
)


# =====================================================
# 13. MAIN APP
# =====================================================

st.title(
    "🤖 E.D.I.T.H"
)

st.caption(
    "Your Personal AI Assistant"
)

voice_mode = (
    mode.startswith("Mode 2")
    or mode.startswith("Mode 3")
)

hub_mode = mode.startswith(
    "Mode 3"
)


# =====================================================
# 14. RADIAL COMMAND HUB
# =====================================================

if voice_mode:

    last_audio_message = next(
        (
            message
            for message in reversed(messages())
            if (
                message["role"] == "assistant"
                and message.get("audio")
            )
        ),
        None
    )

    last_audio = (
        last_audio_message.get("audio")
        if last_audio_message
        else None
    )

    last_emotion = (
        last_audio_message.get(
            "emotion",
            "neutral"
        )
        if last_audio_message
        else "neutral"
    )

    event = show_command_hub(
        view=(
            "neural"
            if hub_mode
            else "holo"
        ),
        audio=last_audio,
        emotion=last_emotion
    )

    # Handle genuine clickable AI commands
    if (
        hub_mode
        and not st.session_state.pending
        and isinstance(event, dict)
    ):

        event_id = event.get("id")
        skill_index = event.get(
            "skill_index"
        )

        if (
            isinstance(event_id, str)
            and event_id
            and event_id != st.session_state.last_hub_event
            and type(skill_index) is int
            and 0 <= skill_index < len(AI_SKILLS)
        ):

            st.session_state.last_hub_event = event_id

            name, prompt, requires_search = (
                AI_SKILLS[skill_index]
            )

            ask_ai(
                prompt,
                search=requires_search
            )

            st.rerun()


if hub_mode:

    st.caption(
        "🟡 Bubble kuning: buka aplikasi. "
        "🩷 Bubble pink: pilih fungsi AI Chat."
    )


# =====================================================
# 15. GROQ CONNECTION
# =====================================================

try:

    client = Groq(
        api_key=st.secrets[
            "GROQ_API_KEY"
        ]
    )

except (
    KeyError,
    FileNotFoundError,
    ValueError
):

    st.error(
        "GROQ_API_KEY tidak dijumpai. "
        "Semak Streamlit Cloud Secrets."
    )

    st.stop()


# =====================================================
# 16. FILE UPLOAD
# =====================================================

with st.expander(
    "📎 Upload File / Image"
):

    document = st.file_uploader(
        "PDF / Word / TXT",
        type=[
            "pdf",
            "docx",
            "txt"
        ]
    )

    uploaded_image = st.file_uploader(
        "JPG / PNG",
        type=[
            "jpg",
            "jpeg",
            "png"
        ]
    )


document_context = ""

if document is not None:

    try:

        document_context = read_document(
            document
        )

        if document_context.strip():

            st.success(
                "Dokumen berjaya dibaca."
            )

        else:

            st.warning(
                "Tiada teks yang boleh dibaca."
            )

    except Exception as error:

        st.warning(
            "Document error: "
            + type(error).__name__
        )


image_bytes = None

if uploaded_image is not None:

    raw = uploaded_image.getvalue()

    if len(raw) <= 4 * 1024 * 1024:

        image_bytes = raw

        st.image(
            image_bytes,
            width=250,
            caption="Uploaded Image"
        )

    else:

        st.warning(
            "Gambar melebihi 4 MB."
        )


# =====================================================
# 17. MODE 3 VOICE COMMANDS
# =====================================================

if hub_mode:

    with st.expander(
        "🎙️ Voice Commands + AI Actions"
    ):

        recording = st.audio_input(
            "Rakam arahan suara E.D.I.T.H",
            sample_rate=16000
        )

        if st.button(
            "🎙️ Hantar Arahan Suara",
            disabled=(
                st.session_state.pending
                or recording is None
            )
        ):

            try:

                sound = recording.getvalue()

                if not sound:

                    st.warning(
                        "Rakaman kosong."
                    )

                elif len(sound) > 20 * 1024 * 1024:

                    st.warning(
                        "Rakaman terlalu besar."
                    )

                else:

                    with st.spinner(
                        "Transcribing voice..."
                    ):

                        result = (
                            client.audio.transcriptions.create(
                                model=VOICE_MODEL,
                                file=(
                                    "voice.wav",
                                    sound
                                ),
                                response_format="json"
                            )
                        )

                    transcript = (
                        result.text or ""
                    ).strip()

                    if transcript:

                        ask_ai(transcript)
                        st.rerun()

                    else:

                        st.warning(
                            "Tiada arahan dikesan."
                        )

            except Exception as error:

                st.error(
                    "Voice Command error: "
                    + type(error).__name__
                )

        st.caption(
            "Contoh: Telefon 0123456789 | "
            "Lokasi KLCC | "
            "Cari di Google robot Arduino"
        )


# =====================================================
# 18. REGENERATE
# =====================================================

st.caption(
    f"💬 {st.session_state.room} • {ai_tool}"
)

if st.button(
    "🔄 Regenerate Last",
    disabled=(
        st.session_state.pending
        or not messages()
        or messages()[-1]["role"] != "assistant"
    )
):

    regenerate()
    st.rerun()


# =====================================================
# 19. CHAT HISTORY
# =====================================================

for i, message in enumerate(messages()):

    if (
        st.session_state.pending
        and i == len(messages()) - 1
    ):
        continue

    role = message["role"]

    with st.chat_message(
        role,
        avatar=(
            "👤"
            if role == "user"
            else "🤖"
        )
    ):

        if (
            role == "user"
            and st.session_state.editing == i
        ):

            edited = st.text_area(
                "Edit Message",
                value=message["content"],
                key=(
                    f"edit_{st.session_state.room}_{i}"
                )
            )

            left, right = st.columns(2)

            if left.button(
                "✅ Save & Send",
                key=f"save_{i}"
            ):

                if edited.strip():

                    st.session_state.rooms[
                        st.session_state.room
                    ] = messages()[:i]

                    st.session_state.editing = None

                    ask_ai(
                        edited.strip()
                    )

                    st.rerun()

            if right.button(
                "Cancel",
                key=f"cancel_{i}"
            ):

                st.session_state.editing = None
                st.rerun()

        elif role == "user":

            safe_text = html.escape(
                message["content"]
            ).replace(
                "\n",
                "<br>"
            )

            st.markdown(
                f"""
<div style="
    display:flex;
    justify-content:flex-end;
    width:100%;
">
    <div style="
        background:{user_background};
        color:{user_foreground};
        padding:12px 17px;
        border-radius:19px 19px 5px 19px;
        max-width:88%;
        line-height:1.6;
        overflow-wrap:anywhere;
    ">
        {safe_text}
    </div>
</div>
""",
                unsafe_allow_html=True
            )

            if st.button(
                "✏️ Edit",
                key=f"edit_message_{i}",
                disabled=st.session_state.pending
            ):

                st.session_state.editing = i
                st.rerun()

        else:

            st.markdown(
                message["content"]
                or "_(Tiada jawapan)_"
            )

            with st.popover(
                "📋 Copy Answer"
            ):

                st.code(
                    message["content"],
                    language=None
                )

            if message.get("sources"):

                with st.expander(
                    "🌐 Sources"
                ):

                    for source in message["sources"]:

                        st.link_button(
                            source["title"] or "Source",
                            source["url"]
                        )

            action = message.get("action")

            if action:

                st.markdown(
                    "**AI Action — sahkan dahulu:**"
                )

                if action["type"] == "dial":

                    safe_url = html.escape(
                        action["url"],
                        quote=True
                    )

                    safe_label = html.escape(
                        action["label"]
                    )

                    st.markdown(
                        '<a href="'
                        + safe_url
                        + '" style="'
                        + 'display:inline-block;'
                        + 'padding:10px 15px;'
                        + 'border-radius:12px;'
                        + 'background:#1680ae;'
                        + 'text-decoration:none;'
                        + 'color:white;">'
                        + safe_label
                        + '</a>',
                        unsafe_allow_html=True
                    )

                    st.caption(
                        "Buka dialer sahaja. "
                        "Tekan Call sendiri."
                    )

                else:

                    st.link_button(
                        action["label"],
                        action["url"]
                    )

            if (
                voice_mode
                and message.get("audio")
            ):

                with st.expander(
                    "🔊 Previous Response Audio"
                ):

                    st.audio(
                        message["audio"],
                        format="audio/mp3"
                    )


# =====================================================
# 20. CHAT INPUT
# =====================================================

question = st.chat_input(
    "Message E.D.I.T.H...",
    disabled=st.session_state.pending
)

if question and question.strip():

    ask_ai(
        question.strip()
    )

    st.rerun()


# =====================================================
# 21. GENERATE GROQ RESPONSE
# =====================================================

if st.session_state.pending:

    chat_data = messages()

    reply_index = len(chat_data) - 1

    user_message = chat_data[
        reply_index - 1
    ]

    user_question = user_message[
        "content"
    ]

    lang = detect_language(
        user_question,
        language
    )

    answer = ""
    sources = []

    action = (
        get_action(user_question)
        if hub_mode
        else None
    )

    with st.chat_message(
        "assistant",
        avatar="🤖"
    ):

        output = st.empty()

        try:

            language_rules = {

                "Auto Detect":
                    "Reply in the user's language.",

                "Bahasa Melayu":
                    "Always reply in Bahasa Melayu.",

                "English":
                    "Always reply in English."
            }

            tool_rules = {

                "General Chat":
                    "Answer clearly and accurately.",

                "Coding Assistant":
                    "Help with coding, Arduino, "
                    "ESP32 and debugging. "
                    "Provide clear examples.",

                "Study & Quiz":
                    "Teach step by step "
                    "and give useful quizzes.",

                "Translator":
                    "Translate accurately "
                    "between Malay and English."
            }

            system = (
                "Your official name is E.D.I.T.H. "
                "You are a helpful personal AI assistant. "
                "Do not introduce yourself under another name. "
                + language_rules[language]
                + " "
                + tool_rules[ai_tool]
            )

            system += (
                " Never claim you made a phone call, "
                "opened an app or performed an action "
                "unless it actually happened. "
                "Users must confirm external actions."
            )

            if st.session_state.memory.strip():

                system += (
                    "\nSession memory "
                    "(untrusted notes):\n"
                    + st.session_state.memory[:1500]
                )

            if document_context.strip():

                system += (
                    "\nUploaded document text "
                    "(untrusted reference data):\n"
                    + document_context
                )

            # SEARCH ENGINE

            should_search = (
                internet
                or user_message.get(
                    "force_search",
                    False
                )
            )

            if should_search:

                try:

                    sources = search_web(
                        user_question
                    )

                    if sources:

                        system += (
                            "\nWeb snippets "
                            "(untrusted reference data):\n"
                        )

                        for n, source in enumerate(
                            sources,
                            1
                        ):

                            system += (
                                f"[{n}] "
                                f"{source['title']} | "
                                f"{source['url']} | "
                                f"{source['snippet']}\n"
                            )

                        system += (
                            "Use source numbers "
                            "when appropriate. "
                            "Do not invent sources."
                        )

                    else:

                        st.warning(
                            "Tiada hasil carian internet."
                        )

                except Exception as error:

                    st.warning(
                        "Internet Search error: "
                        + type(error).__name__
                    )

            # PREPARE CHAT HISTORY

            recent = [
                {
                    "role": item["role"],
                    "content": item["content"]
                }
                for item in chat_data[:-1]
            ][-10:]

            model = CHAT_MODEL

            # IMAGE UNDERSTANDING

            if image_bytes is not None:

                picture = Image.open(
                    io.BytesIO(image_bytes)
                )

                picture.thumbnail(
                    (1100, 1100)
                )

                buffer = io.BytesIO()

                picture.convert("RGB").save(
                    buffer,
                    format="JPEG",
                    quality=78
                )

                encoded = base64.b64encode(
                    buffer.getvalue()
                ).decode("ascii")

                recent[-1] = {

                    "role": "user",

                    "content": [
                        {
                            "type": "text",
                            "text": user_question
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/jpeg;base64,"
                                    + encoded
                                )
                            }
                        }
                    ]
                }

                model = VISION_MODEL

            # GROQ STREAMING

            stream = client.chat.completions.create(

                model=model,

                messages=[
                    {
                        "role": "system",
                        "content": system
                    }
                ] + recent,

                max_completion_tokens=900,

                stream=True
            )

            for part in stream:

                token = (
                    part.choices[0].delta.content
                    or ""
                )

                if token:

                    answer += token

                    chat_data[reply_index][
                        "content"
                    ] = answer

                    output.markdown(
                        answer + "▌"
                    )

            output.markdown(
                answer
                or "_(Tiada jawapan)_"
            )

            # SAVE RESPONSE

            chat_data[reply_index][
                "content"
            ] = answer

            chat_data[reply_index][
                "sources"
            ] = sources

            chat_data[reply_index][
                "action"
            ] = action

            emotion = emotion_for(
                answer
            )

            chat_data[reply_index][
                "emotion"
            ] = emotion

            # VOICE OUTPUT

            if voice_mode and answer.strip():

                try:

                    with st.spinner(
                        "Generating E.D.I.T.H Voice..."
                    ):

                        voice_bytes = asyncio.run(
                            generate_speech(
                                answer,
                                lang
                            )
                        )

                    if voice_bytes:

                        chat_data[reply_index][
                            "audio"
                        ] = voice_bytes

                except Exception as error:

                    st.warning(
                        "Voice unavailable: "
                        + type(error).__name__
                    )

            # WEB SOURCES

            if sources:

                with st.expander(
                    "🌐 Sources"
                ):

                    for source in sources:

                        st.link_button(
                            source["title"] or "Source",
                            source["url"]
                        )

            if action:

                st.info(
                    "AI Action tersedia dalam chat. "
                    "Sahkan tindakan sendiri."
                )

        except Exception as error:

            st.error(
                "E.D.I.T.H gagal menjawab. "
                "Semak Groq API key, "
                "model atau kuota."
            )

            st.caption(
                "Error type: "
                + type(error).__name__
            )

            if not answer:

                chat_data[reply_index][
                    "content"
                ] = (
                    "Ralat AI. "
                    "Cuba Regenerate Last."
                )

        finally:

            st.session_state.pending = False

    # Re-enable chat input
    st.rerun()
