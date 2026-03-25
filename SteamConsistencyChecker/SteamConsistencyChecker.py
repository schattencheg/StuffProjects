import os
import pathlib
import winreg


def get_steam_path():
    """Get Steam install path from registry."""
    paths = []
    registry_keys = [
        r"SOFTWARE\Valve\Steam",
        r"SOFTWARE\WOW6432Node\Valve\Steam"
    ]
    
    for subkey in registry_keys:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey)
            path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            paths.append(path)
        except FileNotFoundError:
            continue
    
    return paths[0] if paths else None


def parse_vdf(file_path):
    """Simple recursive VDF parser for libraryfolders.vdf."""
    def vdf_parse(f, config):
        line = " "
        prev_elements = []
        
        while line:
            line = f.readline()
            if not line or line.strip() == "}":
                return config
            
            elements = [e.strip() for e in line.split('"') if e.strip()]
            
            if len(elements) == 1 and elements[0] == "{":
                key = prev_elements[0]
                config[key] = vdf_parse(f, {})
            elif len(elements) == 2:
                config[elements[0]] = elements[1]
            
            prev_elements = elements
        
        return config

    with open(file_path, 'r', encoding='utf-8') as f:
        return vdf_parse(f, {})


def get_files(path, mask):
    """Get files matching a glob pattern in the specified directory."""
    return [x.name for x in pathlib.Path(path).glob(mask)]


def main():
    """Main execution logic."""
    steam_path = get_steam_path()
    libraries = []
    
    if not steam_path:
        print("[ERROR] Steam not found in registry.")
        return
    
    vdf_path = os.path.join(steam_path, "config", "libraryfolders.vdf")
    
    if not os.path.exists(vdf_path):
        print(f"[WARNING] libraryfolders.vdf not found at: {vdf_path}")
        print(f"[INFO] Using default Steam path only: {steam_path}")
        libraries.append(steam_path)
    else:
        data = parse_vdf(vdf_path)
        subdata = data.get('libraryfolders', {})
        
        for key in subdata:
            if key.isdigit():
                path = subdata[key].get("path", "").strip().replace("\\\\", "\\")
                if path:
                    libraries.append(path)
        
        print(f"[INFO] Found {len(libraries)} Steam library location(s):")
        for lib in libraries:
            print(f"  - {lib}")
    
    # Process each library
    for lib_path in libraries:
        steamapps_path = os.path.join(lib_path, 'steamapps')
        common_path = os.path.join(steamapps_path, 'common')
        
        print(f"\n[INFO] Scanning library: {steamapps_path}")
        
        if not os.path.exists(steamapps_path):
            print(f"  [WARNING] steamapps folder not found at: {steamapps_path}")
            continue
        
        manifest_files = get_files(steamapps_path, "*acf*")
        installed_folders = get_files(common_path, "*") if os.path.exists(common_path) else []
        
        installed_names = set()
        manifest_entries = []
        
        # Parse manifest files
        for manifest_file in manifest_files:
            manifest_path = os.path.join(steamapps_path, manifest_file)
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "installdir" in line.lower():
                            name = line.split("\"")[-2]
                            installed_names.add(name)
                            
                            if name not in installed_folders:
                                entry = f"[MISSING] {name} [{manifest_file}]"
                            else:
                                entry = f"[OK] {name} [{manifest_file}]"
                            manifest_entries.append(entry)
            except (IOError, OSError) as e:
                print(f"  [ERROR] Could not read manifest: {manifest_file} - {e}")
        
        # Display manifest results
        print(f"\n  Manifest files ({len(manifest_entries)}):")
        for entry in manifest_entries:
            print(f"    {entry}")
        
        # Check for orphaned folders
        orphaned_folders = [f for f in installed_folders if f not in installed_names]
        
        if orphaned_folders:
            print(f"\n  [WARNING] Found {len(orphaned_folders)} orphaned folder(s):")
            for folder in orphaned_folders:
                print(f"    [ORPHAN] {folder}")
        else:
            print(f"\n  [OK] No orphaned folders found")


if __name__ == "__main__":
    main()
