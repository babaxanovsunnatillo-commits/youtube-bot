import requests
import subprocess
import os
import asyncio
import json
import edge_tts
from PIL import Image, ImageDraw, ImageFilter

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1"
OUTPUT = "C:/Projects/youtube/output"
SCRIPTS = "C:/Projects/youtube/scripts"
VOICE = "en-US-ChristopherNeural"

def get_trending_topic():
    print("🔥 Ищем тему...")
    prompt = """Generate ONE viral YouTube title for US audience 2026.
Topic: personal finance or AI tools. High CPM niche.
ONE title only, nothing else."""
    r = requests.post(f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=60)
    topic = r.json()["response"].strip().strip('"')
    print(f"✅ Тема: {topic}")
    return topic

def generate_scenes(topic):
    print("📝 Генерируем сцены...")
    prompt = f"""Write a 3-minute YouTube script about: {topic}
Output ONLY a JSON array, no text before or after.
Each object:
- "scene_number": number
- "audio_text": spoken words only
- "title": short slide title (max 4 words)
- "subtitle": one line description (max 6 words)
- "color": background color as hex (dark colors like #0a0a2e or #1a0a2e or #0a1a2e)
Minimum 6 scenes. Output ONLY valid JSON."""
    r = requests.post(f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=180)
    response = r.json()["response"]
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        scenes = json.loads(response[start:end])
        print(f"✅ {len(scenes)} сцен готово!")
        return scenes
    except:
        print("⚠️ Используем простой режим...")
        return None

async def generate_audio_async(text, path):
    communicate = edge_tts.Communicate(text[:4000], VOICE)
    await communicate.save(path)

def generate_audio(scenes, topic):
    print("🎙️ Озвучка...")
    if scenes:
        text = " ".join([s["audio_text"] for s in scenes])
    else:
        text = topic
    path = f"{OUTPUT}/audio.mp3"
    asyncio.run(generate_audio_async(text, path))
    print("✅ Аудио готово!")
    return path

def create_slide(scene, index, total):
    w, h = 1280, 720
    
    color_hex = scene.get("color", "#0a0a2e").lstrip("#")
    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)
    
    img = Image.new("RGB", (w, h), color=(r, g, b))
    draw = ImageDraw.Draw(img)
    
    # Градиентные полосы
    for i in range(h):
        alpha = i / h
        dr = int(r * (1 - alpha * 0.5))
        dg = int(g * (1 - alpha * 0.5))
        db = int(b + (50 * alpha))
        draw.line([(0, i), (w, i)], fill=(dr, dg, db))
    
    # Декоративные линии
    draw.rectangle([0, 0, w, 6], fill=(255, 50, 50))
    draw.rectangle([0, h-6, w, h], fill=(255, 200, 0))
    draw.rectangle([0, 0, 6, h], fill=(255, 50, 50))
    draw.rectangle([w-6, 0, w, h], fill=(255, 200, 0))
    
    # Номер сцены
    draw.text((60, 50), f"{index}/{total}", fill=(255, 255, 255, 128), anchor="lm")
    
    # Заголовок
    title = scene.get("title", "").upper()
    draw.text((w//2 + 2, h//2 - 42), title, fill=(0, 0, 0), anchor="mm")
    draw.text((w//2, h//2 - 44), title, fill=(255, 255, 255), anchor="mm")
    
    # Подзаголовок
    subtitle = scene.get("subtitle", "")
    draw.text((w//2, h//2 + 40), subtitle, fill=(255, 200, 0), anchor="mm")
    
    # Нижняя плашка
    draw.rectangle([0, h-70, w, h-6], fill=(0, 0, 0, 128))
    draw.text((w//2, h-38), "2026 • AI & MONEY", fill=(255, 255, 255), anchor="mm")
    
    path = f"{OUTPUT}/slide_{index:02d}.png"
    img.save(path)
    return path

def create_slides(scenes, topic):
    print("🖼️ Создаём слайды...")
    if not scenes:
        scenes = [
            {"title": topic[:20], "subtitle": "Watch till the end!", "color": "#0a0a2e", "audio_text": ""},
        ]
    slides = []
    for i, scene in enumerate(scenes):
        path = create_slide(scene, i+1, len(scenes))
        slides.append(path)
    print(f"✅ {len(slides)} слайдов готово!")
    return slides

def generate_video(slides, audio_path):
    print("🎬 Создаём видео со слайдами...")
    
    audio_info = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True, text=True)
    
    try:
        duration = float(json.loads(audio_info.stdout)["format"]["duration"])
    except:
        duration = 180
    
    slide_duration = duration / len(slides)
    
    # Создаём список слайдов для ffmpeg
    list_file = f"{OUTPUT}/slides.txt"
    with open(list_file, "w") as f:
        for slide in slides:
            f.write(f"file '{slide}'\n")
            f.write(f"duration {slide_duration:.2f}\n")
        f.write(f"file '{slides[-1]}'\n")
    
    video_no_audio = f"{OUTPUT}/video_no_audio.mp4"
    final_video = f"{OUTPUT}/video.mp4"
    
    # Собираем слайды в видео
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
        "-pix_fmt", "yuv420p", "-r", "24",
        video_no_audio
    ], capture_output=True)
    
    # Добавляем аудио
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_no_audio,
        "-i", audio_path,
        "-shortest", "-c:v", "copy", "-c:a", "aac",
        final_video
    ], capture_output=True)
    
    print("✅ Видео готово!")
    return final_video

def make_video():
    print("\n🚀 ЗАПУСКАЕМ АВТОМАТИЗАЦИЮ\n")
    topic = get_trending_topic()
    scenes = generate_scenes(topic)
    audio = generate_audio(scenes, topic)
    slides = create_slides(scenes, topic)
    video = generate_video(slides, audio)
    os.startfile(video)
    print(f"\n🎉 ГОТОВО!")
    print(f"📌 Тема: {topic}")
    print(f"📁 Видео: {video}")

make_video()