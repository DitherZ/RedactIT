#!/usr/bin/env python3
# ============================================================= #
#  RedactIT — setup.py
#  Author  : Blackflame / DitherZ
#  Installs: pip deps, script, .desktop launcher, icon
# ============================================================= #

import os
import sys
import shutil
import subprocess
from pathlib import Path

# ──── ANSI DEFINITIONS ──── #

BOLD="\033[1m"; ITL="\033[3m"; RC="\033[0m"
GRN="\033[0;38;5;40m"; AMB="\033[0;38;5;214m"; LBLUE="\033[0;38;5;159m"
MAG="\033[0;38;5;165m"; RED="\033[0;38;5;196m"; SKY="\033[0;38;5;111m"
SKYFG_GBG="\033[0;1;38;5;111;48;5;240m"; GRNFG_GBG="\033[0;1;38;5;40;48;5;240m"
MAGFG_GBG="\033[0;1;38;5;165;48;5;240m"; AMBFG_GBG="\033[0;1;38;5;214;48;5;240m"
REDFG_GBG="\033[0;1;38;5;196;48;5;240m"

def print_info(m):  print(f"{SKYFG_GBG}  INFO  {LBLUE} {m}{RC}")
def print_task(m):  print(f"\n{MAGFG_GBG}  TASK  {MAG} {m}{RC}")
def print_done(m):  print(f"{GRNFG_GBG}  DONE  {GRN} {m}{RC}")
def print_warn(m):  print(f"{AMBFG_GBG}  WARN  {AMB} {m}{RC}")
def print_fail(m):  print(f"\n{REDFG_GBG}  FAIL  {RED} {m}{RC}")

# ──── PATHS ──── #

HERE        = Path(__file__).parent.resolve()
SCRIPT_SRC  = HERE / "redactit.py"
REQ_FILE    = HERE / "requirements.txt"

# Install targets
BIN_DIR         = Path("/usr/local/bin")
DATA_DIR        = Path("/usr/local/share/redactit")
DESKTOP_DIR     = Path("/usr/share/applications")
ICON_DIR        = Path("/usr/share/icons/hicolor/128x128/apps")

LAUNCHER_NAME   = "redactit"
DESKTOP_FILE    = DESKTOP_DIR / "redactit.desktop"
ICON_FILE       = ICON_DIR    / "redactit.png"
INSTALLED_SCRIPT = DATA_DIR   / "redactit.py"
LAUNCHER_SCRIPT  = BIN_DIR    / LAUNCHER_NAME

DESKTOP_ENTRY = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=RedactIT
GenericName=Image Redaction Tool
Comment=Redact sensitive information from images
Exec={LAUNCHER_SCRIPT}
Icon=redactit
Terminal=false
Categories=Graphics;Security;Utility;
Keywords=redact;censor;blur;privacy;image;
StartupWMClass=redactit
"""

LAUNCHER_SH = f"""#!/bin/bash
exec python3 {INSTALLED_SCRIPT} "$@"
"""

# ──── HELPERS ──── #

def run(cmd: list, check=True) -> int:
    result = subprocess.run(cmd, capture_output=False)
    if check and result.returncode != 0:
        print_fail(f"Command failed: {' '.join(cmd)}")
        sys.exit(result.returncode)
    return result.returncode

def need_sudo() -> bool:
    return os.geteuid() != 0

def sudo_write(path: Path, content: str, mode: int = 0o644):
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".tmp", delete=False) as f:
        f.write(content); tmp = f.name
    run(["sudo", "cp", tmp, str(path)])
    run(["sudo", "chmod", oct(mode)[2:], str(path)])
    os.unlink(tmp)

def sudo_copy(src: Path, dst: Path, mode: int = 0o644):
    run(["sudo", "cp", str(src), str(dst)])
    run(["sudo", "chmod", oct(mode)[2:], str(dst)])

def sudo_mkdir(path: Path):
    run(["sudo", "mkdir", "-p", str(path)])

# ──── STEPS ──── #

def check_python():
    print_task("Checking Python version…")
    if sys.version_info < (3, 10):
        print_fail(f"Python 3.10+ required (got {sys.version})")
        sys.exit(1)
    print_done(f"Python {sys.version.split()[0]}")

def install_system_deps():
    print_task("Installing system dependencies (tesseract-ocr)…")
    if shutil.which("tesseract"):
        print_info("tesseract-ocr already installed — skipping.")
        return
    if shutil.which("apt"):
        run(["sudo", "apt", "install", "-y", "tesseract-ocr"])
        print_done("tesseract-ocr installed via apt.")
    else:
        print_warn("apt not found — install tesseract-ocr manually:")
        print_warn("  sudo apt install tesseract-ocr")

def install_pip_deps():
    print_task("Installing Python dependencies from requirements.txt…")
    if not REQ_FILE.exists():
        print_fail(f"requirements.txt not found at {REQ_FILE}")
        sys.exit(1)
    run([sys.executable, "-m", "pip", "install",
         "--break-system-packages", "-r", str(REQ_FILE)])
    print_done("Python dependencies installed.")

def install_script():
    print_task("Installing RedactIT script…")
    if not SCRIPT_SRC.exists():
        print_fail(f"redactit.py not found at {SCRIPT_SRC}")
        sys.exit(1)
    sudo_mkdir(DATA_DIR)
    sudo_copy(SCRIPT_SRC, INSTALLED_SCRIPT, mode=0o644)
    print_done(f"Script installed → {INSTALLED_SCRIPT}")

def install_launcher():
    print_task("Creating launcher…")
    sudo_mkdir(BIN_DIR)
    sudo_write(LAUNCHER_SCRIPT, LAUNCHER_SH, mode=0o755)
    print_done(f"Launcher installed → {LAUNCHER_SCRIPT}")
    print_info(f"Run with:  {LAUNCHER_NAME}")

def install_desktop_entry():
    print_task("Installing .desktop entry…")
    sudo_mkdir(DESKTOP_DIR)
    sudo_write(DESKTOP_FILE, DESKTOP_ENTRY, mode=0o644)
    # Refresh desktop DB
    if shutil.which("update-desktop-database"):
        run(["sudo", "update-desktop-database", str(DESKTOP_DIR)], check=False)
    print_done(f".desktop entry → {DESKTOP_FILE}")

def install_icon():
    print_task("Installing application icon…")
    icon_src = HERE / "redactit.png"
    if not icon_src.exists():
        # Generate a minimal placeholder SVG→PNG via Python if no icon provided
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGBA", (128, 128), (42, 46, 50, 255))
            d   = ImageDraw.Draw(img)
            # Simple coloured R shape
            d.rectangle([10, 10, 118, 118], outline=(61, 174, 233), width=4)
            d.text((30, 35), "R", fill=(61, 174, 233))
            d.text((55, 35), "IT", fill=(252, 252, 252))
            img.save(str(icon_src))
            print_info("Generated placeholder icon.")
        except Exception as e:
            print_warn(f"Could not generate icon: {e} — skipping.")
            return
    sudo_mkdir(ICON_DIR)
    sudo_copy(icon_src, ICON_FILE, mode=0o644)
    # Update icon cache
    if shutil.which("gtk-update-icon-cache"):
        run(["sudo", "gtk-update-icon-cache", "-f",
             "/usr/share/icons/hicolor"], check=False)
    print_done(f"Icon installed → {ICON_FILE}")

def uninstall():
    print_task("Uninstalling RedactIT…")
    for path in [LAUNCHER_SCRIPT, INSTALLED_SCRIPT, DESKTOP_FILE, ICON_FILE]:
        if path.exists():
            run(["sudo", "rm", "-f", str(path)], check=False)
            print_info(f"Removed {path}")
    if DATA_DIR.exists():
        run(["sudo", "rm", "-rf", str(DATA_DIR)], check=False)
        print_info(f"Removed {DATA_DIR}")
    if shutil.which("update-desktop-database"):
        run(["sudo", "update-desktop-database", str(DESKTOP_DIR)], check=False)
    print_done("RedactIT uninstalled.")

# ──── MAIN ──── #

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="RedactIT installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  install      Full install (default)
  deps-only    Install Python + system deps only
  uninstall    Remove RedactIT from the system
        """
    )
    parser.add_argument(
        "command", nargs="?", default="install",
        choices=["install", "deps-only", "uninstall"],
        help="Action to perform (default: install)"
    )
    args = parser.parse_args()

    print(f"\n{BOLD}{MAG}  RedactIT Installer  {RC}\n")

    if args.command == "uninstall":
        uninstall()
        return

    check_python()
    install_system_deps()
    install_pip_deps()

    if args.command == "deps-only":
        print_done("Dependencies installed. Run redactit.py directly.")
        return

    install_script()
    install_launcher()
    install_desktop_entry()
    install_icon()

    print(f"\n{GRNFG_GBG}  DONE  {GRN} RedactIT installed successfully!{RC}")
    print(f"{LBLUE}  Run:   {SKY}{BOLD}redactit{RC}")
    print(f"{LBLUE}  Or via application launcher: {SKY}RedactIT{RC}\n")

if __name__ == "__main__":
    main()
