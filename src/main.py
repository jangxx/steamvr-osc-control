import argparse
import pathlib
import signal
import sys
import os
import threading
import time
import subprocess
import asyncio
import traceback
import configparser

import pystray
from PIL import Image
import openvr
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import win32gui
import win32con

from config import CONFIG_DIR, Config
from websocket_interface import WebSocketInterface

APPLICATION_KEY = "com.jangxx.steamvr-osc-control"

parser = argparse.ArgumentParser(description="Controls SteamVR using OSC messages")
parser.add_argument("--stdout", action="store_true", help="Log to stdout and stderr instead of redirecting all output to the log file", dest="use_stdout")

args = parser.parse_args()

# create config dir if it doesn't exist
pathlib.Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)

if not args.use_stdout:
	log_file_path = os.path.join(CONFIG_DIR, "output.log")
	log_file = open(log_file_path, "a", buffering=1)
	sys.stdout = log_file
	sys.stderr = log_file

# determine if we are frozen with cx_freeze or running normally
if getattr(sys, 'frozen', False):
	# The application is frozen
	SCRIPT_DIR = os.path.dirname(sys.executable)
	IS_FROZEN = True
else:
	# The application is not frozen
	SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "../")
	IS_FROZEN = False

# this has to happen after we setup the stdout and stderr redirection
global_config = Config()
async_main_loop: asyncio.AbstractEventLoop = None

websocket_interface: WebSocketInterface = None
osc_transport = None

main_thread_exited = threading.Event()
openvr_event_thread: threading.Thread = None
exit_openvr_event_thread = threading.Event()

global_state = {
	"all_commands": [],
	"reloading_config": False,
	"openvr_initialized": False,
}

SPECIAL_COMMANDS = {
}

trayicon = None

def relpath(p):
	return os.path.normpath(os.path.join(SCRIPT_DIR, p))

def show_error(message, title="Error"):
	def _show():
		win32gui.MessageBox(None, message, title, win32con.MB_ICONERROR)

	threading.Thread(target=_show).start()

def show_message(message, title="Info"):
	def _show():
		win32gui.MessageBox(None, message, title, win32con.MB_ICONINFORMATION)

	threading.Thread(target=_show).start()


def exit_program():
	if async_main_loop is not None:
		asyncio.run_coroutine_threadsafe(exit_async(), async_main_loop)

	# wait until the main thread has exited
	main_thread_exited.wait()

	trayicon.stop()

def reload_config():
	global_state["reloading_config"] = True

	global_config.reload()

	if async_main_loop is not None:
		asyncio.run_coroutine_threadsafe(exit_async(), async_main_loop)

def install_manifest():
	if not IS_FROZEN:
		show_error("Manifest can only be installed when the application is built")
		return

	try:
		openvr.VRApplications().addApplicationManifest(relpath("./manifest.vrmanifest"), False)

		show_message("Successfully registered with SteamVR", "Success")
	except Exception as e:
		show_error(f"Failed to install manifest: {e}")
		traceback.print_exc()

def uninstall_manifest():
	try:
		manifest_working_dir = openvr.VRApplications().getApplicationPropertyString(APPLICATION_KEY, openvr.VRApplicationProperty_WorkingDirectory_String)
		manifest_path = os.path.normpath(os.path.join(manifest_working_dir, "./manifest.vrmanifest"))

		openvr.VRApplications().removeApplicationManifest(manifest_path)

		show_message("Successfully unregistered from SteamVR", "Success")
	except Exception as e:
		show_error(f"Failed to uninstall manifest: {e}")
		traceback.print_exc()

def openvr_event_thread_fn():
	event = openvr.VREvent_t()

	while not exit_openvr_event_thread.is_set():
		if openvr.VRSystem().pollNextEvent(event):
			event_type = event.eventType

			if event_type == openvr.VREvent_Quit:
				exit_program()
				break

		time.sleep(0.1)

def open_config_dir():
	subprocess.Popen(f'explorer "{os.path.dirname(global_config._config_path)}"')

def load_mapping_from_file():
	try:
		filename, _, _ = win32gui.GetOpenFileNameW(
			Filter="Command mapping file (*.txt)\0*.txt\0",
			Title="Load command mapping from file",
			DefExt=".txt",
			Flags=win32con.OFN_NOCHANGEDIR
		)
	except:
		return

	try:
		cp = configparser.RawConfigParser()
		cp.optionxform = str # make option names case sensitive

		cp.read(filename)

		if not "mapping" in cp:
			raise Exception("Command file does not contain a [mapping] section")

		new_command_mapping = {}

		for param_name, command in cp["mapping"].items():
			if " " in param_name:
				raise Exception(f"Parameter '{param_name}' contains spaces")
			
			new_command_mapping[f"/avatar/parameters/{param_name}"] = command

		print(f"Loading new command mapping: {new_command_mapping}")

		command_mapping = global_config.get(["command_mapping"])
		if command_mapping is None:
			command_mapping = {}

		command_mapping.update(new_command_mapping)

		global_config.set(["command_mapping"], command_mapping)

		show_message(f"Successfully loaded {len(new_command_mapping)} commands from file", "Success")
	except Exception as e:
		show_error(f"Failed to load command mapping from file: {e}")
		traceback.print_exc()

def generate_menu():
	if global_state["openvr_initialized"]:
		if openvr.VRApplications().isApplicationInstalled(APPLICATION_KEY):
			yield pystray.MenuItem("Unregister from SteamVR", action=uninstall_manifest)
		else:
			yield pystray.MenuItem("Register with SteamVR", action=install_manifest)
	
	yield pystray.Menu.SEPARATOR
	yield pystray.MenuItem("Open config directory", action=open_config_dir)
	yield pystray.MenuItem("Reload config", action=reload_config)
	yield pystray.MenuItem("Load command mapping from file", action=load_mapping_from_file)
	yield pystray.Menu.SEPARATOR
	yield pystray.MenuItem("Exit", action=exit_program)

traymenu = pystray.Menu(generate_menu)

trayimage_icon = Image.open(relpath("./assets/icon_32.png"))
trayimage_icon_disabled = Image.open(relpath("./assets/icon_disabled_32.png"))

trayicon = pystray.Icon("steamvr_osc_ctrl", title="SteamVR OSC Control", menu=traymenu)
trayicon.icon = trayimage_icon_disabled

# decorator for async functions that prints any exceptions that occur
def print_async_exceptions(f):
	async def wrapper(*args, **kwargs):
		try:
			return await f(*args, **kwargs)
		except:
			traceback.print_exc()
	return wrapper

@print_async_exceptions
async def osc_message_handler(command_mailboxes: dict[str, str], address: str, *osc_args):
	command_mapping = global_config.get(["command_mapping"])

	if command_mapping is None:
		return
	
	if len(osc_args) != 1 or osc_args[0] != True:
		return

	if address in command_mapping:
		command = command_mapping[address]

		if command in SPECIAL_COMMANDS:
			await websocket_interface.send_request(**SPECIAL_COMMANDS[command])
		elif command in command_mailboxes:
			await websocket_interface.send_request(command_mailboxes[command], message_type=command)

async def exit_async():
	if websocket_interface is not None:
		await websocket_interface.stop()
	if osc_transport is not None:
		osc_transport.close()

async def async_main():
	global websocket_interface
	global osc_transport

	trayicon.icon = trayimage_icon_disabled

	global_state["reloading_config"] = False

	websocket_interface = WebSocketInterface()
	ws_running = asyncio.create_task(websocket_interface.run_forever())
	await websocket_interface.connected_event.wait()

	print("Connected to SteamVR websocket")

	all_commands = []

	vrcompositor_commands = await websocket_interface.send_request("vrcompositor_mailbox", message_type="get_debug_commands", expect_response=True)
	all_commands.extend(vrcompositor_commands["commands"])

	vrcompositor_commands = await websocket_interface.send_request("vrcompositor_systemlayer", message_type="get_debug_commands", expect_response=True)
	all_commands.extend(vrcompositor_commands["commands"])

	global_state["all_commands"] = all_commands
	command_mailboxes = { cmd["command"]: cmd["mailbox"] for cmd in all_commands }

	print(f"Got {len(all_commands)} commands")

	osc_dispatcher = Dispatcher()
	osc_dispatcher.set_default_handler(lambda address, *osc_args: 
				    asyncio.run_coroutine_threadsafe(osc_message_handler(command_mailboxes, address, *osc_args), asyncio.get_event_loop()))

	address_tuple = (global_config.get(["osc", "listen_address"]), global_config.get(["osc", "listen_port"]))
	osc_server = AsyncIOOSCUDPServer(address_tuple, osc_dispatcher, async_main_loop)
	osc_transport, _ = await osc_server.create_serve_endpoint()
	print(f"OSC server listening on {address_tuple}")

	trayicon.icon = trayimage_icon

	await ws_running

	if global_state["reloading_config"]:
		show_message("Reloaded config")
		return await async_main()

# main thread after pystray has spawned the tray icon
def main(icon):
	global async_main_loop

	icon.visible = True

	encountered_error = False

	# connect to openvr
	try:
		global_config.save()

		openvr.init(openvr.VRApplication_Background)
	except openvr.error_code.InitError_Init_NoServerForBackgroundApp:
		show_error("SteamVR is not running", "SteamVR Error")
		encountered_error = True
	except Exception as e:
		show_error(f"Encountered unexpected error during initialization: {repr(e)}", "SteamVR Error")
		encountered_error = True

	if encountered_error:
		trayicon.stop()
		return

	openvr_event_thread = threading.Thread(target=openvr_event_thread_fn, daemon=True)
	openvr_event_thread.start()

	global_state["openvr_initialized"] = True
	trayicon.update_menu()
	print("OpenVR initialized")

	async_main_loop = asyncio.new_event_loop()

	# run async main in the same thread
	try:
		async_main_loop.run_until_complete(async_main())
	except Exception as e:
		show_error(f"Encountered unexpected error: {e}", "Error")
		traceback.print_exc()
		encountered_error = True

	print("Async main loop exited")

	exit_openvr_event_thread.set()

	openvr.shutdown()

	global_state["openvr_initialized"] = False
	print("OpenVR shut down")

	main_thread_exited.set()

	if encountered_error:
		trayicon.stop()

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL)

	trayicon.run(setup=main)
