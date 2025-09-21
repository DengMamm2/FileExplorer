import os
from pathlib import Path
from core.file_utils import is_video_file, is_image_file, read_first_dpl_basename


class MediaInfo:
    def __init__(self, path: str, is_file=False):
        self.path = Path(path)
        self.is_file = is_file
        self.has_media = False
        self.poster = None
        self.playlist_name = None

        self._detect()

    def _detect(self):
        try:
            if self.is_file and is_image_file(self.path):
                self.poster = str(self.path)
                return

            if not self.is_file:
                for fn in ("poster.png", "poster.jpg", "poster.jpeg"):
                    p = self.path / fn
                    if p.exists():
                        self.poster = str(p)
                        break

            dpl = self.path / "playlist.dpl"
            if dpl.exists():
                self.has_media = True
                bn = read_first_dpl_basename(str(dpl))
                if bn:
                    self.playlist_name = bn
                return

            if not self.is_file:
                with os.scandir(self.path) as it:
                    for e in it:
                        if e.is_file() and is_video_file(e.name):
                            self.has_media = True
                            break
        except Exception:
            pass
