import asyncio
import websockets

async def main():
    async with websockets.connect("wss://ws.postman-echo.com/raw") as websocket:
        await websocket.send("Hello world!")

        greeting = await websocket.recv()
        print(f"< {greeting}")

asyncio.new_event_loop().run_until_complete(main())