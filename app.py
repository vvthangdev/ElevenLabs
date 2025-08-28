# @title 🔊 Giao diện tạo giọng nói + phụ đề chính xác đa ngôn ngữ (SSML)
import os, re, requests, time, random
from pydub import AudioSegment
from datetime import datetime
from IPython.display import display, Audio, FileLink, clear_output
import ipywidgets as widgets
from google.colab import files

# ==== Giao diện ====
api_input = widgets.Textarea(value='', placeholder='Nhập các API key, mỗi dòng một key', description='🔑 API Key:', layout={'width': '100%', 'height': '100px'})
voice_id_input = widgets.Text(value='', placeholder='Nhập Voice ID', description='🗣️ Voice ID:', layout={'width': '100%'})
text_input = widgets.Textarea(value='', placeholder='Nhập văn bản cần tạo giọng...', description='📘 Văn bản:', layout={'width': '100%', 'height': '200px'})
model_dropdown = widgets.Dropdown(options=[("Eleven Multilingual v2", "eleven_multilingual_v2"), ("Eleven Flash v2.5", "eleven_flash_v2_5"), ("Eleven Turbo v2.5", "eleven_turbo_v2_5")], value="eleven_flash_v2_5", description='🎷 Model:')
slider_stability = widgets.FloatSlider(value=0.3, min=0, max=1.0, step=0.05, description='🔧 Stability')
slider_similarity = widgets.FloatSlider(value=0.75, min=0, max=1.0, step=0.05, description='🎻️ Similarity')
slider_style = widgets.FloatSlider(value=0.0, min=0, max=1.0, step=0.05, description='🎨 Style')
slider_speed = widgets.FloatSlider(value=1.0, min=0.7, max=1.2, step=0.05, description='⏩ Speed')
chk_boost = widgets.Checkbox(value=False, description='⚡ Optimize Streaming')
chk_ssml = widgets.Checkbox(value=False, description='🧠 Sử dụng SSML (SSML Mode)')
split_length = widgets.IntText(value=500, description='✂️ Split limit:')
subtitle_limit = widgets.IntText(value=3, description='📜 SRT từ/ký tự dòng:')
lang_dropdown = widgets.Dropdown(options=[("🇬🇧 English", "en"), ("🇻🇳 Vietnamese", "vi"), ("🇯🇵 Japanese", "ja"), ("🇨🇳 Chinese", "zh"), ("🇰🇷 Korean", "ko"), ("🇫🇷 French", "fr"), ("🇩🇪 German", "de"), ("🇮🇹 Italian", "it"), ("🇷🇺 Russian", "ru"), ("🇪🇸 Spanish", "es")], value="en", description='🌐 Ngôn ngữ phụ đề:')
text_stats = widgets.HTML(value="")
btn_generate = widgets.Button(description="🚀 Bắt đầu tạo giọng nói", button_style='success')
btn_download_segs = widgets.Button(description="⬇️ Tải đoạn lẻ", button_style='primary')
btn_download_srt = widgets.Button(description="📜 Tải phụ đề", button_style='info')
btn_download_full = widgets.Button(description="🎧 Tải đoạn gộp", button_style='primary')

# ==== Tiện ích ====
def convert_time(t):
    ms = int((t - int(t)) * 1000)
    h, m, s = int(t // 3600), int(t % 3600 // 60), int(t % 60)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def ultra_split(text, max_unit=5, lang='en'):
    items = list(text.strip()) if lang in ['ja', 'zh', 'ko'] else text.strip().split()
    chunks, temp = [], []
    for item in items:
        temp.append(item)
        if len(temp) >= max_unit:
            chunks.append(''.join(temp) if lang in ['ja', 'zh', 'ko'] else ' '.join(temp))
            temp = []
    if temp:
        chunks.append(''.join(temp) if lang in ['ja', 'zh', 'ko'] else ' '.join(temp))
    return chunks

def split_text(text, maxlen=500):
    sents = re.split(r'(?<=[.!?。！？])\s*', text)
    out, tmp = [], ""
    for s in sents:
        if len(tmp) + len(s) <= maxlen:
            tmp += s
        else:
            out.append(tmp.strip())
            tmp = s
    if tmp: out.append(tmp.strip())
    return out

def check_credit(api_key):
    try:
        r = requests.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": api_key})
        return r.json()['subscription']['character_limit'] - r.json()['subscription']['character_count']
    except: return None

def gen_audio(text, api_key, voice_id, model_id, settings, outname):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": settings,
        "text_type": "ssml" if chk_ssml.value or text.strip().lower().startswith("<speak>") else "plain"
    }
    r = requests.post(url, headers={"xi-api-key": api_key, "Content-Type": "application/json"}, json=payload)
    if r.status_code == 200:
        with open(outname, "wb") as f: f.write(r.content)
        return True
    else:
        try: return False, r.json().get("detail", {}).get("message", "Unknown error")
        except: return False, "Unknown error"

def generate_subtitles(paragraphs, folder="output_audio", file="output.srt", lang="en", unit=3):
    srt_path = os.path.join(folder, file)
    files = sorted([f for f in os.listdir(folder) if f.startswith("seg") and f.endswith(".mp3")])
    with open(srt_path, "w", encoding="utf-8") as srt:
        current_time, index = 0.0, 1
        for para, fname in zip(paragraphs, files):
            audio = AudioSegment.from_mp3(os.path.join(folder, fname))
            duration = audio.duration_seconds
            units = ultra_split(para, unit, lang)
            total_chars = sum(len(u) for u in units)
            for u in units:
                du = duration * (len(u) / total_chars)
                srt.write(f"{index}\n{convert_time(current_time)} --> {convert_time(current_time + du)}\n{u}\n\n")
                current_time += du
                index += 1
    return srt_path

# ==== Xử lý chính ====
def on_generate(b):
    clear_output()
    display(api_input, voice_id_input, text_input, model_dropdown,
            slider_stability, slider_similarity, slider_style, slider_speed,
            chk_boost, chk_ssml, split_length, subtitle_limit, lang_dropdown,
            text_stats, btn_generate, btn_download_segs, btn_download_srt, btn_download_full)

    apis = api_input.value.strip().splitlines()
    voice_id = voice_id_input.value.strip()
    fulltext = text_input.value.strip()
    lang = lang_dropdown.value
    paragraphs = split_text(fulltext, split_length.value)
    text_stats.value = f"<b>📊 Đoạn:</b> {len(paragraphs)} | <b>Ký tự:</b> {sum(len(p) for p in paragraphs):,}"

    print("🔍 Kiểm tra API:")
    credit_pool = []
    for i, key in enumerate(apis):
        credit = check_credit(key)
        credit_pool.append([key, credit])
        print(f"🔑 API #{i+1}: {credit:,} ký tự" if credit else f"❌ API #{i+1} lỗi")

    settings = {
        "stability": slider_stability.value,
        "similarity_boost": slider_similarity.value,
        "style": slider_style.value,
        "speed": slider_speed.value,
        "optimize_streaming_latency": 4 if chk_boost.value else 0
    }

    os.makedirs("output_audio", exist_ok=True)
    for f in os.listdir("output_audio"):
        if f.endswith(".mp3") or f.endswith(".srt") or f.endswith(".txt"):
            os.remove(os.path.join("output_audio", f))

    error_count = 0
    for i, para in enumerate(paragraphs):
        print(f"\n📘 Đoạn {i+1}: {para[:40]}...")
        for j, (key, credit) in enumerate(credit_pool):
            if credit and len(para) <= credit:
                success = gen_audio(para, key, voice_id, model_dropdown.value, settings, f"output_audio/seg{i+1}.mp3")
                if success is True:
                    credit_pool[j][1] -= len(para)
                    display(Audio(filename=f"output_audio/seg{i+1}.mp3"))
                    time.sleep(random.uniform(5, 10))
                    error_count = 0
                    break
                else:
                    print(f"❌ API #{j+1} lỗi: {success[1]}")
                    credit_pool[j][1] = 0
                    error_count += 1
                    if error_count >= 3:
                        print("⚠️ Gặp nhiều lỗi liên tiếp. Nghỉ 30 giây...")
                        time.sleep(30)
                        error_count = 0
            if j == len(credit_pool) - 1:
                print("⛔ Không còn API đủ quota!")
                return

    with open("output_audio/list.txt", "w") as f:
        for fmp3 in sorted(os.listdir("output_audio")):
            if fmp3.startswith("seg") and fmp3.endswith(".mp3"):
                f.write(f"file '{fmp3}'\n")
    os.system("ffmpeg -loglevel error -f concat -safe 0 -i output_audio/list.txt -c copy output_audio/full.mp3 -y")

    if os.path.exists("output_audio/full.mp3"):
        print("\n✅ Đã tạo file âm thanh:")
        display(Audio(filename="output_audio/full.mp3"))
    else:
        print("❌ Lỗi tạo full.mp3")

    srt = generate_subtitles(paragraphs, folder="output_audio", file="output.srt", lang=lang, unit=subtitle_limit.value)
    print("✅ Đã tạo phụ đề")

    btn_download_full.on_click(lambda b: files.download("output_audio/full.mp3"))
    btn_download_srt.on_click(lambda b: files.download(srt))
    btn_download_segs.on_click(lambda b: [files.download(os.path.join("output_audio", f)) for f in sorted(os.listdir("output_audio")) if f.startswith("seg") and f.endswith(".mp3")])

btn_generate.on_click(on_generate)

# ==== Hiển thị giao diện ====
display(api_input, voice_id_input, text_input, model_dropdown,
        slider_stability, slider_similarity, slider_style, slider_speed,
        chk_boost, chk_ssml, split_length, subtitle_limit, lang_dropdown,
        text_stats, btn_generate, btn_download_segs, btn_download_srt, btn_download_full)
