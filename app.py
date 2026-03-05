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
# サーバーが重い時、順に試すモデルリスト
MODEL_PRIORITY = ["grok-4", "grok-2-vision-1212", "grok-vision-beta"]
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

# --- サーバー不安定対策：自動切り替えリトライ機能 ---
def call_grok_api(messages):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    last_error = ""
    for model_name in MODEL_PRIORITY:
        payload = {
            "model": model_name, 
            "messages": messages, 
            "max_tokens": 1000, 
            "temperature": 0.7
        }
        try:
            # タイムアウトを90秒に延長
            res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=90)
            
            # 正常応答
            if res.status_code == 200:
                try:
                    return res.json()["choices"][0]["message"]["content"].strip()
                except:
                    continue # JSONパース失敗なら次へ

            # サーバーエラー(504, 503等)なら次のモデルを試す
            if res.status_code >= 500 or res.status_code == 404:
                last_error = f"Model {model_name} failed ({res.status_code})"
                continue
            
            # 400系エラー（キーの間違いなど）はそのまま表示
            try:
                msg = res.json().get('error', {}).get('message', res.text)
                return f"API_ERROR_{res.status_code}: {msg}"
            except:
                return f"API_ERROR_{res.status_code}: {res.text[:100]}"

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            last_error = f"Timeout on {model_name}"
            continue
            
    return f"❌ サーバー混雑中: 全てのモデルが応答しませんでした。少し時間をおいてください。({last_error})"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB': img = img.convert('RGB')
    # サーバー負荷軽減のため、少し小さめにリサイズ
    img.thumbnail((800, 800))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- UI ---
st.title("Higgsfield Gen v9.5 (不安定対策版)")

# 1. 身体的特徴
st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("履歴から選択", ["-- 履歴なし --"] + char_h)
if sel_h != "-- 履歴なし --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴", value=st.session_state.get('char_description', ""))

st.markdown("---")

# 2. シチュエーション設定（AI生成機能復活）
st.markdown("### 🎬 2. 設定モード")
mode = st.radio("入力モード", ["📷 画像解析", "🎲 AI自動生成"], horizontal=True)

targets = []
if mode == "📷 画像解析":
    uploaded_images = st.file_uploader("画像アップロード", type=["jpg","png","heic"], accept_multiple_files=True)
    if uploaded_images:
        for f in uploaded_images:
            targets.append({"type": "image", "content": f})
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button(f"🎲 {gen_count}件を自動生成"):
        res = call_grok_api([{"role": "user", "content": f"日本のSNS自撮り。場所、服装、状態の3点で{gen_count}件案を出して。"}] )
        if "❌" not in res and "ERROR" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所" in s][:gen_count]
    
    for i, scene in enumerate(st.session_state.get('scenes_list', [])):
        st.session_state.scenes_list[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
    for s in st.session_state.get('scenes_list', []):
        targets.append({"type": "text", "content": s})

st.markdown("---")

# 3. オプション設定 (ロジック維持)
st.markdown("### ⚙️ 3. オプション")
col1, col2 = st.columns(2)
sex_level = col1.select_slider("露出レベル", options=[1, 2, 3, 4, 5], value=3)
bust_type = col2.radio("胸のサイズ", ["貧乳", "普通", "豊満"], index=1, horizontal=True)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装")
nipple_poke = cb.checkbox("乳首ぽち")
mask_on = cc.checkbox("白いマスク")

# 生成ボタン
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像またはテキストを入力してください。")
        st.stop()
    
    save_char_history(st.session_state.char_description)
    
    for idx, item in enumerate(targets):
        with st.container():
            current_ctx = ""
            display_img = None
            
            if item["type"] == "image":
                img_b64 = process_image(item['content'])
                display_img = item['content'].getvalue()
                with st.spinner(f"画像 {idx+1} 解析中..."):
                    current_ctx = call_grok_api([
                        {"role": "user", "content": [
                            {"type": "text", "text": "Describe the setting, outfit, and background in one paragraph."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]}
                    ])
            else:
                current_ctx = item["content"]

            if "❌" in str(current_ctx):
                st.error(current_ctx)
                continue

            with st.spinner(f"最終プロンプト合成中..."):
                # 過去の強力な指示ロジックを反映
                bust_ins = "(flat chest:1.9), petite bony torso" if bust_type == "貧乳" else ("large ample bust, voluptuous curves" if bust_type == "豊満" else "")
                
                adds = []
                if tight_clothing: adds.append("extremely tight-fitting")
                if nipple_poke: adds.append("visible nipples poking through fabric")
                if mask_on: adds.append("wearing a white surgical mask")

                final_p = call_grok_api([
                    {"role": "system", "content": f"High-end Prompt Engineer. Sexiness level: {sex_level}. {bust_ins}. {', '.join(adds)}. Output English paragraph only."},
                    {"role": "user", "content": f"Scene: {current_ctx}\nSubject: {st.session_state.char_description}"}
                ])

                if "❌" in str(final_p):
                    st.error(final_p)
                    continue

                st.success(f"✅ Result {idx+1}")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                html(f"<button onclick=\"navigator.clipboard.writeText(`{final_p.replace('`', '\\`')}`)\">コピー</button>")
