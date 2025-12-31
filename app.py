import streamlit as st
import requests
import os
import base64

# Grok APIキーの設定（環境変数から取得）
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    st.error("XAI_API_KEY が設定されていません。環境変数を設定してください。")
    st.stop()

# Grok APIエンドポイント
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def analyze_image_with_grok(image_data):
    """Grok APIを使用して画像を分析し、忠実な英語プロンプトを生成"""
    # 画像をBase64エンコード
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    payload = {
        "model": "grok-beta",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in precise English detail, focusing only on visible elements without any creative interpretation. Structure as a prompt for AI video generation: subject, action, environment, clothing, appearance, lighting, style."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 300
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        st.error(f"APIエラー: {response.text}")
        return None

# Streamlit UI
st.title("Image to English Prompt Generator")

# 画像アップロード
uploaded_image = st.file_uploader("画像をアップロードしてください", type=["jpg", "jpeg", "png"])

# 記述欄（テキスト入力）
description = st.text_area("記述欄（任意）：ここに記述すると優先されます", "")

# 生成ボタン
if st.button("プロンプト生成"):
    if uploaded_image or description:
        if description:
            # 記述欄が優先
            prompt = description.strip()  # 英語でない場合もそのまま使用（必要に応じて翻訳追加可能）
            st.write("生成されたプロンプト（記述欄優先）：")
            st.text(prompt)
        else:
            if uploaded_image:
                # 画像分析
                image_data = uploaded_image.read()
                prompt = analyze_image_with_grok(image_data)
                if prompt:
                    st.write("生成されたプロンプト（画像分析ベース）：")
                    st.text(prompt)
            else:
                st.warning("画像をアップロードしてください。")
    else:
        st.warning("画像または記述を入力してください。")

# 実行コマンド: streamlit run app.py
