#!/usr/bin/env python3
"""
ARK Backups - Incremental backup with change detection and screenshot capture.

Backs up path_original to path_backup with timestamped subfolders.
- Skips backup if no changes detected
- For partial changes: copies changed files from original, unchanged from previous backup
- Can capture screenshots of ShooterGame.exe window (even when minimized)
"""

import os
import re
import shutil
import time
import msvcrt
import subprocess
import ctypes
from datetime import datetime
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

try:
    import pywinctl
    PYWINCTL_AVAILABLE = True
except ImportError:
    pywinctl = None
    PYWINCTL_AVAILABLE = False

try:
    import win32gui
    import win32con
    import win32ui
    WIN32_AVAILABLE = True
except ImportError:
    win32gui = None
    win32con = None
    win32ui = None
    WIN32_AVAILABLE = False


def load_config(config_path: str) -> dict:
    """Load configuration from env.txt file."""
    config = {}
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip("'\"")
    return config


def get_folder_hash(folder_path: Path) -> dict:
    """Get file hashes (mtime + size) for all files in a folder."""
    file_info = {}
    if not folder_path.exists():
        return file_info
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(folder_path)
            stat = file_path.stat()
            file_info[str(rel_path)] = {
                'size': stat.st_size,
                'mtime': stat.st_mtime
            }
    return file_info


def get_latest_backup(path_backup: Path) -> Path | None:
    """Get the most recent backup folder."""
    if not path_backup.exists():
        return None
    
    # Try reading from latest.txt first
    latest_file = path_backup / 'latest.txt'
    if latest_file.exists():
        with open(latest_file, 'r') as f:
            latest_path = Path(f.read().strip())
            if latest_path.exists():
                return latest_path
    
    # Fallback: find most recent backup folder
    backup_folders = get_backup_folders(path_backup)
    
    if not backup_folders:
        return None
    
    return max(backup_folders, key=lambda x: x.name)


def get_backup_folders(path_backup: Path) -> list[Path]:
    """Get list of backup folders matching timestamp pattern."""
    if not path_backup.exists():
        return []
    
    # Pattern: YYYY-MM-DD_HH-MM-SS
    timestamp_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$')
    
    backup_folders = [
        d for d in path_backup.iterdir()
        if d.is_dir() and timestamp_pattern.match(d.name)
    ]
    
    return backup_folders


def cleanup_old_backups(path_backup: Path, backup_count: int):
    """Remove oldest backups if count exceeds backup_count."""
    backup_folders = get_backup_folders(path_backup)
    
    if len(backup_folders) <= backup_count:
        return
    
    # Sort by name (timestamp) ascending - oldest first
    backup_folders.sort(key=lambda x: x.name)
    
    # Calculate how many to delete
    to_delete = len(backup_folders) - backup_count
    
    for folder in backup_folders[:to_delete]:
        print(f"  Removing old backup: {folder.name}")
        shutil.rmtree(folder)


def files_changed(current_hash: dict, previous_hash: dict) -> bool:
    """Check if any files have changed between two hashes."""
    if not previous_hash:
        return bool(current_hash)
    
    if current_hash.keys() != previous_hash.keys():
        return True
    
    for rel_path, info in current_hash.items():
        prev_info = previous_hash.get(rel_path)
        if not prev_info:
            return True
        if info['size'] != prev_info['size'] or info['mtime'] != prev_info['mtime']:
            return True
    
    return False


def copy_file_safe(src: Path, dst: Path, progress_callback=None):
    """Copy a file, creating parent directories if needed.
    
    Args:
        src: Source file path
        dst: Destination file path
        progress_callback: Optional callback(bytes_copied) for progress tracking
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    # Use shutil.copyfileobj for chunked copying with progress
    import shutil
    
    with open(src, 'rb') as fsrc:
        with open(dst, 'wb') as fdst:
            # Copy in 64KB chunks for smoother progress
            chunk_size = 64 * 1024
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)
                if progress_callback:
                    progress_callback(len(chunk))
    
    # Preserve metadata after copy
    shutil.copystat(src, dst)


def perform_backup(path_original: Path, path_backup: Path, backup_count: int) -> bool:
    """
    Perform incremental backup.
    
    Returns True if backup was created, False if skipped (no changes).
    """
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    new_backup_path = path_backup / timestamp
    
    # Get current state
    current_hash = get_folder_hash(path_original)
    
    if not current_hash:
        print(f"[{timestamp}] Source folder is empty, skipping backup.")
        return False
    
    # Get previous backup
    latest_backup = get_latest_backup(path_backup)
    previous_hash = get_folder_hash(latest_backup) if latest_backup else {}
    
    # Check if anything changed
    if not files_changed(current_hash, previous_hash):
        print(f"[{timestamp}] No changes detected, skipping backup.")
        return False
    
    # Create new backup folder
    new_backup_path.mkdir(parents=True, exist_ok=True)
    
    print(f"[{timestamp}] Performing backup...")
    
    # Determine which files to copy from where
    files_from_original = []
    files_from_previous = []
    
    for rel_path, info in current_hash.items():
        prev_info = previous_hash.get(rel_path)
        
        if not prev_info:
            # New file
            files_from_original.append(rel_path)
        elif info['size'] != prev_info['size'] or info['mtime'] != prev_info['mtime']:
            # Changed file
            files_from_original.append(rel_path)
        else:
            # Unchanged file - copy from previous backup
            files_from_previous.append(rel_path)
    
    # Calculate total sizes for progress bars
    total_original_size = sum(current_hash[rel_path]['size'] for rel_path in files_from_original)
    total_previous_size = sum(previous_hash[rel_path]['size'] for rel_path in files_from_previous) if previous_hash else 0

    # Copy changed/new files from original
    if tqdm and files_from_original:
        pbar_original = tqdm(total=total_original_size, desc="Original files", unit='B', unit_scale=True, leave=False, mininterval=0.1, ncols=100)
        for rel_path in files_from_original:
            src = path_original / rel_path
            dst = new_backup_path / rel_path
            copy_file_safe(src, dst, progress_callback=pbar_original.update)
        pbar_original.close()
    else:
        for rel_path in files_from_original:
            src = path_original / rel_path
            dst = new_backup_path / rel_path
            copy_file_safe(src, dst)

    # Copy unchanged files from previous backup
    if tqdm and files_from_previous:
        pbar_previous = tqdm(total=total_previous_size, desc="Previous files", unit='B', unit_scale=True, leave=False, mininterval=0.1, ncols=100)
        for rel_path in files_from_previous:
            src = latest_backup / rel_path
            dst = new_backup_path / rel_path
            copy_file_safe(src, dst, progress_callback=pbar_previous.update)
        pbar_previous.close()
    else:
        for rel_path in files_from_previous:
            src = latest_backup / rel_path
            dst = new_backup_path / rel_path
            copy_file_safe(src, dst)
    
    # Update 'latest' reference (using text file to avoid symlink privileges)
    latest_file = path_backup / 'latest.txt'
    with open(latest_file, 'w') as f:
        f.write(str(new_backup_path))

    total_files = len(files_from_original) + len(files_from_previous)
    print(f"[{timestamp}] Backup complete: {total_files} files "
          f"({len(files_from_original)} from original, {len(files_from_previous)} from previous)")

    try:
        capture_game_screenshot(new_backup_path)
    except:
        print('Cant create screenshot')

    # Cleanup old backups
    cleanup_old_backups(path_backup, backup_count)
    
    return True


def wait_for_backup_trigger(wait_seconds: int, path_original: Path, path_backup: Path) -> bool:
    """
    Wait for backup trigger with keyboard input.

    Returns True if backup should run (timeout or 'B' pressed), False if interrupted.
    """
    print(f"Press 'B' to backup, 'F' for folders, 'S' for screenshot. Next in {wait_seconds // 60} min...")

    for remaining in range(wait_seconds, 0, -1):
        minutes, seconds = divmod(remaining, 60)
        print(f"\r  Waiting... [{minutes:02d}:{seconds:02d}]  ", end='', flush=True)

        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
            if key == 'b':
                print("\r  [B] Early backup triggered!                    ")
                return True
            elif key == 'f':
                print("\r  [F] Opening folders...                         ")
                open_folders_in_explorer(path_original, path_backup)
            elif key == 's':
                print("\r  [S] Capturing screenshot...                    ")
                capture_game_screenshot(path_backup)

        time.sleep(1)

    print("\r  Time's up!                                            ")
    return True


def open_folders_in_explorer(path_original: Path, path_backup: Path):
    """Open original and backup folders in Windows Explorer, positioned side by side."""
    import threading

    # Start Explorer windows in background threads to avoid blocking
    def open_and_position(explorer_path, target_x, target_width, target_height):
        """Open folder and attempt to position window."""
        # Open Explorer
        subprocess.Popen(['explorer.exe', str(explorer_path)])
        
        # Give Windows time to create the window
        time.sleep(0.5)
        
        if PYWINCTL_AVAILABLE and pywinctl:
            try:
                # Find the Explorer window (look for window containing the path)
                windows = pywinctl.getAllWindows()
                for win in windows:
                    title = win.title.lower()
                    # Try to match by path or common explorer patterns
                    if 'explorer' in title.lower() or str(explorer_path).lower() in title.lower():
                        # Move and resize the window
                        win.moveTo(target_x, 0, target_width, target_height)
                        win.activate()
                        break
            except Exception:
                # If positioning fails, windows still open normally
                pass

    # Get screen dimensions (assume primary screen)
    try:
        if PYWINCTL_AVAILABLE and pywinctl:
            screen = pywinctl.getScreenSize()
            screen_width = screen[0]
            screen_height = screen[1]
            half_width = screen_width // 2
        else:
            # Fallback: use common resolution
            screen_width = 1920
            screen_height = 1080
            half_width = 960
    except Exception:
        screen_width = 1920
        screen_height = 1080
        half_width = 960

    # Open backup on left, original on right
    # Use threads to open both simultaneously
    thread_backup = threading.Thread(
        target=open_and_position,
        args=(path_backup, 0, half_width, screen_height),
        daemon=True
    )
    thread_original = threading.Thread(
        target=open_and_position,
        args=(path_original, half_width, half_width, screen_height),
        daemon=True
    )

    thread_backup.start()
    thread_original.start()
    
    # Wait briefly for windows to open
    thread_backup.join(timeout=2)
    thread_original.join(timeout=2)
    
    print("  Opened: Backup (left) | Original (right)")


def capture_game_screenshot(path_backup: Path):
    """
    Capture screenshot of ShooterGame.exe window.
    
    Works even when window is minimized or covered by other windows.
    Saves screenshot to backup folder with timestamp.
    """
    if not WIN32_AVAILABLE:
        print("  [!] pywin32 not installed. Install with: pip install pywin32")
        return None
        pass
    
    try:
        # Find ShooterGame window
        hwnd = win32gui.FindWindow(None, "ARK: Survival Evolved")
        
        if not hwnd:
            # Try finding by process name if title doesn't match
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] == 'ShooterGame.exe':
                        # Get main window handle for this process
                        hwnd = _find_window_by_pid(proc.info['pid'])
                        if hwnd:
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        if not hwnd:
            print("  [!] ShooterGame.exe window not found")
            return None
        
        # Get window rectangle
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        
        if width <= 0 or height <= 0:
            print("  [!] Invalid window dimensions")
            return None
        
        # Create device contexts
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        # Create bitmap and select it into save_dc
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        old_bitmap = save_dc.SelectObject(bitmap)

        # PrintWindow with PW_RENDERFULLCONTENT to capture even when minimized
        result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)

        if result == 0:
            # Clean up on failure - restore old bitmap first
            save_dc.SelectObject(old_bitmap)
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())
            print("  [!] Failed to capture window (may be using exclusive fullscreen)")
            return None

        # Convert to PIL Image and save
        try:
            from PIL import Image
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)

            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            # Save to backup folder
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            screenshot_path = path_backup / f'screenshot_{timestamp}.png'
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(screenshot_path, 'PNG')

            # Clean up - restore old bitmap first, then delete in reverse order
            save_dc.SelectObject(old_bitmap)
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            print(f"  Screenshot saved: {screenshot_path.name}")
            return screenshot_path

        except ImportError:
            # Clean up on Pillow import error
            save_dc.SelectObject(old_bitmap)
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())
            print("  [!] Pillow not installed. Install with: pip install Pillow")
            return None
        
    except Exception as e:
        print(f"  [!] Screenshot failed: {e}")
        return None


def _find_window_by_pid(pid: int):
    """Find window handle by process ID."""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            try:
                _, found_pid = win32gui.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    windows.append(hwnd)
            except Exception:
                pass
        return True
    
    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows[0] if windows else None


def main():
    """Main entry point."""
    config_path = Path(__file__).parent / 'env.txt'
    config = load_config(config_path)

    path_original = Path(config['path_origin'])
    path_backup = Path(config['path_backup'])
    backup_time = int(config['backup_time'])
    backup_count = int(config.get('backup_count', 10))

    print(f"ARK Backups initialized")
    print(f"  Source: {path_original}")
    print(f"  Backup: {path_backup}")
    print(f"  Interval: {backup_time} minutes")
    print(f"  Max backups: {backup_count}")
    print("-" * 50)

    while True:
        try:
            perform_backup(path_original, path_backup, backup_count)
        except Exception as e:
            print(f"Error during backup: {e}")

        wait_seconds = backup_time * 60
        wait_for_backup_trigger(wait_seconds, path_original, path_backup)


if __name__ == '__main__':
    main()
