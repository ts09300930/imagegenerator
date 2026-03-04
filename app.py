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

# 保存ファイル名をv5_5に固定
SAVE_FILE = os.path.join(DATA_DIR, "app_state_v5_5.csv")

def save_app_data(char_desc, scene_desc):
    pd.DataFrame({"char_desc": [char_desc], "scene_desc": [scene_desc]}).to_csv(SAVE_FILE, index=False)

def load_app_data():
    char, scene = "", ""
    if os.path.exists(SAVE_FILE):
        try:
            df = pd.read_csv(SAVE_FILE)
            if not df.empty:
                char = str(df["char_desc"].iloc[0]) if "char_desc" in df.columns else ""
                scene = str(df["scene_desc"].iloc[0]) if "scene_desc" in df.columns else ""
        except: pass
    return char, scene

# Grok API設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキーを入力してください", type="password")

if not API_KEY:
    st.error("APIキーが未入力です。サイドバーから入力してください。")
    st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
# テキスト生成用
TEXT_MODEL = "grok-beta"
# 画像解析用（Vision必須）
VISION_MODEL = "grok-2-vision-1224"

# 起動時のデータ復元
init_char, init_scene = load_app_data()

if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []
if 'char_description' not in st.session_state: st.session_state.char_description = init_char
if 'scene_description' not in st.session_state: st.session_state.scene_description = init_scene

# --- AIロジック ---
def analyze_image_with_grok(image_data):
    """画像解析は専用モデルで行う"""
    base64_image = base64.b64encode(image_data).decode('utf-8')
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe the location and clothing in one English sentence. No faces."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=40)
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Image Analysis Error: {str(e)}"

def generate_final_prompt(char_desc, context_info, sex_level, tight, nipple, bust):
    """プロンプト合成は安定したgrok-betaで行う"""
    level_dict = {
        1: "fully clothed, modest outfit", 2: "slight skin exposure", 
        3: "visible cleavage, sexy style", 4: "bikini or lingerie", 5: "nearly nude"
    }
    level_desc = level_dict.get(sex_level, "")
    
    extra = []
    if tight: extra.append("tight clothing")
    if nipple: extra.append("visible nipple outlines")
    
    bust_p = ""
    if bust == "貧乳": bust_p = "strictly flat chest, (flat chest:1.9)"
    elif bust == "豊満": bust_p = "large breasts, deep cleavage"

    # Userロールに指示を全て込める（400エラー対策）
    combined_instruction = (
        "As a prompt engineer, create one high-quality English paragraph for image generation. "
        f"Base Character: {char_desc}. "
        f"Setting/Clothing: {context_info}. "
        f"Style details: {level_desc}, {bust_p}, {', '.join(extra)}. "
        "Output ONLY the paragraph, no preamble."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": combined_instruction}]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=40)
        return response.json()["choices"][0]["message"]["content"].strip()
    except: return "Generation Error"

# --- UI構築 ---
st.title("Higgsfield Generator v5.5")

# 1. 女性の特徴
st.markdown("### 👩 1. 女性の身体的特徴")
char_input = st.text_area("髪型、顔、体型など（固定）", value=st.session_state.char_description, key="c_area")
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
        with st.spinner("AIが考案中..."):
            try:
                # 400エラーを防ぐため最もシンプルな構造
                r = requests.post(GROK_API_URL, 
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": TEXT_MODEL, 
                        "messages": [{"role": "user", "content": "Suggest a scene like '場所：〇〇、服装：××、状態：△△'. Japanese, 1 line only. No body features."}],
                        "temperature": 0.8
                    }, timeout=30
                )
                if r.status_code == 200:
                    new_scene = r.json()["choices"][0]["message"]["content"].strip()
                    st.session_state.scene_description = new_scene
                    save_app_data(st.session_state.char_description, new_scene)
                    st.rerun()
                else:
                    st.error(f"AI提案失敗: {r.status_code} - {r.text}")
            except Exception as e:
                st.error(f"接続エラー: {e}")
    
    scene_input = st.text_area("AI提案のシチュエーション", value=st.session_state.scene_description, key="s_area")
    if scene_input != st.session_state.scene_description:
        st.session_state.scene_description = scene_input
        save_app_data(st.session_state.char_description, scene_input)

# 3. オプション
st.markdown("---")
sex_level = st.radio("露出レベル", options=[1, 2, 3, 4, 5], 
                     format_func=lambda x: f"レベル {x}", index=2, horizontal=True)
bust_type = st.radio("胸のサイズ", options=["貧乳", "普通", "豊満"], index=1, horizontal=True)
c1, c2 = st.columns(2)
tight = c1.checkbox("タイトな服装")
nipple = c2.checkbox("乳首ぽち")

# --- 生成実行 ---
if st.button("🚀 プロンプト生成", type="primary", use_container_width=True):
    # 画像があれば画像優先、なければテキスト
    process_items = [{"type": "image", "file": i} for i in uploaded_images] if uploaded_images else [{"type": "text", "content": st.session_state.scene_description}]
    
    for item in process_items:
        if item["type"] == "image":
            with st.spinner(f"画像を解析中..."):
                ctx = analyze_image_with_grok(item["file"].getvalue())
        else:
            ctx = item["content"]
        
        with st.spinner("プロンプトを合成中..."):
            final = generate_final_prompt(st.session_state.char_description, ctx, sex_level, tight, nipple, bust_type)
        
        # 最終的な貧乳補正
        if bust_type == "貧乳":
            final += ", (flat chest:1.9), (tiny breasts:1.5)"
        
        st.code(final)
