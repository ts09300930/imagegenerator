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
    # 【最終確定】2026年現在、Vision対応の正式名称は 'grok-2-1212' です。
    payload = {
        "model": "grok-2-1212", 
        "messages": messages, 
        "max_tokens": 1500, 
        "temperature": 0.8
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=60)
        
        # 1. まずレスポンスがJSONとして解析できるか
        try:
            json_res = res.json()
        except:
            return f"API_ERROR_{res.status_code}: Response is not JSON. {res.text[:100]}"

        # 2. ステータスコードが200（成功）か
        if res.status_code == 200:
            # 辞書型かつ必要なキーがあるか厳密にチェック
            if isinstance(json_res, dict) and "choices" in json_res:
                return json_res["choices"][0]["message"]["content"].strip()
            else:
                return f"API_ERROR: Unexpected JSON structure: {str(json_res)[:100]}"
        else:
            # 3. エラー時：json_resが辞書なら get を使い、そうでなければ文字列化する
            if isinstance(json_res, dict):
                # errorキーの中身も辞書とは限らないので徹底ガード
                error_obj = json_res.get('error', {})
                if isinstance(error_obj, dict):
                    msg = error_obj.get('message', 'Unknown API Error')
                else:
                    msg = str(error_obj)
            else:
                msg = str(json_res)
            return f"API_ERROR_{res.status_code}: {msg}"

    except Exception as e:
        # キャプチャのエラー(CONNECTION_ERROR)の発生源。
        # ここで .get() などを使わず、確実に文字列として例外を返す。
        return f"CONNECTION_ERROR: {str(e)}"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    img.thumbnail((1024, 1024))
    if img.mode != 'RGB': img = img.convert('RGB')
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 状態初期化 ---
if 'char_description' not in st.session_state: st.session_state.char_description = ""
if 'scenes_list' not in st.session_state: st.session_state.scenes_list = []
if 'prompt_history' not in st.session_state: st.session_state.prompt_history = []

# --- UI ---
st.title("Higgsfield Gen v9.0 (The Final Fix)")

st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("過去の履歴から選択", ["-- 履歴なし --"] + char_h)
if sel_h != "-- 履歴なし --": st.session_state.char_description = sel_h
st.session_state.char_description = st.text_area("身体的特徴 (最優先: 黒髪、眼鏡など)", value=st.session_state.char_description)

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
        res = call_grok_api([{"role": "user", "content": f"日本のSNS自撮り風のシチュエーション案を{gen_count}個考えて。'場所：、服装：、状態：'の形式で。"}] )
        if "API_ERROR" not in res and "CONNECTION_ERROR" not in res:
            st.session_state.scenes_list = [s.strip() for s in res.split('\n') if "場所：" in s][:gen_count]
    if st.session_state.scenes_list:
        for i, scene in enumerate(st.session_state.scenes_list):
            st.session_state.scenes_list[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
        for s in st.session_state.scenes_list: targets.append({"type": "text", "content": s})

st.markdown("---")
st.markdown("### ⚙️ 共通オプション (全機能復旧)")
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
# アングル追加
angle_type = st.selectbox("カメラアングル", ["標準", "俯瞰 (from above)", "アオリ (from below)", "横から (from side)"])

sex_map = {1: "modest", 2: "casual", 3: "sexy", 4: "revealing", 5: "extreme"}

# --- 生成実行 ---
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像かテキストを入力してください。")
        st.stop()
    save_char_history(st.session_state.char_description)
    
    for i, item in enumerate(targets):
        with st.container():
            current_ctx = ""
            display_img = None
            
            if item["type"] == "image":
                img_b64 = process_image(item['content'])
                display_img = item['content'].getvalue()
                with st.spinner(f"画像 {i+1} を解析中..."):
                    # メッセージ構造をVision用に最適化
                    current_ctx = call_grok_api([{"role":"user","content":[{"type":"text","text":"Describe THIS specific image's background and outfit."},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}"}}]}])
            else:
                current_ctx = item["content"]

            if "API_ERROR" in current_ctx or "CONNECTION_ERROR" in current_ctx:
                st.error(f"❌ 解析失敗 {i+1}: {current_ctx}")
                continue

            with st.spinner(f"プロンプト {i+1} を合成中..."):
                quality = "Masterpiece, 8k UHD, photorealistic, cinematic lighting, raw smartphone photo style."
                extras = []
                if tight_clothing: extras.append("extremely tight clothing")
                if nipple_poke: extras.append("visible nipple outlines")
                if mask_on: extras.append("wearing a white surgical mask")
                if iphone_selfie: extras.append("holding iPhone, mirror selfie")
                if face_hidden: extras.append("face hidden, focus on body")
                if angle_type != "標準": extras.append(angle_type.split("(")[-1].replace(")", ""))

                bust_ins = "Flat chest" if bust_type == "貧乳" else ("Large bust" if bust_type == "豊満" else "")
                
                # 指示の独立性を担保
                instruction = (
                    f"Subject Features (MANDATORY): {st.session_state.char_description}, {bust_ins}.\n"
                    f"Scene Context: {current_ctx}.\n"
                    f"Style: {sex_map[sex_level]}, {', '.join(extras)}, Quality: {quality}.\n"
                    "Task: Merge the Subject Features into the Scene Context. Priority: Subject > Scene."
                )

                final_p = call_grok_api([{"role":"user","content": f"{instruction} Output ONLY the English prompt starting with 'A photorealistic shot of...'"}])
                
                if "API_ERROR" in final_p or "CONNECTION_ERROR" in final_p:
                    st.error(f"❌ 合成失敗 {i+1}: {final_p}")
                    continue

                # タグ補正
                if bust_type == "貧乳": final_p += ", (flat chest:1.9)"
                if nipple_poke: final_p += ", (nipples poking through clothing:1.4)"

                st.session_state.prompt_history.append({"prompt": final_p, "image": display_img})
                st.success(f"✅ Result {i+1}")
                if display_img: st.image(display_img, width=200)
                st.code(final_p)
                st.text_area(f"Copy {i+1}", value=final_p, key=f"cp_{i}_{random.randint(0,999)}")
