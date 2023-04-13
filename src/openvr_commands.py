import os
import traceback
from datetime import datetime
import pathlib

from win32com.shell import shell, shellcon
import openvr
from win10toast import ToastNotifier

from config import Config
from utilities import relpath

toast = ToastNotifier()

def get_pictures_dir():
	return shell.SHGetFolderPath(0, shellcon.CSIDL_MYPICTURES, None, 0)

def take_openvr_screenshot(config: Config, *args):
	shreenshot_path = config.get(["screenshots", "save_path"])

	if config.get(["screenshots", "relative_to_pictures"]):
		shreenshot_path = os.path.join(get_pictures_dir(), shreenshot_path)

	# exception will be caught by the caller
	pathlib.Path(shreenshot_path).mkdir(parents=True, exist_ok=True)

	sceneApplicationState = openvr.VRApplications().getSceneApplicationState()

	if sceneApplicationState != openvr.EVRSceneApplicationState_Running and \
			sceneApplicationState != openvr.EVRSceneApplicationState_Waiting:
		return

	datestr = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

	openvr.VRScreenshots().requestScreenshot(
		openvr.VRScreenshotType_Stereo,
		os.path.join(shreenshot_path, datestr),
		os.path.join(shreenshot_path, datestr + "-stereo"),
	)

	toast.show_toast(
		"SteamVR OSC Control",
		f"Screenshot taken and saved to {os.path.join(shreenshot_path, datestr)}.png",
		icon_path=relpath("./assets/icon.ico"),
		threaded=True,
	)