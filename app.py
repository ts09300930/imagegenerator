import streamlit as st
import requests
import os
import base64
import pandas as pd
from pillow_heif import register_heif_opener
import io
from PIL import Image
import random
from streamlit.components.v1 import html

# HEICサポート
register_heif_opener()

# --- 設定（動いていた頃の知見：grok-4 を使用） ---
GROK_MODEL = "grok-4" 
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

# Grok API Key
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキー", type="password")
    if not API_KEY: st.stop()

# --- コア関数（デグレ防止・エラーガード徹底） ---
def call_grok_api(messages):
    payload = {
        "model": GROK_MODEL, 
        "messages": messages, 
        "max_tokens": 1000, 
        "temperature": 0.7
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
        
        # 1. JSON解析試行
        try:
            json_res = res.json()
        except:
            return f"SYSTEM_ERROR_{res.status_code}: Non-JSON Response"

        # 2. 成功判定
        if res.status_code == 200:
            if isinstance(json_res, dict) and "choices" in json_res:
                return json_res["choices"][0]["message"]["content"].strip()
            return "ERROR: Unexpected API Response Structure"

        # 3. エラー時（辞書/文字列判定を厳密に行い 'get' エラーを完全封印）
        msg = "Unknown Error"
        if isinstance(json_res, dict):
            # errorキーが辞書であることを確認して取得
            err_obj = json_res.get('error')
            if isinstance(err_obj, dict):
                msg = err_obj.get('message', str(json_res))
            else:
                msg = str(err_obj) if err_obj else str(json_res)
        else:
            msg = str(json_res)
            
        return f"API_ERROR_{res.status_code}: {msg}"

    except Exception as e:
        return f"CONNECTION_ERROR: {str(e)}"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 状態初期化 ---
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []
if 'char_description' not in st.session_state: st.session_state.char_description = ""

# --- UI ---
st.title("Higgsfield Gen v9.2 (Grok-4 Verified)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴から選択", ["-- 履歴なし --"] + char_h)
if sel_h != "-- 履歴なし --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴 (Gカップ、黒髪ロングなど)", value=st.session_state.char_description)

st.markdown("---")
st.markdown("### 🎬 2. 露出・体型設定 (過去のロジック継承)")
col_opt1, col_opt2 = st.columns(2)
sex_level = col_opt1.select_slider("露出レベル", options=[1, 2, 3, 4, 5], value=3)
bust_type = col_opt2.radio("胸のサイズ", ["貧乳", "普通", "豊満"], index=1, horizontal=True)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装")
nipple_poke = cb.checkbox("乳首ぽち")
mask_on = cc.checkbox("白いマスク")

cd, ce, cf = st.columns(3)
iphone_selfie = cd.checkbox("iPhone鏡自撮り")
face_hidden = ce.checkbox("顔を隠す")
angle_type = st.selectbox("アングル", ["標準", "俯瞰 (from above)", "アオリ (from below)", "横から (from side)"])

st.markdown("---")
uploaded_images = st.file_uploader("画像をアップロード", type=["jpg","png","heic"], accept_multiple_files=True)

if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not uploaded_images:
        st.warning("画像をアップロードしてください。")
        st.stop()
    
    save_char_history(st.session_state.char_description)
    
    for idx, img_file in enumerate(uploaded_images):
        with st.container():
            # 1. 画像解析 (analyze_image_with_grok の役割)
            img_b64 = process_image(img_file)
            with st.spinner(f"画像 {idx+1} 解析中..."):
                base_prompt = call_grok_api([
                    {"role": "user", "content": [
                        {"type": "text", "text": "Describe this image in precise English detail for a diffusion prompt. Paragraph format."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]}
                ])
            
            if "ERROR" in base_prompt:
                st.error(f"❌ 解析失敗: {base_prompt}")
                continue

            # 2. 合成 (merge_description_and_level の役割)
            with st.spinner(f"プロンプト {idx+1} 合成中..."):
                level_desc = {
                    1: "fully clothed, modest outfit, no cleavage",
                    2: "slight skin exposure, minimal cleavage",
                    3: "visible cleavage, sexy outfit",
                    4: "bikini or lingerie, highly revealing",
                    5: "nearly nude, minimal coverage"
                }[sex_level]

                # 過去コードの強力な指示を継承
                strong_adds = []
                if tight_clothing: strong_adds.append("extremely tight-fitting, skin-tight fabric")
                if nipple_poke: strong_adds.append("visible nipple outlines poking through fabric")
                if mask_on: strong_adds.append("wearing a white surgical mask")
                if iphone_selfie: strong_adds.append("holding iPhone, mirror selfie pose")
                if face_hidden: strong_adds.append("face hidden, focus on body")
                if angle_type != "標準": strong_adds.append(angle_type.split("(")[-1].replace(")", ""))

                bust_ins = ""
                if bust_type == "貧乳":
                    bust_ins = "extremely flat chest, no volume, petite ribcage, (flat chest:1.9)"
                elif bust_type == "豊満":
                    bust_ins = "ample bust, voluptuous curves, large breasts"

                system_ins = (
                    "You are an expert prompt engineer. Merge features into the scene. "
                    f"MANDATORY: {level_desc}, {bust_ins}, {', '.join(strong_adds)}. "
                    "Output ONLY the final English paragraph. No preamble."
                )
                
                final_p = call_grok_api([
                    {"role": "system", "content": system_ins},
                    {"role": "user", "content": f"Base: {base_prompt}\nSubject: {st.session_state.char_description}"}
                ])

                if "ERROR" in final_p:
                    st.error(f"❌ 合成失敗: {final_p}")
                    continue

                # 3. 結果表示・履歴保存
                st.session_state.prompt_history.append((final_p, img_file.getvalue()))
                st.success(f"✅ Result {idx+1}")
                st.image(img_file, width=250)
                st.code(final_p)
                st.text_area(f"Copy {idx+1}", value=final_p, key=f"cp_{idx}_{random.randint(0,999)}")

# 履歴（動いていた頃のコピーボタン等のUIを維持）
if st.session_state.prompt_history:
    st.markdown("### 📜 生成履歴")
    for i, (h_p, h_img) in enumerate(reversed(st.session_state.prompt_history[-5:])):
        with st.expander(f"履歴 {i+1}"):
            st.image(h_img, width=200)
            st.code(h_p)
            html(f"<button onclick=\"navigator.clipboard.writeText(`{h_p.replace('`', '\\`')}`)\">プロンプトをコピー</button>")
