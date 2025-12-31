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
    """Grok APIを使用して画像を分析し、忠実な英語プロンプトを生成"""
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
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        st.error(f"APIエラー: {response.text}")
        return "プロンプト生成に失敗しました。"

def translate_description_to_english_prompt(description):
    """日本語記述をHiggsfield Diffuse向けの詳細な英語プロンプトに変換"""
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "system", "content": "Convert the following Japanese description to a detailed, structured English prompt optimized for Higgsfield Diffuse video generation. Include subject, appearance, clothing, action, environment, etc., while keeping it natural and effective."},
            {"role": "user", "content": description}
        ],
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        st.error(f"記述変換エラー: {response.text}")
        return description  # フォールバック

def optimize_prompt(prompt):
    """プロンプトをHiggsfield Diffuse向けに最適化（短く明確に）"""
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "system", "content": "Optimize this English prompt for Higgsfield Diffuse: make it shorter, clearer, more effective, while keeping all key details."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        st.error(f"最適化エラー: {response.text}")
        return prompt

def translate_to_japanese(prompt):
    """英語プロンプトを自然な日本語に翻訳"""
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "system", "content": "Translate this English prompt to natural, fluent Japanese."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        st.error(f"翻訳エラー: {response.text}")
        return "翻訳に失敗しました。"

# Streamlit UI
st.title("Image to English Prompt Generator (Higgsfield向け)")

# 複数画像アップロード
uploaded_images = st.file_uploader(
    "画像をアップロードしてください（複数可）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

# 記述欄（日本語可・優先適用）
description = st.text_area(
    "記述欄（任意・日本語可）：ここに記述すると優先的に英語プロンプトに反映されます",
    ""
)

# 生成ボタン
if st.button("プロンプト生成"):
    if not uploaded_images and not description.strip():
        st.warning("画像をアップロードするか、記述を入力してください。")
    else:
        generated_prompts = []
        if description.strip():
            # 記述優先：日本語→英語プロンプト変換
            with st.spinner("記述を英語プロンプトに変換中..."):
                prompt = translate_description_to_english_prompt(description.strip())
            st.success("記述欄が優先されました。日本語記述を英語プロンプトに変換しました。")
            st.text_area("生成プロンプト（英語）", value=prompt, height=200, key="main_prompt_gen")
            
            # 画像を表示（あれば）
            if uploaded_images:
                for img in uploaded_images:
                    st.image(img, caption="アップロード画像", use_column_width=True)
            
            generated_prompts = [prompt] * (len(uploaded_images) if uploaded_images else 1)
        else:
            # 画像分析ベース
            st.info("各画像に対して個別にプロンプトを生成します。")
            for idx, uploaded_image in enumerate(uploaded_images):
                with st.expander(f"画像 {idx+1}: {uploaded_image.name}"):
                    st.image(uploaded_image, caption="アップロード画像", use_column_width=True)
                    
                    image_data = uploaded_image.read()
                    prompt = analyze_image_with_grok(image_data)
                    generated_prompts.append(prompt)
                    st.text_area(f"生成されたプロンプト {idx+1}（英語）", value=prompt, height=200, key=f"prompt_gen_{idx}")
        
        # 履歴に追加
        st.session_state.prompt_history.extend(generated_prompts)

# 生成履歴の表示（最新10件）
if st.session_state.prompt_history:
    st.markdown("### 生成履歴（最新10件、再利用可能）")
    for i, hist_prompt in enumerate(reversed(st.session_state.prompt_history[-10:])):
        hist_index = len(st.session_state.prompt_history) - 1 - i
        with st.expander(f"履歴 {hist_index + 1}: {hist_prompt[:50]}..."):
            st.text_area("履歴プロンプト", value=hist_prompt, height=150, key=f"hist_text_{i}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                html(f"<button onclick=\"navigator.clipboard.writeText(`{hist_prompt.replace('`', '\\`')}`)\">📋 コピー</button>", height=40)
            with col2:
                st.download_button(
                    "📥 ダウンロード",
                    hist_prompt,
                    file_name=f"prompt_history_{hist_index + 1}.txt",
                    mime="text/plain",
                    key=f"dl_{i}"
                )
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

# 実行コマンド: streamlit run app.py
