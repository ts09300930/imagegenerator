import streamlit as st
import requests
import os
import base64
import pandas as pd
from pillow_heif import register_heif_opener
import io
from PIL import Image

# HEICサポート
register_heif_opener()

# --- 保存・履歴設定 ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

SAVE_FILE = os.path.join(DATA_DIR, "app_state_v6.csv")
CHAR_HISTORY_FILE = os.path.join(DATA_DIR, "char_history.csv")

def save_app_data(char, scene): 
    pd.DataFrame({"char_desc": [char], "scene_desc": [scene]}).to_csv(SAVE_FILE, index=False)

def load_app_data():
    if os.path.exists(SAVE_FILE):
        try:
            df = pd.read_csv(SAVE_FILE)
            return str(df["char_desc"].iloc[0]), str(df["scene_desc"].iloc[0])
        except: pass
    return "", ""

def save_char_history(char):
    if not char.strip(): return
    h = load_char_history()
    if char in h: h.remove(char)
    h.insert(0, char)
    pd.DataFrame({"char_desc": h[:100]}).to_csv(CHAR_HISTORY_FILE, index=False)

def load_char_history():
    if os.path.exists(CHAR_HISTORY_FILE):
        try:
            return pd.read_csv(CHAR_HISTORY_FILE)["char_desc"].dropna().tolist()
        except: return []
    return []

# Grok API設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキー", type="password")
    if not API_KEY: st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def call_grok_api(messages):
    payload = {"model": "grok-4", "messages": messages, "max_tokens": 800}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=40)
        return res.json()["choices"][0]["message"]["content"].strip() if res.status_code == 200 else f"Error: {res.status_code}"
    except: return "Connection Error"

# --- 状態初期化 ---
c_init, s_init = load_app_data()
if 'char_description' not in st.session_state: st.session_state.char_description = c_init
if 'scene_description' not in st.session_state: st.session_state.scene_description = s_init
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- UI構築 ---
st.title("Higgsfield Prompt Gen v6.4 (Final)")

# 1. 特徴入力
st.markdown("### 👩 1. 女性の身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴から選ぶ (最大100件)", ["-- 履歴から選択 --"] + char_h)
if sel_h != "-- 履歴から選択 --":
    st.session_state.char_description = sel_h

char_input = st.text_area("身体的特徴（自動保存）", value=st.session_state.char_description, key="char_area")
if char_input != st.session_state.char_description:
    st.session_state.char_description = char_input
    save_app_data(char_input, st.session_state.scene_description)

st.markdown("---")

# 2. シチュエーション
st.markdown("### 🎬 2. シチュエーション")
mode = st.radio("生成モードを選択", ["📷 画像から取得", "🎲 AI丸投げ・テキスト入力"], horizontal=True)

if mode == "📷 画像から取得":
    uploaded_images = st.file_uploader("参考画像(複数可)", type=["jpg","png","heic"], accept_multiple_files=True)
else:
    if st.button("🎲 AIに新しいシチュエーションを提案させる"):
        with st.spinner("考案中..."):
            res = call_grok_api([{"role":"user","content":"Suggest a sexy Japanese SNS selfie scene. Format: '場所：〇〇、服装：××、状態：△△'. Japanese, 1 line."}])
            if "Error" not in res:
                st.session_state.scene_description = res
                save_app_data(st.session_state.char_description, res)
                st.rerun()

    scene_input = st.text_area("シチュエーション内容", value=st.session_state.scene_description, key="scene_area")
    if scene_input != st.session_state.scene_description:
        st.session_state.scene_description = scene_input
        save_app_data(st.session_state.char_description, scene_input)

# 3. オプション（最初の実装から復活）
st.markdown("---")
st.markdown("### ⚙️ 追加オプション")
c1, c2 = st.columns(2)
sex_level = c1.select_slider("露出レベル", options=[1,2,3,4,5], value=3)
bust_type = c2.radio("胸のサイズ", ["貧乳","普通","豊満"], horizontal=True)

col_a, col_b = st.columns(2)
tight_clothing = col_a.checkbox("タイトな服装（ボディライン強調）", value=False)
nipple_poke = col_b.checkbox("乳首ぽち（布越し）", value=False)

col_d, col_e, col_f = st.columns(3)
mask_on = col_d.checkbox("白マスク着用", value=False)
iphone_selfie = col_e.checkbox("iPhone自撮り構図", value=False)
face_hidden = col_f.checkbox("顔を隠す(匿名)", value=False)

# 露出レベルの英語変換
sex_map = {
    1: "conservative outfit, fully clothed, no skin exposure, modest style",
    2: "casual, slightly revealing, natural look",
    3: "sexy outfit, visible cleavage, attractive skin exposure",
    4: "highly revealing, bikini or lingerie only, maximum skin exposure",
    5: "minimal coverage, borderline nude, extreme sexiness"
}

# --- 生成実行 ---
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    save_char_history(st.session_state.char_description)
    
    tasks = []
    if mode == "📷 画像から取得" and uploaded_images:
        tasks = [{"type": "image", "file": f} for f in uploaded_images]
    else:
        tasks = [{"type": "text", "content": st.session_state.scene_description}]

    for i, item in enumerate(tasks):
        with st.container():
            if item["type"] == "image":
                with st.spinner(f"画像{i+1}を解析中..."):
                    st.image(item['file'], width=200)
                    b64 = base64.b64encode(item['file'].getvalue()).decode('utf-8')
                    context = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe clothing and environment in detail English."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
                    display_img = item['file'].getvalue()
            else:
                context = item["content"]
                display_img = None

            with st.spinner(f"プロンプト{i+1}を合成中..."):
                quality = "Masterpiece, 8k UHD, photorealistic, incredibly detailed skin, visible pores, cinematic lighting, shot on iPhone 15 Pro."
                sex_text = sex_map[sex_level]
                
                # 追加指示の組み立て
                extras = []
                if tight_clothing: extras.append("extremely tight-fitting skin-tight clothing clinging to every curve")
                if nipple_poke: extras.append("visible nipple outlines poking through the fabric")
                if mask_on: extras.append("wearing a white surgical face mask")
                if iphone_selfie: extras.append("holding iPhone, taking a mirror selfie")
                if face_hidden: extras.append("face hidden or cropped, only from mouth down visible")
                
                bust_ins = ""
                if bust_type == "貧乳":
                    bust_ins = "Completely flat chest, bony petite torso, prominent collarbones, no breast volume."
                elif bust_type == "豊満":
                    bust_ins = "Large ample bust, voluptuous curvaceous figure."

                final_instruction = (
                    f"Combine these: [Subject: {st.session_state.char_description}], [Scene: {context}], "
                    f"[Exposure: {sex_text}], [Body: {bust_ins}], [Extras: {', '.join(extras)}], [Quality: {quality}]. "
                    "Output ONE natural English paragraph starting with 'A photorealistic shot of...'."
                )

                final_p = call_grok_api([{"role":"user","content":final_instruction}])
                
                # 重み付けの強制付加
                if bust_type == "貧乳": final_p += ", (flat chest:1.9), (tiny breasts:1.5)"
                if nipple_poke: final_p += ", (nipples poking through clothing:1.4)"
                
                st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
                
                st.success(f"生成完了 {i+1}")
                st.code(final_p)
                st.text_area("コピー用", value=final_p, height=100, key=f"copy_{i}_{os.urandom(4).hex()}")

# --- 履歴表示 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 生成履歴（最新10件）")
    for idx, hist in enumerate(reversed(st.session_state.prompt_history[-10:])):
        with st.expander(f"履歴 {len(st.session_state.prompt_history) - idx}"):
            if hist["image"]: st.image(hist["image"], width=150)
            st.text_area("プロンプト", value=hist["prompt"], height=100, key=f"hist_txt_{idx}")
