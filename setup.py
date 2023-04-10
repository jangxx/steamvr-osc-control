import sys
import os
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
	"packages": [ "pystray", "websockets" ],
	"excludes": [ ],
	"include_files": [
		("./assets/icon_32.png", "assets/icon_32.png"),
		("./assets/icon_disabled_32.png", "assets/icon_disabled_32.png"),
        ("./manifest.vrmanifest", "manifest.vrmanifest"),
	],
	"zip_include_packages": "*",
	"zip_exclude_packages": [ "pystray", "openvr" ],
	"build_exe": "./dist/steam_osc_control",
}

# GUI applications require a different base on Windows (the default is for a console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "src"))

setup(name = "steamvr_osc_control",
	# version = get_version_string(),
    description = "SteamVR OSC Control",
    options = { "build_exe": build_exe_options },
    executables = [
		Executable("src/main.py", base=base, target_name="steamvr_osc_control", icon = "./assets/icon.ico"),
	],
)