
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
from ddgs import DDGS
from docx import Document
from edge_tts import Communicate
from groq import Groq
from PIL import Image
from pypdf import PdfReader


# ======================================================
# E.D.I.T.H - GALAXY NEURAL V3
#
# MODE 1 - CHAT ONLY
# MODE 2 - HOLOGRAPHIC VOICE CORE
# MODE 3 - GALAXY NEURAL V3
#
# 55 BUBBLES:
# 20 APP LAUNCHERS + 35 AI SKILLS
#
# All bubble names are INSIDE each bubble.
# Real Web Audio API reactive animation.
# Clickable app links and AI commands.
# ======================================================

st.set_page_config(
    page_title="E.D.I.T.H",
    page_icon="🤖",
    layout="centered"
)

CHAT_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
STT_MODEL = "whisper-large-v3-turbo"


# ======================================================
# 1. SESSION STATE
# ======================================================

if "rooms" not in st.session_state:
    st.session_state.rooms = {"Chat 1": []}

defaults = {
    "room": "Chat 1",
    "memory": "",
    "pending": False,
    "editing": None,
    "last_bubble_event": "",
    "active_bubble": "",
    "voice_record_id": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def history():
    return st.session_state.rooms[st.session_state.room]


def empty_assistant():
    return {
        "role": "assistant",
        "content": "",
        "sources": [],
        "audio": None,
        "emotion": "neutral",
        "action": None
    }


def ask(text, search=False):
    history().append({
        "role": "user",
        "content": text,
        "force_search": search
    })
    history().append(empty_assistant())
    st.session_state.pending = True


def new_chat():
    i = 1
    while f"Chat {i}" in st.session_state.rooms:
        i += 1

    name = f"Chat {i}"
    st.session_state.rooms[name] = []
    st.session_state.room = name
    st.session_state.editing = None
    st.session_state.active_bubble = ""


def regenerate():
    data = history()

    if data and data[-1]["role"] == "assistant":
        data.pop()

    if data and data[-1]["role"] == "user":
        data.append(empty_assistant())
        st.session_state.pending = True


# ======================================================
# 2. LANGUAGE AND EMOTION
# ======================================================

def detect_language(text, setting):
    if setting == "Bahasa Melayu":
        return "ms"
    if setting == "English":
        return "en"

    malay = {
        "saya", "awak", "boleh", "tolong", "apa",
        "macam", "mana", "nak", "tak", "buat",
        "cari", "ajar", "belajar", "terangkan",
        "projek", "bagaimana", "kenapa", "telefon",
        "lokasi", "panggil", "berikan", "bantu"
    }

    words = set(re.findall(r"\w+", text.lower()))
    return "ms" if words & malay else "en"


def emotion_for(text):
    value = text.lower()

    if any(w in value for w in [
        "sedih", "takziah", "sorry", "dukacita"
    ]):
        return "sad"

    if any(w in value for w in [
        "tahniah", "bagus", "gembira", "excellent"
    ]):
        return "happy"

    if any(w in value for w in [
        "wow", "wah", "amazing", "menakjubkan"
    ]):
        return "surprised"

    return "neutral"


# ======================================================
# 3. TEXT TO SPEECH
# ======================================================

async def synthesize(text, lang):
    voice = (
        "ms-MY-YasminNeural"
        if lang == "ms"
        else "en-US-JennyNeural"
    )

    speaker = Communicate(
        text=text[:1800],
        voice=voice
    )

    result = bytearray()

    async for packet in speaker.stream():
        if packet["type"] == "audio":
            result.extend(packet["data"])

    return bytes(result)


# ======================================================
# 4. DOCUMENT UPLOAD
# ======================================================

def read_document(upload):
    data = upload.getvalue()

    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Maximum document size is 8 MB")

    filename = upload.name.lower()

    if filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        content = "\n".join(
            p.extract_text() or ""
            for p in reader.pages[:20]
        )

    elif filename.endswith(".docx"):
        doc = Document(io.BytesIO(data))

        pieces = [p.text for p in doc.paragraphs]

        for table in doc.tables:
            for row in table.rows:
                pieces.append(
                    " | ".join(cell.text for cell in row.cells)
                )

        content = "\n".join(pieces)

    else:
        content = data.decode("utf-8", errors="replace")

    return content[:12000]


# ======================================================
# 5. INTERNET SEARCH
# ======================================================

def search_web(question):
    results = DDGS(timeout=12).text(
        question,
        max_results=4
    ) or []

    sources = []

    for item in results:
        url = str(item.get("href", ""))

        if urlparse(url).scheme not in ("http", "https"):
            continue

        sources.append({
            "title": str(item.get("title", ""))[:120],
            "url": url,
            "snippet": str(item.get("body", ""))[:450]
        })

    return sources


# ======================================================
# 6. VOICE / TEXT AI ACTIONS
# ======================================================

def action_for(text):
    text = text.strip()

    phone = re.search(
        r"(?:telefon|call|dial|panggil)\s+"
        r"(?:nombor\s+|number\s+)?"
        r"(\+?[\d][\d\s\-()]{6,}[\d])",
        text,
        re.I
    )

    if phone:
        number = re.sub(r"[^\d+]", "", phone.group(1))

        if re.fullmatch(r"\+?\d{7,15}", number):
            return {
                "kind": "dial",
                "label": "📞 Buka Phone: " + number,
                "url": "tel:" + number
            }

    maps = re.search(
        r"(?:lokasi|maps? ke|pergi ke|"
        r"arah ke|navigate to|directions to)\s+(.+)",
        text,
        re.I
    )

    if maps:
        location = maps.group(1).strip(" .?!")[:120]

        if location:
            return {
                "kind": "maps",
                "label": "📍 Google Maps",
                "url": (
                    "https://www.google.com/maps/"
                    "search/?api=1&query="
                    + quote_plus(location)
                )
            }

    google = re.search(
        r"^(?:cari di google|cari web|"
        r"google|search web)\s+(.+)",
        text,
        re.I
    )

    if google:
        query = google.group(1).strip()[:150]

        if query:
            return {
                "kind": "search",
                "label": "🔎 Google Search",
                "url": (
                    "https://www.google.com/search?q="
                    + quote_plus(query)
                )
            }

    return None


# ======================================================
# 7. FIFTY-FIVE INTERACTIVE BUBBLES
#
# FORMAT:
# (Name, Icon, Type, Destination/Prompt)
#
# Types:
# app    -> Show genuine clickable external link
# ai     -> Send prompt to Groq
# search -> Search web, then ask Groq
# ======================================================

BUBBLES = [

    # -------- 20 APP BUBBLES --------

    ("YouTube", "▶", "app", "https://www.youtube.com"),
    ("Google", "G", "app", "https://www.google.com"),
    ("WhatsApp", "✆", "app", "https://web.whatsapp.com"),
    ("Maps", "⌖", "app", "https://www.google.com/maps"),
    ("Gmail", "✉", "app", "https://mail.google.com"),

    ("Spotify", "♫", "app", "https://open.spotify.com"),
    ("GitHub", "⌘", "app", "https://github.com"),
    ("Wikipedia", "W", "app", "https://www.wikipedia.org"),
    ("Drive", "△", "app", "https://drive.google.com"),
    ("Translate", "文", "app", "https://translate.google.com"),

    ("Calendar", "▦", "app", "https://calendar.google.com"),
    ("Google Meet", "▣", "app", "https://meet.google.com"),
    ("Canva", "C", "app", "https://www.canva.com"),
    ("Netflix", "N", "app", "https://www.netflix.com"),
    ("TikTok", "♪", "app", "https://www.tiktok.com"),

    ("Instagram", "◎", "app", "https://www.instagram.com"),
    ("Facebook", "f", "app", "https://www.facebook.com"),
    ("ChatGPT", "✳", "app", "https://chatgpt.com"),
    ("Grok", "𝕏", "app", "https://grok.com"),
    ("Meta AI", "∞", "app", "https://www.meta.ai"),

    # -------- 35 AI BUBBLES --------

    ("AI Chat", "✧", "ai",
     "Perkenalkan E.D.I.T.H dan bantu saya memulakan perbualan."),

    ("Study", "📖", "ai",
     "Bantu saya belajar satu topik secara langkah demi langkah."),

    ("Quiz", "?", "ai",
     "Berikan kuiz pengetahuan am 5 soalan secara interaktif."),

    ("Math", "∑", "ai",
     "Ajar saya matematik dengan contoh dan penerangan."),

    ("Science", "⚗", "ai",
     "Terangkan satu konsep sains yang menarik."),

    ("English", "EN", "ai",
     "Bantu saya berlatih bahasa Inggeris."),

    ("Translator", "⇄", "ai",
     "Bantu saya menterjemah ayat antara bahasa Melayu dan English."),

    ("History", "⌛", "ai",
     "Ceritakan satu peristiwa sejarah yang penting."),

    ("Physics", "Φ", "ai",
     "Ajar saya asas fizik menggunakan contoh mudah."),

    ("Chemistry", "⚛", "ai",
     "Terangkan asas kimia untuk pelajar."),

    ("Python", "Py", "ai",
     "Ajar saya coding Python dengan contoh program."),

    ("Arduino", "∞", "ai",
     "Cadangkan projek Arduino dan berikan coding serta wiring."),

    ("ESP32", "32", "ai",
     "Ajar saya membina projek ESP32 dengan coding."),

    ("Debug", "⚙", "ai",
     "Ajar saya teknik debugging dan cara mengenal pasti error kod."),

    ("HTML", "<>", "ai",
     "Ajar saya asas HTML untuk membina website."),

    ("CSS", "#", "ai",
     "Ajar saya CSS untuk mereka bentuk website moden."),

    ("JavaScript", "JS", "ai",
     "Ajar saya JavaScript dengan contoh mudah."),

    ("C++", "C+", "ai",
     "Ajar saya asas C++ untuk mikropengawal."),

    ("IoT", "◉", "ai",
     "Cadangkan projek Internet of Things menggunakan sensor."),

    ("Robotics", "⚙", "ai",
     "Bantu saya merancang projek robotik dengan Arduino."),

    ("Sensors", "◈", "ai",
     "Terangkan jenis sensor elektronik dan kegunaannya."),

    ("Servo", "↻", "ai",
     "Ajar saya cara menggunakan servo motor bersama Arduino."),

    ("Circuit", "⌁", "ai",
     "Ajar saya asas litar elektronik dan komponen."),

    ("FYP", "★", "ai",
     "Cadangkan idea Final Year Project dalam bidang teknologi."),

    ("AI Project", "AI", "ai",
     "Cadangkan projek artificial intelligence untuk pemula."),

    ("Planner", "▤", "ai",
     "Buatkan pelan belajar selama seminggu."),

    ("Writing", "✎", "ai",
     "Ajar saya teknik penulisan yang baik."),

    ("Business", "$", "ai",
     "Cadangkan perniagaan teknologi modal rendah."),

    ("Prompt", "✦", "ai",
     "Ajar saya cara menulis prompt AI yang berkesan."),

    ("Coding", "{ }", "ai",
     "Bantu saya menulis dan memahami contoh kod Python."),

    ("AI News", "◉", "search",
     "Cari perkembangan berita AI terkini, ringkaskan bersama sumber."),

    ("Tech News", "⌁", "search",
     "Cari berita teknologi terkini dan berikan sumber."),

    ("Research", "⌕", "search",
     "Cari perkembangan robotik terkini dengan sumber rujukan."),

    ("Open Source", "⌘", "search",
     "Cari projek AI open source yang sesuai untuk pemula."),

    ("Malaysia Tech", "MY", "search",
     "Cari perkembangan teknologi terkini di Malaysia bersama sumber."),
]

assert len(BUBBLES) == 55


# ======================================================
# 8. GALAXY NEURAL V3 HTML COMPONENT
#
# Canvas with:
# - ALL 55 labelled bubbles
# - Icons INSIDE bubbles
# - Live frequency analysis
# - Clickable app selection
# - Real external links
# - AI click -> Python
# - Emotion colors
# - Neural links
# ======================================================

VISUAL_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport"
content="width=device-width, initial-scale=1">

<style>
* {
    box-sizing: border-box;
}

html, body {
    margin: 0;
    background: transparent;
    color: #e4f8ff;
    font-family: Arial, sans-serif;
    overflow-x: hidden;
}

.shell {
    text-align: center;
    padding: 6px 4px 12px;
    background:
        radial-gradient(
            ellipse at center,
            rgba(36,103,220,.18),
            transparent 75%
        );
}

.header {
    color: #baf5ff;
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 4px;
    text-shadow: 0 0 12px #38dfff;
    margin: 6px 0;
}

.sub {
    color: #97b7df;
    font: 11px monospace;
    letter-spacing: 1px;
    margin-bottom: 8px;
}

canvas {
    width: 100%;
    display: block;
    cursor: pointer;
    touch-action: manipulation;
}

#status {
    color: #8ee3ff;
    font: 11px monospace;
    letter-spacing: 2px;
    margin: 10px 0 6px;
}

#selection {
    font-size: 12px;
    min-height: 20px;
    color: #ffe0a8;
    margin-top: 5px;
}

#linkPanel {
    display: none;
    background: rgba(13,30,62,.95);
    border: 1px solid #4bbfff88;
    border-radius: 16px;
    padding: 12px;
    margin: 8px 10px;
}

#linkPanel p {
    margin: 4px 0 12px;
    font-size: 12px;
}

#openLink {
    display: inline-block;
    padding: 10px 18px;
    border-radius: 12px;
    background: linear-gradient(
        120deg,
        #117dd1,
        #774bd1
    );
    color: white;
    text-decoration: none;
    font-weight: bold;
    font-size: 13px;
}

#closeLink {
    display: inline-block;
    margin-left: 8px;
    border: 1px solid #679ac5;
    border-radius: 10px;
    color: white;
    background: #24395c;
    padding: 10px;
    font-size: 12px;
    cursor: pointer;
}

.legend {
    color: #9ab1d1;
    font-size: 11px;
    line-height: 1.7;
    margin: 9px 0;
}

audio {
    width: 92%;
    max-width: 350px;
    display: none;
    margin: 12px auto 0;
}

.holoCanvas {
    height: 265px;
}
</style>
</head>

<body>

<div class="shell">

    <div class="header">E.D.I.T.H</div>

    <div class="sub" id="subtitle">
        GALAXY NEURAL V3
    </div>

    <canvas id="galaxy"></canvas>

    <div id="status">STANDBY</div>

    <div id="selection">
        Tap any bubble to activate
    </div>

    <div id="linkPanel">
        <p id="linkTitle"></p>

        <a
            id="openLink"
            target="_blank"
            rel="noopener noreferrer"
        >
            Open App
        </a>

        <button id="closeLink" type="button">
            Close
        </button>
    </div>

    <div class="legend">
        🔵 AI Skills &nbsp; 🟣 Coding
        &nbsp; 🟠 App Launchers / Research
    </div>

    <audio id="speech" controls
        preload="metadata"></audio>

</div>

<script>
"use strict";

// ====================================================
// STREAMLIT BRIDGE
// ====================================================

function post(type, extra = {}) {
    window.parent.postMessage({
        isStreamlitMessage: true,
        type: type,
        ...extra
    }, "*");
}

function setHeight() {
    post("streamlit:setFrameHeight", {
        height: document.body.scrollHeight + 8
    });
}

post("streamlit:componentReady", {
    apiVersion: 1
});

// ====================================================
// ELEMENTS AND STATE
// ====================================================

const canvas = document.getElementById("galaxy");
const ctx = canvas.getContext("2d");

const audio = document.getElementById("speech");
const statusEl = document.getElementById("status");
const selectionEl = document.getElementById("selection");

const linkPanel = document.getElementById("linkPanel");
const linkTitle = document.getElementById("linkTitle");
const openLink = document.getElementById("openLink");
const closeLink = document.getElementById("closeLink");

let bubbles = [];
let mode = "neural";
let emotion = "neutral";
let isBusy = false;

let selected = -1;
let hovered = -1;

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

let w = 400;
let h = 930;

let time = 0;
let positions = [];

// 55 bubbles arranged across 5 columns and 11 rows.
// Text/icons remain legible on a mobile phone.

const COLS = 5;
const ROWS = 11;

function updateStatus() {
    statusEl.textContent = isBusy
        ? "THINKING"
        : speaking
            ? "SPEAKING"
            : "STANDBY";
}

// ====================================================
// AUDIO ANALYSER
// ====================================================

function setupAnalyser() {
    if (analyser) return;

    try {
        const AudioContextClass =
            window.AudioContext ||
            window.webkitAudioContext;

        audioContext = new AudioContextClass();

        analyser = audioContext.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.72;

        mediaSource =
            audioContext.createMediaElementSource(audio);

        mediaSource.connect(analyser);
        analyser.connect(audioContext.destination);

        frequency = new Uint8Array(
            analyser.frequencyBinCount
        );

        waveform = new Uint8Array(
            analyser.fftSize
        );

    } catch (err) {
        console.log("Analyser:", err);
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

audio.addEventListener("play", () => {
    resumeAudio();
    speaking = true;
    updateStatus();
});

audio.addEventListener("playing", () => {
    speaking = true;
    updateStatus();
});

audio.addEventListener("pause", () => {
    speaking = false;
    updateStatus();
});

audio.addEventListener("ended", () => {
    speaking = false;
    updateStatus();
});

function average(a, begin, end) {
    if (!a) return 0;

    let total = 0;
    let count = 0;

    for (let i = begin; i < end; i++) {
        total += a[i] / 255;
        count++;
    }

    return count ? total / count : 0;
}

function updateSound() {
    let nextEnergy = 0;
    let nextBass = 0;
    let nextMid = 0;
    let nextTreble = 0;

    if (speaking && analyser) {
        analyser.getByteFrequencyData(frequency);
        analyser.getByteTimeDomainData(waveform);

        const n = frequency.length;

        nextBass = average(
            frequency,
            1,
            Math.floor(n * .10)
        );

        nextMid = average(
            frequency,
            Math.floor(n * .10),
            Math.floor(n * .35)
        );

        nextTreble = average(
            frequency,
            Math.floor(n * .35),
            Math.floor(n * .85)
        );

        let sum = 0;

        for (let i = 0; i < waveform.length; i++) {
            const sample = (waveform[i] - 128) / 128;
            sum += sample * sample;
        }

        const rms = Math.sqrt(sum / waveform.length);

        nextEnergy = Math.min(
            1,
            rms * 4.5
        );
    }

    const speed = speaking ? .25 : .08;

    energy += (nextEnergy - energy) * speed;
    bass += (nextBass - bass) * speed;
    mid += (nextMid - mid) * speed;
    treble += (nextTreble - treble) * speed;
}

// ====================================================
// COLOR SYSTEM
// ====================================================

function getColor(index) {
    const item = bubbles[index];
    const type = item ? item[2] : "ai";

    if (emotion === "happy") {
        return type === "app"
            ? "#ffc86d"
            : "#6affd7";
    }

    if (emotion === "sad") {
        return type === "app"
            ? "#9ba5ff"
            : "#65caff";
    }

    if (emotion === "surprised") {
        return type === "app"
            ? "#ffad7d"
            : "#dc96ff";
    }

    if (type === "app") {
        return "#ffbd77";
    }

    if (type === "search") {
        return "#ed9dff";
    }

    if (index % 3 === 0) {
        return "#b89cff";
    }

    return "#65eaff";
}

// ====================================================
// CANVAS SIZE
// ====================================================

function resize() {
    const rect = canvas.getBoundingClientRect();

    w = rect.width || 390;

    if (mode === "holo") {
        h = 265;
    } else {
        const cell = w / COLS;
        h = Math.max(740, ROWS * cell * 1.09 + 30);
    }

    canvas.style.height = h + "px";

    const dpr = Math.min(
        window.devicePixelRatio || 1,
        2
    );

    canvas.width = w * dpr;
    canvas.height = h * dpr;

    ctx.setTransform(
        dpr, 0, 0, dpr, 0, 0
    );

    setHeight();
}

window.addEventListener("resize", resize);

// ====================================================
// POSITIONS
// ====================================================

function calculatePositions() {
    const cell = w / COLS;
    const vertical = (h - 26) / ROWS;

    positions = [];

    for (let i = 0; i < bubbles.length; i++) {
        const row = Math.floor(i / COLS);
        const col = i % COLS;

        const wave =
            Math.sin(
                time * 1.5 + i * .67
            ) * (1.3 + energy * 4);

        const x =
            cell * (col + .5) +
            wave;

        const y =
            vertical * (row + .5) +
            13 +
            Math.cos(
                time + i * .47
            ) * (1.5 + bass * 5);

        positions.push({
            x: x,
            y: y,
            r: Math.min(
                cell * .40,
                36
            )
        });
    }
}

// ====================================================
// TEXT INSIDE BUBBLES
// ====================================================

function wrapLabel(label) {
    if (label.length <= 10) {
        return [label];
    }

    const words = label.split(" ");

    if (words.length >= 2) {
        return words;
    }

    return [
        label.slice(0, 9),
        label.slice(9)
    ];
}

function drawBubble(index) {
    const item = bubbles[index];
    const p = positions[index];

    if (!item || !p) return;

    const selectedBubble = index === selected;

    const pulse =
        1 +
        energy * .13 +
        bass * .10 +
        Math.sin(
            time * 2.4 + index
        ) * .015;

    const r =
        p.r * pulse +
        (selectedBubble ? 2 : 0);

    const color = getColor(index);

    // Outer glow
    ctx.beginPath();
    ctx.arc(
        p.x,
        p.y,
        r + 3,
        0,
        Math.PI * 2
    );

    ctx.fillStyle = "rgba(8,22,49,.90)";
    ctx.fill();

    // Bubble gradient
    const gradient =
        ctx.createRadialGradient(
            p.x - r * .25,
            p.y - r * .32,
            2,
            p.x,
            p.y,
            r
        );

    gradient.addColorStop(
        0,
        "rgba(45,79,132,.94)"
    );

    gradient.addColorStop(
        1,
        "rgba(8,15,39,.98)"
    );

    ctx.beginPath();
    ctx.arc(
        p.x, p.y, r,
        0, Math.PI * 2
    );

    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.strokeStyle = color;
    ctx.lineWidth =
        selectedBubble ? 2.8 : 1.2;

    ctx.shadowBlur =
        selectedBubble ? 20 : 8 + energy * 20;

    ctx.shadowColor = color;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Icon INSIDE bubble
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.fillStyle = color;
    ctx.font = (
        "bold " +
        Math.max(13, Math.min(19, r * .48)) +
        "px Arial"
    );

    ctx.fillText(
        item[1],
        p.x,
        p.y - r * .30
    );

    // Name INSIDE bubble
    const lines = wrapLabel(item[0]);

    ctx.fillStyle = "#eefaff";
    ctx.font =
        "bold " +
        Math.max(7, Math.min(10, r * .26)) +
        "px Arial";

    if (lines.length === 1) {
        ctx.fillText(
            lines[0],
            p.x,
            p.y + r * .34,
            r * 1.8
        );
    } else {
        ctx.fillText(
            lines[0],
            p.x,
            p.y + r * .20,
            r * 1.85
        );

        ctx.fillText(
            lines.slice(1).join(" "),
            p.x,
            p.y + r * .49,
            r * 1.85
        );
    }

    // Small activity indicator
    if (selectedBubble) {
        ctx.beginPath();
        ctx.arc(
            p.x + r * .68,
            p.y - r * .70,
            3.6,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "#ffffff";
        ctx.fill();
    }
}

// ====================================================
// NEURAL CONNECTIONS
// ====================================================

function drawConnections() {
    for (let i = 0; i < positions.length; i++) {
        const a = positions[i];

        for (let j = i + 1; j < positions.length; j++) {
            const b = positions[j];

            const d = Math.hypot(
                a.x - b.x,
                a.y - b.y
            );

            if (d < w / COLS * 1.65) {
                const opacity =
                    (1 - d / (w / COLS * 1.65)) *
                    (.18 + energy * .38);

                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);

                ctx.strokeStyle =
                    "rgba(99,219,255," +
                    opacity.toFixed(3) +
                    ")";

                ctx.lineWidth = .8 + bass * 1.2;
                ctx.stroke();
            }
        }
    }
}

// ====================================================
// MODE 2 - HOLOGRAPHIC CORE
// ====================================================

function drawHolo() {
    const cx = w / 2;
    const cy = h / 2;

    for (let k = 0; k < 3; k++) {
        ctx.save();
        ctx.translate(cx, cy);

        ctx.rotate(
            time * (k % 2 ? -.6 : .7)
        );

        ctx.beginPath();
        ctx.setLineDash(
            k === 1 ? [4, 8] : [23, 14]
        );

        ctx.strokeStyle = [
            "#65eaff",
            "#b18cff",
            "#4c8cff"
        ][k];

        ctx.lineWidth = 1.6;

        ctx.arc(
            0, 0,
            64 + k * 22 + energy * 8,
            0, Math.PI * 2
        );

        ctx.stroke();
        ctx.restore();
    }

    const radius = 51 + energy * 17;

    const gradient =
        ctx.createRadialGradient(
            cx - 14,
            cy - 18,
            1,
            cx,
            cy,
            radius
        );

    gradient.addColorStop(0, "#ffffff");
    gradient.addColorStop(.23, "#79efff");
    gradient.addColorStop(.58, "#586bec");
    gradient.addColorStop(1, "#17134e");

    ctx.beginPath();
    ctx.arc(
        cx, cy, radius,
        0, Math.PI * 2
    );

    ctx.fillStyle = gradient;
    ctx.shadowColor = "#4cdfff";
    ctx.shadowBlur = 27 + energy * 20;
    ctx.fill();
    ctx.shadowBlur = 0;

    drawAudioBars(cx, h - 7);
}

// ====================================================
// AUDIO BARS
// ====================================================

function drawAudioBars(cx, bottom) {
    for (let i = 0; i < 19; i++) {
        let value = 0;

        if (speaking && frequency) {
            const idx = Math.min(
                frequency.length - 1,
                i * 5
            );

            value = frequency[idx] / 255;
        }

        const barHeight =
            3 + value * 25;

        ctx.fillStyle =
            i % 3 === 0
                ? "#b99bff"
                : "#65eaff";

        ctx.fillRect(
            cx - 80 + i * 8.5,
            bottom - barHeight,
            4,
            barHeight
        );
    }
}

// ====================================================
// ANIMATION
// ====================================================

function frame() {
    requestAnimationFrame(frame);

    if (document.hidden) return;

    time += speaking ? .033 : .012;

    updateSound();

    ctx.clearRect(
        0, 0, w, h
    );

    if (mode === "holo") {
        drawHolo();
        return;
    }

    // Galaxy aura
    const aura = ctx.createRadialGradient(
        w / 2,
        h / 2,
        10,
        w / 2,
        h / 2,
        h * .55
    );

    aura.addColorStop(
        0,
        "rgba(55,92,210,.13)"
    );

    aura.addColorStop(
        .55,
        "rgba(111,61,196,.08)"
    );

    aura.addColorStop(
        1,
        "rgba(0,0,0,0)"
    );

    ctx.fillStyle = aura;
    ctx.fillRect(0, 0, w, h);

    calculatePositions();
    drawConnections();

    for (let i = 0; i < bubbles.length; i++) {
        drawBubble(i);
    }

    drawAudioBars(w / 2, h - 4);
}

// ====================================================
// CLICK DETECTION
// ====================================================

function clickPosition(event) {
    const rect = canvas.getBoundingClientRect();

    return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
    };
}

function bubbleAt(event) {
    const p = clickPosition(event);

    let match = -1;
    let best = Infinity;

    for (let i = 0; i < positions.length; i++) {
        const node = positions[i];

        const d = Math.hypot(
            p.x - node.x,
            p.y - node.y
        );

        // Slightly enlarged touch target
        if (d < node.r + 5 && d < best) {
            match = i;
            best = d;
        }
    }

    return match;
}

canvas.addEventListener(
    "pointermove",
    event => {
        if (mode === "holo") return;

        hovered = bubbleAt(event);

        canvas.style.cursor =
            hovered >= 0 ? "pointer" : "default";

        canvas.title =
            hovered >= 0
                ? bubbles[hovered][0]
                : "";
    }
);

canvas.addEventListener(
    "click",
    event => {
        if (
            mode === "holo" ||
            isBusy
        ) {
            return;
        }

        const i = bubbleAt(event);

        if (i < 0 || !bubbles[i]) return;

        selected = i;

        const chosen = bubbles[i];
        const name = chosen[0];
        const type = chosen[2];
        const target = chosen[3];

        selectionEl.textContent =
            "Selected: " + name;

        if (type === "app") {

            // The app-opening control is INSIDE
            // the Galaxy interface.
            // A real user click opens the link.

            linkTitle.textContent =
                "Open " + name + "?";

            openLink.textContent =
                "Buka " + name;

            openLink.href = target;

            linkPanel.style.display = "block";
            setHeight();

        } else {

            linkPanel.style.display = "none";

            // Send bubble command to Streamlit
            post(
                "streamlit:setComponentValue",
                {
                    value: {
                        id:
                            Date.now().toString() +
                            "-" +
                            Math.random().toString(36),
                        index: i
                    }
                }
            );
        }
    }
);

closeLink.addEventListener(
    "click",
    () => {
        linkPanel.style.display = "none";
        setHeight();
    }
);

// ====================================================
// STREAMLIT RENDER
// ====================================================

window.addEventListener(
    "message",
    event => {
        if (
            !event.data ||
            event.data.type !== "streamlit:render"
        ) {
            return;
        }

        const args = event.data.args || {};

        bubbles = Array.isArray(args.bubbles)
            ? args.bubbles
            : [];

        mode = args.mode || "neural";
        emotion = args.emotion || "neutral";
        isBusy = !!args.busy;

        const newAudio = args.audio || "";

        if (newAudio !== audioValue) {
            audioValue = newAudio;

            audio.pause();

            if (audioValue) {
                audio.src =
                    "data:audio/mpeg;base64," +
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
            mode === "holo"
                ? "HOLOGRAPHIC VOICE CORE"
                : "GALAXY NEURAL V3 • 55 BUBBLES";

        selectionEl.textContent =
            mode === "holo"
                ? "Voice Core Ready"
                : "Tap a bubble to activate";

        linkPanel.style.display = "none";

        updateStatus();
        resize();
    }
);

resize();
frame();
setHeight();

</script>

</body>
</html>
"""


# ======================================================
# 9. BUILD CUSTOM COMPONENT AUTOMATICALLY
# ======================================================

@st.cache_resource
def create_galaxy_component():
    folder = (
        Path(tempfile.gettempdir())
        / "edith_galaxy_v3"
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
        "edith_galaxy_v3",
        path=str(folder)
    )


galaxy_component = create_galaxy_component()


def render_visual(mode, audio=None, emotion="neutral"):
    audio_base64 = (
        base64.b64encode(audio).decode("ascii")
        if audio
        else ""
    )

    frontend_bubbles = [
        [name, icon, kind, value]
        for name, icon, kind, value in BUBBLES
    ]

    return galaxy_component(
        bubbles=frontend_bubbles,
        mode=mode,
        emotion=emotion,
        audio=audio_base64,
        busy=st.session_state.pending,
        default=None,
        key="edith_galaxy_v3_visual"
    )


# ======================================================
# 10. SIDEBAR
# ======================================================

with st.sidebar:
    st.header("⚙️ E.D.I.T.H Settings")

    mode = st.radio(
        "AI Mode",
        [
            "Mode 1 - Chat Only",
            "Mode 2 - Holographic Voice Core",
            "Mode 3 - Galaxy Neural V3"
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
        "Memory dan Chat History untuk "
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

    names = list(st.session_state.rooms)

    selected_room = st.selectbox(
        "Chat History",
        names,
        index=names.index(st.session_state.room),
        disabled=st.session_state.pending
    )

    if selected_room != st.session_state.room:
        st.session_state.room = selected_room
        st.session_state.editing = None
        st.rerun()


# ======================================================
# 11. QUANTUM ENERGY FLOW + CHATGPT STYLE
# ======================================================

if theme == "Light":
    background = "#f7f9ff"
    foreground = "#17233c"
    user_bg = "#dfeafe"
    user_fg = "#15213d"
    sidebar_bg = "rgba(245,249,255,.97)"
    chat_bg = "rgba(255,255,255,.96)"

elif theme == "Ocean Blue":
    background = "#07172e"
    foreground = "#e8f6ff"
    user_bg = "#174775"
    user_fg = "#ffffff"
    sidebar_bg = "rgba(5,23,46,.96)"
    chat_bg = "rgba(15,48,86,.97)"

else:
    background = "#080f20"
    foreground = "#ecf5ff"
    user_bg = "#354c73"
    user_fg = "#ffffff"
    sidebar_bg = "rgba(9,16,33,.96)"
    chat_bg = "rgba(22,34,60,.96)"


st.markdown(
    f"""
<style>

.stApp {{
    background:
        radial-gradient(
            ellipse at 18% 17%,
            rgba(46,149,245,.16),
            transparent 40%
        ),
        radial-gradient(
            ellipse at 84% 66%,
            rgba(149,74,230,.16),
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
            ellipse at 20% 40%,
            rgba(38,188,255,.15),
            transparent 35%
        ),
        radial-gradient(
            ellipse at 80% 35%,
            rgba(167,85,247,.14),
            transparent 35%
        );

    animation:
        quantumMove 18s
        ease-in-out infinite alternate;
}}

@keyframes quantumMove {{
    from {{
        transform:translate(-2%,0%) scale(1);
    }}
    to {{
        transform:translate(2%,-2%) scale(1.06);
    }}
}}

[data-testid="stHeader"] {{
    background:transparent;
}}

[data-testid="stSidebar"] > div:first-child {{
    background:{sidebar_bg};
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
    margin-bottom:5px;
}}

[data-testid="stChatMessageContent"] {{
    line-height:1.7;
}}

[data-testid="stChatInput"] > div {{
    background:{chat_bg};
    border-radius:22px;
    border:1px solid rgba(130,170,250,.23);
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


# ======================================================
# 12. MAIN APP
# ======================================================

st.title("🤖 E.D.I.T.H")

st.caption(
    "Your Personal AI Assistant • Galaxy Neural V3"
)

voice_mode = (
    mode.startswith("Mode 2")
    or mode.startswith("Mode 3")
)

neural_mode = mode.startswith("Mode 3")


# ======================================================
# 13. VISUAL + BUBBLE ACTION HANDLER
# ======================================================

if voice_mode:

    last_audio_message = next(
        (
            message
            for message in reversed(history())
            if (
                message["role"] == "assistant"
                and message.get("audio")
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
            "emotion",
            "neutral"
        )
        if last_audio_message
        else "neutral"
    )

    bubble_event = render_visual(
        mode=(
            "neural"
            if neural_mode
            else "holo"
        ),
        audio=last_audio,
        emotion=last_emotion
    )

    if (
        neural_mode
        and not st.session_state.pending
        and isinstance(bubble_event, dict)
    ):
        event_id = bubble_event.get("id")
        index = bubble_event.get("index")

        if (
            isinstance(event_id, str)
            and event_id
            and event_id != st.session_state.last_bubble_event
            and type(index) is int
            and 0 <= index < len(BUBBLES)
        ):
            st.session_state.last_bubble_event = event_id

            name, icon, kind, target = BUBBLES[index]

            # External app links are handled by
            # the HTML component's link panel.
            # AI commands are executed here.
            if kind in ("ai", "search"):
                st.session_state.active_bubble = name

                ask(
                    target,
                    search=(kind == "search")
                )

                st.rerun()

if neural_mode:
    st.caption(
        "🫧 Tekan simbol dan nama di dalam bubble. "
        "Bubble aplikasi membuka panel pautan; "
        "bubble AI menghantar arahan kepada Groq."
    )


# ======================================================
# 14. GROQ CONNECTION
# ======================================================

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
        "GROQ_API_KEY tiada dalam Streamlit "
        "Cloud Secrets."
    )
    st.stop()


# ======================================================
# 15. FILE UPLOAD
# ======================================================

with st.expander(
    "📎 Upload File / Image"
):
    document = st.file_uploader(
        "PDF / Word / TXT",
        type=["pdf", "docx", "txt"]
    )

    image_upload = st.file_uploader(
        "JPG / PNG",
        type=["jpg", "jpeg", "png"]
    )

doc_context = ""

if document is not None:
    try:
        doc_context = read_document(document)

        if doc_context.strip():
            st.success("Dokumen berjaya dibaca.")
        else:
            st.warning("Tiada teks ditemui.")

    except Exception as error:
        st.warning(
            "Document error: "
            + type(error).__name__
        )

image_bytes = None

if image_upload is not None:
    image_bytes = image_upload.getvalue()

    if len(image_bytes) <= 4 * 1024 * 1024:
        st.image(
            image_bytes,
            width=250,
            caption="Uploaded Image"
        )
    else:
        st.warning("Gambar melebihi 4 MB.")
        image_bytes = None


# ======================================================
# 16. VOICE COMMANDS - MODE 3
# ======================================================

if neural_mode:

    with st.expander(
        "🎙️ Voice Commands + AI Actions"
    ):

        recorded = st.audio_input(
            "Rakam arahan suara E.D.I.T.H",
            sample_rate=16000
        )

        if st.button(
            "🎙️ Hantar Arahan Suara",
            disabled=(
                st.session_state.pending
                or recorded is None
            )
        ):
            try:
                sound = recorded.getvalue()

                if not sound:
                    st.warning("Rakaman kosong.")

                elif len(sound) > 20 * 1024 * 1024:
                    st.warning("Rakaman terlalu besar.")

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

                    transcript = (
                        result.text or ""
                    ).strip()

                    if transcript:
                        ask(transcript)
                        st.rerun()
                    else:
                        st.warning(
                            "Tiada arahan suara dikesan."
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


# ======================================================
# 17. CHAT ACTIONS
# ======================================================

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


# ======================================================
# 18. SHOW CHAT HISTORY
# ======================================================

for i, message in enumerate(history()):

    if (
        st.session_state.pending
        and i == len(history()) - 1
    ):
        continue

    role = message["role"]

    with st.chat_message(
        role,
        avatar="👤" if role == "user" else "🤖"
    ):

        if (
            role == "user"
            and st.session_state.editing == i
        ):
            edited = st.text_area(
                "Edit Message",
                value=message["content"],
                key=f"edit_{st.session_state.room}_{i}"
            )

            c1, c2 = st.columns(2)

            if c1.button(
                "✅ Save & Send",
                key=f"save_{i}"
            ):
                if edited.strip():
                    st.session_state.rooms[
                        st.session_state.room
                    ] = history()[:i]

                    st.session_state.editing = None

                    ask(edited.strip())
                    st.rerun()

            if c2.button(
                "Cancel",
                key=f"cancel_{i}"
            ):
                st.session_state.editing = None
                st.rerun()

        elif role == "user":

            safe = html.escape(
                message["content"]
            ).replace("\n", "<br>")

            st.markdown(
                f"""
<div style="
    display:flex;
    justify-content:flex-end;
">
    <div style="
        background:{user_bg};
        color:{user_fg};
        padding:12px 17px;
        max-width:88%;
        border-radius:19px 19px 5px 19px;
        overflow-wrap:anywhere;
        line-height:1.6;
    ">
        {safe}
    </div>
</div>
""",
                unsafe_allow_html=True
            )

            if st.button(
                "✏️ Edit",
                key=f"edit_{i}",
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
                    "**AI Action — pengesahan pengguna:**"
                )

                if action["kind"] == "dial":

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
                        + '" style="display:inline-block;'
                        + 'padding:10px 15px;'
                        + 'background:#1680ae;'
                        + 'border-radius:12px;'
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

            if voice_mode and message.get("audio"):
                with st.expander(
                    "🔊 Previous Response Audio"
                ):
                    st.audio(
                        message["audio"],
                        format="audio/mp3"
                    )


# ======================================================
# 19. CHAT INPUT
# ======================================================

question = st.chat_input(
    "Message E.D.I.T.H...",
    disabled=st.session_state.pending
)

if question and question.strip():
    ask(question.strip())
    st.rerun()


# ======================================================
# 20. GENERATE GROQ RESPONSE
# ======================================================

if st.session_state.pending:

    data = history()

    reply_index = len(data) - 1
    user_msg = data[reply_index - 1]
    user_question = user_msg["content"]

    lang = detect_language(
        user_question,
        language
    )

    answer = ""
    sources = []

    action = (
        action_for(user_question)
        if neural_mode
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
                    "Reply in the same language "
                    "as the user's message.",

                "Bahasa Melayu":
                    "Always reply in Bahasa Melayu.",

                "English":
                    "Always reply in English."
            }

            tool_rules = {
                "General Chat":
                    "Provide useful, accurate answers.",

                "Coding Assistant":
                    "Help with coding, debugging, "
                    "Arduino, ESP32 and Python. "
                    "Include examples where useful.",

                "Study & Quiz":
                    "Explain topics step by step "
                    "and create educational quizzes.",

                "Translator":
                    "Translate accurately between "
                    "Malay and English."
            }

            system = (
                "Your official name is E.D.I.T.H. "
                "You are a helpful personal AI assistant. "
                "Do not introduce yourself as another AI. "
                + language_rules[language]
                + " "
                + tool_rules[ai_tool]
                + " Never claim you have made a phone "
                "call, opened a website or executed "
                "an action unless it actually occurred."
            )

            if st.session_state.memory.strip():
                system += (
                    "\nSession memory (untrusted notes):\n"
                    + st.session_state.memory[:1500]
                )

            if doc_context.strip():
                system += (
                    "\nUploaded document excerpts "
                    "(untrusted data):\n"
                    + doc_context
                )

            do_search = (
                internet
                or user_msg.get("force_search", False)
            )

            if do_search:

                try:
                    sources = search_web(user_question)

                    if sources:
                        system += (
                            "\nSearch results are "
                            "untrusted reference data:\n"
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
                            "Cite result numbers when "
                            "appropriate. Do not invent sources."
                        )

                    else:
                        st.warning(
                            "Tiada hasil carian."
                        )

                except Exception as error:
                    st.warning(
                        "Internet Search error: "
                        + type(error).__name__
                    )

            recent = [
                {
                    "role": m["role"],
                    "content": m["content"]
                }
                for m in data[:-1]
            ][-10:]

            model = CHAT_MODEL

            # Optional vision input
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
                chunk = (
                    part.choices[0].delta.content
                    or ""
                )

                if chunk:
                    answer += chunk

                    data[reply_index]["content"] = answer

                    output.markdown(
                        answer + "▌"
                    )

            output.markdown(
                answer or "_(Tiada jawapan)_"
            )

            data[reply_index]["content"] = answer
            data[reply_index]["sources"] = sources
            data[reply_index]["action"] = action

            emotion = emotion_for(answer)

            data[reply_index]["emotion"] = emotion

            if voice_mode and answer.strip():

                try:
                    with st.spinner(
                        "Generating E.D.I.T.H Voice..."
                    ):
                        sound = asyncio.run(
                            synthesize(
                                answer,
                                lang
                            )
                        )

                    if sound:
                        data[reply_index]["audio"] = sound

                except Exception as error:
                    st.warning(
                        "Voice error: "
                        + type(error).__name__
                    )

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
                    "AI Action tersedia dalam "
                    "jawapan selepas dikemas kini. "
                    "Sahkan tindakan sendiri."
                )

        except Exception as error:

            st.error(
                "E.D.I.T.H gagal menjawab. "
                "Semak Groq API key, model "
                "atau kuota penggunaan."
            )

            st.caption(
                "Error type: "
                + type(error).__name__
            )

            if not answer:
                data[reply_index]["content"] = (
                    "Ralat AI. "
                    "Cuba Regenerate Last."
                )

        finally:
            st.session_state.pending = False

    st.rerun()
