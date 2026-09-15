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
HISTORY_COLOR = "#FFFF00"  # 이전 서버 주소는 인게임 여부와 상관없이 항상 이 색
NUMBER_COLORS = ["#FF6B6B", "#FFA94D", "#74C0FC", "#DA77F2", "#63E6BE"]  # 1~5번 순번 색

class TransparentOverlay:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Server Overlay")

        saved_x, saved_y = self.load_config()
        self.root.geometry(f"+{saved_x}+{saved_y}")  # 크기는 지정하지 않고 내용물에 맞춰 자동으로 결정
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.82)  # 창 전체를 은은하게 반투명하게

        self.transparent_color = "#123456"
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)

        # 위쪽 가로형 손잡이 바 (검은 배경 없이 배경과 동화, 텍스트만 보임)
        self.drag_bar = tk.Label(
            root,
            text="⠿ 위치 이동",
            font=("Malgun Gothic", 8, "bold"),
            fg="#AAAAAA",
            bg=self.transparent_color,
            cursor="fleur",
            pady=2
        )
        self.drag_bar.pack(side=tk.TOP, fill=tk.X)

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
        self.label.pack(side=tk.TOP, fill=tk.X, anchor="w")

        # 이전 서버 더보기/접기 버튼 (히스토리가 2개 이상일 때만 표시)
        self.toggle_btn = tk.Label(
            root,
            text="",
            font=("Malgun Gothic", 10, "bold"),
            fg="#66CCFF",
            bg=self.transparent_color,
            cursor="hand2",
            padx=10
        )
        self.toggle_btn.bind("<Button-1>", self.toggle_history)

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
        self.current_session_info = None
        self.session_history = []  # 최근 접속했던 서버(현재 서버 제외), 최대 5개, 최신순
        self.history_expanded = False  # 더보기로 펼쳤는지 여부
        self.last_active_ip = None
        self.game_proc = None  # 매 루프마다 전체 프로세스 목록을 뒤지지 않도록 캐시
        self.last_rendered_key = "__unset__"  # 화면 내용이 실제로 바뀔 때만 다시 그리기 위한 값
        self.history_widgets = []  # 매번 새로 그리는 "이전 서버" 헤더/행 위젯들(정리용)

        self.setup_tray_icon()

        # 저장된 위치가 (해상도 변경 등으로) 화면 밖이면 시작할 때도 안 잘리게 보정
        self.root.update_idletasks()
        x, y = self.clamp_to_screen(self.root.winfo_x(), self.root.winfo_y())
        self.root.geometry(f"+{x}+{y}")

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
        x, y = self.clamp_to_screen(x, y)
        self.root.geometry(f"+{x}+{y}")

    def clamp_to_screen(self, x, y):
        """창이 화면 경계 밖으로 나가서 잘리지 않도록 좌표를 화면 안으로 제한한다."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        x = max(0, min(x, max(0, screen_w - win_w)))
        y = max(0, min(y, max(0, screen_h - win_h)))
        return x, y

    def stop_move(self, event):
        self.save_config(self.root.winfo_x(), self.root.winfo_y())

    def toggle_history(self, event=None):
        self.history_expanded = not self.history_expanded
        self.update_overlay(self.last_active_ip)

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

        self.current_session_info = (ip, port, geo)
        self.last_logged_session = session_id
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] IP: {ip}:{port} | 위치: {geo['country']} ({geo['city']}) | ISP: {geo['isp']}\n"

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"로그 기록 실패: {e}")

    def mark_server_left(self):
        """활성 서버 연결이 끊겼을 때(로비로 나가는 등) 그 서버를 '이전 서버' 기록으로 넘긴다.
        새 서버에 들어가는 순간이 아니라, 이전 서버에서 완전히 빠져나온 시점에만 기록에 뜨게 하기 위함."""
        if self.current_session_info is not None:
            self.session_history.insert(0, self.current_session_info)
            self.session_history = self.session_history[:5]
            self.current_session_info = None
        self.last_logged_session = None

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

    def find_game_process(self, target_name):
        """매번 전체 프로세스 목록을 훑지 않고, 캐시된 핸들이 살아있으면 그대로 재사용한다."""
        if self.game_proc is not None:
            try:
                if self.game_proc.is_running() and self.game_proc.name().lower() == target_name:
                    return self.game_proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            self.game_proc = None

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info['name']
                if pname and pname.lower() == target_name:
                    self.game_proc = proc
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def monitor_loop(self):
        target_name = "prospect-win64-shipping.exe"
        # "net" 키워드 추가
        exclude_keywords = ["valve", "steam", "cloudflare", "akamai", "discord", "fastly", "google cloud", "google llc", "nvidia", "microsoft azure", "daum", "amazon", "net"]
        exclude_countries = ["united kingdom", "영국", "uk", "great britain"]

        while self.is_running:
            now = time.time()

            game_proc = self.find_game_process(target_name)

            if not game_proc:
                self.target_udp_ports.clear()
                self.udp_active_ips.clear()
                self.mark_server_left()
                self.request_overlay_update(None)
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

            if active_ip is None:
                self.mark_server_left()

            self.request_overlay_update(active_ip)
            time.sleep(2)

    def request_overlay_update(self, active_ip):
        """내용이 실제로 바뀔 때만 GUI 스레드에 다시 그리라고 요청한다(불필요한 재렌더/geometry 계산 방지)."""
        key = (active_ip[0], active_ip[1]) if active_ip else None
        if key == self.last_rendered_key:
            return
        self.last_rendered_key = key
        self.root.after(0, self.update_overlay, active_ip)

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
        self.last_active_ip = active_ip

        # 현재 접속한 서버만 인게임(초록)/탐색 중(노랑) 색이 바뀐다.
        if active_ip:
            ip, port, geo = active_ip
            lines = [f"📍 위치: {geo['country']} ({geo['city']})", f"IP: {ip}:{port}"]
            color = "#00FF00"
        else:
            lines = ["🌐 서버 탐색 중..."]
            color = "#FFFF00"
        self.label.config(text="\n".join(lines), fg=color)

        # 이전 서버 목록은 항상 pack_forget 후 다시 그린다(순번 색이 있어 줄마다 위젯이 필요함).
        self.toggle_btn.pack_forget()
        for widget in self.history_widgets:
            widget.destroy()
        self.history_widgets = []

        if self.session_history:
            header = tk.Label(
                self.root, text="── 이전 서버 ──", font=("Malgun Gothic", 10),
                fg="#888888", bg=self.transparent_color, anchor="w"
            )
            header.pack(side=tk.TOP, fill=tk.X, padx=10)
            self.history_widgets.append(header)

            visible = self.session_history if self.history_expanded else self.session_history[:1]
            for i, (hip, hport, hgeo) in enumerate(visible, start=1):
                row = tk.Frame(self.root, bg=self.transparent_color)
                num_color = NUMBER_COLORS[(i - 1) % len(NUMBER_COLORS)]
                num_label = tk.Label(
                    row, text=f"{i}.", font=("Malgun Gothic", 11, "bold"),
                    fg=num_color, bg=self.transparent_color
                )
                num_label.pack(side=tk.LEFT)
                addr_label = tk.Label(
                    row, text=f" {hip}:{hport} ({hgeo['country']})", font=("Malgun Gothic", 11),
                    fg=HISTORY_COLOR, bg=self.transparent_color
                )
                addr_label.pack(side=tk.LEFT)
                row.pack(side=tk.TOP, fill=tk.X, padx=10, anchor="w")
                self.history_widgets.append(row)

        remaining = len(self.session_history) - 1
        if remaining > 0:
            self.toggle_btn.config(text=("접기 ▲" if self.history_expanded else f"더보기 ▼ (+{remaining})"))
            self.toggle_btn.pack(side=tk.TOP, fill=tk.X)

        # 내용이 바뀌어 창 크기가 달라져도 화면 밖으로 잘리지 않게 위치 재보정
        self.root.update_idletasks()
        x, y = self.clamp_to_screen(self.root.winfo_x(), self.root.winfo_y())
        self.root.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TransparentOverlay(root)
    root.mainloop()
