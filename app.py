
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


# ==================================================
# E.D.I.T.H - CRYSTAL ACRYLIC EDITION
#
# MODE 1: CHAT ONLY
# MODE 2: HOLOGRAPHIC VOICE CORE
# MODE 3: RADIAL AI COMMAND HUB
#
# 8 APP BUBBLES + 47 AI SKILLS = 55 FUNCTIONS
#
# CRYSTAL ACRYLIC CHAT + QUANTUM ENERGY FLOW
# REAL WEB AUDIO REACTIVE ANIMATION
# GROQ / VOICE / MEMORY / HISTORY / UPLOAD
# INTERNET SEARCH / AI ACTIONS
#
# NO STOP GENERATING BUTTON
# ==================================================

st.set_page_config(
    page_title="E.D.I.T.H",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

CHAT_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = (
    "meta-llama/llama-4-scout-17b-16e-instruct"
)
STT_MODEL = "whisper-large-v3-turbo"


# ==================================================
# 1. SESSION STATE
# ==================================================

if "rooms" not in st.session_state:
    st.session_state.rooms = {"Chat 1": []}

defaults = {
    "room": "Chat 1",
    "memory": "",
    "pending": False,
    "editing": None,
    "last_hub_event": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def history():
    return st.session_state.rooms[st.session_state.room]


def assistant_message():
    return {
        "role": "assistant",
        "content": "",
        "sources": [],
        "action": None,
        "audio": None,
        "emotion": "neutral",
    }


def ask(question, force_search=False):
    history().append({
        "role": "user",
        "content": question,
        "force_search": force_search,
    })
    history().append(assistant_message())
    st.session_state.pending = True


def new_chat():
    n = 1
    while f"Chat {n}" in st.session_state.rooms:
        n += 1

    name = f"Chat {n}"
    st.session_state.rooms[name] = []
    st.session_state.room = name
    st.session_state.editing = None


def regenerate():
    data = history()

    if data and data[-1]["role"] == "assistant":
        data.pop()

    if data and data[-1]["role"] == "user":
        data.append(assistant_message())
        st.session_state.pending = True


# ==================================================
# 2. LANGUAGE / EMOTION
# ==================================================

def detect_language(text, setting):
    if setting == "Bahasa Melayu":
        return "ms"

    if setting == "English":
        return "en"

    malay = {
        "saya", "awak", "apa", "boleh", "tolong",
        "kenapa", "nak", "tak", "macam", "mana",
        "bagaimana", "buat", "cari", "lokasi",
        "telefon", "ajar", "belajar", "projek",
        "terangkan", "berikan", "bantu", "dengan"
    }

    words = set(re.findall(r"\w+", text.lower()))

    return "ms" if words & malay else "en"


def emotion_for(text):
    value = text.lower()

    if any(x in value for x in [
        "tahniah", "bagus", "excellent",
        "congratulations"
    ]):
        return "happy"

    if any(x in value for x in [
        "sedih", "takziah", "sorry", "dukacita"
    ]):
        return "sad"

    if any(x in value for x in [
        "wow", "wah", "amazing", "menakjubkan"
    ]):
        return "surprised"

    return "neutral"


# ==================================================
# 3. TEXT TO SPEECH
# ==================================================

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

    data = bytearray()

    async for packet in speech.stream():
        if packet["type"] == "audio":
            data.extend(packet["data"])

    return bytes(data)


# ==================================================
# 4. READ DOCUMENTS
# ==================================================

def read_document(upload):
    raw = upload.getvalue()

    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Document exceeds 8 MB")

    name = upload.name.lower()

    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(
            p.extract_text() or ""
            for p in reader.pages[:20]
        )

    elif name.endswith(".docx"):
        doc = Document(io.BytesIO(raw))
        parts = [p.text for p in doc.paragraphs]

        for table in doc.tables:
            for row in table.rows:
                parts.append(
                    " | ".join(c.text for c in row.cells)
                )

        text = "\n".join(parts)

    else:
        text = raw.decode("utf-8", errors="replace")

    return text[:12000]


# ==================================================
# 5. WEB SEARCH
# ==================================================

def search_web(query):
    results = DDGS(timeout=12).text(
        query,
        max_results=4
    ) or []

    output = []

    for item in results:
        url = str(item.get("href", ""))

        if urlparse(url).scheme not in (
            "https", "http"
        ):
            continue

        output.append({
            "title": str(item.get("title", ""))[:100],
            "url": url,
            "snippet": str(item.get("body", ""))[:400],
        })

    return output


# ==================================================
# 6. AI ACTIONS
# ==================================================

def action_for(command):
    command = command.strip()

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

        if re.fullmatch(r"\+?\d{7,15}", number):
            return {
                "type": "dial",
                "label": "📞 Phone: " + number,
                "url": "tel:" + number
            }

    maps = re.search(
        r"(?:lokasi|maps? ke|pergi ke|"
        r"arah ke|navigate to|directions to)"
        r"\s+(.+)",
        command,
        re.I
    )

    if maps:
        place = maps.group(1).strip(" .?!")[:120]

        return {
            "type": "maps",
            "label": "📍 Buka Google Maps",
            "url": (
                "https://www.google.com/maps/"
                "search/?api=1&query=" +
                quote_plus(place)
            )
        }

    google = re.search(
        r"^(?:google|cari di google|"
        r"cari web|search web)\s+(.+)",
        command,
        re.I
    )

    if google:
        query = google.group(1).strip()[:150]

        return {
            "type": "search",
            "label": "🔎 Buka Google Search",
            "url": (
                "https://www.google.com/search?q="
                + quote_plus(query)
            )
        }

    return None


# ==================================================
# 7. EIGHT APP BUBBLES
# ==================================================

APP_BUBBLES = [
    {
        "name": "Facebook",
        "symbol": "f",
        "color": "#75A7FF",
        "url": "https://www.facebook.com"
    },
    {
        "name": "Google",
        "symbol": "G",
        "color": "#77D9FF",
        "url": "https://www.google.com"
    },
    {
        "name": "ChatGPT",
        "symbol": "✳",
        "color": "#6CF0BB",
        "url": "https://chatgpt.com"
    },
    {
        "name": "Arduino IDE",
        "symbol": "∞",
        "color": "#77EFFF",
        "url": "https://www.arduino.cc/en/software"
    },
    {
        "name": "WhatsApp",
        "symbol": "✆",
        "color": "#69ED9A",
        "url": "https://web.whatsapp.com"
    },
    {
        "name": "TikTok",
        "symbol": "♪",
        "color": "#FFACCC",
        "url": "https://www.tiktok.com"
    },
    {
        "name": "YouTube",
        "symbol": "▶",
        "color": "#FF8585",
        "url": "https://www.youtube.com"
    },
    {
        "name": "Instagram",
        "symbol": "◎",
        "color": "#E9A0FF",
        "url": "https://www.instagram.com"
    },
]


# ==================================================
# 8. FORTY-SEVEN AI FUNCTIONS
# ==================================================

AI_SKILLS = [
    ("AI Chat", "Perkenalkan E.D.I.T.H dan mulakan perbualan.", False),
    ("Study", "Ajar saya satu topik baharu langkah demi langkah.", False),
    ("Quiz", "Berikan kuiz pengetahuan am 5 soalan.", False),
    ("Math", "Ajar saya matematik dengan contoh.", False),
    ("Science", "Terangkan satu konsep sains.", False),
    ("English", "Bantu saya berlatih bahasa Inggeris.", False),
    ("Translator", "Ajar saya menterjemah bahasa Melayu dan English.", False),
    ("History", "Ceritakan satu peristiwa sejarah.", False),
    ("Physics", "Terangkan asas fizik.", False),
    ("Chemistry", "Ajar saya asas kimia.", False),
    ("Python", "Ajar saya coding Python dengan contoh.", False),
    ("Arduino", "Cadangkan projek Arduino bersama coding dan wiring.", False),
    ("ESP32", "Ajar saya projek ESP32 dengan coding.", False),
    ("Debug", "Ajar saya mencari dan membetulkan error coding.", False),
    ("HTML", "Ajar saya membuat website menggunakan HTML.", False),
    ("CSS", "Ajar saya CSS dan web design.", False),
    ("JavaScript", "Ajar saya JavaScript dengan contoh.", False),
    ("C++", "Ajar saya asas C++.", False),
    ("IoT", "Cadangkan projek Internet of Things.", False),
    ("Robotics", "Bantu saya membina projek robotik.", False),
    ("Sensors", "Terangkan jenis sensor elektronik.", False),
    ("Servo", "Ajar saya mengawal servo dengan Arduino.", False),
    ("Circuit", "Ajar saya asas litar elektronik.", False),
    ("Wiring", "Tunjukkan contoh wiring Arduino.", False),
    ("FYP", "Cadangkan tajuk Final Year Project teknologi.", False),
    ("AI Project", "Cadangkan projek artificial intelligence.", False),
    ("Planner", "Bina jadual belajar seminggu.", False),
    ("Writing", "Ajar saya teknik penulisan yang baik.", False),
    ("Business", "Cadangkan idea perniagaan teknologi.", False),
    ("Prompt", "Ajar saya menulis prompt AI.", False),
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


# ==================================================
# 9. RADIAL HUB HTML / JAVASCRIPT
#
# Self-contained custom component.
# No separate HTML file needed in GitHub.
# ==================================================

VISUAL_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport"
content="width=device-width,initial-scale=1">

<style>
* { box-sizing:border-box; }

html, body {
    margin:0;
    padding:0;
    background:transparent;
    font-family:system-ui,Arial,sans-serif;
    color:#eaffff;
    overflow-x:hidden;
}

.shell {
    padding:8px 4px 14px;
    text-align:center;
    background:
        radial-gradient(
            ellipse at 50% 43%,
            rgba(33,103,210,.16),
            transparent 70%
        );
}

.brand {
    font-size:18px;
    font-weight:800;
    letter-spacing:5px;
    text-shadow:0 0 14px #60eaff;
}

.subtitle {
    font:10px monospace;
    letter-spacing:2px;
    color:#a6cce9;
    margin:6px 0;
}

canvas {
    display:block;
    width:100%;
    cursor:pointer;
    touch-action:manipulation;
}

#status {
    font:11px monospace;
    letter-spacing:2px;
    margin:9px 0;
    color:#92edff;
}

.legend {
    color:#b9d6ec;
    font-size:11px;
    margin:8px 0;
}

.panel {
    display:none;
    padding:14px;
    margin:10px 8px;
    text-align:left;
    border-radius:19px;
    border:1px solid rgba(154,218,255,.35);

    background:
        linear-gradient(
            125deg,
            rgba(80,115,185,.30),
            rgba(57,41,115,.31)
        );

    backdrop-filter:blur(24px) saturate(170%);
    -webkit-backdrop-filter:blur(24px) saturate(170%);

    box-shadow:0 12px 35px rgba(0,0,0,.22);
}

.panel h3 {
    font-size:15px;
    margin:0 0 8px;
    color:#ffffff;
}

.panel p {
    font-size:12px;
    color:#d4eaff;
    line-height:1.6;
}

.link,
.close {
    display:inline-block;
    padding:10px 14px;
    border-radius:12px;
    border:1px solid #9deaff66;
    font-size:12px;
    color:#ffffff;
    text-decoration:none;
    cursor:pointer;
    margin:4px;
    background:linear-gradient(
        130deg,#1684d4,#7955dc
    );
}

.close {
    background:rgba(50,65,105,.7);
}

.skills {
    display:grid;
    grid-template-columns:repeat(3,minmax(0,1fr));
    gap:7px;
    max-height:270px;
    overflow-y:auto;
}

.skill {
    background:rgba(114,88,173,.35);
    color:#ffffff;
    border:1px solid #c7a7ff66;
    border-radius:11px;
    padding:11px 5px;
    cursor:pointer;
    font-size:11px;
}

.skill:active {
    background:#6c51b8;
}

audio {
    display:none;
    width:92%;
    max-width:360px;
    margin:12px auto 0;
}

</style>
</head>

<body>
<div class="shell">

    <div class="brand">E.D.I.T.H</div>

    <div class="subtitle" id="subtitle">
        MODE 3 • AI COMMAND HUB
    </div>

    <canvas id="scene"></canvas>

    <div id="status">STANDBY</div>

    <div class="legend" id="legend">
        🟡 App / Website • 🩷 AI Chat
    </div>

    <section class="panel" id="appPanel">
        <h3 id="appTitle">Open App</h3>
        <p>
            Tekan pautan untuk membuka aplikasi
            atau website yang dipilih.
        </p>

        <a
            id="appLink"
            class="link"
            target="_blank"
            rel="noopener noreferrer">
            Buka Aplikasi
        </a>

        <button id="closeApp" class="close">
            Tutup
        </button>
    </section>

    <section class="panel" id="skillPanel">
        <h3 id="skillTitle">AI Skills</h3>
        <p>
            Pilih fungsi AI untuk dihantar
            kepada E.D.I.T.H.
        </p>

        <div id="skillGrid" class="skills"></div>

        <button id="closeSkill" class="close">
            Tutup
        </button>
    </section>

    <audio id="audio" controls
        preload="metadata"></audio>

</div>

<script>
"use strict";

// ==============================================
// STREAMLIT V1 COMPONENT BRIDGE
// ==============================================

function post(type, fields={}) {
    window.parent.postMessage({
        isStreamlitMessage:true,
        type:type,
        ...fields
    },"*");
}

function frameHeight() {
    post("streamlit:setFrameHeight",{
        height:document.body.scrollHeight + 10
    });
}

post("streamlit:componentReady",{
    apiVersion:1
});

// ==============================================
// DOM AND STATE
// ==============================================

const scene=document.getElementById("scene");
const ctx=scene.getContext("2d");
const player=document.getElementById("audio");
const status=document.getElementById("status");

const appPanel=document.getElementById("appPanel");
const appTitle=document.getElementById("appTitle");
const appLink=document.getElementById("appLink");

const skillPanel=document.getElementById("skillPanel");
const skillTitle=document.getElementById("skillTitle");
const skillGrid=document.getElementById("skillGrid");

let apps=[];
let skills=[];
let mode="neural";
let emotion="neutral";
let busy=false;
let playing=false;

let audioValue="";
let audioContext=null;
let analyser=null;
let sourceNode=null;
let frequency=null;
let waveform=null;

let energy=0;
let bass=0;
let middle=0;
let treble=0;

let width=390;
let height=430;
let cx=195;
let cy=215;
let t=0;
let selected=null;
let targets=[];


// ==============================================
// WEB AUDIO API - REAL AUDIO REACTIVE
// ==============================================

function setupAnalyser() {
    if(analyser) return;

    try {
        const AC=window.AudioContext ||
                 window.webkitAudioContext;

        if(!AC) return;

        audioContext=new AC();

        analyser=audioContext.createAnalyser();
        analyser.fftSize=1024;
        analyser.smoothingTimeConstant=.75;

        sourceNode=audioContext
            .createMediaElementSource(player);

        sourceNode.connect(analyser);
        analyser.connect(audioContext.destination);

        frequency=new Uint8Array(
            analyser.frequencyBinCount
        );
        waveform=new Uint8Array(
            analyser.fftSize
        );

    }catch(e){
        console.warn("Audio analyser unavailable",e);
    }
}

function updateStatus(){
    status.textContent=busy
        ? "THINKING"
        : playing
            ? "SPEAKING"
            : "STANDBY";
}

player.addEventListener("play",()=>{
    setupAnalyser();

    if(audioContext &&
       audioContext.state==="suspended"){
        audioContext.resume();
    }

    playing=true;
    updateStatus();
});

player.addEventListener("pause",()=>{
    playing=false;
    updateStatus();
});

player.addEventListener("ended",()=>{
    playing=false;
    updateStatus();
});

function average(array,start,end){
    if(!array) return 0;

    let sum=0, count=0;

    for(let i=start;i<end;i++){
        sum+=array[i]/255;
        count++;
    }
    return count ? sum/count : 0;
}

function analyse(){
    let e=0,b=0,m=0,hi=0;

    if(playing && analyser){
        analyser.getByteFrequencyData(frequency);
        analyser.getByteTimeDomainData(waveform);

        const n=frequency.length;

        b=average(frequency,1,Math.floor(n*.10));
        m=average(
            frequency,
            Math.floor(n*.10),
            Math.floor(n*.35)
        );
        hi=average(
            frequency,
            Math.floor(n*.35),
            Math.floor(n*.85)
        );

        let sum=0;
        for(let i=0;i<waveform.length;i++){
            const value=(waveform[i]-128)/128;
            sum+=value*value;
        }

        e=Math.min(
            1,
            Math.sqrt(sum/waveform.length)*4.5
        );
    }

    const factor=playing ? .24 : .08;
    energy+=(e-energy)*factor;
    bass+=(b-bass)*factor;
    middle+=(m-middle)*factor;
    treble+=(hi-treble)*factor;
}


// ==============================================
// SIZE AND COORDINATES
// ==============================================

function resize(){
    width=scene.getBoundingClientRect().width || 390;

    height=mode==="holo"
        ? 290
        : Math.max(390,Math.min(560,width*1.1));

    scene.style.height=height+"px";

    const dpr=Math.min(
        window.devicePixelRatio||1,2
    );

    scene.width=width*dpr;
    scene.height=height*dpr;

    ctx.setTransform(dpr,0,0,dpr,0,0);

    cx=width/2;
    cy=height/2;

    frameHeight();
}

window.addEventListener("resize",resize);

// ==============================================
// DRAWING HELPERS
// ==============================================

function circle(x,y,r,fill,stroke,glow=0){
    ctx.beginPath();
    ctx.arc(x,y,Math.max(1,r),0,Math.PI*2);

    if(fill){
        ctx.fillStyle=fill;
        ctx.fill();
    }

    if(stroke){
        ctx.strokeStyle=stroke;
        ctx.lineWidth=2;
        ctx.shadowColor=stroke;
        ctx.shadowBlur=glow;
        ctx.stroke();
        ctx.shadowBlur=0;
    }
}

function label(text,x,y,size,color="#ffffff"){
    ctx.textAlign="center";
    ctx.textBaseline="middle";
    ctx.fillStyle=color;
    ctx.font="bold "+size+"px Arial";
    ctx.fillText(text,x,y);
}

function spoke(x1,y1,x2,y2,color,thickness){
    ctx.beginPath();
    ctx.moveTo(x1,y1);
    ctx.lineTo(x2,y2);
    ctx.strokeStyle=color;
    ctx.lineWidth=thickness;
    ctx.stroke();
}


// ==============================================
// NODE POSITIONS
// ==============================================

function appPoint(i){
    const a=-Math.PI/2 + i*Math.PI/4;

    const radius=Math.min(
        width*.355,
        height*.35
    );

    return {
        x:cx+Math.cos(a)*radius,
        y:cy+Math.sin(a)*radius
    };
}

function pinkPoint(i){
    const a=-Math.PI/2-.22 + i*Math.PI/6;

    const radius=Math.min(
        width*.46,
        height*.46
    );

    return {
        x:cx+Math.cos(a)*radius,
        y:cy+Math.sin(a)*radius
    };
}

function emotionColor(){
    if(emotion==="happy") return "#7cffc9";
    if(emotion==="sad") return "#719bff";
    if(emotion==="surprised") return "#ef9fff";
    return "#65eaff";
}


// ==============================================
// REACTIVE CENTRAL CORE
// ==============================================

function drawCore(){
    const radius=Math.max(
        33,Math.min(width*.14,75)
    );

    for(let i=0;i<3;i++){
        ctx.save();
        ctx.translate(cx,cy);
        ctx.rotate(t*(i%2 ? -.4 : .5));

        ctx.beginPath();
        ctx.setLineDash(i===1 ? [5,8] : [20,12]);
        ctx.arc(
            0,0,
            radius+5+i*6+energy*9,
            0,Math.PI*2
        );
        ctx.strokeStyle=[
            "#67eaff","#a487ff","#69a9ff"
        ][i];
        ctx.lineWidth=1.6;
        ctx.stroke();
        ctx.restore();
    }

    const gradient=ctx.createRadialGradient(
        cx-radius*.25,cy-radius*.28,2,
        cx,cy,radius
    );

    gradient.addColorStop(0,"#65eaff");
    gradient.addColorStop(.5,"#19538f");
    gradient.addColorStop(1,"#071326");

    circle(
        cx,cy,radius+energy*9,
        gradient,
        emotionColor(),
        24+energy*27
    );

    label(
        "E.D.I.T.H",
        cx,cy,
        Math.max(10,radius*.29)
    );
}


// ==============================================
// APP BUBBLES
// ==============================================

function drawApp(i){
    const app=apps[i];
    if(!app) return;

    const p=appPoint(i);
    const active=selected &&
        selected.type==="app" &&
        selected.index===i;

    const base=Math.max(
        16,Math.min(width*.075,43)
    );

    const r=base*(
        1+energy*.13+bass*.11+
        (active ? .22 : 0)
    );

    const gradient=ctx.createRadialGradient(
        p.x-r*.2,p.y-r*.25,2,
        p.x,p.y,r
    );
    gradient.addColorStop(
        0,"rgba(36,53,88,.96)"
    );
    gradient.addColorStop(
        1,"rgba(7,15,32,.98)"
    );

    circle(
        p.x,p.y,r,
        gradient,"#ffc36a",
        active ? 28 : 13
    );

    label(
        app.symbol,
        p.x,
        p.y-r*.22,
        Math.max(12,r*.63),
        app.color
    );

    label(
        app.name,
        p.x,
        p.y+r*.43,
        Math.max(6,r*.265)
    );

    targets.push({
        type:"app",index:i,
        x:p.x,y:p.y,r:r+8
    });
}


// ==============================================
// PINK AI BUBBLES
// ==============================================

function drawPink(i){
    const p=pinkPoint(i);
    const active=selected &&
        selected.type==="skill" &&
        selected.index===i;

    const r=Math.max(
        8,Math.min(width*.026,15)
    )*(active ? 1.4 : 1)*(1+energy*.18);

    circle(
        p.x,p.y,r,
        "rgba(110,34,92,.52)",
        "#ff87c4",
        active ? 25 : 13
    );

    if(active){
        label(
            "AI",p.x,p.y,
            Math.max(7,r*.6)
        );
    }

    targets.push({
        type:"skill",index:i,
        x:p.x,y:p.y,
        r:Math.max(15,r+8)
    });
}


// ==============================================
// NEURAL NETWORK
// ==============================================

function drawNetwork(){
    for(let i=0;i<8;i++){
        const p=appPoint(i);

        spoke(
            cx,cy,p.x,p.y,
            "rgba(103,204,255,"+
            (.45+energy*.48)+")",
            1.5+bass*2
        );
    }

    for(let i=0;i<12;i++){
        const p=pinkPoint(i);

        spoke(
            cx,cy,p.x,p.y,
            "rgba(255,184,100,"+
            (.30+energy*.48)+")",
            1.2+bass*2
        );
    }
}


// ==============================================
// AUDIO LEVEL BARS
// ==============================================

function drawBars(){
    for(let i=0;i<17;i++){
        let amount=0;

        if(playing && frequency){
            amount=frequency[
                Math.min(
                    frequency.length-1,
                    i*5
                )
            ]/255;
        }

        const h=3+amount*26;

        ctx.fillStyle=i%4===0
            ? "#b79aff"
            : "#65eaff";

        ctx.fillRect(
            cx-71+i*8.7,
            height-7-h,3,h
        );
    }
}


// ==============================================
// MODE 2 HOLOGRAM
// ==============================================

function drawHolo(){
    for(let i=0;i<3;i++){
        ctx.save();
        ctx.translate(cx,cy);
        ctx.rotate(t*(i%2 ? -.6 : .7));

        ctx.beginPath();
        ctx.setLineDash(i===1 ? [4,8] : [22,12]);
        ctx.arc(
            0,0,
            65+i*22+energy*10,
            0,Math.PI*2
        );

        ctx.strokeStyle=[
            "#67eaff","#b18aff","#4b8cff"
        ][i];

        ctx.lineWidth=1.6;
        ctx.stroke();
        ctx.restore();
    }

    const r=52+energy*20;

    const gradient=ctx.createRadialGradient(
        cx-16,cy-18,1,cx,cy,r
    );

    gradient.addColorStop(0,"#ffffff");
    gradient.addColorStop(.25,"#6ceaff");
    gradient.addColorStop(.65,"#5665e9");
    gradient.addColorStop(1,"#171447");

    circle(
        cx,cy,r,gradient,
        emotionColor(),
        28+energy*24
    );

    drawBars();
}


// ==============================================
// ANIMATION LOOP
// ==============================================

function frame(){
    requestAnimationFrame(frame);

    if(document.hidden) return;

    t+=playing ? .032 : .009;
    analyse();

    ctx.clearRect(
        0,0,width,height
    );

    targets=[];

    if(mode==="holo"){
        drawHolo();
        return;
    }

    const aura=ctx.createRadialGradient(
        cx,cy,5,
        cx,cy,height*.45
    );

    aura.addColorStop(
        0,"rgba(42,116,238,.18)"
    );
    aura.addColorStop(
        1,"rgba(0,0,0,0)"
    );

    ctx.fillStyle=aura;
    ctx.fillRect(0,0,width,height);

    drawNetwork();

    for(let i=0;i<8;i++) drawApp(i);
    for(let i=0;i<12;i++) drawPink(i);

    drawCore();
    drawBars();
}


// ==============================================
// INTERACTIVE BUBBLES
// ==============================================

function nodeAt(event){
    const rect=scene.getBoundingClientRect();

    const x=event.clientX-rect.left;
    const y=event.clientY-rect.top;

    let nearest=null;
    let distance=Infinity;

    for(const node of targets){
        const d=Math.hypot(
            node.x-x,node.y-y
        );

        if(d<=node.r && d<distance){
            nearest=node;
            distance=d;
        }
    }

    return nearest;
}

function hidePanels(){
    appPanel.style.display="none";
    skillPanel.style.display="none";
    frameHeight();
}

function openApp(i){
    const app=apps[i];
    if(!app) return;

    hidePanels();

    appTitle.textContent=app.name;
    appLink.textContent="Buka "+app.name+" ↗";
    appLink.href=app.url;

    appPanel.style.display="block";
    frameHeight();
}

function sendSkill(index){
    post("streamlit:setComponentValue",{
        value:{
            id:
                String(Date.now())+"-"+String(
                    Math.random()
                ),
            skill_index:index
        }
    });
}

function openSkills(group){
    hidePanels();
    skillGrid.replaceChildren();

    skillTitle.textContent=
        "AI Chat • Node "+(group+1);

    skills.forEach((skill,index)=>{
        if(index%12!==group) return;

        const btn=document.createElement("button");
        btn.type="button";
        btn.className="skill";
        btn.textContent=skill.name;

        btn.addEventListener("click",()=>{
            sendSkill(index);
            hidePanels();
        });

        skillGrid.appendChild(btn);
    });

    skillPanel.style.display="block";
    frameHeight();
}

scene.addEventListener("click",event=>{
    if(mode==="holo" || busy) return;

    const node=nodeAt(event);
    if(!node) return;

    selected={
        type:node.type,
        index:node.index
    };

    if(node.type==="app"){
        openApp(node.index);
    }else{
        openSkills(node.index);
    }
});

scene.addEventListener("pointermove",event=>{
    scene.style.cursor=nodeAt(event)
        ? "pointer" : "default";
});

document.getElementById("closeApp")
    .addEventListener("click",hidePanels);

document.getElementById("closeSkill")
    .addEventListener("click",hidePanels);


// ==============================================
// STREAMLIT -> COMPONENT RENDER
// ==============================================

window.addEventListener("message",event=>{
    if(
        !event.data ||
        event.data.type!=="streamlit:render"
    ) return;

    const args=event.data.args || {};

    apps=Array.isArray(args.apps)
        ? args.apps : [];

    skills=Array.isArray(args.skills)
        ? args.skills : [];

    const previousMode=mode;
    mode=args.mode || "neural";

    emotion=args.emotion || "neutral";
    busy=!!args.busy;

    const nextAudio=args.audio || "";

    if(nextAudio!==audioValue){
        audioValue=nextAudio;
        player.pause();

        if(audioValue){
            player.src=
                "data:audio/mpeg;base64,"+audioValue;

            player.style.display="block";
        }else{
            player.removeAttribute("src");
            player.style.display="none";
        }
    }

    document.getElementById("subtitle")
        .textContent=mode==="holo"
            ? "MODE 2 • HOLOGRAPHIC VOICE CORE"
            : "MODE 3 • AI COMMAND HUB";

    document.getElementById("legend")
        .style.display=mode==="holo"
            ? "none" : "block";

    if(mode!==previousMode){
        selected=null;
        hidePanels();
    }

    updateStatus();
    resize();
});

resize();
frame();
frameHeight();

</script>
</body>
</html>
"""


# ==================================================
# 10. CREATE STREAMLIT COMPONENT
# ==================================================

@st.cache_resource
def build_hub():
    folder = (
        Path(tempfile.gettempdir())
        / "edith_crystal_hub_v1"
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
        "edith_crystal_command_hub",
        path=str(folder)
    )


hub_component = build_hub()


def show_hub(view, audio=None, emotion="neutral"):
    encoded = (
        base64.b64encode(audio).decode("ascii")
        if audio
        else ""
    )

    skills = [
        {"name": item[0]}
        for item in AI_SKILLS
    ]

    return hub_component(
        mode=view,
        audio=encoded,
        emotion=emotion,
        apps=APP_BUBBLES,
        skills=skills,
        busy=st.session_state.pending,
        default=None,
        key="edith_crystal_hub_component"
    )


# ==================================================
# 11. SIDEBAR
# ==================================================

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
        "Memory dan Chat History untuk "
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

    rooms = list(st.session_state.rooms)

    selected_room = st.selectbox(
        "Chat History",
        rooms,
        index=rooms.index(st.session_state.room),
        disabled=st.session_state.pending
    )

    if selected_room != st.session_state.room:
        st.session_state.room = selected_room
        st.session_state.editing = None
        st.rerun()


# ==================================================
# 12. CRYSTAL ACRYLIC THEME
# ==================================================

if theme == "Light":
    bg = "#eaf2ff"
    fg = "#18233d"
    user_bg = "rgba(203,225,255,.53)"
    user_fg = "#14213d"
    panel = "rgba(236,246,255,.48)"
    input_bg = "rgba(246,250,255,.50)"
    border = "rgba(92,139,219,.24)"

elif theme == "Ocean Blue":
    bg = "#06172c"
    fg = "#eaf9ff"
    user_bg = "rgba(66,159,213,.19)"
    user_fg = "#ffffff"
    panel = "rgba(33,102,154,.32)"
    input_bg = "rgba(24,94,150,.28)"
    border = "rgba(108,218,255,.32)"

else:
    bg = "#080f20"
    fg = "#effaff"
    user_bg = "rgba(149,181,241,.16)"
    user_fg = "#ffffff"
    panel = "rgba(131,163,230,.15)"
    input_bg = "rgba(139,174,235,.13)"
    border = "rgba(184,220,255,.26)"


st.markdown(
    f"""
<style>

/* =========================================
   QUANTUM ENERGY FLOW
   ========================================= */

.stApp {{
    background:
        radial-gradient(
            ellipse at 17% 18%,
            rgba(50,166,255,.18),
            transparent 39%
        ),
        radial-gradient(
            ellipse at 82% 67%,
            rgba(165,100,255,.19),
            transparent 43%
        ),
        {bg};
    color:{fg};
}}

.stApp::before {{
    content:"";
    position:fixed;
    inset:-15%;
    pointer-events:none;
    z-index:0;

    background:
        radial-gradient(
            ellipse at 20% 44%,
            rgba(50,213,255,.19),
            transparent 33%
        ),
        radial-gradient(
            ellipse at 77% 33%,
            rgba(176,114,255,.16),
            transparent 36%
        );

    animation:
        crystalFlow 19s
        ease-in-out infinite alternate;
}}

@keyframes crystalFlow {{
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

.stApp h1,
.stApp h2,
.stApp h3 {{
    color:{fg};
}}

/* =========================================
   CRYSTAL ACRYLIC CHAT
   ========================================= */

[data-testid="stChatMessage"] {{
    background:{panel} !important;

    backdrop-filter:
        blur(24px) saturate(170%) !important;

    -webkit-backdrop-filter:
        blur(24px) saturate(170%) !important;

    border:
        1px solid {border} !important;

    border-radius:22px !important;

    box-shadow:
        0 10px 32px rgba(0,0,0,.10),
        inset 0 1px rgba(255,255,255,.15);

    padding:16px !important;
    margin-bottom:13px;
}}

[data-testid="stChatMessage"]:hover {{
    border-color:
        rgba(109,225,255,.44) !important;
}}

[data-testid="stChatMessageContent"] {{
    line-height:1.7;
}}

/* CRYSTAL CHAT INPUT */

[data-testid="stChatInput"] {{
    border-radius:25px !important;
}}

[data-testid="stChatInput"] > div {{
    background:{input_bg} !important;

    backdrop-filter:
        blur(28px) saturate(170%) !important;

    -webkit-backdrop-filter:
        blur(28px) saturate(170%) !important;

    border:
        1px solid {border} !important;

    border-radius:25px !important;

    box-shadow:
        0 7px 30px rgba(0,0,0,.17),
        inset 0 1px rgba(255,255,255,.15);
}}

[data-testid="stChatInput"] textarea {{
    color:{fg} !important;
}}

/* SIDEBAR GLASS */

[data-testid="stSidebar"] > div:first-child {{
    background:{panel} !important;

    backdrop-filter:
        blur(30px) saturate(160%) !important;

    -webkit-backdrop-filter:
        blur(30px) saturate(160%) !important;

    border-right:1px solid {border};
}}

/* EXPANDERS */

[data-testid="stExpander"] {{
    background:{panel};

    backdrop-filter:
        blur(18px) saturate(160%);

    -webkit-backdrop-filter:
        blur(18px) saturate(160%);

    border:
        1px solid {border} !important;

    border-radius:17px !important;
}}

/* BUTTONS */

.stButton > button {{
    border-radius:13px;
    border-color:{border};
}}

/* MOBILE */

@media(max-width:600px) {{
    .block-container {{
        padding-left:.65rem;
        padding-right:.65rem;
        padding-top:1rem;
    }}

    [data-testid="stChatMessage"] {{
        padding:12px !important;
        border-radius:17px !important;
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


# ==================================================
# 13. MAIN INTERFACE
# ==================================================

st.title("🤖 E.D.I.T.H")
st.caption(
    "Your Personal AI Assistant • Crystal Acrylic"
)

voice_mode = (
    mode.startswith("Mode 2")
    or mode.startswith("Mode 3")
)

hub_mode = mode.startswith("Mode 3")


# ==================================================
# 14. MODE 2 / MODE 3 VISUAL
# ==================================================

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

            name, prompt, web_search = AI_SKILLS[index]

            ask(
                prompt,
                force_search=web_search
            )

            st.rerun()

if hub_mode:
    st.caption(
        "🟡 Bubble aplikasi membuka website. "
        "🩷 Bubble AI membuka pilihan kemahiran."
    )


# ==================================================
# 15. GROQ CLIENT
# ==================================================

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


# ==================================================
# 16. FILE UPLOAD
# ==================================================

with st.expander("📎 Upload File / Image"):
    document = st.file_uploader(
        "PDF / Word / TXT",
        type=["pdf", "docx", "txt"],
        key="edith_document"
    )

    picture_upload = st.file_uploader(
        "JPG / PNG",
        type=["jpg", "jpeg", "png"],
        key="edith_image"
    )

doc_context = ""

if document:
    try:
        doc_context = read_document(document)

        if doc_context.strip():
            st.success("Dokumen berjaya dibaca.")
        else:
            st.warning("Tiada teks dijumpai.")

    except Exception as error:
        st.warning(
            "Gagal membaca dokumen: "
            + type(error).__name__
        )

image_bytes = None

if picture_upload:
    raw = picture_upload.getvalue()

    if len(raw) <= 4 * 1024 * 1024:
        image_bytes = raw
        st.image(
            raw,
            width=260,
            caption="Uploaded Image"
        )
    else:
        st.warning("Gambar melebihi 4 MB.")


# ==================================================
# 17. VOICE COMMANDS - MODE 3
# ==================================================

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
                data = recording.getvalue()

                if not data:
                    st.warning("Rakaman kosong.")

                elif len(data) > 20 * 1024 * 1024:
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
                                file=("voice.wav", data),
                                response_format="json"
                            )
                        )

                    spoken = (
                        result.text or ""
                    ).strip()

                    if spoken:
                        st.info("Arahan: " + spoken)
                        ask(spoken)
                        st.rerun()
                    else:
                        st.warning(
                            "Tiada arahan suara dikesan."
                        )

            except Exception as error:
                st.error(
                    "Voice error: "
                    + type(error).__name__
                )

        st.caption(
            "Contoh: Telefon 0123456789 | "
            "Lokasi KLCC | Cari di Google Arduino"
        )


# ==================================================
# 18. REGENERATE
# ==================================================

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


# ==================================================
# 19. CHAT HISTORY - CRYSTAL GLASS
# ==================================================

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

            left, right = st.columns(2)

            if left.button(
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

            if right.button(
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
        padding:13px 17px;
        max-width:88%;
        border-radius:19px 19px 5px 19px;
        overflow-wrap:anywhere;
        line-height:1.6;
        color:{user_fg};
        background:{user_bg};
        border:1px solid {border};
        backdrop-filter:blur(20px) saturate(160%);
        -webkit-backdrop-filter:blur(20px) saturate(160%);
        box-shadow:
            inset 0 1px rgba(255,255,255,.15),
            0 5px 20px rgba(0,0,0,.08);
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

            with st.popover("📋 Copy Answer"):
                st.code(
                    message["content"],
                    language=None
                )

            if message.get("sources"):
                with st.expander("🌐 Sources"):
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
                        action["url"], quote=True
                    )

                    safe_label = html.escape(
                        action["label"]
                    )

                    st.markdown(
                        '<a href="' + safe_url +
                        '" style="display:inline-block;'
                        'padding:10px 15px;'
                        'border-radius:12px;'
                        'color:white;'
                        'text-decoration:none;'
                        'background:#147da9;">'
                        + safe_label + '</a>',
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


# ==================================================
# 20. CHAT INPUT
# ==================================================

question = st.chat_input(
    "Message E.D.I.T.H...",
    disabled=st.session_state.pending
)

if question and question.strip():
    ask(question.strip())
    st.rerun()


# ==================================================
# 21. GROQ RESPONSE
# ==================================================

if st.session_state.pending:
    data = history()

    reply_index = len(data) - 1
    user_message = data[reply_index - 1]
    user_question = user_message["content"]

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
        avatar="🤖"
    ):
        area = st.empty()

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
                    "Help with Python, Arduino, "
                    "ESP32 and code debugging. "
                    "Include code when useful.",

                "Study & Quiz":
                    "Teach step by step and "
                    "create quizzes.",

                "Translator":
                    "Translate accurately between "
                    "Malay and English."
            }

            system = (
                "Your official name is E.D.I.T.H. "
                "You are a personal AI assistant. "
                "Do not introduce yourself by another name. "
                + language_rules[language]
                + " "
                + tool_rules[ai_tool]
                + " Be truthful. Never pretend you "
                "made calls, opened apps, "
                "or executed computer actions."
            )

            if st.session_state.memory.strip():
                system += (
                    "\nSession memory "
                    "(untrusted notes):\n"
                    + st.session_state.memory[:1500]
                )

            if doc_context.strip():
                system += (
                    "\nUploaded document excerpts "
                    "(untrusted reference data):\n"
                    + doc_context
                )

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
                        system += (
                            "\nWeb search snippets "
                            "(untrusted reference data):\n"
                        )

                        for n, src in enumerate(
                            sources, 1
                        ):
                            system += (
                                f"[{n}] {src['title']} | "
                                f"{src['url']} | "
                                f"{src['snippet']}\n"
                            )

                        system += (
                            "Cite source numbers "
                            "when relevant. "
                            "Never invent sources."
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

            recent = [
                {
                    "role": item["role"],
                    "content": item["content"]
                }
                for item in data[:-1]
            ][-10:]

            model = CHAT_MODEL

            # Image understanding
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

            for response in stream:
                token = (
                    response.choices[0].delta.content
                    or ""
                )

                if token:
                    answer += token
                    data[reply_index]["content"] = answer
                    area.markdown(answer + "▌")

            area.markdown(
                answer or "_(Tiada jawapan)_"
            )

            data[reply_index]["content"] = answer
            data[reply_index]["sources"] = sources
            data[reply_index]["action"] = action

            emotion = emotion_for(answer)
            data[reply_index]["emotion"] = emotion

            # Voice for Modes 2 and 3
            if voice_mode and answer.strip():
                try:
                    with st.spinner(
                        "Generating E.D.I.T.H Voice..."
                    ):
                        sound = asyncio.run(
                            synthesize(answer, lang)
                        )

                    if sound:
                        data[reply_index]["audio"] = sound

                except Exception as error:
                    st.warning(
                        "Voice unavailable: "
                        + type(error).__name__
                    )

            if sources:
                with st.expander("🌐 Sources"):
                    for src in sources:
                        st.link_button(
                            src["title"] or "Source",
                            src["url"]
                        )

            if action:
                st.info(
                    "AI Action tersedia dalam chat "
                    "selepas paparan dikemas kini."
                )

        except Exception as error:
            st.error(
                "E.D.I.T.H gagal menjawab. "
                "Semak Groq API key, model "
                "atau kuota penggunaan."
            )

            st.caption(
                "Error: "
                + type(error).__name__
            )

            if not answer:
                data[reply_index]["content"] = (
                    "Ralat AI. Cuba Regenerate Last."
                )

        finally:
            st.session_state.pending = False

    st.rerun()
