import argparse
import pathlib
import signal
import sys
import os
import threading
import tkinter as tk
from tkinter.filedialog import asksaveasfilename
from tkinter import messagebox
import subprocess
import asyncio
import traceback

import pystray
from PIL import Image
import openvr
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher

from config import CONFIG_DIR, Config
from websocket_interface import WebSocketInterface

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
	SCRIPT_DIR = os.path.dirname(__file__)
	IS_FROZEN = False

# this has to happen after we setup the stdout and stderr redirection
global_config = Config()
async_main_loop: asyncio.AbstractEventLoop = None

websocket_interface: WebSocketInterface = None
osc_transport = None

main_thread_exited = threading.Event()

global_state = {
	"all_commands": []
}

trayicon = None

def relpath(p):
	return os.path.normpath(os.path.join(SCRIPT_DIR, p))

def show_error(message, title="Error"):
	root = tk.Tk()
	root.withdraw()
	messagebox.showerror(title, message)
	root.destroy()

def exit_program():
	if async_main_loop is not None:
		asyncio.run_coroutine_threadsafe(exit_async(), async_main_loop)

	# wait until the main thread has exited
	main_thread_exited.wait()

	trayicon.stop()

def open_config_dir():
	subprocess.Popen(f'explorer "{os.path.dirname(global_config._config_path)}"')

def write_all_commands_to_file():
	root = tk.Tk()
	root.withdraw()
	filename = asksaveasfilename(
		filetypes=[("Text file", "*.txt")],
		defaultextension=".txt",
		title="Write all commands to file",
		initialfile="all_commands.txt",
	)
	root.destroy()

	if filename == "":
		return
	
	try:
		with open(filename, "w") as f:
			for command in global_state["all_commands"]:
				f.write(command["command"] + "\n")
	except Exception as e:
		show_error(f"Failed to write commands to file: {repr(e)}")

def generate_menu():
	# yield pystray.MenuItem("Register with SteamVR", action=open_config_dir)
	yield pystray.MenuItem("Open config directory", action=open_config_dir)
	yield pystray.MenuItem("Write all commands to file", action=write_all_commands_to_file)
	yield pystray.MenuItem("Exit", action=exit_program)

traymenu = pystray.Menu(generate_menu)

trayimage_icon = Image.open(relpath("../assets/drink_tracker_icon_256.png"))

trayicon = pystray.Icon("steamvr_osc_ctrl", title="SteamVR OSC Control", menu=traymenu)
trayicon.icon = trayimage_icon

def print_async_exceptions(f):
	async def wrapper(*args, **kwargs):
		try:
			await f(*args, **kwargs)
		except:
			traceback.print_exc()
	return wrapper

@print_async_exceptions
async def osc_message_handler(command_mailboxes: dict[str, str], address: str, *osc_args):
	command_mapping = global_config.get(["command_mapping"])

	if command_mapping is None:
		return

	if address in command_mapping:
		command = command_mapping[address]

		if command in command_mailboxes:
			await websocket_interface.send_request(command_mailboxes[command], message_type=command)

async def exit_async():
	if websocket_interface is not None:
		await websocket_interface.stop()
	if osc_transport is not None:
		osc_transport.close()

async def async_main():
	global websocket_interface
	global osc_transport

	websocket_interface = WebSocketInterface()

	ws_running = asyncio.create_task(websocket_interface.run_forever())

	await websocket_interface.connected_event.wait()

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

	osc_server = AsyncIOOSCUDPServer(
		(global_config.get(["osc", "listen_address"]), global_config.get(["osc", "listen_port"])),
		osc_dispatcher,
		async_main_loop
	)

	osc_transport, _ = await osc_server.create_serve_endpoint()

	await ws_running

# main thread after pystray has spawned the tray icon
def main(icon):
	global async_main_loop

	icon.visible = True

	encountered_error = False

	# setup openvr and feeder
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

	async_main_loop = asyncio.new_event_loop()
	async_main_loop.run_until_complete(async_main())

	print("Async main loop exited")

	openvr.shutdown()

	print("OpenVR shut down")

	main_thread_exited.set()

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL)

	trayicon.run(setup=main)
