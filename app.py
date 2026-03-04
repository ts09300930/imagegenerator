import streamlit as st
import requests
import os
import base64
import pandas as pd
from pillow_heif import register_heif_opener
import io
from PIL import Image
import random

# HEICサポート
register_heif_opener()

# --- 保存・履歴設定 ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
SAVE_FILE = os.path.join(DATA_DIR, "app_state_v8.csv")
CHAR_HISTORY_FILE = os.path.join(DATA_DIR, "char_history_v8.csv")

def save_char_history(char):
    if not char.strip(): return
    h = load_char_history()
    if char in h: h.remove(char)
    h.insert(0, char)
    pd.DataFrame({"char_desc": h[:100]}).to_csv(CHAR_HISTORY_FILE, index=False)

def load_char_history():
    if os.path.exists(CHAR_HISTORY_FILE):
        try: return pd.read_csv(CHAR_HISTORY_FILE)["char_desc"].dropna().tolist()
        except: return []
    return []

# Grok API
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキー", type="password")
    if not API_KEY: st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def call_grok_api(messages):
    payload = {"model": "grok-4", "messages": messages, "max_tokens": 1500, "temperature": 0.9}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
        return res.json()["choices"][0]["message"]["content"].strip() if res.status_code == 200 else f"Error: {res.status_code}"
    except: return "Connection Error"

# --- 状態初期化 ---
if 'char_description' not in st.session_state: st.session_state.char_description = ""
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = []
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- AI提案：複数一括生成関数 ---
def generate_multiple_scenes(count):
    buffer_count = count + 2
    with st.spinner(f"シチュエーションを{count}パターン生成中..."):
        prompt = [{
            "role": "user", 
            "content": (
                f"日本のSNSで人気の『裏垢女子』風シチュエーションを【{buffer_count}個】作成してください。\n"
                "形式：'場所：〇〇、服装：××、状態：△△'。挨拶抜き、1行ずつ。"
            )
        }]
        res = call_grok_api(prompt)
        if "Error" not in res:
            all_lines = [s.strip() for s in res.split('\n') if s.strip()]
            valid_scenes = [line for line in all_lines if "場所：" in line]
            st.session_state.scenes_list = valid_scenes[:count]

# --- UI ---
st.title("Higgsfield Gen v8.4 (Level 1-5 Strict Control)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --": st.session_state.char_description = sel_h

st.session_state.char_description = st.text_area("身体的特徴", value=st.session_state.char_description)

st.markdown("---")

st.markdown("### 🎬 2. シチュエーション設定")
mode = st.radio("入力モードを選択", ["📷 画像解析（アップロード）", "🎲 AI自動生成（テキスト）"], horizontal=True)

targets = []

if mode == "📷 画像解析（アップロード）":
    uploaded_images = st.file_uploader("画像アップロード", type=["jpg","png","heic"], accept_multiple_files=True)
    if uploaded_images:
        for f in uploaded_images:
            targets.append({"type": "image", "content": f})
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button(f"🎲 {gen_count}件を自動生成", use_container_width=True):
        generate_multiple_scenes(gen_count)
    
    if st.session_state.scenes_list:
        new_scenes = []
        for i, scene in enumerate(st.session_state.scenes_list):
            s_val = st.text_area(f"シチュエーション {i+1}", value=scene, key=f"txt_{i}_{hash(scene)}")
            new_scenes.append(s_val)
        st.session_state.scenes_list = new_scenes
        for s in st.session_state.scenes_list:
            if s.strip():
                targets.append({"type": "text", "content": s})

st.markdown("---")
st.markdown("### ⚙️ 共通オプション")
col1, col2 = st.columns(2)

# --- 露出レベル定義の強化 ---
sex_level = col1.select_slider(
    "露出レベル", 
    options=[1, 2, 3, 4, 5], 
    value=3,
    help="1:完全露出なし, 2:日常的, 3:セクシー, 4:過激, 5:全裸・ヌード"
)
bust_type = col2.radio("胸のサイズ", ["貧乳","普通","豊満"], horizontal=True)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装")
nipple_poke = cb.checkbox("乳首ぽち")
mask_on = cc.checkbox("白マスク")

cd, ce, cf = st.columns(3)
iphone_selfie = cd.checkbox("iPhone鏡自撮り")
face_hidden = ce.checkbox("顔を隠す")

# --- 生成実行 ---
if st.button("🚀 全てのプロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像アップロードか、AI生成を行ってください。")
        st.stop()
    
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        with st.container():
            if item["type"] == "image":
                with st.spinner(f"画像 {i+1} 解析中..."):
                    b64 = base64.b64encode(item['content'].getvalue()).decode('utf-8')
                    context = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe this girl's location, clothes and pose."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
                    display_img = item['content'].getvalue()
            else:
                context = item["content"]
                display_img = None

            with st.spinner(f"プロンプト {i+1} 合成中..."):
                # --- レベルに応じた最強の命令セット ---
                level_configs = {
                    1: "NO skin exposure. Fully clothed, modest, innocent, everyday life shot. NO sexy elements. (highneck, long sleeves, jeans, etc.)",
                    2: "Natural and casual. Standard everyday outfit. Very little skin showing. (T-shirt, skirt, casual dress.)",
                    3: "Sexy and attractive. Some skin exposure. Flirty atmosphere. (mini skirt, cleavage, off-shoulder.)",
                    4: "Very revealing and provocative. High skin exposure. Erotic mood. (lingerie, bikini, very short clothes.)",
                    5: "Full nudity, naked, nude, uncensored skin. No clothes. (full body nude, masterpiece skin texture.)"
                }
                
                style_instruction = level_configs[sex_level]
                
                extras = []
                if tight_clothing: extras.append("extremely tight clothing")
                if nipple_poke: extras.append("visible nipple outlines")
                if mask_on: extras.append("white surgical mask")
                if iphone_selfie: extras.append("holding iPhone, mirror selfie")
                if face_hidden: extras.append("face hidden, focused on body")
                
                bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")

                # 命令文の構築
                final_instruction = (
                    f"Task: Create a photorealistic English image prompt.\n"
                    f"Subject: {st.session_state.char_description}\n"
                    f"Situation: {context}\n"
                    f"EXPOSURE LEVEL [{sex_level}/5]: {style_instruction}\n"
                    f"Body: {bust_ins}, Extras: {', '.join(extras)}\n"
                    f"Quality: Masterpiece, 8k, raw photo, realistic skin texture.\n"
                    f"CRITICAL RULE: Strictly follow the EXPOSURE LEVEL. "
                    f"If level is 1, do not use words like 'sexy'. If level is 5, describe the subject as 'naked' or 'nude'."
                )

                final_p = call_grok_api([{"role":"user","content":final_instruction}])
                
                # スケール調整
                if sex_level == 5: final_p += ", (nude:1.5), (completely naked:1.5)"
                if bust_type == "貧乳": final_p += ", (flat chest:1.9)"
                if nipple_poke: final_p += ", (nipples poking through clothing:1.4)"
                
                st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
                st.success(f"Result {i+1} (Level {sex_level})")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                st.text_area(f"Copy {i+1}", value=final_p, height=100, key=f"copy_{i}_{random.randint(0,99999)}")

# --- 履歴 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 生成履歴（最新10件）")
    for idx, hist in enumerate(reversed(st.session_state.prompt_history[-10:])):
        with st.expander(f"履歴 {len(st.session_state.prompt_history) - idx}"):
            if hist["image"]: st.image(hist["image"], width=150)
            st.text_area("プロンプト", value=hist["prompt"], height=100, key=f"hist_txt_{idx}")
