#!/usr/bin/env python3
# ============================================================= #
#  RedactIT — Image Redaction GUI Tool
#  Author  : Blackflame / DitherZ
#  Version : 2.1.0
#  Requires: PyQt6, Pillow, pytesseract, numpy, opencv-python
# ============================================================= #
#
#  CHANGELOG
#  ---------
#  v2.1.0 — KlassyDark palette + zone border control + per-zone ✕
#           - NEW: border_width field on RedactionZone (0 = none)
#             Exposed in Zone Editor; default 0 (no visible border)
#           - NEW: Per-zone ✕ delete button rendered as a
#             QGraphicsProxyWidget anchored top-right of each zone
#             rect — click to instantly remove that zone
#           - THEME: Full KlassyDark colour scheme applied:
#               Window BG  (42,46,50)   View BG    (27,30,32)
#               Button BG  (49,54,59)   Accent     (61,174,233)
#               FG normal  (252,252,252) FG muted  (161,169,177)
#               Negative   (218,68,83)  Positive   (39,174,96)
#               Neutral    (246,116,0)  Selection  (61,174,233)
#               Visited    (155,89,182)
#
#  v2.0.0 — Full UX overhaul + C++ deleted-object crash fix
#  v1.0.1 — Fixed PyQt6 QAction overload error
#  v1.0.0 — Initial release
#
# ============================================================= #

import sys, os, copy, math, traceback, datetime
from dataclasses import dataclass
from typing import Optional

# ──── ANSI DEFINITIONS ──── #

BOLD="\033[1m"; ITL="\033[3m"; DIM="\033[2m"; RVRS="\033[7m"; BLINK="\033[5m"
RESET="\033[0m"; RC="\033[0m"; RCFG="\033[39m"; RCBG="\033[49m"; RCFX="\033[22m"
GRN="\033[0;38;5;40m"; AMB="\033[0;38;5;214m"; LBLUE="\033[0;38;5;159m"
MAG="\033[0;38;5;165m"; RED="\033[0;38;5;196m"; SKY="\033[0;38;5;111m"
WHT="\033[0;38;5;231m"; LGRAY="\033[0;38;5;250m"; DGRAY="\033[0;38;5;240m"
WFG_BBG="\033[0;1;38;5;233;48;5;255m"; SKYFG_GBG="\033[0;1;38;5;111;48;5;240m"
GRNFG_GBG="\033[0;1;38;5;40;48;5;240m"; MAGFG_GBG="\033[0;1;38;5;165;48;5;240m"
AMBFG_GBG="\033[0;1;38;5;214;48;5;240m"; REDFG_GBG="\033[0;1;38;5;196;48;5;240m"

# ──── PRINT LOGIC/ABSTRACTION ──── #

def print_info(m):     print(f"{SKYFG_GBG}  INFO  {LBLUE} {m}{RC}")
def print_task(m):     print(f"\n{MAGFG_GBG}  TASK  {MAG} {m}{RC}")
def print_done(m):     print(f"{GRNFG_GBG}  DONE  {GRN} {m}{RC}")
def print_warn(m):     print(f"{AMBFG_GBG}  WARN  {AMB} {m}{RC}")
def print_fail(m):     print(f"\n{REDFG_GBG}  FAIL  {RED} {m}{RC}")
def print_filepath(p): print(f"{LBLUE}{ITL}{p}{RC}", end="")

# ──── DEPENDENCY CHECK ──── #

def check_deps():
    missing = []
    for pkg, imp in [("PyQt6","PyQt6"),("Pillow","PIL"),
                     ("numpy","numpy"),("opencv-python","cv2"),
                     ("pytesseract","pytesseract")]:
        try: __import__(imp)
        except ImportError: missing.append(pkg)
    if missing:
        print_fail(f"Missing: {', '.join(missing)}")
        print_info(f"pip install {' '.join(missing)}")
        sys.exit(1)
    print_done("All dependencies satisfied.")

check_deps()

# ──── IMPORTS ──── #

import numpy as np, cv2
from PIL import Image, ImageFilter, ImageDraw
import pytesseract

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QFileDialog, QGroupBox, QSlider,
    QComboBox, QSpinBox, QSizePolicy, QColorDialog, QSplitter,
    QStatusBar, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem,
    QListWidget, QListWidgetItem, QToolBar, QScrollArea,
)
from PyQt6.QtCore  import (
    Qt, QRect, QRectF, QPoint, QPointF, QSize,
    pyqtSignal, QThread, pyqtSlot, QTimer,
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QBrush, QColor,
    QFont, QFontDatabase, QAction, QKeySequence,
)

# ──── KLASSY DARK PALETTE ──── #
# Source: KlassyDark colour scheme INI

# Window
C_WIN_BG        = "#2a2e32"   # (42,46,50)   Window:BackgroundNormal
C_WIN_BG_ALT    = "#31363b"   # (49,54,59)   Window:BackgroundAlternate / Button:BackgroundNormal
C_VIEW_BG       = "#1b1e20"   # (27,30,32)   View:BackgroundNormal
C_VIEW_BG_ALT   = "#23262a"   # (35,38,41)   View:BackgroundAlternate

# Foreground
C_FG            = "#fcfcfc"   # (252,252,252) ForegroundNormal
C_FG_INACTIVE   = "#a1a9b1"   # (161,169,177) ForegroundInactive
C_FG_ACTIVE     = "#3daee9"   # (61,174,233)  ForegroundActive

# Accent / Decoration
C_ACCENT        = "#3daee9"   # (61,174,233)  DecorationFocus / Selection BG
C_HOVER         = "#3daee9"   # (61,174,233)  DecorationHover

# Semantic
C_POSITIVE      = "#27ae60"   # (39,174,96)   ForegroundPositive
C_NEGATIVE      = "#da4453"   # (218,68,83)   ForegroundNegative
C_NEUTRAL       = "#f67400"   # (246,116,0)   ForegroundNeutral
C_LINK          = "#1d99f3"   # (29,153,243)  ForegroundLink
C_VISITED       = "#9b59b6"   # (155,89,182)  ForegroundVisited

# Borders (derived — slightly lighter than BG)
C_BORDER        = "#3a3f44"
C_BORDER_LT     = "#4a5259"

# Method colours (mapped to palette semantics)
REDACT_METHODS  = ["Blackout","Whiteout","Blur","Pixelate","Distort","Clone Stamp"]
METHOD_COLORS   = {
    "Blackout":    C_FG_INACTIVE,
    "Whiteout":    "#dddddd",
    "Blur":        C_ACCENT,
    "Pixelate":    C_NEUTRAL,
    "Distort":     C_VISITED,
    "Clone Stamp": C_POSITIVE,
}

APP_NAME    = "RedactIT"
APP_VERSION = "2.1.0"
LOG_DIR     = os.path.expanduser("~/.log")
LOG_FILE    = os.path.join(LOG_DIR, "redactit.log")

# ──── FONT HELPERS ──── #

_FM: Optional[QFont] = None
_FR: Optional[QFont] = None

def _load_fonts():
    global _FM, _FR
    families = QFontDatabase.families()
    chosen = next((f for f in ["Lato","Noto Sans","DejaVu Sans",
                                "Liberation Sans"] if f in families), None)
    if chosen:
        _FM = QFont(chosen, 10, QFont.Weight.Medium)
        _FR = QFont(chosen, 10, QFont.Weight.Normal)
        tag = "" if chosen == "Lato" else f" (fallback for Lato)"
        print_done(f"Font: {chosen}{tag}")
    else:
        _FM = _FR = QFont()
        print_warn("No preferred font — using system default.")

def fm(sz=10) -> QFont:
    f = QFont(_FM); f.setPointSize(sz); f.setWeight(QFont.Weight.Medium); return f

def fr(sz=10) -> QFont:
    f = QFont(_FR); f.setPointSize(sz); f.setWeight(QFont.Weight.Normal); return f

# ──── DATA MODEL ──── #

@dataclass
class RedactionZone:
    rect:          QRect
    method:        str   = "Blackout"
    intensity:     int   = 15
    pad_x:         int   = 2
    pad_y:         int   = 2
    opacity:       float = 1.0
    fill_color:    str   = "#000000"
    border_radius: int   = 0
    border_width:  int   = 0          # 0 = no border on canvas overlay
    feather:       int   = 0          # edge softness radius in px (0 = hard)
    clone_src:     Optional[QPoint] = None
    label:         str   = ""

    def padded_rect(self) -> QRect:
        return self.rect.adjusted(-self.pad_x, -self.pad_y,
                                   self.pad_x,  self.pad_y)

# ──── PIL ↔ QPixmap ──── #

def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    """Convert PIL image to QPixmap, preserving alpha channel."""
    img  = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qi   = QImage(data, img.width, img.height,
                  img.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qi)

# ──── OCR WORKER ──── #

class OcrWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, img: Image.Image):
        super().__init__(); self._img = img

    def run(self):
        try:
            # Tesseract requires RGB/L — convert without touching the original
            ocr_img = self._img.convert("RGB")
            d   = pytesseract.image_to_data(
                ocr_img, output_type=pytesseract.Output.DICT)
            out = []
            for i in range(len(d["text"])):
                txt = d["text"][i].strip()
                if not txt or int(d["conf"][i]) < 30: continue
                out.append((txt, QRect(d["left"][i], d["top"][i],
                                       d["width"][i], d["height"][i])))
            self.finished.emit(out)
        except Exception as e:
            self.error.emit(str(e))

# ──── REDACTION ENGINE ──── #

class RedactionEngine:

    @staticmethod
    def apply(src: Image.Image, zones: list) -> Image.Image:
        out = src.copy().convert("RGBA")
        W, H = out.size
        for z in zones:
            r  = z.padded_rect()
            x1, y1 = max(0, r.left()),  max(0, r.top())
            x2, y2 = min(W, r.right()), min(H, r.bottom())
            if x2 <= x1 or y2 <= y1: continue
            region = out.crop((x1, y1, x2, y2))
            proc   = RedactionEngine._process(region, z, src, x1, y1)
            if z.border_radius > 0:
                proc = RedactionEngine._round(region, proc, z.border_radius)
            if z.feather > 0:
                proc = RedactionEngine._feather(region, proc, z.feather)
            if z.opacity < 1.0:
                proc = Image.blend(region.convert("RGBA"),
                                   proc.convert("RGBA"), z.opacity)
            out.paste(proc.convert("RGBA"), (x1, y1))
        return out  # stays RGBA — caller decides final mode

    @staticmethod
    def _process(region, z, full, ox, oy) -> Image.Image:
        w, h = region.size; m = z.method
        if m == "Blackout":  return Image.new("RGBA", (w,h), z.fill_color)
        if m == "Whiteout":  return Image.new("RGBA", (w,h), "#ffffff")
        if m == "Blur":
            return region.convert("RGBA").filter(
                ImageFilter.GaussianBlur(max(1, z.intensity*2)))
        if m == "Pixelate":
            bl = max(2, z.intensity)
            sm = region.resize((max(1,w//bl), max(1,h//bl)), Image.NEAREST)
            return sm.resize((w,h), Image.NEAREST).convert("RGBA")
        if m == "Distort":
            arr  = np.array(region.convert("RGBA"), dtype=np.uint8)
            ah, aw = arr.shape[:2]; s = max(1, z.intensity)
            xs = np.tile(np.arange(aw, dtype=np.float32), (ah,1))
            ys = np.tile(np.arange(ah, dtype=np.float32).reshape(-1,1), (1,aw))
            mx = xs + s*np.sin(2*math.pi*ys/max(1,s*3))
            my = ys + s*np.cos(2*math.pi*xs/max(1,s*3))
            res = cv2.remap(arr, mx.astype(np.float32), my.astype(np.float32),
                            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            return Image.fromarray(res, "RGBA")
        if m == "Clone Stamp":
            sx = z.clone_src.x() if z.clone_src else max(0, ox-w-10)
            sy = z.clone_src.y() if z.clone_src else oy
            src = full.convert("RGBA").crop((sx,sy,sx+w,sy+h))
            return src.filter(ImageFilter.GaussianBlur(1))
        return region.convert("RGBA")

    @staticmethod
    def _round(orig, proc, radius) -> Image.Image:
        w, h = orig.size
        mask = Image.new("L", (w,h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0,0,w-1,h-1], radius=radius, fill=255)
        base = orig.convert("RGBA")
        base.paste(proc.convert("RGBA"), (0,0), mask)
        return base

    @staticmethod
    def _feather(orig, proc, radius) -> Image.Image:
        """Soft edge blend — gaussian feather mask around the border."""
        w, h = orig.size
        r    = max(1, radius)
        # White filled rectangle, then blur it to create a soft alpha mask
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rectangle([r, r, w-r-1, h-r-1], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(r))
        base = orig.convert("RGBA")
        base.paste(proc.convert("RGBA"), (0, 0), mask)
        return base

# ──── CANVAS VIEW ──── #

class CanvasView(QGraphicsView):
    """
    _base (QGraphicsPixmapItem, Z=0) — the image; setPixmap() for preview
    _ocr_items  (Z=1) — amber dotted OCR highlights
    _zone_items (Z=2) — redaction zone outlines
    _del_items  (Z=3) — per-zone ✕ proxy buttons

    Preview = _base.setPixmap() in-place. No second item created, ever.
    """

    zone_drawn   = pyqtSignal(QRect)
    zone_clicked = pyqtSignal(int)
    ocr_clicked  = pyqtSignal(str, QRect)
    clone_picked = pyqtSignal(QPoint)
    zoom_changed = pyqtSignal(int)   # percent 10–500

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sc = QGraphicsScene(self)
        self.setScene(self._sc)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setStyleSheet(
            f"background:{C_VIEW_BG}; border:none;")

        self._base:       Optional[QGraphicsPixmapItem] = None
        self._ocr_items:  list = []
        self._zone_items: list = []
        self._rb_item:    Optional[QGraphicsRectItem] = None   # scene rubber-band
        self._rb_origin:  Optional[QPointF]     = None           # scene origin
        self._mode:       str = "draw"
        self._sel_idx:    int = -1

    # ── Public API ── #

    def load_pixmap(self, px: QPixmap):
        self._base = None
        self._ocr_items = []; self._zone_items = []
        self._rb_item = None; self._rb_origin = None
        self._sc.clear()
        self._base = QGraphicsPixmapItem(px)
        self._base.setZValue(0)
        self._sc.addItem(self._base)
        self._sc.setSceneRect(QRectF(px.rect()))
        self.fitInView(self._base, Qt.AspectRatioMode.KeepAspectRatio)

    def update_preview(self, px: QPixmap):
        if self._base is not None:
            self._base.setPixmap(px)

    def set_ocr(self, results: list):
        for it in self._ocr_items: self._sc.removeItem(it)
        self._ocr_items = []
        for text, rect in results:
            it = QGraphicsRectItem(QRectF(rect))
            it.setPen(QPen(Qt.PenStyle.NoPen))
            it.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            it.setZValue(1)
            it.setData(0, text); it.setData(1, rect)
            self._sc.addItem(it); self._ocr_items.append(it)
        self._refresh_ocr_visibility()

    def _refresh_ocr_visibility(self):
        """Show OCR highlights only in select mode."""
        show = (self._mode == "select")
        for it in self._ocr_items:
            if show:
                it.setPen(QPen(QColor(C_NEUTRAL), 1, Qt.PenStyle.DotLine))
                bg = QColor(C_NEUTRAL); bg.setAlphaF(0.12)
                it.setBrush(QBrush(bg))
            else:
                it.setPen(QPen(Qt.PenStyle.NoPen))
                it.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    def set_zones(self, zones: list, sel: int = -1):
        self._sel_idx = sel
        for it in self._zone_items: self._sc.removeItem(it)
        self._zone_items = []

        for i, z in enumerate(zones):
            r       = z.padded_rect()
            rf      = QRectF(r)
            it      = QGraphicsRectItem(rf)
            is_sel  = (i == sel) and (self._mode == "select")

            if is_sel:
                col = QColor(METHOD_COLORS.get(z.method, C_ACCENT))
                bw  = z.border_width if z.border_width > 0 else 1
                it.setPen(QPen(col, bw, Qt.PenStyle.SolidLine))
                bg  = QColor(col); bg.setAlphaF(0.22)
                it.setBrush(QBrush(bg))
            else:
                # Completely invisible — no pen, no fill
                it.setPen(QPen(Qt.PenStyle.NoPen))
                it.setBrush(QBrush(Qt.BrushStyle.NoBrush))

            it.setZValue(2); it.setData(0, i)
            self._sc.addItem(it); self._zone_items.append(it)

    def set_mode(self, mode: str):
        self._mode = mode
        cur = {"draw": Qt.CursorShape.CrossCursor,
               "select": Qt.CursorShape.ArrowCursor,
               "clone_src": Qt.CursorShape.PointingHandCursor}
        self.setCursor(cur.get(mode, Qt.CursorShape.ArrowCursor))
        # Overlays and OCR chips only visible in select mode
        self._refresh_ocr_visibility()
        # Re-draw zone overlays respecting new mode
        self._reapply_zone_visibility()

    def _reapply_zone_visibility(self):
        """Hide all zone overlays unless in select mode with one selected."""
        for it in self._zone_items:
            idx    = it.data(0)
            is_sel = (idx == self._sel_idx) and (self._mode == "select")
            if is_sel:
                # Re-colour — we don't have zone data here so just use accent
                it.setPen(QPen(QColor(C_ACCENT), 1, Qt.PenStyle.SolidLine))
                bg = QColor(C_ACCENT); bg.setAlphaF(0.18)
                it.setBrush(QBrush(bg))
            else:
                it.setPen(QPen(Qt.PenStyle.NoPen))
                it.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    # ── Mouse ── #

    def _s(self, vp): return self.mapToScene(vp)

    def mousePressEvent(self, ev):
        if self._base is None: return super().mousePressEvent(ev)
        sp = self._s(ev.pos()); lb = ev.button() == Qt.MouseButton.LeftButton

        if self._mode == "clone_src" and lb:
            self.clone_picked.emit(QPoint(int(sp.x()), int(sp.y()))); return

        if self._mode == "draw" and lb:
            self._rb_origin = self._s(ev.pos())
            # Remove any leftover rubber band rect
            if self._rb_item:
                self._sc.removeItem(self._rb_item)
            self._rb_item = QGraphicsRectItem(
                QRectF(self._rb_origin, QSizeF()))
            pen = QPen(QColor(C_ACCENT), 1, Qt.PenStyle.DashLine)
            self._rb_item.setPen(pen)
            bg = QColor(C_ACCENT); bg.setAlphaF(0.08)
            self._rb_item.setBrush(QBrush(bg))
            self._rb_item.setZValue(10)
            self._sc.addItem(self._rb_item)
            return

        if self._mode == "select" and lb:
            for it in reversed(self._zone_items):
                if it.boundingRect().contains(sp):
                    self.zone_clicked.emit(it.data(0)); return
            for it in self._ocr_items:
                if it.boundingRect().contains(sp):
                    self.ocr_clicked.emit(it.data(0), it.data(1)); return
            # Clicked empty area — deselect everything
            self._sel_idx = -1
            self._reapply_zone_visibility()
            self.zone_clicked.emit(-1)

        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._mode == "draw" and self._rb_item and self._rb_origin:
            cur = self._s(ev.pos())
            self._rb_item.setRect(
                QRectF(self._rb_origin, cur).normalized())
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._mode == "draw" and self._rb_item and self._rb_origin:
            cur  = self._s(ev.pos())
            rf   = QRectF(self._rb_origin, cur).normalized()
            self._sc.removeItem(self._rb_item)
            self._rb_item   = None
            self._rb_origin = None
            if rf.width() > 4 and rf.height() > 4:
                self.zone_drawn.emit(QRect(
                    int(rf.x()), int(rf.y()),
                    int(rf.width()), int(rf.height())))
        super().mouseReleaseEvent(ev)

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1/1.15
        self.scale(f, f)
        self.zoom_changed.emit(self._zoom_pct())

    def _zoom_pct(self) -> int:
        return max(10, min(500, int(self.transform().m11() * 100)))

    def zoom_to(self, pct: int):
        """Set absolute zoom level (10–500%)."""
        if self._base is None: return
        target = max(0.10, min(5.0, pct / 100.0))
        current = self.transform().m11()
        if abs(current - target) < 0.001: return
        self.scale(target / current, target / current)

    def fit_view(self):
        if self._base is not None:
            self.fitInView(self._base, Qt.AspectRatioMode.KeepAspectRatio)
            self.zoom_changed.emit(self._zoom_pct())

# ──── ZONE EDITOR ──── #

class ZoneEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zone: Optional[RedactionZone] = None
        self._busy = False
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0); root.setSpacing(6)

        hdr = QLabel("Zone Editor"); hdr.setFont(fm(11))
        hdr.setStyleSheet(f"color:{C_ACCENT}; padding-bottom:2px;")
        root.addWidget(hdr)

        self._grp = QGroupBox(); self._grp.setEnabled(False)
        gl = QVBoxLayout(self._grp); gl.setSpacing(8)

        def lbl(t):
            l = QLabel(t); l.setFont(fr(9)); l.setFixedWidth(94); return l

        def row(t, w):
            r = QHBoxLayout(); r.addWidget(lbl(t)); r.addWidget(w); return r

        # Method
        self._method = QComboBox(); self._method.setFont(fm(10))
        self._method.addItems(REDACT_METHODS)
        self._method.currentTextChanged.connect(self._on_method)
        gl.addLayout(row("Method", self._method))

        # Intensity
        self._intensity = QSpinBox(); self._intensity.setFont(fr(10))
        self._intensity.setRange(1, 60); self._intensity.setValue(15)
        self._intensity.valueChanged.connect(self._emit)
        gl.addLayout(row("Intensity", self._intensity))

        # Padding X/Y
        pr = QHBoxLayout()
        pr.addWidget(lbl("Padding  X"))
        self._padx = QSpinBox(); self._padx.setRange(0,200)
        self._padx.setFont(fr(10)); self._padx.valueChanged.connect(self._emit)
        pr.addWidget(self._padx)
        yl = QLabel("Y"); yl.setFont(fr(9)); yl.setFixedWidth(14); pr.addWidget(yl)
        self._pady = QSpinBox(); self._pady.setRange(0,200)
        self._pady.setFont(fr(10)); self._pady.valueChanged.connect(self._emit)
        pr.addWidget(self._pady)
        gl.addLayout(pr)

        # Opacity
        opr = QHBoxLayout()
        opr.addWidget(lbl("Opacity"))
        self._opacity = QSlider(Qt.Orientation.Horizontal)
        self._opacity.setRange(0,100); self._opacity.setValue(100)
        self._opacity.valueChanged.connect(self._emit)
        opr.addWidget(self._opacity)
        self._op_lbl = QLabel("100%"); self._op_lbl.setFont(fr(9))
        self._op_lbl.setFixedWidth(34); opr.addWidget(self._op_lbl)
        gl.addLayout(opr)

        # Corner radius
        self._radius = QSpinBox(); self._radius.setRange(0,80)
        self._radius.setFont(fr(10)); self._radius.valueChanged.connect(self._emit)
        gl.addLayout(row("Corner Radius", self._radius))

        # Border width (0 = none)
        self._border_w = QSpinBox(); self._border_w.setRange(0,12)
        self._border_w.setFont(fr(10)); self._border_w.setValue(0)
        self._border_w.setToolTip("0 = no border on canvas overlay")
        self._border_w.valueChanged.connect(self._emit)
        gl.addLayout(row("Border Width", self._border_w))

        # Feather / Tolerance
        self._feather = QSpinBox(); self._feather.setRange(0, 60)
        self._feather.setFont(fr(10)); self._feather.setValue(0)
        self._feather.setToolTip("Feather: soften/fade the redaction edges (0 = hard)")
        self._feather.valueChanged.connect(self._emit)
        gl.addLayout(row("Tolerance", self._feather))

        # Fill color (Blackout/Whiteout)
        self._col_row = QHBoxLayout()
        self._col_row.addWidget(lbl("Fill Color"))
        self._col_btn = QPushButton(); self._col_btn.setFixedSize(38,22)
        self._col_btn.clicked.connect(self._pick_color)
        self._col_row.addWidget(self._col_btn); self._col_row.addStretch()
        gl.addLayout(self._col_row)

        self._tag = QLabel(""); self._tag.setFont(fr(9))
        self._tag.setStyleSheet(
            f"color:{C_FG_INACTIVE}; padding:4px 0; font-style:italic;")
        self._tag.setWordWrap(True)
        gl.addWidget(self._tag)

        root.addWidget(self._grp); root.addStretch()

    def load(self, z: RedactionZone):
        self._zone = z; self._busy = True
        self._grp.setEnabled(True)
        self._method.setCurrentText(z.method)
        self._intensity.setValue(z.intensity)
        self._padx.setValue(z.pad_x); self._pady.setValue(z.pad_y)
        self._opacity.setValue(int(z.opacity*100))
        self._op_lbl.setText(f"{int(z.opacity*100)}%")
        self._radius.setValue(z.border_radius)
        self._border_w.setValue(z.border_width)
        self._feather.setValue(z.feather)
        self._col_btn.setStyleSheet(
            f"background:{z.fill_color}; border:1px solid {C_BORDER_LT};")
        self._update_col_vis(z.method)
        self._tag.setText(f'"{z.label}"' if z.label else "")
        self._busy = False

    def clear(self):
        self._zone = None; self._grp.setEnabled(False); self._tag.setText("")

    def _on_method(self, m): self._update_col_vis(m); self._emit()

    def _update_col_vis(self, m):
        show = m in ("Blackout","Whiteout")
        for i in range(self._col_row.count()):
            it = self._col_row.itemAt(i)
            if it and it.widget(): it.widget().setVisible(show)

    def _emit(self):
        if self._busy or not self._zone: return
        self._zone.method        = self._method.currentText()
        self._zone.intensity     = self._intensity.value()
        self._zone.pad_x         = self._padx.value()
        self._zone.pad_y         = self._pady.value()
        self._zone.opacity       = self._opacity.value() / 100.0
        self._zone.border_radius = self._radius.value()
        self._zone.border_width  = self._border_w.value()
        self._zone.feather       = self._feather.value()
        self._op_lbl.setText(f"{self._opacity.value()}%")
        self.changed.emit()

    def _pick_color(self):
        if not self._zone: return
        c = QColorDialog.getColor(QColor(self._zone.fill_color), self)
        if c.isValid():
            self._zone.fill_color = c.name()
            self._col_btn.setStyleSheet(
                f"background:{c.name()}; border:1px solid {C_BORDER_LT};")
            self.changed.emit()

# ──── ZONE LIST ──── #

class ZoneList(QWidget):
    """
    Simple zone list. Each row is a QListWidgetItem with a custom
    widget that has WA_TransparentForMouseEvents on the label/dot
    portion, and a real ✕ QPushButton that is NOT transparent.
    Selection is driven by QListWidget.currentRowChanged which is
    always reliable because clicks on the transparent label area
    fall through to the underlying QListWidget item.
    The ✕ button calls deleted() directly and calls
    event.ignore() so the click does NOT propagate to the list row
    (avoids accidental selection changes on delete).
    """
    selected = pyqtSignal(int)
    deleted  = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0); root.setSpacing(4)

        hdr = QHBoxLayout()
        t = QLabel("Zones"); t.setFont(fm(11))
        t.setStyleSheet(f"color:{C_ACCENT};"); hdr.addWidget(t)
        hdr.addStretch()
        root.addLayout(hdr)

        self._lw = QListWidget()
        self._lw.setFont(fr(10))
        self._lw.setSpacing(1)
        self._lw.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self._lw)

    def _on_row_changed(self, row: int):
        if row >= 0:
            self.selected.emit(row)

    def refresh(self, zones: list):
        # Block signals during rebuild to avoid spurious selects
        self._lw.blockSignals(True)
        cur = self._lw.currentRow()
        self._lw.clear()

        for i, z in enumerate(zones):
            label = z.label or f"Zone {i+1}"
            col   = METHOD_COLORS.get(z.method, C_ACCENT)

            item = QListWidgetItem(self._lw)
            item.setSizeHint(QSize(0, 32))
            item.setData(Qt.ItemDataRole.UserRole, i)

            # Outer container — passes mouse events through to list item
            outer = QWidget()
            outer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            outer.setStyleSheet("background:transparent;")
            outer_l = QHBoxLayout(outer)
            outer_l.setContentsMargins(6, 0, 4, 0)
            outer_l.setSpacing(4)

            # Dot + label — transparent so list row captures clicks
            info = QWidget()
            info.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            info.setStyleSheet("background:transparent;")
            info_l = QHBoxLayout(info)
            info_l.setContentsMargins(0,0,0,0); info_l.setSpacing(4)

            dot = QLabel("●"); dot.setFont(fr(9))
            dot.setStyleSheet(f"color:{col}; background:transparent;")
            dot.setFixedWidth(14)
            info_l.addWidget(dot)

            lbl = QLabel(f"{z.method}  —  {label}")
            lbl.setFont(fr(10))
            lbl.setStyleSheet(f"color:{C_FG}; background:transparent;")
            info_l.addWidget(lbl)

            outer_l.addWidget(info, stretch=1)

            # ✕ button — real mouse events, does NOT propagate to list
            xbtn = QPushButton("✕")
            xbtn.setFixedSize(18, 18)
            xbtn.setFont(fr(8))
            xbtn.setCursor(Qt.CursorShape.PointingHandCursor)
            xbtn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            xbtn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C_FG_INACTIVE};
                    border: none;
                    border-radius: 9px;
                    padding: 0;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {C_NEGATIVE};
                    color: {C_FG};
                }}
            """)
            _i = i
            xbtn.clicked.connect(lambda _, idx=_i: self.deleted.emit(idx))
            outer_l.addWidget(xbtn)

            self._lw.setItemWidget(item, outer)

        self._lw.blockSignals(False)

        # Restore selection
        if 0 <= cur < self._lw.count():
            self._lw.setCurrentRow(cur)
        elif self._lw.count() > 0:
            self._lw.setCurrentRow(self._lw.count() - 1)

    def select(self, idx: int):
        if 0 <= idx < self._lw.count():
            self._lw.blockSignals(True)
            self._lw.setCurrentRow(idx)
            self._lw.blockSignals(False)

    def clear_selection(self):
        self._lw.blockSignals(True)
        self._lw.clearSelection()
        self._lw.setCurrentRow(-1)
        self._lw.blockSignals(False)


class OcrChipStrip(QScrollArea):
    zone_requested = pyqtSignal(str, QRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(52)
        self.setStyleSheet(
            f"background:{C_WIN_BG_ALT}; border:none; "
            f"border-top:1px solid {C_BORDER};")
        self._inner = QWidget()
        self._lay   = QHBoxLayout(self._inner)
        self._lay.setContentsMargins(8,6,8,6); self._lay.setSpacing(6)
        self.setWidget(self._inner); self.setWidgetResizable(True)
        self._chips: list = []
        self._ph = QLabel(
            "Run OCR Scan → detected words appear here · "
            "click any chip to add a redaction zone")
        self._ph.setFont(fr(9))
        self._ph.setStyleSheet(f"color:{C_FG_INACTIVE};")
        self._lay.addWidget(self._ph); self._lay.addStretch()

    def set_results(self, results: list):
        for c in self._chips:
            self._lay.removeWidget(c); c.deleteLater()
        self._chips = []
        item = self._lay.itemAt(self._lay.count()-1)
        if item and item.spacerItem(): self._lay.removeItem(item)
        self._lay.removeWidget(self._ph)
        if not results:
            self._lay.addWidget(self._ph); self._lay.addStretch(); return
        for text, rect in results:
            b = QPushButton(text); b.setFont(fr(9)); b.setFixedHeight(26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{C_VIEW_BG}; color:{C_FG};
                    border:1px solid {C_BORDER_LT};
                    border-radius:4px; padding:0 8px;
                }}
                QPushButton:hover {{
                    background:{C_NEUTRAL}; color:#000;
                    border-color:{C_NEUTRAL};
                }}
            """)
            t, r = text, rect
            b.clicked.connect(lambda _, _t=t, _r=r:
                              self.zone_requested.emit(_t, _r))
            self._lay.addWidget(b); self._chips.append(b)
        self._lay.addStretch()

# ──── MAIN WINDOW ──── #

class RedactITWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1440, 880); self.setMinimumSize(960, 600)

        self._pil:       Optional[Image.Image] = None
        self._path:      str  = ""
        self._zones:     list = []
        self._undo:      list = []
        self._redo:      list = []
        self._sel:       int  = -1
        self._clone_src: Optional[QPoint] = None
        self._ocr_worker: Optional[OcrWorker] = None

        self._apply_style()
        self._build_ui()
        self._build_menus()
        self._wire()

        self._ptimer = QTimer()
        self._ptimer.setSingleShot(True); self._ptimer.setInterval(400)
        self._ptimer.timeout.connect(self._do_preview)

        os.makedirs(LOG_DIR, exist_ok=True)
        print_info(f"{APP_NAME} v{APP_VERSION} started.")

    # ──────────────────────── STYLE ──────────────────────── #

    def _apply_style(self):
        self.setStyleSheet(f"""
        * {{ font-family:'Lato','Noto Sans','DejaVu Sans',sans-serif; }}
        QMainWindow, QWidget   {{ background:{C_WIN_BG}; color:{C_FG}; }}

        QGroupBox {{
            border:1px solid {C_BORDER}; border-radius:6px;
            margin-top:10px; padding:10px 8px 8px 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin:margin; left:10px;
            color:{C_FG_INACTIVE}; font-size:9px;
        }}

        QPushButton {{
            background:{C_WIN_BG_ALT}; color:{C_FG};
            border:1px solid {C_BORDER}; border-radius:5px; padding:5px 14px;
        }}
        QPushButton:hover   {{ background:#3a3f44; border-color:{C_ACCENT}; }}
        QPushButton:pressed {{ background:{C_VIEW_BG}; }}
        QPushButton:checked {{ background:{C_ACCENT}; color:{C_WIN_BG}; border-color:{C_ACCENT}; font-weight:600; }}
        QPushButton#accent  {{ background:{C_ACCENT}; color:{C_WIN_BG}; border:none; font-weight:600; }}
        QPushButton#accent:hover {{ background:#5cc0f5; }}
        QPushButton#danger  {{ background:#2a0a10; color:{C_NEGATIVE}; border:1px solid #4a1020; }}
        QPushButton#danger:hover {{ background:#3a0c14; }}

        QComboBox {{
            background:{C_WIN_BG_ALT}; border:1px solid {C_BORDER};
            border-radius:4px; padding:3px 8px; color:{C_FG};
        }}
        QComboBox::drop-down {{ border:none; width:20px; }}
        QComboBox QAbstractItemView {{
            background:{C_WIN_BG}; selection-background-color:{C_ACCENT};
            selection-color:{C_WIN_BG};
        }}
        QSpinBox {{
            background:{C_WIN_BG_ALT}; border:1px solid {C_BORDER};
            border-radius:4px; padding:2px 6px; color:{C_FG};
        }}
        QSlider::groove:horizontal {{
            background:{C_BORDER}; height:4px; border-radius:2px;
        }}
        QSlider::handle:horizontal {{
            background:{C_ACCENT}; width:14px; height:14px;
            margin:-5px 0; border-radius:7px;
        }}
        QSlider::sub-page:horizontal {{
            background:{C_ACCENT}; opacity:0.5; border-radius:2px;
        }}
        QListWidget {{
            background:{C_VIEW_BG}; border:1px solid {C_BORDER}; border-radius:5px;
        }}
        QListWidget::item          {{ padding:5px 8px; }}
        QListWidget::item:selected {{
            background:{C_WIN_BG_ALT}; color:{C_ACCENT};
            border-left:2px solid {C_ACCENT};
        }}
        QListWidget::item:hover    {{ background:{C_WIN_BG_ALT}; }}

        QLabel {{ color:{C_FG_INACTIVE}; }}

        QMenuBar {{ background:{C_WIN_BG}; border-bottom:1px solid {C_BORDER}; }}
        QMenuBar::item {{ padding:4px 10px; color:{C_FG}; }}
        QMenuBar::item:selected {{ background:{C_WIN_BG_ALT}; }}
        QMenu {{
            background:{C_WIN_BG}; border:1px solid {C_BORDER};
            color:{C_FG};
        }}
        QMenu::item {{ padding:5px 24px 5px 14px; }}
        QMenu::item:selected {{ background:{C_ACCENT}; color:{C_WIN_BG}; }}

        QToolBar {{
            background:{C_WIN_BG}; border-bottom:1px solid {C_BORDER};
            spacing:2px; padding:3px 6px;
        }}
        QToolBar QToolButton {{
            background:transparent; color:{C_FG};
            border:1px solid transparent; border-radius:5px;
            padding:4px 10px; font-size:11px;
        }}
        QToolBar QToolButton:hover   {{
            background:{C_WIN_BG_ALT}; border-color:{C_BORDER_LT};
        }}
        QToolBar QToolButton:checked {{
            background:{C_ACCENT}; color:{C_WIN_BG};
            border-color:{C_ACCENT}; font-weight:600;
        }}

        QStatusBar {{
            background:{C_WIN_BG}; border-top:1px solid {C_BORDER};
            color:{C_FG_INACTIVE}; font-size:10px; padding:0 8px;
        }}
        QSplitter::handle {{ background:{C_BORDER}; }}
        QScrollBar:vertical {{
            background:transparent; width:8px; border:none;
        }}
        QScrollBar:horizontal {{
            background:transparent; height:8px; border:none;
        }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            background:{C_BORDER_LT}; border-radius:4px; min-height:20px;
        }}
        QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
            background:{C_ACCENT};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{ background:none; border:none; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
        QAbstractScrollArea {{ border:none; }}
        QGraphicsView QScrollBar:vertical, QGraphicsView QScrollBar:horizontal {{
            background:transparent;
        }}
        """)

    # ──────────────────────── UI BUILD ──────────────────────── #

    def _build_ui(self):
        # ── Toolbar ── #
        tb = QToolBar(); tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        self._a_open   = QAction("📂  Open",        self)
        self._a_ocr    = QAction("🔍  Scan OCR",    self)
        self._a_sel    = QAction("↖  Select",       self)
        self._a_draw   = QAction("✏  Draw Zone",    self)
        self._a_clone  = QAction("⊕  Clone Source", self)
        self._a_undo   = QAction("⟲  Undo",         self)
        self._a_redo   = QAction("⟳  Redo",         self)
        self._a_clear  = QAction("🗑  Clear",        self)
        self._a_export = QAction("💾  Export",       self)

        for a in (self._a_sel, self._a_draw, self._a_clone):
            a.setCheckable(True)
        self._a_draw.setChecked(True)

        tb.addAction(self._a_open); tb.addAction(self._a_ocr)
        tb.addSeparator()
        tb.addAction(self._a_sel); tb.addAction(self._a_draw)
        tb.addAction(self._a_clone)
        tb.addSeparator()

        self._method_cb = QComboBox()
        self._method_cb.addItems(REDACT_METHODS)
        self._method_cb.setFont(fm(10)); self._method_cb.setFixedWidth(132)
        self._method_cb.setToolTip("Default method for new zones")
        tb.addWidget(self._method_cb)
        tb.addSeparator()

        tb.addAction(self._a_undo); tb.addAction(self._a_redo)
        tb.addSeparator(); tb.addAction(self._a_clear)
        sp = QWidget()
        sp.setSizePolicy(QSizePolicy.Policy.Expanding,
                         QSizePolicy.Policy.Preferred)
        tb.addWidget(sp); tb.addAction(self._a_export)

        # ── Central ── #
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        spl = QSplitter(Qt.Orientation.Horizontal); spl.setHandleWidth(3)

        # ── Left panel ── #
        left = QWidget(); left.setObjectName("lp")
        left.setStyleSheet(
            f"#lp{{background:{C_WIN_BG};border-right:1px solid {C_BORDER};}}")
        left.setFixedWidth(252)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12,14,12,12); ll.setSpacing(10)

        logo = QLabel(); logo.setTextFormat(Qt.TextFormat.RichText)
        logo.setText(
            f"<span style='font-size:22px;font-weight:700;"
            f"color:{C_ACCENT};'>Redact</span>"
            f"<span style='font-size:22px;font-weight:300;"
            f"color:{C_FG};'>IT</span>"
            f"  <span style='font-size:9px;color:{C_FG_INACTIVE};'>"
            f"v{APP_VERSION}</span>")
        ll.addWidget(logo)

        self._img_lbl = QLabel("No image loaded"); self._img_lbl.setFont(fr(9))
        self._img_lbl.setStyleSheet(
            f"color:{C_FG_INACTIVE};padding:4px 6px;"
            f"background:{C_VIEW_BG};border:1px solid {C_BORDER};border-radius:4px;")
        self._img_lbl.setWordWrap(True); ll.addWidget(self._img_lbl)

        self._clone_lbl = QLabel("Clone source:  not set")
        self._clone_lbl.setFont(fr(9))
        self._clone_lbl.setStyleSheet(f"color:{C_FG_INACTIVE};")
        ll.addWidget(self._clone_lbl)

        self._zlist = ZoneList(); ll.addWidget(self._zlist, stretch=1)

        ur = QHBoxLayout()
        self._undo_btn = QPushButton("⟲ Undo"); self._undo_btn.setFont(fm(9))
        self._redo_btn = QPushButton("⟳ Redo"); self._redo_btn.setFont(fm(9))
        ur.addWidget(self._undo_btn); ur.addWidget(self._redo_btn)
        ll.addLayout(ur)

        self._clear_btn = QPushButton("🗑  Clear All Zones")
        self._clear_btn.setFont(fm(10)); self._clear_btn.setObjectName("danger")
        ll.addWidget(self._clear_btn)

        self._export_btn = QPushButton("💾  Export Redacted Image")
        self._export_btn.setFont(fm(11)); self._export_btn.setObjectName("accent")
        self._export_btn.setFixedHeight(40); ll.addWidget(self._export_btn)

        spl.addWidget(left)

        # ── Canvas ── #
        cw = QWidget()
        cl = QVBoxLayout(cw); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)

        self._hint = QLabel(
            "  Open an image to get started  ·  "
            "Draw Zone or run OCR Scan to add redaction zones")
        self._hint.setFont(fr(9))
        self._hint.setStyleSheet(
            f"background:{C_WIN_BG};color:{C_FG_INACTIVE};"
            f"padding:4px 12px;border-bottom:1px solid {C_BORDER};")
        cl.addWidget(self._hint)

        self._canvas = CanvasView(); self._canvas.set_mode("draw")
        cl.addWidget(self._canvas, stretch=1)

        self._chip_strip = OcrChipStrip(); cl.addWidget(self._chip_strip)

        # ── Zoom bar ── #
        zoom_bar = QWidget()
        zoom_bar.setStyleSheet(
            f"background:{C_WIN_BG}; border-top:1px solid {C_BORDER};")
        zoom_bar.setFixedHeight(32)
        zbl = QHBoxLayout(zoom_bar)
        zbl.setContentsMargins(8, 4, 8, 4); zbl.setSpacing(6)
        zbl.addStretch()
        zoom_lbl = QLabel("Zoom:")
        zoom_lbl.setFont(fr(9))
        zoom_lbl.setStyleSheet(f"color:{C_FG_INACTIVE}; background:transparent;")
        zbl.addWidget(zoom_lbl)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(10, 500)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(140)
        self._zoom_slider.setToolTip("Canvas zoom level")
        zbl.addWidget(self._zoom_slider)
        self._zoom_pct_lbl = QLabel("100%")
        self._zoom_pct_lbl.setFont(fr(9))
        self._zoom_pct_lbl.setFixedWidth(38)
        self._zoom_pct_lbl.setStyleSheet(f"color:{C_FG}; background:transparent;")
        zbl.addWidget(self._zoom_pct_lbl)
        self._zoom_fit_btn = QPushButton("Fit")
        self._zoom_fit_btn.setFont(fm(9))
        self._zoom_fit_btn.setFixedSize(36, 22)
        zbl.addWidget(self._zoom_fit_btn)
        cl.addWidget(zoom_bar)

        spl.addWidget(cw)

        # ── Right panel ── #
        right = QWidget(); right.setObjectName("rp")
        right.setStyleSheet(
            f"#rp{{background:{C_WIN_BG};border-left:1px solid {C_BORDER};}}")
        right.setFixedWidth(228)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12,14,12,12); rl.setSpacing(10)

        self._editor = ZoneEditor(); rl.addWidget(self._editor)

        self._preview_btn = QPushButton("🖼  Refresh Preview")
        self._preview_btn.setFont(fm(9)); rl.addWidget(self._preview_btn)
        rl.addStretch()

        spl.addWidget(right)
        spl.setSizes([252, 968, 228])
        root.addWidget(spl, stretch=1)

        self._sb = QStatusBar(); self._sb.setFont(fr(9))
        self.setStatusBar(self._sb)
        self._sb.showMessage("Ready — open an image to begin.")

    # ──────────────────────── MENUS ──────────────────────── #

    def _build_menus(self):
        mb = self.menuBar()
        fm_ = mb.addMenu("File")
        for txt, slot, key in [
            ("Open Image…",  self._open_image,   QKeySequence.StandardKey.Open),
            ("Export…",      self._export_image, QKeySequence.StandardKey.Save),
        ]:
            a = QAction(txt, self); a.setShortcut(key)
            a.triggered.connect(slot); fm_.addAction(a)
        fm_.addSeparator()
        qa = QAction("Quit", self)
        qa.setShortcut(QKeySequence.StandardKey.Quit)
        qa.triggered.connect(self.close); fm_.addAction(qa)

        em = mb.addMenu("Edit")
        for txt, slot, key in [
            ("Undo", self._do_undo, QKeySequence.StandardKey.Undo),
            ("Redo", self._do_redo, QKeySequence.StandardKey.Redo),
        ]:
            a = QAction(txt, self); a.setShortcut(key)
            a.triggered.connect(slot); em.addAction(a)
        em.addSeparator()
        ca = QAction("Clear All Zones", self)
        ca.triggered.connect(self._clear_zones); em.addAction(ca)

    # ──────────────────────── SIGNALS ──────────────────────── #

    def _wire(self):
        self._a_open.triggered.connect(self._open_image)
        self._a_ocr.triggered.connect(self._run_ocr)
        self._a_sel.triggered.connect(lambda:   self._set_mode("select"))
        self._a_draw.triggered.connect(lambda:  self._set_mode("draw"))
        self._a_clone.triggered.connect(lambda: self._set_mode("clone_src"))
        self._a_undo.triggered.connect(self._do_undo)
        self._a_redo.triggered.connect(self._do_redo)
        self._a_clear.triggered.connect(self._clear_zones)
        self._a_export.triggered.connect(self._export_image)

        self._undo_btn.clicked.connect(self._do_undo)
        self._redo_btn.clicked.connect(self._do_redo)
        self._clear_btn.clicked.connect(self._clear_zones)
        self._export_btn.clicked.connect(self._export_image)
        self._preview_btn.clicked.connect(self._do_preview)

        self._canvas.zone_drawn.connect(self._zone_drawn)
        self._canvas.zone_clicked.connect(self._select_zone)
        self._canvas.ocr_clicked.connect(self._ocr_zone)
        self._canvas.clone_picked.connect(self._clone_src_set)

        self._chip_strip.zone_requested.connect(self._ocr_zone)

        self._zlist.selected.connect(self._select_zone)
        self._zlist.deleted.connect(self._delete_zone)

        self._editor.changed.connect(self._editor_changed)

        # Zoom bar
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider)
        self._zoom_fit_btn.clicked.connect(self._on_zoom_fit)
        self._canvas.zoom_changed.connect(self._on_canvas_zoom_changed)

    # ──────────────────────── ZOOM ──────────────────────── #

    def _on_zoom_slider(self, value: int):
        self._zoom_pct_lbl.setText(f"{value}%")
        self._canvas.zoom_to(value)

    def _on_zoom_fit(self):
        self._canvas.fit_view()
        pct = self._canvas._zoom_pct()
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(pct)
        self._zoom_slider.blockSignals(False)
        self._zoom_pct_lbl.setText(f"{pct}%")

    def _on_canvas_zoom_changed(self, pct: int):
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(pct)
        self._zoom_slider.blockSignals(False)
        self._zoom_pct_lbl.setText(f"{pct}%")

    # ──────────────────────── MODE ──────────────────────── #

    def _set_mode(self, mode: str):
        self._a_sel.setChecked(mode == "select")
        self._a_draw.setChecked(mode == "draw")
        self._a_clone.setChecked(mode == "clone_src")
        self._canvas.set_mode(mode)
        hints = {
            "select":    "Select mode — click a zone on the canvas or an OCR chip",
            "draw":      "Draw mode — drag on the image to place a redaction zone",
            "clone_src": "Clone Source — click a point on the image to copy from",
        }
        self._hint.setText(f"  {hints.get(mode,'')}")

    # ──────────────────────── OPEN ──────────────────────── #

    def _open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", os.path.expanduser("~"),
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)")
        if not path: return
        try:
            self._pil   = Image.open(path)  # preserve native mode (RGBA, P, L, RGB…)
            self._path  = path
            self._zones = []; self._undo = []; self._redo = []; self._sel = -1
            name = os.path.basename(path); w, h = self._pil.size
            self._img_lbl.setText(f"{name}\n{w} × {h} px")
            self._canvas.load_pixmap(pil_to_qpixmap(self._pil))
            self._canvas.set_zones([])
            self._set_mode("draw")
            self._zlist.refresh([]); self._editor.clear()
            self._chip_strip.set_results([])
            self._sb.showMessage(
                f"Loaded: {name}  ({w}×{h})  ·  "
                f"Draw zones or run OCR Scan")
            self._hint.setText(
                "  Draw mode — drag on the image to create a zone  ·  "
                "Run OCR Scan to detect text automatically")
            print_done(f"Opened: {path}")
        except Exception as e:
            print_fail(f"Open: {e}")
            QMessageBox.critical(self, "Error", str(e))

    # ──────────────────────── OCR ──────────────────────── #

    def _run_ocr(self):
        if not self._pil:
            QMessageBox.information(self, "No Image", "Open an image first.")
            return
        self._a_ocr.setEnabled(False)
        self._sb.showMessage("OCR scanning…"); print_task("OCR scan…")
        self._ocr_worker = OcrWorker(self._pil)
        self._ocr_worker.finished.connect(self._ocr_done)
        self._ocr_worker.error.connect(self._ocr_err)
        self._ocr_worker.start()

    @pyqtSlot(list)
    def _ocr_done(self, results):
        self._canvas.set_ocr(results)
        self._chip_strip.set_results(results)
        self._a_ocr.setEnabled(True)
        self._sb.showMessage(
            f"OCR complete — {len(results)} words found  ·  "
            f"Click chips below, or switch to Select and click highlights")
        print_done(f"OCR: {len(results)} detections.")

    @pyqtSlot(str)
    def _ocr_err(self, msg):
        self._a_ocr.setEnabled(True)
        self._sb.showMessage(f"OCR error: {msg}"); print_fail(f"OCR: {msg}")
        QMessageBox.warning(self, "OCR Error",
            f"{msg}\n\nsudo apt install tesseract-ocr")

    # ──────────────────────── ZONES ──────────────────────── #

    def _push_undo(self):
        self._undo.append(copy.deepcopy(self._zones))
        if len(self._undo) > 60: self._undo.pop(0)
        self._redo.clear()

    def _new_zone(self, rect: QRect, label: str = "") -> RedactionZone:
        z = RedactionZone(
            rect=rect, method=self._method_cb.currentText(), label=label)
        if z.method == "Clone Stamp" and self._clone_src:
            z.clone_src = self._clone_src
        return z

    def _add_zone(self, z: RedactionZone):
        self._zones.append(z)
        self._sel = len(self._zones) - 1
        self._sync()
        self._zlist.refresh(self._zones); self._zlist.select(self._sel)
        self._editor.load(z)
        self._schedule_preview()

    @pyqtSlot(QRect)
    def _zone_drawn(self, rect: QRect):
        self._push_undo(); z = self._new_zone(rect); self._add_zone(z)
        self._sb.showMessage(
            f"Zone {self._sel+1} created  [{z.method}]  ·  "
            f"Edit in Zone Editor →  ·  Click ✕ on canvas to remove")
        print_info(f"Zone drawn: {z.method} @ {z.rect}")

    @pyqtSlot(str, QRect)
    def _ocr_zone(self, text: str, rect: QRect):
        self._push_undo(); z = self._new_zone(rect, label=text)
        self._add_zone(z)
        self._sb.showMessage(
            f'Redaction added for "{text}"  [{z.method}]')
        print_info(f'OCR zone: "{text}" → {z.method}')

    @pyqtSlot(int)
    def _select_zone(self, idx: int):
        if not (0 <= idx < len(self._zones)):
            # Index out of range — fall back to last zone if any
            if self._zones:
                idx = len(self._zones) - 1
            else:
                self._sel = -1; self._sync()
                return
        self._sel = idx; self._sync()
        self._zlist.select(idx)
        self._editor.load(self._zones[idx])
        self._sb.showMessage(
            f"Zone {idx+1} selected  [{self._zones[idx].method}]")

    @pyqtSlot(int)
    def _delete_zone(self, idx: int):
        if not (0 <= idx < len(self._zones)): return
        self._push_undo(); self._zones.pop(idx)
        if self._zones:
            self._sel = min(idx, len(self._zones) - 1)
        else:
            self._sel = -1
        self._sync()
        self._zlist.refresh(self._zones)
        if self._zones:
            self._zlist.select(self._sel)
            self._editor.load(self._zones[self._sel])
        else:
            self._editor.clear()
        self._schedule_preview(); print_info(f"Zone {idx+1} deleted.")

    def _clear_zones(self):
        if not self._zones: return
        self._push_undo(); self._zones.clear(); self._sel = -1; self._sync()
        self._zlist.refresh([]); self._editor.clear()
        self._schedule_preview(); print_info("All zones cleared.")

    def _editor_changed(self):
        if self._sel < 0: return
        self._sync(); self._zlist.refresh(self._zones)
        self._schedule_preview()

    def _sync(self):
        self._canvas.set_zones(self._zones, sel=self._sel)

    # ──────────────────────── CLONE SRC ──────────────────────── #

    @pyqtSlot(QPoint)
    def _clone_src_set(self, pt: QPoint):
        self._clone_src = pt
        self._clone_lbl.setText(f"Clone source:  ({pt.x()}, {pt.y()})")
        self._sb.showMessage(
            f"Clone source set at ({pt.x()}, {pt.y()})  ·  "
            f"Now draw a zone over the area to replace")
        self._set_mode("draw"); print_info(f"Clone src: ({pt.x()}, {pt.y()})")

    # ──────────────────────── UNDO / REDO ──────────────────────── #

    def _do_undo(self):
        if not self._undo: return
        self._redo.append(copy.deepcopy(self._zones))
        self._zones = self._undo.pop()
        self._sel = len(self._zones) - 1 if self._zones else -1
        self._sync(); self._zlist.refresh(self._zones)
        if self._zones:
            self._zlist.select(self._sel)
            self._editor.load(self._zones[self._sel])
        else:
            self._editor.clear()
        self._schedule_preview()

    def _do_redo(self):
        if not self._redo: return
        self._undo.append(copy.deepcopy(self._zones))
        self._zones = self._redo.pop(); self._sel = -1; self._sync()
        self._zlist.refresh(self._zones); self._editor.clear()
        self._schedule_preview()

    # ──────────────────────── PREVIEW ──────────────────────── #

    def _schedule_preview(self): self._ptimer.start()

    def _do_preview(self):
        if not self._pil: return
        try:
            rendered = (RedactionEngine.apply(self._pil, self._zones)
                        if self._zones else self._pil)
            self._canvas.update_preview(pil_to_qpixmap(rendered))
            self._sync()
        except Exception as e:
            print_fail(f"Preview: {e}"); traceback.print_exc()

    # ──────────────────────── EXPORT ──────────────────────── #

    def _export_image(self):
        if not self._pil:
            QMessageBox.information(self, "No Image", "Open an image first.")
            return
        default = os.path.splitext(self._path)[0] + "_redacted.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Redacted Image", default,
            "PNG (*.png);;JPEG (*.jpg);;All Files (*)")
        if not path: return
        try:
            print_task(f"Exporting → {path}")
            result = RedactionEngine.apply(self._pil, self._zones)
            ext = os.path.splitext(path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                # JPEG cannot carry alpha — flatten against white
                bg = Image.new("RGB", result.size, (255, 255, 255))
                bg.paste(result, mask=result.split()[3])
                result = bg
            result.save(path)
            self._log(path)
            self._sb.showMessage(f"✔  Exported → {path}")
            print_done(f"Exported: {path}")
            QMessageBox.information(self, "Export Complete",
                f"Saved to:\n{path}")
        except Exception as e:
            print_fail(f"Export: {e}")
            QMessageBox.critical(self, "Export Failed", str(e))

    def _log(self, path: str):
        try:
            with open(LOG_FILE, "a") as f:
                f.write(
                    f"[{datetime.datetime.now().isoformat()}] "
                    f"EXPORT src={self._path!r} dst={path!r} "
                    f"zones={len(self._zones)}\n")
        except Exception: pass

# ──── ENTRY POINT ──── #

def main():
    print_task(f"Launching {APP_NAME} v{APP_VERSION}")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    _load_fonts()
    win = RedactITWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
