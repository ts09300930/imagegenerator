import streamlit as st
import requests
import os
import base64
import pandas as pd
from pillow_heif import register_heif_opener
import io
from PIL import Image
import random

# HEICサポート
register_heif_opener()

# --- 保存・履歴設定 ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
SAVE_FILE = os.path.join(DATA_DIR, "app_state_v8.csv")
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

# Grok API
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキー", type="password")
    if not API_KEY: st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def call_grok_api(messages):
    payload = {"model": "grok-4", "messages": messages, "max_tokens": 1500, "temperature": 0.9}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
        return res.json()["choices"][0]["message"]["content"].strip() if res.status_code == 200 else f"Error: {res.status_code}"
    except: return "Connection Error"

# --- 状態初期化 ---
if 'char_description' not in st.session_state: st.session_state.char_description = ""
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = [""] # 初期は1件
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- AI提案：複数一括生成関数 ---
def generate_multiple_scenes(count):
    with st.spinner(f"裏垢女子の日常を{count}パターン妄想中..."):
        prompt = [{
            "role": "user", 
            "content": (
                f"日本のSNS（X/Twitter）の『裏垢女子』が投稿しそうな、あざとくてセクシーな自撮りシチュエーションを【{count}個】考えてください。\n"
                "【重要】挨拶や説明は一切不要です。シチュエーションのみを出力してください。\n"
                "1個につき必ず1行で、以下の形式を厳守してください。\n"
                "形式：'場所：〇〇、服装：××、状態：△△'\n"
                "行の先頭に「1.」や「シチュエーション1」などの番号も付けないでください。"
            )
        }]
        res = call_grok_api(prompt)
        if "Error" not in res:
            # 「場所：」が含まれる行だけを抽出
            raw_lines = [s.strip() for s in res.split('\n') if s.strip()]
            valid_scenes = [line for line in raw_lines if "場所：" in line]
            
            # もしAIが番号付きで出してきた場合のために、先頭の「1. 」などを削る処理（念のため）
            import re
            cleaned_scenes = [re.sub(r'^(\d+\.|シチュエーション\d+[:：])\s*', '', s) for s in valid_scenes]
            
            # 指定された個数分をセット（足りない場合は空文字で埋める）
            final_scenes = (cleaned_scenes + [""] * count)[:count]
            st.session_state.scenes_list = final_scenes

# --- UI ---
st.title("Higgsfield Gen v8.0 (Multi-Batch)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --": st.session_state.char_description = sel_h

st.session_state.char_description = st.text_area("身体的特徴", value=st.session_state.char_description)

st.markdown("---")

st.markdown("### 🎬 2. シチュエーション（一括生成）")
mode = st.radio("生成モード", ["📷 画像解析", "🎲 AIに丸投げ（複数可）"], horizontal=True)

if mode == "📷 画像解析":
    uploaded_images = st.file_uploader("画像アップロード", type=["jpg","png","heic"], accept_multiple_files=True)
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button(f"🎲 {gen_count}件のシチュエーションを自動生成", use_container_width=True):
        generate_multiple_scenes(gen_count)
    
    # 動的に生成された入力欄を表示
    st.markdown(f"**現在の候補: {len(st.session_state.scenes_list)} 件**")
    updated_scenes = []
    for i, scene in enumerate(st.session_state.scenes_list):
        new_scene = st.text_area(f"シチュエーション {i+1}", value=scene, key=f"scene_input_{i}")
        updated_scenes.append(new_scene)
    st.session_state.scenes_list = updated_scenes

st.markdown("---")
st.markdown("### ⚙️ 共通オプション")
col1, col2 = st.columns(2)
sex_level = col1.select_slider("露出レベル", options=[1,2,3,4,5], value=3)
bust_type = col2.radio("胸のサイズ", ["貧乳","普通","豊満"], horizontal=True)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装")
nipple_poke = cb.checkbox("乳首ぽち")
mask_on = cc.checkbox("白マスク")

cd, ce, cf = st.columns(3)
iphone_selfie = cd.checkbox("iPhone鏡自撮り")
face_hidden = ce.checkbox("顔を隠す")

sex_map = {1: "modest", 2: "casual", 3: "sexy", 4: "revealing", 5: "extreme"}

# --- 生成実行 ---
if st.button("🚀 全てのプロンプトを一括生成", type="primary", use_container_width=True):
    save_char_history(st.session_state.char_description)
    
    # 処理対象の決定
    if mode == "📷 画像解析" and uploaded_images:
        targets = [{"type": "image", "content": f} for f in uploaded_images]
    else:
        targets = [{"type": "text", "content": s} for s in st.session_state.scenes_list if s.strip()]

    for i, item in enumerate(targets):
        with st.container():
            if item["type"] == "image":
                b64 = base64.b64encode(item['content'].getvalue()).decode('utf-8')
                context = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe details."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
                display_img = item['content'].getvalue()
            else:
                context = item["content"]
                display_img = None

            with st.spinner(f"プロンプト {i+1} 合成中..."):
                quality = "Masterpiece, 8k UHD, photorealistic, cinematic lighting, raw smartphone photo style."
                sex_text = sex_map[sex_level]
                
                extras = []
                if tight_clothing: extras.append("extremely tight clothing")
                if nipple_poke: extras.append("visible nipple outlines")
                if mask_on: extras.append("white surgical mask")
                if iphone_selfie: extras.append("holding iPhone, mirror selfie")
                if face_hidden: extras.append("face hidden, focused on body")
                
                bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")

                # 身体特徴 + シチュエーション + オプションを合成
                final_instruction = (
                    f"Subject: {st.session_state.char_description}, "
                    f"Scene context: {context}, "
                    f"Exposure: {sex_text}, Body: {bust_ins}, "
                    f"Extras: {', '.join(extras)}, "
                    f"Quality: {quality}. "
                    "Create ONE long, detailed photorealistic English prompt starting with 'A photorealistic shot of...'."
                )

                final_p = call_grok_api([{"role":"user","content":final_instruction}])
                if bust_type == "貧乳": final_p += ", (flat chest:1.9)"
                if nipple_poke: final_p += ", (nipples poking through clothing:1.4)"
                
                st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
                st.success(f"Result {i+1}")
                st.code(final_p)
                st.text_area(f"Copy {i+1}", value=final_p, height=100, key=f"copy_{i}_{os.urandom(4).hex()}")

# --- 履歴 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 生成履歴（最新10件）")
    for idx, hist in enumerate(reversed(st.session_state.prompt_history[-10:])):
        with st.expander(f"履歴 {len(st.session_state.prompt_history) - idx}"):
            if hist["image"]: st.image(hist["image"], width=150)
            st.text_area("プロンプト", value=hist["prompt"], height=100, key=f"hist_txt_{idx}")
