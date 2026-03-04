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

# --- 設定（2026年現在の主力モデル ID） ---
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

# --- コア関数（絶対にクラッシュさせないガード付き） ---
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
        try:
            json_res = res.json()
        except:
            return f"SYSTEM_ERROR_{res.status_code}: Non-JSON Response"

        if res.status_code == 200:
            if isinstance(json_res, dict) and "choices" in json_res:
                return json_res["choices"][0]["message"]["content"].strip()
            return "ERROR: Unexpected API Structure"

        # エラーメッセージ抽出（型チェックを徹底して 'str' object... エラーを防止）
        msg = str(json_res)
        if isinstance(json_res, dict):
            err = json_res.get('error')
            if isinstance(err, dict):
                msg = err.get('message', msg)
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
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = []

# --- UI ---
st.title("Higgsfield Gen v9.3 (デグレ修正・完全版)")

# 1. 身体的特徴
st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴から選択", ["-- 履歴なし --"] + char_h)
if sel_h != "-- 履歴なし --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴 (Gカップ、黒髪ロングなど)", value=st.session_state.char_description)

st.markdown("---")

# 2. シチュエーション設定（復活：画像解析 or AI自動生成）
st.markdown("### 🎬 2. シチュエーション設定")
mode = st.radio("入力モードを選択", ["📷 画像解析（アップロード）", "🎲 AI自動生成（テキスト）"], horizontal=True)

targets = []
if mode == "📷 画像解析（アップロード）":
    uploaded_images = st.file_uploader("画像をアップロード", type=["jpg","png","heic"], accept_multiple_files=True)
    if uploaded_images:
        for f in uploaded_images:
            targets.append({"type": "image", "content": f})
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button(f"🎲 {gen_count}件を自動提案", use_container_width=True):
        res = call_grok_api([{"role": "user", "content": f"日本のSNS自撮り風。'場所：、服装：、状態：'の形式で{gen_count}件考えて。"}] )
        if "ERROR" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所" in s][:gen_count]
    
    # 提案されたリストを表示・編集可能にする
    for i, scene in enumerate(st.session_state.scenes_list):
        st.session_state.scenes_list[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
    for s in st.session_state.scenes_list:
        targets.append({"type": "text", "content": s})

st.markdown("---")

# 3. 共通オプション
st.markdown("### ⚙️ 3. オプション設定")
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

# --- 生成実行 ---
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像かシチュエーション案を入力してください。")
        st.stop()
    
    save_char_history(st.session_state.char_description)
    
    for idx, item in enumerate(targets):
        with st.container():
            current_ctx = ""
            display_img = None
            
            # コンテキスト（画像解析 or テキスト）の取得
            if item["type"] == "image":
                img_b64 = process_image(item['content'])
                display_img = item['content'].getvalue()
                with st.spinner(f"画像 {idx+1} 解析中..."):
                    current_ctx = call_grok_api([
                        {"role": "user", "content": [
                            {"type": "text", "text": "Describe this image context for a prompt paragraph."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]}
                    ])
            else:
                current_ctx = item["content"]

            if "ERROR" in str(current_ctx):
                st.error(f"❌ 解析失敗: {current_ctx}")
                continue

            # 最終プロンプトの合成（過去の強力なロジックを反映）
            with st.spinner(f"Result {idx+1} 合成中..."):
                level_desc = {
                    1: "fully clothed, modest outfit, opaque fabric, no skin exposure",
                    2: "minimal skin exposure, form-fitting",
                    3: "visible cleavage, sexy lingerie style elements",
                    4: "bikini or lingerie only, no outer clothing",
                    5: "minimal coverage, nearly nude, extreme skin exposure"
                }[sex_level]

                strong_adds = []
                if tight_clothing: strong_adds.append("extremely tight-fitting, skin-tight, body-hugging")
                if nipple_poke: strong_adds.append("visible nipple outlines poking through thin fabric")
                if mask_on: strong_adds.append("wearing a white surgical mask")
                if iphone_selfie: strong_adds.append("holding iPhone, mirror selfie pose")
                if face_hidden: strong_adds.append("face hidden, focus on body")
                if angle_type != "標準": strong_adds.append(angle_type.split("(")[-1].replace(")", ""))

                bust_ins = ""
                if bust_type == "貧乳":
                    bust_ins = "completely flat chest, no volume, bony torso, (flat chest:1.9)"
                elif bust_type == "豊満":
                    bust_ins = "large ample bust, voluptuous curves, high-volume breasts"

                system_ins = (
                    "You are an expert prompt engineer for Higgsfield. Merge description and scene. "
                    f"Rules: {level_desc}, {bust_ins}, {', '.join(strong_adds)}. "
                    "Output ONLY a single continuous English paragraph. Start with 'A young...'"
                )
                
                final_p = call_grok_api([
                    {"role": "system", "content": system_ins},
                    {"role": "user", "content": f"Base: {current_ctx}\nSubject: {st.session_state.char_description}"}
                ])

                if "ERROR" in final_p:
                    st.error(f"❌ 合成失敗: {final_p}")
                    continue

                # 履歴保存と表示
                st.session_state.prompt_history.append((final_p, display_img))
                st.success(f"✅ Result {idx+1}")
                if display_img: st.image(display_img, width=250)
                st.code(final_p)
                html(f"<button onclick=\"navigator.clipboard.writeText(`{final_p.replace('`', '\\`')}`)\">コピー</button>")

# 履歴表示セクション
if st.session_state.prompt_history:
    st.markdown("### 📜 最新履歴")
    for i, (h_p, h_img) in enumerate(reversed(st.session_state.prompt_history[-5:])):
        with st.expander(f"履歴 {i+1}"):
            if h_img: st.image(h_img, width=150)
            st.code(h_p)
