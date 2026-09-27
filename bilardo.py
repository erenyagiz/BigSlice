import tkinter as tk
from tkinter import messagebox, simpledialog, font
import threading
import time
import math
import os
import platform
import subprocess
from datetime import datetime

# --- Platforma Göre Font ---
# "Helvetica Neue" Windows'ta bulunmaz; Windows'ta Segoe UI kullanılır.
if platform.system() == "Windows":
    UI_FONT = "Segoe UI"
elif platform.system() == "Darwin":
    UI_FONT = "Helvetica Neue"
else:
    UI_FONT = "DejaVu Sans"

# --- Modern Renk Paleti ---
BG_COLOR = "#1e1e1e"          # Ana Arkaplan (Çok koyu gri)
CARD_BG = "#2d2d2d"           # Kart Arkaplanı (Biraz daha açık)
TEXT_COLOR_PRIMARY = "#99FFFF"    # Ana Metin
TEXT_COLOR_SECONDARY = "#a0a0a0"  # İkincil Metin (Açık gri)
ACCENT_COLOR_ACTIVE = "#2ecc71"   # Aktif/Yeşil (Masa dolu)
ACCENT_COLOR_INACTIVE = "#e74c3c" # Pasif/Kırmızı (Masa boş/durduruldu)
ACCENT_COLOR_INFO = "#3498db"     # Bilgi/Mavi (Saat düzenle)
BORDER_COLOR = "#444444"

# Buton Renk Paleti ( macOS ve Windows Uyumlu )
BTN_START_BG = "#2ecc71"          # Başlat Canlı Yeşil
BTN_START_ACTIVE = "#27ae60"
BTN_STOP_BG = "#e74c3c"           # Durdur Canlı Kırmızı
BTN_STOP_ACTIVE = "#c0392b"
BTN_EDIT_BG = "#3498db"           # Düzenle Mavi
BTN_EDIT_ACTIVE = "#2980b9"
BTN_RESET_BG = "#e67e22"          # Sıfırla Canlı Turuncu
BTN_RESET_ACTIVE = "#d35400"
BTN_DISABLED_BG = "#3a3a3a"       # Pasif Buton Arkaplanı
BTN_DISABLED_FG = "#888888"       # Pasif Buton Metin Rengi (Belirgin Gri)

TICK_INTERVAL_MS = 200            # Ekran kontrol aralığı (ms)


class ModernButton(tk.Label):
    """
    macOS ve Windows üzerinde renk kaybı ve grileşme olmadan
    tam uyumlu çalışan özel modern buton bileşeni.
    """
    def __init__(self, master, text="", command=None, bg="#2ecc71", fg="white",
                 active_bg=None, disabled_bg=BTN_DISABLED_BG, disabled_fg=BTN_DISABLED_FG,
                 font=None, state="normal", padx=10, pady=8, width=12, **kwargs):
        super().__init__(
            master, text=text, font=font, padx=padx, pady=pady, width=width,
            relief=tk.FLAT, bd=0, **kwargs
        )
        self.command = command
        self.normal_bg = bg
        self.normal_fg = fg
        self.active_bg = active_bg or bg
        self.disabled_bg = disabled_bg
        self.disabled_fg = disabled_fg
        self.state = state

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        self._update_appearance()

    def _is_disabled(self):
        return self.state == "disabled" or self.state == tk.DISABLED

    def _update_appearance(self):
        if self._is_disabled():
            super().config(bg=self.disabled_bg, fg=self.disabled_fg, cursor="arrow")
        else:
            super().config(bg=self.normal_bg, fg=self.normal_fg, cursor="hand2")

    def _on_enter(self, event):
        if not self._is_disabled() and self.active_bg:
            super().config(bg=self.active_bg)

    def _on_leave(self, event):
        if not self._is_disabled():
            super().config(bg=self.normal_bg)

    def _on_click(self, event):
        if not self._is_disabled() and self.command:
            self.command()

    def config(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs.pop("state")
        if "bg" in kwargs:
            self.normal_bg = kwargs.pop("bg")
        if "fg" in kwargs:
            self.normal_fg = kwargs.pop("fg")
        if "active_bg" in kwargs:
            self.active_bg = kwargs.pop("active_bg")
        if "disabled_bg" in kwargs:
            self.disabled_bg = kwargs.pop("disabled_bg")
        if "disabled_fg" in kwargs:
            self.disabled_fg = kwargs.pop("disabled_fg")
        super().config(**kwargs)
        self._update_appearance()

    def configure(self, **kwargs):
        self.config(**kwargs)


class ModernBilliardsTable:
    def __init__(self, master, table_number, default_minutes=30):
        self.table_number = table_number
        self.default_seconds = default_minutes * 60
        self.remaining_seconds = self.default_seconds
        self.is_running = False

        # Zamanlayıcı durumu (thread yerine tkinter after döngüsü)
        self._tick_job = None     # Planlanmış after() görevinin kimliği
        self._end_time = None     # Sürenin biteceği an (time.monotonic cinsinden)

        # Özel Fontlar
        self.font_large = font.Font(family=UI_FONT, size=32, weight="bold")
        self.font_medium = font.Font(family=UI_FONT, size=13, weight="bold")
        self.font_small = font.Font(family=UI_FONT, size=11)

        # Ana Çerçeve (Kenarlıklı kart)
        self.frame = tk.Frame(master, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.frame.pack(side=tk.LEFT, padx=12, pady=10, expand=True, fill="both")

        # Masa Başlığı
        header_label = tk.Label(self.frame, text=f"MASA {self.table_number}", font=self.font_small,
                                fg=TEXT_COLOR_SECONDARY, bg=CARD_BG)
        header_label.pack(pady=(12, 3))

        # Süre Göstergesi (Tıklayarak da düzenlenebilir)
        self.time_label = tk.Label(
            self.frame, text=self.format_time(self.remaining_seconds),
            font=self.font_large, fg=ACCENT_COLOR_INACTIVE, bg=CARD_BG,
            cursor="hand2"
        )
        self.time_label.pack(pady=3)
        self.time_label.bind("<Button-1>", lambda e: self.edit_remaining_time())

        # Durum Göstergesi (Metin + Renkli Nokta)
        status_frame = tk.Frame(self.frame, bg=CARD_BG)
        status_frame.pack(pady=(0, 10))

        # Renkli Durum Noktası (Yuvarlak Canvas)
        self.status_canvas = tk.Canvas(status_frame, width=15, height=15, bg=CARD_BG, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.status_circle = self.status_canvas.create_oval(2, 2, 13, 13, fill=ACCENT_COLOR_INACTIVE, outline="")

        self.status_label = tk.Label(status_frame, text="Boş / Bekliyor", font=self.font_small,
                                     fg=TEXT_COLOR_SECONDARY, bg=CARD_BG)
        self.status_label.pack(side=tk.LEFT)

        # Butonlar Çerçevesi
        btn_frame = tk.Frame(self.frame, bg=CARD_BG)
        btn_frame.pack(pady=5, padx=10, fill=tk.X)

        # Başlat Butonu
        self.start_btn = ModernButton(
            btn_frame, text="BAŞLAT",
            bg=BTN_START_BG, fg="white", active_bg=BTN_START_ACTIVE,
            font=self.font_medium, padx=8, pady=6, width=12,
            command=self.start_timer
        )
        self.start_btn.pack(side=tk.TOP, pady=4, fill=tk.X)

        # Durdur Butonu (Başlangıçta Pasif)
        self.stop_btn = ModernButton(
            btn_frame, text="DURDUR",
            bg=BTN_STOP_BG, fg="white", active_bg=BTN_STOP_ACTIVE,
            font=self.font_medium, padx=8, pady=6, width=12,
            state=tk.DISABLED,
            command=self.stop_timer
        )
        self.stop_btn.pack(side=tk.TOP, pady=4, fill=tk.X)

        # Süreyi Düzenle Butonu
        edit_time_btn = ModernButton(
            btn_frame, text="SÜREYİ DÜZENLE",
            bg=BTN_EDIT_BG, fg="white", active_bg=BTN_EDIT_ACTIVE,
            font=self.font_medium, padx=8, pady=6, width=12,
            command=self.edit_remaining_time
        )
        edit_time_btn.pack(side=tk.TOP, pady=4, fill=tk.X)

        # Sıfırla Butonu
        reset_btn = ModernButton(
            btn_frame, text="SIFIRLA",
            bg=BTN_RESET_BG, fg="white", active_bg=BTN_RESET_ACTIVE,
            font=self.font_medium, padx=8, pady=6, width=12,
            command=self.reset_timer
        )
        reset_btn.pack(side=tk.TOP, pady=(4, 8), fill=tk.X)

    # ------------------------------------------------------------------ #
    # Yardımcılar
    # ------------------------------------------------------------------ #
    @staticmethod
    def format_time(seconds):
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    def update_display(self):
        self.time_label.config(text=self.format_time(self.remaining_seconds))

    def _cancel_tick(self):
        if self._tick_job is not None:
            try:
                self.frame.after_cancel(self._tick_job)
            except tk.TclError:
                pass
            self._tick_job = None

    # ------------------------------------------------------------------ #
    # Süre düzenleme
    # ------------------------------------------------------------------ #
    def edit_remaining_time(self):
        """Masa için kalan süreyi dakika veya dakika:saniye olarak düzenler."""
        current_mins = self.remaining_seconds // 60
        current_secs = self.remaining_seconds % 60
        initial_val = f"{current_mins}" if current_secs == 0 else f"{current_mins}:{current_secs:02d}"

        new_val = simpledialog.askstring(
            "Süreyi Düzenle",
            f"Masa {self.table_number} için kalan süreyi giriniz (Dakika örn: 45 veya DD:SS örn: 45:00):",
            initialvalue=initial_val,
            parent=self.frame
        )
        if not new_val:
            return

        new_val = new_val.strip()
        try:
            if ":" in new_val:
                parts = new_val.split(":")
                if len(parts) != 2:
                    raise ValueError("Geçersiz format.")
                mins = int(parts[0])
                secs = int(parts[1])
            else:
                mins = int(new_val)
                secs = 0

            if mins < 0 or secs < 0 or secs >= 60:
                raise ValueError("Geçersiz süre aralığı.")

            total_sec = mins * 60 + secs
            if total_sec <= 0:
                raise ValueError("Süre 0'dan büyük olmalıdır.")
        except ValueError:
            messagebox.showerror(
                "Hata",
                "Geçersiz süre formatı! Lütfen dakika (Örn: 45) veya DD:SS (Örn: 45:00) şeklinde giriniz.",
                parent=self.frame
            )
            return

        self.remaining_seconds = total_sec
        if self.is_running:
            # Çalışırken düzenlendiyse bitiş anını yeniden hesapla
            self._end_time = time.monotonic() + total_sec
        else:
            self.default_seconds = total_sec
        self.update_display()

    # ------------------------------------------------------------------ #
    # Arayüz durumu
    # ------------------------------------------------------------------ #
    def set_active_ui(self, is_active):
        if is_active:
            self.time_label.config(fg=ACCENT_COLOR_ACTIVE)
            self.status_canvas.itemconfig(self.status_circle, fill=ACCENT_COLOR_ACTIVE)
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_label.config(text="Oyun Oynanıyor", fg=ACCENT_COLOR_ACTIVE)
        else:
            self.time_label.config(fg=ACCENT_COLOR_INACTIVE)
            self.status_canvas.itemconfig(self.status_circle, fill=ACCENT_COLOR_INACTIVE)
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Boş / Bekliyor", fg=TEXT_COLOR_SECONDARY)

    # ------------------------------------------------------------------ #
    # Zamanlayıcı (thread yok; tkinter after döngüsü + gerçek saat)
    # ------------------------------------------------------------------ #
    def start_timer(self):
        if self.is_running:
            return
        # Süre bitmişse varsayılan süreyle yeniden başla
        if self.remaining_seconds <= 0:
            self.remaining_seconds = self.default_seconds
            self.update_display()

        self.is_running = True
        self._end_time = time.monotonic() + self.remaining_seconds
        self.set_active_ui(True)
        self._cancel_tick()
        self._tick_job = self.frame.after(TICK_INTERVAL_MS, self._tick)

    def _tick(self):
        self._tick_job = None
        if not self.is_running:
            return

        rem = max(0, math.ceil(self._end_time - time.monotonic()))
        if rem != self.remaining_seconds:
            self.remaining_seconds = rem
            self.update_display()

        if rem <= 0:
            self.is_running = False
            self.time_up_actions()
        else:
            self._tick_job = self.frame.after(TICK_INTERVAL_MS, self._tick)

    def stop_timer(self):
        if not self.is_running:
            return
        self.is_running = False
        self._cancel_tick()
        # Durdurulduğu andaki kalan süreyi kesinleştir
        if self._end_time is not None:
            self.remaining_seconds = max(0, math.ceil(self._end_time - time.monotonic()))
            self.update_display()
        self.set_active_ui(False)
        self.status_label.config(text="Durduruldu", fg=ACCENT_COLOR_INACTIVE)

    def reset_timer(self):
        self.stop_timer()
        self._cancel_tick()
        self.remaining_seconds = self.default_seconds
        self.update_display()
        self.set_active_ui(False)

    # ------------------------------------------------------------------ #
    # Süre bitişi
    # ------------------------------------------------------------------ #
    def play_alarm_sound(self):
        """Süre bittiğinde sesli alarm çalar (macOS, Windows ve Linux uyumlu)."""
        def sound_thread():
            try:
                system_name = platform.system()
                if system_name == "Darwin":  # macOS
                    sound_path = "/System/Library/Sounds/Glass.aiff"
                    if not os.path.exists(sound_path):
                        sound_path = "/System/Library/Sounds/Ping.aiff"
                    if os.path.exists(sound_path):
                        for _ in range(3):
                            subprocess.run(["afplay", sound_path])
                            time.sleep(0.3)
                elif system_name == "Windows":
                    import winsound
                    for _ in range(3):
                        winsound.Beep(1000, 400)
                        time.sleep(0.2)
            except Exception:
                pass

        # Ses çalma arayüze dokunmadığı için ayrı thread'de güvenle çalışır
        threading.Thread(target=sound_thread, daemon=True).start()

    def time_up_actions(self):
        self.set_active_ui(False)
        self.status_label.config(text="SÜRE BİTTİ!", fg=ACCENT_COLOR_INACTIVE)

        self.play_alarm_sound()
        self.frame.bell()

        messagebox.showwarning("Süre Bitti!", f"Masa {self.table_number} için süre dolmuştur!", parent=self.frame)


class ModernBilliardsApp:
    def __init__(self, root, table_count=4):
        self.root = root
        self.root.title("Bilardo Masası Süre Takip Sistemi")
        self.root.geometry("1060x520")
        self.root.configure(bg=BG_COLOR)

        self.font_ui = font.Font(family=UI_FONT, size=12)
        self.font_header = font.Font(family=UI_FONT, size=16, weight="bold")

        # Üst Bilgi Alanı
        top_frame = tk.Frame(root, bg=BG_COLOR)
        top_frame.pack(fill=tk.X, padx=20, pady=15)

        title_label = tk.Label(top_frame, text="Bilardo Salonu Masa Yönetimi", font=self.font_header,
                               fg=TEXT_COLOR_PRIMARY, bg=BG_COLOR)
        title_label.pack(side=tk.LEFT)

        right_panel = tk.Frame(top_frame, bg=BG_COLOR)
        right_panel.pack(side=tk.RIGHT)

        # Canlı Saat Etiketi
        self.clock_label = tk.Label(right_panel, text="", font=self.font_ui, fg=ACCENT_COLOR_INFO, bg=BG_COLOR)
        self.clock_label.pack(side=tk.LEFT, padx=10)

        # Süre Düzenle Butonu (Üst Panel)
        edit_clock_btn = ModernButton(
            right_panel, text="Süre Ayarla",
            bg=BTN_EDIT_BG, fg="white", active_bg=BTN_EDIT_ACTIVE,
            font=self.font_ui, padx=10, pady=5, width=12,
            command=self.open_edit_time_dialog
        )
        edit_clock_btn.pack(side=tk.LEFT)

        self.update_live_clock()

        # Masalar için ana çerçeve
        tables_outer_frame = tk.Frame(root, bg=BG_COLOR)
        tables_outer_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tables = []
        for i in range(1, table_count + 1):
            table = ModernBilliardsTable(tables_outer_frame, i, default_minutes=30)
            self.tables.append(table)

    def update_live_clock(self):
        time_string = datetime.now().strftime("%H:%M:%S")
        self.clock_label.config(text=f"Sistem Saati: {time_string}")
        self.root.after(1000, self.update_live_clock)

    def open_edit_time_dialog(self):
        """Üst panelden tıklanınca hangi masanın süresinin düzenleneceğini sorar."""
        n = len(self.tables)
        table_str = simpledialog.askstring(
            "Süre Düzenle",
            f"Süresini değiştirmek istediğiniz masa numarasını giriniz (1-{n}):",
            initialvalue="1",
            parent=self.root
        )
        if not table_str:
            return
        try:
            table_num = int(table_str.strip())
            if not 1 <= table_num <= n:
                raise ValueError
        except ValueError:
            messagebox.showerror("Hata", f"Lütfen 1 ile {n} arasında geçerli bir masa numarası giriniz.",
                                 parent=self.root)
            return
        self.tables[table_num - 1].edit_remaining_time()


if __name__ == "__main__":
    # Yüksek çözünürlüklü ekranlar için DPI desteği (yalnızca Windows)
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    app = ModernBilliardsApp(root)
    root.mainloop()
