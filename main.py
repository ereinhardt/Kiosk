import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from pynput import keyboard, mouse
import signal
import time
from AppKit import NSScreen

def get_running_apps():
    script = 'tell application "System Events" to get name of (processes where background only is false)'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip().split(", ")

def get_screen_resolutions():
    command = ["system_profiler", "SPDisplaysDataType"]
    result = subprocess.run(command, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    resolutions = []
    for line in lines:
        if "Resolution:" in line:
            resolutions.append(line.strip())
    return resolutions

def get_scale_factor():
    screen = NSScreen.mainScreen()
    if screen:
        return screen.backingScaleFactor()
    return 1  # Default to 1 if no screen is detected

def enable_kiosk_mode():
    subprocess.run(["defaults", "write", "com.apple.dock", "autohide", "-bool", "true"])
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-tl-corner", "-int", "0"])
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-tr-corner", "-int", "0"])
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-bl-corner", "-int", "0"])
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-br-corner", "-int", "0"])
    subprocess.run(["killall", "Dock"])

def disable_kiosk_mode():
    subprocess.run(["defaults", "write", "com.apple.dock", "autohide", "-bool", "false"])
    subprocess.run(["killall", "Dock"])

def is_app_running(app_name):
    return app_name in get_running_apps()

def focus_app(app_name, stop_event):
    while not stop_event.is_set():
        try:
            if not is_app_running(app_name):
                print(f"{app_name} is not running. Attempting to relaunch...")
                subprocess.run(["open", "-a", app_name])
                time.sleep(2)  # Shortened wait time for app to start

            focus_script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    set frontmost to true
                    repeat while not frontmost
                        delay 0.1  # Reduced delay to make the check quicker
                        set frontmost to true
                    end repeat
                end tell
            end tell
            tell application "{app_name}" to activate
            tell application "System Events"
                tell process "{app_name}"
                    if exists (window 1) then
                        set value of attribute "AXFullScreen" of window 1 to true
                    end if
                end tell
            end tell
            '''
            subprocess.run(["osascript", "-e", focus_script])
        except Exception as e:
            print(f"Error focusing {app_name}: {str(e)}")
        stop_event.wait(1)  # Keeping this to avoid a tight loop

def track_mouse(label, percent_label):
    screen = NSScreen.mainScreen()
    screen_frame = screen.frame()
    screen_height = screen_frame.size.height
    one_percent_height = screen_height * 0.05  # 5% of the screen height

    scale_factor = get_scale_factor()  # Get the scale factor dynamically

    def update_position():
        try:
            mouse_controller = mouse.Controller()
            x, y = mouse_controller.position
            x *= scale_factor
            y *= scale_factor

            # Boundary check and reset
            boundary_y = one_percent_height * scale_factor
            if y < boundary_y:
                mouse_controller.position = (x / scale_factor, boundary_y / scale_factor)
                y = boundary_y

            label.config(text=f"Mouse Position: x={int(x)}, y={int(y)}")
            percent_label.config(text=f"5% from top in pixels: {int(boundary_y)}px")
            print(f"Mouse Position: x={int(x)}, y={int(y)}")  # Print position to terminal
        except Exception as e:
            print(f"Error reading mouse position: {str(e)}")
        root.after(1, update_position)  # Schedule next update

    update_position()

def start_focusing_app():
    selected_index = app_list.curselection()
    if selected_index:
        global focus_thread, stop_event
        stop_event = threading.Event()
        app_name = app_list.get(selected_index[0])

        enable_kiosk_mode()

        focus_thread = threading.Thread(target=focus_app, args=(app_name, stop_event))
        focus_thread.start()

def stop_focusing_app():
    if stop_event:
        stop_event.set()
        focus_thread.join()
        disable_kiosk_mode()
    print("Focus stopped. Exiting application and script.")

def on_press(key):
    if key == keyboard.Key.cmd:
        current_keys.add(key)
    elif hasattr(key, 'char') and key.char == 'e':
        current_keys.add(key.char)

    if keyboard.Key.cmd in current_keys and 'e' in current_keys:
        stop_focusing_app()

def on_release(key):
    if key == keyboard.Key.cmd:
        current_keys.discard(key)
    elif hasattr(key, 'char') and key.char == 'e':
        current_keys.discard(key.char)

def handle_exit_signal(signum, frame):
    print("Received shutdown signal")
    disable_kiosk_mode()
    root.quit()

# GUI Setup
root = tk.Tk()
root.title("Kiosk")

# Display Resolutions
resolutions = get_screen_resolutions()
resolution_label = tk.Label(root, text="\n".join(resolutions))
resolution_label.pack(pady=20)

percent_label = tk.Label(root, text="5% from top in pixels: 0px")
percent_label.pack(pady=10)

mouse_position_label = tk.Label(root, text="Mouse Position: x=0, y=0")
mouse_position_label.pack(pady=20)
track_mouse(mouse_position_label, percent_label) # Start tracking mouse position


app_list = tk.Listbox(root, height=10, width=50, exportselection=0)
for app in get_running_apps():
    app_list.insert(tk.END, app)
app_list.pack(pady=20)

focus_button = ttk.Button(root, text="Focus Selected Application", command=start_focusing_app)
focus_button.pack(pady=10)

quit_button = ttk.Button(root, text="Quit", command=stop_focusing_app)
quit_button.pack(pady=20)

# Key Listener Setup
current_keys = set()
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)

root.mainloop()
