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

# Grok API設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキーを入力してください", type="password")

if not API_KEY:
    st.error("APIキーが未入力です。")
    st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-4" # 元の成功モデル名

# 状態の初期化
init_char, init_scene = load_app_data()
if 'char_description' not in st.session_state: st.session_state.char_description = init_char
if 'scene_description' not in st.session_state: st.session_state.scene_description = init_scene
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- AIロジック ---
def call_grok_api(messages, max_tokens=600):
    payload = {"model": GROK_MODEL, "messages": messages, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=40)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        return f"API Error: {response.status_code}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# --- UI構築 ---
st.title("Higgsfield Prompt Gen v5.8")

# 1. 特徴入力
st.markdown("### 👩 1. 女性の身体的特徴")
char_input = st.text_area("髪型、顔、体型など（自動保存）", value=st.session_state.char_description)
if char_input != st.session_state.char_description:
    st.session_state.char_description = char_input
    save_app_data(char_input, st.session_state.scene_description)

st.markdown("---")

# 2. シチュエーション
st.markdown("### 🎬 2. シチュエーション")
tab1, tab2 = st.tabs(["📷 画像解析", "🎲 AI丸投げ"])

with tab1:
    uploaded_images = st.file_uploader("参考画像（複数可）", type=["jpg", "png", "heic"], accept_multiple_files=True)

with tab2:
    if st.button("🎲 AIに新しいシチュエーションを提案させる"):
        with st.spinner("リアルな投稿ネタを考案中..."):
            prompt = [{"role": "user", "content": (
                "Suggest one realistic Japanese SNS selfie situation for a sexy influencer. "
                "Context: bedroom, hotel, bathroom, or daily life. "
                "Format: '場所：〇〇、服装：××、状態：△△'. Japanese, 1 line only."
            )}]
            res = call_grok_api(prompt, max_tokens=100)
            if "Error" not in res:
                st.session_state.scene_description = res
                save_app_data(st.session_state.char_description, res)
                st.rerun()

scene_input = st.text_area("現在のシチュエーション（編集可）", value=st.session_state.scene_description)
if scene_input != st.session_state.scene_description:
    st.session_state.scene_description = scene_input
    save_app_data(st.session_state.char_description, scene_input)

# 3. オプション
st.markdown("---")
col1, col2 = st.columns(2)
sex_level = col1.radio("露出レベル", options=[1, 2, 3, 4, 5], index=2, horizontal=True)
bust_type = col2.radio("胸のサイズ", options=["貧乳", "普通", "豊満"], index=1, horizontal=True)

# --- 生成実行 ---
if st.button("🚀 プロンプト生成", type="primary", use_container_width=True):
    # 画像があれば画像優先、なければテキスト
    process_list = []
    if uploaded_images:
        for img in uploaded_images:
            process_list.append({"type": "image", "file": img})
    else:
        process_list.append({"type": "text", "content": st.session_state.scene_description})

    for item in process_list:
        if item["type"] == "image":
            with st.spinner(f"画像を解析中: {item['file'].name}..."):
                # 画像プレビュー表示
                st.image(item['file'], caption=f"解析元: {item['file'].name}", width=300)
                b64 = base64.b64encode(item['file'].getvalue()).decode('utf-8')
                msg = [{"role": "user", "content": [
                    {"type": "text", "text": "Describe environment and clothing in one English paragraph. Realistic focus."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]}]
                context = call_grok_api(msg)
                display_img = item['file'].getvalue()
        else:
            context = item["content"]
            display_img = None

        with st.spinner("プロンプトを高品質に合成中..."):
            # 肌感・画質を極限まで高める英語指示を追加
            quality_boost = "Masterpiece, 8k UHD, photorealistic, raw photo, high-quality skin texture, detailed pores, cinematic lighting, shot on iPhone, realistic SNS selfie."
            
            final_instruction = (
                f"As a pro prompt engineer, create one photorealistic English paragraph. "
                f"Subject: {st.session_state.char_description}. "
                f"Scene & Clothing: {context}. Sexiness Level: {sex_level}. Bust: {bust_type}. "
                f"Style: {quality_boost}. "
                "Output ONLY the paragraph, starting with 'A photorealistic shot of...'"
            )
            
            if bust_type == "貧乳":
                final_instruction += " Strictly describe as a flat chest, petite bony torso, zero breast volume."

            final_prompt = call_grok_api([{"role": "user", "content": final_instruction}])
            
            # 貧乳ウェイトの最終調整
            if bust_type == "貧乳":
                final_prompt += ", (flat chest:1.9), (tiny breasts:1.5), (bony collarbones:1.3)"
            
            # 履歴に追加
            st.session_state.prompt_history.append({"prompt": final_prompt, "image": display_img})
            st.code(final_prompt)

# --- 履歴表示 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 生成履歴（最新10件）")
    for idx, hist in enumerate(reversed(st.session_state.prompt_history[-10:])):
        with st.expander(f"履歴 {len(st.session_state.prompt_history) - idx}"):
            if hist["image"]:
                st.image(hist["image"], width=200)
            st.code(hist["prompt"])
