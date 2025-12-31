import streamlit as st
import requests
import os
import base64

# Grok APIキーの設定
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    st.error("XAI_API_KEY が設定されていません。環境変数を設定してください。")
    st.stop()

# Grok APIエンドポイント
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def analyze_image_with_grok(image_data):
    """Grok APIを使用して画像を分析し、忠実な英語プロンプトを生成"""
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    payload = {
        "model": "grok-4",  # ここを修正（ビジョン対応の現在のモデル）
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

# Streamlit UI
st.title("Image to English Prompt Generator (Higgsfield向け)")

# 複数画像アップロード
uploaded_images = st.file_uploader(
    "画像をアップロードしてください（複数可）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

# 記述欄（テキスト入力：優先適用）
description = st.text_area("記述欄（任意）：ここに英語で記述すると、全画像に対して優先適用されます", "")

# 生成ボタン
if st.button("プロンプト生成"):
    if not uploaded_images:
        st.warning("少なくとも1枚の画像をアップロードしてください。")
    else:
        if description.strip():
            # 記述欄が優先：全画像に対して同じプロンプトを使用
            prompt = description.strip()
            st.success("記述欄が優先されました。すべての画像に対して以下のプロンプトを使用可能です：")
            st.text_area("生成プロンプト", value=prompt, height=200)
            # 画像を表示
            for img in uploaded_images:
                st.image(img, caption="アップロード画像", use_column_width=True)
        else:
            # 画像分析ベース：各画像ごとにプロンプト生成
            st.info("各画像に対して個別にプロンプトを生成します。")
            for idx, uploaded_image in enumerate(uploaded_images):
                with st.expander(f"画像 {idx+1}: {uploaded_image.name}"):
                    # 画像を表示
                    st.image(uploaded_image, caption="アップロード画像", use_column_width=True)
                    
                    # 分析
                    image_data = uploaded_image.read()
                    prompt = analyze_image_with_grok(image_data)
                    st.text_area(f"生成されたプロンプト {idx+1}", value=prompt, height=200, key=f"prompt_{idx}")

# 実行: streamlit run app.py
