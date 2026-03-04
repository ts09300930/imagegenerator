import streamlit as st
import requests
import os
import base64
import pandas as pd
from pillow_heif import register_heif_opener
import io
from PIL import Image
import random
import time

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
    # 最新の安定名称 'grok-vision-beta' に固定。これで404/503を回避します。
    payload = {"model": "grok-vision-beta", "messages": messages, "max_tokens": 1500, "temperature": 0.7}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    for attempt in range(3):
        try:
            res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"].strip()
            elif res.status_code in [503, 429]:
                time.sleep(5)
                continue
            else:
                return f"Error: {res.status_code} - {res.text}"
        except Exception as e:
            if attempt == 2: return f"Connection Error: {str(e)}"
            time.sleep(3)
    return "Service Unavailable"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    img.thumbnail((1024, 1024))
    if img.mode != 'RGB': img = img.convert('RGB')
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=80)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 状態初期化 ---
if 'char_description' not in st.session_state: st.session_state.char_description = ""
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = []
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- AI提案 ---
def generate_multiple_scenes(count):
    with st.spinner(f"シチュエーション生成中..."):
        prompt = [{"role": "user", "content": f"日本の裏垢女子風の自撮り案を{count}個考えて。形式：'場所：〇〇、服装：××、状態：△△' を厳守。"}]
        res = call_grok_api(prompt)
        if "Error" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所：" in s][:count]

# --- UI ---
st.title("Higgsfield Gen v8.6 (Official Model Fix)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴 (黒髪など)", value=st.session_state.char_description)

st.markdown("---")
st.markdown("### 🎬 2. シチュエーション設定")
mode = st.radio("入力モード", ["📷 画像解析", "🎲 AI自動生成"], horizontal=True)

targets = []
if mode == "📷 画像解析":
    files = st.file_uploader("アップロード", type=["jpg","png","heic"], accept_multiple_files=True)
    if files:
        for f in files: targets.append({"type": "image", "content": f})
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button("🎲 シチュエーション生成"): generate_multiple_scenes(gen_count)
    if st.session_state.scenes_list:
        new_scenes = []
        for i, scene in enumerate(st.session_state.scenes_list):
            new_scenes.append(st.text_area(f"案 {i+1}", value=scene, key=f"t_{i}_{hash(scene)}"))
        st.session_state.scenes_list = new_scenes
        for s in st.session_state.scenes_list: targets.append({"type": "text", "content": s})

st.markdown("---")
st.markdown("### ⚙️ オプション")
col1, col2 = st.columns(2)
sex_level = col1.select_slider("露出度", options=[1,2,3,4,5], value=3)
bust_type = col2.radio("胸", ["貧乳","普通","豊満"], horizontal=True)
sex_map = {1: "modest", 2: "casual", 3: "sexy", 4: "revealing", 5: "extreme"}

# --- 生成 ---
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets: st.stop()
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        with st.container():
            if item["type"] == "image":
                img_data = process_image(item['content'])
                with st.spinner(f"画像 {i+1} 解析..."):
                    # 他の画像と完全に分離するため、個別のメッセージで送信
                    current_ctx = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe THIS image only. Exact outfit, background, and lighting."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_data}"}}]}])
                is_img = True
                display_img = item['content'].getvalue()
            else:
                current_ctx = item["content"]
                is_img = False
                display_img = None

            if "Error" in current_ctx:
                st.error(f"解析失敗 {i+1}: {current_ctx}")
                continue

            with st.spinner(f"プロンプト {i+1} 合成..."):
                quality = "Masterpiece, 8k UHD, photorealistic, cinematic lighting, raw smartphone photo style."
                bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")
                
                # 指示の完全独立化
                if is_img:
                    instruction = (
                        f"Target Person: {st.session_state.char_description} (HIGHEST PRIORITY). {bust_ins}.\n"
                        f"Image Scene (DO NOT MIX WITH OTHERS): {current_ctx}.\n"
                        f"Quality: {quality}.\n"
                        "Task: Create a prompt for THIS image's scene using the Target Person's features."
                    )
                else:
                    instruction = f"Subject: {st.session_state.char_description}, Scene: {current_ctx}, Style: {sex_map[sex_level]}, {bust_ins}, {quality}."

                final_p = call_grok_api([{"role":"user","content": f"{instruction} Output ONLY the English prompt starting with 'A photorealistic shot of...'"}])
                
                if bust_type == "貧乳": final_p += ", (flat chest:1.9)"
                
                st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
                st.success(f"Result {i+1}")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                st.text_area(f"Copy {i+1}", value=final_p, height=100, key=f"c_{i}_{random.randint(0,999)}")
