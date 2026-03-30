import streamlit as st
import requests
import os
import base64
import pandas as pd
from pillow_heif import register_heif_opener
import io
from PIL import Image
from streamlit.components.v1 import html

# HEICサポート
register_heif_opener()

# ====================== 設定 ======================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
CHAR_HISTORY_FILE = os.path.join(DATA_DIR, "char_history_v10.csv")

MODEL_PRIORITY = ["grok-4", "grok-2-vision-1212", "grok-vision-beta"]
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# ====================== ヘルパー関数 ======================
def load_char_history() -> list:
    if os.path.exists(CHAR_HISTORY_FILE):
        try:
            return pd.read_csv(CHAR_HISTORY_FILE)["char_desc"].dropna().tolist()
        except Exception:
            return []
    return []

def save_char_history(char: str):
    if not char or not char.strip():
        return
    history = load_char_history()
    if char in history:
        history.remove(char)
    history.insert(0, char)
    pd.DataFrame({"char_desc": history[:100]}).to_csv(CHAR_HISTORY_FILE, index=False)

def call_grok_api(messages: list, temperature: float = 0.7, max_tokens: int = 1000) -> str:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        api_key = st.session_state.get("api_key")
        if not api_key:
            st.error("Grok APIキーが設定されていません。")
            st.stop()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_error = ""

    for model_name in MODEL_PRIORITY:
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        try:
            res = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=90)

            if res.status_code == 200:
                try:
                    return res.json()["choices"][0]["message"]["content"].strip()
                except Exception:
                    continue

            if res.status_code >= 500 or res.status_code in (404, 429):
                last_error = f"{model_name} failed ({res.status_code})"
                continue

            try:
                msg = res.json().get('error', {}).get('message', res.text)
                return f"API_ERROR_{res.status_code}: {msg}"
            except Exception:
                return f"API_ERROR_{res.status_code}: {res.text[:150]}"

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            last_error = f"Timeout on {model_name}"
            continue

    return f"❌ サーバー混雑中: 全てのモデルが応答しませんでした。({last_error})"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# ====================== UI ======================
st.title("Higgsfield Gen v10.2 (露出0 超強化版)")

# APIキー
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("XAI_API_KEY", "")

if not st.session_state.api_key:
    st.session_state.api_key = st.sidebar.text_input("Grok APIキー", type="password")
    if not st.session_state.api_key:
        st.stop()

# 1. 身体的特徴
st.markdown("### 👩 1. 身体的特徴")
char_h = load_char_history()
sel_h = st.selectbox("履歴から選択", ["-- 履歴なし --"] + char_h)

if sel_h != "-- 履歴なし --":
    st.session_state.char_description = sel_h

char_description = st.text_area(
    "身体的特徴",
    value=st.session_state.get('char_description', ""),
    height=120
)
st.session_state.char_description = char_description

if st.button("履歴に保存"):
    save_char_history(char_description)
    st.success("保存しました")

st.markdown("---")

# 2. シチュエーション設定
st.markdown("### 🎬 2. 設定モード")
mode = st.radio("入力モード", ["📷 画像解析", "🎲 AI自動生成"], horizontal=True)

targets = []

if mode == "📷 画像解析":
    uploaded_images = st.file_uploader(
        "画像アップロード（複数可）",
        type=["jpg", "jpeg", "png", "heic"],
        accept_multiple_files=True
    )
    if uploaded_images:
        for f in uploaded_images:
            targets.append({"type": "image", "content": f})

else:
    c1, c2 = st.columns([1, 2])
    gen_count = c1.selectbox("生成数", options=list(range(1, 11)), index=2)
   
    if c2.button(f"🎲 {gen_count}件を自動生成"):
        with st.spinner("生成中..."):
            res = call_grok_api([{
                "role": "user",
                "content": f"日本のSNS自撮り風のシチュエーションを{gen_count}件提案してください。各案を場所・服装・状態の観点で簡潔に記述。"
            }])
            if "❌" not in res and "ERROR" not in res:
                st.session_state.scenes_list = [s.strip() for s in res.split('\n') if s.strip()][:gen_count]
                st.rerun()

    scenes = st.session_state.get('scenes_list', [])
    for i, scene in enumerate(scenes):
        scenes[i] = st.text_area(f"案 {i+1}", value=scene, key=f"scene_{i}")
   
    for s in scenes:
        if s.strip():
            targets.append({"type": "text", "content": s})

st.markdown("---")

# 3. オプション設定
st.markdown("### ⚙️ 3. オプション設定")
col1, col2 = st.columns(2)
sex_level = col1.select_slider("露出レベル", options=[1, 2, 3, 4, 5], value=3)
bust_type = col2.radio("胸のサイズ", ["貧乳", "普通", "豊満"], index=1, horizontal=True)

photo_real_mode = st.checkbox("✅ リアルな写真風プロンプトにする（Photorealisticモード）", value=False)
safe_mode = st.checkbox("✅ 露出を完全に抑える（露出度0） — 谷間・胸の強調・透けなどを強力に排除", value=False)

ca, cb, cc = st.columns(3)
tight_clothing = ca.checkbox("タイトな服装", disabled=safe_mode)
nipple_poke = cb.checkbox("乳首ぽち", disabled=safe_mode)
mask_on = cc.checkbox("白いマスク")

# ====================== 生成処理 ======================
if st.button("🚀 プロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像またはテキストを少なくとも1つ入力してください。")
        st.stop()

    save_char_history(char_description)

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
                            {"type": "text", "text": "Describe the setting, outfit, pose, and background in one concise English paragraph."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]}
                    ])
            else:
                current_ctx = item["content"]

            if "❌" in str(current_ctx) or "ERROR" in str(current_ctx):
                st.error(current_ctx)
                continue

            with st.spinner("最終プロンプト合成中..."):
                # 胸の記述（安全モード時は控えめ固定）
                if safe_mode:
                    bust_ins = "modest bust, average chest size, no breast emphasis"
                else:
                    bust_ins = "(flat chest:1.9), petite bony torso" if bust_type == "貧乳" else \
                               ("large ample bust, voluptuous curves" if bust_type == "豊満" else "")

                adds = []
                if tight_clothing and not safe_mode:
                    adds.append("extremely tight-fitting")
                if nipple_poke and not safe_mode:
                    adds.append("visible nipples poking through fabric")
                if mask_on:
                    adds.append("wearing a white surgical mask")

                # リアル写真モード
                style_instruction = (
                    "photorealistic, raw smartphone photo, natural lighting, casual mirror selfie style, "
                    "slight grain, realistic skin texture, 8k raw photo, shot on iPhone, natural pose, "
                    "unfiltered, documentary style" if photo_real_mode else ""
                )

                # ====================== 露出0 超強力指示 ======================
                if safe_mode:
                    safe_instruction = (
                        "strictly modest clothing, conservative outfit, fully covered body, high neckline, "
                        "no cleavage, no deep neckline, no plunging neckline, no underboob, no sideboob, "
                        "no visible breast contour, no emphasized breasts, no breast focus, breasts not prominent, "
                        "no exposed chest skin, no valley between breasts, completely flat chest appearance, "
                        "no see-through fabric, no sheer clothing, no wet clothing, no tight clothing revealing shape, "
                        "no upskirt, no short skirt with excessive thigh exposure, no suggestive clothing, "
                        "safe for work, sfw, completely non-sexual, modest and proper attire, fully clothed, "
                        "no erotic elements whatsoever. "
                        "(cleavage:1.9), (deep cleavage:1.9), (underboob:1.9), (visible nipples:1.9), "
                        "(exposed breasts:1.9), (breast emphasis:1.9), (suggestive pose:1.8) — "
                        "ABSOLUTELY AVOID ALL OF THE ABOVE. MUST strictly enforce modesty."
                    )
                    effective_sex_level = 0
                else:
                    safe_instruction = ""
                    effective_sex_level = sex_level

                system_content = (
                    f"You are a professional prompt engineer for safe AI image generation. "
                    f"Sexiness level: {effective_sex_level}/5 (0 = completely modest and non-erotic). "
                    f"{bust_ins}. "
                    f"Additional descriptors: {', '.join(adds) if adds else 'none'}. "
                    f"{style_instruction}. "
                    f"{safe_instruction}. "
                    "CRITICAL: If safe_mode is enabled, you MUST output only modest, conservative, and fully covered clothing. "
                    "Never generate any revealing, sexy, or suggestive elements. "
                    "Output ONLY a single, detailed, well-structured English paragraph. "
                    "Do not add explanations or extra text."
                )

                final_p = call_grok_api([
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": f"Scene: {current_ctx}\nSubject: {char_description}"}
                ])

                if "❌" in str(final_p) or "ERROR" in str(final_p):
                    st.error(final_p)
                    continue

                st.success(f"✅ Result {idx+1}")
                if display_img:
                    st.image(display_img, width=220)
                st.code(final_p, language=None)

                # コピーボタン
                escaped_p = final_p.replace('`', '\\`').replace('$', '\\$')
                html(f"""
                <button onclick="navigator.clipboard.writeText(`{escaped_p}`)">
                    📋 プロンプトをコピー
                </button>
                """)

st.caption("Higgsfield Gen v10.2 — 露出0 超強化版（谷間・胸強調を強力排除）")
