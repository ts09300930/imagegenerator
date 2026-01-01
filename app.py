import streamlit as st
import requests
import os
import base64
from streamlit.components.v1 import html
from PIL import Image  # Pillowインポート追加
import io

# Grok APIキー
API_KEY = os.environ.get("XAI_API_KEY")
if not API_KEY:
    st.error("XAI_API_KEY が設定されていません。環境変数を設定してください。")
    st.stop()
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

if 'prompt_history' not in st.session_state:
    st.session_state.prompt_history = []

def analyze_image_with_grok(image_data):
    base64_image = base64.b64encode(image_data).decode('utf-8')
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this image in precise English detail, focusing only on visible elements. Structure as a single continuous paragraph prompt for Higgsfield Diffuse."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}
        ],
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    return "プロンプト生成に失敗しました。"

def merge_description_and_level(base_prompt, description, sex_level, tight_clothing, nipple_poke, ample_bust):
    level_desc = {
        1: "fully clothed, modest outfit, no cleavage or skin exposure",
        2: "slight skin exposure, form-fitting clothes, minimal cleavage",
        3: "visible cleavage, lingerie under open top or dress, sexy but still wearing clothes",
        4: "wearing only bikini or lingerie, no outer clothing, highly revealing",
        5: "nearly nude, minimal coverage, topless or fully nude"
    }[sex_level]
    strong_additions = []
    if tight_clothing:
        strong_additions.append("Make all clothing extremely tight-fitting, skin-tight, body-hugging, and clinging tightly to every curve of the body to strongly emphasize the figure.")
    if nipple_poke:
        strong_additions.append("Explicitly include visible nipple outlines, pokies, or erect nipples clearly poking through the thin fabric of the clothing.")
    if ample_bust:
        strong_additions.append("Strongly accentuate her ample bust and curvaceous figure, with clothing gently hugging her slender yet voluptuous body, revealing subtle minimal cleavage and slight skin exposure on her arms.")
    additional_instruction = " ".join(strong_additions)
    payload = {
        "model": "grok-4",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert prompt engineer for Higgsfield Diffuse. "
                           "Merge the base image prompt with the Japanese description and sexiness level. "
                           "Strictly override clothing and exposure according to the level. "
                           f"{additional_instruction} These additional instructions are mandatory and must be strongly reflected in the final prompt. "
                           "Output ONLY one single continuous English paragraph as the final prompt. "
                           "Start directly with 'A young...' or similar. "
                           "Never use bullet points, sections, headings, or structured format. "
                           "Do not add explanations."
            },
            {"role": "user", "content": f"Base prompt: {base_prompt}\nJapanese description: {description}\nSexiness level: {level_desc}"}
        ],
        "max_tokens": 600
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        raw = response.json()["choices"][0]["message"]["content"].strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        cleaned_lines = []
        for line in lines:
            if ':' in line and any(line.lower().startswith(sec) for sec in ['subject', 'appearance', 'clothing', 'action', 'environment', 'lighting', 'camera', 'style']):
                cleaned_lines.append(line.split(':', 1)[1].strip())
            else:
                cleaned_lines.append(line)
        final = ' '.join(cleaned_lines)
        final = final.replace('  ', ' ').strip()
        if final.startswith('"') and final.endswith('"'):
            final = final[1:-1].strip()
        return final
    return base_prompt

def optimize_prompt(prompt):
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "system", "content": "Optimize this prompt for Higgsfield Diffuse: make it shorter, clearer, more effective. Output only the single paragraph prompt."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    return prompt

def translate_to_japanese(prompt):
    payload = {
        "model": "grok-4",
        "messages": [
            {"role": "system", "content": "Translate to natural fluent Japanese."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROK_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"].strip()
    return "翻訳に失敗しました。"

# UI
st.title("Image to English Prompt Generator (Higgsfield向け)")

st.markdown("### セクシーレベル（全画像共通）")
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
    index=2
)

st.markdown("### 追加オプション（全画像共通）")
col_a, col_b, col_c = st.columns(3)
tight_clothing = col_a.checkbox("タイトな服装（ボディラインを強く強調）", value=False)
nipple_poke = col_b.checkbox("乳首ぽち（布越しに強く浮き出る）", value=False)
ample_bust = col_c.checkbox("豊満バスト強調（ample bust & curvaceous figure）", value=False)

st.markdown("### 画像構成オプション（全画像共通）")
col_d, col_e, col_f = st.columns(3)
mask_on = col_d.checkbox("白いマスク着用を追加", value=False)
iphone_selfie = col_e.checkbox("iPhoneを持って鏡自撮り構図", value=False)
face_hidden = col_f.checkbox("顔を生成しない（口から下または首から下のみ）", value=False)

uploaded_images = st.file_uploader("画像をアップロード（複数可）", type=["jpg", "jpeg", "png", "JPG", "JPEG", "PNG"], accept_multiple_files=True)
description = st.text_area("記述欄（任意・日本語可）：例：Gカップ、黒髪ロング、150cm", "")

if st.button("プロンプト生成"):
    if not uploaded_images:
        st.warning("画像を1枚以上アップロードしてください。")
    else:
        generated_prompts = []
        for idx, img in enumerate(uploaded_images):
            with st.expander(f"画像 {idx+1}: {img.name}"):
                try:
                    image_bytes = img.getvalue()
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    st.image(pil_image, caption="アップロード画像", use_column_width=True)
                    image_data = image_bytes
                except Exception as e:
                    st.error(f"画像 {idx+1} ({img.name}) は有効な画像ファイルではありません。対応形式（jpg/png）を確認してください。エラー: {str(e)}")
                    continue
                
                base_prompt = analyze_image_with_grok(image_data)
               
                with st.spinner(f"画像{idx+1}を処理中..."):
                    final_prompt = merge_description_and_level(
                        base_prompt, description.strip(), sex_level, tight_clothing, nipple_poke, ample_bust
                    )
               
                # 画像構成オプションをプロンプトに追加
                additional_elements = []
                if mask_on:
                    additional_elements.append("wearing a white surgical face mask covering nose and mouth")
                if iphone_selfie:
                    additional_elements.append("taking a mirror selfie in front of a mirror, holding iPhone smartphone with one hand")
                if face_hidden:
                    additional_elements.append("face hidden or cropped, only from mouth down or neck down visible, anonymous style")
                if additional_elements:
                    final_prompt = final_prompt.rstrip(".") + ", " + ", ".join(additional_elements) + "."
               
                generated_prompts.append(final_prompt)
                st.text_area(f"生成プロンプト {idx+1}（英語）", value=final_prompt, height=200, key=f"prompt_{idx}")
       
        st.session_state.prompt_history.extend(generated_prompts)

# 履歴
if st.session_state.prompt_history:
    st.markdown("### 生成履歴（最新10件）")
    for i, hist_prompt in enumerate(reversed(st.session_state.prompt_history[-10:])):
        hist_index = len(st.session_state.prompt_history) - 1 - i
        with st.expander(f"履歴 {hist_index + 1}: {hist_prompt[:60]}..."):
            st.text_area("プロンプト", value=hist_prompt, height=150, key=f"hist_{i}")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                html(f"<button onclick=\"navigator.clipboard.writeText(`{hist_prompt.replace('`', '\\`')}`)\">コピー</button>", height=40)
            with col2:
                st.download_button("ダウンロード", hist_prompt, file_name=f"prompt_{hist_index+1}.txt", key=f"dl_{i}")
            with col3:
                if st.button("最適化", key=f"opt_{i}"):
                    optimized = optimize_prompt(hist_prompt)
                    st.text_area("最適化後", value=optimized, height=150, key=f"opt_res_{i}")
            with col4:
                if st.button("日本語翻訳", key=f"trans_{i}"):
                    translated = translate_to_japanese(hist_prompt)
                    st.text_area("日本語", value=translated, height=150, key=f"jtrans_{i}")
