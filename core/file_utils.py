# core/file_utils.py
import os
import sys
from pathlib import Path
from typing import Optional
from PyQt5 import QtCore, QtWidgets
import config

def is_video_file(name: str) -> bool:
    return Path(name).suffix.lower() in config.VIDEO_EXTS

def is_image_file(name: str) -> bool:
    return Path(name).suffix.lower() in config.IMAGE_EXTS

def find_first_video(folder: str) -> Optional[str]:
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.is_file() and is_video_file(e.name):
                    return str(Path(folder) / e.name)
    except Exception:
        return None
    return None

def read_first_dpl_basename(path: str) -> Optional[str]:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                ln = line.strip()
                # look for the first line starting with "playname="
                if ln.lower().startswith('playname='):
                    filename = ln.split('=', 1)[1].strip()
                    # replace backslashes with forward slashes for consistent basename
                    filename = filename.replace('\\', '/')
                    return os.path.basename(filename)
    except Exception:
        return None
    return None

def launch_with_player(player_exe: str, target: str) -> bool:
    try:
        if player_exe:
            QtCore.QProcess.startDetached(player_exe, [target])
        else:
            if sys.platform.startswith('win'):
                os.startfile(target)
            else:
                QtCore.QProcess.startDetached('xdg-open', [target])
        return True
    except Exception as e:
        try:
            QtWidgets.QMessageBox.warning(None, 'Launch failed', f'Failed to open {target}:\n{e}')
        except Exception:
            pass
        return False
