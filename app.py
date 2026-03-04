import streamlit as st
import requests
import os
import base64
import pandas as pd
from streamlit.components.v1 import html
from PIL import Image
import io

# HEICサポート
from pillow_heif import register_heif_opener
register_heif_opener()

# --- 保存設定 ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

SAVE_FILE = os.path.join(DATA_DIR, "app_state.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "description_history.csv")

# --- データの読み込み・保存関数 ---
def save_app_data(desc, history):
    pd.DataFrame({"desc": [desc]}).to_csv(SAVE_FILE, index=False)
    unique_h = list(dict.fromkeys(history))
    pd.DataFrame({"history": unique_h[-100:]}).to_csv(HISTORY_FILE, index=False)

def load_app_data():
    desc, history = "", []
    if os.path.exists(SAVE_FILE):
        try: desc = pd.read_csv(SAVE_FILE)["desc"][0]
        except: pass
    if os.path.exists(HISTORY_FILE):
        try: history = pd.read_csv(HISTORY_FILE)["history"].tolist()
        except: pass
    return desc, history

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
init_desc, init_h = load_app_data()

if 'prompt_history' not in st.session_state:
    st.session_state.prompt_history = []
if 'current_description' not in st.session_state:
    st.session_state.current_description = init_desc
if 'desc_history' not in st.session_state:
    st.session_state.desc_history = init_h

# --- AIロジック ---
def analyze_image_with_grok(image_data):
    base64_image = base64.b64encode(image_data).decode('utf-8')
    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this image in precise English detail for Higgsfield Diffuse."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    return f"解析失敗: {response.status_code}"

def merge_description_and_level(base_prompt, description, sex_level, tight_clothing, nipple_poke, bust_type):
    level_desc = {1: "fully clothed", 2: "slight skin exposure", 3: "visible cleavage", 4: "bikini/lingerie", 5: "nearly nude"}[sex_level]
    
    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": "Merge into a single English paragraph."},
            {"role": "user", "content": f"Base: {base_prompt}\nExtra: {description}\nSexiness: {level_desc}\nOptions: Tight={tight_clothing}, Nipples={nipple_poke}, Bust={bust_type}"}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"].strip() if response.status_code == 200 else base_prompt

# --- UI ---
st.title("Higgsfield Prompt Generator v4.1")

# --- 設定とランダマイザー ---
st.markdown("### 🛠️ 設定とランダマイザー")
col_rand, col_hist = st.columns([1, 1])

with col_rand:
    if st.button("🎲 AIにシチュエーションを丸投げ"):
        with st.spinner("AI提案中..."):
            try:
                r = requests.post(GROK_API_URL, 
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": GROK_MODEL, 
                        "messages": [{"role": "user", "content": "裏垢女子の画像設定を1つ提案してください。「場所：〇〇、服装：××」の形式で1行だけで。"}]
                    }
                )
                if r.status_code == 200:
                    ai_idea = r.json()["choices"][0]["message"]["content"].strip()
                    st.session_state.current_description = (st.session_state.current_description + f"\n{ai_idea}").strip()
                    save_app_data(st.session_state.current_description, st.session_state.desc_history)
                    st.rerun()
                else:
                    st.error(f"AI提案失敗: {r.status_code}")
            except Exception as e:
                st.error(f"接続失敗: {str(e)}")

with col_hist:
    if st.session_state.desc_history:
        selected_h = st.selectbox("過去の記述を復元", ["-- 選択 --"] + st.session_state.desc_history[::-1])
        if selected_h != "-- 選択 --" and st.button("反映"):
            st.session_state.current_description = selected_h
            save_app_data(selected_h, st.session_state.desc_history)
            st.rerun()

# --- 入力 ---
sex_level = st.radio("露出レベル", options=[1, 2, 3, 4, 5], index=2, horizontal=True)
bust_type = st.radio("胸のサイズ", options=["貧乳", "普通", "豊満"], index=1, horizontal=True)
tight_clothing = st.checkbox("タイトな服装")
nipple_poke = st.checkbox("乳首ぽち")

uploaded_images = st.file_uploader("画像アップロード", type=["jpg", "jpeg", "png", "heic"], accept_multiple_files=True)

description = st.text_area("記述欄", value=st.session_state.current_description, height=100)
if description != st.session_state.current_description:
    st.session_state.current_description = description
    save_app_data(description, st.session_state.desc_history)

if st.button("プロンプト生成", type="primary"):
    if not uploaded_images:
        st.warning("画像をアップロードしてください。")
    else:
        generated_prompts = [] # ここで初期化
        if description and description not in st.session_state.desc_history:
            st.session_state.desc_history.append(description)
            save_app_data(description, st.session_state.desc_history)
            
        for idx, img in enumerate(uploaded_images):
            try:
                img.seek(0)
                pil_image = Image.open(img).convert("RGB")
                img_bytes_io = io.BytesIO()
                pil_image.save(img_bytes_io, format="JPEG")
                
                with st.spinner(f"画像 {idx+1} 解析中..."):
                    base_prompt = analyze_image_with_grok(img_bytes_io.getvalue())
                    final_prompt = merge_description_and_level(base_prompt, description, sex_level, tight_clothing, nipple_poke, bust_type)
                    
                st.text_area(f"プロンプト {idx+1}", value=final_prompt, height=100)
                st.session_state.prompt_history.append((final_prompt, img.getvalue()))
            except Exception as e:
                st.error(f"エラー: {str(e)}")

# --- 履歴 ---
if st.session_state.prompt_history:
    st.markdown("### 生成履歴")
    for i, (p, img_b) in enumerate(reversed(st.session_state.prompt_history[-10:])):
        with st.expander(f"履歴 {i+1}"):
            st.image(img_b, width=200)
            st.code(p)
