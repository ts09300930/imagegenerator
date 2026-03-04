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
    # 【最新確定】grok-2-vision-latest を使用。
    # これが画像解析における公式の最新推奨エンドポイント名です。
    payload = {
        "model": "grok-2-vision-latest", 
        "messages": messages, 
        "max_tokens": 1000, 
        "temperature": 0.7
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}", 
        "Content-Type": "application/json"
    }
    
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"].strip()
        else:
            # エラー時に詳細を表示（モデル名不正ならここで原因が判明する）
            error_detail = res.json().get('error', {}).get('message', 'No message')
            return f"Error_{res.status_code}: {error_detail}"
    except Exception as e:
        return f"Connection_Error: {str(e)}"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    img.thumbnail((800, 800))
    if img.mode != 'RGB': img = img.convert('RGB')
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=80)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- UI ---
st.title("Higgsfield Gen v8.8 (Verified Model)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴 (黒髪など、画像より優先されます)", value=st.session_state.get('char_description', ""))

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
    if c2.button("🎲 シチュエーション生成"):
        res = call_grok_api([{"role": "user", "content": "日本のSNS自撮り風シチュエーション案を3個出して。'場所：、服装：、状態：'の形式で。"}] )
        if "Error" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所：" in s][:gen_count]
    
    if 'scenes_list' in st.session_state:
        for i, scene in enumerate(st.session_state.scenes_list):
            st.session_state.scenes_list[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
        for s in st.session_state.scenes_list: targets.append({"type": "text", "content": s})

st.markdown("---")
st.markdown("### ⚙️ オプション")
col1, col2 = st.columns(2)
bust_type = col2.radio("胸", ["貧乳","普通","豊満"], horizontal=True)

# --- 生成実行 ---
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.error("画像またはテキストを入力してください。")
        st.stop()
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        with st.container():
            if item["type"] == "image":
                img_b64 = process_image(item['content'])
                with st.spinner(f"画像 {i+1} 解析中..."):
                    # 確実に vision 対応モデルで解析
                    current_ctx = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe this image's outfit and background precisely."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}"}}]}])
                display_img = item['content'].getvalue()
            else:
                current_ctx = item["content"]
                display_img = None

            if "Error" in current_ctx:
                st.error(f"❌ 解析失敗 {i+1}: {current_ctx}")
                continue

            with st.spinner(f"プロンプト {i+1} 合成中..."):
                bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")
                
                # 最終プロンプト構築
                instruction = (
                    f"Subject: {st.session_state.char_description}, {bust_ins}. "
                    f"Reference Scene: {current_ctx}. "
                    "Task: Create a detailed Stable Diffusion prompt. Replicate the scene but prioritize the Subject's features."
                )

                final_p = call_grok_api([{"role":"user","content": f"{instruction} Output ONLY the prompt starting with 'A photorealistic shot of...'"}])
                
                if "Error" in final_p:
                    st.error(f"❌ 生成失敗 {i+1}: {final_p}")
                    continue

                st.success(f"✅ Result {i+1}")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                st.text_area(f"Copy {i+1}", value=final_p, key=f"copy_{i}")
