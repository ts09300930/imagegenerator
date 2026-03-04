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

# --- 保存・履歴設定 ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

SAVE_FILE = os.path.join(DATA_DIR, "app_state_v6.csv")
CHAR_HISTORY_FILE = os.path.join(DATA_DIR, "char_history.csv")

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

def save_char_history(char_desc):
    if not char_desc.strip(): return
    history = load_char_history()
    if char_desc in history: history.remove(char_desc)
    history.insert(0, char_desc)
    pd.DataFrame({"char_desc": history[:100]}).to_csv(CHAR_HISTORY_FILE, index=False)

def load_char_history():
    if os.path.exists(CHAR_HISTORY_FILE):
        try:
            df = pd.read_csv(CHAR_HISTORY_FILE)
            return df["char_desc"].dropna().tolist()
        except: return []
    return []

# Grok API設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキーを入力", type="password")

if not API_KEY:
    st.error("APIキーが必要です。")
    st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-4"

# 状態初期化
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
st.title("Higgsfield Prompt Gen v6.1")

# 1. 特徴入力
st.markdown("### 👩 1. 女性の身体的特徴")
char_hist_list = load_char_history()
selected_hist = st.selectbox("過去の履歴から選ぶ (最大100件)", ["-- 履歴から選択 --"] + char_hist_list)

if selected_hist != "-- 履歴から選択 --":
    st.session_state.char_description = selected_hist

char_input = st.text_area("身体的特徴を入力（自動保存）", value=st.session_state.char_description, key="char_area")
if char_input != st.session_state.char_description:
    st.session_state.char_description = char_input
    save_app_data(char_input, st.session_state.scene_description)

st.markdown("---")

# 2. シチュエーション
st.markdown("### 🎬 2. シチュエーション")
# ラジオボタンで明示的にモードを選択するように変更（これで混同を防ぎます）
mode = st.radio("生成モードを選択", ["📷 画像から取得", "🎲 AI丸投げ・テキスト入力"], horizontal=True)

if mode == "📷 画像から取得":
    uploaded_images = st.file_uploader("参考画像", type=["jpg", "png", "heic"], accept_multiple_files=True)
else:
    if st.button("🎲 AIに新しいシチュエーションを提案させる"):
        with st.spinner("考案中..."):
            prompt = [{"role": "user", "content": "Suggest a realistic Japanese SNS selfie scene for a sexy influencer. Format: '場所：〇〇、服装：××、状態：△△'. Japanese, 1 line."}]
            res = call_grok_api(prompt, max_tokens=100)
            if "Error" not in res:
                st.session_state.scene_description = res
                save_app_data(st.session_state.char_description, res)
                st.rerun()

    scene_input = st.text_area("シチュエーション（編集可）", value=st.session_state.scene_description, key="scene_area")
    if scene_input != st.session_state.scene_description:
        st.session_state.scene_description = scene_input
        save_app_data(st.session_state.char_description, scene_input)

# 3. オプション
st.markdown("---")
c1, c2 = st.columns(2)
sex_level = c1.radio("露出レベル", options=[1, 2, 3, 4, 5], index=2, horizontal=True)
bust_type = c2.radio("胸のサイズ", options=["貧乳", "普通", "豊満"], index=1, horizontal=True)

# --- 生成実行 ---
if st.button("🚀 プロンプト生成", type="primary", use_container_width=True):
    save_char_history(st.session_state.char_description)
    
    # モードに応じて処理対象を厳密に切り分け
    process_list = []
    if mode == "📷 画像から取得" and uploaded_images:
        for f in uploaded_images:
            process_list.append({"type": "image", "file": f})
    else:
        # モードがテキスト、または画像モードなのに画像がない場合
        process_list.append({"type": "text", "content": st.session_state.scene_description})

    for item in process_list:
        if item["type"] == "image":
            with st.spinner(f"画像を解析中..."):
                st.image(item['file'], width=200)
                b64 = base64.b64encode(item['file'].getvalue()).decode('utf-8')
                msg = [{"role": "user", "content": [{"type": "text", "text": "Describe environment and clothing. Realistic."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]
                context = call_grok_api(msg)
                display_img = item['file'].getvalue()
        else:
            context = item["content"]
            display_img = None

        with st.spinner("高品質プロンプトを作成中..."):
            quality = "Masterpiece, 8k UHD, photorealistic, raw photo, detailed skin, detailed pores, cinematic lighting, shot on iPhone, SNS selfie."
            final_instruction = f"Subject: {st.session_state.char_description}. Scene: {context}. Sexiness: {sex_level}. Bust: {bust_type}. Style: {quality}. Output one English paragraph starting with 'A photorealistic shot of...'"
            
            if bust_type == "貧乳": final_instruction += " Strictly flat chest, bony torso."
            
            final_p = call_grok_api([{"role": "user", "content": final_instruction}])
            if bust_type == "貧乳": final_p += ", (flat chest:1.9), (tiny breasts:1.5)"
            
            st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
            
            st.code(final_p)
            st.text_area("コピー用", value=final_p, height=100, key=os.urandom(8))

# --- 履歴表示 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 生成履歴（最新10件）")
    for idx, hist in enumerate(reversed(st.session_state.prompt_history[-10:])):
        with st.expander(f"履歴 {len(st.session_state.prompt_history) - idx}"):
            if hist["image"]: st.image(hist["image"], width=150)
            st.text_area("プロンプト", value=hist["prompt"], height=100, key=f"hist_txt_{idx}")
