import streamlit as st
import requests
import os
import base64
import pandas as pd
from pillow_heif import register_heif_opener
from PIL import Image
import io

# HEICサポート
register_heif_opener()

# --- 保存設定 ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

SAVE_FILE = os.path.join(DATA_DIR, "app_state_v5_final.csv")

def save_app_data(char_desc, scene_desc):
    pd.DataFrame({"char_desc": [char_desc], "scene_desc": [scene_desc]}).to_csv(SAVE_FILE, index=False)

def load_app_data():
    char, scene = "", ""
    if os.path.exists(SAVE_FILE):
        try:
            df = pd.read_csv(SAVE_FILE)
            if not df.empty:
                char = str(df["char_desc"].iloc[0])
                scene = str(df["scene_desc"].iloc[0])
        except: pass
    return char, scene

# Grok API設定（元のコードのモデル名 'grok-4' に戻しました）
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキーを入力してください", type="password")

if not API_KEY:
    st.error("APIキーが未入力です。")
    st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
# ★元のコードで動いていたモデル名に固定します
GROK_MODEL = "grok-4" 

# 起動時のデータ復元
init_char, init_scene = load_app_data()
if 'char_description' not in st.session_state: st.session_state.char_description = init_char
if 'scene_description' not in st.session_state: st.session_state.scene_description = init_scene

# --- AIロジック ---
def call_grok_api(messages, max_tokens=600):
    payload = {
        "model": GROK_MODEL,
        "messages": messages,
        "max_tokens": max_tokens
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=40)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"API Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# --- UI構築 ---
st.title("Higgsfield Prompt Gen v5.7")

st.markdown("### 👩 1. 女性の特徴 (固定)")
char_input = st.text_area("身体的特徴を入力", value=st.session_state.char_description)
if char_input != st.session_state.char_description:
    st.session_state.char_description = char_input
    save_app_data(char_input, st.session_state.scene_description)

st.markdown("---")

st.markdown("### 🎬 2. シチュエーション")
tab1, tab2 = st.tabs(["📷 画像解析", "🎲 AI丸投げ"])

with tab1:
    uploaded_images = st.file_uploader("参考画像", type=["jpg", "png", "heic"], accept_multiple_files=True)

with tab2:
    if st.button("🎲 AIに新しいシチュエーションを提案させる"):
        with st.spinner("AIが考案中..."):
            prompt = [{"role": "user", "content": "Suggest a creative photo scene: '場所：〇〇、服装：××、状態：△△'. Japanese, 1 line."}]
            res = call_grok_api(prompt, max_tokens=100)
            if "Error" not in res:
                st.session_state.scene_description = res
                save_app_data(st.session_state.char_description, res)
                st.rerun()
            else:
                st.error(res)

scene_input = st.text_area("現在のシチュエーション", value=st.session_state.scene_description)
if scene_input != st.session_state.scene_description:
    st.session_state.scene_description = scene_input
    save_app_data(st.session_state.char_description, scene_input)

# 3. オプション設定
st.markdown("---")
sex_level = st.radio("露出レベル", options=[1, 2, 3, 4, 5], index=2, horizontal=True)
bust_type = st.radio("胸のサイズ", options=["貧乳", "普通", "豊満"], index=1, horizontal=True)

# --- 生成実行 ---
if st.button("🚀 プロンプト生成", type="primary", use_container_width=True):
    items = []
    if uploaded_images:
        for img in uploaded_images:
            b64 = base64.b64encode(img.getvalue()).decode('utf-8')
            items.append({"type": "image", "data": b64})
    else:
        items.append({"type": "text", "content": st.session_state.scene_description})

    for item in items:
        if item["type"] == "image":
            # 画像解析
            msg = [{"role": "user", "content": [
                {"type": "text", "text": "Describe environment and clothing in one English paragraph."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{item['data']}"}}
            ]}]
            context = call_grok_api(msg)
        else:
            context = item["content"]

        # プロンプト合成（元のコードの強力な指示セットを流用）
        final_instruction = (
            f"Merge features: {st.session_state.char_description}. "
            f"Scene: {context}. Sexiness Level: {sex_level}. Bust: {bust_type}. "
            "Output ONLY one English paragraph for AI image generation. "
            "Start with 'A photo of...'"
        )
        
        # 貧乳補正の強制（元のロジック）
        if bust_type == "貧乳":
            final_instruction += " Strictly flat chest, bony torso, no volume."

        final_prompt = call_grok_api([{"role": "user", "content": final_instruction}])
        
        # 最終的な重み付け
        if bust_type == "貧乳":
            final_prompt += ", (flat chest:1.9), (tiny breasts:1.5)"
        
        st.code(final_prompt)
