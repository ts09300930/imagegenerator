import streamlit as st
import requests
import os
import base64
from streamlit.components.v1 import html

# Grok APIキーの設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    st.error("XAI_API_KEY が設定されていません。環境変数を設定してください。")
    st.stop()

# Grok APIエンドポイント
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# セッション状態の初期化（履歴保存用）
if 'prompt_history' not in st.session_state:
    st.session_state.prompt_history = []

def analyze_image_with_grok(image_data):
    """画像だけを分析"""
    base64_image = base64.b64encode(image_data).decode('utf-8')
    payload = {
        "model": "grok-4",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in precise English detail, focusing only on visible elements without any creative interpretation. Structure as a prompt for AI video generation (e.g., Higgsfield Diffuse): subject, appearance, clothing, action, environment, lighting, camera angle, style."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        st.error(f"APIエラー: {response.text}")
        return "プロンプト生成に失敗しました。"

def merge_description_to_prompt(base_prompt, description):
    """画像分析結果＋記述欄を融合して新しいプロンプトを作成（本文のみ出力）"""
    payload = {
        "model": "grok-4",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert prompt engineer. Take the base English prompt from the image analysis and merge the user's Japanese description into it. "
                           "Override or add details from the Japanese description (e.g., bust size, hair, height, clothing). "
                           "Output ONLY the final English prompt text. No explanations, no headings, no markdown."
            },
            {"role": "user", "content": f"Base prompt: {base_prompt}\n\nJapanese description to add/override: {description}"}
        ],
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        raw = response.json()["choices"][0]["message"]["content"].strip()
        # 余分な文字を除去
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        return raw.strip()
    else:
        st.error(f"融合エラー: {response.text}")
        return base_prompt

def optimize_prompt(prompt):
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "system", "content": "Optimize this English prompt for Higgsfield Diffuse: make it shorter, clearer, more effective, while keeping all key details. Output only the optimized prompt text."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        st.error(f"最適化エラー: {response.text}")
        return prompt

def translate_to_japanese(prompt):
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "system", "content": "Translate this English prompt to natural, fluent Japanese."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        st.error(f"翻訳エラー: {response.text}")
        return "翻訳に失敗しました。"

# Streamlit UI
st.title("Image to English Prompt Generator (Higgsfield向け)")

uploaded_images = st.file_uploader(
    "画像をアップロードしてください（複数可）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

description = st.text_area(
    "記述欄（任意・日本語可）：ここに書くと各画像に個別に反映されます（例：Gカップ、黒髪ロング、赤いドレス）",
    ""
)

if st.button("プロンプト生成"):
    if not uploaded_images:
        st.warning("少なくとも1枚の画像をアップロードしてください。")
    else:
        generated_prompts = []
        has_description = description.strip() != ""
        
        if has_description:
            st.success("記述欄の内容を各画像に個別に反映します！")
        
        for idx, uploaded_image in enumerate(uploaded_images):
            with st.expander(f"画像 {idx+1}: {uploaded_image.name}"):
                st.image(uploaded_image, caption="アップロード画像", use_column_width=True)
                
                # まず画像だけを分析
                image_data = uploaded_image.read()
                base_prompt = analyze_image_with_grok(image_data)
                
                # 記述があれば融合
                if has_description:
                    with st.spinner(f"画像{idx+1}に記述を反映中..."):
                        final_prompt = merge_description_to_prompt(base_prompt, description.strip())
                else:
                    final_prompt = base_prompt
                
                generated_prompts.append(final_prompt)
                st.text_area(f"生成プロンプト {idx+1}（英語）", value=final_prompt, height=200, key=f"prompt_gen_{idx}")
        
        # 履歴に追加
        st.session_state.prompt_history.extend(generated_prompts)

# 生成履歴（最新10件）
if st.session_state.prompt_history:
    st.markdown("### 生成履歴（最新10件、再利用可能）")
    for i, hist_prompt in enumerate(reversed(st.session_state.prompt_history[-10:])):
        hist_index = len(st.session_state.prompt_history) - 1 - i
        with st.expander(f"履歴 {hist_index + 1}: {hist_prompt[:50]}..."):
            st.text_area("履歴プロンプト", value=hist_prompt, height=150, key=f"hist_text_{i}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                html(f"<button onclick=\"navigator.clipboard.writeText(`{hist_prompt.replace('`', '\\`')}`)\">コピー</button>", height=40)
            with col2:
                st.download_button("ダウンロード", hist_prompt, file_name=f"prompt_{hist_index + 1}.txt", mime="text/plain", key=f"dl_{i}")
            with col3:
                if st.button("最適化", key=f"opt_{i}"):
                    with st.spinner("最適化中..."):
                        optimized = optimize_prompt(hist_prompt)
                    st.text_area("最適化後プロンプト", value=optimized, height=150, key=f"opt_result_{i}")
            with col4:
                if st.button("日本語翻訳", key=f"trans_{i}"):
                    with st.spinner("翻訳中..."):
                        translated = translate_to_japanese(hist_prompt)
                    st.text_area("日本語翻訳（編集可能）", value=translated, height=150, key=f"jtrans_{i}")
