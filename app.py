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

SAVE_FILE = os.path.join(DATA_DIR, "app_state_final.csv")

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
            char = df["char_desc"][0]
            scene = df["scene_desc"][0]
        except: pass
    return char, scene

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
    """画像から場所・服装・行動のみを抽出"""
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
        response = requests.post(GROK_API_URL, json=payload, headers=headers)
        return response.json()["choices"][0]["message"]["content"].strip()
    except:
        return ""

def generate_final_prompt(char_desc, context_info, sex_level, tight, nipple, bust):
    """【女性の特徴】+【画像 or AIシチュエーション】+【ラジオボタン等の補正】を合成"""
    level_dict = {
        1: "fully clothed, modest outfit, no cleavage, no skin exposure",
        2: "slight skin exposure, form-fitting clothes, minimal cleavage",
        3: "visible cleavage, lingerie visible under clothes, sexy style",
        4: "wearing only bikini or lingerie, highly revealing, no outer clothing",
        5: "nearly nude, minimal coverage, topless or fully nude"
    }
    level_desc = level_dict.get(sex_level, "")

    # オプション補正
    extra_prompts = []
    if tight: extra_prompts.append("extremely tight skin-tight clothing hugging every curve")
    if nipple: extra_prompts.append("visible nipple outlines poking through the fabric")
    
    bust_prompt = ""
    if bust == "貧乳": 
        bust_prompt = "strictly flat chest, zero breast volume, petite frame, (flat chest:1.9)"
    elif bust == "豊満": 
        bust_prompt = "voluptuous large breasts, deep cleavage"

    system_msg = (
        "You are a master prompt engineer for Higgsfield Diffuse. Combine the user's permanent physical features and the scene context into a single, high-quality English paragraph. "
        "The scene/context provided is the absolute priority for location and outfit. Do not add explanations."
    )
    user_msg = f"Physical Features: {char_desc}\nScene/Action Context: {context_info}\nSexiness Level: {level_desc}\nBust Style: {bust_prompt}\nExtras: {', '.join(extra_prompts)}"

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(GROK_API_URL, json=payload, headers=headers)
        return response.json()["choices"][0]["message"]["content"].strip()
    except:
        return "Prompt Generation Error"

# --- UI構築 ---
st.title("Higgsfield Prompt Generator v5.2")

# 1. 女性の特徴
st.markdown("### 👩 1. 女性の身体的特徴（固定）")
char_input = st.text_area("髪型、体型、顔の特徴などを入力（自動保存されます）", 
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
        st.success(f"{len(uploaded_images)}枚の画像を認識しました。画像から場所と服装を抽出します。")

with tab2:
    if st.button("🎲 AIに新しいシチュエーションを提案させる", key="ai_rand_btn"):
        with st.spinner("AI提案中..."):
            try:
                r = requests.post(GROK_API_URL, 
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": GROK_MODEL, 
                        "messages": [
                            {"role": "system", "content": "フェティッシュで物語性のあるシチュエーションを1つ提案してください。"},
                            {"role": "user", "content": "「場所：〇〇、服装：××、状態：△△」の形式で1行だけで出力。身体的特徴は含めない。"}
                        ],
                        "temperature": 1.0
                    }
                )
                if r.status_code == 200:
                    st.session_state.scene_description = r.json()["choices"][0]["message"]["content"].strip()
                    save_app_data(st.session_state.char_description, st.session_state.scene_description)
                    st.rerun()
            except Exception as e:
                st.error(f"AI提案失敗: {e}")
    
    scene_input = st.text_area("AI提案のシチュエーション（編集可）", 
                              value=st.session_state.scene_description, 
                              key="scene_area", height=80)
    if scene_input != st.session_state.scene_description:
        st.session_state.scene_description = scene_input
        save_app_data(st.session_state.char_description, scene_input)

# 3. 共通オプション
st.markdown("---")
st.markdown("### ⚙️ 3. 詳細オプション（全画像共通）")

sex_level = st.radio(
    "露出レベルを選んでください",
    options=[1, 2, 3, 4, 5],
    format_func=lambda x: f"レベル {x} - " + {
        1: "露出なし（普通の服）",
        2: "軽微な露出",
        3: "谷間くらい、下着OKだが服着用",
        4: "水着・下着だけ",
        5: "ほぼ全裸"
    }[x],
    index=2,
    horizontal=False
)

bust_type = st.radio("胸のサイズ", options=["貧乳", "普通", "豊満"], index=1, horizontal=True)

col_a, col_b = st.columns(2)
tight = col_a.checkbox("タイトな服装（ボディライン強調）")
nipple = col_b.checkbox("乳首ぽち（布越し）")

# --- 生成実行 ---
st.markdown("---")
if st.button("🚀 プロンプト生成開始", type="primary", use_container_width=True):
    # コンテキスト（シチュエーション）の決定
    # 画像があれば画像から、なければテキストエリアから
    process_list = []
    if uploaded_images:
        for img in uploaded_images:
            img.seek(0)
            pil_img = Image.open(img).convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG")
            process_list.append({"type": "image", "content": buf.getvalue(), "name": img.name})
    else:
        process_list.append({"type": "text", "content": st.session_state.scene_description, "name": "AIシチュエーション"})

    for item in process_list:
        with st.container():
            st.markdown(f"#### 🔹 {item['name']} から生成")
            
            # 画像解析
            if item["type"] == "image":
                with st.spinner("画像を解析中..."):
                    context_info = analyze_image_with_grok(item["content"])
                st.image(item["content"], width=200)
            else:
                context_info = item["content"]

            # プロンプト合成
            with st.spinner("プロンプト合成中..."):
                final_p = generate_final_prompt(
                    st.session_state.char_description,
                    context_info,
                    sex_level, tight, nipple, bust_type
                )
            
            # 貧乳力技補正（Higgsfield用）
            if bust_type == "貧乳":
                final_p += ", (extremely flat chest:1.9), (no protrusion:1.8), bony collarbones"
            if sex_level == 1:
                final_p += ", thick modest clothing, opaque fabric"
            final_p += "."

            st.code(final_p)
            
            # 履歴に保存
            if item["type"] == "image":
                st.session_state.prompt_history.append((final_p, item["content"]))

# --- 履歴表示 ---
if st.session_state.prompt_history:
    st.markdown("---")
    st.markdown("### 🕒 最近の履歴 (画像あり)")
    for p, img_b in reversed(st.session_state.prompt_history[-5:]):
        with st.expander("履歴を表示"):
            st.image(img_b, width=150)
            st.code(p)
