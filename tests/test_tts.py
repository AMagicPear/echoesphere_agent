import requests
import dotenv
import os
import subprocess
import tempfile

dotenv.load_dotenv()

url = "https://api.minimaxi.com/v1/t2a_v2"
headers = {
    "Authorization": f"Bearer {os.environ['MINIMAX_API_KEY']}",
    "Content-Type": "application/json",
}
payload = {
    "model": "speech-2.8-turbo",
    "text": "你好，这是测试语音",
    "stream": False,
    "voice_setting": {"voice_id": "Chinese (Mandarin)_Warm_Girl"},
    "audio_setting": {"sample_rate": 32000, "format": "mp3"},
}

response = requests.post(url, headers=headers, json=payload)
response.raise_for_status()

result = response.json()
hex_audio = result["data"]["audio"]
audio_bytes = bytes.fromhex(hex_audio)

with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
    f.write(audio_bytes)
    tmp_path = f.name

subprocess.run(["afplay", tmp_path])
os.unlink(tmp_path)
