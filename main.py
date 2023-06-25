import os
import io
import time
import socket
import struct
import threading
from PIL import Image
from mss import mss
from time import sleep
import numpy as np
import json
import subprocess
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox
from mss import mss
import numpy as np

active_screencasts = {}
running_programs = []

def capture_and_send_screen(monitor_id, server_socket, stop_event):
    conn, _ = server_socket.accept()
    print(f"Client connected. Screen sharing started.")
    sct = mss()

    # Get the monitor
    monitor = sct.monitors[monitor_id]

    while not stop_event.is_set():
        try:
            screen = np.array(sct.grab(monitor))
            img = Image.fromarray(screen)
            buf = io.BytesIO()
            img.convert('RGB').save(buf, format='JPEG')
            byte_im = buf.getvalue()

            # Send the size of the data first
            size = len(byte_im)
            size = struct.pack('>L', size)
            conn.sendall(size)

            time.sleep(0.01)

            # Now send the image data
            conn.sendall(byte_im)
            time.sleep(0.1)
        except BrokenPipeError:
            print("Client disconnected, stopping screencast.")
            break

    server_socket.close()

def start_background(port):
    server_socket = socket.socket()
    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(0)

    print(f"Screen background service on port {port}.")

    stop_event = threading.Event()
    screencast_thread = threading.Thread(target=handle_monitor_list_request, args=(server_socket, stop_event))
    screencast_thread.start()

    active_screencasts[port] = (screencast_thread, stop_event, server_socket)

def start_screencast(monitor_id, port):
    server_socket = socket.socket()
    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(0)

    print(f"Screen sharing service started on port {port}. Waiting for client connection.")

    stop_event = threading.Event()
    screencast_thread = threading.Thread(target=capture_and_send_screen, args=(monitor_id, server_socket, stop_event))
    screencast_thread.start()

    active_screencasts[port] = (screencast_thread, stop_event, server_socket)

def stop_screencast(port):
    if port in active_screencasts:
        _, stop_event, server_socket = active_screencasts[port]
        stop_event.set()  # Signal the thread to stop
        server_socket.close()
        del active_screencasts[port]
        print(f"Service stopped on port {port}.")
    else:
        print(f"No active screen sharing on port {port}.")

# def list_monitors(conn):
#     sct = mss()
#     monitor_list = [{"id": i, "info": monitor} for i, monitor in enumerate(sct.monitors)]
#     conn.sendall(json.dumps(monitor_list).encode())

def list_monitors(conn):
    monitors = mss().monitors
    print(f"Listing monitors.")
    if conn:
        monitor_list = [{"id": i, "info": monitor} for i, monitor in enumerate(monitors)]
        conn.sendall(json.dumps(monitor_list).encode())
    else:
        print(monitors)
        for i, monitor in enumerate(monitors[1:], start=1):  # Exclude the first monitor as it's the "All in One" monitor
            print(f"Monitor {i}: {monitor}")

def handle_monitor_list_request(server_socket, stop_event):
    while not stop_event.is_set():
        try:
            conn, _ = server_socket.accept()
            data = conn.recv(1024)
            command = data.decode('utf-8').strip()
            if command == "list":
                list_monitors(conn)
            elif command == "add":
                add_program(conn)
            elif command == "remove":
                remove_program(conn)
            conn.close()
        except socket.error:
            break
    server_socket.close()

def add_last_screen():
    time.sleep(1.5)
    last_monitor = len(mss().monitors) - 1
    start_screencast(int(last_monitor), 9999 + int(last_monitor))

def add_program(conn):
    global running_programs
    print(f"Adding screen.")
    monitor_serial = int(time.time())
    command = ['nohup', './createdummy', f'serial={monitor_serial}', f'name={monitor_serial}', '&']
    program = subprocess.Popen(command, start_new_session=True)
    running_programs.append(program)
    conn.sendall(str(len(running_programs)).encode())
    add_last_screen()

def remove_program(conn):
    global running_programs
    print(f"Removing screen.")
    if running_programs:
        program = running_programs.pop()
        try:
            os.killpg(os.getpgid(program.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        conn.sendall(str(len(running_programs)).encode())







def main():
    def start_screencast_from_gui():
        selected_monitor_id = monitor_var.get()
        if selected_monitor_id == "":
            messagebox.showerror("Error", "Please select a monitor before starting the screencast.")
            return
        start_screencast(int(selected_monitor_id), 9999 + int(selected_monitor_id))

    # Get monitor list
    sct = mss()
    monitors = sct.monitors

    # Create a new tkinter window
    root = tk.Tk()
    root.geometry("600x300")

    # Add title to the window
    root.title("VR Project - Select a Monitor")

    # Create a StringVar to hold the selected monitor ID
    monitor_var = tk.StringVar()

    # Create and pack a radio button for each monitor
    for i, monitor in enumerate(monitors[1:], start=1):
        # Capture screenshot of the monitor
        screenshot = sct.grab(monitor)
        # Convert screenshot to PIL Image
        img = Image.fromarray(np.array(screenshot))
        # Resize the image to fit into the GUI
        img = img.resize((150, 100), Image.ANTIALIAS)
        

        # Convert PIL Image to PhotoImage
        photo = ImageTk.PhotoImage(img)

        monitor_frame = tk.Frame(root)
        monitor_frame.pack()

        monitor_label = tk.Label(monitor_frame, image=photo)
        monitor_label.image = photo  # Keep a reference to prevent garbage collection
        monitor_label.pack(side="left", padx=10, pady=10)


        tk.Radiobutton(
            monitor_frame, text=f"Monitor {i}", variable=monitor_var, value=i
        ).pack(side="right")

    # Create and pack a start button
    start_button = tk.Button(root, text="Start Screencast", command=start_screencast_from_gui)
    
    start_button.pack()


    # Run the tkinter main loop
    root.mainloop()

if __name__ == "__main__":
    main()


