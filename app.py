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
    """画像をbase64に変換して返す（PIL経由でRGB変換・リサイズ）"""
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def analyze_image(img_b64: str) -> str:
    """画像を解析してシーン描写テキストを返す"""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Analyze this image and describe in one concise English paragraph: "
                        "1) the setting/background, 2) the pose and composition/angle, "
                        "3) the outfit style (not the person's appearance), "
                        "4) the lighting conditions. "
                        "Be specific and visual. Do not describe the person's face or body."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "high"
                    }
                }
            ]
        }
    ]
    return call_grok_api(messages, temperature=0.3, max_tokens=400)

def build_prompt(scene_ctx: str, char_desc: str, options: dict) -> str:
    """シーン情報＋ペルソナからプロンプトを1回のAPI呼び出しで生成"""

    sys_parts = [
        "You are an expert prompt engineer specializing in photorealistic AI portrait generation.",
        "Generate a single, detailed English prompt for an image generation AI.",
        "Output ONLY the prompt text itself — no labels, no explanations, no lists.",
        "The prompt must describe the scene, composition, lighting, and subject as one flowing description.",
        "",
        "CRITICAL PERSONA RULE: Replace ALL physical characteristics of the person in the reference "
        "with the persona below. Keep everything else (pose, composition, background, lighting, outfit style) "
        "as faithful to the reference as possible.",
    ]

    if options.get("clean_strategy"):
        bust = options.get("bust_size", "標準")
        sys_parts.append(
            "Clothing must be strictly modest and conservative. "
            "Adhere to the '2:1 skin ratio' rule — minimal skin exposure. "
            "ABSOLUTELY NO: cleavage, chest emphasis, suggestive poses, or revealing clothing. "
            f"Bust appearance: {bust}, natural and understated."
        )

    if options.get("date_vibe"):
        sys_parts.append(
            "Composition style: candid, unposed — as if her boyfriend quietly captured this moment during a real date. "
            "Convey genuine emotion and natural spontaneity."
        )

    if options.get("iphone_real"):
        lighting_str = options.get("lighting", "natural window light, 5500K")
        iphone_tags = ", ".join([
            "shot on iPhone 16 Pro, 24mm wide lens",
            f"{lighting_str}",
            "natural skin with visible pores, subtle blemishes, faint under-eye circles",
            "hair with natural flyaways and loose strands catching the backlight",
            "slightly wrinkled linen blouse with natural fabric drape",
            "shallow depth of field, f/2.8, background softly blurred with recognizable bokeh shapes",
            "slight iPhone HDR processing, subtle vignette at corners, faint sensor noise in shadows"
        ])
        sys_parts.append(f"Photography realism tags to append: {iphone_tags}")

    sys_parts += [
        "",
        "QUALITY TAGS to include: masterpiece, best quality, ultra-detailed, sharp focus, in focus",
        "NEGATIVE elements (describe what to avoid in the prompt context if needed): "
        "blurry, text on clothing, watermark, logo, bad anatomy",
    ]

    system_prompt = "\n".join(sys_parts)

    user_content = (
        f"SCENE/REFERENCE DESCRIPTION:\n{scene_ctx}\n\n"
        f"PERSONA (replace the person with this):\n{char_desc}\n\n"
        "Generate the complete English image generation prompt now."
    )

    result = call_grok_api(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.7,
        max_tokens=1000
    )

    # iPhone質感タグを末尾に強制付与（APIが省略した場合のフォールバック）
    if options.get("iphone_real") and "iPhone" not in result:
        lighting_str = options.get("lighting", "natural window light, 5500K")
        note_elements = [
            "shot on iPhone 16 Pro, 24mm wide lens",
            f"{lighting_str}, soft natural window light from the left, color temperature around 5500K",
            "natural skin with visible pores, subtle blemishes, faint under-eye circles",
            "hair with natural flyaways and loose strands catching the backlight",
            "slightly wrinkled linen blouse with natural fabric drape",
            "shallow depth of field, f/2.8, background softly blurred with recognizable bokeh shapes",
            "slight iPhone HDR processing, subtle vignette at corners, faint sensor noise in shadows"
        ]
        result = result.rstrip('.') + ". " + ", ".join(note_elements) + "."

    return result

# ====================== UI ======================
st.set_page_config(page_title="Higgsfield Gen v11.1", layout="wide")
st.title("📸 Higgsfield Gen v11.1 (Date-style with Reference View)")
st.caption("note戦略準拠：露出0 × iPhoneリアリティ × 彼氏目線構図 × 参考画像表示")

# APIキー
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("XAI_API_KEY", "")
if not st.session_state.api_key:
    st.session_state.api_key = st.sidebar.text_input("Grok APIキー", type="password")
    if not st.session_state.api_key:
        st.stop()

# ====================== サイドバー：ペルソナ ======================
with st.sidebar:
    st.markdown("### 👩 1. 身体的特徴（ペルソナ）")
    char_h = load_char_history()
    sel_h = st.selectbox("履歴から選択", ["-- 履歴なし --"] + char_h)
    if sel_h != "-- 履歴なし --":
        st.session_state.char_description = sel_h

    char_description = st.text_area(
        "身体的特徴 (例: 20代中盤の日本人女性、黒髪ボブ、薄いメイク)",
        value=st.session_state.get("char_description", ""),
        height=150
    )
    st.session_state.char_description = char_description

    if st.button("履歴に保存"):
        save_char_history(char_description)
        st.success("保存完了")

# ====================== メイン：モード選択 ======================
col_main, col_opt = st.columns([2, 1])

with col_main:
    st.markdown("### 🎬 2. シチュエーション設定")
    mode = st.radio(
        "入力モード",
        ["📷 画像からデート風に変換", "🎲 デートプラン自動生成"],
        horizontal=True
    )

    targets = []  # {"type": "image"|"text", "content": bytes|str, "display": bytes|None}

    if mode == "📷 画像からデート風に変換":
        uploaded_images = st.file_uploader(
            "参考画像（アングルや服装の参考にします）",
            type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True
        )
        if uploaded_images:
            for f in uploaded_images:
                file_bytes = f.read()  # ここで一度だけ読む
                targets.append({
                    "type": "image",
                    "content": file_bytes,
                    "display": file_bytes,
                    "name": f.name
                })

    else:
        c1, c2 = st.columns([1, 2])
        gen_count = c1.selectbox("生成数", options=list(range(1, 6)), index=2)

        if c2.button(f"🎲 デート案を{gen_count}件生成"):
            with st.spinner("AIがデートプランを考案中..."):
                res = call_grok_api([{
                    "role": "user",
                    "content": (
                        f"2026年のトレンドを反映した、露出なしでバズる『デート風AI美女』の"
                        f"シチュエーションを{gen_count}件提案して。"
                        "場所・服装・日常的な動作（カフェで注文中など）を日本語で。"
                        "各案を番号付きで改行して出力して。"
                    )
                }])
                if "❌" not in res:
                    scenes = [s.strip() for s in res.split('\n') if s.strip()][:gen_count]
                    st.session_state.scenes_list = scenes
                    st.rerun()

        scenes = st.session_state.get("scenes_list", [])
        edited_scenes = []
        for i, scene in enumerate(scenes):
            edited = st.text_area(f"デート案 {i+1}", value=scene, key=f"scene_{i}")
            edited_scenes.append(edited)
            if edited.strip():
                targets.append({
                    "type": "text",
                    "content": edited,
                    "display": None,
                    "name": f"デート案 {i+1}"
                })

# ====================== オプション ======================
with col_opt:
    st.markdown("### ⚙️ 3. note戦略オプション")
    date_vibe = st.checkbox("💖 彼氏目線モード (Boyfriend Lens)", value=True,
                            help="『彼氏が向かいから撮った』ような構図と雰囲気を追加")
    iphone_real = st.checkbox("📱 iPhone 16 Pro 質感", value=True,
                               help="毛穴、産毛、光の透過、HDR感を追加")
    clean_strategy = st.checkbox("🛡️ 露出0 (クリーン戦略)", value=True,
                                  help="2:1の素肌比率を遵守。露出を完全に排除")
    bust_size = st.select_slider(
        "胸の存在感",
        options=["控えめ", "標準", "強調なし"],
        value="標準"
    )
    lighting = st.selectbox("光の演出", [
        "自然な窓の光 (5500K)",
        "夕方のゴールデンアワー",
        "バーの琥珀色ライト",
        "街灯のミックス光"
    ])

options = {
    "date_vibe": date_vibe,
    "iphone_real": iphone_real,
    "clean_strategy": clean_strategy,
    "bust_size": bust_size,
    "lighting": lighting,
}

# ====================== 生成処理 ======================
if st.button("🚀 note戦略に基づいたプロンプトを一括生成", type="primary", use_container_width=True):
    if not targets:
        st.warning("画像またはテキストシーンを入力してください。")
        st.stop()

    if not char_description.strip():
        st.warning("サイドバーで身体的特徴（ペルソナ）を入力してください。")
        st.stop()

    for idx, item in enumerate(targets):
        st.markdown("---")
        scene_ctx = ""

        # --- シーン情報を取得 ---
        if item["type"] == "image":
            with st.spinner(f"[{idx+1}/{len(targets)}] 画像を解析中: {item['name']}"):
                try:
                    img_b64 = process_image(item["content"])
                    scene_ctx = analyze_image(img_b64)
                    if "❌" in scene_ctx:
                        st.warning(f"画像解析に失敗しました: {scene_ctx}")
                        scene_ctx = f"Image file: {item['name']}"  # フォールバック
                except Exception as e:
                    st.warning(f"画像処理エラー: {e}")
                    scene_ctx = f"Image file: {item['name']}"
        else:
            scene_ctx = item["content"]

        # --- プロンプト生成 ---
        with st.spinner(f"[{idx+1}/{len(targets)}] プロンプト生成中..."):
            final_prompt = build_prompt(scene_ctx, char_description, options)

        # --- 結果表示 ---
        is_error = "❌" in final_prompt

        if is_error:
            st.error(f"プロンプト {idx+1} の生成に失敗しました")
            st.code(final_prompt)
        else:
            st.success(f"✅ デート風プロンプト {idx+1} — {item['name']}")
            col_ref, col_res = st.columns([1, 3])

            with col_ref:
                if item["display"]:
                    st.image(item["display"], caption="参考画像", width=180)
                else:
                    st.info(f"**参考デート案:**\n\n{item['content']}")

            with col_res:
                st.code(final_prompt, language=None)
                # クリップボードコピーボタン
                escaped = final_prompt.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
                html(f"""
                <button
                  onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>{{this.textContent='✅ コピー済み';setTimeout(()=>this.textContent='📋 コピー',1500)}})"
                  style="padding:6px 14px;border-radius:6px;border:1px solid #ccc;background:#fff;cursor:pointer;font-size:13px;">
                  📋 コピー
                </button>
                """, height=40)

                # シーン解析内容を折りたたみで表示
                with st.expander("🔍 シーン解析内容を確認"):
                    st.write(scene_ctx)

st.markdown("---")
st.caption("Higgsfield Gen v11.1 | Strategy by note. Model: Grok-4 / Nano Banana Pro Ready")
