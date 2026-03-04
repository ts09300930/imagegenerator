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
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = []
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- AI提案 ---
def generate_multiple_scenes(count):
    buffer_count = count + 2
    with st.spinner(f"シチュエーション生成中..."):
        prompt = [{
            "role": "user", 
            "content": (
                f"日本の裏垢女子風の自撮りシチュエーションを【{buffer_count}個】考えて。\n"
                "形式：'場所：〇〇、服装：××、状態：△△' を厳守。1行ずつ出力。"
            )
        }]
        res = call_grok_api(prompt)
        if "Error" not in res:
            all_lines = [s.strip() for s in res.split('\n') if s.strip()]
            valid_scenes = [line for line in all_lines if "場所：" in line]
            st.session_state.scenes_list = valid_scenes[:count]

# --- UI ---
st.title("Higgsfield Gen v8.4 (Strict Independence)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴 (これが画像解析より最優先されます)", value=st.session_state.char_description)

st.markdown("---")
st.markdown("### 🎬 2. シチューション設定")
mode = st.radio("入力モードを選択", ["📷 画像解析（アップロード）", "🎲 AI自動生成（テキスト）"], horizontal=True)

targets = []
if mode == "📷 画像解析（アップロード）":
    uploaded_images = st.file_uploader("画像アップロード", type=["jpg","png","heic"], accept_multiple_files=True)
    if uploaded_images:
        for f in uploaded_images:
            targets.append({"type": "image", "content": f})
else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=0)
    if c2.button(f"🎲 {gen_count}件を自動生成", use_container_width=True):
        generate_multiple_scenes(gen_count)
    if st.session_state.scenes_list:
        new_scenes = []
        for i, scene in enumerate(st.session_state.scenes_list):
            s_val = st.text_area(f"案 {i+1}", value=scene, key=f"txt_{i}_{hash(scene)}")
            new_scenes.append(s_val)
        st.session_state.scenes_list = new_scenes
        for s in st.session_state.scenes_list:
            if s.strip(): targets.append({"type": "text", "content": s})

st.markdown("---")
st.markdown("### ⚙️ 共通オプション")
col1, col2 = st.columns(2)
sex_level = col1.select_slider("露出レベル (テキスト生成時のみ適用)", options=[1,2,3,4,5], value=3)
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
    if not targets:
        st.warning("画像かテキストを入力してください。")
        st.stop()
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        # 各ループでコンテキストを完全にリセット
        current_image_context = "" 
        display_img = None
        is_image_mode = False

        with st.container():
            if item["type"] == "image":
                is_image_mode = True
                display_img = item['content'].getvalue()
                with st.spinner(f"画像 {i+1} を単独解析中..."):
                    b64 = base64.b64encode(display_img).decode('utf-8')
                    # 他の画像の影響を受けないよう、この画像だけの情報を抽出
                    analysis_prompt = (
                        "Describe THIS specific image ONLY. Do not refer to any previous images.\n"
                        "1. BACKGROUND: Describe the exact setting (e.g., stone bench, concrete wall, park greenery).\n"
                        "2. OUTFIT: Exact details of the clothes in THIS image (e.g., blue stripes, specific fabric).\n"
                        "3. ATMOSPHERE: Lighting and camera angle of THIS image."
                    )
                    # messagesを毎回新しく作成して、前の画像履歴が混ざらないようにする
                    current_image_context = call_grok_api([{"role":"user","content":[{"type":"text","text":analysis_prompt},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
            else:
                current_image_context = item["content"]
                is_image_mode = False

            with st.spinner(f"プロンプト {i+1} を独立合成中..."):
                quality = "Masterpiece, 8k UHD, photorealistic, cinematic lighting, raw smartphone photo style."
                
                extras = []
                if tight_clothing: extras.append("extremely tight clothing")
                if nipple_poke: extras.append("visible nipple outlines")
                if mask_on: extras.append("white surgical mask")
                if iphone_selfie: extras.append("holding iPhone, mirror selfie")
                if face_hidden: extras.append("face hidden, focused on body")
                bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")

                if is_image_mode:
                    # 身体的特徴(Subject)を最優先しつつ、背景・服装を「この画像のものだけ」に限定
                    instruction_content = (
                        f"Create a prompt based SOLELY on the following details. Discard any previous image information.\n"
                        f"Target Person Features (HIGHEST PRIORITY): {st.session_state.char_description}, {bust_ins}.\n"
                        f"Mandatory Background & Outfit from THIS image: {current_image_context}.\n"
                        f"Additional Tags: {', '.join(extras)}, Quality: {quality}.\n"
                        "Constraint: The output must strictly combine the 'Target Person Features' with the 'Mandatory Background & Outfit' of THIS image only."
                    )
                else:
                    instruction_content = (
                        f"Subject: {st.session_state.char_description}, Context: {current_image_context}, "
                        f"Style: {sex_map[sex_level]}, Body: {bust_ins}, Extras: {', '.join(extras)}, Quality: {quality}."
                    )

                # API呼び出しも毎回「独立した1回きりの命令」として扱う
                final_p = call_grok_api([{"role":"user","content": f"{instruction_content} Output ONLY the English prompt starting with 'A photorealistic shot of...'"}])
                
                # 強制補正タグ
                if not is_image_mode:
                    if sex_level == 5: final_p += ", (nude:1.5)"
                    if sex_level == 1: final_p += ", (fully clothed:1.5)"
                if bust_type == "貧乳": final_p += ", (flat chest:1.9)"
                if nipple_poke: final_p += ", (nipples poking through clothing:1.4)"
                
                st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
                st.success(f"Result {i+1}")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                st.text_area(f"Copy {i+1}", value=final_p, height=100, key=f"copy_{i}_{random.randint(0,99999)}")

# --- 履歴 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 生成履歴（最新10件）")
    for idx, hist in enumerate(reversed(st.session_state.prompt_history[-10:])):
        with st.expander(f"履歴 {len(st.session_state.prompt_history) - idx}"):
            if hist["image"]: st.image(hist["image"], width=150)
            st.text_area("プロンプト", value=hist["prompt"], height=100, key=f"hist_txt_{idx}")
