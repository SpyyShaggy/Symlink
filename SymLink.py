#!/usr/bin/env python3
import os
import re
import stat
import struct
import subprocess
import json
import shutil
import urllib.request
from urllib.parse import urlparse
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
    "target_dir": "/home/spyyshaggy",
    "icons_dir": "/home/spyyshaggy/Изображения",
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


class CustomPathDialog(tk.Toplevel):
    """Окно выбора файла или папки без блокировок Wayland."""
    def __init__(self, parent, title, init_dir, theme_colors, mode="file", exts=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("680x470")
        self.transient(parent)
        self.result = None
        self.mode = mode
        self.exts = exts
        self.colors = theme_colors
        self.configure(bg=self.colors["bg"])

        cur_dir = init_dir if (init_dir and os.path.isdir(init_dir)) else os.path.expanduser("~")
        self.path_var = tk.StringVar(value=cur_dir)

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Путь (можно вставить и нажать Enter):").pack(anchor="w")

        bar = ttk.Frame(top)
        bar.pack(fill="x", pady=4)
        self.path_entry = ttk.Entry(bar, textvariable=self.path_var)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.path_entry.bind("<Return>", lambda e: self.on_enter_path())

        ttk.Button(bar, text="Перейти", width=9, command=self.on_enter_path).pack(side="left", padx=2)
        ttk.Button(bar, text="⬆ Вверх", width=8, command=self.go_up).pack(side="left", padx=2)

        mid = ttk.Frame(self, padding=(10, 0))
        mid.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            mid, bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
            selectbackground=self.colors["accent"], selectforeground="#ffffff",
            highlightthickness=1, highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"], bd=0, font=("Sans", 10)
        )
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.listbox.bind("<Double-Button-1>", self.on_double_click)

        bot = ttk.Frame(self, padding=10)
        bot.pack(fill="x")
        if self.mode == "dir":
            ttk.Button(bot, text="Выбрать открытую папку", style="Accent.TButton", command=self.accept_current_dir).pack(side="right", padx=4)
            ttk.Button(bot, text="Выбрать выделенную", command=self.accept_current).pack(side="right", padx=4)
        else:
            ttk.Button(bot, text="Выбрать файл", style="Accent.TButton", command=self.accept_current).pack(side="right", padx=4)
        ttk.Button(bot, text="Отмена", command=self.destroy).pack(side="right", padx=4)

        self.refresh_dir(cur_dir)
        self.lift()
        self.focus_force()

    def refresh_dir(self, d):
        if not os.path.isdir(d):
            return
        self.cur_dir = os.path.abspath(d)
        self.path_var.set(self.cur_dir)
        self.listbox.delete(0, tk.END)
        try:
            items = os.listdir(self.cur_dir)
        except PermissionError:
            return

        dirs = sorted([x for x in items if os.path.isdir(os.path.join(self.cur_dir, x)) and not x.startswith(".")], key=str.lower)
        files = sorted([x for x in items if os.path.isfile(os.path.join(self.cur_dir, x)) and not x.startswith(".")], key=str.lower)

        for folder in dirs:
            self.listbox.insert(tk.END, f"📁 {folder}")

        if self.mode == "file":
            for f in files:
                if self.exts and not any(f.lower().endswith(ext) for ext in self.exts):
                    continue
                self.listbox.insert(tk.END, f)

    def go_up(self):
        parent = os.path.dirname(self.cur_dir)
        if parent and parent != self.cur_dir:
            self.refresh_dir(parent)

    def on_enter_path(self):
        p = os.path.expanduser(self.path_var.get().strip())
        if os.path.isdir(p):
            self.refresh_dir(p)
        elif os.path.isfile(p) and self.mode == "file":
            self.result = os.path.abspath(p)
            self.destroy()

    def on_double_click(self, _):
        sel = self.listbox.curselection()
        if not sel:
            return
        val = self.listbox.get(sel[0])
        if val.startswith("📁 "):
            folder = val.replace("📁 ", "", 1)
            self.refresh_dir(os.path.join(self.cur_dir, folder))
        else:
            full = os.path.join(self.cur_dir, val)
            self.path_var.set(full)
            if self.mode == "file":
                self.result = full
                self.destroy()

    def accept_current_dir(self):
        p = os.path.expanduser(self.path_var.get().strip())
        if os.path.isdir(p):
            self.result = os.path.abspath(p)
            self.destroy()

    def accept_current(self):
        sel = self.listbox.curselection()
        if sel:
            val = self.listbox.get(sel[0])
            if val.startswith("📁 "):
                chosen = os.path.join(self.cur_dir, val.replace("📁 ", "", 1))
            else:
                chosen = os.path.join(self.cur_dir, val)
        else:
            chosen = os.path.expanduser(self.path_var.get().strip())

        if self.mode == "dir" and os.path.isdir(chosen):
            self.result = os.path.abspath(chosen)
            self.destroy()
        elif self.mode == "file" and os.path.exists(chosen) and not os.path.isdir(chosen):
            self.result = os.path.abspath(chosen)
            self.destroy()
        elif self.mode == "file" and not os.path.isdir(chosen) and chosen:
            self.result = chosen
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
            rp = os.path.realpath(path)
            if rp in seen_paths:
                return
            seen_paths.add(rp)
            found.append((score, f"[{tag}] {os.path.basename(path)}", path))

        if is_url(raw_input):
            url = normalize_url(raw_input)
            domain = urlparse(url).netloc.lower().replace("www.", "")
            stem = domain.split(".")[0] if domain else "website"

            out_png = os.path.join(icons_dir, f"{stem}.png")
            try:
                fav_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
                req = urllib.request.Request(fav_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=3) as resp, open(out_png, "wb") as out_f:
                    out_f.write(resp.read())
                if os.path.isfile(out_png) and os.path.getsize(out_png) > 100:
                    add_candidate(120, "Сайт", out_png)
            except Exception:
                pass
        else:
            raw_path = os.path.expanduser(raw_input)
            stem = os.path.splitext(os.path.basename(raw_path))[0].lower() if raw_path else ""

            if os.path.isfile(raw_path):
                folder = os.path.dirname(os.path.abspath(raw_path))

                if raw_path.lower().endswith(".exe"):
                    exe_icons = extract_icons_from_exe_pure_python(raw_path, icons_dir, stem)
                    for idx, p in enumerate(exe_icons):
                        add_candidate(115 - idx, "Из .exe", p)

                exts = (".png", ".svg", ".ico", ".jpg", ".jpeg", ".xpm")
                for root, dirs, files in os.walk(folder):
                    rel = os.path.relpath(root, folder)
                    depth = 0 if rel == "." else rel.count(os.sep) + 1
                    if depth > 3:
                        dirs[:] = []
                        continue
                    for f in files:
                        fl = f.lower()
                        if fl.endswith(exts):
                            full_p = os.path.join(root, f)
                            sc = 50 - depth * 5
                            if stem and stem in fl:
                                sc += 45
                            if any(k in fl for k in ("icon", "logo", "app", "header")):
                                sc += 25
                            if fl.endswith(".ico"):
                                out_conv = os.path.join(icons_dir, f"{stem}_{os.path.splitext(f)[0]}.png")
                                full_p = convert_to_png(full_p, out_conv) or full_p
                            add_candidate(sc, "Папка игры", full_p)

                appid, _, _ = self.analyze_game_folder(raw_path)
                if appid:
                    lib_cache = os.path.join(get_steam_root(), "appcache", "librarycache")
                    if os.path.isdir(lib_cache):
                        for root, _, files in os.walk(lib_cache):
                            for f in files:
                                if f.startswith(str(appid)) or os.path.basename(root) == str(appid):
                                    if f.lower().endswith((".png", ".jpg", ".ico")):
                                        fp = os.path.join(root, f)
                                        if fp.lower().endswith(".jpg"):
                                            out_c = os.path.join(icons_dir, f"steam_{appid}_{os.path.splitext(f)[0]}.png")
                                            fp = convert_to_png(fp, out_c) or fp
                                        add_candidate(95, "Steam Cache", fp)

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
                                add_candidate(90, "Система", os.path.join(sd, f))

        q_stem = os.path.splitext(os.path.basename(raw_input))[0].lower() if raw_input else ""
        if os.path.isdir(icons_dir):
            for f in sorted(os.listdir(icons_dir)):
                fl = f.lower()
                if fl.endswith((".png", ".svg", ".ico", ".jpg", ".jpeg")):
                    fp = os.path.join(icons_dir, f)
                    sc = 110 if (q_stem and q_stem in fl) else 30
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

        win = tk.Toplevel(self)
        win.title("Галерея логотипов")
        win.geometry("620x460")
        win.configure(bg=self.colors["bg"])
        win.transient(self)

        ttk.Label(win, text="Кликните на логотип для выбора:").pack(anchor="w", padx=12, pady=(10, 4))

        container = ttk.Frame(win, padding=10)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=self.colors["entry_bg"], highlightthickness=1, highlightbackground=self.colors["border"])
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        win.thumbs = []

        def pick(p):
            if p.lower().endswith((".ico", ".jpg", ".jpeg")):
                stem = os.path.splitext(os.path.basename(p))[0].lower()
                out_p = os.path.join(self.config_data["icons_dir"], f"{stem}_conv.png")
                p = convert_to_png(p, out_p) or p
            self.icon_var.set(p)
            win.destroy()

        cols = 4
        for idx, (_, label, path) in enumerate(self.found_icons_list[:48]):
            r, c = divmod(idx, cols)
            cell = tk.Frame(scroll_frame, bg=self.colors["btn_bg"], bd=1, relief="flat", padx=6, pady=6)
            cell.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

            img_lbl = tk.Label(cell, bg=self.colors["btn_bg"], width=64, height=64)
            img_lbl.pack()

            try:
                tmp_t = f"/tmp/gal_{os.getpid()}_{idx}.png"
                if HAS_GDK:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 52, 52, True)
                    pb.savev(tmp_t, "png", [], [])
                    ph = tk.PhotoImage(file=tmp_t)
                    win.thumbs.append(ph)
                    img_lbl.config(image=ph)
                elif path.lower().endswith(".png"):
                    raw_p = tk.PhotoImage(file=path)
                    f_sub = max(1, max(raw_p.width(), raw_p.height()) // 52)
                    ph = raw_p.subsample(f_sub, f_sub)
                    win.thumbs.append(ph)
                    img_lbl.config(image=ph)
            except Exception:
                img_lbl.config(text="PNG", fg=self.colors["fg"], width=8, height=3)

            short_lbl = label[:18] + ("…" if len(label) > 18 else "")
            txt_lbl = tk.Label(cell, text=short_lbl, bg=self.colors["btn_bg"], fg=self.colors["fg"], font=("Sans", 8))
            txt_lbl.pack(pady=(4, 0))

            for w in (cell, img_lbl, txt_lbl):
                w.bind("<Button-1>", lambda e, p=path: pick(p))

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
    #yay -S --needed tk python-gobject gdk-pixbuf2 python-pillow icoutils imagemagick desktop-file-utils xdg-utils umu-launcher faugus-launcher