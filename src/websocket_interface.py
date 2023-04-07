import json
import time
import asyncio
import traceback

import websockets

class WebSocketInterface:
	def __init__(self):
		self._ws = None
		self._connected_since = None

		self._message_id = 1
		self._channel_name = f"osc_control_{round(time.time())}"
		self._close_event = asyncio.Event()

		self._open_requests: dict[int, asyncio.Future] = {}

		self._connected_event = asyncio.Event()

	@property
	def connected_event(self):
		return self._connected_event

	def _on_message(self, message_raw):
		try:
			message = json.loads(message_raw)
		except:
			print("Couldn't parse message: " + message_raw)
			return
		
		if "message_id" not in message: # we only do request-response this time around
			return
		
		if message["message_id"] not in self._open_requests:
			return
		
		self._open_requests[message["message_id"]].set_result(message)
		del self._open_requests[message["message_id"]]

	async def send_request(self, mailbox, message_type, data = {}, expect_response = False):
		if not self.is_connected():
			raise Exception("Not connected")

		message = {
			"type": message_type,
			**data,
		}

		if expect_response:
			message_id = self._message_id
			self._message_id += 1

			message["message_id"] = message_id
			message["returnAddress"] = self._channel_name

			self._open_requests[message_id] = asyncio.Future()
		
		print(f"mailbox_send {mailbox} {json.dumps(message)}")

		await self._ws.send(f"mailbox_send {mailbox} {json.dumps(message)}")

		if expect_response:
			return await self._open_requests[message_id]

	def is_connected(self):
		return self._connected_since is not None

	def connected_since(self):
		return self._connected_since

	async def _connect(self):
		for open_request in self._open_requests.values():
			open_request.cancel("Reconnected")
		self._open_requests = {}

		self._channel_name = f"osc_control_{round(time.time())}"

		await self._ws.send(f"mailbox_open {self._channel_name}")

		self._connected_since = time.monotonic()

		self._connected_event.set()
		self._connected_event = asyncio.Event()

	async def stop(self):
		if self._ws is not None:
			self._close_event.set()
			print("Trying to close websocket connection...")
			await self._ws.close()
			print("Closed websocket connection")

	async def _run(self):
		async for message in self._ws:
			self._on_message(message)

	async def run_forever(self):
		async for websocket in websockets.connect("ws://localhost:27062/", compression=None, origin="http://localhost:27062"):
			self._ws = websocket

			await self._connect()

			try:
				await self._run()
			except websockets.ConnectionClosed:
				continue
			except:
				traceback.print_exc()
				continue

			self._connected_since = None

			if self._close_event.is_set():
				break
		