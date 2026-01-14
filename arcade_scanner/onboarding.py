"""
First-run onboarding setup wizard for Arcade Media Scanner.
Provides an interactive ASCII terminal experience for initial configuration.
"""
import os
import sys
import shutil
import subprocess
from typing import Optional, List, Tuple

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

ARCADE_BANNER = f"""{Colors.CYAN}
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║  {Colors.YELLOW}█████╗ ██████╗  ██████╗ █████╗ ██████╗ ███████╗{Colors.CYAN}                              ║
║  {Colors.YELLOW}██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝{Colors.CYAN}                              ║
║  {Colors.YELLOW}███████║██████╔╝██║     ███████║██║  ██║█████╗{Colors.CYAN}                                ║
║  {Colors.YELLOW}██╔══██║██╔══██╗██║     ██╔══██║██║  ██║██╔══╝{Colors.CYAN}                                ║
║  {Colors.YELLOW}██║  ██║██║  ██║╚██████╗██║  ██║██████╔╝███████╗{Colors.CYAN}                              ║
║  {Colors.YELLOW}╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝{Colors.CYAN}                              ║
║                                                                               ║
║  {Colors.GREEN}███╗   ███╗███████╗██████╗ ██╗ █████╗{Colors.CYAN}                                         ║
║  {Colors.GREEN}████╗ ████║██╔════╝██╔══██╗██║██╔══██╗{Colors.CYAN}                                        ║
║  {Colors.GREEN}██╔████╔██║█████╗  ██║  ██║██║███████║{Colors.CYAN}                                        ║
║  {Colors.GREEN}██║╚██╔╝██║██╔══╝  ██║  ██║██║██╔══██║{Colors.CYAN}                                        ║
║  {Colors.GREEN}██║ ╚═╝ ██║███████╗██████╔╝██║██║  ██║{Colors.CYAN}                                        ║
║  {Colors.GREEN}╚═╝     ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═╝{Colors.CYAN}                                        ║
║                                                                               ║
║  {Colors.HEADER}███████╗ ██████╗ █████╗ ███╗   ██╗███╗   ██╗███████╗██████╗{Colors.CYAN}                  ║
║  {Colors.HEADER}██╔════╝██╔════╝██╔══██╗████╗  ██║████╗  ██║██╔════╝██╔══██╗{Colors.CYAN}                 ║
║  {Colors.HEADER}███████╗██║     ███████║██╔██╗ ██║██╔██╗ ██║█████╗  ██████╔╝{Colors.CYAN}                 ║
║  {Colors.HEADER}╚════██║██║     ██╔══██║██║╚██╗██║██║╚██╗██║██╔══╝  ██╔══██╗{Colors.CYAN}                 ║
║  {Colors.HEADER}███████║╚██████╗██║  ██║██║ ╚████║██║ ╚████║███████╗██║  ██║{Colors.CYAN}                 ║
║  {Colors.HEADER}╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝{Colors.CYAN}                 ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                      {Colors.BOLD}{Colors.YELLOW}✨ FIRST-TIME SETUP WIZARD ✨{Colors.RESET}{Colors.CYAN}                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
{Colors.RESET}"""

def print_section(title: str):
    """Print a section header."""
    width = 60
    print(f"\n{Colors.CYAN}{'━' * width}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}  {title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'━' * width}{Colors.RESET}\n")

def print_success(msg: str):
    print(f"  {Colors.GREEN}✓{Colors.RESET} {msg}")

def print_error(msg: str):
    print(f"  {Colors.RED}✗{Colors.RESET} {msg}")

def print_info(msg: str):
    print(f"  {Colors.BLUE}ℹ{Colors.RESET} {msg}")

def print_dim(msg: str):
    print(f"  {Colors.DIM}{msg}{Colors.RESET}")

def prompt(message: str, default: str = "") -> str:
    """Prompt user for input with optional default."""
    if default:
        display = f"{Colors.CYAN}▶{Colors.RESET} {message} [{Colors.DIM}{default}{Colors.RESET}]: "
    else:
        display = f"{Colors.CYAN}▶{Colors.RESET} {message}: "
    
    try:
        value = input(display).strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        print("\n")
        return default

def prompt_yes_no(message: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    default_str = "Y/n" if default else "y/N"
    response = prompt(f"{message} ({default_str})", "y" if default else "n")
    return response.lower() in ("y", "yes", "1", "true")

def expand_path(path: str) -> str:
    """Expand ~ and environment variables in path."""
    return os.path.expandvars(os.path.expanduser(path))

def validate_path(path: str, must_exist: bool = True) -> Tuple[bool, str]:
    """Validate a path, return (is_valid, expanded_path)."""
    expanded = expand_path(path)
    if must_exist and not os.path.exists(expanded):
        return False, expanded
    return True, expanded

def find_binary(name: str) -> Optional[str]:
    """Find a binary in PATH."""
    return shutil.which(name)

def validate_binary(path: str, name: str) -> bool:
    """Check if a binary exists and is executable."""
    if not path:
        return False
    expanded = expand_path(path)
    if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
        return True
    # Check if it's just a command name in PATH
    if shutil.which(path):
        return True
    return False

def detect_ffmpeg() -> Tuple[Optional[str], Optional[str]]:
    """Auto-detect ffmpeg and ffprobe paths."""
    ffmpeg = find_binary("ffmpeg")
    ffprobe = find_binary("ffprobe")
    return ffmpeg, ffprobe


def reset_databases():
    """
    Reset all application databases for a fresh start.
    Removes: users.db, video_cache.json, thumbnails
    """
    from arcade_scanner.config import HIDDEN_DATA_DIR, THUMB_DIR, CACHE_FILE
    
    files_to_remove = [
        os.path.join(HIDDEN_DATA_DIR, "users.db"),
        os.path.join(HIDDEN_DATA_DIR, "users.db-shm"),
        os.path.join(HIDDEN_DATA_DIR, "users.db-wal"),
        CACHE_FILE,
    ]
    
    removed = 0
    for f in files_to_remove:
        if os.path.exists(f):
            try:
                os.remove(f)
                removed += 1
            except Exception as e:
                print_error(f"Could not remove {os.path.basename(f)}: {e}")
    
    # Clear thumbnails directory
    if os.path.exists(THUMB_DIR):
        try:
            import shutil
            shutil.rmtree(THUMB_DIR)
            os.makedirs(THUMB_DIR)
            print_success("Thumbnails cleared")
        except Exception as e:
            print_error(f"Could not clear thumbnails: {e}")
    
    return removed


def run_setup_wizard() -> dict:
    """
    Run the interactive setup wizard and return configuration dict.
    Returns a dict with all configuration values collected.
    """
    # Clear screen
    os.system('cls' if sys.platform == 'win32' else 'clear')
    
    print(ARCADE_BANNER)
    print(f"  {Colors.DIM}Welcome! Let's configure your media scanner.{Colors.RESET}")
    print(f"  {Colors.DIM}Press Enter to accept defaults shown in [brackets].{Colors.RESET}")
    print()
    
    config = {
        "scan_targets": [],
        "exclude_paths": [],
        "min_size_mb": 100,
        "bitrate_threshold_kbps": 15000,
        "ffmpeg_path": None,
        "ffprobe_path": None,
        "create_users": [],
        "first_run_completed": True,
        "reset_db": False,
    }
    
    # =========================================================================
    # STEP 0: Database Reset Option
    # =========================================================================
    print_section("0/7 • DATABASE RESET")
    
    print_info("Would you like to start completely fresh?")
    print_dim("This will remove all existing media data, users, and thumbnails.")
    print_dim("Choose 'yes' if you're setting up from scratch or want a clean slate.")
    print()
    
    if prompt_yes_no("Reset all databases?", False):
        print()
        print_info(f"{Colors.YELLOW}⚠ WARNING:{Colors.RESET} This will permanently delete:")
        print_dim("  • All scanned media information")
        print_dim("  • All user accounts (including admin)")
        print_dim("  • All thumbnails and previews")
        print_dim("  • All favorites, tags, and collections")
        print()
        
        if prompt_yes_no(f"{Colors.RED}Are you sure?{Colors.RESET}", False):
            config["reset_db"] = True
            removed = reset_databases()
            print_success(f"Databases reset ({removed} files removed)")
        else:
            print_info("Database reset cancelled")
    else:
        print_info("Keeping existing data")
    
    # =========================================================================
    # STEP 1: ffmpeg/ffprobe Detection
    # =========================================================================
    print_section("1/7 • FFMPEG & FFPROBE")
    
    ffmpeg_path, ffprobe_path = detect_ffmpeg()
    
    if ffmpeg_path and ffprobe_path:
        print_success(f"ffmpeg found: {ffmpeg_path}")
        print_success(f"ffprobe found: {ffprobe_path}")
        
        if not prompt_yes_no("Use these paths?", True):
            ffmpeg_path = prompt("Enter path to ffmpeg", ffmpeg_path)
            ffprobe_path = prompt("Enter path to ffprobe", ffprobe_path)
    else:
        print_info("Could not auto-detect ffmpeg/ffprobe in PATH.")
        print_dim("These are required for video processing and optimization.")
        print()
        
        ffmpeg_path = prompt("Enter path to ffmpeg", "ffmpeg")
        ffprobe_path = prompt("Enter path to ffprobe", "ffprobe")
    
    # Validate
    if validate_binary(ffmpeg_path, "ffmpeg"):
        print_success("ffmpeg validated")
        config["ffmpeg_path"] = ffmpeg_path
    else:
        print_error(f"ffmpeg not found at '{ffmpeg_path}' - video optimization may not work")
        config["ffmpeg_path"] = ffmpeg_path  # Store anyway, user can fix later
    
    if validate_binary(ffprobe_path, "ffprobe"):
        print_success("ffprobe validated")
        config["ffprobe_path"] = ffprobe_path
    else:
        print_error(f"ffprobe not found at '{ffprobe_path}' - video scanning may be limited")
        config["ffprobe_path"] = ffprobe_path
    
    # =========================================================================
    # STEP 2: Scan Directories
    # =========================================================================
    print_section("2/7 • SCAN DIRECTORIES")
    
    print_info("Add directories to scan for media files.")
    print_dim("Enter paths one per line. Press Enter on empty line when done.")
    print_dim("Example: /Volumes/Media or ~/Movies")
    print()
    
    while True:
        path = prompt("Add directory (or Enter to finish)")
        if not path:
            if not config["scan_targets"]:
                print_error("At least one scan directory is required!")
                continue
            break
        
        valid, expanded = validate_path(path)
        if valid:
            config["scan_targets"].append(expanded)
            print_success(f"Added: {expanded}")
        else:
            print_error(f"Directory not found: {expanded}")
            if prompt_yes_no("Add anyway?", False):
                config["scan_targets"].append(expanded)
                print_info(f"Added (will be created/mounted later): {expanded}")
    
    # =========================================================================
    # STEP 3: Exclusions
    # =========================================================================
    print_section("3/7 • EXCLUSIONS")
    
    # Show default exclusions
    from arcade_scanner.config import DEFAULT_EXCLUSIONS
    
    print_info("The following paths are excluded by default:")
    for exc in DEFAULT_EXCLUSIONS[:5]:
        print_dim(f"  • {exc['path']} ({exc['desc']})")
    if len(DEFAULT_EXCLUSIONS) > 5:
        print_dim(f"  ... and {len(DEFAULT_EXCLUSIONS) - 5} more")
    print()
    
    print_info("Add additional paths to exclude from scanning.")
    print_dim("Enter paths one per line. Press Enter on empty line when done.")
    print()
    
    while True:
        path = prompt("Add exclusion (or Enter to skip)")
        if not path:
            break
        
        expanded = expand_path(path)
        config["exclude_paths"].append(expanded)
        print_success(f"Excluding: {expanded}")
    
    # =========================================================================
    # STEP 4: File Size Filter
    # =========================================================================
    print_section("4/7 • FILE SIZE FILTER")
    
    print_info("Set minimum file size to scan (ignores small video clips).")
    print_dim("This helps skip short clips, trailers, and samples.")
    print()
    
    while True:
        size_str = prompt("Minimum file size in MB", "100")
        try:
            size = int(size_str)
            if size >= 0:
                config["min_size_mb"] = size
                print_success(f"Files under {size}MB will be skipped")
                break
            else:
                print_error("Please enter a positive number")
        except ValueError:
            print_error("Please enter a valid number")
    
    # =========================================================================
    # STEP 5: Bitrate Threshold
    # =========================================================================
    print_section("5/7 • BITRATE THRESHOLD")
    
    print_info("Videos above this bitrate will be marked as 'HIGH BITRATE'.")
    print_dim("These are candidates for optimization/compression.")
    print()
    
    while True:
        bitrate_str = prompt("Bitrate threshold in kbps", "15000")
        try:
            bitrate = int(bitrate_str)
            if bitrate > 0:
                config["bitrate_threshold_kbps"] = bitrate
                print_success(f"Videos above {bitrate} kbps will be marked as high bitrate")
                break
            else:
                print_error("Please enter a positive number")
        except ValueError:
            print_error("Please enter a valid number")
    
    # =========================================================================
    # STEP 6: Additional Users
    # =========================================================================
    print_section("6/7 • USER ACCOUNTS")
    
    print_info("The 'admin' account will be created automatically.")
    print_dim("Default password: admin (change this after first login!)")
    print()
    
    if prompt_yes_no("Create additional user accounts now?", False):
        print_dim("Enter usernames one per line. Press Enter when done.")
        print()
        
        while True:
            username = prompt("New username (or Enter to finish)")
            if not username:
                break
            
            if username.lower() == "admin":
                print_error("'admin' is reserved")
                continue
            
            if username in config["create_users"]:
                print_error(f"'{username}' already added")
                continue
            
            # Simple validation
            if len(username) < 3:
                print_error("Username must be at least 3 characters")
                continue
            
            password = prompt(f"Password for '{username}'", username)
            config["create_users"].append({"username": username, "password": password})
            print_success(f"User '{username}' will be created")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print_section("CONFIGURATION SUMMARY")
    
    print(f"  {Colors.BOLD}Scan Directories:{Colors.RESET}")
    for t in config["scan_targets"]:
        print(f"    • {t}")
    
    if config["exclude_paths"]:
        print(f"\n  {Colors.BOLD}Additional Exclusions:{Colors.RESET}")
        for e in config["exclude_paths"]:
            print(f"    • {e}")
    
    print(f"\n  {Colors.BOLD}File Settings:{Colors.RESET}")
    print(f"    • Minimum size: {config['min_size_mb']}MB")
    print(f"    • Bitrate threshold: {config['bitrate_threshold_kbps']} kbps")
    
    print(f"\n  {Colors.BOLD}Tools:{Colors.RESET}")
    print(f"    • ffmpeg: {config['ffmpeg_path'] or 'not set'}")
    print(f"    • ffprobe: {config['ffprobe_path'] or 'not set'}")
    
    if config["create_users"]:
        print(f"\n  {Colors.BOLD}Additional Users:{Colors.RESET}")
        for u in config["create_users"]:
            print(f"    • {u['username']}")
    
    print()
    
    if not prompt_yes_no("Save this configuration?", True):
        print_info("Setup cancelled. Run the application again to restart setup.")
        sys.exit(0)
    
    print()
    print_success("Configuration saved!")
    print_info("Starting media scanner...")
    print()
    
    return config


def apply_configuration(config: dict):
    """
    Apply the wizard configuration to settings and user database.
    """
    import json
    from arcade_scanner.config import config as app_config, SETTINGS_FILE
    
    # 1. Update settings.json
    settings_data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
        except Exception:
            pass
    
    # Merge wizard config into settings
    settings_data["first_run_completed"] = True
    settings_data["min_size_mb"] = config["min_size_mb"]
    settings_data["bitrate_threshold_kbps"] = config["bitrate_threshold_kbps"]
    
    if config.get("ffmpeg_path"):
        settings_data["ffmpeg_path"] = config["ffmpeg_path"]
    if config.get("ffprobe_path"):
        settings_data["ffprobe_path"] = config["ffprobe_path"]
    
    # Save settings
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print_error(f"Failed to save settings: {e}")
    
    # 2. Update admin user with scan targets and exclusions
    from arcade_scanner.database.user_store import user_db
    
    admin = user_db.get_user("admin")
    if admin:
        # Add scan targets
        for t in config["scan_targets"]:
            if t not in admin.data.scan_targets:
                admin.data.scan_targets.append(t)
        
        # Add exclusions
        for e in config["exclude_paths"]:
            if e not in admin.data.exclude_paths:
                admin.data.exclude_paths.append(e)
        
        user_db.add_user(admin)
    
    # 3. Create additional users
    for user_info in config.get("create_users", []):
        import binascii
        
        existing = user_db.get_user(user_info["username"])
        if not existing:
            salt = os.urandom(16)
            pwd_hash = user_db.hash_password(user_info["password"], salt)
            
            from arcade_scanner.models.user import User
            new_user = User(
                username=user_info["username"],
                password_hash=binascii.hexlify(pwd_hash).decode('ascii'),
                salt=binascii.hexlify(salt).decode('ascii'),
                is_admin=False
            )
            user_db.add_user(new_user)
            print_success(f"Created user: {user_info['username']}")


def should_run_wizard() -> bool:
    """
    Check if the setup wizard should run.
    Returns True if first_run_completed is not set to True.
    """
    import json
    from arcade_scanner.config import SETTINGS_FILE
    
    if not os.path.exists(SETTINGS_FILE):
        return True
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return not data.get("first_run_completed", False)
    except Exception:
        return True


def run_onboarding():
    """
    Main entry point for onboarding.
    Checks if wizard should run, and if so, runs it and applies config.
    """
    if not should_run_wizard():
        return False
    
    try:
        config = run_setup_wizard()
        apply_configuration(config)
        return True
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Setup cancelled.{Colors.RESET}")
        sys.exit(0)
