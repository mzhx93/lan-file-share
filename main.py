#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
局域网文件共享工具 (LAN File Share)  v1.0.0

在 Windows 上运行后，选择要分享的目录或文件，程序会在局域网内启动一个
HTTP 服务并生成二维码。同一局域网内的手机扫描二维码，即可在手机浏览器中
预览、在线播放和下载分享的内容。

依赖: qrcode, Pillow  (tkinter 为 Windows Python 自带)
用法:
    python main.py                 # 图形界面，选择要分享的内容
    python main.py D:\\some\\dir     # 命令行直接分享某目录
    python main.py D:\\a.mp4 8080   # 分享单文件并指定端口
"""

import os
import re
import sys
import time
import socket
import shutil
import tempfile
import zipfile
import threading
import webbrowser
import mimetypes
import urllib.parse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.0.0"
DEFAULT_PORT = 8000

# ---------- 可选依赖 ----------
try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None

mimetypes.init()

# ---------- 预览类型 ----------
TEXT_EXTS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".xml", ".yaml", ".yml",
    ".html", ".htm", ".css", ".csv", ".log", ".ini", ".cfg", ".conf",
    ".bat", ".sh", ".ps1", ".sql", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php", ".rb", ".toml", ".gitignore", ".nfo",
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".avif"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"}


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def human_size(n):
    if n < 1024:
        return str(n) + " B"
    value = float(n)
    for unit in ("KB", "MB", "GB", "TB", "PB"):
        value /= 1024.0
        if value < 1024:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} PB"


# ---------- 网络 ----------
def get_all_ips():
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip:
                ips = [ip]
        except Exception:
            ips = ["127.0.0.1"]
    return ips


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def find_free_port(start=DEFAULT_PORT, limit=200):
    for p in range(start, start + limit):
        if port_is_free(p):
            return p
    return start


# ---------- 页面样式 ----------
PAGE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
       background: #f2f3f7; color: #1f2328; padding-bottom: 40px; }
header { background: #3b6ff5; color: #fff; padding: 15px 18px; position: sticky; top: 0;
         z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,.15); }
header .wrap { max-width: 720px; margin: 0 auto; display: flex; align-items: center;
               justify-content: space-between; gap: 10px; }
header h1 { font-size: 17px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
header a.zip { color: #fff; background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.4);
               padding: 6px 12px; border-radius: 16px; font-size: 13px; text-decoration: none; white-space: nowrap; }
.crumbs { max-width: 720px; margin: 12px auto 4px; padding: 0 18px; font-size: 13px; color: #666;
          overflow-x: auto; white-space: nowrap; }
.crumbs a { color: #3b6ff5; text-decoration: none; }
.list { max-width: 720px; margin: 8px auto 0; padding: 0 12px; list-style: none; }
.item { display: flex; align-items: center; background: #fff; border-radius: 12px; margin-bottom: 8px;
        overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.item a.main { flex: 1; display: flex; align-items: center; gap: 12px; padding: 12px 14px;
               text-decoration: none; color: inherit; min-width: 0; }
.icon { width: 38px; height: 38px; flex: 0 0 38px; display: flex; align-items: center;
        justify-content: center; font-size: 22px; border-radius: 9px; background: #eef1f7; }
.icon.dir { background: #fff3d6; }
.icon.img { background: #e3f2fd; }
.icon.vid { background: #fdeaea; }
.icon.mus { background: #e8f5e9; }
.meta { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.name { font-size: 15px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sub { font-size: 12px; color: #999; }
.item a.dl { flex: 0 0 auto; margin-right: 8px; background: #3b6ff5; color: #fff; text-decoration: none;
             font-size: 13px; padding: 7px 14px; border-radius: 16px; }
.item a.zdl { background: #ff9f43; }
footer { text-align: center; color: #aaa; font-size: 12px; margin-top: 14px; }
.preview-wrap { max-width: 860px; margin: 0 auto; padding: 10px; }
.preview-wrap video, .preview-wrap img { width: 100%; max-height: 80vh; background: #000;
                                          border-radius: 8px; display: block; }
.preview-wrap audio { width: 100%; margin-top: 20px; }
.preview-head { max-width: 860px; margin: 0 auto; padding: 12px 16px; display: flex;
                align-items: center; justify-content: space-between; }
.preview-head .nm { font-size: 15px; font-weight: 600; overflow: hidden; text-overflow: ellipsis;
                    white-space: nowrap; }
.preview-head a { color: #3b6ff5; text-decoration: none; font-size: 14px; margin-left: 12px;
                  white-space: nowrap; }
"""


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def render_dir_page(title, crumbs, rows, zip_url, count):
    zip_link = ('<a class="zip" href="' + zip_url + '">⬇ 打包下载</a>') if zip_url else ''
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title><style>{PAGE_CSS}</style></head><body>
<header><div class="wrap"><h1>{esc(title)}</h1>{zip_link}</div></header>
<div class="crumbs">{crumbs}</div>
<ul class="list">{rows}</ul>
<footer>局域网文件共享 · 共 {count} 项</footer>
</body></html>"""


def render_media_page(title, src_url, kind):
    if kind == "video":
        body = '<video controls playsinline preload="metadata" src="' + src_url + '"></video>'
    else:
        body = '<audio controls playsinline preload="metadata" src="' + src_url + '"></audio>'
    dl = src_url + '&dl=1'
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title><style>{PAGE_CSS}</style></head><body>
<div class="preview-head"><div class="nm">{esc(title)}</div><a href="{dl}">下载</a></div>
<div class="preview-wrap">{body}</div>
</body></html>"""


# ---------- HTTP 服务器 ----------
class ShareHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LanFileShare/" + VERSION

    def __init__(self, *args, share_root=None, **kwargs):
        self.share_root = share_root
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):
        # 默认静默，可按需开启访问日志
        pass

    def resolve(self, url_path):
        root = self.share_root
        if os.path.isfile(root):
            return root
        rel = url_path.lstrip("/")
        if not rel:
            return root
        target = os.path.realpath(os.path.join(root, rel))
        root_real = os.path.realpath(root)
        if target == root_real or target.startswith(root_real + os.sep):
            return target
        return None

    def do_GET(self):
        try:
            self._handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError):
            pass
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def do_HEAD(self):
        try:
            parsed = urllib.parse.urlsplit(self.path)
            target = self.resolve(urllib.parse.unquote(parsed.path))
            if target and os.path.isfile(target):
                self.send_response(200)
                self.send_header("Content-Type",
                                 mimetypes.guess_type(target)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(os.path.getsize(target)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
        except Exception:
            pass

    def _handle(self):
        parsed = urllib.parse.urlsplit(self.path)
        enc_path = parsed.path
        url_path = urllib.parse.unquote(enc_path)
        qs = urllib.parse.parse_qs(parsed.query)

        target = self.resolve(url_path)
        if target is None:
            self.send_error(403, "Forbidden")
            return

        if os.path.isdir(target):
            if qs.get("zip"):
                self.serve_zip(target)
            else:
                self.serve_dir(target, enc_path)
        else:
            self.serve_file(target, qs, enc_path)

    def serve_dir(self, target, enc_path):
        try:
            entries = []
            with os.scandir(target) as it:
                for e in it:
                    try:
                        st = e.stat()
                    except OSError:
                        continue
                    entries.append((e.name, e.is_dir(follow_symlinks=False),
                                    st.st_size, st.st_mtime))
            entries.sort(key=lambda x: (not x[1], x[0].lower()))
        except OSError as e:
            self.send_error(500, str(e))
            return

        root_name = os.path.basename(self.share_root.rstrip(os.sep)) or self.share_root
        rel = os.path.relpath(target, self.share_root)
        parts = [] if rel == "." else [p for p in rel.replace("\\", "/").split("/") if p]

        crumbs = ['<a href="/">' + esc(root_name) + '</a>']
        acc = ""
        for p in parts:
            acc += "/" + urllib.parse.quote(p)
            crumbs.append('<span> / </span><a href="' + acc + '">' + esc(p) + '</a>')
        crumbs_html = "".join(crumbs)

        rows = []
        if rel != ".":
            if len(parts) > 1:
                up = "/" + "/".join(urllib.parse.quote(p) for p in parts[:-1])
            else:
                up = "/"
            rows.append('<li class="item"><a class="main" href="' + up +
                        '"><span class="icon dir">📁</span><span class="meta">'
                        '<span class="name">..</span></span></a></li>')

        for name, is_dir, size, mtime in entries:
            qname = urllib.parse.quote(name)
            child = enc_path.rstrip("/") + "/" + qname
            mtime_s = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            if is_dir:
                row = ('<li class="item"><a class="main" href="' + child + '/">'
                       '<span class="icon dir">📁</span><span class="meta">'
                       '<span class="name">' + esc(name) + '</span>'
                       '<span class="sub">' + mtime_s + '</span></span></a>'
                       '<a class="dl zdl" href="' + child + '?zip=1">打包</a></li>')
            else:
                ext = ext_of(name)
                if ext in IMAGE_EXTS:
                    icon, cls = "🖼️", "img"
                elif ext in VIDEO_EXTS:
                    icon, cls = "🎬", "vid"
                elif ext in AUDIO_EXTS:
                    icon, cls = "🎵", "mus"
                else:
                    icon, cls = "📄", "doc"
                sub = human_size(size) + " · " + mtime_s
                row = ('<li class="item"><a class="main" href="' + child + '">'
                       '<span class="icon ' + cls + '">' + icon + '</span><span class="meta">'
                       '<span class="name">' + esc(name) + '</span>'
                       '<span class="sub">' + sub + '</span></span></a>'
                       '<a class="dl" href="' + child + '?dl=1">下载</a></li>')
            rows.append(row)

        p = enc_path.rstrip("/")
        if not p:
            p = "/"
        zip_url = p + "?zip=1"
        title = root_name if rel == "." else (parts[-1] if parts else root_name)
        body = render_dir_page(title, crumbs_html, "".join(rows), zip_url, len(entries)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, target, qs, enc_path):
        ext = ext_of(target)
        if qs.get("dl"):
            self.serve_bytes(target, download=True)
        elif (ext in VIDEO_EXTS or ext in AUDIO_EXTS) and not qs.get("raw"):
            self.serve_media_page(target, enc_path)
        else:
            self.serve_bytes(target, download=False)

    def serve_media_page(self, target, enc_path):
        ext = ext_of(target)
        kind = "video" if ext in VIDEO_EXTS else "audio"
        src_url = enc_path + "?raw=1"
        body = render_media_page(os.path.basename(target), src_url, kind).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_bytes(self, path, download=False):
        size = os.path.getsize(path)
        ext = ext_of(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ext in TEXT_EXTS:
            if ctype.startswith("text/") or ctype == "application/octet-stream":
                ctype = "text/plain; charset=utf-8"
            elif ";" not in ctype:
                ctype += "; charset=utf-8"

        fname = os.path.basename(path)
        qname = urllib.parse.quote(fname)
        disp = "attachment" if download else "inline"

        range_header = self.headers.get("Range")
        start = 0
        end = size - 1

        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)$", range_header.strip())
            if m:
                g1, g2 = m.groups()
                if g1 == "":
                    length = int(g2)
                    start = max(0, size - length)
                    end = size - 1
                else:
                    start = int(g1)
                    end = int(g2) if g2 else size - 1
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */" + str(size))
                    self.end_headers()
                    return
                end = min(end, size - 1)
                self.send_response(206)
                self.send_header("Content-Range",
                                 "bytes " + str(start) + "-" + str(end) + "/" + str(size))
            else:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */" + str(size))
                self.end_headers()
                return
        else:
            self.send_response(200)

        length = end - start + 1
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        disposition = disp + '; filename="' + qname + '"; filename*=UTF-8\'\'' + qname
        self.send_header("Content-Disposition", disposition)
        self.end_headers()

        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def serve_zip(self, dirpath):
        base = os.path.basename(dirpath.rstrip(os.sep)) or "share"
        tmpdir = tempfile.mkdtemp(prefix="lanshare_")
        zippath = os.path.join(tmpdir, base + ".zip")
        try:
            with zipfile.ZipFile(zippath, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(dirpath):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, dirpath)
                        zf.write(full, arc)
            size = os.path.getsize(zippath)
            qname = urllib.parse.quote(base + ".zip")
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(size))
            disposition = 'attachment; filename="' + qname + '"; filename*=UTF-8\'\'' + qname
            self.send_header("Content-Disposition", disposition)
            self.end_headers()
            with open(zippath, "rb") as fp:
                shutil.copyfileobj(fp, self.wfile)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class ShareServer:
    def __init__(self, root, port=DEFAULT_PORT):
        self.root = os.path.abspath(root)
        self.port = port
        self.httpd = None

    def start(self):
        handler = partial(ShareHandler, share_root=self.root)
        self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), handler)
        self.httpd.daemon_threads = True
        t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        t.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


# ---------- 二维码 ----------
def make_qr_pil(url, box_size=10, border=2):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


# ---------- 图形界面 ----------
class ShareApp:
    def __init__(self, root):
        self.root = root
        self.server = None
        self.share_path = None
        self.urls = []
        self.qr_photo = None
        self.build_ui()
        self.root.after(250, self.ask_initial)

    def build_ui(self):
        self.root.title("局域网文件共享 LAN File Share")
        self.root.geometry("560x840")
        self.root.minsize(480, 640)
        pad = 12

        tk.Label(self.root, text="局域网文件共享", font=("Microsoft YaHei UI", 16, "bold")
                 ).pack(pady=(pad, 2))

        self.path_label = tk.Label(self.root, text="尚未选择要分享的内容", font=("Microsoft YaHei UI", 10),
                                   fg="#555", wraplength=500, justify="center")
        self.path_label.pack(fill="x", padx=pad, pady=(0, 2))

        port_frame = tk.Frame(self.root)
        port_frame.pack(pady=(2, 0))
        tk.Label(port_frame, text="端口:", font=("Microsoft YaHei UI", 10), fg="#555").pack(side="left")
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.port_entry = tk.Spinbox(port_frame, from_=1, to=65535, textvariable=self.port_var,
                                     width=8, font=("Consolas", 11), justify="center")
        self.port_entry.pack(side="left", padx=6)

        self.qr_label = tk.Label(self.root, text="二维码将在此显示", bg="#fff", fg="#888", pady=8)
        self.qr_label.pack(padx=pad, pady=4)

        self.url_text = tk.Text(self.root, height=4, font=("Consolas", 10), wrap="word",
                                relief="flat", bg="#f5f5f5", padx=6, pady=4)
        self.url_text.pack(fill="x", padx=pad, pady=(2, 0))
        self.url_text.insert("1.0", "访问地址将在此显示")
        self.url_text.configure(state="disabled")

        self.list_title = tk.Label(self.root, text="分享内容列表", font=("Microsoft YaHei UI", 10, "bold"),
                                   fg="#333", anchor="w")
        self.list_title.pack(fill="x", padx=pad, pady=(8, 2))

        list_frame = tk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=pad, pady=(0, 4))

        columns = ("type", "name", "size")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("type", text="类型")
        self.tree.heading("name", text="名称")
        self.tree.heading("size", text="大小")
        self.tree.column("type", width=64, anchor="center", stretch=False)
        self.tree.column("name", width=280, anchor="w")
        self.tree.column("size", width=110, anchor="e", stretch=False)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.status_label = tk.Label(self.root, text="未启动", fg="#888")
        self.status_label.pack(pady=2)

        btns = tk.Frame(self.root)
        btns.pack(pady=6)
        tk.Button(btns, text="选择文件夹", command=self.choose_folder, width=13).grid(row=0, column=0, padx=4, pady=3)
        tk.Button(btns, text="选择文件", command=self.choose_file, width=13).grid(row=0, column=1, padx=4, pady=3)
        tk.Button(btns, text="浏览器打开", command=self.open_browser, width=13).grid(row=1, column=0, padx=4, pady=3)
        tk.Button(btns, text="复制地址", command=self.copy_url, width=13).grid(row=1, column=1, padx=4, pady=3)
        tk.Button(btns, text="停止并退出", command=self.stop_and_exit, width=28).grid(row=2, column=0, columnspan=2, padx=4, pady=3)

    def read_port(self):
        """从端口输入框读取端口；非法或占用时自动调整，并把实际端口回写面板。"""
        try:
            p = int(str(self.port_var.get()).strip())
        except ValueError:
            p = DEFAULT_PORT
        if p < 1 or p > 65535:
            p = DEFAULT_PORT
        if not port_is_free(p):
            p = find_free_port(p)
        self.port_var.set(str(p))
        return p

    def refresh_list(self):
        """列出被选中分享的内容本身（单个文件夹或文件），不展开子内容。"""
        self.tree.delete(*self.tree.get_children())
        if not self.share_path:
            self.list_title.configure(text="分享内容列表")
            return
        name = os.path.basename(os.path.normpath(self.share_path)) or self.share_path
        if os.path.isdir(self.share_path):
            self.tree.insert("", "end", values=("目录", name, ""))
        else:
            try:
                size = os.path.getsize(self.share_path)
            except OSError:
                size = 0
            self.tree.insert("", "end", values=("文件", name, human_size(size)))
        self.list_title.configure(text="分享内容列表 · 共 " + str(len(self.tree.get_children())) + " 项")
    def ask_initial(self):
        answer = messagebox.askyesnocancel(
            "选择要分享的内容",
            "请选择要分享的内容：\n\n点击“是” → 选择文件夹\n点击“否” → 选择单个文件\n点击“取消” → 稍后手动选择"
        )
        if answer is True:
            self.choose_folder()
        elif answer is False:
            self.choose_file()

    def choose_folder(self):
        p = filedialog.askdirectory(title="选择要分享的文件夹")
        if p:
            self.start_share(p)

    def choose_file(self):
        p = filedialog.askopenfilename(title="选择要分享的文件")
        if p:
            self.start_share(p)

    def start_share(self, path):
        if self.server:
            self.server.stop()
            self.server = None
        self.share_path = path
        self.path_label.configure(text="分享内容: " + path)
        self.refresh_list()

        port = self.read_port()
        self.server = ShareServer(path, port)
        self.server.start()

        self.urls = ["http://" + ip + ":" + str(port) + "/" for ip in get_all_ips()]
        primary = self.urls[0] if self.urls else "http://127.0.0.1:" + str(port) + "/"

        if qrcode and Image and ImageTk:
            img = make_qr_pil(primary)
            self.qr_photo = ImageTk.PhotoImage(img)
            self.qr_label.configure(image=self.qr_photo, text="")
        else:
            self.qr_label.configure(image="", text="未安装 qrcode/Pillow，无法生成二维码\n请运行 run.bat 安装依赖", fg="#c00")

        text = "\n".join(self.urls) + "\n\n请确保手机与本机连接同一局域网/路由器"
        self.url_text.configure(state="normal")
        self.url_text.delete("1.0", "end")
        self.url_text.insert("1.0", text)
        self.url_text.configure(state="disabled")

        self.status_label.configure(text="服务运行中 · 端口 " + str(port), fg="#2a7")

    def open_browser(self):
        if self.urls:
            webbrowser.open(self.urls[0])

    def copy_url(self):
        if self.urls:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.urls[0])
            self.root.update()
            self.status_label.configure(text="已复制地址", fg="#2a7")

    def stop_and_exit(self):
        if self.server:
            self.server.stop()
            self.server = None
        self.root.destroy()


# ---------- 命令行 ----------
def run_cli(path, port):
    server = ShareServer(path, port)
    server.start()
    ips = get_all_ips()
    urls = ["http://" + ip + ":" + str(port) + "/" for ip in ips]
    print("=" * 46)
    print("局域网文件共享已启动")
    print("分享内容:", path)
    print("访问地址 (手机需与本机在同一局域网):")
    for u in urls:
        print("   ", u)
    print("=" * 46)
    if qrcode:
        qr = qrcode.QRCode()
        qr.add_data(urls[0])
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    print("按 Ctrl+C 停止服务")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        server.stop()


def run_gui():
    root = tk.Tk()
    app = ShareApp(root)
    root.protocol("WM_DELETE_WINDOW", app.stop_and_exit)
    root.mainloop()


def _main():
    args = sys.argv[1:]
    path = None
    port = DEFAULT_PORT
    if args:
        path = args[0]
        if not os.path.exists(path):
            print("[错误] 路径不存在: " + path, file=sys.stderr)
            sys.exit(1)
    if len(args) > 1:
        try:
            port = int(args[1])
        except ValueError:
            port = DEFAULT_PORT

    if path:
        if not port_is_free(port):
            port = find_free_port(port)
        run_cli(path, port)
    elif tk:
        run_gui()
    else:
        print("未指定路径，且当前环境无图形界面(tkinter)。")
        print("用法: python main.py <目录或文件> [端口]")
        sys.exit(1)


def main():
    try:
        _main()
    except Exception as e:
        if tk:
            try:
                r = tk.Tk()
                r.withdraw()
                messagebox.showerror("局域网文件共享 - 错误", str(e))
                r.destroy()
            except Exception:
                pass
        print("Error:", e, file=sys.stderr)


if __name__ == "__main__":
    main()
