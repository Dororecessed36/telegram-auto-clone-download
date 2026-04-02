import os
import asyncio
import time
import shutil
import gc
from telethon import TelegramClient, events, errors

# --- CONFIGURATION (NO CHANGES TO YOUR INFO) ---
API_ID = 00000 #--- GET FROM TELEGRAM API
API_HASH = "" #--- GET FROM TELEGRAM API
SOURCE_IDS = [-10000000000, -10000000000] #--- ADDITIONAL SOURCE CAN BE ADDED. GET ID FROM TELEGRAM WEB URL EG: (https://web.telegram.org/a/#-100XXXXXXXX) -100XXXXXXXX 
DEST_ID = -10000000000 #--- DESTINATION ID TO GET FROM TELEGRAM WEB AS ABOVE METHOD

MAX_FILE_SIZE = 500 * 1024 * 1024 #--- MAX FILE SIZE 500MB, CAN BE CHANGE DEPENDING ON REQUIREMENT
FINAL_STORAGE = r"C:\Telegram" #--- LOCAL DRIVE EG: "C:\Telegram"
TEMP_BUFFER = os.path.join(FINAL_STORAGE, "temp_buffer")

os.makedirs(FINAL_STORAGE, exist_ok=True)
os.makedirs(TEMP_BUFFER, exist_ok=True)

channel_map = {}

def progress_bar(current, total, action="Processing"):
    percentage = 100 * (current / total)
    print(f"   {action}: [{percentage:.1f}%] ({current // 1024} / {total // 1024} KB)", end="\r")
    if current == total:
        print() 

async def maintenance_loop(client):
    while True:
        await asyncio.sleep(86400) 
        try:
            print(f"\n[{time.strftime('%H:%M:%S')}] 🧹 RUNNING MAINTENANCE...")
            client._entity_cache.clear()
            gc.collect()
            if os.path.exists(TEMP_BUFFER):
                for f in os.listdir(TEMP_BUFFER):
                    try: os.remove(os.path.join(TEMP_BUFFER, f))
                    except: pass
            print(" ✅ Memory Optimized.")
        except: pass

async def run_client():
    """Main execution logic with automatic reconnection"""
    # connection_retries=None means it will keep trying to reconnect forever
    client = TelegramClient('pc_mirror_resilient', API_ID, API_HASH, 
                            connection_retries=None, 
                            retry_delay=5)
    
    print("Connecting to Telegram...")
    await client.start() # Handles connect and auth check automatically

    # Start maintenance in background
    asyncio.create_task(maintenance_loop(client))

    print("\n" + "="*60)
    print("   STEP 1: CHANNEL VERIFICATION")
    print("="*60)
    
    async for dialog in client.iter_dialogs():
        if dialog.id in SOURCE_IDS:
            channel_map[dialog.id] = dialog.title
            print(f" [SOURCE] ID: {dialog.id} | NAME: {dialog.title}")
        if dialog.id == DEST_ID:
            channel_map[dialog.id] = dialog.title
            print(f" [DEST]   ID: {dialog.id} | NAME: {dialog.title}")

    print("\n" + "="*60)
    print("   STEP 2: MONITORING ENGINE ACTIVE")
    print("="*60)

    @client.on(events.NewMessage(chats=SOURCE_IDS))
    async def mirror_handler(event):
        src_name = channel_map.get(event.chat_id, f"Channel({event.chat_id})")
        try:
            if event.message.media:
                file_size = event.message.file.size if event.message.file else 0
                if file_size > MAX_FILE_SIZE:
                    print(f"\n[{time.strftime('%H:%M:%S')}] SKIP: '{src_name}' file too large.")
                    return 
                
                print(f"\n[{time.strftime('%H:%M:%S')}] DETECTED: New media in '{src_name}'")
                
                # [1/2] DOWNLOAD
                path = await client.download_media(
                    event.message, 
                    file=TEMP_BUFFER,
                    progress_callback=lambda c, t: progress_bar(c, t, "   [1/2] Downloading")
                )
                
                # [2/2] UPLOAD
                # Wrap upload in a small retry loop specifically for [WinError 121]
                for attempt in range(3):
                    try:
                        await client.send_file(
                            DEST_ID, 
                            path, 
                            caption=event.message.message or "",
                            progress_callback=lambda c, t: progress_bar(c, t, "   [2/2] Uploading")
                        )
                        break # Success!
                    except Exception as upload_err:
                        if "121" in str(upload_err) and attempt < 2:
                            print(f"\n [!] Semaphore Timeout. Retrying upload ({attempt+1}/3)...")
                            await asyncio.sleep(10)
                        else:
                            raise upload_err
                
                # MOVE TO FINAL
                final_filename = os.path.basename(path)
                final_path = os.path.join(FINAL_STORAGE, final_filename)
                shutil.move(path, final_path)
                print(f" ✅ SUCCESS: {final_filename} saved to D: Drive.")
                
            else:
                await client.send_message(DEST_ID, event.message.message)
                print(f" ✅ TEXT CLONE SUCCESS: {src_name}")

        except Exception as e:
            print(f" !! Mirroring Error: {e}")

    # Keep running until disconnected
    await client.run_until_disconnected()

async def main():
    while True:
        try:
            await run_client()
        except (errors.CdnError, errors.ConnectionError, errors.TimeoutError) as e:
            print(f"\n[!] Network Error: {e}. Reconnecting in 10 seconds...")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"\n[!] Unexpected Crash: {e}. Restarting engine...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping...")
