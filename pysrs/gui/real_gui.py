import tkinter as tk
from tkinter import ttk, messagebox
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pysrs.mains.run_image_2d import lockin_scan
from pysrs.instruments.galvo_funcs import Galvo
import os
import sys

class GUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Stimulated Raman Coordinator')

        self.root.geometry('1600x1600')
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.simulation_mode = tk.BooleanVar(value=False)
        self.running = False
        self.root.protocol('WM_DELETE_WINDOW', self.close)

        self.config = {
            'device': 'Dev1',
            'ao_chans': ['ao1', 'ao0'],
            'ai_chan': 'ai1',
            'amp_x': 0.5,
            'amp_y': 0.5,
            'rate': 1e5,
            'numsteps_x': 100,
            'numsteps_y': 100,
            'dwell': 1e-5
        }

        self.colorbar = None
        self.ax_hslice = None
        self.ax_vslice = None

        self.create_widgets()

        self.acquire_single(startup=True)

    def create_widgets(self):
        style = ttk.Style()
        style.configure('button1.TButton', font=('Calibri', 16))

        control_frame = ttk.LabelFrame(self.root, text='Control Panel', padding=(10, 10))
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky='ew')

        self.start_button = ttk.Button(control_frame, text='Acquire Continuously', command=self.start_scan, style='button1.TButton')
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(control_frame, text='Stop', command=self.stop_scan, state='disabled', style='button1.TButton')
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        self.single_button = ttk.Button(control_frame, text='Acquire Single', command=self.acquire_single, style='button1.TButton')
        self.single_button.grid(row=0, column=2, padx=5, pady=5)

        ttk.Checkbutton(control_frame, text='Simulate data', variable=self.simulation_mode).grid(row=1, column=0, columnspan=3, pady=5)

        param_frame = ttk.LabelFrame(self.root, text='Galvo Parameters', padding=(10, 10))
        param_frame.grid(row=2, column=0, padx=10, pady=10, sticky='ew')

        self.param_entries = {}
        params = [
            ('Device', 'device'),
            ('Galvo AO Channels (comma-separated)', 'ao_chans'),
            ('Lockin AI Channel', 'ai_chan'),
            ('Amplitude X', 'amp_x'),
            ('Amplitude Y', 'amp_y'),
            ('Rate (Hz)', 'rate'),
            ('Steps X', 'numsteps_x'),
            ('Steps Y', 'numsteps_y'),
            ('Dwell Time (s)', 'dwell')
        ]

        for i, (label_text, key) in enumerate(params):
            ttk.Label(param_frame, text=label_text).grid(row=i, column=0, sticky='w', padx=5, pady=2)
            entry = ttk.Entry(param_frame)
            entry.insert(0, str(self.config[key]) if key != 'ao_chans' else ','.join(self.config[key]))
            entry.grid(row=i, column=1, padx=5, pady=2)
            self.param_entries[key] = entry

        display_frame = ttk.LabelFrame(self.root, text='Data Display', padding=(10, 10))
        display_frame.grid(row=3, column=0, padx=10, pady=10, sticky='ew')
        self.root.grid_rowconfigure(3, weight=1)
        display_frame.grid_rowconfigure(0, weight=1)
        display_frame.grid_columnconfigure(0, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.canvas = FigureCanvasTkAgg(self.fig, master=display_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, padx=5, pady=5)

    def start_scan(self):
        if self.running:
            messagebox.showwarning('Warning', 'Scan is already running.')
            return

        self.running = True
        self.start_button['state'] = 'disabled'
        self.stop_button['state'] = 'normal'

        scan_thread = threading.Thread(target=self.scan, daemon=True)
        scan_thread.start()

    def stop_scan(self):
        self.running = False
        self.start_button['state'] = 'normal'
        self.stop_button['state'] = 'disabled'

    def acquire_single(self, startup=False):
        if self.running:
            messagebox.showwarning('Warning', 'Stop continuous acquisition first.')
            return

        try:
            self.update_config()
            galvo = Galvo(self.config)
            if startup or self.simulation_mode.get(): 
                data = self.generate_data()         
            else:
                data = lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)
            self.display(data)
        except Exception as e:
            messagebox.showerror('Error', f'Cannot collect data: {e}')

    def scan(self):
        try:
            while self.running:
                self.update_config()
                galvo = Galvo(self.config)

                if self.simulation_mode.get():
                    data = self.generate_data()
                else:
                    data = lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)

                self.display(data)
        except Exception as e:
            messagebox.showerror('Error', f'Cannot display data: {e}')
        finally:
            self.running = False
            self.start_button['state'] = 'normal'
            self.stop_button['state'] = 'disabled'


    def update_config(self):
        for key, entry in self.param_entries.items():
            value = entry.get()
            try:
                if key == 'ao_chans':
                    self.config[key] = value.split(',')
                elif key in ['device', 'ai_chan']:
                    self.config[key] = value.strip()
                elif key in ['amp_x', 'amp_y', 'rate', 'dwell']:
                    self.config[key] = float(value)
                else:
                    self.config[key] = int(value)

                self.show_feedback(entry)

            except ValueError:
                messagebox.showerror('Error', f'Invalid value for {key}. Please check your input.')


    def generate_data(self):
        numsteps_x = self.config['numsteps_x']
        numsteps_y = self.config['numsteps_y']

        data = np.random.uniform(0, 0.1, size=(numsteps_y, numsteps_x))

        center_x, center_y = numsteps_x // 2, numsteps_y // 2
        radius = min(numsteps_x, numsteps_y) // 4
        eye_offset = radius // 2
        eye_radius = radius // 8
        mouth_radius = radius // 2
        mouth_thickness = 2

        for x in range(numsteps_x):
            for y in range(numsteps_y):
                if (x - (center_x - eye_offset))**2 + (y - (center_y + eye_offset))**2 < eye_radius**2:
                    data[y, x] = 1.0
                if (x - (center_x + eye_offset))**2 + (y - (center_y + eye_offset))**2 < eye_radius**2:
                    data[y, x] = 1.0

        for x in range(numsteps_x):
            for y in range(numsteps_y):
                distance = ((x - center_x)**2 + (y - (center_y + eye_offset // 2))**2)**0.5
                if mouth_radius - mouth_thickness < distance < mouth_radius + mouth_thickness and y < center_y:
                    data[y, x] = 1.0

        return data

    def display(self, data):
        self.ax.clear()
        im = self.ax.imshow(
            data,
            extent=[-self.config['amp_x'], self.config['amp_x'], -self.config['amp_y'], self.config['amp_y']],
            origin='lower',
            aspect='equal',  
            cmap='viridis'
        )
        self.ax.set_title('Live Data')
        self.ax.set_xlabel('X Amplitude')
        self.ax.set_ylabel('Y Amplitude')

        if hasattr(self, 'colorbar') and self.colorbar is not None:
            self.colorbar.mappable.set_clim(vmin=data.min(), vmax=data.max())
            self.colorbar.update_normal(im)
        else:
            self.colorbar = self.fig.colorbar(im, ax=self.ax, orientation='vertical', pad=0.1)
            self.colorbar.set_label('Intensity')

        mid_y, mid_x = data.shape[0] // 2, data.shape[1] // 2
        x_slice = data[mid_y, :] 
        y_slice = data[:, mid_x] 

        if hasattr(self, 'ax_hslice') and self.ax_hslice:
            self.ax_hslice.clear()
        else:
            self.ax_hslice = self.fig.add_axes([0.1, 0.88, 0.8, 0.1])  

        self.ax_hslice.plot(
            np.linspace(-self.config['amp_x'], self.config['amp_x'], data.shape[1]),
            x_slice,
            color='blue'
        )
        self.ax_hslice.set_title('Horizontal Slice')
        self.ax_hslice.set_xticks([])

        if hasattr(self, 'ax_vslice') and self.ax_vslice:
            self.ax_vslice.clear()
        else:
            self.ax_vslice = self.fig.add_axes([0.92, 0.1, 0.02, 0.8]) 

        self.ax_vslice.plot(
            y_slice,
            np.linspace(-self.config['amp_y'], self.config['amp_y'], data.shape[0]),
            color='red'
        )
        self.ax_vslice.set_title('Vertical Slice', rotation=-90)
        self.ax_vslice.set_yticks([])
        self.canvas.draw()

    def close(self):
        self.running = False  
        self.root.quit()  
        self.root.destroy()       
        os._exit(0) 

    def show_feedback(self, entry):
        original = entry.cget("background")  
        entry.configure(background="lightgreen")  
        self.root.after(500, lambda: entry.configure(background=original))  


if __name__ == '__main__':
    root = tk.Tk()
    app = GUI(root)
    root.mainloop()
