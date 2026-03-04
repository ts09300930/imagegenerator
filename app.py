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

# --- 設定 ---
GROK_MODEL = "grok-2-vision-latest"  # Vision対応の最新モデルID
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

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

# Grok API Key取得
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキー", type="password")
    if not API_KEY: st.stop()

def call_grok_api(messages):
    payload = {
        "model": GROK_MODEL, 
        "messages": messages, 
        "max_tokens": 1500, 
        "temperature": 0.8
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
        
        # HTTPエラー（400番台、500番台）をチェック
        if res.status_code != 200:
            try:
                err_json = res.json()
                msg = err_json.get('error', {}).get('message', 'Unknown Error')
                return f"API_ERROR_{res.status_code}: {msg}"
            except:
                return f"API_ERROR_{res.status_code}: {res.text[:100]}"

        # 正常応答の解析
        json_res = res.json()
        return json_res["choices"][0]["message"]["content"].strip()

    except Exception as e:
        # ここが諸悪の根源でした。属性操作を一切せず、文字列だけを返します。
        return f"SYSTEM_ERROR: {str(e)}"

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

# --- UI ---
st.title("Higgsfield Gen v9.0 (Absolute Fix)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴から選択", ["-- 履歴なし --"] + char_h)
if sel_h != "-- 履歴なし --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴", value=st.session_state.char_description)

st.markdown("---")
st.markdown("### 🎬 2. シチュエーション設定")
mode = st.radio("入力モード", ["📷 画像解析", "🎲 AI自動生成"], horizontal=True)

targets = []
if mode == "📷 画像解析":
    uploaded_images = st.file_uploader("画像アップロード", type=["jpg","png","heic"], accept_multiple_files=True)
    if uploaded_images:
        for f in uploaded_images:
            targets.append({"type": "image", "content": f})
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button(f"🎲 {gen_count}件を自動生成"):
        res = call_grok_api([{"role": "user", "content": f"日本のSNS自撮り風シチュエーションを{gen_count}個。'場所：、服装：、状態：'の形式で。"}] )
        if "ERROR" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所：" in s][:gen_count]
    
    for i, scene in enumerate(st.session_state.scenes_list):
        st.session_state.scenes_list[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
    for s in st.session_state.scenes_list: targets.append({"type": "text", "content": s})

st.markdown("---")
st.markdown("### ⚙️ オプション")
col1, col2 = st.columns(2)
sex_level = col1.select_slider("露出レベル", options=[1,2,3,4,5], value=3)
bust_type = col2.radio("胸のサイズ", ["貧乳","普通","豊満"], horizontal=True)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装")
nipple_poke = cb.checkbox("乳首ぽち")
mask_on = cc.checkbox("白マスク")

sex_map = {1: "modest", 2: "casual", 3: "sexy", 4: "revealing", 5: "extreme"}

if st.button("🚀 プロンプトを一括生成", type="primary"):
    if not targets:
        st.warning("対象がありません。")
        st.stop()
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        current_ctx = ""
        display_img = None
        
        if item["type"] == "image":
            img_b64 = process_image(item['content'])
            display_img = item['content'].getvalue()
            with st.spinner(f"解析中..."):
                current_ctx = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe outfit and background."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}"}}]}])
        else:
            current_ctx = item["content"]

        # ここでエラーがあればスキップ。'str' object...エラーを防ぐため慎重に判定
        if "ERROR" in str(current_ctx):
            st.error(f"❌ {current_ctx}")
            continue

        with st.spinner(f"合成中..."):
            bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")
            prompt_msg = f"Subject: {st.session_state.char_description}, {bust_ins}. Context: {current_ctx}. Create a photorealistic English prompt."
            
            final_p = call_grok_api([{"role":"user","content": prompt_msg}])
            
            if "ERROR" in str(final_p):
                st.error(f"❌ {final_p}")
                continue

            st.success(f"✅ Result {i+1}")
            if display_img: st.image(display_img, width=200)
            st.code(final_p)
