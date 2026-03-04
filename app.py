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
    # 最新確定モデル: grok-2-vision-latest
    payload = {
        "model": "grok-2-vision-latest", 
        "messages": messages, 
        "max_tokens": 1500, 
        "temperature": 0.8
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"Error_{res.status_code}: {res.json().get('error', {}).get('message', 'API Error')}"
    except Exception as e:
        return f"Connection_Error: {str(e)}"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    img.thumbnail((1024, 1024))
    if img.mode != 'RGB': img = img.convert('RGB')
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 状態初期化 ---
if 'char_description' not in st.session_state: st.session_state.char_description = ""
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = []
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- UI ---
st.title("Higgsfield Gen v8.9 (Full Features & Latest Model)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴 (黒髪など、画像より絶対優先)", value=st.session_state.char_description)

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
        res = call_grok_api([{"role": "user", "content": f"日本の裏垢女子風の自撮りシチュエーションを{gen_count}個考えて。形式：'場所：〇〇、服装：××、状態：△△' を厳守。"}] )
        if "Error" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所：" in s][:gen_count]
    if st.session_state.scenes_list:
        for i, scene in enumerate(st.session_state.scenes_list):
            st.session_state.scenes_list[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
        for s in st.session_state.scenes_list: targets.append({"type": "text", "content": s})

st.markdown("---")
st.markdown("### ⚙️ 共通オプション (全機能復活)")
col1, col2 = st.columns(2)
sex_level = col1.select_slider("露出レベル", options=[1,2,3,4,5], value=3)
bust_type = col2.radio("胸のサイズ", ["貧乳","普通","豊満"], horizontal=True)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装")
nipple_poke = cb.checkbox("乳首ぽち")
mask_on = cc.checkbox("白マスク")
cd, ce, cf = st.columns(3)
iphone_selfie = cd.checkbox("iPhone鏡自撮り")
face_hidden = ce.checkbox("顔を隠す")

sex_map = {1: "modest", 2: "casual", 3: "sexy", 4: "revealing", 5: "extreme"}

# --- 生成実行 ---
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像かテキストを入力してください。")
        st.stop()
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        with st.container():
            if item["type"] == "image":
                img_b64 = process_image(item['content'])
                with st.spinner(f"画像 {i+1} を独立解析中..."):
                    current_ctx = call_grok_api([{"role":"user","content":[{"type":"text","text":"Analyze THIS image's background and outfit details precisely. Ignore other images."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}"}}]}])
                is_img = True
                display_img = item['content'].getvalue()
            else:
                current_ctx = item["content"]
                is_img = False
                display_img = None

            if "Error" in current_ctx:
                st.error(f"❌ 解析失敗 {i+1}: {current_ctx}")
                continue

            with st.spinner(f"プロンプト {i+1} 合成中..."):
                quality = "Masterpiece, 8k UHD, photorealistic, cinematic lighting, raw smartphone photo style."
                extras = []
                if tight_clothing: extras.append("extremely tight clothing, showing body lines")
                if nipple_poke: extras.append("visible nipple outlines through clothes")
                if mask_on: extras.append("wearing a white surgical mask")
                if iphone_selfie: extras.append("holding iPhone, mirror selfie, camera flash")
                if face_hidden: extras.append("face hidden or obscured, focused on body")
                
                bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")
                
                # 指示の構築
                if is_img:
                    instruction = (
                        f"Target Subject (ABSOLUTE PRIORITY): {st.session_state.char_description}, {bust_ins}.\n"
                        f"Mandatory Scene from Image: {current_ctx}.\n"
                        f"Style/Options: {sex_map[sex_level]}, {', '.join(extras)}, Quality: {quality}.\n"
                        "Task: Replicate the image's background/outfit but force the Target Subject's features onto the person."
                    )
                else:
                    instruction = f"Subject: {st.session_state.char_description}, Scene: {current_ctx}, Style: {sex_map[sex_level]}, {bust_ins}, {', '.join(extras)}, Quality: {quality}."

                final_p = call_grok_api([{"role":"user","content": f"{instruction} Output ONLY the English prompt starting with 'A photorealistic shot of...'"}])
                
                if "Error" in final_p:
                    st.error(f"❌ 生成失敗 {i+1}: {final_p}")
                    continue

                # 強制補正タグ
                if bust_type == "貧乳": final_p += ", (flat chest:1.9)"
                if nipple_poke: final_p += ", (nipples poking through clothing:1.4)"
                if sex_level == 5: final_p += ", (suggestive pose:1.3)"

                st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
                st.success(f"✅ Result {i+1}")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                st.text_area(f"Copy {i+1}", value=final_p, height=100, key=f"copy_{i}_{random.randint(0,999)}")
