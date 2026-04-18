import os
import sys
import threading
import json
import socket
import traceback
import subprocess
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

# --- TERMİNAL PENCERESİNİ OTOMATİK GİZLE ---
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        hWnd = kernel32.GetConsoleWindow()
        if hWnd:
            user32.ShowWindow(hWnd, 0)
    except Exception:
        pass

# --- HATA GÜNLÜĞÜ (LOGLAMA) ---
def log_error(e_msg):
    try:
        with open("error_log.txt", "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now()} ---\n{e_msg}\n\n")
    except:
        pass

# --- WATCHDOG (KENDİNİ KORUMA) ---
def start_watchdog():
    if getattr(sys, 'frozen', False):
        curr_exe = sys.executable
        watchdog_script = f"""
        @echo off
        :loop
        tasklist | find /i "{os.path.basename(curr_exe)}" >nul
        if errorlevel 1 (
            start "" "{curr_exe}"
        )
        timeout /t 5 >nul
        goto loop
        """
        with open("guard.bat", "w") as f:
            f.write(watchdog_script)
        subprocess.Popen("guard.bat", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)

# --- KÜTÜPHANE KONTROLÜ ---
try:
    import http.server
    import socketserver
    import tkinter as tk
    from tkinter import messagebox
    from PIL import Image, ImageTk, ImageGrab
    import qrcode
    import pystray
    from pystray import MenuItem as item
except ImportError as e:
    log_error(f"Kütüphane hatası: {e}")
    sys.exit(1)

# --- TASARIM SABİTLERİ ---
COLOR_BG_RIGHT = "#0F111A"
COLOR_BG_LEFT = "#1A1C24"
COLOR_ACCENT = "#722ED1"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_DIM = "#8C8C8C"
COLOR_DANGER = "#EF4444"
API_PORT = 65432

# --- WEB ARAYÜZÜ HTML (PIN KONTROLLÜ) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartLock Panel</title>
    <style>
        body { background: #0F111A; color: white; font-family: sans-serif; text-align: center; padding: 20px; }
        .card { background: #1A1C24; border-radius: 15px; padding: 20px; max-width: 400px; margin: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        h1 { color: #722ED1; margin-bottom: 10px; }
        input { width: 80%; padding: 12px; margin: 10px 0; border-radius: 8px; border: 1px solid #333; background: #0F111A; color: white; font-size: 16px; text-align: center; }
        button { width: 85%; padding: 12px; margin: 5px; border-radius: 8px; border: none; font-weight: bold; cursor: pointer; transition: 0.3s; }
        .btn-unlock { background: #52C41A; color: white; }
        .btn-lock { background: #F5222D; color: white; }
        .btn-msg { background: #722ED1; color: white; }
        button:hover { opacity: 0.8; transform: scale(1.02); }
    </style>
</head>
<body>
    <div class="card">
        <h1>SmartLock</h1>
        <p style="color: #8C8C8C;">Güvenli Yönetim Paneli</p>
        <hr style="border: 0; border-top: 1px solid #333; margin: 20px 0;">
        
        <input type="password" id="pin" placeholder="Yönetici PIN Kodunu Girin">
        
        <button class="btn-unlock" onclick="send('unlock')">KİLİDİ AÇ</button>
        <button class="btn-lock" onclick="send('lock')">TAHTAYI KİLİTLE</button>
        
        <input type="text" id="msg" placeholder="Kilit ekranına mesaj gönder...">
        <button class="btn-msg" onclick="sendMsg()">MESAJI YAYINLA</button>
    </div>

    <script>
        function send(action) {
            const pin = document.getElementById('pin').value;
            if(!pin) { alert("PIN kodu girmelisiniz!"); return; }
            fetch(`/cmd?action=${action}&pin=${pin}`)
            .then(r => r.text())
            .then(t => {
                if(t === "OK") alert("İşlem Başarılı");
                else alert("Hata: " + t);
            });
        }
        function sendMsg() {
            const pin = document.getElementById('pin').value;
            const msg = document.getElementById('msg').value;
            fetch(`/cmd?action=set_msg&val=${encodeURIComponent(msg)}&pin=${pin}`)
            .then(r => r.text())
            .then(t => alert(t === "OK" ? "Mesaj Gönderildi" : "Hata: " + t));
        }
    </script>
</body>
</html>
"""

class SmartLockServer:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartLock Safety")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.attributes("-fullscreen", True, "-topmost", True)
        self.root.configure(bg=COLOR_BG_RIGHT)
        
        self.is_locked = True
        self.admin_pin = "1234" # Varsayılan Admin Kodu
        self.admin_message = ""
        
        self.config_file = "smartlock_config.json"
        self.load_config()

        self.setup_ui()
        self.start_api_server()
        self.update_clock()
        self.setup_tray()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except:
                self.config = {"school": "SmartLock Eğitim Sistemleri", "class": "GÜVENLİ MOD AKTİF"}
        else:
            self.config = {"school": "SmartLock Eğitim Sistemleri", "class": "GÜVENLİ MOD AKTİF"}
            self.save_config()

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def setup_ui(self):
        for widget in self.root.winfo_children(): widget.destroy()
        
        # Sol Panel
        self.left_panel = tk.Frame(self.root, bg=COLOR_BG_LEFT, width=450)
        self.left_panel.pack(side="left", fill="y")
        self.left_panel.pack_propagate(False)
        
        tk.Frame(self.left_panel, bg=COLOR_ACCENT, height=5).pack(fill="x")
        self.lbl_time = tk.Label(self.left_panel, text="00:00", font=("Inter", 80, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_LEFT)
        self.lbl_time.pack(pady=(60, 0))
        self.lbl_date = tk.Label(self.left_panel, text="", font=("Inter", 16), fg=COLOR_TEXT_DIM, bg=COLOR_BG_LEFT)
        self.lbl_date.pack(pady=(0, 40))
        tk.Label(self.left_panel, text=self.config.get("school"), font=("Inter", 20, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_LEFT, wraplength=400).pack(pady=20)

        qr_container = tk.Frame(self.left_panel, bg="white", padx=10, pady=10)
        qr_container.pack(pady=30)
        self.qr_label = tk.Label(qr_container, bg="white")
        self.qr_label.pack()
        self.update_qr()

        # Sağ Panel
        self.right_panel = tk.Frame(self.root, bg=COLOR_BG_RIGHT)
        self.right_panel.pack(side="right", fill="both", expand=True)
        center = tk.Frame(self.right_panel, bg=COLOR_BG_RIGHT)
        center.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(center, text="🔒", font=("Segoe UI Emoji", 120), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_RIGHT).pack()
        tk.Label(center, text="SmartLock", font=("Inter", 64, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_RIGHT).pack(pady=10)
        
        self.lbl_status = tk.Label(center, text=self.config.get("class"), font=("Inter", 20), fg=COLOR_TEXT_DIM, bg=COLOR_BG_RIGHT)
        self.lbl_status.pack()
        
        self.lbl_admin_msg = tk.Label(center, text="", font=("Inter", 18, "italic"), fg=COLOR_ACCENT, bg=COLOR_BG_RIGHT, wraplength=600)
        self.lbl_admin_msg.pack(pady=30)

    def update_qr(self):
        try:
            ip = socket.gethostbyname(socket.gethostname())
            qr = qrcode.make(f"http://{ip}:{API_PORT}").resize((200, 200))
            self.qr_img = ImageTk.PhotoImage(qr)
            self.qr_label.config(image=self.qr_img)
        except: pass

    def update_clock(self):
        now = datetime.now()
        self.lbl_time.config(text=now.strftime("%H:%M"))
        self.lbl_date.config(text=now.strftime("%d %B %Y").upper())
        
        # Admin mesajını güncelle
        if hasattr(self, 'lbl_admin_msg'):
            self.lbl_admin_msg.config(text=self.admin_message)

        if self.is_locked:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.lift()
        else:
            self.root.withdraw()
        self.root.after(1000, self.update_clock)

    def setup_tray(self):
        def quit_app(icon, item):
            icon.stop()
            os._exit(0)
        
        def show_lock(icon, item):
            self.is_locked = True
            self.root.after(0, self.root.deiconify)

        try:
            icon_path = "CYK.png"
            img = Image.open(icon_path) if os.path.exists(icon_path) else Image.new('RGB', (64, 64), COLOR_ACCENT)
            menu = (item('Kilitle', show_lock), item('Çıkış', quit_app))
            self.icon = pystray.Icon("SmartLock", img, "SmartLock Safety", menu)
            threading.Thread(target=self.icon.run, daemon=True).start()
        except Exception as e:
            log_error(f"Tray hatası: {e}")

    def start_api_server(self):
        outer = self
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                parsed = urlparse(self.path)
                p = parse_qs(parsed.query)
                action = p.get('action', [None])[0]
                pin_sent = p.get('pin', [None])[0]
                val = p.get('val', [""])[0]

                if parsed.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
                    return

                if parsed.path == '/cmd':
                    # PIN Doğrulaması
                    if pin_sent != outer.admin_pin:
                        self.send_response(403)
                        self.end_headers()
                        self.wfile.write(b"Gecersiz PIN Kodu!")
                        return

                    if action == "unlock":
                        outer.is_locked = False
                    elif action == "lock":
                        outer.is_locked = True
                    elif action == "set_msg":
                        outer.admin_message = unquote(val)
                    
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    self.send_response(404)
                    self.end_headers()

        threading.Thread(target=lambda: socketserver.TCPServer(("", API_PORT), H).serve_forever(), daemon=True).start()

if __name__ == "__main__":
    if getattr(sys, 'frozen', False): start_watchdog()
    root = tk.Tk()
    app = SmartLockServer(root)
    root.mainloop()