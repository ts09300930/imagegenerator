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

# --- 設定 ---
# 2026年現在の利用可能モデル候補（504対策で複数試行するように実装）
MODEL_CANDIDATES = ["grok-4", "grok-2-vision-1212", "grok-vision-beta"]
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

# --- 504/404エラー対策：リトライ付きAPIコール ---
def call_grok_api(messages):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    # モデル候補を順に試す（504対策）
    for model_name in MODEL_CANDIDATES:
        payload = {
            "model": model_name, 
            "messages": messages, 
            "max_tokens": 1000, 
            "temperature": 0.7
        }
        try:
            res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=90)
            
            if res.status_code == 200:
                json_res = res.json()
                return json_res["choices"][0]["message"]["content"].strip()
            
            # 504(Timeout)や404(Not Found)なら次のモデルへ
            if res.status_code in [504, 404, 503]:
                continue
            
            # それ以外のエラー（400等）は詳細を返す
            try:
                err_msg = res.json().get('error', {}).get('message', res.text)
                return f"API_ERROR_{res.status_code}: {err_msg}"
            except:
                return f"API_ERROR_{res.status_code}: Server returned non-JSON"

        except requests.exceptions.Timeout:
            continue # 次のモデルへ
        except Exception as e:
            return f"CONNECTION_ERROR: {str(e)}"
    
    return "SERVER_BUSY: 全てのモデルが応答しません。xAIサーバーの過負荷です。"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 状態初期化 ---
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = []

# --- UI ---
st.title("Higgsfield Gen v9.4 (Server Error Fix)")

# 1. 身体的特徴
st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴から選択", ["-- 履歴なし --"] + char_h)
if sel_h != "-- 履歴なし --": st.session_state.char_description = sel_h
char_desc = st.text_area("身体的特徴 (例: 黒髪ロング、Gカップ、眼鏡)", value=st.session_state.get('char_description', ""))
st.session_state.char_description = char_desc

st.markdown("---")

# 2. シチュエーション設定 (デグレ修正版)
st.markdown("### 🎬 2. シチュエーション設定")
mode = st.radio("入力モードを選択", ["📷 画像解析", "🎲 AI自動生成"], horizontal=True)

targets = []
if mode == "📷 画像解析":
    uploaded_images = st.file_uploader("画像をアップロード", type=["jpg","png","heic"], accept_multiple_files=True)
    if uploaded_images:
        for f in uploaded_images:
            targets.append({"type": "image", "content": f})
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button(f"🎲 {gen_count}件を自動提案"):
        # 過去のロジックそのまま
        res = call_grok_api([{"role": "user", "content": f"日本のSNS自撮り風。'場所：、服装：、状態：'の形式で{gen_count}件考えて。"}] )
        if "ERROR" not in res and "SERVER_BUSY" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所" in s][:gen_count]
    
    for i, scene in enumerate(st.session_state.scenes_list):
        st.session_state.scenes_list[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
    for s in st.session_state.scenes_list: targets.append({"type": "text", "content": s})

st.markdown("---")

# 3. オプション設定 (動いていた頃の強力な指示を継承)
st.markdown("### ⚙️ 3. オプション設定")
col_opt1, col_opt2 = st.columns(2)
sex_level = col_opt1.select_slider("露出レベル", options=[1, 2, 3, 4, 5], value=3)
bust_type = col_opt2.radio("胸のサイズ", ["貧乳", "普通", "豊満"], index=1, horizontal=True)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装")
nipple_poke = cb.checkbox("乳首ぽち")
mask_on = cb.checkbox("白マスク着用")

# --- 生成実行 ---
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像またはシチュエーション案が必要です。")
        st.stop()
    
    save_char_history(st.session_state.char_description)
    
    for idx, item in enumerate(targets):
        with st.container():
            current_ctx = ""
            display_img = None
            
            if item["type"] == "image":
                img_b64 = process_image(item['content'])
                display_img = item['content'].getvalue()
                with st.spinner(f"解析中..."):
                    current_ctx = call_grok_api([
                        {"role": "user", "content": [
                            {"type": "text", "text": "Describe this image context for a prompt paragraph."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]}
                    ])
            else:
                current_ctx = item["content"]

            if "ERROR" in str(current_ctx) or "SERVER_BUSY" in str(current_ctx):
                st.error(f"❌ 解析失敗: {current_ctx}")
                continue

            with st.spinner(f"合成中..."):
                # 動いていた頃のウェイト・指示ロジックを復元
                bust_ins = ""
                if bust_type == "貧乳":
                    bust_ins = "completely flat chest, no volume, bony ribcage, (flat chest:1.9)"
                elif bust_type == "豊満":
                    bust_ins = "large ample bust, voluptuous curves, prominent cleavage"

                adds = []
                if tight_clothing: adds.append("skin-tight, body-hugging fabric")
                if nipple_poke: adds.append("visible nipples poking through fabric")
                if mask_on: adds.append("wearing a white surgical mask")

                system_ins = (
                    f"Expert Prompt Engineer mode. Sexiness level: {sex_level}. "
                    f"Mandatory Body: {bust_ins}. {', '.join(adds)}. "
                    "Output ONLY the final English paragraph starting with 'A photorealistic shot of...'"
                )
                
                final_p = call_grok_api([
                    {"role": "system", "content": system_ins},
                    {"role": "user", "content": f"Context: {current_ctx}\nFeatures: {st.session_state.char_description}"}
                ])

                if "ERROR" in final_p:
                    st.error(f"❌ 合成失敗: {final_p}")
                    continue

                st.session_state.prompt_history.append((final_p, display_img))
                st.success(f"✅ Result {idx+1}")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                html(f"<button onclick=\"navigator.clipboard.writeText(`{final_p.replace('`', '\\`')}`)\">コピー</button>")
