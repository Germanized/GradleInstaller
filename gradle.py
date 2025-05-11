import os
import sys
import subprocess
import ctypes
import requests
import zipfile
import shutil
import winreg
import time

try:
    from rich.console import Console
    from rich.text import Text
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
    from rich.style import Style
    from rich.theme import Theme
    import winshell
    from winshell import shortcut
    import win32gui
    import win32con
except ImportError:
    # rich is critical for the admin prompt too, so check before anything else
    # that might use `console`.
    # Fallback to basic print if rich is not available for this initial error.
    is_rich_available = all(mod in sys.modules for mod in ['rich.console', 'rich.prompt'])
    if not is_rich_available:
        print("CRITICAL ERROR: Required library 'rich' is not installed.")
        print("This script cannot proceed without it, even to show prompts.")
        print("Please install it by running: pip install rich requests winshell pywin32")
        if not getattr(sys, 'frozen', False):
             input("Press Enter to exit.") # Stall if run from python
        sys.exit(1)
    
    # If rich is available, but others are missing, use rich console for the message.
    # Define a basic console for this specific error message if rich.console is available.
    console_fallback = None
    try:
        from rich.console import Console as RichConsole
        from rich.theme import Theme as RichTheme
        console_fallback_theme = RichTheme({"danger": "bold red"})
        console_fallback = RichConsole(theme=console_fallback_theme)
        console_fallback.print("[danger]Required libraries (requests, winshell, pywin32) are not installed (or 'rich' components are missing).[/danger]")
        console_fallback.print("[danger]Please install them by running: pip install rich requests winshell pywin32[/danger]")
    except Exception: # Fallback if even RichConsole can't be instantiated
        print("Required libraries (requests, winshell, pywin32) are not installed (or 'rich' components are missing).")
        print("Please install them by running: pip install rich requests winshell pywin32")

    if getattr(sys, 'frozen', False) and console_fallback: 
        Prompt.ask("Press Enter to exit.", console=console_fallback)
    else: 
        input("Press Enter to exit.")
    sys.exit(1)


GRADLE_VERSION = None
DOWNLOAD_URL = None
TEMP_DIR = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "gradle_installer_py")
GRADLE_ZIP_NAME = None
GRADLE_ZIP_PATH = None
INSTALL_DIR = "C:\\Gradle"
GRADLE_HOME_DIR_NAME = None
GRADLE_HOME = None

custom_theme = Theme({
    "info": "cyan", "warning": "yellow", "danger": "bold red",
    "success": "bold green", "highlight": "bold magenta", "title": "bold cyan on black",
    "path": "italic blue", "variable": "bold yellow"
})
console = Console(theme=custom_theme, width=100)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError: 
        return False
    except Exception: 
        return False

def run_as_admin():
    if sys.platform != 'win32':
        console.print("[danger]This script is designed for Windows only and cannot be re-launched as admin on other platforms.[/danger]")
        return False

    try:
        script_args = sys.argv[1:] 

        if getattr(sys, 'frozen', False):  
            executable_to_run = sys.executable
            parameters_list = script_args
        else:  
            executable_to_run = sys.executable  
            current_script_path = os.path.abspath(sys.argv[0])
            parameters_list = [current_script_path] + script_args
        
        parameters_for_shell = ' '.join([f'"{p}"' for p in parameters_list])

        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable_to_run, parameters_for_shell, os.getcwd(), 1 
        )

        if ret > 32:
            return True 
        else:
            error_messages = {
                0: "The operating system is out of memory or resources.", 2: "The specified file was not found.",
                3: "The specified path was not found.", 5: "Access was denied. (UAC may be disabled or policy restrictions in place).",
                8: "There was not enough memory to complete the operation.", 31: "There is no application associated with the specified file type."
            }
            error_message = error_messages.get(ret, f"Unknown error code: {ret}")
            console.print(f"[danger]Failed to re-launch as admin. ShellExecuteW error: {error_message}[/danger]")
            console.print("[danger]Please try running the script manually as an administrator.[/danger]")
            return False
            
    except Exception as e:
        console.print(f"[danger]Exception while trying to re-launch as admin: {e}[/danger]")
        console.print("[danger]Please try running the script manually as an administrator.[/danger]")
        return False

def fetch_latest_gradle_version():
    api_url = "https://services.gradle.org/versions/current"
    console.print(f"Fetching latest Gradle version from [link={api_url}]{api_url}[/link]...", style="info")
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        latest_version = data.get("version")
        if latest_version:
            console.print(f"  [success]Latest Gradle version found: [variable]{latest_version}[/variable][/success]")
            return latest_version
        else:
            console.print("  [danger]Could not parse version from API response.[/danger]")
            return None
    except requests.RequestException as e:
        console.print(f"  [danger]Error fetching latest Gradle version: {e}[/danger]")
        return None
    except ValueError: 
        console.print("  [danger]Error parsing version data (not valid JSON).[/danger]")
        return None

def update_global_config(version_str):
    global GRADLE_VERSION, DOWNLOAD_URL, GRADLE_ZIP_NAME, GRADLE_ZIP_PATH
    global GRADLE_HOME_DIR_NAME, GRADLE_HOME, INSTALL_DIR

    GRADLE_VERSION = version_str
    DOWNLOAD_URL = f"https://services.gradle.org/distributions/gradle-{GRADLE_VERSION}-bin.zip"
    GRADLE_ZIP_NAME = f"gradle-{GRADLE_VERSION}-bin.zip"
    GRADLE_ZIP_PATH = os.path.join(TEMP_DIR, GRADLE_ZIP_NAME)
    GRADLE_HOME_DIR_NAME = f"gradle-{GRADLE_VERSION}"
    GRADLE_HOME = os.path.join(INSTALL_DIR, GRADLE_HOME_DIR_NAME)

def lerp_color(color1_rgb, color2_rgb, factor):
    r = int(color1_rgb[0] + (color2_rgb[0] - color1_rgb[0]) * factor)
    g = int(color1_rgb[1] + (color2_rgb[1] - color1_rgb[1]) * factor)
    b = int(color1_rgb[2] + (color2_rgb[2] - color1_rgb[2]) * factor)
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

def print_logo():
    logo_art = """
                                                             @@@@@@@@@@@
                                                          @@@@@@@@@@@@@@@@@
                                                         @@@@@@@@@@@@@@@@@@@@
                                                          @@@@@@   @@@@@@@@@@@
                                                                      @@@@@@@@@
                               @@@@@@@                                   @@@@@@@@
                       @@@@@@@@@@@@@@@@@@@@@@@                           @@@@@@@@
                  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@                      @@@@@@@@
               @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@                  @@@@@@@@
              @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@             @@@@@@@@@
              @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@      @@@@@@@@@@@@
               @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
           @@@  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
         @@@@@@  @@@@@@@@@@@@@@@@@@@ @@@@@@@@@@@@@@@@   @@@@@@@@@@@@@@@@@@@@@@@
       @@@@@@@@@@ @@@@@@@@@@@@@@@@  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@ @@@@@@@@@@@@   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@ @@@@@@@@   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@       @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@         @@@@@@@@@@@@@@@@         @@@@@@@@@@@@@
@@@@@@@@@@@             @@@@@@@@@@@@             @@@@@@@@@@
@@@@@@@@@@               @@@@@@@@@@               @@@@@@@@@
@@@@@@@@@@                @@@@@@@@                @@@@@@@@@
"""
    logo_lines = logo_art.strip("\n").split("\n")
    num_lines = len(logo_lines)
    START_COLOR_RGB = (0, 60, 60); END_COLOR_RGB = (120, 255, 255) 
    console.print()
    for i, line in enumerate(logo_lines):
        factor = i / (num_lines - 1) if num_lines > 1 else 0
        current_rgb_color = lerp_color(START_COLOR_RGB, END_COLOR_RGB, factor)
        style = Style(color=f"rgb({current_rgb_color[0]},{current_rgb_color[1]},{current_rgb_color[2]})")
        console.print(Text(line, style=style), justify="center")
    console.print()

def check_java():
    console.print("Checking for Java installation...", style="info")
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            console.print("  [success]Java is installed.[/success]"); return True
        else:
            console.print("  [warning]Java not found! Gradle requires Java Development Kit (JDK).[/warning]")
            console.print("  Please install a JDK from: [link=https://adoptium.net/]Adoptium (Recommended)[/link] or [link=https://www.oracle.com/java/technologies/javase-downloads.html]Oracle Java SE[/link]")
            return False
    except FileNotFoundError:
        console.print("  [warning]Java command not found. Is JDK installed and an entry for it in PATH variable?[/warning]"); return False

def set_env_var_system(var_name, var_value):
    console.print(f"Setting system environment variable [variable]{var_name}[/variable] to [path]{var_value}[/path]...", style="info")
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", 0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(key, var_name, 0, winreg.REG_EXPAND_SZ if '%' in var_value else winreg.REG_SZ, var_value)
        winreg.CloseKey(key)
        console.print(f"  [success]Successfully set {var_name}.[/success]"); return True
    except Exception as e:
        console.print(f"  [danger]Failed to set system environment variable {var_name}: {e}[/danger]"); return False

def add_to_path_system(dir_to_add):
    console.print(f"Adding [path]{dir_to_add}[/path] to system PATH environment variable...", style="info")
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", 0, winreg.KEY_ALL_ACCESS)
        current_path, reg_type = winreg.QueryValueEx(key, "Path")
        
        paths = current_path.split(';')
        normalized_dir_to_add = os.path.normpath(dir_to_add)
        
        path_already_exists = any(os.path.normpath(p) == normalized_dir_to_add for p in paths)
        
        if not path_already_exists:
            if not current_path or current_path.endswith(';'):
                new_path = f"{current_path}{dir_to_add}"
            else:
                new_path = f"{current_path};{dir_to_add}"
            winreg.SetValueEx(key, "Path", 0, reg_type, new_path) 
            console.print(f"  [success]Successfully added {dir_to_add} to system PATH.[/success]")
        else:
            console.print(f"  [info]{dir_to_add} is already in system PATH.[/info]")
        winreg.CloseKey(key); return True
    except Exception as e:
        console.print(f"  [danger]Failed to update system PATH: {e}[/danger]"); return False

def broadcast_env_change():
    console.print("Broadcasting environment variable changes to other processes...", style="info")
    try:
        win32gui.SendMessageTimeout(
            win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, "Environment",
            win32con.SMTO_ABORTIFHUNG | win32con.SMTO_NORMAL, 1000)
        console.print("  [success]Environment change broadcast sent.[/success]")
    except Exception as e:
        console.print(f"  [warning]Failed to broadcast environment change: {e}. A system restart may be required for changes to take full effect everywhere.[/warning]")

def set_cmd_colors():
    console.print("Setting up custom CMD color scheme (Teal & White for this session)...", style="info")
    colors = {
        "ColorTable00": 0x001E1E1E, "ColorTable01": 0x00C84A33, "ColorTable02": 0x003EC84A,
        "ColorTable03": 0x00D0B000, "ColorTable04": 0x00334AC8, "ColorTable05": 0x00C83ED0,
        "ColorTable06": 0x000080D0, "ColorTable07": 0x00E0E0E0, "ColorTable08": 0x00808080,
        "ColorTable09": 0x00FF8A70, "ColorTable10": 0x007EFF8A, "ColorTable11": 0x00FFFF00,
        "ColorTable12": 0x00708AFF, "ColorTable13": 0x00FF7EF0, "ColorTable14": 0x0000FFFF,
        "ColorTable15": 0x00FFFFFF, "ScreenColors": 0x0000000E, "PopupColors":  0x000000F5  
    }
    try:
        key_path = r"Console"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) 
        for name, value in colors.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        console.print("  [success]Default CMD color scheme configured in registry.[/success]"); return True
    except Exception as e:
        console.print(f"  [danger]Failed to set default CMD color scheme in registry: {e}[/danger]"); return False

def create_shortcut():
    global GRADLE_VERSION, GRADLE_HOME
    console.print("Creating Gradle Command Prompt shortcut on Desktop...", style="info")
    desktop_path = winshell.desktop()
    shortcut_path = os.path.join(desktop_path, f"Gradle Command Prompt ({GRADLE_VERSION}).lnk")
    target_exe = os.path.expandvars("%windir%\\system32\\cmd.exe")
    arguments = (f'/K "title Gradle {GRADLE_VERSION} Command Prompt & color 0E & '
                 f'echo Gradle {GRADLE_VERSION} Environment Initialized & echo GRADLE_HOME is set to: {GRADLE_HOME} & '
                 f'echo PATH includes: {os.path.join(GRADLE_HOME, "bin")} & '
                 f'echo.& gradle --version & echo.& cd /d %USERPROFILE%"')
    icon_location = target_exe 
    
    try:
        with shortcut(shortcut_path) as sc:
            sc.path = target_exe
            sc.arguments = arguments
            sc.description = f"Command Prompt for Gradle {GRADLE_VERSION} (GRADLE_HOME={GRADLE_HOME})"
            sc.icon_location = (icon_location, 0) 
            sc.working_directory = os.path.expanduser("~") 
        console.print(f"  [success]Shortcut created: [path]{shortcut_path}[/path][/success]"); return True
    except Exception as e:
        console.print(f"  [danger]Failed to create shortcut: {e}[/danger]"); return False

def verify_gradle():
    global GRADLE_VERSION, GRADLE_HOME
    console.print("Verifying Gradle installation...", style="info")
    gradle_exe = os.path.join(GRADLE_HOME, "bin", "gradle.bat") 

    if not os.path.exists(gradle_exe):
        console.print(f"  [danger]Gradle executable not found at [path]{gradle_exe}[/path]. Verification cannot proceed.[/danger]"); return False
    
    try:
        env = os.environ.copy()
        env["GRADLE_HOME"] = GRADLE_HOME
        env["PATH"] = os.path.join(GRADLE_HOME, "bin") + os.pathsep + env["PATH"]
        
        result = subprocess.run([gradle_exe, "--no-daemon", "--version"], capture_output=True, text=True, check=False, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        
        console.print("-" * 60, style="dim")
        if result.stdout:
            console.print(Text(result.stdout.strip(), style="dim"))
        if result.stderr:
            console.print(f"[warning]stderr from gradle --version:\n{result.stderr.strip()}[/warning]")
        console.print("-" * 60, style="dim")
        
        if result.returncode == 0 and f"Gradle {GRADLE_VERSION}" in result.stdout:
            console.print(f"  [success]Gradle {GRADLE_VERSION} verified successfully![/success]"); return True
        elif result.returncode == 0:
            console.print(f"  [warning]Gradle command executed, but version string mismatch or not found in output. Expected '{GRADLE_VERSION}'.[/warning]")
            return False
        else:
            console.print(f"  [danger]Gradle {GRADLE_VERSION} verification failed. Return code: {result.returncode}[/danger]"); return False
    except Exception as e:
        console.print(f"  [danger]An error occurred while verifying Gradle: {e}[/danger]"); return False

def stop_gradle_daemons():
    global GRADLE_HOME
    console.print("Attempting to stop all running Gradle daemons (if any)...", style="info")
    if not GRADLE_HOME or not os.path.isdir(GRADLE_HOME):
        console.print(f"  [warning]GRADLE_HOME ([path]{GRADLE_HOME}[/path]) is not valid. Cannot stop daemons.[/warning]")
        return False
        
    gradle_exe = os.path.join(GRADLE_HOME, "bin", "gradle.bat")
    if not os.path.exists(gradle_exe):
        console.print(f"  [warning]Gradle executable not found at [path]{gradle_exe}[/path]. Cannot stop daemons.[/warning]")
        return False
        
    try:
        env = os.environ.copy()
        env["GRADLE_HOME"] = GRADLE_HOME 
        env["PATH"] = os.path.join(GRADLE_HOME, "bin") + os.pathsep + env["PATH"] 

        result = subprocess.run([gradle_exe, "--no-daemon", "--stop"], capture_output=True, text=True, check=False, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        
        if result.stdout:
            processed_stdout = result.stdout.strip().replace('\n', '\n  ') 
            console.print(f"  [info]Output from 'gradle --stop':[/info]\n  [dim]{processed_stdout}[/dim]")
        if result.stderr:
            processed_stderr = result.stderr.strip().replace('\n', '\n  ')
            console.print(f"  [warning]Error output from 'gradle --stop':[/warning]\n  [dim]{processed_stderr}[/dim]")

        if result.returncode == 0:
            console.print("  [success]Gradle '--stop' command executed successfully.[/success]")
            console.print("  Waiting a few seconds for daemons to terminate gracefully...", style="info")
            time.sleep(5) 
            return True
        else:
            console.print("  [warning]Gradle '--stop' command finished with an error (this might be okay if no daemons were running or due to environment issues).[/warning]")
            time.sleep(2)
            return False 
    except Exception as e:
        console.print(f"  [danger]Error executing 'gradle --stop': {e}[/danger]")
        return False

def cleanup_old_gradle_versions():
    global INSTALL_DIR, GRADLE_HOME 
    console.print(f"Cleaning up old Gradle installations in [path]{INSTALL_DIR}[/path] (excluding current: [path]{GRADLE_HOME}[/path])...", style="info")
    if not os.path.isdir(INSTALL_DIR):
        console.print(f"  [info]Installation directory [path]{INSTALL_DIR}[/path] not found. Nothing to clean.[/info]")
        return

    cleaned_count = 0
    error_count = 0
    normalized_current_gradle_home = os.path.normpath(GRADLE_HOME)

    for item_name in os.listdir(INSTALL_DIR):
        item_path = os.path.join(INSTALL_DIR, item_name)
        if os.path.isdir(item_path) and item_name.startswith("gradle-") and os.path.normpath(item_path) != normalized_current_gradle_home:
            console.print(f"  Attempting to remove old version: [path]{item_path}[/path]")
            try:
                shutil.rmtree(item_path)
                console.print(f"    [success]Successfully removed [path]{item_path}[/path][/success]")
                cleaned_count += 1
            except OSError as e: 
                console.print(f"    [danger]Failed to remove [path]{item_path}[/path]: {e}[/danger]")
                console.print(f"    [info]This might be due to lingering processes. A reboot might be required to fully clean up, or manually delete it later.[/info]")
                error_count += 1
    
    if cleaned_count == 0 and error_count == 0:
        console.print("  No old Gradle versions found to remove (other than the current one).", style="info")
    elif error_count > 0:
        console.print(f"  [warning]Cleanup attempt finished. {cleaned_count} old version(s) removed. {error_count} version(s) could not be automatically removed.[/warning]")
    else: 
        console.print(f"  [success]Successfully cleaned up {cleaned_count} old Gradle version(s).[/success]")

def main():
    global GRADLE_VERSION, DOWNLOAD_URL, GRADLE_ZIP_NAME, GRADLE_ZIP_PATH
    global GRADLE_HOME_DIR_NAME, GRADLE_HOME, TEMP_DIR, INSTALL_DIR

    if not is_admin():
        console.clear()
        try: console.show_cursor(False) 
        except Exception: pass
        
        print_logo()
        console.print()
        console.print(Panel("[b yellow]ADMINISTRATOR PRIVILEGES REQUIRED[/b yellow]\n\n"
                            "This script needs administrator privileges to install Gradle, modify\n"
                            "system environment variables, and create system-wide settings.\n\n"
                            "It can attempt to restart itself with the required permissions.",
                            title="Permissions Notice", border_style="yellow", expand=False))
        console.print()
        
        if Confirm.ask("Do you want to try restarting as administrator now?", default=True, console=console):
            console.print("\nAttempting to re-launch with admin rights...", style="info")
            time.sleep(1)  
            
            if run_as_admin():
                sys.exit(0) 
            else:
                console.print("[warning]Could not automatically restart with admin rights.[/warning]")
                console.print("Please close this window and run the script manually as an administrator (right-click -> Run as administrator).")
                if getattr(sys, 'frozen', False): Prompt.ask("Press Enter to exit.", console=console)
                else: input("Press Enter to exit.")
                sys.exit(1)
        else:
            console.print("\nUser declined to restart with admin privileges.", style="warning")
            console.print("Please run the script manually as an administrator if you wish to proceed with the installation.")
            if getattr(sys, 'frozen', False): Prompt.ask("Press Enter to exit.", console=console)
            else: input("Press Enter to exit.")
            sys.exit(1)
        # The finally block for show_cursor(True) in the initial if __name__ == "__main__" 
        # will handle restoring cursor for these sys.exit() paths if script is run directly
    # --- If we are here, we are running as Admin ---
    try: console.show_cursor(True) 
    except Exception: pass
            
    console.clear(); print_logo()
    latest_version = fetch_latest_gradle_version()
    if not latest_version:
        console.print("[danger]Could not determine the latest Gradle version. Aborting installation.[/danger]")
        if getattr(sys, 'frozen', False): Prompt.ask("Press Enter to exit.", console=console)
        else: input("Press Enter to exit.")
        sys.exit(1)
    update_global_config(latest_version)

    console.print(Panel(f"[bold white on teal] Gradle Setup Utility by Germanized [/]\n[dim]Targeting Gradle: [variable]{GRADLE_VERSION}[/variable][/dim]",
                  title="Welcome", subtitle=f"Latest: v{GRADLE_VERSION}", highlight=True))

    console.rule("[bold cyan]System Checks[/bold cyan]")
    if not check_java():
        if not Confirm.ask("Java JDK not found or verification failed. Gradle may not work.\nContinue with Gradle installation anyway?", default=False, console=console):
            console.print("Installation aborted by user due to Java JDK issue.", style="warning")
            sys.exit(1)
    console.print()

    console.rule("[bold cyan]Installation Settings[/bold cyan]")
    console.print(f"  Gradle Version: [variable]{GRADLE_VERSION}[/variable] (Latest)")
    console.print(f"  Download URL: [link={DOWNLOAD_URL}]{DOWNLOAD_URL}[/link]")
    console.print(f"  Temporary Directory: [path]{TEMP_DIR}[/path]")
    console.print(f"  Installation Root Directory: [path]{INSTALL_DIR}[/path]")
    console.print(f"  GRADLE_HOME will be set to: [path]{GRADLE_HOME}[/path]")
    console.print()

    if not Confirm.ask("Proceed with installation using these settings?", default=True, console=console):
        console.print("Installation aborted by user.", style="warning"); sys.exit(0)

    console.rule("[bold cyan]Gradle Installation[/bold cyan]")
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(INSTALL_DIR, exist_ok=True) 

    console.print(f"Downloading Gradle {GRADLE_VERSION} from [link={DOWNLOAD_URL}]{DOWNLOAD_URL}[/link]...", style="info")
    try:
        with requests.get(DOWNLOAD_URL, stream=True, timeout=(10, 300)) as r: 
            r.raise_for_status() 
            total_size = int(r.headers.get('content-length', 0))
            
            with Progress(
                "[progress.description]{task.description}", BarColumn(), DownloadColumn(), 
                TransferSpeedColumn(), "ETA:", TimeRemainingColumn(),
                console=console, transient=False 
            ) as progress:
                download_task = progress.add_task(f"Downloading {GRADLE_ZIP_NAME}", total=total_size)
                with open(GRADLE_ZIP_PATH, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192 * 4): 
                        if chunk: 
                            f.write(chunk)
                            progress.update(download_task, advance=len(chunk))
            if total_size > 0:
                 progress.update(download_task, completed=total_size, refresh=True) # Ensure 100%
        console.print("  [success]Download complete.[/success]")
    except requests.exceptions.Timeout:
        console.print(f"  [danger]Download failed: The request timed out connecting to or reading from {DOWNLOAD_URL}[/danger]")
        if os.path.exists(GRADLE_ZIP_PATH): os.remove(GRADLE_ZIP_PATH)
        sys.exit(1)
    except requests.RequestException as e:
        console.print(f"  [danger]Download failed: {e}[/danger]")
        if os.path.exists(GRADLE_ZIP_PATH): os.remove(GRADLE_ZIP_PATH)
        sys.exit(1)
    console.print()

    console.print(f"Extracting Gradle to [path]{INSTALL_DIR}[/path]...", style="info")
    if os.path.exists(GRADLE_HOME):
        console.print(f"  [warning]Target directory [path]{GRADLE_HOME}[/path] already exists.[/warning]")
        if Confirm.ask(f"Remove existing directory [path]{GRADLE_HOME}[/path] and perform a fresh extraction?", default=True, console=console):
            try:
                shutil.rmtree(GRADLE_HOME)
                console.print(f"  [success]Successfully removed existing target directory.[/success]")
            except OSError as e:
                console.print(f"  [danger]Error removing existing directory [path]{GRADLE_HOME}[/path]: {e}.[/danger]")
                console.print(f"  Please remove it manually and re-run the script. Or, ensure no files are in use.")
                sys.exit(1)
        else:
            console.print("  Extraction skipped as user chose not to overwrite existing directory.", style="info")
    
    if not os.path.exists(GRADLE_HOME): 
        try:
            with zipfile.ZipFile(GRADLE_ZIP_PATH, 'r') as zip_ref:
                zip_ref.extractall(INSTALL_DIR) 
            console.print("  [success]Extraction complete.[/success]")
            if not os.path.isdir(GRADLE_HOME):
                 console.print(f"  [danger]Post-extraction check failed: Expected directory [path]{GRADLE_HOME}[/path] not found.[/danger]")
                 extracted_items = os.listdir(INSTALL_DIR)
                 console.print(f"  [info]Contents of [path]{INSTALL_DIR}[/path] are: {extracted_items}[/info]")
                 console.print(f"  [info]The ZIP might have an unexpected top-level folder structure.[/info]")
                 sys.exit(1)
        except zipfile.BadZipFile:
            console.print(f"  [danger]Extraction failed: The downloaded file [path]{GRADLE_ZIP_PATH}[/path] is not a valid ZIP archive or is corrupted.[/danger]"); sys.exit(1)
        except Exception as e:
            console.print(f"  [danger]An unexpected error occurred during extraction: {e}[/danger]"); sys.exit(1)
    console.print()

    console.rule("[bold cyan]Environment Configuration (System-wide)[/bold cyan]")
    env_vars_changed = False
    if set_env_var_system("GRADLE_HOME", GRADLE_HOME): env_vars_changed = True
    if add_to_path_system(os.path.join(GRADLE_HOME, "bin")): env_vars_changed = True
    
    if env_vars_changed:
        broadcast_env_change()
        console.print("[highlight]System environment variables updated. For these changes to take full effect, a [bold]new Command Prompt must be opened[/bold], or in some cases, a system restart might be necessary.[/highlight]")
    else:
        console.print("No system environment variables needed changes (or changes failed).", style="info")
    console.print()

    console.rule("[bold cyan]User Experience Customizations[/bold cyan]")
    set_cmd_colors() 
    create_shortcut()  
    console.print()

    verification_passed = False
    console.rule("[bold cyan]Final Verification[/bold cyan]")
    if verify_gradle():
        verification_passed = True
    console.print()

    if verification_passed:
        console.rule("[bold cyan]Post-Install Operations[/bold cyan]")
        stop_gradle_daemons()
        cleanup_old_gradle_versions()
        console.print()
    else:
        console.print("[warning]Gradle verification failed or was skipped. Critical post-install steps (stopping daemons, cleaning old versions) will be skipped to prevent unintended actions.[/warning]")
        console.print("[warning]Please manually verify your Gradle installation and environment variables.[/warning]")
        console.print()

    console.rule("[bold cyan]Final Cleanup (Temporary Files)[/bold cyan]")
    console.print(f"Cleaning up temporary download file [path]{GRADLE_ZIP_PATH}[/path]...", style="info")
    try:
        if os.path.exists(GRADLE_ZIP_PATH):
            os.remove(GRADLE_ZIP_PATH)
            console.print(f"  [success]Removed temporary file: [path]{GRADLE_ZIP_PATH}[/path][/success]")
        else:
            console.print(f"  [info]Temporary file [path]{GRADLE_ZIP_PATH}[/path] not found, skipping removal.[/info]")
    except Exception as e:
        console.print(f"  [warning]Error during temporary file cleanup: {e}[/warning]")

    console.print()
    final_status_title = "[SUCCESS]" if verification_passed else "[WARNING]"
    final_status_style = "green" if verification_passed else "yellow"
    final_message_intro = "Gradle setup completed successfully!" if verification_passed else "Gradle setup completed with warnings/errors."

    console.print(Panel(
        f"[bold {final_status_style}]{final_message_intro}[/bold {final_status_style}]\n\n"
        f"Target Gradle Version: [variable]{GRADLE_VERSION}[/variable]\n"
        f"Installed to/GRADLE_HOME: [path]{GRADLE_HOME}[/path]\n\n"
        f"{'Verification: [success]Passed[/success]' if verification_passed else 'Verification: [danger]Failed or Skipped[/danger]'}\n"
        "System Environment Variables: Configured (GRADLE_HOME and PATH updated).\n"
        f"Desktop Shortcut: {'Created' if os.path.exists(os.path.join(winshell.desktop(), f'Gradle Command Prompt ({GRADLE_VERSION}).lnk')) else 'Not created or failed'}.\n"
        "Default CMD Colors: Updated in registry.\n\n"
        "[bold]Important Next Steps:[/bold]\n"
        "  1. [highlight]Open a NEW Command Prompt window[/highlight] or use the created Desktop Shortcut to ensure all environment changes are active.\n"
        "  2. In the new terminal, type `[yellow]gradle --version[/yellow]` to confirm the installation.\n"
        f"{'' if verification_passed else '  3. [warning]Since verification failed, please double-check your Java installation and PATH settings.[/warning]'}\n\n"
        "Thank you for using the Gradle Setup Utility!\n\nBy Germanized",
        title=final_status_title, style=final_status_style, highlight=True
    ))

    if getattr(sys, 'frozen', False): Prompt.ask("Press Enter to exit script.", console=console)
    else: input("Press Enter to exit script.")


if __name__ == "__main__":
    # This is the outer try/except/finally that wraps the whole script execution.
    try:
        if 'console' in globals() and console is not None:
            console.show_cursor(True) # Ensure cursor is initially visible
        main()
    except SystemExit: 
        # This allows sys.exit() to terminate the script cleanly.
        # The finally block will still execute to restore the cursor.
        pass
    except ImportError: 
        # This is a fallback for ImportErrors not caught by the very first check,
        # or if `console` object itself failed to initialize properly for the messages.
        print("FATAL: A critical library is missing. The script cannot continue.")
        print("Please ensure 'rich', 'requests', 'winshell', and 'pywin32' are installed.")
        print("Run: pip install rich requests winshell pywin32")
        if not getattr(sys, 'frozen', False): input("Press Enter to exit.")
    except Exception as e:
        # General exception handler for any other unexpected errors during main execution.
        if 'console' in globals() and console is not None:
            console.print_exception(show_locals=True, width=120)
            console.print("[danger]An unexpected error occurred. Please review the output above for details.[/danger]")
            if getattr(sys, 'frozen', False): Prompt.ask("Press Enter to exit due to error.", console=console)
            else: input("Press Enter to exit due to error.")
        else: 
            # Fallback if 'console' object itself is problematic or not defined.
            print("AN UNEXPECTED CRITICAL ERROR OCCURRED (console object unavailable):")
            import traceback
            traceback.print_exc()
            if not getattr(sys, 'frozen', False): input("Press Enter to exit due to error.")
    finally:
        # This block will execute whether an exception occurred or not.
        # Ensure cursor is visible when script exits, regardless of how.
        if 'console' in globals() and console is not None:
            try:
                console.show_cursor(True)
            except Exception: 
                # Silently ignore if console operations fail at this critical exit stage.
                pass