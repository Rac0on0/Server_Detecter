import sys
import os
import json
import tkinter as tk
import psutil
import requests
import threading
import time
import socket
import struct
import pystray
from datetime import datetime
from PIL import Image, ImageDraw

CONFIG_FILE = "config.json"
ICON_FILE = "icon.png"
LOG_FILE = "server_log.txt"

class TransparentOverlay:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Server Overlay")

        saved_x, saved_y = self.load_config()
        self.root.geometry(f"340x70+{saved_x}+{saved_y}")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)

        self.transparent_color = "#123456"
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)

        # 오른쪽 세로형 손잡이 바
        self.drag_bar = tk.Label(
            root,
            text="위\n치\n이\n동",
            font=("Malgun Gothic", 7, "bold"),
            fg="#AAAAAA",
            bg="#000000",
            cursor="fleur",
            padx=4
        )
        self.drag_bar.pack(side=tk.RIGHT, fill=tk.Y)

        # 서버 정보 표시 라벨
        self.label = tk.Label(
            root,
            text="🌐 서버 탐색 중...",
            font=("Malgun Gothic", 11, "bold"),
            fg="#FFFF00",
            bg=self.transparent_color,
            justify=tk.LEFT,
            padx=10,
            pady=5
        )
        self.label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 마우스 드래그 이동 바인딩
        self.drag_bar.bind("<Button-1>", self.start_move)
        self.drag_bar.bind("<B1-Motion>", self.do_move)
        self.drag_bar.bind("<ButtonRelease-1>", self.stop_move)

        self.label.bind("<Button-1>", self.start_move)
        self.label.bind("<B1-Motion>", self.do_move)
        self.label.bind("<ButtonRelease-1>", self.stop_move)

        self.is_running = True
        self.cache = {}
        self.target_udp_ports = set()
        self.udp_active_ips = {}
        self.last_logged_session = None

        self.setup_tray_icon()

        threading.Thread(target=self.udp_sniffer_loop, daemon=True).start()
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def stop_move(self, event):
        self.save_config(self.root.winfo_x(), self.root.winfo_y())

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("x", 30), data.get("y", 30)
            except Exception:
                pass
        return 30, 30

    def save_config(self, x, y):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"x": x, "y": y}, f)
        except Exception:
            pass

    def log_server_session(self, ip, port, geo):
        session_id = f"{ip}:{port}"
        if self.last_logged_session == session_id:
            return

        self.last_logged_session = session_id
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] IP: {ip}:{port} | 위치: {geo['country']} ({geo['city']}) | ISP: {geo['isp']}\n"

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"로그 기록 실패: {e}")

    def create_tray_image(self):
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, ICON_FILE)
        else:
            icon_path = os.path.join(os.path.abspath("."), ICON_FILE)

        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                img = img.convert('RGBA')
                return img.resize((32, 32), Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"아이콘 로드 실패: {e}")

        image = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, 28, 28), fill=(0, 255, 0, 255))
        return image

    def setup_tray_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("종료", self.quit_app)
        )
        self.tray_icon = pystray.Icon("ServerOverlay", self.create_tray_image(), "서버 탐지기", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def quit_app(self, icon=None, item=None):
        self.save_config(self.root.winfo_x(), self.root.winfo_y())
        self.is_running = False
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def udp_sniffer_loop(self):
        local_ip = self.get_local_ip()
        try:
            sniffer = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
            sniffer.bind((local_ip, 0))
            sniffer.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
            sniffer.settimeout(1.0)
        except Exception:
            return

        while self.is_running:
            try:
                raw_data, _ = sniffer.recvfrom(65535)
                if len(raw_data) < 28:
                    continue
                
                ip_header = raw_data[:20]
                iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
                version_ihl = iph[0]
                ihl = (version_ihl & 0xF) * 4
                protocol = iph[6]
                src_ip = socket.inet_ntoa(iph[8])
                dst_ip = socket.inet_ntoa(iph[9])

                if protocol == 17:
                    udp_header = raw_data[ihl:ihl+8]
                    if len(udp_header) < 8:
                        continue
                    src_port, dst_port, _, _ = struct.unpack('!HHHH', udp_header)

                    if src_port in self.target_udp_ports or dst_port in self.target_udp_ports:
                        if src_ip == local_ip:
                            target_ip = dst_ip
                            server_port = dst_port
                        else:
                            target_ip = src_ip
                            server_port = src_port

                        if not self.is_private_ip(target_ip):
                            self.udp_active_ips[target_ip] = (time.time(), server_port)
            except socket.timeout:
                continue
            except Exception:
                continue

        try:
            sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
            sniffer.close()
        except Exception:
            pass

    def is_private_ip(self, ip):
        if ip in ('127.0.0.1', '0.0.0.0', '255.255.255.255'):
            return True
        if ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.16.') or ip.startswith('224.'):
            return True
        return False

    def monitor_loop(self):
        target_name = "prospect-win64-shipping.exe"
        # "net" 키워드 추가
        exclude_keywords = ["valve", "steam", "cloudflare", "akamai", "discord", "fastly", "google cloud", "google llc", "nvidia", "microsoft azure", "daum", "amazon", "net"]
        exclude_countries = ["united kingdom", "영국", "uk", "great britain"]

        while self.is_running:
            now = time.time()

            game_proc = None
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pname = proc.info['name']
                    if pname and pname.lower() == target_name:
                        game_proc = proc
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if not game_proc:
                self.target_udp_ports.clear()
                self.udp_active_ips.clear()
                self.last_logged_session = None
                self.root.after(0, self.update_overlay, None)
                time.sleep(2)
                continue

            active_ports = set()
            try:
                for c in game_proc.connections(kind='udp'):
                    if c.laddr and c.laddr.port != 0:
                        active_ports.add(c.laddr.port)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            self.target_udp_ports = active_ports

            valid_ips = []
            for ip, val in list(self.udp_active_ips.items()):
                last_time, port = val
                if now - last_time < 2.0:
                    valid_ips.append((ip, last_time, port))
                else:
                    del self.udp_active_ips[ip]

            valid_ips.sort(key=lambda x: x[1], reverse=True)

            active_ip = None
            for ip, _, port in valid_ips:
                geo = self.get_geoip(ip)
                isp_lower = geo["isp"].lower()
                country_lower = geo["country"].lower()

                if any(k in isp_lower for k in exclude_keywords):
                    continue

                if any(c in country_lower for c in exclude_countries):
                    continue

                active_ip = (ip, port, geo)
                self.log_server_session(ip, port, geo)
                break

            self.root.after(0, self.update_overlay, active_ip)
            time.sleep(2)

    def get_geoip(self, ip):
        if ip in self.cache:
            return self.cache[ip]
        try:
            res = requests.get("http://ip-api.com/json/" + str(ip) + "?lang=ko", timeout=3).json()
            if res.get("status") == "success":
                info = {
                    "country": res.get("country", "Unknown"),
                    "city": res.get("city", "Unknown"),
                    "isp": res.get("org") or res.get("isp", "Unknown")
                }
            else:
                info = {"country": "Unknown", "city": "-", "isp": "-"}
        except Exception:
            info = {"country": "Error", "city": "-", "isp": "-"}
        
        self.cache[ip] = info
        return info

    def update_overlay(self, active_ip):
        if active_ip:
            ip, port, geo = active_ip
            line1 = f"📍 위치: {geo['country']} ({geo['city']})"
            line2 = f"IP: {ip}:{port}"
            
            display_text = f"{line1}\n{line2}"
            self.label.config(text=display_text, fg="#00FF00")
        else:
            self.label.config(text="🌐 서버 탐색 중...", fg="#FFFF00")

if __name__ == "__main__":
    root = tk.Tk()
    app = TransparentOverlay(root)
    root.mainloop()
