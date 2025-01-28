import tkinter as tk
from tkinter import ttk, messagebox, font
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pysrs.mains.run_image_2d import lockin_scan

def gen():
    data = [(np.random.uniform(0, 1), np.random.uniform(0, 1), np.random.uniform(0, 100)) for _ in range(100)]
    return data

class GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("gui test")

        self.root.geometry("1600x1600")
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.simulation_mode = tk.BooleanVar(value=False)
        self.running = False
        self.root.protocol('WM_DELETE_WINDOW', self.close)

        self.create_widgets()

    def create_widgets(self):
        style = ttk.Style()
        style.configure("button1.TButton", font=('Calibri', 16))

        control_frame = ttk.LabelFrame(self.root, text="Control Panel", padding=(10, 10))
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.start_button = ttk.Button(control_frame, text="Acquire Continuously", command=self.start_scan, style="button1.TButton")
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_scan, state="disabled", style="button1.TButton")
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        self.single_button = ttk.Button(control_frame, text="Acquire Single", command=self.acquire_single, style="button1.TButton")
        self.single_button.grid(row=0, column=2, padx=5, pady=5)

        ttk.Checkbutton(control_frame, text="Simulate data", variable=self.simulation_mode).grid(row=1, column=0, columnspan=3, pady=5)

        display_frame = ttk.LabelFrame(self.root, text="Data Display", padding=(10, 10))
        display_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.root.grid_rowconfigure(1, weight=1)
        display_frame.grid_rowconfigure(0, weight=1)
        display_frame.grid_columnconfigure(0, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.canvas = FigureCanvasTkAgg(self.fig, master=display_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, padx=5, pady=5)

    def start_scan(self):
        if self.running:
            messagebox.showwarning("Warning", "Scan is already running.")
            return

        self.running = True
        self.start_button["state"] = "disabled"
        self.stop_button["state"] = "normal"

        # Start scan in a separate thread
        scan_thread = threading.Thread(target=self.scan, daemon=True)
        scan_thread.start()

    def stop_scan(self):
        self.running = False
        self.start_button["state"] = "normal"
        self.stop_button["state"] = "disabled"

    def acquire_single(self):
        if self.running:
            messagebox.showwarning("Warning", "Stop continuous acquisition first.")
            return

        try:
            data = gen() if self.simulation_mode.get() else lockin_scan()
            self.display(data)
        except Exception as e:
            messagebox.showerror(f'Error, cannot collect real data currently: {e}')

    def scan(self):
        try:
            while self.running:
                data = gen() if self.simulation_mode.get() else lockin_scan()
                self.display(data)
        except Exception as e:
            messagebox.showerror(f'Error, cannot display data: {e}')
        finally:
            self.running = False
            self.start_button["state"] = "normal"
            self.stop_button["state"] = "disabled"

    def display(self, data):
        self.ax.clear()
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.set_title("Live Data")
        for x, y, intensity in data:
            self.ax.scatter(x, y, c='blue', s=intensity/2, alpha=0.6)
        self.canvas.draw()

    def close(self):
        self.running=False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = GUI(root)
    root.mainloop()