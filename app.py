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
CHAR_HISTORY_FILE = os.path.join(DATA_DIR, "char_history_v11.csv")

# 2026年最新モデルを優先
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

def call_grok_api(messages: list, temperature: float = 0.7, max_tokens: int = 1200) -> str:
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
                return res.json()["choices"][0]["message"]["content"].strip()
            last_error = f"{model_name} failed ({res.status_code}): {res.text[:200]}"
        except Exception as e:
            last_error = str(e)
            continue
    return f"❌ エラー: {last_error}"

def process_image(file_bytes: bytes) -> str:
    """画像をbase64に変換（PIL経由でRGB変換・リサイズ）"""
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def generate_prompt(img_b64: str, persona: str) -> str:
    """
    画像を直接分析しながら、ペルソナ上書きした英語プロンプトを1回のAPI呼び出しで生成。
    画像の構図・ポーズ・背景・光・服装スタイルは忠実に再現。
    人物の外見・体型・雰囲気のみペルソナに置き換える。
    """
    system_prompt = """You are an expert AI image generation prompt engineer.

Your task:
1. Carefully analyze the provided reference image.
2. Extract and preserve these elements EXACTLY as they appear:
   - Pose and body position
   - Composition and camera angle/framing
   - Background and location
   - Lighting conditions and atmosphere
   - Outfit style and clothing type (style only, not the person wearing it)
   - Any props or accessories present

3. Replace ONLY the person's physical characteristics with the given persona description.

4. Output a single detailed English prompt suitable for Stable Diffusion / Midjourney / NovelAI.

Rules:
- Output ONLY the prompt text. No explanations, no labels, no bullet points.
- Write as a natural flowing description with comma-separated detail tags.
- The result should feel like the exact same photo re-taken with a different person.

PHOTO REALISM — always include these tags:
- RAW photo, photorealistic, hyperrealistic, DSLR quality, shot on Sony A7R V, 85mm lens
- ultra-detailed, sharp focus, in focus, depth of field, masterpiece, best quality

SKIN REALISM — always include these tags:
- realistic skin texture, visible pores, natural skin imperfections, subtle skin blemishes
- subsurface scattering, translucent skin, natural skin tone, soft skin highlight
- natural under-eye texture, faint laugh lines, realistic lip texture

NEVER include: blurry, 8k, soft focus, film grain, text on clothing, watermark, logo, anime, illustration, painting, drawing, cartoon"""

    user_content = [
        {
            "type": "text",
            "text": f"Reference image attached. Persona to apply (replace the person with this):\n{persona}\n\nGenerate the prompt now."
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}",
                "detail": "high"
            }
        }
    ]

    return call_grok_api(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.6,
        max_tokens=1000
    )

# ====================== UI ======================
st.set_page_config(page_title="画像×ペルソナ プロンプトジェネレーター", layout="wide")
st.title("🖼️ 画像×ペルソナ プロンプトジェネレーター")
st.caption("画像の構図・ポーズ・背景を忠実に再現 → 人物だけペルソナに置き換えた英語プロンプトを生成")

# ====================== APIキー ======================
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("XAI_API_KEY", "")
if not st.session_state.api_key:
    st.session_state.api_key = st.sidebar.text_input("Grok APIキー", type="password")
    if not st.session_state.api_key:
        st.stop()

# ====================== サイドバー：ペルソナ ======================
with st.sidebar:
    st.markdown("### 👩 ペルソナ設定")

    char_h = load_char_history()
    sel_h = st.selectbox("履歴から選択", ["-- 履歴なし --"] + char_h)
    if sel_h != "-- 履歴なし --":
        st.session_state.char_description = sel_h

    char_description = st.text_area(
        "ペルソナ（人物の特徴）",
        value=st.session_state.get("char_description", ""),
        height=200,
        placeholder="例：\n日本人20歳、アイドルっぽい雰囲気\nAカップ、ショートボブ、清楚系\n色白、たれ目、微笑み"
    )
    st.session_state.char_description = char_description

    if st.button("💾 履歴に保存"):
        save_char_history(char_description)
        st.success("保存しました")

    st.markdown("---")
    st.markdown("**使い方**")
    st.caption("1. ペルソナを入力\n2. 画像をアップロード\n3. 生成ボタンを押す\n\n画像のポーズ・構図・背景・光・服装スタイルはそのままに、人物の見た目だけペルソナに置き換えます。")

# ====================== メイン：画像アップロード ======================
st.markdown("### 📎 参考画像をアップロード")
uploaded_images = st.file_uploader(
    "複数枚OK（JPG / PNG / HEIC）",
    type=["jpg", "jpeg", "png", "heic"],
    accept_multiple_files=True
)

# アップロードされた画像を bytes で保持
image_items = []
if uploaded_images:
    cols = st.columns(min(len(uploaded_images), 5))
    for i, f in enumerate(uploaded_images):
        file_bytes = f.read()
        image_items.append({"bytes": file_bytes, "name": f.name})
        with cols[i % 5]:
            st.image(file_bytes, caption=f.name, use_container_width=True)

# ====================== 生成ボタン ======================
st.markdown("---")
if st.button("✦ 英語プロンプトを生成する", type="primary", use_container_width=True):
    if not image_items:
        st.warning("画像をアップロードしてください。")
        st.stop()
    if not char_description.strip():
        st.warning("サイドバーでペルソナを入力してください。")
        st.stop()

    st.markdown("### 生成結果")

    for idx, item in enumerate(image_items):
        st.markdown(f"---\n#### {idx+1}. {item['name']}")
        col_img, col_prompt = st.columns([1, 3])

        with col_img:
            st.image(item["bytes"], caption="参考画像", use_container_width=True)

        with col_prompt:
            with st.spinner(f"画像を分析してプロンプトを生成中... ({idx+1}/{len(image_items)})"):
                try:
                    img_b64 = process_image(item["bytes"])
                    result = generate_prompt(img_b64, char_description)
                except Exception as e:
                    result = f"❌ エラー: {e}"

            if result.startswith("❌"):
                st.error(result)
            else:
                st.code(result, language=None)
                escaped = result.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                html(f"""
                <button
                  onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>{{
                    this.textContent='✅ コピー済み';
                    setTimeout(()=>this.textContent='📋 コピー', 1500);
                  }})"
                  style="padding:6px 16px;border-radius:6px;border:1px solid #ccc;
                         background:#fff;cursor:pointer;font-size:13px;margin-top:4px;">
                  📋 コピー
                </button>
                """, height=44)

st.markdown("---")
st.caption("画像×ペルソナ プロンプトジェネレーター | Powered by Grok API")
