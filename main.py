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

def enable_boundary():
    global boundary_active
    boundary_active = True

def disable_boundary():
    global boundary_active
    boundary_active = False

def get_scale_factor():
    screen = NSScreen.mainScreen()
    if screen:
        return screen.backingScaleFactor()
    return 1  # Default to 1 if no screen is detected

def enable_kiosk_mode():
    # Hide the Dock automatically
    subprocess.run(["defaults", "write", "com.apple.dock", "autohide", "-bool", "true"])
    # Disable hot corners
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-tl-corner", "-int", "0"])
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-tr-corner", "-int", "0"])
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-bl-corner", "-int", "0"])
    subprocess.run(["defaults", "write", "com.apple.dock", "wvous-br-corner", "-int", "0"])
    # Disable swipe between pages and other multi-touch trackpad gestures
    subprocess.run(["defaults", "write", "com.apple.AppleMultitouchTrackpad", "TrackpadThreeFingerHorizSwipeGesture", "-int", "0"])
    subprocess.run(["defaults", "write", "com.apple.AppleMultitouchTrackpad", "TrackpadFourFingerHorizSwipeGesture", "-int", "0"])
    # Disable Mission Control and App Expose gestures
    subprocess.run(["defaults", "write", "com.apple.dock", "showMissionControlGestureEnabled", "-bool", "false"])
    subprocess.run(["defaults", "write", "com.apple.dock", "showAppExposeGestureEnabled", "-bool", "false"])
    # Disable moving spaces
    subprocess.run(["defaults", "write", "com.apple.dock", "mru-spaces", "-bool", "false"])
    # Restart the Dock to apply changes
    subprocess.run(["killall", "Dock"])

def disable_kiosk_mode():
    # Show the Dock
    subprocess.run(["defaults", "write", "com.apple.dock", "autohide", "-bool", "false"])
    # Restore swipe gestures
    subprocess.run(["defaults", "delete", "com.apple.AppleMultitouchTrackpad", "TrackpadThreeFingerHorizSwipeGesture"])
    subprocess.run(["defaults", "delete", "com.apple.AppleMultitouchTrackpad", "TrackpadFourFingerHorizSwipeGesture"])
    # Enable Mission Control and App Expose gestures
    subprocess.run(["defaults", "write", "com.apple.dock", "showMissionControlGestureEnabled", "-bool", "true"])
    subprocess.run(["defaults", "write", "com.apple.dock", "showAppExposeGestureEnabled", "-bool", "true"])
    # Enable moving spaces
    subprocess.run(["defaults", "write", "com.apple.dock", "mru-spaces", "-bool", "true"])
    # Restart the Dock to apply changes
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

def track_mouse(root, labels):
    screens = NSScreen.screens()  # Get all connected screens
    scale_factors = [screen.backingScaleFactor() for screen in screens]
    screen_frames = [screen.frame() for screen in screens]
    boundaries = [(screen_frame.size.height * 0.05 * scale, screen_frame.size.height * 0.95 * scale) for screen_frame, scale in zip(screen_frames, scale_factors)]

    def update_position():
        if boundary_active:
            try:
                mouse_controller = mouse.Controller()
                x, y = mouse_controller.position

                for label, screen_frame, (top_boundary, bottom_boundary), scale_factor in zip(labels, screen_frames, boundaries, scale_factors):
                    if screen_frame.origin.x <= x * scale_factor <= screen_frame.origin.x + screen_frame.size.width * scale_factor:
                        adjusted_x = x * scale_factor
                        adjusted_y = y * scale_factor

                        # Check and enforce the top boundary
                        if adjusted_y < top_boundary:
                            adjusted_y = top_boundary
                            new_y = adjusted_y / scale_factor
                            mouse_controller.position = (x, new_y)
                        # Check and enforce the bottom boundary
                        elif adjusted_y > bottom_boundary:
                            adjusted_y = bottom_boundary
                            new_y = adjusted_y / scale_factor
                            mouse_controller.position = (x, new_y)

                        label.config(text=f"Mouse Position: x={int(adjusted_x)}, y={int(adjusted_y)}; 5% boundaries: Top={int(top_boundary)}px, Bottom={int(bottom_boundary)}px")
                        print(f"Mouse Position: x={int(adjusted_x)}, y={int(adjusted_y)}; Monitor Boundaries: Top={int(top_boundary)}px, Bottom={int(bottom_boundary)}px")  # Print to terminal

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

def setup_gui(root):
    screens = NSScreen.screens()
    labels = []
    for screen in screens:
        label = tk.Label(root, text="")
        label.pack(pady=20)
        labels.append(label)
    return labels


# GUI Setup
root = tk.Tk()
root.title("Kiosk")

boundary_active = False  # This flag controls the boundary enforcement

# Display Resolutions
resolutions = get_screen_resolutions()
resolution_label = tk.Label(root, text="\n".join(resolutions))
resolution_label.pack(pady=20)

labels = setup_gui(root)
track_mouse(root, labels)

app_list = tk.Listbox(root, height=10, width=50, exportselection=0)
for app in get_running_apps():
    app_list.insert(tk.END, app)
app_list.pack(pady=20)

focus_button = ttk.Button(root, text="Focus Selected Application", command=lambda: [enable_boundary(), start_focusing_app()])
focus_button.pack(pady=10)

quit_button = ttk.Button(root, text="Quit", command=lambda: [disable_boundary(), stop_focusing_app()])
quit_button.pack(pady=20)

# Key Listener Setup
current_keys = set()
def on_press(key):
    if key == keyboard.Key.cmd:
        current_keys.add(key)
    elif hasattr(key, 'char') and key.char == 'e':
        current_keys.add(key.char)

    if keyboard.Key.cmd in current_keys and 'e' in current_keys:
        disable_boundary()
        stop_focusing_app()

def on_release(key):
    if key == keyboard.Key.cmd:
        current_keys.discard(key)
    elif hasattr(key, 'char') and key.char == 'e':
        current_keys.discard(key.char)

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)

root.mainloop()