#!/usr/bin/env python3
import os
import re
import stat
import struct
import subprocess
import json
import shutil
import urllib.request
from urllib.parse import urlparse, quote
import threading
import time
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    HAS_GDK = True
except Exception:
    HAS_GDK = False

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

CONFIG_PATH = os.path.expanduser("~/.config/desktop_maker_cfg.json")
RUNNERS_DIR = os.path.expanduser("~/.local/share/desktop_maker/runners")
LAST_LOG_PATH = "/tmp/dm_last_launch.log"

DEFAULT_CONFIG = {
    "target_dir": os.path.expanduser("~"),
    "icons_dir": os.path.expanduser("~/Изображения") if os.path.isdir(os.path.expanduser("~/Изображения")) else os.path.expanduser("~/Pictures"),
    "also_app_menu": True,
    "theme": "AMOLED Black",
    "custom_proton": ""
}

THEMES = {
    "AMOLED Black": {
        "bg": "#000000",
        "card": "#0a0a0f",
        "fg": "#e4e4e7",
        "muted": "#71717a",
        "entry_bg": "#0f0f17",
        "entry_fg": "#ffffff",
        "btn_bg": "#181824",
        "btn_fg": "#f4f4f5",
        "accent": "#6366f1",
        "border": "#232334"
    },
    "Пастельная (Кофе/Беж)": {
        "bg": "#1e1814",
        "card": "#28201a",
        "fg": "#f2e6d8",
        "muted": "#a89687",
        "entry_bg": "#18130f",
        "entry_fg": "#faf5ef",
        "btn_bg": "#362b23",
        "btn_fg": "#f4ece4",
        "accent": "#cbb59d",
        "border": "#46372e"
    },
    "Пастельная светлая (Латте)": {
        "bg": "#f8f3ed",
        "card": "#ffffff",
        "fg": "#2e221b",
        "muted": "#857062",
        "entry_bg": "#ffffff",
        "entry_fg": "#241812",
        "btn_bg": "#eadbce",
        "btn_fg": "#2e221b",
        "accent": "#9e7b5c",
        "border": "#d7c4b0"
    },
    "Темно-зеленый": {
        "bg": "#050807",
        "card": "#0a100d",
        "fg": "#e2e8f0",
        "muted": "#64748b",
        "entry_bg": "#0e1713",
        "entry_fg": "#ffffff",
        "btn_bg": "#15241d",
        "btn_fg": "#f1f5f9",
        "accent": "#10b981",
        "border": "#1e352b"
    },
    "Темно-голубой": {
        "bg": "#05070e",
        "card": "#0a0f1c",
        "fg": "#e2e8f0",
        "muted": "#64748b",
        "entry_bg": "#0e1526",
        "entry_fg": "#ffffff",
        "btn_bg": "#16213a",
        "btn_fg": "#f1f5f9",
        "accent": "#0ea5e9",
        "border": "#203254"
    },
    "Светло-зеленый": {
        "bg": "#f4f7f5",
        "card": "#ffffff",
        "fg": "#18181b",
        "muted": "#71717a",
        "entry_bg": "#ffffff",
        "entry_fg": "#09090b",
        "btn_bg": "#e4efe9",
        "btn_fg": "#18181b",
        "accent": "#10b981",
        "border": "#cde0d5"
    },
    "Светло-голубой": {
        "bg": "#f4f7fb",
        "card": "#ffffff",
        "fg": "#0f172a",
        "muted": "#64748b",
        "entry_bg": "#ffffff",
        "entry_fg": "#020617",
        "btn_bg": "#e2ecf7",
        "btn_fg": "#0f172a",
        "accent": "#0284c7",
        "border": "#cbdceb"
    }
}

RUNNERS = [
    "Авто",
    "Steam (Пиратка OnlineFix / Proton)",
    "Steam (Лицензия по AppID)",
    "Faugus Launcher",
    "PortProton",
    "Wine",
    "Веб-сайт (Браузер)",
    "Нативно (Linux)"
]

ONLINEFIX_DLLS = (
    "OnlineFix64=n",
    "OnlineFix=n",
    "SteamOverlay64=n",
    "SteamOverlay=n",
    "winmm=n,b",
    "dnet=n",
    "steam_api64=n,b",
    "steam_api=n,b",
    "version=n,b",
    "dinput8=n,b",
    "dsound=n,b",
    "winhttp=n,b",
    "dbghelp=n,b",
    "httpapi=n,b",
    "Custom=n"
)


class ToggleButton(tk.Button):
    """Надёжная кнопка-переключатель вместо невидимого ttk.Checkbutton."""
    def __init__(self, parent, text, variable, colors, command=None):
        super().__init__(
            parent,
            bd=0,
             highlightthickness=1,
            relief="flat",
            cursor="hand2",
            font=("Sans", 9, "bold"),
            padx=10,
            pady=5
        )
        self.base_text = text
        self.variable = variable
        self.colors = colors
        self.user_cmd = command
        self.configure(command=self.toggle)
        self.variable.trace_add("write", lambda *_: self.refresh_visual())
        self.refresh_visual()

    def toggle(self):
        self.variable.set(not self.variable.get())
        if self.user_cmd:
            self.user_cmd()

    def update_colors(self, colors):
        self.colors = colors
        self.refresh_visual()

    def refresh_visual(self):
        if not self.winfo_exists():
            return
        state = self.variable.get()
        c = self.colors
        if state:
            self.configure(
                text=f"✓  {self.base_text}: ВКЛ",
                bg=c["accent"],
                fg="#ffffff",
                activebackground=c["accent"],
                activeforeground="#ffffff",
                highlightbackground=c["accent"]
            )
        else:
            self.configure(
                text=f"○  {self.base_text}: ВЫКЛ",
                bg=c["btn_bg"],
                fg=c["fg"],
                activebackground=c["border"],
                activeforeground=c["fg"],
                highlightbackground=c["border"]
            )


def is_url(text):
    t = text.strip()
    if t.startswith(("http://", "https://", "www.")):
        return True
    if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$", t) and not os.path.exists(t) and not t.lower().endswith(".exe"):
        return True
    return False


def normalize_url(text):
    t = text.strip()
    if not t.startswith(("http://", "https://")):
        return "https://" + t
    return t


def find_terminal_emulator():
    """Находит установленный эмулятор терминала в системе."""
    terms = [
        ("kitty", ["kitty", "-e"]),
        ("foot", ["foot"]),
        ("ptyxis", ["ptyxis", "--"]),
        ("kgx", ["kgx", "-e"]),
        ("gnome-terminal", ["gnome-terminal", "--"]),
        ("alacritty", ["alacritty", "-e"]),
        ("konsole", ["konsole", "-e"]),
        ("xfce4-terminal", ["xfce4-terminal", "-x"]),
        ("xterm", ["xterm", "-e"])
    ]
    for bin_name, args in terms:
        if shutil.which(bin_name):
            return args
    return None


def get_faugus_cmd():
    for cmd in ("faugus-run", "faugus-launcher"):
        p = shutil.which(cmd)
        if p:
            return p
        local_p = os.path.expanduser(f"~/.local/bin/{cmd}")
        if os.path.isfile(local_p) and os.access(local_p, os.X_OK):
            return local_p
    if shutil.which("flatpak"):
        try:
            out = subprocess.check_output(["flatpak", "list", "--app"], text=True, stderr=subprocess.DEVNULL)
            if "io.github.Faugus.faugus-launcher" in out:
                return "flatpak run io.github.Faugus.faugus-launcher"
        except Exception:
            pass
    return "faugus-launcher"


def get_steam_root():
    candidates = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"),
        os.path.expanduser("~/.steam/root"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam")
    ]
    for c in candidates:
        if os.path.isdir(c):
            return os.path.realpath(c)
    return os.path.expanduser("~/.local/share/Steam")


def get_steam_libraries(extra_exe_path=None):
    root = get_steam_root()
    libs = [root]
    vdf_paths = [
        os.path.join(root, "steamapps", "libraryfolders.vdf"),
        os.path.join(root, "config", "libraryfolders.vdf")
    ]
    for vdf in vdf_paths:
        if os.path.isfile(vdf):
            try:
                with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for m in re.finditer(r'"path"\s+"([^"]+)"', content):
                    p = m.group(1).replace("\\\\", "/")
                    if os.path.isdir(p) and p not in libs:
                        libs.append(p)
            except Exception:
                pass

    if extra_exe_path and "steamapps" in extra_exe_path:
        parts = os.path.abspath(extra_exe_path).split(os.sep)
        if "steamapps" in parts:
            idx = parts.index("steamapps")
            lib_cand = os.sep.join(parts[:idx])
            if os.path.isdir(lib_cand) and lib_cand not in libs:
                libs.append(lib_cand)
    return libs


def find_all_protons(extra_exe_path=None):
    protons = []
    search_dirs = [
        "/usr/share/steam/compatibilitytools.d",
        os.path.expanduser("~/.local/share/Steam/compatibilitytools.d"),
        os.path.expanduser("~/.steam/root/compatibilitytools.d"),
    ]
    for lib in get_steam_libraries(extra_exe_path):
        search_dirs.append(os.path.join(lib, "steamapps", "common"))

    seen = set()
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        try:
            for entry in sorted(os.listdir(d), reverse=True):
                full_dir = os.path.join(d, entry)
                proton_bin = os.path.join(full_dir, "proton")
                if os.path.isfile(proton_bin):
                    real_p = os.path.realpath(proton_bin)
                    if real_p not in seen:
                        seen.add(real_p)
                        protons.append(proton_bin)
        except PermissionError:
            continue

    def sort_key(p):
        pl = p.lower()
        if "cachyos" in pl:
            return 0
        if "ge-proton" in pl or "proton-ge" in pl:
            return 1
        if "experimental" in pl:
            return 2
        if "hotfix" in pl:
            return 3
        return 4

    protons.sort(key=sort_key)
    return protons


def convert_to_png(src_path, out_png):
    if not os.path.isfile(src_path):
        return None
    if src_path.lower().endswith(".png"):
        return src_path

    os.makedirs(os.path.dirname(out_png), exist_ok=True)

    if HAS_GDK:
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(src_path)
            pixbuf.savev(out_png, "png", [], [])
            if os.path.isfile(out_png) and os.path.getsize(out_png) > 0:
                return out_png
        except Exception:
            pass

    if HAS_PIL:
        try:
            with Image.open(src_path) as im:
                im.save(out_png, "PNG")
            if os.path.isfile(out_png) and os.path.getsize(out_png) > 0:
                return out_png
        except Exception:
            pass

    if src_path.lower().endswith(".ico") and shutil.which("icotool"):
        try:
            tmp_dir = f"/tmp/ico_conv_{os.getpid()}"
            os.makedirs(tmp_dir, exist_ok=True)
            subprocess.run(["icotool", "-x", "-o", tmp_dir, src_path], stderr=subprocess.DEVNULL, check=True)
            pngs = [os.path.join(tmp_dir, x) for x in os.listdir(tmp_dir) if x.endswith(".png")]
            if pngs:
                pngs.sort(key=lambda p: os.path.getsize(p), reverse=True)
                shutil.move(pngs[0], out_png)
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return out_png
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    for tool in ("magick", "ffmpeg"):
        if shutil.which(tool):
            try:
                cmd = ["magick", f"{src_path}[0]", out_png] if tool == "magick" else ["ffmpeg", "-y", "-i", src_path, out_png]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.isfile(out_png) and os.path.getsize(out_png) > 0:
                    return out_png
            except Exception:
                pass

    return src_path


def extract_icons_from_exe_pure_python(exe_path, out_dir, stem):
    results = []
    if not os.path.isfile(exe_path):
        return results
    os.makedirs(out_dir, exist_ok=True)

    try:
        file_size = os.path.getsize(exe_path)
        read_limit = min(file_size, 180 * 1024 * 1024)
        with open(exe_path, "rb") as f:
            data = f.read(read_limit)
    except Exception:
        return results

    png_sig = b"\x89PNG\r\n\x1a\n"
    iend_sig = b"IEND\xaeB`\x82"
    pos = 0
    idx = 0
    while idx < 6:
        start = data.find(png_sig, pos)
        if start == -1:
            break
        end = data.find(iend_sig, start)
        if end == -1 or (end - start) > 2 * 1024 * 1024:
            pos = start + 8
            continue
        end += len(iend_sig)
        blob = data[start:end]
        if len(blob) >= 64:
            try:
                w, h = struct.unpack(">II", blob[16:24])
                if 24 <= w <= 1024 and w == h:
                    out_p = os.path.join(out_dir, f"{stem}_exe_{w}x{h}_{idx}.png")
                    with open(out_p, "wb") as pf:
                        pf.write(blob)
                    results.append(out_p)
                    idx += 1
            except Exception:
                pass
        pos = end

    try:
        if data[:2] == b"MZ":
            pe_off = struct.unpack_from("<I", data, 0x3C)[0]
            if data[pe_off:pe_off + 4] == b"PE\x00\x00":
                num_sec = struct.unpack_from("<H", data, pe_off + 6)[0]
                opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
                opt_off = pe_off + 24
                magic = struct.unpack_from("<H", data, opt_off)[0]
                dd_off = opt_off + (96 if magic == 0x10B else 112)
                rsrc_rva, _ = struct.unpack_from("<II", data, dd_off + 16)

                sec_off = opt_off + opt_size
                sections = []
                for i in range(num_sec):
                    s = sec_off + i * 40
                    vsize, va, rsize, roff = struct.unpack_from("<IIII", data, s + 8)
                    sections.append((va, max(vsize, rsize), roff))

                def rva_to_off(rva):
                    for va, sz, roff in sections:
                        if va <= rva < va + sz:
                            return roff + (rva - va)
                    return None

                base_off = rva_to_off(rsrc_rva)
                if base_off is not None:
                    n_named, n_id = struct.unpack_from("<HH", data, base_off + 12)
                    for i in range(n_named + n_id):
                        ent_off = base_off + 16 + i * 8
                        res_id, sub_ofs = struct.unpack_from("<II", data, ent_off)
                        if res_id == 3 and (sub_ofs & 0x80000000):
                            dir2 = base_off + (sub_ofs & 0x7FFFFFFF)
                            n2_named, n2_id = struct.unpack_from("<HH", data, dir2 + 12)
                            best_icons = []
                            for j in range(min(n2_named + n2_id, 25)):
                                e2 = dir2 + 16 + j * 8
                                _, sub2 = struct.unpack_from("<II", data, e2)
                                if sub2 & 0x80000000:
                                    dir3 = base_off + (sub2 & 0x7FFFFFFF)
                                    n3_n, n3_i = struct.unpack_from("<HH", data, dir3 + 12)
                                    if n3_n + n3_i > 0:
                                        _, data_ent_ofs = struct.unpack_from("<II", data, dir3 + 16)
                                        if not (data_ent_ofs & 0x80000000):
                                            de = base_off + data_ent_ofs
                                            ic_rva, ic_sz = struct.unpack_from("<II", data, de)
                                            ic_off = rva_to_off(ic_rva)
                                            if ic_off and 40 < ic_sz < 1024 * 1024:
                                                best_icons.append(data[ic_off:ic_off + ic_sz])
                            best_icons.sort(key=len, reverse=True)
                            for k, blob in enumerate(best_icons[:3]):
                                if blob.startswith(png_sig):
                                    out_p = os.path.join(out_dir, f"{stem}_rsrc_{k}.png")
                                    with open(out_p, "wb") as pf:
                                        pf.write(blob)
                                    results.append(out_p)
                                else:
                                    hdr_sz, bw, bh, planes, bpp = struct.unpack_from("<IIIHH", blob, 0)
                                    if hdr_sz == 40 and 16 <= bw <= 512:
                                        real_h = bh // 2
                                        wb = bw if bw < 256 else 0
                                        hb = real_h if real_h < 256 else 0
                                        ico_hdr = struct.pack("<HHH", 0, 1, 1)
                                        ico_ent = struct.pack("<BBBBHHII", wb, hb, 0, 0, planes or 1, bpp or 32, len(blob), 22)
                                        tmp_ico = f"/tmp/{stem}_pe_{k}.ico"
                                        with open(tmp_ico, "wb") as icf:
                                            icf.write(ico_hdr + ico_ent + blob)
                                        out_p = os.path.join(out_dir, f"{stem}_pe_{bw}x{real_h}_{k}.png")
                                        conv = convert_to_png(tmp_ico, out_p)
                                        try:
                                            os.remove(tmp_ico)
                                        except OSError:
                                            pass
                                        if conv and os.path.isfile(conv):
                                            results.append(conv)
    except Exception:
        pass

    return results


def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    for unit in ["КБ", "МБ", "ГБ", "ТБ"]:
        size_bytes /= 1024.0
        if size_bytes < 1024.0 or unit == "ТБ":
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} Б"


def get_file_type_and_icon(filename, is_dir=False):
    if is_dir:
        return "📁", "Папка"
    fl = filename.lower()
    if fl.endswith(".exe"):
        return "🎮", "Игра / EXE Windows"
    if fl.endswith((".sh", ".bin", ".bash", ".run", ".cmd", ".bat")):
        return "⚙️", "Скрипт Linux / Бинарник"
    if fl.endswith(".appimage"):
        return "📦", "AppImage пакет"
    if fl.endswith(".desktop"):
        return "🖥️", "Ярлык .desktop"
    if fl.endswith(".py"):
        return "🐍", "Python скрипт"
    if fl.endswith((".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp", ".xpm")):
        ext = os.path.splitext(fl)[1].replace(".", "").upper()
        return "🖼️", f"Изображение {ext}"
    if fl.endswith((".zip", ".tar", ".gz", ".7z", ".rar", ".xz")):
        return "🗜️", "Архив"
    if fl.endswith((".txt", ".log", ".md", ".ini", ".cfg", ".conf")):
        return "📄", "Документ / Конфиг"
    return "📄", "Файл"


class CustomPathDialog(tk.Toplevel):
    """Современный двухпанельный проводник с закладками, фильтрацией и подсветкой исполняемых файлов."""
    def __init__(self, parent, title, init_dir, theme_colors, mode="file", exts=None):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.result = None
        self.mode = mode
        self.exts = tuple(exts) if exts else None
        self.colors = theme_colors
        self.configure(bg=self.colors["bg"])

        # Центрирование окна
        w, h = 920, 580
        self.minsize(740, 460)
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = max(0, px + (pw - w) // 2)
            y = max(0, py + (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        cur_dir = init_dir if (init_dir and os.path.isdir(init_dir)) else os.path.expanduser("~")
        self.cur_dir = os.path.abspath(cur_dir)

        # История навигации (Назад / Вперёд)
        self.history = [self.cur_dir]
        self.history_idx = 0
        self.navigating_history = False

        # Состояние сортировки
        self.sort_col = "name"
        self.sort_reverse = False

        # Переменные
        self.path_var = tk.StringVar(value=self.cur_dir)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        self.show_hidden = tk.BooleanVar(value=False)
        self.show_hidden.trace_add("write", lambda *_: self.refresh_dir(self.cur_dir, update_history=False))

        # Переменная фильтра типов
        self.filter_var = tk.StringVar()
        self.setup_filter_options()

        self.current_items = []

        self.build_ui()
        self.refresh_dir(self.cur_dir, update_history=False)

        self.bind("<Escape>", lambda e: self.destroy())
        self.lift()
        self.focus_force()

    def setup_filter_options(self):
        if self.mode == "dir":
            self.filter_options = ["📁 Только папки"]
            self.filter_var.set(self.filter_options[0])
        elif self.exts and any(x in self.exts for x in (".png", ".jpg", ".ico", ".svg")):
            self.filter_options = [
                "🖼️ Изображения (*.png, *.svg, *.ico, *.jpg, *.webp)",
                "📁 Все файлы (*.*)"
            ]
            self.filter_var.set(self.filter_options[0])
        else:
            self.filter_options = [
                "🎮 Все исполняемые (*.exe, *.sh, *.bin, *.AppImage, *.py)",
                "🪟 Игры Windows (*.exe)",
                "🐧 Программы Linux (*.sh, *.bin, *.AppImage)",
                "📁 Все файлы (*.*)"
            ]
            self.filter_var.set(self.filter_options[0])

    def build_ui(self):
        # ── Верхняя панель навигации ──
        top = ttk.Frame(self, padding=(12, 10, 12, 6))
        top.pack(fill="x")

        nav_box = ttk.Frame(top)
        nav_box.pack(fill="x", pady=(0, 6))

        self.btn_back = ttk.Button(nav_box, text="◀", width=3, command=self.go_back)
        self.btn_back.pack(side="left", padx=(0, 2))
        self.btn_fwd = ttk.Button(nav_box, text="▶", width=3, command=self.go_forward)
        self.btn_fwd.pack(side="left", padx=2)
        ttk.Button(nav_box, text="⬆ Вверх", width=8, command=self.go_up).pack(side="left", padx=2)
        ttk.Button(nav_box, text="⌂ Домой", width=8, command=self.go_home).pack(side="left", padx=2)
        ttk.Button(nav_box, text="🔄", width=3, command=lambda: self.refresh_dir(self.cur_dir, update_history=False)).pack(side="left", padx=(2, 8))

        self.path_entry = ttk.Entry(nav_box, textvariable=self.path_var)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.path_entry.bind("<Return>", lambda e: self.on_enter_path())
        ttk.Button(nav_box, text="Перейти", width=9, command=self.on_enter_path).pack(side="left")

        # Строка быстрого поиска и фильтров
        filter_box = ttk.Frame(top)
        filter_box.pack(fill="x")

        ttk.Label(filter_box, text="Поиск:").pack(side="left", padx=(0, 6))
        search_entry = ttk.Entry(filter_box, textvariable=self.search_var, width=22)
        search_entry.pack(side="left", padx=(0, 12))

        ttk.Label(filter_box, text="Тип:").pack(side="left", padx=(0, 6))
        filter_cb = ttk.Combobox(filter_box, textvariable=self.filter_var, values=self.filter_options, state="readonly", width=38)
        filter_cb.pack(side="left", padx=(0, 12))
        filter_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        hidden_cb = ttk.Checkbutton(filter_box, text="Скрытые файлы (.*)", variable=self.show_hidden)
        hidden_cb.pack(side="left", padx=4)

        # ── Основная рабочая область (Две панели) ──
        body = ttk.Frame(self, padding=(12, 4, 12, 6))
        body.pack(fill="both", expand=True)

        paned = ttk.PanedWindow(body, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Левая панель: Быстрый доступ
        quick_frame = ttk.Frame(paned, padding=(0, 0, 8, 0))
        paned.add(quick_frame, weight=1)

        ttk.Label(quick_frame, text="Быстрый доступ", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))

        self.quick_box = tk.Listbox(
            quick_frame, bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
            selectbackground=self.colors["accent"], selectforeground="#ffffff",
            highlightthickness=1, highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"], bd=0, font=("Sans", 9), activestyle="none"
        )
        self.quick_box.pack(fill="both", expand=True)
        self.quick_box.bind("<<ListboxSelect>>", self.on_quick_select)

        self.populate_quick_places()

        # Правая панель: Таблица файлов (Treeview)
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=5)

        cols = ("name", "size", "type", "mtime")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("name", text="Имя файла / папки", command=lambda: self.sort_by("name"))
        self.tree.heading("size", text="Размер", command=lambda: self.sort_by("size"))
        self.tree.heading("type", text="Тип", command=lambda: self.sort_by("type"))
        self.tree.heading("mtime", text="Дата изменения", command=lambda: self.sort_by("mtime"))

        self.tree.column("name", width=340, anchor="w")
        self.tree.column("size", width=95, anchor="e")
        self.tree.column("type", width=160, anchor="w")
        self.tree.column("mtime", width=145, anchor="w")

        tree_sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")

        self.tree.bind("<Double-Button-1>", self.on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Return>", lambda e: self.on_tree_enter())
        self.tree.bind("<BackSpace>", lambda e: self.go_up())

        # ── Нижняя панель действий ──
        bot = ttk.Frame(self, padding=(12, 6, 12, 10))
        bot.pack(fill="x")

        # Строка выбранного объекта
        sel_row = ttk.Frame(bot)
        sel_row.pack(fill="x", pady=(0, 6))
        ttk.Label(sel_row, text="Выбрано:").pack(side="left", padx=(0, 6))
        self.selected_var = tk.StringVar()
        self.selected_entry = ttk.Entry(sel_row, textvariable=self.selected_var)
        self.selected_entry.pack(side="left", fill="x", expand=True)
        self.selected_entry.bind("<Return>", lambda e: self.accept_current())

        # Кнопки действий и статус-бар
        action_row = ttk.Frame(bot)
        action_row.pack(fill="x")

        self.status_lbl = ttk.Label(action_row, text="", style="Muted.TLabel")
        self.status_lbl.pack(side="left")

        ttk.Button(action_row, text="Отмена", width=10, command=self.destroy).pack(side="right", padx=(4, 0))
        btn_text = "Выбрать эту папку" if self.mode == "dir" else "Выбрать файл"
        ttk.Button(action_row, text=btn_text, style="Accent.TButton", command=self.accept_current).pack(side="right", padx=4)

    def populate_quick_places(self):
        home = os.path.expanduser("~")
        places = [("⌂ Главная", home)]

        standard_dirs = [
            ("Рабочий стол", "🖥️ Рабочий стол"),
            ("Desktop", "🖥️ Рабочий стол"),
            ("Загрузки", "📥 Загрузки"),
            ("Downloads", "📥 Загрузки"),
            ("Игры", "🎮 Папка Игр"),
            ("Games", "🎮 Папка Игр"),
            ("Изображения", "🖼️ Изображения"),
            ("Pictures", "🖼️ Изображения")
        ]
        seen_dirs = {home}
        for sub, lbl in standard_dirs:
            full = os.path.join(home, sub)
            if os.path.isdir(full) and full not in seen_dirs:
                places.append((lbl, full))
                seen_dirs.add(full)

        if os.path.isdir("/mnt/game") and "/mnt/game" not in seen_dirs:
            places.append(("🎮 Диск Игры (/mnt/game)", "/mnt/game"))
            seen_dirs.add("/mnt/game")

        # Библиотеки Steam
        for lib in get_steam_libraries():
            common = os.path.join(lib, "steamapps", "common")
            if os.path.isdir(common) and common not in seen_dirs:
                places.append(("💨 Steam Common", common))
                seen_dirs.add(common)

        # Приложения
        app_d = os.path.expanduser("~/.local/share/applications")
        if os.path.isdir(app_d):
            places.append(("⚙️ Приложения (.desktop)", app_d))

        places.append(("💽 Корень (/)", "/"))

        self.quick_places = places
        self.quick_box.delete(0, tk.END)
        for label, _ in places:
            self.quick_box.insert(tk.END, f" {label}")

    def on_quick_select(self, _):
        sel = self.quick_box.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.quick_places):
            target = self.quick_places[idx][1]
            if os.path.isdir(target):
                self.refresh_dir(target)

    def refresh_dir(self, d, update_history=True):
        if not os.path.isdir(d):
            return
        self.cur_dir = os.path.abspath(d)
        self.path_var.set(self.cur_dir)

        if update_history and not self.navigating_history:
            if self.history_idx < len(self.history) - 1:
                self.history = self.history[:self.history_idx + 1]
            if not self.history or self.history[-1] != self.cur_dir:
                self.history.append(self.cur_dir)
                self.history_idx = len(self.history) - 1

        self.update_nav_buttons()

        try:
            raw_entries = os.listdir(self.cur_dir)
        except PermissionError:
            messagebox.showerror("Доступ запрещен", f"Нет прав доступа к папке:\n{self.cur_dir}", parent=self)
            return

        show_hid = self.show_hidden.get()
        items = []
        for name in raw_entries:
            if not show_hid and name.startswith("."):
                continue
            full_path = os.path.join(self.cur_dir, name)
            try:
                st = os.stat(full_path, follow_symlinks=True)
                is_directory = stat.S_ISDIR(st.st_mode)
                size_num = st.st_size if not is_directory else -1
                mtime_num = st.st_mtime
                mtime_str = datetime.datetime.fromtimestamp(mtime_num).strftime("%d.%m.%Y %H:%M")
            except OSError:
                is_directory = os.path.isdir(full_path)
                size_num = -1
                mtime_num = 0
                mtime_str = "—"

            icon, type_label = get_file_type_and_icon(name, is_directory)
            size_str = "—" if is_directory else format_file_size(size_num)
            display_name = f"{icon}  {name}"

            items.append({
                "name": name,
                "display_name": display_name,
                "full_path": full_path,
                "is_dir": is_directory,
                "size_num": size_num,
                "size_str": size_str,
                "type_str": type_label,
                "mtime_num": mtime_num,
                "mtime_str": mtime_str
            })

        self.current_items = items
        self.apply_filter()

    def update_nav_buttons(self):
        can_back = self.history_idx > 0
        can_fwd = self.history_idx < len(self.history) - 1
        self.btn_back.state(["!disabled"] if can_back else ["disabled"])
        self.btn_fwd.state(["!disabled"] if can_fwd else ["disabled"])

    def go_back(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            self.navigating_history = True
            self.refresh_dir(self.history[self.history_idx], update_history=False)
            self.navigating_history = False

    def go_forward(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self.navigating_history = True
            self.refresh_dir(self.history[self.history_idx], update_history=False)
            self.navigating_history = False

    def go_up(self):
        parent = os.path.dirname(self.cur_dir)
        if parent and parent != self.cur_dir:
            self.refresh_dir(parent)

    def go_home(self):
        self.refresh_dir(os.path.expanduser("~"))

    def on_enter_path(self):
        raw = os.path.expanduser(self.path_var.get().strip())
        if os.path.isdir(raw):
            self.refresh_dir(raw)
        elif os.path.isfile(raw) and self.mode == "file":
            self.result = os.path.abspath(raw)
            self.destroy()
        else:
            messagebox.showwarning("Путь не найден", f"Указанный путь не существует:\n{raw}", parent=self)

    def apply_filter(self):
        query = self.search_var.get().strip().lower()
        active_filter = self.filter_var.get()

        filtered = []
        for it in self.current_items:
            # Текстовый поиск
            if query and (query not in it["name"].lower()):
                continue

            # Фильтр типов
            if not it["is_dir"]:
                fn = it["name"].lower()
                if "Только Windows (*.exe)" in active_filter and not fn.endswith(".exe"):
                    continue
                if "Только Linux" in active_filter and not fn.endswith((".sh", ".bin", ".appimage", ".py")):
                    continue
                if "Все исполняемые" in active_filter and not fn.endswith((".exe", ".sh", ".bin", ".appimage", ".py", ".bat", ".cmd")):
                    continue
                if "Изображения" in active_filter and not fn.endswith((".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp", ".xpm")):
                    continue
                if self.mode == "dir":
                    continue
                if self.exts and not any(fn.endswith(ext.lower()) for ext in self.exts):
                    continue

            filtered.append(it)

        # Сортировка: папки всегда сверху!
        col = self.sort_col
        rev = self.sort_reverse

        def sort_key(item):
            dir_rank = 0 if item["is_dir"] else 1
            if col == "name":
                val = item["name"].lower()
            elif col == "size":
                val = item["size_num"]
            elif col == "type":
                val = item["type_str"].lower()
            elif col == "mtime":
                val = item["mtime_num"]
            else:
                val = item["name"].lower()
            return (dir_rank, val)

        filtered.sort(key=sort_key, reverse=rev)

        self.tree.delete(*self.tree.get_children())
        for it in filtered:
            self.tree.insert(
                "", "end", iid=it["full_path"],
                values=(it["display_name"], it["size_str"], it["type_str"], it["mtime_str"])
            )

        dirs_cnt = sum(1 for x in filtered if x["is_dir"])
        files_cnt = len(filtered) - dirs_cnt
        self.status_lbl.config(text=f"Папок: {dirs_cnt} · Файлов: {files_cnt} · Всего: {len(filtered)}")

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = False
        self.apply_filter()

    def on_tree_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        full_p = sel[0]
        if os.path.isfile(full_p):
            self.selected_var.set(full_p)
            sz = format_file_size(os.path.getsize(full_p))
            self.status_lbl.config(text=f"Выбран файл: {os.path.basename(full_p)} ({sz})")
        elif os.path.isdir(full_p):
            self.selected_var.set(full_p)
            self.status_lbl.config(text=f"Выбрана папка: {os.path.basename(full_p)}")

    def on_tree_enter(self):
        sel = self.tree.selection()
        if not sel:
            self.accept_current()
            return
        full_p = sel[0]
        if os.path.isdir(full_p):
            self.refresh_dir(full_p)
        else:
            self.accept_current()

    def on_tree_double_click(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        full_p = sel[0]
        if os.path.isdir(full_p):
            self.refresh_dir(full_p)
        else:
            self.result = full_p
            self.destroy()

    def accept_current(self):
        chosen = self.selected_var.get().strip()
        if not chosen:
            sel = self.tree.selection()
            if sel:
                chosen = sel[0]
            else:
                chosen = self.cur_dir

        chosen = os.path.abspath(os.path.expanduser(chosen))

        if self.mode == "dir":
            if os.path.isdir(chosen):
                self.result = chosen
                self.destroy()
            elif os.path.isdir(self.cur_dir):
                self.result = self.cur_dir
                self.destroy()
        else:
            if os.path.isfile(chosen):
                self.result = chosen
                self.destroy()
            elif os.path.isdir(chosen):
                self.refresh_dir(chosen)
            elif os.path.exists(chosen):
                self.result = chosen
                self.destroy()


def download_image_as_png(url, out_png):
    """Безопасно скачивает картинку по URL и конвертирует в PNG."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            }
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = resp.read()
            if len(data) < 80:
                return None
            tmp_dl = f"/tmp/dl_ico_{os.getpid()}_{hash(url) & 0xffffffff}"
            with open(tmp_dl, "wb") as f:
                f.write(data)
            conv = convert_to_png(tmp_dl, out_png)
            try:
                if os.path.exists(tmp_dl) and tmp_dl != conv:
                    os.remove(tmp_dl)
            except OSError:
                pass
            return conv if (conv and os.path.isfile(conv) and os.path.getsize(conv) > 0) else None
    except Exception:
        return None


def fetch_steam_icons_online(query_or_appid, icons_dir):
    """Ищет официальные логотипы в Steam API / CDN и сохраняет в PNG."""
    results = []
    os.makedirs(icons_dir, exist_ok=True)
    appid = None
    query = str(query_or_appid).strip()

    if query.isdigit() and len(query) >= 2 and query != "480":
        appid = query
        game_title = f"AppID {appid}"
    else:
        clean = re.sub(r"[\-_.]", " ", query)
        clean = re.sub(r"(?i)\b(shipping|win64|win32|binaries|launcher|game|exe|x64|x86)\b", " ", clean)
        clean = " ".join(clean.split())
        if not clean or clean.lower() == "spacewar":
            return results
        game_title = clean

        try:
            api_url = f"https://store.steampowered.com/api/storesearch/?term={quote(clean)}&l=russian&cc=RU"
            req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8", "ignore"))
                items = data.get("items", [])
                if items:
                    appid = str(items[0].get("id"))
                    game_title = items[0].get("name", clean)
        except Exception:
            pass

    if appid and appid != "480":
        safe_stem = re.sub(r"\W+", "_", game_title.lower()).strip("_") or f"steam_{appid}"
        # 1. Прозрачное PNG лого из CDN Steam
        cdn_logo = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/logo.png"
        out_logo = os.path.join(icons_dir, f"{safe_stem}_steam_logo.png")
        p = download_image_as_png(cdn_logo, out_logo)
        if p:
            results.append((130, f"[Steam Онлайн] {os.path.basename(p)}", p))

        # 2. Обложка Header
        cdn_hdr = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
        out_hdr = os.path.join(icons_dir, f"{safe_stem}_steam_header.png")
        p_h = download_image_as_png(cdn_hdr, out_hdr)
        if p_h:
            results.append((105, f"[Steam Обложка] {os.path.basename(p_h)}", p_h))

    return results


def fetch_website_icons_online(site_url, icons_dir):
    """Ищет favicon, apple-touch-icon и og:image сайта и сохраняет в PNG."""
    results = []
    os.makedirs(icons_dir, exist_ok=True)
    norm = normalize_url(site_url)
    domain = urlparse(norm).netloc.lower().replace("www.", "")
    stem = domain.split(".")[0] if domain else "site"

    # 1. Google Favicon 128px
    fav_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    out_fav = os.path.join(icons_dir, f"{stem}_favicon.png")
    p1 = download_image_as_png(fav_url, out_fav)
    if p1 and os.path.getsize(p1) > 100:
        results.append((125, f"[Сайт] {os.path.basename(p1)}", p1))

    # 2. DuckDuckGo ICO/PNG
    ddg_url = f"https://icons.duckduckgo.com/ip3/{domain}.ico"
    out_ddg = os.path.join(icons_dir, f"{stem}_ddg.png")
    p2 = download_image_as_png(ddg_url, out_ddg)
    if p2 and os.path.getsize(p2) > 100:
        results.append((115, f"[Сайт DDG] {os.path.basename(p2)}", p2))

    # 3. Парсинг HTML
    try:
        req = urllib.request.Request(norm, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            html = resp.read().decode("utf-8", "ignore")
            m_apple = re.search(r'<link[^>]+(?:rel=["\'](?:apple-touch-icon|icon)["\'][^>]+href=["\']([^"\']+)["\']|href=["\']([^"\']+)["\'][^>]+rel=["\'](?:apple-touch-icon|icon)["\'])', html, re.IGNORECASE)
            if m_apple:
                icon_href = m_apple.group(1) or m_apple.group(2)
                if not icon_href.startswith(("http://", "https://")):
                    base = f"https://{domain}" if not norm.startswith("http") else norm.rstrip("/")
                    icon_href = urllib.parse.urljoin(base + "/", icon_href.lstrip("/"))
                out_web = os.path.join(icons_dir, f"{stem}_touch_icon.png")
                p3 = download_image_as_png(icon_href, out_web)
                if p3 and os.path.getsize(p3) > 200:
                    results.append((130, f"[Сайт HD] {os.path.basename(p3)}", p3))
    except Exception:
        pass

    return results


def make_thumbnail_photo(path, size=72):
    """Генерирует аккуратный PhotoImage для карточки галереи и путь к временному файлу."""
    try:
        tmp_t = f"/tmp/gal_th_{os.getpid()}_{hash(path) & 0xffffffff}_{size}.png"
        if HAS_GDK:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
            pb.savev(tmp_t, "png", [], [])
            return tk.PhotoImage(file=tmp_t), tmp_t
        elif HAS_PIL:
            with Image.open(path) as im:
                im.thumbnail((size, size))
                im.save(tmp_t, "PNG")
            return tk.PhotoImage(file=tmp_t), tmp_t
        elif path.lower().endswith(".png"):
            raw_p = tk.PhotoImage(file=path)
            f_sub = max(1, max(raw_p.width(), raw_p.height()) // size)
            return raw_p.subsample(f_sub, f_sub), None
    except Exception:
        pass
    return None, None


class IconGalleryDialog(tk.Toplevel):
    """Полнофункциональная, красивая и отзывчивая галерея логотипов с онлайн-поиском и предпросмотром."""
    def __init__(self, parent, app, found_icons, on_pick_callback):
        super().__init__(parent)
        self.app = app
        self.colors = app.colors
        self.on_pick_callback = on_pick_callback
        self.all_icons = list(found_icons)
        self.temp_thumbs = []
        self.thumb_refs = []
        self.card_widgets = []
        self.selected_path = None

        self.title("Галерея логотипов")
        self.configure(bg=self.colors["bg"])
        self.transient(parent)

        w, h = 920, 620
        self.minsize(740, 480)
        self.geometry(f"{w}x{h}")

        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = max(0, px + (pw - w) // 2)
            y = max(0, py + (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        self.category_var = tk.StringVar(value="ALL")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.render_grid())

        # Определение начального запроса для онлайн-поиска
        init_query = ""
        current_input = self.app.file_var.get().strip().strip("\"'")
        if is_url(current_input):
            init_query = urlparse(normalize_url(current_input)).netloc.lower().replace("www.", "")
        elif current_input:
            init_query = os.path.splitext(os.path.basename(current_input))[0]
            init_query = re.sub(r"(?i)\b(shipping|win64|win32|binaries|launcher|game)\b", "", init_query).strip("-_ ")
        if not init_query and self.app.name_var.get().strip():
            init_query = self.app.name_var.get().strip()
        self.online_search_var = tk.StringVar(value=init_query)

        self.build_ui()
        self.render_grid()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Escape>", lambda e: self.on_close())
        self.lift()
        self.focus_force()

    def build_ui(self):
        # ── Верхняя панель ──
        top = ttk.Frame(self, padding=(14, 12, 14, 6))
        top.pack(fill="x")

        # Строка 1: Фильтр и категории
        r1 = ttk.Frame(top)
        r1.pack(fill="x", pady=(0, 6))

        ttk.Label(r1, text="Фильтр:").pack(side="left", padx=(0, 6))
        s_entry = ttk.Entry(r1, textvariable=self.search_var, width=18)
        s_entry.pack(side="left", padx=(0, 10))

        cats = [
            ("Все", "ALL"),
            ("🎮 Из игры / .exe", "EXE"),
            ("💨 Steam", "STEAM"),
            ("🌐 Веб / Онлайн", "WEB"),
            ("🖼️ Изображения", "PICS")
        ]
        for lbl, val in cats:
            rb = ttk.Radiobutton(r1, text=lbl, value=val, variable=self.category_var, command=self.render_grid)
            rb.pack(side="left", padx=4)

        # Строка 2: Онлайн-поиск и действия
        r2 = ttk.Frame(top)
        r2.pack(fill="x")

        ttk.Label(r2, text="🌐 Найти в сети:").pack(side="left", padx=(0, 6))
        q_entry = ttk.Entry(r2, textvariable=self.online_search_var, width=26)
        q_entry.pack(side="left", padx=(0, 6))
        q_entry.bind("<Return>", lambda e: self.start_online_search())

        self.btn_online = ttk.Button(r2, text="🔍 Искать логотипы", command=self.start_online_search)
        self.btn_online.pack(side="left", padx=2)

        ttk.Button(r2, text="📋 Из буфера", command=self.import_from_clipboard).pack(side="left", padx=2)
        ttk.Button(r2, text="📁 Обзор файла...", command=self.browse_custom_icon).pack(side="left", padx=2)

        self.online_status = ttk.Label(r2, text="", style="Muted.TLabel")
        self.online_status.pack(side="left", padx=(8, 0))

        # ── Основная рабочая область ──
        body = ttk.Frame(self, padding=(14, 4, 14, 6))
        body.pack(fill="both", expand=True)

        paned = ttk.PanedWindow(body, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Левая часть: Сетка иконок
        grid_container = ttk.Frame(paned)
        paned.add(grid_container, weight=4)

        self.canvas = tk.Canvas(
            grid_container, bg=self.colors["entry_bg"],
            highlightthickness=1, highlightbackground=self.colors["border"]
        )
        self.sb = ttk.Scrollbar(grid_container, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = ttk.Frame(self.canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_win = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.sb.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Колесо мыши
        self.bind("<MouseWheel>", self.on_mousewheel)
        self.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.bind("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

        # Правая часть: Предпросмотр и свойства
        details_frame = ttk.Frame(paned, padding=(14, 8))
        paned.add(details_frame, weight=1)

        ttk.Label(details_frame, text="Предпросмотр", font=("Sans", 10, "bold")).pack(anchor="w", pady=(0, 6))

        self.preview_canvas = tk.Canvas(
            details_frame, width=130, height=130, bg=self.colors["entry_bg"],
            highlightthickness=1, highlightbackground=self.colors["border"]
        )
        self.preview_canvas.pack(pady=(0, 10))

        self.det_name = ttk.Label(details_frame, text="Выберите логотип", font=("Sans", 9, "bold"), wraplength=190)
        self.det_name.pack(anchor="w", pady=2)

        self.det_res = ttk.Label(details_frame, text="Разрешение: —", style="Muted.TLabel")
        self.det_res.pack(anchor="w", pady=1)

        self.det_size = ttk.Label(details_frame, text="Размер: —", style="Muted.TLabel")
        self.det_size.pack(anchor="w", pady=1)

        self.det_source = ttk.Label(details_frame, text="Источник: —", style="Muted.TLabel")
        self.det_source.pack(anchor="w", pady=1)

        self.det_path = ttk.Label(details_frame, text="", style="Muted.TLabel", wraplength=190, font=("Monospace", 8))
        self.det_path.pack(anchor="w", pady=(6, 12))

        ttk.Separator(details_frame, orient="horizontal").pack(fill="x", pady=6)

        self.btn_apply = ttk.Button(details_frame, text="✓ Выбрать этот логотип", style="Accent.TButton", command=self.apply_selected)
        self.btn_apply.pack(fill="x", pady=4)
        ttk.Button(details_frame, text="Отмена", command=self.on_close).pack(fill="x", pady=4)

        # ── Нижний статус-бар ──
        bot = ttk.Frame(self, padding=(14, 4, 14, 8))
        bot.pack(fill="x")
        self.status_bar = ttk.Label(bot, text="", style="Muted.TLabel")
        self.status_bar.pack(side="left")

    def on_canvas_resize(self, event):
        self.canvas.itemconfig(self.canvas_win, width=event.width)

    def on_mousewheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def render_grid(self):
        # Очищаем карточки
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.thumb_refs.clear()
        self.card_widgets.clear()

        query = self.search_var.get().strip().lower()
        cat = self.category_var.get()

        filtered = []
        for score, label, path in self.all_icons:
            if not os.path.isfile(path):
                continue
            lbl_low = label.lower()
            if cat == "EXE" and not any(k in lbl_low for k in ("exe", "папка игры")):
                continue
            if cat == "STEAM" and "steam" not in lbl_low:
                continue
            if cat == "WEB" and not any(k in lbl_low for k in ("сайт", "онлайн")):
                continue
            if cat == "PICS" and not any(k in lbl_low for k in ("изображения", "система")):
                continue
            if query and (query not in lbl_low and query not in os.path.basename(path).lower()):
                continue
            filtered.append((score, label, path))

        if not filtered:
            empty_lbl = ttk.Label(
                self.scroll_frame,
                text="Логотипы не найдены.\nВоспользуйтесь онлайн-поиском или кнопкой 'Обзор...'",
                style="Muted.TLabel", justify="center"
            )
            empty_lbl.pack(pady=40, fill="both", expand=True)
            self.status_bar.config(text="Логотипы не найдены")
            return

        cols = 5
        for idx, (score, label, path) in enumerate(filtered):
            r, c = divmod(idx, cols)

            card = tk.Frame(
                self.scroll_frame, bg=self.colors["btn_bg"],
                bd=1, relief="solid", highlightthickness=1,
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["accent"],
                padx=6, pady=6, cursor="hand2"
            )
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

            # Генерация превью
            ph, tmp_t = make_thumbnail_photo(path, size=68)
            if tmp_t:
                self.temp_thumbs.append(tmp_t)

            img_lbl = tk.Label(card, bg=self.colors["btn_bg"], width=72, height=72)
            img_lbl.pack()

            if ph:
                self.thumb_refs.append(ph)
                img_lbl.config(image=ph)
            else:
                img_lbl.config(text="PNG", fg=self.colors["fg"], font=("Sans", 9, "bold"))

            # Бейдж категории
            clean_tag = label.split("]")[0].replace("[", "").strip() if "]" in label else "Лого"
            tag_lbl = tk.Label(
                card, text=clean_tag, bg=self.colors["btn_bg"],
                fg=self.colors["accent"], font=("Sans", 8, "bold")
            )
            tag_lbl.pack(pady=(2, 0))

            # Имя файла
            short_name = os.path.basename(path)
            if len(short_name) > 16:
                short_name = short_name[:14] + "…"
            name_lbl = tk.Label(
                card, text=short_name, bg=self.colors["btn_bg"],
                fg=self.colors["fg"], font=("Sans", 8)
            )
            name_lbl.pack()

            # Привязка событий клика и hover
            for widget in (card, img_lbl, tag_lbl, name_lbl):
                widget.bind("<Button-1>", lambda e, p=path, l=label, cd=card: self.select_icon(p, l, cd))
                widget.bind("<Double-Button-1>", lambda e, p=path: self.choose_and_apply(p))
                widget.bind("<Enter>", lambda e, cd=card: cd.configure(highlightbackground=self.colors["accent"]))
                widget.bind("<Leave>", lambda e, cd=card: self.refresh_card_highlight(cd))

            self.card_widgets.append((card, path))

        for col_idx in range(cols):
            self.scroll_frame.columnconfigure(col_idx, weight=1)

        self.status_bar.config(text=f"Отображено: {len(filtered)} из {len(self.all_icons)} иконок")

        # Автовыбор первой иконки, если ничего не выбрано
        if filtered and not self.selected_path:
            self.select_icon(filtered[0][2], filtered[0][1], self.card_widgets[0][0])

    def refresh_card_highlight(self, card):
        for cd, p in self.card_widgets:
            if cd == card:
                if p == self.selected_path:
                    cd.configure(highlightbackground=self.colors["accent"], bd=2)
                else:
                    cd.configure(highlightbackground=self.colors["border"], bd=1)

    def select_icon(self, path, label, card):
        self.selected_path = path
        for cd, p in self.card_widgets:
            if p == path:
                cd.configure(highlightbackground=self.colors["accent"], bd=2)
            else:
                cd.configure(highlightbackground=self.colors["border"], bd=1)

        # Обновляем правый предпросмотр
        self.preview_canvas.delete("all")
        ph, tmp_t = make_thumbnail_photo(path, size=115)
        if tmp_t:
            self.temp_thumbs.append(tmp_t)
        if ph:
            self.preview_photo_ref = ph
            self.preview_canvas.create_image(65, 65, image=ph)
        else:
            self.preview_canvas.create_text(65, 65, text="Логотип", fill=self.colors["muted"])

        fn = os.path.basename(path)
        self.det_name.config(text=fn)

        # Читаем разрешение и размер
        res_text = "—"
        if HAS_PIL:
            try:
                with Image.open(path) as im:
                    res_text = f"{im.width} × {im.height} px"
            except Exception:
                pass
        self.det_res.config(text=f"Разрешение: {res_text}")

        try:
            sz_str = format_file_size(os.path.getsize(path))
        except OSError:
            sz_str = "—"
        self.det_size.config(text=f"Размер: {sz_str}")

        clean_tag = label.split("]")[0].replace("[", "").strip() if "]" in label else "Файл"
        self.det_source.config(text=f"Источник: {clean_tag}")
        self.det_path.config(text=path)

    def choose_and_apply(self, path):
        self.selected_path = path
        self.apply_selected()

    def apply_selected(self):
        if not self.selected_path or not os.path.isfile(self.selected_path):
            messagebox.showwarning("Внимание", "Сначала выберите логотип из списка!", parent=self)
            return
        p = self.selected_path
        self.on_pick_callback(p)
        self.on_close()

    def start_online_search(self):
        query = self.online_search_var.get().strip()
        if not query:
            messagebox.showwarning("Поиск", "Введите название игры или адрес сайта для поиска!", parent=self)
            return

        self.btn_online.state(["disabled"])
        self.online_status.config(text="⏳ Идёт поиск в сети...")

        def worker():
            icons_dir = self.app.config_data["icons_dir"]
            found_new = []
            if query.startswith(("http://", "https://", "www.")) or "." in query and " " not in query:
                found_new.extend(fetch_website_icons_online(query, icons_dir))
            else:
                found_new.extend(fetch_steam_icons_online(query, icons_dir))

            self.after(0, self.on_online_search_done, found_new, query)

        threading.Thread(target=worker, daemon=True).start()

    def on_online_search_done(self, new_icons, query):
        self.btn_online.state(["!disabled"])
        if new_icons:
            seen_existing = {item[2] for item in self.all_icons}
            added = 0
            for item in new_icons:
                if item[2] not in seen_existing:
                    self.all_icons.insert(0, item)
                    seen_existing.add(item[2])
                    added += 1

            self.app.found_icons_list = self.all_icons
            labels = [it[1] for it in self.all_icons]
            self.app.found_icons_cb["values"] = labels

            self.online_status.config(text=f"✓ Найдено логотипов: {added}")
            self.selected_path = new_icons[0][2]
            self.render_grid()
        else:
            self.online_status.config(text="Ничего не найдено онлайн")
            messagebox.showinfo("Онлайн-поиск", f"По запросу '{query}' логотипы не найдены в Steam и сети.", parent=self)

    def import_from_clipboard(self):
        try:
            text = self.clipboard_get().strip()
        except Exception:
            text = ""

        if not text or not text.startswith(("http://", "https://")):
            messagebox.showinfo("Буфер обмена", "В буфере нет ссылки на картинку или сайт!", parent=self)
            return

        icons_dir = self.app.config_data["icons_dir"]
        self.online_status.config(text="Загрузка из буфера...")

        def worker():
            new_items = []
            if any(text.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".ico", ".webp", ".svg")):
                fn = os.path.basename(urlparse(text).path)
                out_p = os.path.join(icons_dir, f"clip_{fn}")
                p = download_image_as_png(text, out_p)
                if p:
                    new_items.append((135, f"[Буфер] {os.path.basename(p)}", p))
            else:
                new_items.extend(fetch_website_icons_online(text, icons_dir))

            self.after(0, self.on_online_search_done, new_items, text)

        threading.Thread(target=worker, daemon=True).start()

    def browse_custom_icon(self):
        init_dir = self.app.config_data["icons_dir"]
        dlg = CustomPathDialog(
            self, "Выбор логотипа с диска", init_dir, self.colors,
            mode="file", exts=(".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp", ".xpm")
        )
        self.wait_window(dlg)
        if dlg.result and os.path.isfile(dlg.result):
            p = dlg.result
            if p.lower().endswith((".ico", ".jpg", ".jpeg", ".webp")):
                stem = os.path.splitext(os.path.basename(p))[0].lower()
                out_p = os.path.join(self.app.config_data["icons_dir"], f"{stem}.png")
                p = convert_to_png(p, out_p) or p

            entry = (140, f"[Файл] {os.path.basename(p)}", p)
            self.all_icons.insert(0, entry)
            self.selected_path = p
            self.render_grid()

    def on_close(self):
        # Удаление временных файлов предпросмотра текущей сессии
        for tmp_f in self.temp_thumbs:
            try:
                if os.path.isfile(tmp_f):
                    os.remove(tmp_f)
            except OSError:
                pass
        self.temp_thumbs.clear()
        self.destroy()


class DesktopCreatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Менеджер ярлыков (.desktop)")
        self.geometry("800x550")
        self.resizable(False, False)
        self.config_data = self.load_config()
        self.found_icons_list = []
        self.toggle_widgets = []
        self.preview_photo = None
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.colors = THEMES.get(self.config_data.get("theme", "AMOLED Black"), THEMES["AMOLED Black"])
        self.build_ui()
        self.apply_theme(self.config_data.get("theme", "AMOLED Black"))

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return {**DEFAULT_CONFIG, **json.load(f)}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=2)

    def apply_theme(self, theme_name):
        if theme_name not in THEMES:
            theme_name = "AMOLED Black"
        self.config_data["theme"] = theme_name
        self.save_config()
        c = THEMES[theme_name]
        self.colors = c

        self.configure(bg=c["bg"])
        self.style.configure(
            ".", background=c["bg"], foreground=c["fg"],
            bordercolor=c["border"], darkcolor=c["bg"], lightcolor=c["bg"],
            font=("Sans", 10)
        )
        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("TLabel", background=c["bg"], foreground=c["fg"])
        self.style.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"], font=("Sans", 9))
        self.style.configure(
            "TEntry", fieldbackground=c["entry_bg"], foreground=c["entry_fg"],
            insertcolor=c["fg"], bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"], padding=6
        )
        self.style.configure(
            "TButton", background=c["btn_bg"], foreground=c["btn_fg"],
            bordercolor=c["border"], lightcolor=c["btn_bg"], darkcolor=c["btn_bg"],
            focuscolor=c["accent"], padding=(10, 6), relief="flat"
        )
        self.style.map(
            "TButton",
            background=[("active", c["accent"]), ("pressed", c["accent"])],
            foreground=[("active", "#ffffff")]
        )
        self.style.configure(
            "Accent.TButton", background=c["accent"], foreground="#ffffff",
            bordercolor=c["accent"], padding=(12, 6), relief="flat"
        )
        self.style.map("Accent.TButton", background=[("active", c["btn_bg"])], foreground=[("active", c["fg"])])
        self.style.configure("TRadiobutton", background=c["bg"], foreground=c["fg"], indicatorbackground=c["entry_bg"], indicatorforeground=c["accent"])
        self.style.map("TRadiobutton", background=[("active", c["bg"])])
        self.style.configure(
            "TCombobox", fieldbackground=c["entry_bg"], background=c["btn_bg"],
            foreground=c["entry_fg"], arrowcolor=c["fg"], bordercolor=c["border"], padding=5
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", c["entry_bg"])],
            foreground=[("readonly", c["entry_fg"])],
            selectbackground=[("readonly", c["entry_bg"])],
            selectforeground=[("readonly", c["entry_fg"])]
        )
        self.style.configure("TSeparator", background=c["border"])
        self.style.configure(
            "Treeview",
            background=c["entry_bg"],
            foreground=c["entry_fg"],
            fieldbackground=c["entry_bg"],
            bordercolor=c["border"],
            rowheight=26
        )
        self.style.map(
            "Treeview",
            background=[("selected", c["accent"])],
            foreground=[("selected", "#ffffff")]
        )
        self.style.configure(
            "Treeview.Heading",
            background=c["btn_bg"],
            foreground=c["fg"],
            bordercolor=c["border"],
            font=("Sans", 9, "bold"),
            padding=4
        )
        self.style.map("Treeview.Heading", background=[("active", c["border"])])
        self.option_add("*TCombobox*Listbox*Background", c["entry_bg"])
        self.option_add("*TCombobox*Listbox*Foreground", c["entry_fg"])
        self.option_add("*TCombobox*Listbox*selectBackground", c["accent"])
        self.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")

        if hasattr(self, "preview_canvas"):
            self.preview_canvas.configure(bg=c["entry_bg"], highlightbackground=c["border"])

        for tw in list(self.toggle_widgets):
            if tw.winfo_exists():
                tw.update_colors(c)
            else:
                self.toggle_widgets.remove(tw)

    def build_ui(self):
        pad = {"padx": 8, "pady": 6}
        main_frame = ttk.Frame(self, padding=16)
        main_frame.pack(fill="both", expand=True)

        # Верхняя панель
        top_bar = ttk.Frame(main_frame)
        top_bar.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        ttk.Label(top_bar, text="Тема:").pack(side="left", padx=(0, 8))
        self.theme_var = tk.StringVar(value=self.config_data.get("theme", "AMOLED Black"))
        theme_cb = ttk.Combobox(top_bar, textvariable=self.theme_var, values=list(THEMES.keys()), state="readonly", width=18)
        theme_cb.pack(side="left")
        theme_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_theme(self.theme_var.get()))

        self.status_lbl = ttk.Label(top_bar, text="Готов к работе", style="Muted.TLabel")
        self.status_lbl.pack(side="right", padx=6)

        # Название
        ttk.Label(main_frame, text="Название (Name):").grid(row=1, column=0, sticky="w", **pad)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", **pad)

        # Превью иконки
        preview_box = ttk.Frame(main_frame)
        preview_box.grid(row=1, column=3, rowspan=3, padx=(10, 0), pady=4, sticky="n")
        self.preview_canvas = tk.Canvas(preview_box, width=72, height=72, highlightthickness=1, bd=0)
        self.preview_canvas.pack()
        ttk.Label(preview_box, text="Превью", style="Muted.TLabel").pack(pady=(3, 0))

        # Файл / Ссылка / Пакет
        ttk.Label(main_frame, text="Файл / Ссылка / Пакет:").grid(row=2, column=0, sticky="w", **pad)
        self.file_var = tk.StringVar()
        file_entry = ttk.Entry(main_frame, textvariable=self.file_var, width=28)
        file_entry.grid(row=2, column=1, sticky="ew", **pad)
        file_entry.bind("<FocusOut>", lambda e: self.on_file_changed())
        file_entry.bind("<Return>", lambda e: self.on_file_changed())

        file_btn_frame = ttk.Frame(main_frame)
        file_btn_frame.grid(row=2, column=2, sticky="ew")
        ttk.Button(file_btn_frame, text="Файл...", width=8, command=self.pick_binary).pack(side="left", padx=2)
        ttk.Button(file_btn_frame, text="Пакет / yay", width=11, command=self.pick_package).pack(side="left", padx=2)

        # Способ запуска
        ttk.Label(main_frame, text="Через что запускать:").grid(row=3, column=0, sticky="w", **pad)
        self.runner_var = tk.StringVar(value="Авто")
        runner_cb = ttk.Combobox(main_frame, textvariable=self.runner_var, values=RUNNERS, state="readonly")
        runner_cb.grid(row=3, column=1, sticky="ew", **pad)
        runner_cb.bind("<<ComboboxSelected>>", lambda e: self.rebuild_exec_command())

        self.detected_lbl = ttk.Label(main_frame, text="Режим: ожидание", style="Muted.TLabel")
        self.detected_lbl.grid(row=3, column=2, sticky="w", padx=6)

        # Итоговый Exec
        ttk.Label(main_frame, text="Итоговый Exec:").grid(row=4, column=0, sticky="w", **pad)
        self.exec_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.exec_var, width=28).grid(row=4, column=1, columnspan=3, sticky="ew", **pad)

        # Поле логотипа
        ttk.Label(main_frame, text="Логотип (Icon):").grid(row=5, column=0, sticky="w", **pad)
        self.icon_var = tk.StringVar()
        self.icon_var.trace_add("write", lambda *_: self.update_icon_preview())
        ttk.Entry(main_frame, textvariable=self.icon_var, width=28).grid(row=5, column=1, sticky="ew", **pad)

        icon_btn_frame = ttk.Frame(main_frame)
        icon_btn_frame.grid(row=5, column=2, columnspan=2, sticky="ew")
        ttk.Button(icon_btn_frame, text="Файл...", width=7, command=self.pick_icon).pack(side="left", padx=2)
        ttk.Button(icon_btn_frame, text="Галерея...", width=9, command=self.open_icon_gallery).pack(side="left", padx=2)
        ttk.Button(icon_btn_frame, text="Сканировать", width=10, command=self.manual_rescan_icon).pack(side="left", padx=2)

        # Выпадающий список найденных иконок
        ttk.Label(main_frame, text="Найденные лого:").grid(row=6, column=0, sticky="w", **pad)
        self.found_icons_var = tk.StringVar()
        self.found_icons_cb = ttk.Combobox(main_frame, textvariable=self.found_icons_var, state="readonly")
        self.found_icons_cb.grid(row=6, column=1, columnspan=3, sticky="ew", **pad)
        self.found_icons_cb.bind("<<ComboboxSelected>>", self.on_select_found_icon)

        # Категории + Надёжная кнопка Терминала
        ttk.Label(main_frame, text="Категории:").grid(row=7, column=0, sticky="w", **pad)
        self.cat_var = tk.StringVar(value="Game;")
        cat_combo = ttk.Combobox(main_frame, textvariable=self.cat_var, values=[
            "Game;",
            "Network;WebBrowser;",
            "Utility;Application;",
            "Development;",
            "AudioVideo;",
            "System;"
        ])
        cat_combo.grid(row=7, column=1, sticky="ew", **pad)

        self.term_var = tk.BooleanVar(value=False)
        term_btn = ToggleButton(
            main_frame,
            text="Запускать в терминале",
            variable=self.term_var,
            colors=self.colors,
            command=lambda: self.status_lbl.config(text=f"Терминал: {'ВКЛ' if self.term_var.get() else 'ВЫКЛ'}")
        )
        term_btn.grid(row=7, column=2, columnspan=2, sticky="ew", **pad)
        self.toggle_widgets.append(term_btn)

        ttk.Separator(main_frame, orient="horizontal").grid(row=8, column=0, columnspan=4, sticky="ew", pady=12)

        # Кнопки управления
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=9, column=0, columnspan=4, sticky="ew")

        ttk.Button(btn_frame, text="Создать ярлык", style="Accent.TButton", command=self.create_desktop).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="▶ Тест запуска", command=self.test_launch).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Лог запуска", command=self.show_last_log).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Удалить ярлыки...", command=self.delete_desktop_window).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Настройки", command=self.settings_window).pack(side="right", padx=4)

        main_frame.columnconfigure(1, weight=1)

    def update_icon_preview(self):
        self.preview_canvas.delete("all")
        path = self.icon_var.get().strip()
        if not path or not os.path.isfile(path):
            self.preview_canvas.create_text(36, 36, text="Нет\nлого", fill=self.colors["muted"], font=("Sans", 8), justify="center")
            return

        tmp_prev = f"/tmp/dm_prev_{os.getpid()}.png"
        try:
            if HAS_GDK:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 60, 60, True)
                pb.savev(tmp_prev, "png", [], [])
                self.preview_photo = tk.PhotoImage(file=tmp_prev)
            elif HAS_PIL:
                with Image.open(path) as im:
                    im.thumbnail((60, 60))
                    im.save(tmp_prev, "PNG")
                self.preview_photo = tk.PhotoImage(file=tmp_prev)
            elif path.lower().endswith(".png"):
                raw_img = tk.PhotoImage(file=path)
                w, h = raw_img.width(), raw_img.height()
                factor = max(1, max(w, h) // 60)
                self.preview_photo = raw_img.subsample(factor, factor)
            else:
                self.preview_canvas.create_text(36, 36, text=os.path.splitext(path)[1], fill=self.colors["fg"], font=("Sans", 9))
                return
            self.preview_canvas.create_image(36, 36, image=self.preview_photo)
        except Exception:
            self.preview_canvas.create_text(36, 36, text="Иконка", fill=self.colors["muted"], font=("Sans", 8))

    def analyze_game_folder(self, exe_path):
        """
        Сканирует папку с .exe (а также на 2 уровня вверх, если выбрана Binaries/Win64)
        и определяет: есть ли OnlineFix/кряк, какой AppID и где лежат кастомные DLL.
        """
        if not exe_path or not os.path.exists(exe_path):
            return None, False, []

        exe_dir = os.path.dirname(os.path.abspath(exe_path))
        search_root = exe_dir
        # Если .exe лежит в Binaries/Win64 или Binaries/Win32 — поднимаемся к корню игры
        parts_low = [p.lower() for p in exe_dir.split(os.sep)]
        if "binaries" in parts_low:
            b_idx = len(parts_low) - 1 - parts_low[::-1].index("binaries")
            if b_idx > 1:
                search_root = os.sep.join(exe_dir.split(os.sep)[:b_idx])

        has_crack = False
        crack_files = {
            "onlinefix.ini", "onlinefix64.dll", "onlinefix.dll", "steamoverlay64.dll",
            "steam_settings", "goldberg", "steam_api64.dll.bak", "steam_api.dll.bak",
            "custom.ini", "dlllist.txt", "codex.ini", "flt.ini", "tenoke.ini"
        }
        detected_appid = None
        dll_dirs = {exe_dir}

        for root, dirs, files in os.walk(search_root):
            rel = os.path.relpath(root, search_root)
            if rel != "." and rel.count(os.sep) >= 3:
                dirs[:] = []
                continue
            for item in files + dirs:
                il = item.lower()
                full_item = os.path.join(root, item)
                if il in crack_files:
                    has_crack = True
                    dll_dirs.add(root)
                if il in ("onlinefix64.dll", "winmm.dll", "steam_api64.dll", "version.dll", "dnet.dll"):
                    dll_dirs.add(root)
                if il == "onlinefix.ini" and os.path.isfile(full_item):
                    has_crack = True
                    try:
                        with open(full_item, "r", encoding="utf-8", errors="ignore") as f:
                            txt = f.read()
                        m = re.search(r"(?:FakeAppId|RealAppId)\s*=\s*(\d+)", txt, re.IGNORECASE)
                        if m:
                            detected_appid = m.group(1)
                    except Exception:
                        pass
                if il == "steam_appid.txt" and os.path.isfile(full_item):
                    try:
                        with open(full_item, "r", encoding="utf-8", errors="ignore") as f:
                            m = re.search(r"(\d+)", f.read())
                            if m:
                                detected_appid = m.group(1)
                                if detected_appid == "480":
                                    has_crack = True
                    except Exception:
                        pass

        # Проверяем манифест Steam (если это чистая лицензия в steamapps)
        abs_parts = os.path.abspath(exe_path).split(os.sep)
        if "steamapps" in abs_parts and "common" in abs_parts:
            try:
                sa_idx = abs_parts.index("steamapps")
                cm_idx = abs_parts.index("common")
                if cm_idx == sa_idx + 1 and len(abs_parts) > cm_idx + 1:
                    steamapps_dir = os.sep.join(abs_parts[:sa_idx + 1])
                    install_folder = abs_parts[cm_idx + 1]
                    for fname in os.listdir(steamapps_dir):
                        if fname.startswith("appmanifest_") and fname.endswith(".acf"):
                            acf_path = os.path.join(steamapps_dir, fname)
                            with open(acf_path, "r", encoding="utf-8", errors="ignore") as f:
                                data = f.read()
                            m_dir = re.search(r'"installdir"\s+"([^"]+)"', data, re.IGNORECASE)
                            m_id = re.search(r'"appid"\s+"(\d+)"', data, re.IGNORECASE)
                            if m_dir and m_id and m_dir.group(1).lower() == install_folder.lower():
                                if not has_crack:
                                    return m_id.group(1), True, list(dll_dirs)
                                elif not detected_appid:
                                    detected_appid = "480"
            except Exception:
                pass

        if has_crack and not detected_appid:
            detected_appid = "480"

        return detected_appid, False, list(dll_dirs)

    def generate_proton_runner_script(self, target_exe, appid=None, dll_dirs=None):
        """
        Создаёт надёжный исполняемый скрипт запуска в ~/.local/share/desktop_maker/runners/,
        который запускает Steam, настраивает OnlineFix DLL Overrides, steam_appid.txt и Proton.
        """
        os.makedirs(RUNNERS_DIR, exist_ok=True)
        raw_name = self.name_var.get().strip() or os.path.splitext(os.path.basename(target_exe))[0]
        safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in raw_name.lower()) or "game"
        script_path = os.path.join(RUNNERS_DIR, f"launch_{safe_slug}.sh")

        protons = find_all_protons(target_exe)
        custom_p = self.config_data.get("custom_proton", "").strip()
        proton_bin = custom_p if (custom_p and os.path.isfile(custom_p)) else (protons[0] if protons else "")

        use_appid = str(appid or "480")
        steam_root = get_steam_root()
        game_dir = os.path.dirname(os.path.abspath(target_exe))

        # Префикс ВСЕГДА держим в домашней папке на Linux ФС (ext4/btrfs), чтобы не падал на NTFS /mnt/game
        compat_dir = os.path.join(steam_root, "steamapps", "compatdata", use_appid)
        os.makedirs(compat_dir, exist_ok=True)

        # Прописываем steam_appid.txt в папке с .exe (необходимо для OnlineFix / Goldberg под Proton)
        appid_txt = os.path.join(game_dir, "steam_appid.txt")
        if not os.path.exists(appid_txt):
            try:
                with open(appid_txt, "w", encoding="utf-8") as af:
                    af.write(f"{use_appid}\n")
            except Exception:
                pass

        dll_overrides = ";".join(ONLINEFIX_DLLS)
        extra_dll_paths = ":".join(dll_dirs) if dll_dirs else game_dir

        # Гарантируем симлинки steamclient.so в ~/.steam/sdk64 и sdk32 (нужны OnlineFix для связи со Steam)
        sdk64 = os.path.expanduser("~/.steam/sdk64")
        sdk32 = os.path.expanduser("~/.steam/sdk32")
        os.makedirs(sdk64, exist_ok=True)
        os.makedirs(sdk32, exist_ok=True)
        sc64_src = os.path.join(steam_root, "linux64", "steamclient.so")
        sc32_src = os.path.join(steam_root, "linux32", "steamclient.so")
        if os.path.isfile(sc64_src) and not os.path.exists(os.path.join(sdk64, "steamclient.so")):
            try:
                os.symlink(sc64_src, os.path.join(sdk64, "steamclient.so"))
            except OSError:
                pass
        if os.path.isfile(sc32_src) and not os.path.exists(os.path.join(sdk32, "steamclient.so")):
            try:
                os.symlink(sc32_src, os.path.join(sdk32, "steamclient.so"))
            except OSError:
                pass

        script_content = f"""#!/usr/bin/env bash
# Автоматически сгенерировано DesktopCreatorApp для {raw_name}
exec >"{LAST_LOG_PATH}" 2>&1
set -x

 GAME_EXE="{target_exe}"
GAME_DIR="{game_dir}"
STEAM_ROOT="{steam_root}"
COMPAT_DATA="{compat_dir}"
PROTON_BIN="{proton_bin}"
APPID="{use_appid}"

mkdir -p "$COMPAT_DATA"
cd "$GAME_DIR" || exit 1

# 1. Проверяем, запущен ли клиент Steam (обязателен для OnlineFix / Spacewar)
if ! pgrep -x "steam" >/dev/null 2>&1; then
    nohup steam -silent >/dev/null 2>&1 &
    for _ in {{1..15}}; do
        pgrep -x "steam" >/dev/null 2>&1 && break
        sleep 1
    done
    sleep 3
fi

# 2. Переменные окружения Steam + OnlineFix DLL Overrides
export SteamAppId="$APPID"
export SteamGameId="$APPID"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_INSTALL_PATH="$GAME_DIR"
export STEAM_COMPAT_LIBRARY_PATHS="{extra_dll_paths}:$STEAM_ROOT/steamapps"
export WINEDLLPATH="{extra_dll_paths}"
export WINEDLLOVERRIDES="{dll_overrides}"
export WINE_LARGE_ADDRESS_AWARE=1
export PROTON_NO_ESYNC=0
export PROTON_NO_FSYNC=0

# 3. Запуск через Proton / UMU / Wine
if [ -n "$PROTON_BIN" ] && [ -f "$PROTON_BIN" ]; then
    "\\$PROTON_BIN" waitforexitandrun "\\$GAME_EXE"
    RET=$?
    if [ $RET -ne 0 ] && command -v umu-run >/dev/null 2>&1; then
        WINEPREFIX="$COMPAT_DATA/pfx" GAMEID="umu-$APPID" PROTONPATH="$(dirname "$PROTON_BIN")" umu-run "$GAME_EXE"
    fi
elif command -v umu-run >/dev/null 2>&1; then
    WINEPREFIX="$COMPAT_DATA/pfx" GAMEID="umu-$APPID" umu-run "$GAME_EXE"
else
    wine "$GAME_EXE"
fi
"""
        # Исправляем вызов "$PROTON_BIN" без лишних слэшей
        script_content = script_content.replace('"\\$PROTON_BIN" waitforexitandrun "\\$GAME_EXE"', '"$PROTON_BIN" waitforexitandrun "$GAME_EXE"')

        with open(script_path, "w", encoding="utf-8") as sf:
            sf.write(script_content)
        st = os.stat(script_path)
        os.chmod(script_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return script_path

    def detect_best_runner(self, target):
        if not target:
            return "Нативно (Linux)", None, []
        if is_url(target):
            return "Веб-сайт (Браузер)", None, []
        if target.lower().endswith(".exe"):
            appid, is_clean_licensed, dll_dirs = self.analyze_game_folder(target)
            if is_clean_licensed and appid:
                return "Steam (Лицензия по AppID)", appid, dll_dirs
            return "Steam (Пиратка OnlineFix / Proton)", appid or "480", dll_dirs
        return "Нативно (Linux)", None, []

    def build_command_for_runner(self, runner, target):
        if not target:
            return ""

        appid, is_clean_licensed, dll_dirs = self.analyze_game_folder(target)

        if runner == "Авто":
            actual_runner, auto_appid, dll_dirs = self.detect_best_runner(target)
            self.detected_lbl.config(text=f"Авто: {actual_runner[:24]}")
            runner = actual_runner
            if auto_appid:
                appid = auto_appid
        else:
            self.detected_lbl.config(text=f"Режим: {runner[:24]}")

        if runner == "Веб-сайт (Браузер)":
            return f"xdg-open {normalize_url(target)}"

        if runner == "Steam (Пиратка OnlineFix / Proton)":
            if os.path.isfile(target):
                script_p = self.generate_proton_runner_script(target, appid or "480", dll_dirs)
                return f'"{script_p}"' if " " in script_p else script_p
            return f'wine "{target}"'

        if runner == "Steam (Лицензия по AppID)":
            if appid and is_clean_licensed:
                return f"steam steam://rungameid/{appid}"
            elif appid:
                return f"steam steam://rungameid/{appid}"
            if os.path.isfile(target):
                return self.generate_proton_runner_script(target, "480", dll_dirs)
            return f'steam "{target}"'

        dll_env = f'env SteamAppId={appid or "480"} SteamGameId={appid or "480"} WINEDLLOVERRIDES="{";".join(ONLINEFIX_DLLS)}" '

        if runner == "Faugus Launcher":
            fcmd = get_faugus_cmd()
            return f'{dll_env}{fcmd} "{target}"'

        if runner == "PortProton":
            return f'{dll_env}portproton "{target}"'

        if runner == "Wine":
            return f'{dll_env}wine "{target}"'

        # Нативно (Linux)
        if target.lower().endswith(".exe") and os.path.isfile(target):
            return self.generate_proton_runner_script(target, appid or "480", dll_dirs)
        return f'"{target}"' if " " in target else target

    def rebuild_exec_command(self):
        raw_input = self.file_var.get().strip().strip("\"'")
        target = raw_input if is_url(raw_input) else os.path.expanduser(raw_input)
        cmd = self.build_command_for_runner(self.runner_var.get(), target)
        if cmd:
            self.exec_var.set(cmd)

    def collect_all_icons(self, raw_input):
        raw_input = raw_input.strip().strip("\"'")
        icons_dir = self.config_data["icons_dir"]
        os.makedirs(icons_dir, exist_ok=True)
        found = []
        seen_paths = set()

        def add_candidate(score, tag, path):
            if not path or not os.path.isfile(path):
                return
            # Автоматическая конвертация любого не-PNG в чистый PNG без лишних действий пользователя
            if not path.lower().endswith(".png"):
                stem = os.path.splitext(os.path.basename(path))[0].lower()
                out_c = os.path.join(icons_dir, f"{stem}_auto.png")
                path = convert_to_png(path, out_c) or path

            rp = os.path.realpath(path)
            if rp in seen_paths:
                return
            seen_paths.add(rp)
            found.append((score, f"[{tag}] {os.path.basename(path)}", path))

        if is_url(raw_input):
            # Онлайн-парсинг иконок сайта (Google Favicon 128, DuckDuckGo, Touch Icon, og:image)
            web_icons = fetch_website_icons_online(raw_input, icons_dir)
            for sc, lbl, p in web_icons:
                add_candidate(sc, lbl.replace("[", "").replace("]", ""), p)
        else:
            raw_path = os.path.expanduser(raw_input)
            stem = os.path.splitext(os.path.basename(raw_path))[0].lower() if raw_path else ""

            if os.path.isfile(raw_path):
                folder = os.path.dirname(os.path.abspath(raw_path))

                if raw_path.lower().endswith(".exe"):
                    exe_icons = extract_icons_from_exe_pure_python(raw_path, icons_dir, stem)
                    for idx, p in enumerate(exe_icons):
                        add_candidate(120 - idx, "Из .exe", p)

                # Глубокий рекурсивный поиск в папке игры (до 4 уровней вглубь)
                exts = (".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp", ".xpm")
                for root, dirs, files in os.walk(folder):
                    rel = os.path.relpath(root, folder)
                    depth = 0 if rel == "." else rel.count(os.sep) + 1
                    if depth > 4:
                        dirs[:] = []
                        continue
                    for f in files:
                        fl = f.lower()
                        if fl.endswith(exts):
                            full_p = os.path.join(root, f)
                            sc = 50 - depth * 4
                            if stem and stem in fl:
                                sc += 50
                            if any(k in fl for k in ("icon", "logo", "app", "header", "banner", "splash", "capsule")):
                                sc += 30
                            add_candidate(sc, "Папка игры", full_p)

                # Поиск AppID и Steam логотипов (локальный кэш + онлайн Steam CDN)
                appid, _, _ = self.analyze_game_folder(raw_path)
                if appid and appid != "480":
                    # Локальный кэш Steam
                    lib_cache = os.path.join(get_steam_root(), "appcache", "librarycache")
                    if os.path.isdir(lib_cache):
                        for root, _, files in os.walk(lib_cache):
                            for f in files:
                                if f.startswith(str(appid)) or os.path.basename(root) == str(appid):
                                    if f.lower().endswith((".png", ".jpg", ".ico", ".webp")):
                                        fp = os.path.join(root, f)
                                        add_candidate(100, "Steam Cache", fp)

                    # Автоматический онлайн-поиск в Steam CDN без скачивания пользователем
                    steam_online = fetch_steam_icons_online(appid, icons_dir)
                    for sc, lbl, p in steam_online:
                        add_candidate(sc, lbl.replace("[", "").replace("]", ""), p)
                elif stem and stem not in ("setup", "install", "launcher", "game", "start"):
                    # Поиск по названию игры в Steam Store API
                    steam_online = fetch_steam_icons_online(stem, icons_dir)
                    for sc, lbl, p in steam_online:
                        add_candidate(sc, lbl.replace("[", "").replace("]", ""), p)

            # Системные иконки Linux
            if stem:
                sys_dirs = [
                    "/usr/share/pixmaps",
                    "/usr/share/icons/hicolor/256x256/apps",
                    "/usr/share/icons/hicolor/128x128/apps",
                    "/usr/share/icons/hicolor/scalable/apps",
                    os.path.expanduser("~/.local/share/icons")
                ]
                for sd in sys_dirs:
                    if os.path.isdir(sd):
                        for f in os.listdir(sd):
                            if stem in f.lower() and f.lower().endswith((".png", ".svg")):
                                add_candidate(95, "Система", os.path.join(sd, f))

        # Поиск в личной папке Изображений
        q_stem = os.path.splitext(os.path.basename(raw_input))[0].lower() if raw_input else ""
        if os.path.isdir(icons_dir):
            for f in sorted(os.listdir(icons_dir)):
                fl = f.lower()
                if fl.endswith((".png", ".svg", ".ico", ".jpg", ".jpeg", ".webp")):
                    fp = os.path.join(icons_dir, f)
                    sc = 115 if (q_stem and q_stem in fl) else 35
                    add_candidate(sc, "Изображения", fp)

        found.sort(key=lambda x: x[0], reverse=True)
        self.found_icons_list = found

        labels = [item[1] for item in found]
        self.found_icons_cb["values"] = labels
        if found:
            self.found_icons_cb.current(0)
            return found[0][2]
        return None

    def on_select_found_icon(self, _=None):
        idx = self.found_icons_cb.current()
        if 0 <= idx < len(self.found_icons_list):
            chosen = self.found_icons_list[idx][2]
            self.icon_var.set(chosen)

    def on_file_changed(self):
        val = self.file_var.get().strip().strip("\"'")
        if not val:
            return

        if is_url(val):
            url = normalize_url(val)
            domain = urlparse(url).netloc.lower().replace("www.", "")
            site_name = domain.split(".")[0].capitalize() if domain else "Website"
            if not self.name_var.get().strip():
                self.name_var.set(site_name)
            self.cat_var.set("Network;WebBrowser;")
            self.runner_var.set("Веб-сайт (Браузер)")
            self.rebuild_exec_command()
            best_icon = self.collect_all_icons(val)
            if best_icon and not self.icon_var.get().strip():
                self.icon_var.set(best_icon)
            return

        raw = os.path.expanduser(val)
        if os.path.exists(raw):
            stem = os.path.splitext(os.path.basename(raw))[0]
            if not self.name_var.get().strip():
                self.name_var.set(stem.capitalize())
            if raw.lower().endswith(".exe"):
                self.cat_var.set("Game;")
            self.rebuild_exec_command()
            best_icon = self.collect_all_icons(raw)
            if best_icon:
                self.icon_var.set(best_icon)
        else:
            self.rebuild_exec_command()

    def manual_rescan_icon(self):
        best = self.collect_all_icons(self.file_var.get())
        if best:
            self.icon_var.set(best)
            self.status_lbl.config(text=f"Найдено иконок: {len(self.found_icons_list)}")
        else:
            messagebox.showinfo("Поиск иконок", "Подходящие иконки не найдены.")

    def open_icon_gallery(self):
        if not self.found_icons_list:
            self.collect_all_icons(self.file_var.get())

        def on_picked(chosen_path):
            if chosen_path.lower().endswith((".ico", ".jpg", ".jpeg", ".webp")):
                stem = os.path.splitext(os.path.basename(chosen_path))[0].lower()
                out_p = os.path.join(self.config_data["icons_dir"], f"{stem}.png")
                chosen_path = convert_to_png(chosen_path, out_p) or chosen_path
            self.icon_var.set(chosen_path)
            self.status_lbl.config(text=f"✓ Выбран логотип: {os.path.basename(chosen_path)}")

        IconGalleryDialog(self, self, self.found_icons_list, on_picked)

    def pick_binary(self):
        cur = self.file_var.get().strip().strip("\"'")
        init_dir = os.path.dirname(cur) if os.path.exists(cur) else os.path.expanduser("~")
        dlg = CustomPathDialog(self, "Выбор файла / .exe / бинарника", init_dir, self.colors, mode="file")
        self.wait_window(dlg)
        if dlg.result:
            self.file_var.set(dlg.result)
            self.name_var.set("")
            self.icon_var.set("")
            self.runner_var.set("Авто")
            self.on_file_changed()

    def pick_icon(self):
        init_dir = self.config_data["icons_dir"]
        dlg = CustomPathDialog(
            self, "Выбор логотипа", init_dir, self.colors,
            mode="file", exts=(".png", ".svg", ".ico", ".jpg", ".jpeg", ".xpm")
        )
        self.wait_window(dlg)
        if dlg.result:
            chosen = dlg.result
            if chosen.lower().endswith((".ico", ".jpg", ".jpeg")):
                stem = os.path.splitext(os.path.basename(chosen))[0].lower()
                out_png = os.path.join(self.config_data["icons_dir"], f"{stem}.png")
                chosen = convert_to_png(chosen, out_png) or chosen
            self.icon_var.set(chosen)

    def ensure_native_executable(self, raw_file):
        if os.path.isfile(raw_file) and not raw_file.lower().endswith(".exe"):
            if not os.access(raw_file, os.X_OK):
                try:
                    st = os.stat(raw_file)
                    os.chmod(raw_file, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                except Exception:
                    pass

    def show_last_log(self):
        win = tk.Toplevel(self)
        win.title("Лог последнего запуска")
        win.geometry("680x420")
        win.configure(bg=self.colors["bg"])
        win.transient(self)

        txt = tk.Text(
            win, bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
            font=("Monospace", 9), bd=0, highlightthickness=1, highlightbackground=self.colors["border"]
        )
        txt.pack(fill="both", expand=True, padx=12, pady=12)

        if os.path.isfile(LAST_LOG_PATH):
            try:
                with open(LAST_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                    txt.insert("1.0", f.read())
            except Exception as e:
                txt.insert("1.0", f"Ошибка чтения лога: {e}")
        else:
            txt.insert("1.0", "Лог пока пуст. Нажмите '▶ Тест запуска'.")

        ttk.Button(win, text="Закрыть", command=win.destroy).pack(pady=(0, 10))

    def test_launch(self):
        self.rebuild_exec_command()
        cmd = self.exec_var.get().strip()
        if not cmd:
            messagebox.showwarning("Внимание", "Сначала выберите файл, ссылку или укажите команду запуска!")
            return

        runner = self.runner_var.get()
        if runner == "Faugus Launcher":
            fcmd = get_faugus_cmd()
            if not fcmd.startswith("flatpak") and not shutil.which(fcmd) and not os.path.isfile(fcmd):
                messagebox.showerror(
                    "Faugus не найден",
                    "В системе не найден Faugus Launcher!\nВыберите режим 'Steam (Пиратка OnlineFix / Proton)'."
                )
                return

        raw_input = self.file_var.get().strip().strip("\"'")
        raw_file = "" if is_url(raw_input) else os.path.expanduser(raw_input)

        if raw_file:
            self.ensure_native_executable(raw_file)

        work_dir = os.path.dirname(raw_file) if (raw_file and os.path.isfile(raw_file)) else os.path.expanduser("~")
        self.status_lbl.config(text="Запуск теста...")

        # Если включена кнопка "Запускать в терминале" — открываем реальный терминал
        if self.term_var.get():
            term_args = find_terminal_emulator()
            if term_args:
                bash_wrap = f'{cmd}; echo ""; read -p "Процесс завершен. Нажмите Enter для закрытия..."'
                subprocess.Popen(term_args + ["bash", "-c", bash_wrap], cwd=work_dir)
                self.status_lbl.config(text="✓ Запущено в терминале")
                return

        try:
            proc = subprocess.Popen(cmd, shell=True, cwd=work_dir, stderr=subprocess.PIPE, text=True)

            def check_proc():
                ret = proc.poll()
                if ret is not None and ret != 0:
                    err = (proc.stderr.read() if proc.stderr else "").strip()
                    if not err and os.path.isfile(LAST_LOG_PATH):
                        try:
                            with open(LAST_LOG_PATH, "r", encoding="utf-8", errors="ignore") as lf:
                                err = lf.read()[-800:]
                        except Exception:
                            pass
                    self.status_lbl.config(text=f"Ошибка запуска (код {ret})")
                    messagebox.showerror("Ошибка при запуске", f"Команда завершилась с кодом {ret}:\n\n{err or cmd}")
                else:
                    self.status_lbl.config(text="✓ Тест запущен")

            self.after(2000, check_proc)
        except Exception as e:
            messagebox.showerror("Ошибка запуска", f"Не удалось запустить:\n{e}")

    def update_gnome_menu(self):
        app_dir = os.path.expanduser("~/.local/share/applications")
        os.makedirs(app_dir, exist_ok=True)
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", app_dir], stderr=subprocess.DEVNULL)

    def create_desktop(self):
        self.rebuild_exec_command()
        name = self.name_var.get().strip()
        exec_cmd = self.exec_var.get().strip()
        icon = self.icon_var.get().strip()
        categories = self.cat_var.get().strip()
        terminal = "true" if self.term_var.get() else "false"

        if not name or not exec_cmd:
            messagebox.showwarning("Внимание", "Заполните поля 'Название' и 'Итоговый Exec'!")
            return

        if icon.lower().endswith((".ico", ".jpg", ".jpeg")) and os.path.exists(icon):
            stem = "".join(c if c.isalnum() else "_" for c in name.lower())
            out_png = os.path.join(self.config_data["icons_dir"], f"{stem}.png")
            icon = convert_to_png(icon, out_png) or icon
            self.icon_var.set(icon)

        raw_input = self.file_var.get().strip().strip("\"'")
        raw_file = "" if is_url(raw_input) else os.path.expanduser(raw_input)

        work_dir_line = ""
        if raw_file and os.path.isfile(raw_file):
            self.ensure_native_executable(raw_file)
            work_dir_line = f"Path={os.path.dirname(os.path.abspath(raw_file))}\n"

        content = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Exec={exec_cmd}\n"
            f"{work_dir_line}"
            f"Icon={icon}\n"
            f"Terminal={terminal}\n"
            f"Categories={categories}\n"
        )

        safe_filename = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.lower()) + ".desktop"
        target_dir = self.config_data["target_dir"]
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, safe_filename)

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            st = os.stat(target_path)
            os.chmod(target_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            if self.config_data.get("also_app_menu", True):
                app_dir = os.path.expanduser("~/.local/share/applications")
                os.makedirs(app_dir, exist_ok=True)
                app_link = os.path.join(app_dir, safe_filename)
                if os.path.abspath(target_path) != os.path.abspath(app_link):
                    if os.path.lexists(app_link):
                        os.remove(app_link)
                    os.symlink(target_path, app_link)
                self.update_gnome_menu()

            self.status_lbl.config(text=f"✓ Создан: {safe_filename}")
            messagebox.showinfo("Готово", f"Ярлык создан и добавлен в меню GNOME:\n{target_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать ярлык:\n{e}")

    def delete_desktop_window(self):
        win = tk.Toplevel(self)
        win.title("Менеджер .desktop файлов (Удаление)")
        win.geometry("680x430")
        win.configure(bg=self.colors["bg"])
        win.transient(self)

        target_dir = self.config_data["target_dir"]
        app_dir = os.path.expanduser("~/.local/share/applications")

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=f"Фильтр: только *.desktop в {target_dir} и меню GNOME").pack(side="left")

        search_var = tk.StringVar()
        s_entry = ttk.Entry(top, textvariable=search_var, width=22)
        s_entry.pack(side="right")
        ttk.Label(top, text="Поиск:").pack(side="right", padx=6)

        mid = ttk.Frame(win, padding=(10, 0))
        mid.pack(fill="both", expand=True)

        listbox = tk.Listbox(
            mid, selectmode=tk.EXTENDED,
            bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
            selectbackground=self.colors["accent"], selectforeground="#ffffff",
            highlightthickness=1, highlightbackground=self.colors["border"], bd=0, font=("Sans", 10)
        )
        sb = ttk.Scrollbar(mid, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=sb.set)
        listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        items_map = []

        def parse_desktop_name(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Name="):
                            return line.split("=", 1)[1].strip()
            except Exception:
                pass
            return ""

        def refresh(*_):
            listbox.delete(0, tk.END)
            items_map.clear()
            q = search_var.get().strip().lower()
            seen = set()

            for d in (target_dir, app_dir):
                if os.path.isdir(d):
                    for f in sorted(os.listdir(d)):
                        if f.endswith(".desktop"):
                            seen.add(f)

            for fname in sorted(seen):
                p_home = os.path.join(target_dir, fname)
                p_app = os.path.join(app_dir, fname)
                real_p = p_home if os.path.exists(p_home) else p_app
                disp_name = parse_desktop_name(real_p)
                locs = []
                if os.path.lexists(p_home):
                    locs.append(target_dir)
                if os.path.lexists(p_app):
                    locs.append("GNOME Menu")
                label = f"{fname}   —   [{disp_name}]   ({', '.join(locs)})"
                if not q or q in label.lower():
                    items_map.append(fname)
                    listbox.insert(tk.END, label)

        search_var.trace_add("write", refresh)
        refresh()

        def delete_selected():
            sel = listbox.curselection()
            if not sel:
                return
            if not messagebox.askyesno("Подтверждение", f"Удалить выбранные .desktop файлы ({len(sel)} шт.)?", parent=win):
                return
            for idx in sel:
                fname = items_map[idx]
                for folder in (target_dir, app_dir):
                    fpath = os.path.join(folder, fname)
                    try:
                        if os.path.lexists(fpath):
                            os.remove(fpath)
                    except Exception as e:
                        messagebox.showerror("Ошибка", f"Не удалось удалить {fpath}: {e}", parent=win)
            self.update_gnome_menu()
            refresh()

        bot = ttk.Frame(win, padding=10)
        bot.pack(fill="x")
        ttk.Button(bot, text="Удалить выбранные", style="Accent.TButton", command=delete_selected).pack(side="left", padx=4)
        ttk.Button(bot, text="Открыть папку в ФМ", command=lambda: subprocess.Popen(["xdg-open", target_dir])).pack(side="left", padx=4)
        ttk.Button(bot, text="Закрыть", command=win.destroy).pack(side="right", padx=4)

    def pick_package(self):
        win = tk.Toplevel(self)
        win.title("Пакеты (Официальные репо + AUR / yay)")
        win.geometry("560x480")
        win.configure(bg=self.colors["bg"])
        win.transient(self)

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")

        filter_var = tk.StringVar(value="ALL")
        f_bar = ttk.Frame(top)
        f_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(f_bar, text="Источник:").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(f_bar, text="Все", value="ALL", variable=filter_var).pack(side="left", padx=4)
        ttk.Radiobutton(f_bar, text="Только yay / AUR (-Qm)", value="AUR", variable=filter_var).pack(side="left", padx=4)
        ttk.Radiobutton(f_bar, text="Явно установленные (-Qe)", value="EXP", variable=filter_var).pack(side="left", padx=4)

        search_var = tk.StringVar()
        ttk.Label(top, text="Быстрый поиск:").pack(anchor="w")
        s_entry = ttk.Entry(top, textvariable=search_var)
        s_entry.pack(fill="x", pady=4)
        s_entry.focus_set()

        mid = ttk.Frame(win, padding=(10, 0))
        mid.pack(fill="both", expand=True)
        listbox = tk.Listbox(
            mid, bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
            selectbackground=self.colors["accent"], selectforeground="#ffffff",
            highlightthickness=1, highlightbackground=self.colors["border"], bd=0, font=("Sans", 10)
        )
        sb = ttk.Scrollbar(mid, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=sb.set)
        listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        runner = "yay" if shutil.which("yay") else "pacman"
        try:
            all_pkgs = subprocess.check_output([runner, "-Qq"], text=True).splitlines()
            aur_pkgs = set(subprocess.check_output([runner, "-Qmq"], text=True).splitlines())
            exp_pkgs = set(subprocess.check_output([runner, "-Qeq"], text=True).splitlines())
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить пакеты: {e}", parent=win)
            win.destroy()
            return

        def update_list(*_):
            q = search_var.get().strip().lower()
            mode = filter_var.get()
            listbox.delete(0, tk.END)

            pool = all_pkgs
            if mode == "AUR":
                pool = [p for p in all_pkgs if p in aur_pkgs]
            elif mode == "EXP":
                pool = [p for p in all_pkgs if p in exp_pkgs]

            exact, starts, contains = [], [], []
            for p in pool:
                pl = p.lower()
                if not q or q in pl:
                    tag = "[AUR/yay]" if p in aur_pkgs else "[Repo]"
                    label = f"{p}   {tag}"
                    if pl == q:
                        exact.append(label)
                    elif pl.startswith(q):
                        starts.append(label)
                    else:
                        contains.append(label)

            for item in exact + starts + contains:
                listbox.insert(tk.END, item)

        search_var.trace_add("write", update_list)
        filter_var.trace_add("write", update_list)
        update_list()

        def apply_selected(_=None):
            sel = listbox.curselection()
            if not sel:
                return
            pkg = listbox.get(sel[0]).split()[0]

            try:
                files = subprocess.check_output([runner, "-Qlq", pkg], text=True).splitlines()
            except Exception:
                files = []

            bins = [
                f for f in files
                if (f.startswith("/usr/bin/") or f.startswith("/opt/"))
                and not f.endswith("/")
                and os.access(f, os.X_OK)
                and not f.endswith(".so")
            ]
            pkg_icons = [
                f for f in files
                if f.lower().endswith((".png", ".svg")) and ("icons" in f or "pixmaps" in f)
            ]

            chosen_bin = pkg
            if len(bins) == 1:
                chosen_bin = bins[0]
            elif len(bins) > 1:
                chosen_bin = self.choose_from_list_dialog(win, f"Выберите бинарник пакета {pkg}", bins) or bins[0]

            self.file_var.set(chosen_bin)
            self.name_var.set(pkg.capitalize())
            self.runner_var.set("Нативно (Linux)")
            self.rebuild_exec_command()

            best = self.collect_all_icons(chosen_bin)
            if pkg_icons:
                pkg_icons.sort(key=lambda x: ("256" in x or "128" in x or "scalable" in x), reverse=True)
                self.icon_var.set(pkg_icons[0])
            elif best:
                self.icon_var.set(best)

            win.destroy()

        listbox.bind("<Double-Button-1>", apply_selected)
        ttk.Button(win, text="Выбрать пакет", style="Accent.TButton", command=apply_selected).pack(pady=10)

    def choose_from_list_dialog(self, parent, title, items):
        d = tk.Toplevel(parent)
        d.title(title)
        d.geometry("440x320")
        d.configure(bg=self.colors["bg"])
        d.transient(parent)
        res = {"val": None}

        lb = tk.Listbox(
            d, bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
            selectbackground=self.colors["accent"], selectforeground="#ffffff",
            highlightthickness=1, highlightbackground=self.colors["border"], bd=0
        )
        lb.pack(fill="both", expand=True, padx=10, pady=10)
        for i in items:
            lb.insert(tk.END, i)
        lb.selection_set(0)

        def ok():
            s = lb.curselection()
            if s:
                res["val"] = lb.get(s[0])
            d.destroy()

        ttk.Button(d, text="ОК", style="Accent.TButton", command=ok).pack(pady=6)
        parent.wait_window(d)
        return res["val"]

    def settings_window(self):
        win = tk.Toplevel(self)
        win.title("Настройки")
        win.geometry("720x340")
        win.configure(bg=self.colors["bg"])
        win.transient(self)

        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)

        pad = {"padx": 8, "pady": 8}
        t_var = tk.StringVar(value=self.config_data["target_dir"])
        i_var = tk.StringVar(value=self.config_data["icons_dir"])
        p_var = tk.StringVar(value=self.config_data.get("custom_proton", ""))
        m_var = tk.BooleanVar(value=self.config_data.get("also_app_menu", True))

        protons = find_all_protons(self.file_var.get())
        if not p_var.get() and protons:
            p_var.set(protons[0])

        def pick_dir_custom(var):
            dlg = CustomPathDialog(win, "Выбор папки", var.get(), self.colors, mode="dir")
            win.wait_window(dlg)
            if dlg.result:
                var.set(dlg.result)

        def pick_dir_system(var):
            chosen = filedialog.askdirectory(parent=win, initialdir=var.get() if os.path.isdir(var.get()) else os.path.expanduser("~"))
            if chosen:
                var.set(chosen)

        # Строка 0: Папка сохранения .desktop
        ttk.Label(frame, text="Папка сохранения .desktop:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=t_var, width=32).grid(row=0, column=1, sticky="ew", **pad)
        b_row0 = ttk.Frame(frame)
        b_row0.grid(row=0, column=2, sticky="ew")
        ttk.Button(b_row0, text="Обзор...", width=9, command=lambda: pick_dir_custom(t_var)).pack(side="left", padx=2)
        ttk.Button(b_row0, text="ФМ", width=5, command=lambda: pick_dir_system(t_var)).pack(side="left", padx=2)

        # Строка 1: Папка с логотипами
        ttk.Label(frame, text="Папка с логотипами:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=i_var, width=32).grid(row=1, column=1, sticky="ew", **pad)
        b_row1 = ttk.Frame(frame)
        b_row1.grid(row=1, column=2, sticky="ew")
        ttk.Button(b_row1, text="Обзор...", width=9, command=lambda: pick_dir_custom(i_var)).pack(side="left", padx=2)
        ttk.Button(b_row1, text="ФМ", width=5, command=lambda: pick_dir_system(i_var)).pack(side="left", padx=2)

        # Строка 2: Версия Proton
        ttk.Label(frame, text="Версия Steam Proton:").grid(row=2, column=0, sticky="w", **pad)
        p_cb = ttk.Combobox(frame, textvariable=p_var, values=protons)
        p_cb.grid(row=2, column=1, columnspan=2, sticky="ew", **pad)

        # Строка 3: Надёжный переключатель меню GNOME
        gnome_toggle = ToggleButton(
            frame,
            text="Добавлять ярлык в меню GNOME (~/.local/share/applications)",
            variable=m_var,
            colors=self.colors
        )
        gnome_toggle.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=10)
        self.toggle_widgets.append(gnome_toggle)

        # Строка 4: Кнопки Сохранить / Сброс / Отмена
        bot_bar = ttk.Frame(frame)
        bot_bar.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(14, 0))

        def save():
            self.config_data["target_dir"] = os.path.expanduser(t_var.get().strip())
            self.config_data["icons_dir"] = os.path.expanduser(i_var.get().strip())
            self.config_data["custom_proton"] = p_var.get().strip()
            self.config_data["also_app_menu"] = m_var.get()
            self.save_config()
            self.rebuild_exec_command()
            self.status_lbl.config(text="✓ Настройки сохранены")
            win.destroy()

        def reset_defaults():
            t_var.set(DEFAULT_CONFIG["target_dir"])
            i_var.set(DEFAULT_CONFIG["icons_dir"])
            m_var.set(True)
            if protons:
                p_var.set(protons[0])

        ttk.Button(bot_bar, text="Сохранить настройки", style="Accent.TButton", command=save).pack(side="left", padx=4)
        ttk.Button(bot_bar, text="Сбросить по умолчанию", command=reset_defaults).pack(side="left", padx=4)
        ttk.Button(bot_bar, text="Отмена", command=win.destroy).pack(side="right", padx=4)

        frame.columnconfigure(1, weight=1)
        win.lift()
        win.focus_force()


if __name__ == "__main__":
    app = DesktopCreatorApp()
    app.mainloop()