# Gradle Windows Installer Script

A Python script to simplify the installation and setup of the latest official Gradle distribution on Windows systems. This utility automates downloading, extracting, setting environment variables, and creating helpful shortcuts.

![Gradle Logo Art](https://i.imgur.com/oFEwvzq.png) 

## Features

-   **Fetches Latest Version**: Automatically queries Gradle's services to find and download the latest stable release.
-   **Admin Rights Check**: Detects if running without administrator privileges and prompts to re-run as admin (required for system-wide changes).
-   **Java JDK Check**: Verifies if Java is installed and accessible, as Gradle requires a JDK.
-   **Automated Download & Extraction**: Downloads the official Gradle binary ZIP and extracts it to a configurable location (default: `C:\Gradle`).
-   **Environment Variable Setup**:
    -   Sets the `GRADLE_HOME` system environment variable.
    -   Adds Gradle's `bin` directory to the system `PATH`.
    -   Broadcasts environment changes to active processes.
-   **Custom CMD Prompt**:
    -   Configures default CMD color scheme in the registry for a more modern look (optional).
    -   Creates a "Gradle Command Prompt" shortcut on the Desktop, pre-configured with the correct `GRADLE_HOME` and PATH, and which displays the Gradle version on launch.
-   **Installation Verification**: Runs `gradle --version` to confirm the installation was successful.
-   **Gradle Daemon Management**: Attempts to stop any running Gradle daemons after a successful installation.
-   **Cleanup**:
    -   Removes old Gradle versions from the installation directory (configurable).
    -   Deletes temporary downloaded files.
-   **User-Friendly CLI**: Uses the `rich` library for a visually appealing and interactive command-line interface with progress bars, prompts, and styled output.

## Prerequisites

1.  **Windows Operating System**: This script is designed for Windows.
2.  **Python**: Python 3.6+ is recommended. Ensure Python is added to your system's PATH.
3.  **PIP**: Python's package installer, usually comes with Python.
4.  **Required Python Libraries**:
    -   `rich`: For the rich CLI experience.
    -   `requests`: For downloading Gradle.
    -   `winshell`: For creating shortcuts.
    -   `pywin32`: For interacting with Windows APIs (admin check, environment variables, registry).

    The script will check for these and instruct you to install them if missing. You can pre-install them via:
    ```bash
    pip install rich requests winshell pywin32
    ```
5.  **Java Development Kit (JDK)**: Gradle requires a JDK (version 8 or higher). The script will check for it, but you should install it beforehand. Recommended: [Adoptium Temurin](https://adoptium.net/).

## Usage

1.  **Download the Script**:
    -   Save the script content as a `.py` file (e.g., `gradle_installer.py`).
2.  **Run the Script**:
    -   Open a Command Prompt or PowerShell.
    -   Navigate to the directory where you saved the script.
    -   Execute the script:
        ```bash
        python gradle_installer.py
        ```
    -   If not run as administrator, the script will detect this and offer to restart itself with admin privileges. Approve the UAC prompt.
3.  **Follow Prompts**: The script will guide you through the installation process.

    ![Screenshot of Installer UI](https://i.imgur.com/JbznCBM.png)
    *(Consider adding a screenshot of your script in action here if you have one)*

## Script Overview

The script performs the following main steps:

1.  **Initialization**: Imports necessary libraries, defines global variables, and sets up the Rich console.
2.  **Admin Check**: Ensures the script is running with administrator privileges. If not, it attempts to re-launch itself with elevation.
3.  **Fetch Gradle Version**: Connects to `services.gradle.org` to get the latest Gradle version string.
4.  **System Checks**:
    -   Checks for a valid Java installation.
5.  **Configuration**: Displays installation paths and settings, and asks for user confirmation.
6.  **Download**: Downloads the Gradle binary `.zip` file with a progress bar.
7.  **Extraction**: Extracts the downloaded archive to the specified installation directory (e.g., `C:\Gradle\gradle-X.Y`). Handles existing installations by prompting for removal.
8.  **Environment Setup**:
    -   Sets `GRADLE_HOME` system-wide.
    -   Appends `GRADLE_HOME\bin` to the system `PATH`.
    -   Sends a `WM_SETTINGCHANGE` message to notify other applications of the environment update.
9.  **Customizations**:
    -   Modifies `HKEY_CURRENT_USER\Console` registry keys to set a default color scheme for new CMD prompts.
    -   Creates a `.lnk` shortcut on the user's Desktop that opens a CMD prompt with Gradle environment initialized.
10. **Verification**: Runs `gradle --no-daemon --version` using the newly configured `GRADLE_HOME` to confirm correct installation.
11. **Post-Install**:
    -   Attempts to run `gradle --stop` to terminate any running Gradle daemons.
    -   Scans the `C:\Gradle` (or custom install root) directory and removes older `gradle-X.Y` folders.
12. **Cleanup**: Deletes the downloaded `.zip` file from the temporary directory.
13. **Summary**: Displays a final status panel.

## Default Paths

-   **Temporary Download Directory**: `%TEMP%\gradle_installer_py` (e.g., `C:\Users\<YourUser>\AppData\Local\Temp\gradle_installer_py`)
-   **Gradle Installation Root**: `C:\Gradle`
-   **GRADLE_HOME Example**: `C:\Gradle\gradle-8.14` (version number will vary)

These can be modified within the script's global variables if needed.

## Customization

If you wish to change default behaviors (like the installation directory):

-   Modify the global variables at the beginning of the script:
    -   `TEMP_DIR`: For where the Gradle ZIP is temporarily stored.
    -   `INSTALL_DIR`: The root directory for Gradle installations (e.g., `C:\Gradle`).
    -   `GRADLE_HOME_DIR_NAME_FORMAT`: Not explicitly defined, but `GRADLE_HOME_DIR_NAME` is derived like `f"gradle-{GRADLE_VERSION}"`.

## Troubleshooting

-   **Admin Privileges**: The most common issue is not running the script as an administrator. The script attempts to handle this, but if automatic relaunch fails, right-click the `.py` file and select "Run as administrator" (if your Python file associations are set up) or run `python gradle_installer.py` from an already elevated command prompt.
-   **Python Libraries Not Found**: Ensure you've run `pip install rich requests winshell pywin32`.
-   **Firewall/Antivirus**: If downloads fail, your firewall or antivirus might be blocking `requests` or access to `services.gradle.org`.
-   **Path Length Limitations**: Windows has a MAX_PATH limit (traditionally 260 characters). While less common with modern Windows versions if long path support is enabled, be mindful if choosing very deep installation paths. `C:\Gradle` is short and generally safe.
-   **Environment Variable Changes Not Taking Effect**: After the script runs, you *must* open a new Command Prompt window for the environment variable changes (`GRADLE_HOME`, `PATH`) to be reflected. Existing CMD windows will not pick up the changes. Sometimes, a full system restart is required for all applications to recognize the new system variables.

## Disclaimer

This script modifies system environment variables and the registry. While tested, use it at your own risk. Always understand what a script does before running it, especially one requiring administrator privileges.

## Contributing

Feel free to fork this repository, make improvements, and submit pull requests. Suggestions are welcome!

## License

This project is open-source and available under the [MIT License](LICENSE.md). (You would need to add a `LICENSE.md` file with the MIT License text if you want this).
