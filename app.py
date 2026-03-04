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

# --- AI提案：複数一括生成関数 ---
def generate_multiple_scenes(count):
    buffer_count = count + 2
    with st.spinner(f"裏垢女子の日常を{count}パターン妄想中..."):
        prompt = [{
            "role": "user", 
            "content": (
                f"日本のSNS（X/Twitter）の『裏垢女子』が投稿しそうな、あざとくてセクシーな自撮りシチュエーションを【{buffer_count}個】考えてください。\n"
                "場所、服装、状態（ライティング、ポーズ、背景、質感、生々しさ）を、非常に詳しく描写すること。\n"
                "各シチュエーションは必ず1行にまとめ、形式：'場所：〇〇、服装：××、状態：△△' を厳守。\n"
                "※説明や挨拶、番号、空行は一切不要。必ず『場所：』から書き始めること。"
            )
        }]
        res = call_grok_api(prompt)
        if "Error" not in res:
            all_lines = [s.strip() for s in res.split('\n') if s.strip()]
            valid_scenes = [line for line in all_lines if "場所：" in line]
            st.session_state.scenes_list = valid_scenes[:count]

# --- UI ---
st.title("Higgsfield Gen v8.2 (Exposure Fix)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --": st.session_state.char_description = sel_h

st.session_state.char_description = st.text_area("身体的特徴", value=st.session_state.char_description)

st.markdown("---")

st.markdown("### 🎬 2. シチュエーション設定")
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
        st.markdown(f"**現在の候補: {len(st.session_state.scenes_list)} 件**")
        new_scenes = []
        for i, scene in enumerate(st.session_state.scenes_list):
            s_val = st.text_area(f"シチュエーション {i+1}", value=scene, key=f"txt_{i}_{hash(scene)}")
            new_scenes.append(s_val)
        st.session_state.scenes_list = new_scenes
        for s in st.session_state.scenes_list:
            if s.strip():
                targets.append({"type": "text", "content": s})

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

# --- 露出度指示の明確化 ---
sex_map = {
    1: "fully clothed, modest, no skin exposure, conservative style",
    2: "casual everyday outfit, minimal skin exposure",
    3: "sexy, suggestive, attractive outfit",
    4: "revealing, erotic, high skin exposure, provocative",
    5: "completely naked, full nudity, no clothes"
}

# --- 生成実行 ---
if st.button("🚀 全てのプロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像アップロードか、AI生成を行ってください。")
        st.stop()
        
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        with st.container():
            if item["type"] == "image":
                with st.spinner(f"画像 {i+1} 解析中..."):
                    b64 = base64.b64encode(item['content'].getvalue()).decode('utf-8')
                    res_context = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe this girl's location, outfit, and pose in detail for an image prompt."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
                    context = res_context
                    display_img = item['content'].getvalue()
            else:
                context = item["content"]
                display_img = None

            # プロンプト合成
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

                # AIへの指示：露出レベルを絶対守らせる
                final_instruction = (
                    f"Subject: {st.session_state.char_description}, "
                    f"Context: {context}, "
                    f"Clothing/Exposure Level: {sex_text}, " # ここで露出度を強く指定
                    f"Body: {bust_ins}, Extras: {', '.join(extras)}, "
                    f"Quality: {quality}. "
                    "Output a long, detailed photorealistic English prompt. "
                    f"Note: Strictly follow the Clothing/Exposure Level '{sex_text}'."
                )

                final_p = call_grok_api([{"role":"user","content":final_instruction}])
                
                # 強制強調タグの追加（露出度に応じた補正）
                if sex_level == 5: final_p += ", (completely naked:1.5), (nude:1.5)"
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
