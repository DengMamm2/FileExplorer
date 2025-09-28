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
            # Always use only the central posters folder for folder posters
            if not self.is_file:
                from poster_utils import get_new_poster_path
                import config
                poster_path = get_new_poster_path(str(self.path), str(config.APP_DIR / 'posters'))
                from pathlib import Path
                if Path(poster_path).exists():
                    self.poster = poster_path
                else:
                    self.poster = None  # No poster available

            else:
                # For files, never use any image as a poster
                self.poster = None

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
