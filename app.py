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
            last_error = f"{model_name} failed ({res.status_code})"
        except Exception as e:
            last_error = str(e)
            continue
    return f"❌ エラー: {last_error}"

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    # 解析用なので少し小さめに縮小（トークン節約）
    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# ====================== UI ======================
st.set_page_config(page_title="Higgsfield Gen v11.1", layout="wide")
st.title("📸 Higgsfield Gen v11.1 (Date-style with Reference View)")
st.caption("note戦略準拠：露出0 × iPhoneリアリティ × 彼氏目線構図 × 参考画像表示")

# APIキー
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("XAI_API_KEY", "")
if not st.session_state.api_key:
    st.session_state.api_key = st.sidebar.text_input("Grok APIキー", type="password")
    if not st.session_state.api_key: st.stop()

# 1. 身体的特徴
with st.sidebar:
    st.markdown("### 👩 1. 身体的特徴")
    char_h = load_char_history()
    sel_h = st.selectbox("履歴から選択", ["-- 履歴なし --"] + char_h)
    if sel_h != "-- 履歴なし --":
        st.session_state.char_description = sel_h

    char_description = st.text_area(
        "身体的特徴 (例: 20代中盤の日本人女性、黒髪ボブ、薄いメイク)",
        value=st.session_state.get('char_description', ""),
        height=150
    )
    st.session_state.char_description = char_description
    if st.button("履歴に保存"):
        save_char_history(char_description)
        st.success("保存完了")

# 2. シチュエーション設定
col_main, col_opt = st.columns([2, 1])

with col_main:
    st.markdown("### 🎬 2. シチュエーション設定")
    mode = st.radio("入力モード", ["📷 画像からデート風に変換", "🎲 デートプラン自動生成"], horizontal=True)

    targets = []
    if mode == "📷 画像からデート風に変換":
        uploaded_images = st.file_uploader("参考画像（アングルや服装の参考にします）", type=["jpg", "jpeg", "png", "heic"], accept_multiple_files=True)
        if uploaded_images:
            for f in uploaded_images:
                targets.append({"type": "image", "content": f})
    else:
        c1, c2 = st.columns([1, 2])
        gen_count = c1.selectbox("生成数", options=list(range(1, 6)), index=2)
        if c2.button(f"🎲 デート案を{gen_count}件生成"):
            with st.spinner("AIがデートプランを考案中..."):
                res = call_grok_api([{
                    "role": "user",
                    "content": f"2026年のトレンドを反映した、露出なしでバズる『デート風AI美女』のシチュエーションを{gen_count}件提案して。場所・服装・日常的な動作（カフェで注文中など）を日本語で。"
                }])
                if "❌" not in res:
                    st.session_state.scenes_list = [s.strip() for s in res.split('\n') if s.strip()][:gen_count]
                    st.rerun()

        scenes = st.session_state.get('scenes_list', [])
        for i, scene in enumerate(scenes):
            scenes[i] = st.text_area(f"デート案 {i+1}", value=scene, key=f"scene_{i}")
            if scenes[i].strip():
                targets.append({"type": "text", "content": scenes[i]})

with col_opt:
    st.markdown("### ⚙️ 3. note戦略オプション")
    date_vibe = st.checkbox("💖 彼氏目線モード (Boyfriend Lens)", value=True, help="『彼氏が向かいから撮った』ような構図と雰囲気を追加")
    iphone_real = st.checkbox("📱 iPhone 16 Pro 質感", value=True, help="毛穴、産毛、光の透過、HDR感を追加")
    clean_strategy = st.checkbox("🛡️ 露出0 (クリーン戦略)", value=True, help="2:1の素肌比率を遵守。露出を完全に排除")
    
    bust_size = st.select_slider("胸の存在感", options=["控えめ", "標準", "強調なし"], value="標準")
    lighting = st.selectbox("光の演出", ["自然な窓の光 (5500K)", "夕方のゴールデンアワー", "バーの琥珀色ライト", "街灯のミックス光"])

# ====================== 生成処理 ======================
if st.button("🚀 note戦略に基づいたプロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像またはテキストを入力してください。")
        st.stop()

    for idx, item in enumerate(targets):
        with st.container():
            st.markdown("---")
            current_ctx = ""
            display_img = None
            ref_text = ""

            if item["type"] == "image":
                # 【復元ポイント】アップロード画像をプレビュー用に保持
                img_b64 = process_image(item['content'])
                display_img = item['content'].getvalue() 
                with st.spinner(f"画像 {idx+1} 解析中..."):
                    current_ctx = call_grok_api([
                        {"role": "user", "content": [
                            {"type": "text", "text": "Extract only the setting, outfit (describe as modest), and pose. Concise paragraph."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]}
                    ])
            else:
                current_ctx = item["content"]
                ref_text = item["content"] # テキストモード用の参考テキスト

            # システムプロンプトの構築（noteの知見を全投入）
            sys_parts = [
                "You are an expert prompt engineer for 'Date-style AI photography'.",
                "Output ONLY a single detailed natural language paragraph in English.",
                "NO tags, NO lists, NO explanations."
            ]

            # iPhoneリアリティの注入
            if iphone_real:
                sys_parts.append(
                    "Style: Shot on iPhone 16 Pro, 24mm or 48mm lens. Computational photography look. "
                    "Incorporate natural skin texture with visible pores, subtle blemishes, and faint under-eye circles. "
                    "Hair should have natural flyaways and loose strands catching the light. "
                    "Apply slight smart HDR processing and subtle sensor noise in shadows."
                )

            # クリーン戦略
            if clean_strategy:
                sys_parts.append(
                    "Clothing: Strictly modest and conservative. Adhere to the '2:1 skin ratio' (hide most skin except face/wrists/ankles). "
                    "Oversized knits, high necklines, or coats are preferred. "
                    "ABSOLUTELY AVOID: cleavage, chest emphasis, suggestive poses, swimwear, or revealing clothes. "
                    f"Bust description: {bust_size} and natural, no emphasis."
                )

            # 彼氏目線
            if date_vibe:
                sys_parts.append(
                    "Composition: The photo must feel spontaneous and intimate, 'as if her boyfriend quietly took this photo' "
                    "during a real date. Focus on unposed, candid moments and genuine expressions."
                )

            sys_parts.append(f"Lighting: {lighting}.")

            with st.spinner(f"デート風プロンプト {idx+1} 合成中..."):
                final_p = call_grok_api([
                    {"role": "system", "content": " ".join(sys_parts)},
                    {"role": "user", "content": f"Scene Context: {current_ctx}\nSubject Details: {char_description}"}
                ])

                # 【画面出力】参考と結果を並べて表示
                st.success(f"✅ デート風プロンプト {idx+1}")
                col_ref, col_res = st.columns([1, 3])

                with col_ref:
                    # 画像モードなら画像、テキストモードならデート案テキストを表示
                    if display_img:
                        st.image(display_img, caption="参考画像（アングル・服装）", width=180)
                    else:
                        st.info(f"参考デート案:\n\n{ref_text}")

                with col_res:
                    st.code(final_p, language=None)
                    # コピーボタン
                    escaped_p = final_p.replace('`', '\\`').replace('$', '\\$')
                    html(f"""<button onclick="navigator.clipboard.writeText(`{escaped_p}`)">📋 プロンプトをコピー</button>""")

st.markdown("---")
st.caption("Higgsfield Gen v11.1 | Strategy by note. Model: Grok-4 / Nano Banana Pro Ready")
