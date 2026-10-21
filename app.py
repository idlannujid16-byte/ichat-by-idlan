
import asyncio
import base64
import html
import io
import json
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


# ====================================================
# E.D.I.T.H - GALAXY NEURAL V2
#
# MODE 1: CHAT ONLY
# MODE 2: HOLOGRAPHIC VOICE CORE
# MODE 3: 55 INTERACTIVE REACTIVE BUBBLES
#
# Features:
# Groq / Voice Commands / Web Audio API
# Memory / Chat History / Image & Document Reading
# Search / AI Actions / Edit / Regenerate
# Quantum Energy Flow / ChatGPT Style
#
# No Stop Generating button
# ====================================================

st.set_page_config(
    page_title="E.D.I.T.H",
    page_icon="🤖",
    layout="centered"
)

CHAT_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = (
    "meta-llama/llama-4-scout-17b-16e-instruct"
)
STT_MODEL = "whisper-large-v3-turbo"


# ====================================================
# 1. SESSION STATE
# ====================================================

if "rooms" not in st.session_state:
    st.session_state.rooms = {
        "Chat 1": []
    }

DEFAULTS = {
    "room": "Chat 1",
    "memory": "",
    "pending": False,
    "editing": None,
    "bubble_event_seen": None,
    "last_voice_signature": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def history():
    return st.session_state.rooms[
        st.session_state.room
    ]


def new_chat():
    i = 1

    while f"Chat {i}" in st.session_state.rooms:
        i += 1

    name = f"Chat {i}"
    st.session_state.rooms[name] = []
    st.session_state.room = name
    st.session_state.editing = None


def ask(question, force_search=False):
    history().append({
        "role": "user",
        "content": question,
        "force_search": force_search
    })

    history().append({
        "role": "assistant",
        "content": "",
        "sources": [],
        "audio": None,
        "emotion": "neutral",
        "action": None,
        "failed": False
    })

    st.session_state.pending = True


def regenerate():
    messages = history()

    if messages and messages[-1]["role"] == "assistant":
        messages.pop()

    if messages and messages[-1]["role"] == "user":
        messages.append({
            "role": "assistant",
            "content": "",
            "sources": [],
            "audio": None,
            "emotion": "neutral",
            "action": None,
            "failed": False
        })

        st.session_state.pending = True


# ====================================================
# 2. LANGUAGE
# ====================================================

def detect_language(text, setting):
    if setting == "Bahasa Melayu":
        return "ms"

    if setting == "English":
        return "en"

    malay_words = {
        "saya", "awak", "apa", "boleh", "tolong",
        "kenapa", "nak", "tak", "macam", "bagaimana",
        "siapa", "panggil", "telefon", "cari",
        "buat", "lokasi", "pergi", "buka",
        "terangkan", "ajarkan", "bagitahu",
        "belajar", "kod", "soalan", "projek"
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
    text = text.lower()

    moods = {
        "happy": [
            "tahniah",
            "bagus",
            "excellent",
            "congratulations",
            "gembira"
        ],
        "sad": [
            "sedih",
            "takziah",
            "sorry",
            "condolences"
        ],
        "surprised": [
            "wow",
            "wah",
            "amazing",
            "menakjubkan"
        ]
    }

    for mood, words in moods.items():
        if any(word in text for word in words):
            return mood

    return "neutral"


# ====================================================
# 3. VOICE SYNTHESIS
# ====================================================

async def synthesize(text, lang):
    voice = (
        "ms-MY-YasminNeural"
        if lang == "ms"
        else "en-US-JennyNeural"
    )

    speech = Communicate(
        text=text[:1800],
        voice=voice
    )

    output = bytearray()

    async for item in speech.stream():
        if item["type"] == "audio":
            output.extend(item["data"])

    return bytes(output)


# ====================================================
# 4. DOCUMENT READER
# ====================================================

def read_document(upload):
    data = upload.getvalue()

    if len(data) > 8 * 1024 * 1024:
        raise ValueError(
            "Fail melebihi 8 MB"
        )

    filename = upload.name.lower()

    if filename.endswith(".pdf"):
        reader = PdfReader(
            io.BytesIO(data)
        )

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages[:20]
        )

    elif filename.endswith(".docx"):
        document = Document(
            io.BytesIO(data)
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
        text = data.decode(
            "utf-8",
            errors="replace"
        )

    return text[:12000]


# ====================================================
# 5. SEARCH ENGINE
# ====================================================

def search_web(question):
    results = DDGS(
        timeout=12
    ).text(
        question,
        max_results=4
    ) or []

    output = []

    for item in results:
        url = str(
            item.get("href", "")
        )

        if urlparse(url).scheme not in (
            "http",
            "https"
        ):
            continue

        output.append({
            "title": str(
                item.get("title", "")
            )[:120],
            "url": url,
            "snippet": str(
                item.get("body", "")
            )[:450]
        })

    return output


# ====================================================
# 6. AI ACTIONS
# ====================================================

def action_for(text):
    command = text.strip()

    phone = re.search(
        r"(?:telefon|call|dial|panggil)"
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

    maps = re.search(
        r"(?:navigate to|directions to|"
        r"arah ke|pergi ke|lokasi|maps? ke)"
        r"\s+(.+)",
        command,
        re.I
    )

    if maps:
        location = maps.group(1).strip(
            " .?!"
        )[:120]

        if location:
            return {
                "type": "maps",
                "label": "📍 Buka Google Maps",
                "url": (
                    "https://www.google.com/maps/"
                    "search/?api=1&query="
                    + quote_plus(location)
                )
            }

    google = re.search(
        r"^(?:google|search web|"
        r"cari di google|cari web)"
        r"\s+(.+)",
        command,
        re.I
    )

    if google:
        phrase = google.group(1).strip()[:150]

        if phrase:
            return {
                "type": "search",
                "label": "🔎 Buka Google",
                "url": (
                    "https://www.google.com/search?q="
                    + quote_plus(phrase)
                )
            }

    return None


# ====================================================
# 7. GALAXY NEURAL BUBBLE COMMANDS
#
# 55 unique clickable bubbles.
#
# A click sends a structured event to Streamlit.
# Streamlit then sends its prompt to Groq.
#
# "search" bubbles request web search too.
# ====================================================

BUBBLE_COMMANDS = [
    # 1 - 10: General learning
    ("AI Chat", "Terangkan apa yang boleh E.D.I.T.H bantu saya.", "prompt"),
    ("Study", "Bantu saya belajar satu topik baharu secara berperingkat.", "prompt"),
    ("Quiz", "Berikan saya kuiz pengetahuan am dengan 5 soalan.", "prompt"),
    ("Math", "Ajar saya menyelesaikan masalah matematik dengan contoh.", "prompt"),
    ("Science", "Terangkan satu konsep sains yang menarik.", "prompt"),
    ("English", "Bantu saya berlatih bahasa Inggeris secara interaktif.", "prompt"),
    ("Translate", "Terjemahkan contoh ayat bahasa Melayu kepada bahasa Inggeris.", "prompt"),
    ("History", "Ceritakan satu peristiwa sejarah penting.", "prompt"),
    ("Physics", "Terangkan hukum Newton menggunakan contoh mudah.", "prompt"),
    ("Chemistry", "Ajar saya asas kimia dengan contoh.", "prompt"),

    # 11 - 20: Programming
    ("Python", "Ajar saya Python daripada asas dengan contoh coding.", "prompt"),
    ("Arduino", "Ajar saya projek Arduino untuk pemula.", "prompt"),
    ("ESP32", "Cadangkan satu projek ESP32 dengan coding.", "prompt"),
    ("Debug", "Terangkan kaedah debugging kod dengan contoh.", "prompt"),
    ("HTML", "Ajar saya HTML untuk membuat website.", "prompt"),
    ("CSS", "Ajar saya CSS untuk reka bentuk website moden.", "prompt"),
    ("JavaScript", "Ajar saya JavaScript dengan contoh interaktif.", "prompt"),
    ("C++", "Ajar saya asas C++ untuk projek elektronik.", "prompt"),
    ("IoT", "Cadangkan projek Internet of Things yang menarik.", "prompt"),
    ("Robotics", "Bimbing saya membina robot ringkas dengan Arduino.", "prompt"),

    # 21 - 30: Projects and engineering
    ("Sensors", "Terangkan jenis sensor Arduino dan kegunaannya.", "prompt"),
    ("Servo", "Ajar saya cara mengawal servo motor menggunakan Arduino.", "prompt"),
    ("Circuit", "Ajar saya membaca rajah litar elektronik.", "prompt"),
    ("Wiring", "Berikan contoh wiring Arduino dengan sensor.", "prompt"),
    ("FYP", "Cadangkan idea projek akhir bidang teknologi.", "prompt"),
    ("Innovation", "Berikan idea inovasi teknologi yang praktikal.", "prompt"),
    ("AI Project", "Cadangkan projek AI yang boleh saya bina.", "prompt"),
    ("App Design", "Bantu saya merancang reka bentuk aplikasi Android.", "prompt"),
    ("Cybersecurity", "Ajar saya asas keselamatan siber secara beretika.", "prompt"),
    ("Database", "Terangkan asas database SQL dengan contoh.", "prompt"),

    # 31 - 40: Productivity and creation
    ("Planner", "Buatkan jadual belajar produktif selama seminggu.", "prompt"),
    ("Ideas", "Berikan 10 idea kreatif untuk projek teknologi.", "prompt"),
    ("Writing", "Ajar saya menulis karangan yang lebih baik.", "prompt"),
    ("Presentation", "Berikan panduan membuat slide pembentangan.", "prompt"),
    ("Resume", "Terangkan cara menyediakan resume profesional.", "prompt"),
    ("Interview", "Latih saya menjawab soalan temuduga.", "prompt"),
    ("Business", "Cadangkan idea perniagaan teknologi kos rendah.", "prompt"),
    ("Finance", "Terangkan asas menyimpan wang dan bajet.", "prompt"),
    ("Motivation", "Berikan motivasi untuk belajar hari ini.", "prompt"),
    ("Mind Map", "Buatkan peta minda teks tentang teknologi AI.", "prompt"),

    # 41 - 50: Research
    ("AI News", "Cari perkembangan teknologi AI terkini dan ringkaskan bersama sumber.", "search"),
    ("Tech News", "Cari berita teknologi terkini dengan sumber.", "search"),
    ("Research", "Cari maklumat terkini tentang perkembangan robotik dengan sumber.", "search"),
    ("Arduino Web", "Cari tutorial Arduino untuk pemula dengan sumber.", "search"),
    ("ESP32 Web", "Cari idea projek ESP32 terkini dengan sumber.", "search"),
    ("Science Web", "Cari berita penemuan sains terkini dengan sumber.", "search"),
    ("Malaysia Tech", "Cari perkembangan industri teknologi Malaysia dengan sumber.", "search"),
    ("Open Source", "Cari projek AI open source yang sesuai untuk pemula.", "search"),
    ("Education", "Cari sumber pembelajaran Python percuma yang berkualiti.", "search"),
    ("AI Tools", "Cari aplikasi AI yang berguna untuk pelajar dengan sumber.", "search"),

    # 51 - 55: Advanced helpful functions
    ("Explain Code", "Terangkan contoh program Python baris demi baris.", "prompt"),
    ("Fix Arduino", "Berikan contoh error Arduino dan cara menyelesaikannya.", "prompt"),
    ("Prompt Maker", "Ajar saya cara menulis prompt AI yang berkesan.", "prompt"),
    ("Study Test", "Uji pengetahuan saya tentang elektronik melalui kuiz interaktif.", "prompt"),
    ("About EDITH", "Perkenalkan E.D.I.T.H dan fungsi yang tersedia dalam aplikasi ini.", "prompt"),
]

assert len(BUBBLE_COMMANDS) == 55


# ====================================================
# 8. CUSTOM STREAMLIT COMPONENT
#
# This frontend is automatically written to a temp
# directory. User does not need a separate HTML file.
# ====================================================

GALAXY_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">

<style>
* {
    box-sizing: border-box;
}

html, body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: transparent;
    color: #defaff;
    font-family: system-ui, Arial, sans-serif;
}

.shell {
    width: 100%;
    max-width: 480px;
    margin: auto;
    text-align: center;
    padding: 6px 4px 10px;
    background:
        radial-gradient(
            ellipse at center,
            rgba(29,82,179,.14),
            transparent 75%
        );
}

canvas {
    display: block;
    width: 100%;
    height: 318px;
    cursor: pointer;
    touch-action: manipulation;
}

.title {
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 5px;
    text-shadow: 0 0 12px #41dfff;
}

.status {
    font: 11px monospace;
    letter-spacing: 2px;
    color: #80dfff;
    margin: 7px 0 4px;
}

.selection {
    font-size: 12px;
    font-weight: 650;
    color: #ffe1a3;
    min-height: 18px;
}

.tip {
    font-size: 10px;
    color: #99afd1;
    margin: 6px 0;
}

audio {
    display: block;
    width: 92%;
    max-width: 355px;
    margin: 9px auto 0;
}

.legend {
    font-size: 10px;
    color: #abc5ed;
    line-height: 1.7;
}

@media(prefers-reduced-motion:reduce) {
    canvas {
        opacity: .85;
    }
}
</style>
</head>

<body>

<div class="shell">

    <canvas
        id="galaxy"
        aria-label="Interactive Galaxy Neural Bubble"
    ></canvas>

    <div class="title">
        E.D.I.T.H
    </div>

    <div id="status" class="status">
        STANDBY
    </div>

    <div id="selection" class="selection">
        Tap a bubble to activate AI
    </div>

    <div class="tip">
        55 Interactive AI Bubbles
    </div>

    <div class="legend">
        Cyan: AI Skills &nbsp; • &nbsp;
        Purple: Coding &nbsp; • &nbsp;
        Orange: Research
    </div>

    <audio
        id="speech"
        controls
        preload="metadata"
        style="display:none"
    ></audio>

</div>

<script>
"use strict";

// Streamlit Custom Component bridge

function send(type, data = {}) {
    window.parent.postMessage(
        Object.assign({
            isStreamlitMessage: true,
            type: type
        }, data),
        "*"
    );
}

function sendHeight() {
    send("streamlit:setFrameHeight", {
        height: document.body.scrollHeight + 6
    });
}

const canvas = document.getElementById("galaxy");
const ctx = canvas.getContext("2d");
const speech = document.getElementById("speech");
const statusText = document.getElementById("status");
const selectionText = document.getElementById("selection");

let commands = [];
let emotion = "neutral";
let busy = false;
let speaking = false;
let isHolo = false;
let audioSource = "";
let time = 0;
let width = 400;
let height = 318;

let analyser = null;
let audioContext = null;
let audioSourceNode = null;
let frequencyData = null;
let waveformData = null;

let energy = 0;
let bass = 0;
let middle = 0;
let treble = 0;

let selected = -1;
let hover = -1;
let points = [];

const nodes = [];

for (let i = 0; i < 55; i++) {
    nodes.push({
        a: i * 2.399963229728653,
        r: 23 + Math.sqrt((i + 1) / 55) * 116,
        size: 2.9 + (i % 5) * .50,
        phase: i * 1.63
    });
}

function resize() {
    const rect = canvas.getBoundingClientRect();
    width = rect.width || 380;

    const dpr = Math.min(
        window.devicePixelRatio || 1,
        2
    );

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    ctx.setTransform(
        dpr, 0, 0, dpr, 0, 0
    );
}

window.addEventListener("resize", resize);

function setupAudio() {
    if (!audioSource || analyser) return;

    try {
        const AudioContextClass =
            window.AudioContext ||
            window.webkitAudioContext;

        audioContext = new AudioContextClass();

        analyser = audioContext.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = .74;

        audioSourceNode =
            audioContext.createMediaElementSource(speech);

        audioSourceNode.connect(analyser);
        analyser.connect(audioContext.destination);

        frequencyData = new Uint8Array(
            analyser.frequencyBinCount
        );

        waveformData = new Uint8Array(
            analyser.fftSize
        );

    } catch (err) {
        console.warn("Audio analyser:", err);
        analyser = null;
    }
}

function resumeAudio() {
    setupAudio();

    if (
        audioContext &&
        audioContext.state === "suspended"
    ) {
        audioContext.resume();
    }
}

speech.addEventListener("play", () => {
    resumeAudio();
    speaking = true;
    updateStatus();
});

speech.addEventListener("playing", () => {
    resumeAudio();
    speaking = true;
    updateStatus();
});

speech.addEventListener("pause", () => {
    speaking = false;
    updateStatus();
});

speech.addEventListener("ended", () => {
    speaking = false;
    updateStatus();
});

speech.addEventListener("error", () => {
    speaking = false;
    updateStatus();
});

function updateStatus() {
    statusText.textContent = busy
        ? "THINKING"
        : speaking
            ? "SPEAKING"
            : "STANDBY";
}

function onRender(event) {
    if (!event.data) return;

    const args = event.data.args || {};

    commands = Array.isArray(args.commands)
        ? args.commands
        : [];

    emotion = args.emotion || "neutral";
    busy = !!args.busy;
    isHolo = args.mode === "holo";

    const newAudio = args.audio || "";

    if (newAudio !== audioSource) {
        audioSource = newAudio;

        speech.pause();

        if (audioSource) {
            speech.src =
                "data:audio/mpeg;base64," +
                audioSource;

            speech.style.display = "block";
        } else {
            speech.removeAttribute("src");
            speech.style.display = "none";
        }
    }

    selectionText.textContent = isHolo
        ? "Holographic Voice Core"
        : selected >= 0 && commands[selected]
            ? "Selected: " + commands[selected][0]
            : "Tap a bubble to activate AI";

    updateStatus();
    sendHeight();
}

window.addEventListener(
    "message",
    function(event) {
        if (
            event.data &&
            event.data.type === "streamlit:render"
        ) {
            onRender(event);
        }
    }
);

send("streamlit:componentReady", {
    apiVersion: 1
});

function averageRange(array, first, last) {
    let sum = 0;
    let count = 0;

    for (let i = first; i < last; i++) {
        sum += array[i] / 255;
        count++;
    }

    return count ? sum / count : 0;
}

function updateAudioLevels() {
    let nextEnergy = 0;
    let nextBass = 0;
    let nextMiddle = 0;
    let nextTreble = 0;

    if (speaking && analyser) {
        analyser.getByteFrequencyData(
            frequencyData
        );

        analyser.getByteTimeDomainData(
            waveformData
        );

        const n = frequencyData.length;

        nextBass = averageRange(
            frequencyData,
            1,
            Math.max(2, Math.floor(n * .08))
        );

        nextMiddle = averageRange(
            frequencyData,
            Math.floor(n * .08),
            Math.floor(n * .34)
        );

        nextTreble = averageRange(
            frequencyData,
            Math.floor(n * .34),
            Math.floor(n * .80)
        );

        let squareSum = 0;

        for (let i = 0; i < waveformData.length; i++) {
            const sample =
                (waveformData[i] - 128) / 128;

            squareSum += sample * sample;
        }

        const rms = Math.sqrt(
            squareSum / waveformData.length
        );

        nextEnergy = Math.min(1, rms * 4.2);
    }

    const smoothing = speaking ? .24 : .08;

    energy += (nextEnergy - energy) * smoothing;
    bass += (nextBass - bass) * smoothing;
    middle += (nextMiddle - middle) * smoothing;
    treble += (nextTreble - treble) * smoothing;
}

function palette(i) {
    if (emotion === "happy") {
        return i % 3 === 0
            ? "#ffc86a"
            : "#60f0ca";
    }

    if (emotion === "sad") {
        return i % 3 === 0
            ? "#6c8dff"
            : "#77c5ff";
    }

    if (emotion === "surprised") {
        return i % 3 === 0
            ? "#ffa36b"
            : "#f2a5ff";
    }

    if (i >= 40 && i < 50) {
        return "#ffc67a";
    }

    if (i >= 10 && i < 30) {
        return "#b99aff";
    }

    return "#58e5ff";
}

function positions() {
    const cx = width / 2;
    const cy = 150;

    const scale = Math.min(
        1,
        width / 390
    );

    return nodes.map((node, i) => {
        const shift =
            Math.sin(time * 1.5 + node.phase) *
            (2 + energy * 8);

        const radius =
            (node.r + shift + bass * 18) *
            scale;

        const a =
            node.a +
            time * (
                .09 + treble * .09
            );

        return {
            x: cx + Math.cos(a) * radius,
            y: cy + Math.sin(a) * radius * .78,
            i: i
        };
    });
}

function circle(x, y, r, color, glow) {
    ctx.beginPath();
    ctx.arc(x, y, Math.max(1, r), 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = glow;
    ctx.fill();
    ctx.shadowBlur = 0;
}

function drawBars(cx) {
    for (let i = 0; i < 21; i++) {
        const idx = frequencyData
            ? Math.min(
                frequencyData.length - 1,
                Math.floor(
                    i / 21 *
                    frequencyData.length * .48
                )
            )
            : 0;

        const val = (
            speaking && frequencyData
                ? frequencyData[idx] / 255
                : 0
        );

        const h =
            3 + val * 30 +
            (!speaking
                ? Math.abs(Math.sin(time + i)) * 1.5
                : 0);

        ctx.fillStyle =
            i % 4 === 0
                ? "#b59aff"
                : "#62eaff";

        ctx.fillRect(
            cx - 91 + i * 8.7,
            303 - h,
            4,
            h
        );
    }
}

function drawGalaxy() {
    const cx = width / 2;
    const cy = 150;

    points = positions();

    const outer = ctx.createRadialGradient(
        cx, cy, 10,
        cx, cy, 148 + energy * 35
    );

    outer.addColorStop(
        0,
        "rgba(65,158,255,.14)"
    );

    outer.addColorStop(
        .55,
        "rgba(139,92,246,.08)"
    );

    outer.addColorStop(
        1,
        "rgba(0,0,0,0)"
    );

    ctx.fillStyle = outer;
    ctx.fillRect(
        0, 0, width, height
    );

    // Neural connections
    for (let i = 0; i < points.length; i++) {
        for (let j = i + 1; j < points.length; j++) {
            const a = points[i];
            const b = points[j];

            const d = Math.hypot(
                a.x - b.x,
                a.y - b.y
            );

            const limit = 67;

            if (d < limit) {
                const opacity =
                    (1 - d / limit) *
                    (.22 + energy * .65);

                ctx.beginPath();

                ctx.strokeStyle =
                    "rgba(99,218,255," +
                    opacity.toFixed(3) +
                    ")";

                ctx.lineWidth =
                    .75 + bass * 1.6;

                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.stroke();
            }
        }
    }

    // Nodes
    points.forEach((p, i) => {
        let radius =
            nodes[i].size +
            energy * 6 +
            treble * 3;

        if (i === selected) {
            radius += 3;

            ctx.beginPath();
            ctx.arc(
                p.x,
                p.y,
                radius + 5,
                0,
                Math.PI * 2
            );

            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 1.3;
            ctx.stroke();
        }

        if (i === hover) {
            radius += 2.8;
        }

        circle(
            p.x,
            p.y,
            radius,
            palette(i),
            i === selected ? 23 : 12
        );
    });

    // Center orb
    const coreRadius =
        23 +
        energy * 20 +
        bass * 8 +
        Math.sin(time * 4) * 1.2;

    const gradient =
        ctx.createRadialGradient(
            cx - 7, cy - 8, 1,
            cx, cy, coreRadius
        );

    gradient.addColorStop(
        0,
        "#ffffff"
    );

    gradient.addColorStop(
        .34,
        "#85f4ff"
    );

    gradient.addColorStop(
        1,
        "#3148ba"
    );

    circle(
        cx,
        cy,
        coreRadius,
        gradient,
        24 + energy * 25
    );

    drawBars(cx);
}

function drawHologram() {
    const cx = width / 2;
    const cy = 150;

    for (let k = 0; k < 3; k++) {
        ctx.save();
        ctx.translate(cx, cy);

        ctx.rotate(
            time * (k % 2 ? -.5 : .7)
        );

        ctx.setLineDash(
            k === 1
                ? [4, 8]
                : [22, 13]
        );

        ctx.beginPath();

        ctx.strokeStyle = [
            "#63eaff",
            "#ad8aff",
            "#4c8bff"
        ][k];

        ctx.lineWidth = 1.5;

        ctx.arc(
            0, 0,
            64 + k * 22 + energy * 12,
            0,
            Math.PI * 2
        );

        ctx.stroke();
        ctx.restore();
    }

    const radius =
        51 + energy * 18;

    const gradient =
        ctx.createRadialGradient(
            cx - 15,
            cy - 17,
            1,
            cx,
            cy,
            radius
        );

    gradient.addColorStop(
        0,
        "#ecffff"
    );

    gradient.addColorStop(
        .25,
        "#67eaff"
    );

    gradient.addColorStop(
        .6,
        "#5863ea"
    );

    gradient.addColorStop(
        1,
        "#161444"
    );

    circle(
        cx,
        cy,
        radius,
        gradient,
        24 + energy * 24
    );

    drawBars(cx);
}

function draw() {
    requestAnimationFrame(draw);

    const moving = !document.hidden;

    if (!moving) return;

    time += speaking ? .032 : .010;

    updateAudioLevels();

    ctx.clearRect(
        0, 0, width, height
    );

    if (isHolo) {
        drawHologram();
    } else {
        drawGalaxy();
    }
}

function getPointer(evt) {
    const r = canvas.getBoundingClientRect();

    return {
        x: evt.clientX - r.left,
        y: evt.clientY - r.top
    };
}

function findBubble(evt) {
    const mouse = getPointer(evt);

    let best = -1;
    let distance = Infinity;

    for (let i = 0; i < points.length; i++) {
        const p = points[i];

        const d = Math.hypot(
            mouse.x - p.x,
            mouse.y - p.y
        );

        if (d < distance) {
            distance = d;
            best = i;
        }
    }

    // Enlarge touch target for phones
    return distance < 16 ? best : -1;
}

canvas.addEventListener(
    "pointermove",
    evt => {
        if (isHolo) return;

        hover = findBubble(evt);

        canvas.style.cursor =
            hover >= 0
                ? "pointer"
                : "default";

        if (
            hover >= 0 &&
            commands[hover]
        ) {
            canvas.title =
                commands[hover][0];
        } else {
            canvas.title = "";
        }
    }
);

canvas.addEventListener(
    "pointerleave",
    () => {
        hover = -1;
    }
);

canvas.addEventListener(
    "click",
    evt => {
        if (isHolo || busy) return;

        const index = findBubble(evt);

        if (
            index < 0 ||
            !commands[index]
        ) {
            return;
        }

        selected = index;

        const chosen = commands[index];

        selectionText.textContent =
            "Activating: " + chosen[0];

        // This sends the click to the Python backend.
        // Python can then execute the requested AI prompt.
        send(
            "streamlit:setComponentValue",
            {
                value: {
                    id:
                        String(Date.now()) +
                        "-" +
                        String(Math.random()),
                    index: index
                }
            }
        );
    }
);

resize();
draw();
sendHeight();
</script>
</body>
</html>
"""


@st.cache_resource
def create_visual_component():
    folder = Path(
        tempfile.gettempdir()
    ) / "edith_galaxy_v2_component"

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    index_file = folder / "index.html"

    # Rewrite if a newer HTML version is deployed.
    index_file.write_text(
        GALAXY_HTML,
        encoding="utf-8"
    )

    return declare_component(
        "edith_galaxy_v2",
        path=str(folder)
    )


galaxy_component = create_visual_component()


def display_visual(
    mode,
    audio=None,
    emotion="neutral",
    busy=False
):
    encoded = (
        base64.b64encode(audio).decode("ascii")
        if audio
        else ""
    )

    commands_for_js = [
        [item[0], item[2]]
        for item in BUBBLE_COMMANDS
    ]

    return galaxy_component(
        mode=mode,
        audio=encoded,
        emotion=emotion,
        busy=busy,
        commands=commands_for_js,
        default=None,
        key="edith_interactive_visual"
    )


# ====================================================
# 9. SIDEBAR
# ====================================================

with st.sidebar:
    st.header("⚙️ E.D.I.T.H Settings")

    mode = st.radio(
        "AI Mode",
        [
            "Mode 1 - Chat Only",
            "Mode 2 - Holographic Voice Core",
            "Mode 3 - Galaxy Neural V2"
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
        "Memory dan chat adalah untuk "
        "sesi semasa sahaja."
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


# ====================================================
# 10. QUANTUM ENERGY FLOW / CHATGPT STYLE
# ====================================================

if theme == "Light":
    bg = "#f7faff"
    ink = "#18243d"
    bubble_bg = "#dfeafe"
    bubble_ink = "#15213d"
    sidebar = "rgba(245,249,255,.96)"
    input_bg = "rgba(255,255,255,.95)"

elif theme == "Ocean Blue":
    bg = "#07172e"
    ink = "#e9f8ff"
    bubble_bg = "#164572"
    bubble_ink = "#ffffff"
    sidebar = "rgba(5,24,48,.96)"
    input_bg = "rgba(15,48,86,.96)"

else:
    bg = "#080f20"
    ink = "#ecf5ff"
    bubble_bg = "#354c73"
    bubble_ink = "#ffffff"
    sidebar = "rgba(9,16,33,.96)"
    input_bg = "rgba(22,34,60,.96)"


st.markdown(
    f"""
<style>

.stApp {{
    background:
        radial-gradient(
            ellipse at 20% 17%,
            rgba(50,140,240,.16),
            transparent 42%
        ),
        radial-gradient(
            ellipse at 85% 65%,
            rgba(146,65,230,.16),
            transparent 40%
        ),
        {bg};
    color: {ink};
}}

.stApp::before {{
    content:"";
    position:fixed;
    inset:-15%;
    pointer-events:none;

    background:
        radial-gradient(
            ellipse at 15% 50%,
            rgba(33,181,255,.15),
            transparent 35%
        ),
        radial-gradient(
            ellipse at 80% 35%,
            rgba(162,81,255,.14),
            transparent 35%
        );

    animation:
        edithQuantum 18s
        ease-in-out infinite alternate;
}}

@keyframes edithQuantum {{
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
    background:{sidebar};
}}

.stApp h1,
.stApp h2,
.stApp h3 {{
    color:{ink};
}}

[data-testid="stChatMessage"] {{
    background:transparent;
    border:0;
    border-radius:0;
    box-shadow:none;
    padding:14px 4px;
    margin-bottom:5px;
}}

[data-testid="stChatMessageContent"] {{
    line-height:1.7;
}}

[data-testid="stChatInput"] > div {{
    background:{input_bg};
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


# ====================================================
# 11. MAIN PAGE
# ====================================================

st.title("🤖 E.D.I.T.H")

st.caption(
    "Your Personal AI Assistant • Galaxy Neural V2"
)

voice_mode = (
    mode.startswith("Mode 2")
    or mode.startswith("Mode 3")
)

neural_mode = mode.startswith("Mode 3")


# ====================================================
# 12. DISPLAY VISUAL & PROCESS BUBBLE CLICKS
# ====================================================

if voice_mode:
    last_audio_message = next(
        (
            m
            for m in reversed(history())
            if (
                m["role"] == "assistant"
                and m.get("audio")
            )
        ),
        None
    )

    audio_data = (
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

    event = display_visual(
        mode=(
            "neural"
            if neural_mode
            else "holo"
        ),
        audio=audio_data,
        emotion=last_emotion,
        busy=st.session_state.pending
    )

    if (
        neural_mode
        and not st.session_state.pending
        and isinstance(event, dict)
    ):
        event_id = event.get("id")
        index = event.get("index")

        if (
            isinstance(event_id, str)
            and event_id
            and event_id != st.session_state.bubble_event_seen
            and type(index) is int
            and 0 <= index < len(BUBBLE_COMMANDS)
        ):
            st.session_state.bubble_event_seen = event_id

            label, prompt, kind = (
                BUBBLE_COMMANDS[index]
            )

            ask(
                prompt,
                force_search=(kind == "search")
            )

            st.rerun()

if neural_mode:
    st.caption(
        "✨ Tekan mana-mana bubble untuk "
        "mengaktifkan fungsi AI."
    )

    with st.expander(
        "🫧 Senarai 55 Bubble Functions"
    ):
        for start in range(
            0,
            len(BUBBLE_COMMANDS),
            11
        ):
            part = BUBBLE_COMMANDS[
                start:start + 11
            ]

            st.write(
                " • ".join(
                    f"{start + i + 1}. {item[0]}"
                    for i, item in enumerate(part)
                )
            )


# ====================================================
# 13. GROQ CONNECTION
# ====================================================

try:
    api_key = st.secrets[
        "GROQ_API_KEY"
    ]

    client = Groq(
        api_key=api_key
    )

except (
    KeyError,
    FileNotFoundError,
    ValueError
):
    st.error(
        "GROQ_API_KEY tidak dijumpai. "
        "Masukkan API key dalam "
        "Streamlit Cloud Secrets."
    )
    st.stop()


# ====================================================
# 14. FILE UPLOAD
# ====================================================

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

    image_file = st.file_uploader(
        "JPG / PNG",
        type=[
            "jpg",
            "jpeg",
            "png"
        ]
    )

doc_context = ""

if document is not None:
    try:
        doc_context = read_document(
            document
        )

        if doc_context.strip():
            st.success(
                "Dokumen berjaya dibaca."
            )
        else:
            st.warning(
                "Dokumen tidak mengandungi "
                "teks yang boleh dibaca."
            )

    except Exception as exc:
        st.warning(
            "Document error: "
            + type(exc).__name__
        )

image_bytes = None

if image_file is not None:
    data = image_file.getvalue()

    if len(data) <= 4 * 1024 * 1024:
        image_bytes = data

        st.image(
            image_bytes,
            width=250,
            caption="Uploaded image"
        )
    else:
        st.warning(
            "Gambar melebihi 4 MB."
        )


# ====================================================
# 15. MODE 3 VOICE COMMANDS
# ====================================================

if neural_mode:
    with st.expander(
        "🎙️ Voice Commands + AI Actions",
        expanded=False
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
                sound_bytes = recorded.getvalue()

                if not sound_bytes:
                    st.warning(
                        "Rakaman kosong."
                    )

                elif len(sound_bytes) > (
                    20 * 1024 * 1024
                ):
                    st.warning(
                        "Rakaman terlalu besar."
                    )

                else:
                    with st.spinner(
                        "Transcribing voice..."
                    ):
                        transcript = (
                            client.audio.transcriptions.create(
                                model=STT_MODEL,
                                file=(
                                    "voice.wav",
                                    sound_bytes
                                ),
                                response_format="json"
                            )
                        )

                    spoken = (
                        transcript.text or ""
                    ).strip()

                    if spoken:
                        ask(spoken)
                        st.rerun()
                    else:
                        st.warning(
                            "Tiada suara dikesan."
                        )

            except Exception as exc:
                st.error(
                    "Voice error: "
                    + type(exc).__name__
                )

        st.caption(
            "Contoh: Telefon 0123456789 | "
            "Lokasi KLCC | "
            "Cari di Google Arduino"
        )


# ====================================================
# 16. REGENERATE LAST
# ====================================================

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


# ====================================================
# 17. CHAT HISTORY
# ====================================================

for i, message in enumerate(history()):
    if (
        st.session_state.pending
        and i == len(history()) - 1
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
        background:{bubble_bg};
        color:{bubble_ink};
        padding:12px 17px;
        border-radius:19px 19px 5px 19px;
        max-width:88%;
        line-height:1.6;
        overflow-wrap:anywhere;
        text-align:left;
    ">
        {safe}
    </div>
</div>
""",
                unsafe_allow_html=True
            )

            if st.button(
                "✏️ Edit",
                key=f"edit_button_{i}",
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
                            source["title"]
                            or "Source",
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
                        + 'padding:10px 16px;'
                        + 'background:#217b9e;'
                        + 'color:white;'
                        + 'border-radius:12px;'
                        + 'text-decoration:none;">'
                        + safe_label
                        + '</a>',
                        unsafe_allow_html=True
                    )

                    st.caption(
                        "Aplikasi Phone akan dibuka "
                        "jika disokong. "
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
                    "🔊 Play response audio"
                ):
                    st.audio(
                        message["audio"],
                        format="audio/mp3"
                    )


# ====================================================
# 18. CHAT INPUT
# ====================================================

question = st.chat_input(
    "Message E.D.I.T.H...",
    disabled=st.session_state.pending
)

if question and question.strip():
    ask(question.strip())
    st.rerun()


# ====================================================
# 19. GROQ AI RESPONSE
# ====================================================

if st.session_state.pending:
    messages = history()
    reply_index = len(messages) - 1

    user_message = messages[
        reply_index - 1
    ]

    user_question = user_message[
        "content"
    ]

    force_search = user_message.get(
        "force_search",
        False
    )

    language_code = detect_language(
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
                    "Reply in the language "
                    "used by the user.",

                "Bahasa Melayu":
                    "Always reply in Bahasa Melayu.",

                "English":
                    "Always reply in English."
            }

            tool_rules = {
                "General Chat":
                    "Answer clearly and helpfully.",

                "Coding Assistant":
                    "Provide working coding examples "
                    "and explain debugging steps.",

                "Study & Quiz":
                    "Teach step by step "
                    "and generate useful quizzes.",

                "Translator":
                    "Translate accurately "
                    "between Malay and English."
            }

            system = (
                "Your name is E.D.I.T.H. "
                "You are a personal AI assistant. "
                "Never claim your name is another AI. "
                "Be accurate and helpful. "
                + language_rules[language]
                + " "
                + tool_rules[ai_tool]
            )

            system += (
                " Never pretend you have completed "
                "phone calls, opened apps, "
                "executed code or contacted people. "
                "Actions require user confirmation."
            )

            if st.session_state.memory.strip():
                system += (
                    "\nUser session notes "
                    "(reference only):\n"
                    + st.session_state.memory[:1500]
                )

            if doc_context.strip():
                system += (
                    "\nUploaded document text "
                    "(untrusted source material):\n"
                    + doc_context
                )

            # Internet search can be manually enabled
            # or triggered by a Search Bubble.
            if internet or force_search:
                try:
                    sources = search_web(
                        user_question
                    )

                    if sources:
                        system += (
                            "\nWeb search results "
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
                            "Cite result numbers "
                            "when appropriate. "
                            "Do not invent sources."
                        )

                    else:
                        st.warning(
                            "Tiada hasil internet."
                        )

                except Exception as exc:
                    st.warning(
                        "Internet Search tidak tersedia: "
                        + type(exc).__name__
                    )

            # Build recent messages.
            recent = [
                {
                    "role": m["role"],
                    "content": m["content"]
                }

                for m in messages[:-1]
            ][-10:]

            model = CHAT_MODEL

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

                    messages[reply_index][
                        "content"
                    ] = answer

                    output.markdown(
                        answer + "▌"
                    )

            output.markdown(
                answer
                or "_(Tiada jawapan)_"
            )

            messages[reply_index][
                "content"
            ] = answer

            messages[reply_index][
                "sources"
            ] = sources

            messages[reply_index][
                "action"
            ] = action

            emotion = emotion_for(
                answer
            )

            messages[reply_index][
                "emotion"
            ] = emotion

            # Voice only in Modes 2 and 3
            if voice_mode and answer.strip():
                try:
                    with st.spinner(
                        "Generating voice..."
                    ):
                        sound = asyncio.run(
                            synthesize(
                                answer,
                                language_code
                            )
                        )

                    if sound:
                        messages[reply_index][
                            "audio"
                        ] = sound

                except Exception as exc:
                    st.warning(
                        "Voice tidak tersedia: "
                        + type(exc).__name__
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

        except Exception as exc:
            st.error(
                "E.D.I.T.H gagal menjawab. "
                "Semak sambungan Groq, "
                "model dan kuota API."
            )

            st.caption(
                "Error type: "
                + type(exc).__name__
            )

            messages[reply_index][
                "failed"
            ] = True

            if not answer:
                messages[reply_index][
                    "content"
                ] = (
                    "Ralat AI. "
                    "Cuba Regenerate Last."
                )

        finally:
            st.session_state.pending = False

    # Re-enable input after generating.
    st.rerun()
