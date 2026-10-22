
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
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from docx import Document


# ============================================================
# E.D.I.T.H - CRYSTAL LOGO + ACRYLIC FULL EDITION
#
# MODE 1 - CHAT ONLY
# MODE 2 - HOLOGRAPHIC VOICE CORE
# MODE 3 - RADIAL AI COMMAND HUB
#
# 8 APP BUBBLES + 47 AI SKILLS = 55 FUNCTIONS
#
# Features:
# - Custom Crystal logo
# - Crystal Acrylic Glass Chat
# - Quantum Energy Flow background
# - Groq AI Chat
# - Yasmin / Jenny voices
# - Voice Commands
# - Real Web Audio API Reactive Animation
# - Interactive app and AI bubbles
# - Chat History and Session Memory
# - PDF / Word / TXT / Image Upload
# - Internet Search
# - AI Actions
# - Copy / Edit / Regenerate
#
# No Stop Generating button
# ============================================================


# ============================================================
# 1. LOGO SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "edith_logo.png"

LOGO_EXISTS = LOGO_PATH.is_file()

if LOGO_EXISTS:
    try:
        with Image.open(LOGO_PATH) as image_check:
            image_check.verify()
    except (OSError, UnidentifiedImageError):
        LOGO_EXISTS = False

PAGE_ICON = "✨"

if LOGO_EXISTS:
    try:
        PAGE_ICON = Image.open(LOGO_PATH).copy()
    except Exception:
        PAGE_ICON = "✨"
        LOGO_EXISTS = False

st.set_page_config(
    page_title="E.D.I.T.H",
    page_icon=PAGE_ICON,
    layout="centered",
    initial_sidebar_state="collapsed"
)

AI_AVATAR = str(LOGO_PATH) if LOGO_EXISTS else "✨"
USER_AVATAR = "👤"

CHAT_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = (
    "meta-llama/llama-4-scout-17b-16e-instruct"
)
STT_MODEL = "whisper-large-v3-turbo"


# ============================================================
# 2. SESSION STATE
# ============================================================

if "rooms" not in st.session_state:
    st.session_state.rooms = {"Chat 1": []}

DEFAULTS = {
    "room": "Chat 1",
    "memory": "",
    "pending": False,
    "editing": None,
    "last_hub_event": "",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def history():
    return st.session_state.rooms[
        st.session_state.room
    ]


def empty_assistant():
    return {
        "role": "assistant",
        "content": "",
        "sources": [],
        "audio": None,
        "action": None,
        "emotion": "neutral",
        "failed": False,
    }


def ask(question, force_search=False):
    if not question.strip():
        return

    history().append({
        "role": "user",
        "content": question.strip(),
        "force_search": force_search
    })

    history().append(empty_assistant())
    st.session_state.pending = True


def new_chat():
    number = 1

    while f"Chat {number}" in st.session_state.rooms:
        number += 1

    name = f"Chat {number}"

    st.session_state.rooms[name] = []
    st.session_state.room = name
    st.session_state.editing = None


def regenerate():
    items = history()

    if items and items[-1]["role"] == "assistant":
        items.pop()

    if items and items[-1]["role"] == "user":
        items.append(empty_assistant())
        st.session_state.pending = True


# ============================================================
# 3. LANGUAGE AND EMOTION
# ============================================================

def detect_language(text, setting):
    if setting == "Bahasa Melayu":
        return "ms"

    if setting == "English":
        return "en"

    malay_words = {
        "saya", "awak", "boleh", "tolong", "apa",
        "macam", "mana", "nak", "tak", "buat",
        "cari", "ajar", "belajar", "terangkan",
        "projek", "bagaimana", "kenapa", "telefon",
        "lokasi", "berikan", "bantu", "dengan",
        "untuk", "adakah", "bolehkah"
    }

    words = set(re.findall(r"\w+", text.lower()))

    return "ms" if words & malay_words else "en"


def emotion_for(text):
    text = text.lower()

    if any(word in text for word in [
        "tahniah", "bagus", "excellent",
        "congratulations", "gembira"
    ]):
        return "happy"

    if any(word in text for word in [
        "sedih", "takziah", "sorry", "dukacita"
    ]):
        return "sad"

    if any(word in text for word in [
        "wow", "wah", "amazing", "menakjubkan"
    ]):
        return "surprised"

    return "neutral"


# ============================================================
# 4. TEXT TO SPEECH
# ============================================================

async def create_speech(text, lang):
    voice = (
        "ms-MY-YasminNeural"
        if lang == "ms"
        else "en-US-JennyNeural"
    )

    clean_text = re.sub(
        r"[*#`_]+", " ", text
    )

    speech = Communicate(
        text=clean_text[:1800],
        voice=voice
    )

    sound = bytearray()

    async for packet in speech.stream():
        if packet["type"] == "audio":
            sound.extend(packet["data"])

    return bytes(sound)


# ============================================================
# 5. DOCUMENT READER
# ============================================================

def read_document(upload):
    raw = upload.getvalue()

    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Dokumen melebihi 8 MB.")

    name = upload.name.lower()

    if name.endswith(".pdf"):
        pdf = PdfReader(io.BytesIO(raw))

        content = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages[:20]
        )

    elif name.endswith(".docx"):
        doc = Document(io.BytesIO(raw))

        parts = [
            p.text for p in doc.paragraphs
        ]

        for table in doc.tables:
            for row in table.rows:
                parts.append(
                    " | ".join(
                        cell.text for cell in row.cells
                    )
                )

        content = "\n".join(parts)

    else:
        content = raw.decode(
            "utf-8",
            errors="replace"
        )

    return content[:12000]


# ============================================================
# 6. INTERNET SEARCH
# ============================================================

def search_web(question):
    results = DDGS(
        timeout=12
    ).text(
        question,
        max_results=4
    ) or []

    sources = []

    for item in results:
        url = str(item.get("href", ""))

        if urlparse(url).scheme not in (
            "http", "https"
        ):
            continue

        sources.append({
            "title": str(
                item.get("title", "")
            )[:120],

            "url": url,

            "snippet": str(
                item.get("body", "")
            )[:450]
        })

    return sources


# ============================================================
# 7. AI ACTIONS
# ============================================================

def action_for(command):
    command = command.strip()

    # PHONE
    phone = re.search(
        r"(?:telefon|panggil|call|dial)"
        r"\s+(?:nombor\s+|number\s+)?"
        r"(\+?[\d][\d\s\-()]{6,}[\d])",
        command,
        re.I
    )

    if phone:
        number = re.sub(
            r"[^\d+]", "", phone.group(1)
        )

        if re.fullmatch(
            r"\+?\d{7,15}", number
        ):
            return {
                "type": "dial",
                "label": "📞 Buka Phone: " + number,
                "url": "tel:" + number
            }

    # MAPS
    maps = re.search(
        r"(?:lokasi|maps? ke|pergi ke|"
        r"arah ke|navigate to|directions to)"
        r"\s+(.+)",
        command,
        re.I
    )

    if maps:
        place = maps.group(1).strip(
            " .?!"
        )[:120]

        if place:
            return {
                "type": "maps",
                "label": "📍 Buka Google Maps",
                "url": (
                    "https://www.google.com/maps/"
                    "search/?api=1&query="
                    + quote_plus(place)
                )
            }

    # GOOGLE
    google = re.search(
        r"^(?:google|cari di google|"
        r"cari web|search web)"
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


# ============================================================
# 8. MODE 3 - APP BUBBLES
# ============================================================

APP_BUBBLES = [
    {
        "name": "Facebook",
        "symbol": "f",
        "color": "#73A6FF",
        "url": "https://www.facebook.com"
    },
    {
        "name": "Google",
        "symbol": "G",
        "color": "#76DEFF",
        "url": "https://www.google.com"
    },
    {
        "name": "ChatGPT",
        "symbol": "✳",
        "color": "#61F2BC",
        "url": "https://chatgpt.com"
    },
    {
        "name": "Arduino IDE",
        "symbol": "∞",
        "color": "#69EDFF",
        "url": "https://www.arduino.cc/en/software"
    },
    {
        "name": "WhatsApp",
        "symbol": "✆",
        "color": "#62EF9D",
        "url": "https://web.whatsapp.com"
    },
    {
        "name": "TikTok",
        "symbol": "♪",
        "color": "#FF9CC8",
        "url": "https://www.tiktok.com"
    },
    {
        "name": "YouTube",
        "symbol": "▶",
        "color": "#FF7878",
        "url": "https://www.youtube.com"
    },
    {
        "name": "Instagram",
        "symbol": "◎",
        "color": "#E6A1FF",
        "url": "https://www.instagram.com"
    }
]


# ============================================================
# 9. MODE 3 - AI SKILLS
# ============================================================

AI_SKILLS = [
    ("AI Chat", "Perkenalkan E.D.I.T.H dan mulakan perbualan.", False),
    ("Study", "Ajar saya satu topik baharu langkah demi langkah.", False),
    ("Quiz", "Berikan kuiz pengetahuan am 5 soalan.", False),
    ("Math", "Ajar saya matematik dengan contoh.", False),
    ("Science", "Terangkan satu konsep sains.", False),
    ("English", "Bantu saya berlatih bahasa Inggeris.", False),
    ("Translator", "Bantu saya menterjemah antara Melayu dan English.", False),
    ("History", "Ceritakan satu peristiwa sejarah.", False),
    ("Physics", "Terangkan asas fizik.", False),
    ("Chemistry", "Ajar saya asas kimia.", False),

    ("Python", "Ajar saya coding Python dengan contoh.", False),
    ("Arduino", "Cadangkan projek Arduino bersama coding dan wiring.", False),
    ("ESP32", "Ajar saya projek ESP32 dengan coding.", False),
    ("Debug", "Ajar saya debugging kod dan mencari error.", False),
    ("HTML", "Ajar saya membuat website menggunakan HTML.", False),
    ("CSS", "Ajar saya CSS dan web design.", False),
    ("JavaScript", "Ajar saya JavaScript dengan contoh.", False),
    ("C++", "Ajar saya asas C++.", False),
    ("IoT", "Cadangkan projek Internet of Things.", False),
    ("Robotics", "Bantu saya membina projek robotik.", False),

    ("Sensors", "Terangkan jenis sensor elektronik.", False),
    ("Servo", "Ajar saya mengawal servo menggunakan Arduino.", False),
    ("Circuit", "Terangkan asas litar elektronik.", False),
    ("Wiring", "Tunjukkan contoh wiring Arduino.", False),
    ("FYP", "Cadangkan tajuk Final Year Project teknologi.", False),
    ("AI Project", "Cadangkan projek artificial intelligence.", False),
    ("Planner", "Bina jadual belajar seminggu.", False),
    ("Writing", "Ajar saya teknik penulisan yang baik.", False),
    ("Business", "Cadangkan idea perniagaan teknologi.", False),
    ("Prompt", "Ajar saya menulis prompt AI yang berkesan.", False),

    ("AI News", "Cari berita AI terkini dengan sumber.", True),
    ("Tech News", "Cari berita teknologi terkini dengan sumber.", True),
    ("Research", "Cari perkembangan robotik terkini dengan sumber.", True),
    ("Open Source", "Cari projek AI open source untuk pemula.", True),
    ("Malaysia Tech", "Cari perkembangan teknologi Malaysia terkini.", True),

    ("AI Vision", "Terangkan cara AI mengenali gambar.", False),
    ("Computer", "Ajar saya asas komputer.", False),
    ("Database", "Ajar saya database dan SQL.", False),
    ("Cybersecurity", "Ajar asas keselamatan siber secara beretika.", False),
    ("Project Ideas", "Berikan 10 idea projek teknologi.", False),
    ("Presentation", "Ajar saya membuat slide pembentangan.", False),
    ("Resume", "Ajar saya menyediakan resume.", False),
    ("Interview", "Latih saya menghadapi temuduga.", False),
    ("Finance", "Terangkan asas bajet peribadi.", False),
    ("Mind Map", "Buatkan peta minda teks tentang AI.", False),
    ("Study Test", "Uji pengetahuan elektronik saya.", False),
    ("About E.D.I.T.H", "Terangkan fungsi E.D.I.T.H yang tersedia.", False),
]

assert len(APP_BUBBLES) == 8
assert len(AI_SKILLS) == 47


# ============================================================
# 10. VISUAL COMPONENT
#     HOLOGRAM + RADIAL HUB + REAL AUDIO ANALYSER
# ============================================================

VISUAL_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport"
content="width=device-width,initial-scale=1">

<style>
* {
    box-sizing: border-box;
}

html, body {
    margin: 0;
    padding: 0;
    background: transparent;
    color: #eafaff;
    font-family: Arial, sans-serif;
    overflow-x: hidden;
}

.shell {
    width: 100%;
    text-align: center;
    padding: 8px 4px 12px;
    background:
        radial-gradient(
            ellipse at center,
            rgba(32,108,230,.17),
            transparent 72%
        );
}

.heading {
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 4px;
    color: #edffff;
    text-shadow: 0 0 15px #49ddff;
}

.subtitle {
    color: #a4cae5;
    font: 10px monospace;
    letter-spacing: 2px;
    margin: 7px 0 5px;
}

canvas {
    display: block;
    width: 100%;
    touch-action: manipulation;
    cursor: pointer;
}

.status {
    margin: 8px 0;
    font: 11px monospace;
    letter-spacing: 2px;
    color: #8feaff;
}

.legend {
    margin: 8px 0;
    font-size: 11px;
    color: #bed7ec;
}

.panel {
    display: none;
    text-align: left;
    padding: 14px;
    margin: 8px;
    border-radius: 18px;

    background:
        linear-gradient(
            130deg,
            rgba(83,116,189,.29),
            rgba(77,49,139,.31)
        );

    border:
        1px solid rgba(172,220,255,.42);

    backdrop-filter:
        blur(25px) saturate(165%);

    -webkit-backdrop-filter:
        blur(25px) saturate(165%);

    box-shadow:
        0 10px 30px rgba(0,0,0,.22);
}

.panel h3 {
    margin: 0 0 7px;
    color: white;
    font-size: 15px;
}

.panel p {
    font-size: 12px;
    color: #d7ecff;
    line-height: 1.6;
}

.btn {
    display: inline-block;
    padding: 10px 15px;
    margin: 4px;
    border: 1px solid #9fddff75;
    border-radius: 12px;
    background:
        linear-gradient(
            120deg,
            #137fd0,
            #7750cf
        );
    color: white;
    text-decoration: none;
    font-size: 12px;
    font-weight: bold;
    cursor: pointer;
}

.btn.secondary {
    background: #293a5e;
}

.skills {
    display: grid;
    grid-template-columns:
        repeat(3, minmax(0,1fr));
    gap: 8px;
    max-height: 275px;
    overflow-y: auto;
}

.skill {
    min-height: 44px;
    border-radius: 12px;
    border: 1px solid #ca9cff85;
    color: white;
    background: rgba(114,80,176,.43);
    cursor: pointer;
    font-size: 11px;
    padding: 8px 4px;
}

.skill:active {
    background: #7851bb;
}

#audio {
    width: 92%;
    max-width: 360px;
    display: none;
    margin: 11px auto 0;
}
</style>
</head>

<body>

<div class="shell">

    <div class="heading">
        E.D.I.T.H
    </div>

    <div class="subtitle" id="subtitle">
        MODE 3 • AI COMMAND HUB
    </div>

    <canvas id="scene"></canvas>

    <div class="status" id="status">
        STANDBY
    </div>

    <div class="legend" id="legend">
        🟡 App / Website
        &nbsp; • &nbsp;
        🩷 AI Chat
    </div>

    <section class="panel" id="appPanel">
        <h3 id="appTitle">
            App Launcher
        </h3>

        <p>
            Tekan butang untuk membuka
            aplikasi atau website pilihan.
        </p>

        <a
            id="appLink"
            class="btn"
            target="_blank"
            rel="noopener noreferrer">
            Buka Aplikasi
        </a>

        <button
            id="closeApp"
            class="btn secondary"
            type="button">
            Tutup
        </button>
    </section>

    <section class="panel" id="skillPanel">
        <h3 id="skillTitle">AI Skills</h3>

        <p>
            Pilih fungsi untuk dihantar
            kepada E.D.I.T.H.
        </p>

        <div
            id="skillGrid"
            class="skills"></div>

        <button
            id="closeSkill"
            class="btn secondary"
            type="button">
            Tutup
        </button>
    </section>

    <audio
        id="audio"
        controls
        preload="metadata"></audio>
</div>


<script>
"use strict";

// ==========================================
// STREAMLIT COMPONENT COMMUNICATION
// ==========================================

function post(type, fields={}) {
    window.parent.postMessage(
        {
            isStreamlitMessage: true,
            type: type,
            ...fields
        },
        "*"
    );
}

function updateHeight() {
    post(
        "streamlit:setFrameHeight",
        {
            height:
                document.body.scrollHeight + 10
        }
    );
}

post(
    "streamlit:componentReady",
    {apiVersion:1}
);


// ==========================================
// ELEMENTS
// ==========================================

const canvas =
    document.getElementById("scene");

const ctx =
    canvas.getContext("2d");

const audio =
    document.getElementById("audio");

const statusEl =
    document.getElementById("status");

const appPanel =
    document.getElementById("appPanel");

const skillPanel =
    document.getElementById("skillPanel");

const appTitle =
    document.getElementById("appTitle");

const appLink =
    document.getElementById("appLink");

const skillTitle =
    document.getElementById("skillTitle");

const skillGrid =
    document.getElementById("skillGrid");


// ==========================================
// STATE
// ==========================================

let apps = [];
let skills = [];

let mode = "neural";
let emotion = "neutral";
let busy = false;

let audioValue = "";
let speaking = false;

let audioContext = null;
let analyser = null;
let mediaSource = null;
let frequency = null;
let waveform = null;

let energy = 0;
let bass = 0;
let mid = 0;
let treble = 0;

let width = 390;
let height = 430;

let cx = 195;
let cy = 215;

let t = 0;

let selected = null;
let targets = [];


// ==========================================
// AUDIO ANALYSER
// ==========================================

function initAudio() {
    if (analyser) return;

    try {
        const AC =
            window.AudioContext ||
            window.webkitAudioContext;

        if (!AC) return;

        audioContext = new AC();

        analyser =
            audioContext.createAnalyser();

        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = .75;

        mediaSource =
            audioContext.createMediaElementSource(
                audio
            );

        mediaSource.connect(analyser);
        analyser.connect(
            audioContext.destination
        );

        frequency =
            new Uint8Array(
                analyser.frequencyBinCount
            );

        waveform =
            new Uint8Array(
                analyser.fftSize
            );

    } catch(error) {
        console.warn(
            "Audio analyser error:",
            error
        );
    }
}

function updateStatus() {
    statusEl.textContent =
        busy
            ? "THINKING"
            : speaking
                ? "SPEAKING"
                : "STANDBY";
}

audio.addEventListener(
    "play",
    () => {
        initAudio();

        if (
            audioContext &&
            audioContext.state === "suspended"
        ) {
            audioContext.resume();
        }

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

audio.addEventListener(
    "error",
    () => {
        speaking = false;
        updateStatus();
    }
);

function average(data, start, end) {
    if (!data) return 0;

    let total = 0;
    let count = 0;

    for (let i = start; i < end; i++) {
        total += data[i] / 255;
        count++;
    }

    return count ? total / count : 0;
}

function analyseSound() {
    let newEnergy = 0;
    let newBass = 0;
    let newMid = 0;
    let newTreble = 0;

    if (speaking && analyser) {
        analyser.getByteFrequencyData(
            frequency
        );

        analyser.getByteTimeDomainData(
            waveform
        );

        const n = frequency.length;

        newBass = average(
            frequency,
            1,
            Math.floor(n * .10)
        );

        newMid = average(
            frequency,
            Math.floor(n * .10),
            Math.floor(n * .35)
        );

        newTreble = average(
            frequency,
            Math.floor(n * .35),
            Math.floor(n * .85)
        );

        let sum = 0;

        for (
            let i = 0;
            i < waveform.length;
            i++
        ) {
            const sample =
                (waveform[i] - 128) / 128;

            sum += sample * sample;
        }

        newEnergy = Math.min(
            1,
            Math.sqrt(
                sum / waveform.length
            ) * 4.5
        );
    }

    const smoothing =
        speaking ? .24 : .08;

    energy +=
        (newEnergy - energy) * smoothing;

    bass +=
        (newBass - bass) * smoothing;

    mid +=
        (newMid - mid) * smoothing;

    treble +=
        (newTreble - treble) * smoothing;
}


// ==========================================
// RESIZE
// ==========================================

function resize() {
    width =
        canvas.getBoundingClientRect().width
        || 390;

    height = mode === "holo"
        ? 295
        : Math.max(
            400,
            Math.min(
                565,
                width * 1.10
            )
        );

    canvas.style.height =
        height + "px";

    const dpr = Math.min(
        window.devicePixelRatio || 1,
        2
    );

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    ctx.setTransform(
        dpr, 0, 0, dpr, 0, 0
    );

    cx = width / 2;
    cy = height / 2;

    updateHeight();
}

window.addEventListener(
    "resize", resize
);


// ==========================================
// DRAW HELPERS
// ==========================================

function circle(
    x, y, r,
    fill, stroke,
    glow=0
) {
    ctx.beginPath();

    ctx.arc(
        x, y,
        Math.max(1,r),
        0, Math.PI*2
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

function text(
    value, x, y,
    size, color="#ffffff"
) {
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.font =
        "bold " + size + "px Arial";

    ctx.fillStyle = color;

    ctx.fillText(value,x,y);
}

function line(
    x1,y1,x2,y2,
    color,thickness=1.5
) {
    ctx.beginPath();

    ctx.moveTo(x1,y1);
    ctx.lineTo(x2,y2);

    ctx.strokeStyle = color;
    ctx.lineWidth = thickness;

    ctx.stroke();
}


// ==========================================
// RADIAL POSITIONS
// ==========================================

function appPoint(index) {
    const angle =
        -Math.PI/2 +
        index * Math.PI/4;

    const radius = Math.min(
        width * .355,
        height * .35
    );

    return {
        x:
            cx + Math.cos(angle) * radius,
        y:
            cy + Math.sin(angle) * radius
    };
}

function pinkPoint(index) {
    const angle =
        -Math.PI/2 - .22 +
        index * Math.PI/6;

    const radius = Math.min(
        width * .465,
        height * .465
    );

    return {
        x:
            cx + Math.cos(angle) * radius,
        y:
            cy + Math.sin(angle) * radius
    };
}

function moodColor() {
    if (emotion === "happy") {
        return "#70FFD0";
    }

    if (emotion === "sad") {
        return "#77A3FF";
    }

    if (emotion === "surprised") {
        return "#EF9FFF";
    }

    return "#60E7FF";
}


// ==========================================
// CONNECTION LINES
// ==========================================

function drawConnections() {
    for (let i=0; i<8; i++) {
        const p = appPoint(i);

        line(
            cx,cy,p.x,p.y,
            "rgba(90,193,255,"+
            (.46+energy*.46)+")",
            1.5 + bass*2
        );
    }

    for (let i=0; i<12; i++) {
        const p = pinkPoint(i);

        line(
            cx,cy,p.x,p.y,
            "rgba(255,181,96,"+
            (.34+energy*.45)+")",
            1.3 + bass*2
        );
    }
}


// ==========================================
// MAIN E.D.I.T.H CORE
// ==========================================

function drawCore() {
    const radius = Math.max(
        34,
        Math.min(
            width * .14,
            76
        )
    );

    for (let k=0; k<3; k++) {
        ctx.save();

        ctx.translate(cx,cy);
        ctx.rotate(
            t * (k%2 ? -.45 : .55)
        );

        ctx.setLineDash(
            k===1 ? [5,8] : [22,12]
        );

        ctx.beginPath();

        ctx.arc(
            0,0,
            radius+5+k*6+energy*10,
            0,Math.PI*2
        );

        ctx.strokeStyle = [
            "#62EBFF",
            "#B292FF",
            "#6B9CFF"
        ][k];

        ctx.lineWidth = 1.7;
        ctx.stroke();

        ctx.restore();
    }

    const gradient =
        ctx.createRadialGradient(
            cx-radius*.25,
            cy-radius*.3,
            1,
            cx,
            cy,
            radius
        );

    gradient.addColorStop(
        0,"#5BE8FF"
    );

    gradient.addColorStop(
        .5,"#16518A"
    );

    gradient.addColorStop(
        1,"#071126"
    );

    circle(
        cx,cy,
        radius+energy*9,
        gradient,
        moodColor(),
        22+energy*28
    );

    text(
        "E.D.I.T.H",
        cx,cy,
        Math.max(
            10,
            radius*.30
        )
    );
}


// ==========================================
// APP BUBBLES
// ==========================================

function drawApp(index) {
    const app = apps[index];

    if (!app) return;

    const p = appPoint(index);

    const active =
        selected &&
        selected.type==="app" &&
        selected.index===index;

    const base = Math.max(
        17,
        Math.min(
            width*.076,
            44
        )
    );

    const radius =
        base * (
            1 +
            energy*.13 +
            bass*.11 +
            (active ? .22 : 0)
        );

    const gradient =
        ctx.createRadialGradient(
            p.x-radius*.25,
            p.y-radius*.28,
            1,
            p.x,p.y,radius
        );

    gradient.addColorStop(
        0,"rgba(42,59,99,.96)"
    );

    gradient.addColorStop(
        1,"rgba(7,16,34,.99)"
    );

    circle(
        p.x,p.y,
        radius,
        gradient,
        "#FFC56B",
        active ? 30 : 13
    );

    text(
        app.symbol,
        p.x,
        p.y-radius*.22,
        Math.max(
            12,
            radius*.64
        ),
        app.color
    );

    text(
        app.name,
        p.x,
        p.y+radius*.44,
        Math.max(
            6,
            radius*.265
        )
    );

    targets.push({
        type:"app",
        index:index,
        x:p.x,
        y:p.y,
        r:radius+7
    });
}


// ==========================================
// PINK AI CHAT NODES
// ==========================================

function drawPink(index) {
    const p = pinkPoint(index);

    const active =
        selected &&
        selected.type==="skill" &&
        selected.index===index;

    const radius =
        Math.max(
            8,
            Math.min(
                width*.027,
                16
            )
        ) *
        (active ? 1.4 : 1) *
        (1+energy*.20);

    circle(
        p.x,p.y,
        radius,
        "rgba(112,25,94,.56)",
        "#FF87C4",
        active ? 26 : 14
    );

    if (active) {
        text(
            "AI",
            p.x,p.y,
            Math.max(
                7,
                radius*.58
            )
        );
    }

    targets.push({
        type:"skill",
        index:index,
        x:p.x,
        y:p.y,
        r:Math.max(
            15,
            radius+8
        )
    });
}


// ==========================================
// AUDIO REACTIVE BARS
// ==========================================

function drawBars() {
    for (let i=0; i<17; i++) {
        let amount = 0;

        if (speaking && frequency) {
            const index = Math.min(
                frequency.length-1,
                i*5
            );

            amount =
                frequency[index] / 255;
        }

        const barHeight =
            3 + amount*27;

        ctx.fillStyle =
            i%3===0
                ? "#B79CFF"
                : "#6BEAFF";

        ctx.fillRect(
            cx-71+i*8.7,
            height-7-barHeight,
            3,
            barHeight
        );
    }
}


// ==========================================
// MODE 2 - HOLOGRAM
// ==========================================

function drawHologram() {
    for (let k=0; k<3; k++) {
        ctx.save();

        ctx.translate(cx,cy);

        ctx.rotate(
            t*(k%2 ? -.60 : .70)
        );

        ctx.setLineDash(
            k===1 ? [5,8] : [24,12]
        );

        ctx.beginPath();

        ctx.arc(
            0,0,
            65+k*22+energy*12,
            0,Math.PI*2
        );

        ctx.strokeStyle = [
            "#67EAFF",
            "#B08CFF",
            "#4D8FFF"
        ][k];

        ctx.lineWidth = 1.6;
        ctx.stroke();

        ctx.restore();
    }

    const radius =
        52+energy*20;

    const gradient =
        ctx.createRadialGradient(
            cx-15,cy-17,2,
            cx,cy,radius
        );

    gradient.addColorStop(
        0,"#FFFFFF"
    );

    gradient.addColorStop(
        .25,"#72EBFF"
    );

    gradient.addColorStop(
        .62,"#596BEF"
    );

    gradient.addColorStop(
        1,"#171449"
    );

    circle(
        cx,cy,
        radius,
        gradient,
        moodColor(),
        25+energy*24
    );

    drawBars();
}


// ==========================================
// ANIMATION LOOP
// ==========================================

function frame() {
    requestAnimationFrame(frame);

    if (document.hidden) return;

    t += speaking ? .032 : .010;

    analyseSound();

    ctx.clearRect(
        0,0,width,height
    );

    targets = [];

    if (mode==="holo") {
        drawHologram();
        return;
    }

    const aura =
        ctx.createRadialGradient(
            cx,cy,5,
            cx,cy,height*.46
        );

    aura.addColorStop(
        0,
        "rgba(45,118,238,.17)"
    );

    aura.addColorStop(
        1,
        "rgba(0,0,0,0)"
    );

    ctx.fillStyle = aura;

    ctx.fillRect(
        0,0,width,height
    );

    drawConnections();

    for (let i=0; i<8; i++) {
        drawApp(i);
    }

    for (let i=0; i<12; i++) {
        drawPink(i);
    }

    drawCore();
    drawBars();
}


// ==========================================
// FIND CLICKED BUBBLE
// ==========================================

function findBubble(event) {
    const rect =
        canvas.getBoundingClientRect();

    const x =
        event.clientX - rect.left;

    const y =
        event.clientY - rect.top;

    let chosen = null;
    let best = Infinity;

    for (const item of targets) {
        const distance =
            Math.hypot(
                x-item.x,
                y-item.y
            );

        if (
            distance <= item.r &&
            distance < best
        ) {
            chosen = item;
            best = distance;
        }
    }

    return chosen;
}


// ==========================================
// APP AND AI PANELS
// ==========================================

function hidePanels() {
    appPanel.style.display = "none";
    skillPanel.style.display = "none";
    updateHeight();
}

function showAppPanel(index) {
    const app = apps[index];

    if (!app) return;

    hidePanels();

    appTitle.textContent =
        app.name;

    appLink.href = app.url;

    appLink.textContent =
        "Buka "+app.name+" ↗";

    appPanel.style.display = "block";

    updateHeight();
}

function sendSkill(index) {
    post(
        "streamlit:setComponentValue",
        {
            value: {
                id:
                    String(Date.now())+
                    "-"+
                    Math.random().toString(36),

                skill_index: index
            }
        }
    );
}

function showSkillPanel(group) {
    hidePanels();

    skillGrid.replaceChildren();

    skillTitle.textContent =
        "AI Chat • Node "+(group+1);

    skills.forEach(
        (skill,index) => {
            if (index%12 !== group) {
                return;
            }

            const button =
                document.createElement(
                    "button"
                );

            button.type = "button";
            button.className = "skill";
            button.textContent = skill.name;

            button.addEventListener(
                "click",
                () => {
                    sendSkill(index);
                    hidePanels();
                }
            );

            skillGrid.appendChild(
                button
            );
        }
    );

    skillPanel.style.display = "block";
    updateHeight();
}


// ==========================================
// CLICK LISTENERS
// ==========================================

canvas.addEventListener(
    "click",
    event => {
        if (mode==="holo" || busy) {
            return;
        }

        const item = findBubble(event);

        if (!item) return;

        selected = {
            type:item.type,
            index:item.index
        };

        if (item.type==="app") {
            showAppPanel(item.index);
        } else {
            showSkillPanel(item.index);
        }
    }
);

canvas.addEventListener(
    "pointermove",
    event => {
        if (mode==="holo") {
            canvas.style.cursor =
                "default";
            return;
        }

        canvas.style.cursor =
            findBubble(event)
                ? "pointer"
                : "default";
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


// ==========================================
// RECEIVE STREAMLIT DATA
// ==========================================

window.addEventListener(
    "message",
    event => {
        if (
            !event.data ||
            event.data.type !==
            "streamlit:render"
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

        const previousMode = mode;

        mode = args.mode || "neural";
        emotion = args.emotion || "neutral";
        busy = !!args.busy;

        const nextAudio =
            args.audio || "";

        if (nextAudio !== audioValue) {
            audioValue = nextAudio;

            audio.pause();

            if (audioValue) {
                audio.src =
                    "data:audio/mpeg;base64,"+
                    audioValue;

                audio.style.display = "block";
            } else {
                audio.removeAttribute("src");
                audio.style.display = "none";
            }
        }

        document.getElementById(
            "subtitle"
        ).textContent =
            mode==="holo"
                ? "MODE 2 • HOLOGRAPHIC VOICE CORE"
                : "MODE 3 • AI COMMAND HUB";

        document.getElementById(
            "legend"
        ).style.display =
            mode==="holo"
                ? "none"
                : "block";

        if (previousMode !== mode) {
            selected = null;
            hidePanels();
        }

        updateStatus();
        resize();
    }
);

resize();
frame();
updateHeight();

</script>
</body>
</html>
"""


# ============================================================
# 11. REGISTER STREAMLIT CUSTOM COMPONENT
# ============================================================

@st.cache_resource
def build_hub():
    folder = (
        Path(tempfile.gettempdir())
        / "edith_crystal_logo_hub_v2"
    )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    (folder / "index.html").write_text(
        VISUAL_HTML,
        encoding="utf-8"
    )

    return declare_component(
        "edith_crystal_logo_hub_v2",
        path=str(folder)
    )


hub_component = build_hub()


def show_hub(view, audio=None, emotion="neutral"):
    audio_base64 = (
        base64.b64encode(audio).decode("ascii")
        if audio
        else ""
    )

    frontend_skills = [
        {"name": item[0]}
        for item in AI_SKILLS
    ]

    return hub_component(
        mode=view,
        audio=audio_base64,
        emotion=emotion,
        apps=APP_BUBBLES,
        skills=frontend_skills,
        busy=st.session_state.pending,
        default=None,
        key="edith_crystal_logo_hub"
    )


# ============================================================
# 12. SIDEBAR
# ============================================================

with st.sidebar:
    st.header("⚙️ E.D.I.T.H Settings")

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
    st.subheader("🧠 AI Memory")

    st.text_area(
        "Apa E.D.I.T.H perlu ingat?",
        key="memory",
        height=100
    )

    if st.button("Clear Memory"):
        st.session_state.memory = ""
        st.rerun()

    st.caption(
        "Memory dan sejarah chat disimpan "
        "untuk sesi semasa sahaja."
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


# ============================================================
# 13. CRYSTAL ACRYLIC + QUANTUM ENERGY FLOW
# ============================================================

if theme == "Light":
    bg = "#edf4ff"
    fg = "#17233b"
    user_bg = "rgba(196,224,255,.53)"
    user_fg = "#15223d"

    sidebar_bg = "rgba(235,247,255,.50)"
    input_bg = "rgba(246,252,255,.52)"
    glass = "rgba(227,243,255,.50)"
    border = "rgba(82,138,216,.26)"

elif theme == "Ocean Blue":
    bg = "#06172d"
    fg = "#effaff"
    user_bg = "rgba(73,155,210,.23)"
    user_fg = "#ffffff"

    sidebar_bg = "rgba(20,70,120,.47)"
    input_bg = "rgba(27,89,146,.34)"
    glass = "rgba(37,103,160,.25)"
    border = "rgba(118,222,255,.34)"

else:
    bg = "#080f20"
    fg = "#effaff"
    user_bg = "rgba(143,183,237,.17)"
    user_fg = "#ffffff"

    sidebar_bg = "rgba(51,79,143,.27)"
    input_bg = "rgba(143,175,232,.14)"
    glass = "rgba(120,161,225,.15)"
    border = "rgba(174,218,255,.28)"


st.markdown(
    f"""
<style>

/* QUANTUM ENERGY FLOW */

.stApp {{
    background:
        radial-gradient(
            ellipse at 16% 18%,
            rgba(42,154,255,.18),
            transparent 41%
        ),
        radial-gradient(
            ellipse at 83% 67%,
            rgba(159,88,255,.19),
            transparent 43%
        ),
        {bg};

    color: {fg};
}}

.stApp::before {{
    content: "";
    position: fixed;
    inset: -15%;
    pointer-events: none;

    background:
        radial-gradient(
            ellipse at 20% 43%,
            rgba(53,214,255,.19),
            transparent 34%
        ),
        radial-gradient(
            ellipse at 78% 33%,
            rgba(174,113,255,.17),
            transparent 36%
        );

    animation:
        edithFlow 19s ease-in-out
        infinite alternate;
}}

@keyframes edithFlow {{
    from {{
        transform:
            translate(-2%,0%) scale(1);
    }}

    to {{
        transform:
            translate(2%,-2%) scale(1.06);
    }}
}}

/* TITLE */

[data-testid="stHeader"] {{
    background: transparent;
}}

.stApp h1,
.stApp h2,
.stApp h3 {{
    color: {fg};
}}

/* CRYSTAL ACRYLIC MESSAGES */

[data-testid="stChatMessage"] {{
    background: {glass} !important;

    backdrop-filter:
        blur(25px) saturate(175%) !important;

    -webkit-backdrop-filter:
        blur(25px) saturate(175%) !important;

    border:
        1px solid {border} !important;

    border-radius:
        21px !important;

    padding:
        15px !important;

    margin-bottom:
        12px !important;

    box-shadow:
        0 9px 32px rgba(0,0,0,.12),
        inset 0 1px rgba(255,255,255,.15);
}}

[data-testid="stChatMessage"]:hover {{
    border-color:
        rgba(105,225,255,.48) !important;
}}

[data-testid="stChatMessageContent"] {{
    line-height: 1.7;
}}

/* ACRYLIC INPUT */

[data-testid="stChatInput"] > div {{
    background: {input_bg} !important;

    backdrop-filter:
        blur(28px) saturate(170%) !important;

    -webkit-backdrop-filter:
        blur(28px) saturate(170%) !important;

    border:
        1px solid {border} !important;

    border-radius:
        25px !important;

    box-shadow:
        0 8px 25px rgba(0,0,0,.16);
}}

[data-testid="stChatInput"] textarea {{
    color: {fg} !important;
}}

/* SIDEBAR */

[data-testid="stSidebar"] > div:first-child {{
    background: {sidebar_bg} !important;

    backdrop-filter:
        blur(30px) saturate(160%) !important;

    -webkit-backdrop-filter:
        blur(30px) saturate(160%) !important;

    border-right:
        1px solid {border};
}}

/* EXPANDERS */

[data-testid="stExpander"] {{
    background: {glass};

    backdrop-filter:
        blur(18px) saturate(160%);

    -webkit-backdrop-filter:
        blur(18px) saturate(160%);

    border:
        1px solid {border} !important;

    border-radius:
        17px !important;
}}

/* BUTTONS */

.stButton > button {{
    border-radius: 13px;
}}

/* MOBILE */

@media(max-width:600px) {{
    .block-container {{
        padding-left: .65rem;
        padding-right: .65rem;
        padding-top: 1rem;
    }}

    [data-testid="stChatMessage"] {{
        padding: 11px !important;
        border-radius: 17px !important;
    }}
}}

/* REDUCED MOTION */

@media(prefers-reduced-motion:reduce) {{
    .stApp::before {{
        animation: none;
    }}
}}

</style>
""",
    unsafe_allow_html=True
)


# ============================================================
# 14. MAIN HEADER WITH CUSTOM LOGO
# ============================================================

if LOGO_EXISTS:
    logo_col, title_col = st.columns(
        [1, 5],
        vertical_alignment="center"
    )

    with logo_col:
        st.image(
            str(LOGO_PATH),
            width=65
        )

    with title_col:
        st.title("E.D.I.T.H")

else:
    st.title("✨ E.D.I.T.H")

st.caption(
    "Your Personal AI Assistant • Crystal Edition"
)


# ============================================================
# 15. MODE FLAGS
# ============================================================

voice_mode = (
    mode.startswith("Mode 2")
    or mode.startswith("Mode 3")
)

hub_mode = mode.startswith("Mode 3")


# ============================================================
# 16. VISUAL + INTERACTIVE BUBBLES
# ============================================================

if voice_mode:
    last_audio_message = next(
        (
            m for m in reversed(history())
            if (
                m["role"] == "assistant"
                and m.get("audio")
            )
        ),
        None
    )

    last_audio = (
        last_audio_message["audio"]
        if last_audio_message
        else None
    )

    last_emotion = (
        last_audio_message.get(
            "emotion", "neutral"
        )
        if last_audio_message
        else "neutral"
    )

    event = show_hub(
        view="neural" if hub_mode else "holo",
        audio=last_audio,
        emotion=last_emotion
    )

    if (
        hub_mode
        and not st.session_state.pending
        and isinstance(event, dict)
    ):
        event_id = event.get("id")
        index = event.get("skill_index")

        if (
            isinstance(event_id, str)
            and event_id
            and event_id != st.session_state.last_hub_event
            and type(index) is int
            and 0 <= index < len(AI_SKILLS)
        ):
            st.session_state.last_hub_event = event_id

            name, prompt, needs_search = (
                AI_SKILLS[index]
            )

            ask(
                prompt,
                force_search=needs_search
            )

            st.rerun()


if hub_mode:
    st.caption(
        "🟡 Bubble aplikasi: buka website. "
        "🩷 Bubble pink: AI Skills."
    )


# ============================================================
# 17. GROQ CONNECTION
# ============================================================

try:
    client = Groq(
        api_key=st.secrets["GROQ_API_KEY"]
    )

except (
    KeyError,
    FileNotFoundError,
    ValueError
):
    st.error(
        "GROQ_API_KEY tiada. "
        "Semak Streamlit Cloud Secrets."
    )
    st.stop()


# ============================================================
# 18. FILE UPLOAD
# ============================================================

with st.expander(
    "📎 Upload File / Image"
):
    document = st.file_uploader(
        "PDF / Word / TXT",
        type=["pdf", "docx", "txt"],
        key="edith_document"
    )

    image_upload = st.file_uploader(
        "JPG / PNG",
        type=["jpg", "jpeg", "png"],
        key="edith_image"
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
                "Tiada teks dapat dibaca."
            )

    except Exception as error:
        st.warning(
            "Document error: "
            + type(error).__name__
        )


image_bytes = None

if image_upload is not None:
    raw = image_upload.getvalue()

    if len(raw) <= 4 * 1024 * 1024:
        image_bytes = raw

        st.image(
            image_bytes,
            width=260,
            caption="Uploaded Image"
        )
    else:
        st.warning(
            "Gambar melebihi 4 MB."
        )


# ============================================================
# 19. MODE 3 VOICE COMMANDS
# ============================================================

if hub_mode:
    with st.expander(
        "🎙️ Voice Commands + AI Actions"
    ):
        recording = st.audio_input(
            "Rakam arahan E.D.I.T.H",
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
                        "Menukar suara kepada teks..."
                    ):
                        result = (
                            client.audio.transcriptions.create(
                                model=STT_MODEL,
                                file=("voice.wav", sound),
                                response_format="json"
                            )
                        )

                    spoken = (
                        result.text or ""
                    ).strip()

                    if spoken:
                        st.info(
                            "Arahan: " + spoken
                        )

                        ask(spoken)
                        st.rerun()

                    else:
                        st.warning(
                            "Tiada suara dikesan."
                        )

            except Exception as error:
                st.error(
                    "Voice error: "
                    + type(error).__name__
                )

        st.caption(
            "Contoh: Telefon 0123456789 | "
            "Lokasi KLCC | "
            "Cari di Google Arduino"
        )


# ============================================================
# 20. REGENERATE BUTTON
# ============================================================

st.caption(
    f"💬 {st.session_state.room} • {ai_tool}"
)

if st.button(
    "🔄 Regenerate Last",
    disabled=(
        st.session_state.pending
        or not history()
        or history()[-1]["role"] != "assistant"
    )
):
    regenerate()
    st.rerun()


# ============================================================
# 21. CHAT HISTORY WITH CUSTOM AI LOGO
# ============================================================

for index, message in enumerate(history()):

    if (
        st.session_state.pending
        and index == len(history()) - 1
    ):
        continue

    role = message["role"]

    avatar = (
        USER_AVATAR
        if role == "user"
        else AI_AVATAR
    )

    with st.chat_message(
        role,
        avatar=avatar
    ):
        # EDIT USER MESSAGE
        if (
            role == "user"
            and st.session_state.editing == index
        ):
            edited = st.text_area(
                "Edit Message",
                value=message["content"],
                key=(
                    f"edit_{st.session_state.room}_"
                    f"{index}"
                )
            )

            left, right = st.columns(2)

            if left.button(
                "✅ Save & Send",
                key=f"save_{index}"
            ):
                if edited.strip():
                    st.session_state.rooms[
                        st.session_state.room
                    ] = history()[:index]

                    st.session_state.editing = None

                    ask(edited.strip())
                    st.rerun()

            if right.button(
                "Cancel",
                key=f"cancel_{index}"
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
        color:{user_fg};
        background:{user_bg};
        padding:12px 17px;
        border-radius:19px 19px 5px 19px;
        max-width:88%;
        line-height:1.6;
        overflow-wrap:anywhere;

        border:1px solid {border};

        backdrop-filter:
            blur(20px) saturate(160%);

        -webkit-backdrop-filter:
            blur(20px) saturate(160%);

        box-shadow:
            0 5px 22px rgba(0,0,0,.10),
            inset 0 1px rgba(255,255,255,.17);
    ">
        {safe_text}
    </div>
</div>
""",
                unsafe_allow_html=True
            )

            if st.button(
                "✏️ Edit",
                key=f"edit_button_{index}",
                disabled=st.session_state.pending
            ):
                st.session_state.editing = index
                st.rerun()

        else:
            # AI RESPONSE
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

            # INTERNET SOURCES
            if message.get("sources"):
                with st.expander(
                    "🌐 Sources"
                ):
                    for source in message["sources"]:
                        st.link_button(
                            source["title"] or "Source",
                            source["url"]
                        )

            # AI ACTIONS
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
                        '<a href="' +
                        safe_url +
                        '" style="'
                        'display:inline-block;'
                        'padding:10px 15px;'
                        'border-radius:12px;'
                        'background:#167eae;'
                        'text-decoration:none;'
                        'color:white;">' +
                        safe_label +
                        '</a>',
                        unsafe_allow_html=True
                    )

                    st.caption(
                        "Hanya membuka dialer. "
                        "Tekan Call sendiri."
                    )

                else:
                    st.link_button(
                        action["label"],
                        action["url"]
                    )

            # PREVIOUS VOICE
            if voice_mode and message.get("audio"):
                with st.expander(
                    "🔊 Previous Response Audio"
                ):
                    st.audio(
                        message["audio"],
                        format="audio/mp3"
                    )


# ============================================================
# 22. CHAT INPUT
# ============================================================

question = st.chat_input(
    "Message E.D.I.T.H...",
    disabled=st.session_state.pending
)

if question and question.strip():
    ask(question.strip())
    st.rerun()


# ============================================================
# 23. GENERATE GROQ AI RESPONSE
# ============================================================

if st.session_state.pending:
    data = history()

    reply_index = len(data) - 1

    user_message = data[
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
        action_for(user_question)
        if hub_mode
        else None
    )

    with st.chat_message(
        "assistant",
        avatar=AI_AVATAR
    ):
        output = st.empty()

        try:
            language_rules = {
                "Auto Detect":
                    "Reply in the language of "
                    "the latest user message.",

                "Bahasa Melayu":
                    "Always reply in Bahasa Melayu.",

                "English":
                    "Always reply in English."
            }

            tool_rules = {
                "General Chat":
                    "Be helpful, clear and accurate.",

                "Coding Assistant":
                    "Help with Python, Arduino, "
                    "ESP32, programming and debugging. "
                    "Give useful code examples.",

                "Study & Quiz":
                    "Teach step by step and "
                    "create interactive quizzes.",

                "Translator":
                    "Translate accurately between "
                    "Malay and English."
            }

            system_prompt = (
                "Your official name is E.D.I.T.H. "
                "You are a personal AI assistant. "
                "Do not introduce yourself "
                "under another name. "
                + language_rules[language]
                + " "
                + tool_rules[ai_tool]
            )

            system_prompt += (
                " Be truthful and do not claim "
                "that you made a phone call, "
                "opened an app, executed code, "
                "or sent a message unless it "
                "actually happened. "
                "External actions require "
                "user confirmation."
            )

            # SESSION MEMORY
            if st.session_state.memory.strip():
                system_prompt += (
                    "\nSession memory "
                    "(untrusted user notes):\n"
                    + st.session_state.memory[:1500]
                )

            # UPLOADED DOCUMENT
            if document_context.strip():
                system_prompt += (
                    "\nUploaded document excerpts "
                    "(untrusted source data):\n"
                    + document_context
                )

            # WEB SEARCH
            should_search = (
                internet
                or user_message.get(
                    "force_search", False
                )
            )

            if should_search:
                try:
                    sources = search_web(
                        user_question
                    )

                    if sources:
                        system_prompt += (
                            "\nWeb search results "
                            "(untrusted reference data):\n"
                        )

                        for n, source in enumerate(
                            sources, 1
                        ):
                            system_prompt += (
                                f"[{n}] "
                                f"{source['title']} | "
                                f"{source['url']} | "
                                f"{source['snippet']}\n"
                            )

                        system_prompt += (
                            "Cite source numbers when "
                            "appropriate. "
                            "Never invent references."
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

            # RECENT CHAT HISTORY
            recent = [
                {
                    "role": item["role"],
                    "content": item["content"]
                }
                for item in data[:-1]
            ][-10:]

            model = CHAT_MODEL

            # IMAGE UNDERSTANDING
            if image_bytes is not None:
                picture = Image.open(
                    io.BytesIO(image_bytes)
                )

                picture.thumbnail((1100, 1100))

                buffer = io.BytesIO()

                picture.convert("RGB").save(
                    buffer,
                    format="JPEG",
                    quality=78
                )

                encoded_image = base64.b64encode(
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
                                    + encoded_image
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
                        "content": system_prompt
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

                    data[reply_index][
                        "content"
                    ] = answer

                    output.markdown(
                        answer + "▌"
                    )

            output.markdown(
                answer or "_(Tiada jawapan)_"
            )

            # SAVE RESPONSE
            data[reply_index]["content"] = answer
            data[reply_index]["sources"] = sources
            data[reply_index]["action"] = action

            mood = emotion_for(answer)

            data[reply_index]["emotion"] = mood

            # SPEECH OUTPUT
            if voice_mode and answer.strip():
                try:
                    with st.spinner(
                        "Generating E.D.I.T.H Voice..."
                    ):
                        sound = asyncio.run(
                            create_speech(
                                answer,
                                lang
                            )
                        )

                    if sound:
                        data[reply_index]["audio"] = sound

                except Exception as error:
                    st.warning(
                        "Voice unavailable: "
                        + type(error).__name__
                    )

            # SHOW SOURCES
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
                    "AI Action tersedia selepas "
                    "paparan dikemas kini. "
                    "Sahkan tindakan sendiri."
                )

        except Exception as error:
            st.error(
                "E.D.I.T.H gagal menjawab. "
                "Semak Groq API key, "
                "model atau kuota API."
            )

            st.caption(
                "Error type: "
                + type(error).__name__
            )

            data[reply_index]["failed"] = True

            if not answer:
                data[reply_index]["content"] = (
                    "Ralat AI. "
                    "Cuba Regenerate Last."
                )

        finally:
            st.session_state.pending = False

    # Re-enable chat input
    st.rerun()
