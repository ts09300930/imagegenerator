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

SAVE_FILE = os.path.join(DATA_DIR, "app_state_v5_4.csv")

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
            # ★修正: より安全な取得方法に変更
            if not df.empty:
                char = str(df["char_desc"].iloc[0]) if "char_desc" in df.columns else ""
                scene = str(df["scene_desc"].iloc[0]) if "scene_desc" in df.columns else ""
        except: pass
    return char, scene

# Grok API設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    API_KEY = st.sidebar.text_input("Grok APIキーを入力してください", type="password")

if not API_KEY:
    st.error("APIキーが設定されていません。サイドバーから入力してください。")
    st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-2-vision-1224" 

# 起動時のデータ復元
init_char, init_scene = load_app_data()

# セッション状態の初期化
if 'prompt_history' not in st.session_state:
    st.session_state.prompt_history = []
if 'char_description' not in st.session_state:
    st.session_state.char_description = init_char
if 'scene_description' not in st.session_state:
    st.session_state.scene_description = init_scene

# --- AIロジック ---
def analyze_image_with_grok(image_data):
    base64_image = base64.b64encode(image_data).decode('utf-8')
    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Identify ONLY the environment/location, specific clothing, and the current action in this image. Do not mention facial features or body type. Paragraph only, English."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=40)
        return response.json()["choices"][0]["message"]["content"].strip()
    except:
        return ""

def generate_final_prompt(char_desc, context_info, sex_level, tight, nipple, bust):
    level_dict = {
        1: "fully clothed, modest outfit, no cleavage, no skin exposure",
        2: "slight skin exposure, form-fitting clothes, minimal cleavage",
        3: "visible cleavage, lingerie visible under clothes, sexy style",
        4: "wearing only bikini or lingerie, highly revealing, no outer clothing",
        5: "nearly nude, minimal coverage, topless or fully nude"
    }
    level_desc = level_dict.get(sex_level, "")

    extra_prompts = []
    if tight: extra_prompts.append("extremely tight skin-tight clothing hugging every curve")
    if nipple: extra_prompts.append("visible nipple outlines poking through the fabric")
    
    bust_prompt = ""
    if bust == "貧乳": 
        bust_prompt = "strictly flat chest, zero breast volume, (flat chest:1.9)"
    elif bust == "豊満": 
        bust_prompt = "voluptuous large breasts, deep cleavage"

    # ★修正: 指示をより具体的に（Higgsfieldに最適化）
    system_msg = (
        "You are a master prompt engineer for Higgsfield Diffuse. Create one seamless English paragraph. "
        "Combine the user's permanent physical features with the specific scene context. "
        "The scene/context provided MUST be the setting and outfit. Do not describe other people. No explanations."
    )
    user_msg = f"Physical Features: {char_desc}\nScene/Context (Priority for Setting/Outfit): {context_info}\nSexiness Level: {level_desc}\nBust Style: {bust_prompt}\nExtras: {', '.join(extra_prompts)}"

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=40)
        return response.json()["choices"][0]["message"]["content"].strip()
    except:
        return "Prompt Generation Error"

# --- UI構築 ---
st.title("Higgsfield Prompt Generator v5.4")

# 1. 女性の特徴
st.markdown("### 👩 1. 女性の身体的特徴（固定）")
char_input = st.text_area("髪型、体型、顔の特徴などを入力（丸投げしても維持されます）", 
                         value=st.session_state.char_description, 
                         key="char_area", height=80)
if char_input != st.session_state.char_description:
    st.session_state.char_description = char_input
    save_app_data(char_input, st.session_state.scene_description)

st.markdown("---")

# 2. シチュエーション
st.markdown("### 🎬 2. シチュエーション（画像優先）")
tab1, tab2 = st.tabs(["📷 画像から取得", "🎲 AIに丸投げ"])

with tab1:
    uploaded_images = st.file_uploader("参考画像をアップロード（複数可）", type=["jpg", "png", "heic"], accept_multiple_files=True)
    if uploaded_images:
        st.info("画像解析によるシチュエーションを優先して生成します。")

with tab2:
    if st.button("🎲 AIに新しいシチュエーションを提案させる"):
        with st.spinner("AIが考案中..."):
            try:
                r = requests.post(GROK_API_URL, 
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": GROK_MODEL, 
                        "messages": [
                            {"role": "system", "content": "具体的な場所・服装・行動を1つ提案してください。"},
                            {"role": "user", "content": "「場所：〇〇、服装：××、状態：△△」の形式で1行のみ。身体的特徴（胸のサイズや顔、髪型）は一切含めない。"}
                        ],
                        "temperature": 1.0
                    }, timeout=30
                )
                if r.status_code == 200:
                    new_scene = r.json()["choices"][0]["message"]["content"].strip()
                    st.session_state.scene_description = new_scene
                    save_app_data(st.session_state.char_description, new_scene)
                    st.rerun()
                else:
                    st.error(f"AI提案失敗: {r.status_code}")
            except Exception as e:
                st.error(f"接続エラー: {e}")
    
    scene_input = st.text_area("AI提案のシチュエーション（編集可）", 
                              value=st.session_state.scene_description, 
                              key="scene_area", height=80)
    if scene_input != st.session_state.scene_description:
        st.session_state.scene_description = scene_input
        save_app_data(st.session_state.char_description, scene_input)

# 3. 共通オプション
st.markdown("---")
st.markdown("### ⚙️ 3. 詳細設定")

sex_level = st.radio(
    "露出レベル",
    options=[1, 2, 3, 4, 5],
    format_func=lambda x: {
        1: "レベル 1 - 露出なし（普通の服）",
        2: "レベル 2 - 軽微な露出",
        3: "レベル 3 - 谷間・下着OKだが服着用",
        4: "レベル 4 - 水着・下着のみ",
        5: "レベル 5 - ほぼ全裸"
    }[x],
    index=2
)

bust_type = st.radio("胸のサイズ", options=["貧乳", "普通", "豊満"], index=1, horizontal=True)

col_a, col_b = st.columns(2)
tight = col_a.checkbox("タイトな服装（ボディライン強調）")
nipple = col_b.checkbox("乳首ぽち（布越し）")

# --- 生成実行 ---
st.markdown("---")
if st.button("🚀 プロンプト生成開始", type="primary", use_container_width=True):
    process_items = []
    if uploaded_images:
        for img in uploaded_images:
            img.seek(0)
            process_items.append({"type": "image", "file": img})
    else:
        process_items.append({"type": "text", "content": st.session_state.scene_description})

    for item in process_items:
        with st.container():
            if item["type"] == "image":
                st.image(item["file"], width=200)
                with st.spinner(f"画像を解析中..."):
                    context_info = analyze_image_with_grok(item["file"].getvalue())
            else:
                context_info = item["content"]
                st.write(f"シチュエーション: {context_info}")

            with st.spinner("プロンプトを合成中..."):
                final_p = generate_final_prompt(
                    st.session_state.char_description,
                    context_info,
                    sex_level, tight, nipple, bust_type
                )
            
            if bust_type == "貧乳":
                final_p += ", (flat chest:1.9), (no breast protrusion:1.8), bony shoulders"
            if sex_level == 1:
                final_p += ", thick modest clothing"
            final_p += "."

            st.code(final_p)
            
            if item["type"] == "image":
                st.session_state.prompt_history.append((final_p, item["file"].getvalue()))

# --- 履歴表示 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 最近の生成履歴 (画像)")
    for p, img_b in reversed(st.session_state.prompt_history[-5:]):
        with st.expander("履歴を表示"):
            st.image(img_b, width=150)
            st.code(p)
