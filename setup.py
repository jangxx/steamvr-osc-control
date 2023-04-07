import sys
import os
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
	"packages": [ "pystray" ],
	"excludes": [ ],
	"include_files": [
		# ("./assets/drink_tracker_icon_256.png", "assets/drink_tracker_icon_256.png"),
		# ("./assets/icon_green.png", "assets/icon_green.png"),
		# ("./assets/icon_red.png", "assets/icon_red.png"),
		# ("./assets/hold_clip_1.wav", "assets/hold_clip_1.wav"),
		# ("./assets/hold_clip_2.wav", "assets/hold_clip_2.wav"),
		# ("./assets/hold_clip_3.wav", "assets/hold_clip_3.wav"),
		# ("./assets/hold_clip_4.wav", "assets/hold_clip_4.wav"),
		# ("./assets/hold_clip_5.wav", "assets/hold_clip_5.wav"),
		# ("./assets/hold_clip_6.wav", "assets/hold_clip_6.wav"),
		# ("./assets/error_clip.wav", "assets/error_clip.wav"),
	],
	"zip_include_packages": "*",
	"zip_exclude_packages": [ "pystray", "openvr" ],
	"build_exe": "./dist/feeder",
}

# GUI applications require a different base on Windows (the default is for a console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "src"))

setup(name = "steamvr_osc_control",
	# version = get_version_string(),
    description = "SteamVR OSC Control",
    options = { "build_exe": build_exe_options },
    executables = [
		Executable("src/main.py", base=base, target_name="steamvr_osc_control", icon = "./assets/drink_tracker_icon.ico"),
	],
)