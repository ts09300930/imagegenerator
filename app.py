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

SAVE_FILE = os.path.join(DATA_DIR, "app_state_v3.csv")

# --- データの読み込み・保存関数 ---
def save_app_data(char_desc, scene_desc):
    pd.DataFrame({
        "char_desc": [char_desc],
        "scene_desc": [scene_desc]
    }).to_csv(SAVE_FILE, index=False)

def load_app_data():
    char, scene = "", ""
    if os.path.exists(SAVE_FILE):
        try:
            df = pd.read_csv(SAVE_FILE)
            char = df["char_desc"][0]
            scene = df["scene_desc"][0]
        except: pass
    return char, scene

# Grok APIキー設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキーを入力してください", type="password")

if not API_KEY:
    st.error("APIキーが設定されていません。サイドバーから入力してください。")
    st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-4" 

# 起動時のデータ復元
init_char, init_scene = load_app_data()

if 'prompt_history' not in st.session_state:
    st.session_state.prompt_history = []
if 'char_description' not in st.session_state:
    st.session_state.char_description = init_char
if 'scene_description' not in st.session_state:
    st.session_state.scene_description = init_scene

# --- AIロジック ---
def analyze_image_with_grok(image_data):
    """画像からシチュエーション（場所・服装・行動）のみを抽出"""
    base64_image = base64.b64encode(image_data).decode('utf-8')
    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe ONLY the environment, clothing, and action in this image in precise English. Do not describe the person's face or body type. Paragraph only."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"].strip() if response.status_code == 200 else ""

def generate_final_prompt(char_desc, context_info, sex_level, tight, nipple, bust):
    """女性の特徴 + (画像解析 or AIシチュエーション) を合成"""
    level_info = {
        1: "fully clothed, modest", 2: "slight skin exposure", 
        3: "visible cleavage, sexy", 4: "bikini or lingerie", 5: "nearly nude"
    }[sex_level]

    opts = []
    if tight: opts.append("extremely tight-fitting clothing")
    if nipple: opts.append("visible nipple outlines through fabric")
    
    bust_prompt = ""
    if bust == "貧乳": bust_prompt = "strictly flat chest, no breast volume"
    elif bust == "豊満": bust_prompt = "large voluptuous breasts, deep cleavage"

    system_msg = (
        "You are an expert prompt engineer. Combine the physical features and the provided scene/action info into one seamless English paragraph. "
        "The scene/action info provided is the absolute priority for location and clothing. "
        "Output ONLY the paragraph, no extra text."
    )
    user_msg = f"Physical Features: {char_desc}\nScene/Action Context: {context_info}\nSexiness: {level_info}\nBust: {bust_prompt}\nExtras: {', '.join(opts)}"

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"].strip() if response.status_code == 200 else "Error"

# --- UI ---
st.title("Higgsfield Generator v5.1")

# --- 1. 女性の特徴（固定エリア） ---
st.markdown("### 👩 1. 女性の身体的特徴（固定）")
char_input = st.text_area("髪型、体型、顔の特徴などを入力（自動保存されます）", 
                         value=st.session_state.char_description, 
                         key="char_area", height=80)
if char_input != st.session_state.char_description:
    st.session_state.char_description = char_input
    save_app_data(char_input, st.session_state.scene_description)

st.markdown("---")

# --- 2. どちらのシチュエーションを使うか ---
st.markdown("### 🎬 2. シチュエーション（画像 or AI提案）")
tab1, tab2 = st.tabs(["📷 画像から取得", "🎲 AIに丸投げ"])

with tab1:
    uploaded_images = st.file_uploader("参考画像をアップロード（複数可）", type=["jpg", "png", "heic"], accept_multiple_files=True)
    if uploaded_images:
        st.info("※画像がある場合、下のシチュエーション入力欄は無視され、画像の内容が優先されます。")

with tab2:
    if st.button("🎲 AIに新しいシチュエーションを提案させる"):
        with st.spinner("シチュエーションを考案中..."):
            r = requests.post(GROK_API_URL, 
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROK_MODEL, 
                    "messages": [
                        {"role": "system", "content": "具体的なフェティッシュな状況（場所・服装・行動）を1つ提案してください。"},
                        {"role": "user", "content": "「場所：〇〇、服装：××、状態：△△」の形式で1行だけで出力。身体的特徴は一切含めない。"}
                    ],
                    "temperature": 1.0
                }
            )
            if r.status_code == 200:
                st.session_state.scene_description = r.json()["choices"][0]["message"]["content"].strip()
                save_app_data(st.session_state.char_description, st.session_state.scene_description)
                st.rerun()
    
    scene_input = st.text_area("AI提案のシチュエーション（編集可）", 
                              value=st.session_state.scene_description, 
                              key="scene_area", height=80)
    if scene_input != st.session_state.scene_description:
        st.session_state.scene_description = scene_input
        save_app_data(st.session_state.char_description, scene_input)

# --- 共通オプション ---
st.markdown("---")
col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    sex_level = st.radio("露出度", [1, 2, 3, 4, 5], index=2, horizontal=True)
    bust_type = st.radio("胸のサイズ", ["貧乳", "普通", "豊満"], index=1, horizontal=True)
with col_opt2:
    tight = st.checkbox("タイトな服装")
    nipple = st.checkbox("乳首ぽち")

# --- 生成実行 ---
if st.button("🚀 プロンプト生成", type="primary"):
    # 画像があれば画像ループ、なければAIシチュエーションで1回生成
    context_list = []
    if uploaded_images:
        for img in uploaded_images:
            img.seek(0)
            pil_img = Image.open(img).convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG")
            with st.spinner(f"{img.name} を解析中..."):
                analysis = analyze_image_with_grok(buf.getvalue())
                context_list.append((analysis, buf.getvalue()))
    else:
        context_list.append((st.session_state.scene_description, None))

    for ctx_text, img_bytes in context_list:
        with st.expander("生成結果", expanded=True):
            if img_bytes:
                st.image(img_bytes, width=200)
            
            with st.spinner("プロンプト合成中..."):
                final = generate_final_prompt(
                    st.session_state.char_description, 
                    ctx_text, 
                    sex_level, tight, nipple, bust_type
                )
            
            st.code(final)
            if img_bytes:
                st.session_state.prompt_history.append((final, img_bytes))

# --- 履歴 ---
if st.session_state.prompt_history:
    st.markdown("### 生成履歴（画像ありのみ）")
    for p, im in reversed(st.session_state.prompt_history[-5:]):
        with st.expander("履歴"):
            st.image(im, width=150)
            st.code(p)
