import os
import hashlib
import shutil

def get_folder_hash(folder_path):
    # Normalize the path to ensure consistent hashing regardless of slash direction
    normalized_path = str(folder_path).replace('\\', '/')
    # Create a SHA1 hash of the normalized folder path
    return hashlib.sha1(normalized_path.encode('utf-8')).hexdigest()

def get_new_poster_path(folder_path, posters_root="posters"):
    h = get_folder_hash(folder_path)
    subfolder_2 = h[:2]
    subfolder_3 = h[:5]
    poster_dir = os.path.join(posters_root, subfolder_2, subfolder_3)
    os.makedirs(poster_dir, exist_ok=True)
    return os.path.join(poster_dir, f"{h}.jpg")

def move_poster(folder_path, posters_root="posters"):
    src = os.path.join(folder_path, "poster.jpg")
    if os.path.exists(src):
        dest = get_new_poster_path(folder_path, posters_root)
        
        # Make sure the destination directory exists (redundant but safe)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        
        # Copy first, then delete original to prevent data loss
        shutil.copy2(src, dest)
        os.remove(src)
        
        return dest
    return None