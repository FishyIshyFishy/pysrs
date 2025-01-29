import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pysrs.mains.run_image_2d import lockin_scan
from pysrs.instruments.galvo_funcs import Galvo
import os
import sys
from PIL import Image

class GUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Stimulated Raman Coordinator')

        self.root.geometry('1600x1600')
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.simulation_mode = tk.BooleanVar(value=False)
        self.running = False

        self.save_acquisitions = tk.BooleanVar(value=False)  

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
        style.configure('TButton', font=('Calibri', 16, 'bold'), padding=8)  
        style.configure('TLabel', font=('Calibri', 16)) 
        style.configure('TEntry', font=('Calibri', 16), padding=3) 
        style.configure('TCheckbutton', font=('Calibri', 16))

        control_frame = ttk.LabelFrame(self.root, text='Control Panel', padding=(8, 8))
        control_frame.grid(row=0, column=0, padx=10, pady=5, sticky='ew')

        self.start_button = ttk.Button(control_frame, text='Acquire Continuously', command=self.start_scan, style='TButton')
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(control_frame, text='Stop', command=self.stop_scan, state='disabled', style='TButton')
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        self.single_button = ttk.Button(control_frame, text='Acquire Single', command=self.acquire_single, style='TButton')
        self.single_button.grid(row=0, column=2, padx=5, pady=5)

        save_frame = ttk.Frame(control_frame)
        save_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='w')  

        self.save_checkbutton = ttk.Checkbutton(
            save_frame, text='Save Acquisitions',
            variable=self.save_acquisitions,
            command=self.toggle_save_options
        )
        self.save_checkbutton.pack(side=tk.LEFT, padx=5)

        info_button = ttk.Label(save_frame, text='ⓘ', foreground='blue', cursor='hand2', font=('Calibri', 16, 'bold'))
        info_button.pack(side=tk.LEFT)
        tooltip_text = (
            '• Press "Acquire Continuously" to continuously update the display.\n'
            '• Press "Acquire Single" for one image if "Save Acquisitions" is OFF.\n'
            '• If "Save Acquisitions" is ON, "Acquire Single" will collect multiple frames\n'
            '  and save them all to a single multi-page TIFF file.'
        )
        Tooltip(info_button, tooltip_text)

        self.simulation_mode_checkbutton = ttk.Checkbutton(control_frame, text='Simulate Data', variable=self.simulation_mode)
        self.simulation_mode_checkbutton.grid(row=1, column=1, padx=5, pady=5, sticky='w') 

        frames_label = ttk.Label(control_frame, text='Frames to acquire')
        frames_label.grid(row=4, column=0, sticky='w', padx=5, pady=3)

        frames_frame = ttk.Frame(control_frame)
        frames_frame.grid(row=4, column=1, padx=5, pady=3, sticky='w')

        self.save_num_entry = ttk.Entry(frames_frame, width=8, font=('Calibri', 16))
        self.save_num_entry.insert(0, '10')
        self.save_num_entry.pack(side=tk.LEFT, padx=(0, 5))

        self.progress_label = ttk.Label(frames_frame, text='(0/0)', font=('Calibri', 16, 'bold'))
        self.progress_label.pack(side=tk.LEFT)


        ttk.Label(control_frame, text='Save to').grid(row=5, column=0, sticky='w', padx=5, pady=3)
        self.file_path_frame = ttk.Frame(control_frame)
        self.file_path_frame.grid(row=5, column=1, pady=3, sticky='w')

        self.save_file_entry = ttk.Entry(self.file_path_frame, width=35, font=('Calibri', 16))  
        self.save_file_entry.insert(0, 'Documents/example.tiff')
        self.save_file_entry.pack(side=tk.LEFT, padx=(0, 5))

        browse_button = ttk.Button(self.file_path_frame, text='Browse...', command=self.browse_save_path, style='TButton')
        browse_button.pack(side=tk.LEFT)

        self.toggle_save_options()

        param_frame = ttk.LabelFrame(self.root, text='Galvo Parameters', padding=(8, 8))
        param_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew')

        self.param_entries = {}

        param_groups = [
            ('Device', 'device'),
            ('Galvo AO Chans', 'ao_chans'),
            ('Lockin AI Chan', 'ai_chan'),
            ('Rate (Hz)', 'rate'),
            ('Amp X', 'amp_x'),
            ('Amp Y', 'amp_y'),
            ('Steps X', 'numsteps_x'),
            ('Steps Y', 'numsteps_y'),
            ('Dwell Time (s)', 'dwell')  
        ]

        for col, (label, key) in enumerate(param_groups):
            ttk.Label(param_frame, text=label).grid(row=0, column=col, sticky='w', padx=5, pady=3)
            entry = ttk.Entry(param_frame, width=12, font=('Calibri', 16))  
            entry.insert(0, str(self.config[key]) if key != 'ao_chans' else ','.join(self.config[key]))
            entry.grid(row=1, column=col, padx=5, pady=3)
            self.param_entries[key] = entry

        display_frame = ttk.LabelFrame(self.root, text='Data Display', padding=(15, 15))
        display_frame.grid(row=2, column=0, padx=10, pady=10, sticky='nsew')  
        self.root.grid_rowconfigure(2, weight=1)  
        display_frame.grid_rowconfigure(0, weight=1)
        display_frame.grid_columnconfigure(0, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(10, 10))  # **Increased size from (10, 10) to (12, 12)**
        self.canvas = FigureCanvasTkAgg(self.fig, master=display_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, padx=10, pady=10)

    def browse_save_path(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension='.tiff',
            filetypes=[('TIFF files', '*.tiff *.tif'), ('All files', '*.*')],
            title='Choose a file name to save'
        )
        if filepath:
            self.save_file_entry.delete(0, tk.END)
            self.save_file_entry.insert(0, filepath)

    def toggle_save_options(self):
        state = 'normal' if self.save_acquisitions.get() else 'disabled'
        self.save_num_entry.configure(state=state)
        self.save_file_entry.configure(state=state)

    def start_scan(self):
        if self.running:
            messagebox.showwarning('Warning', 'Scan is already running.')
            return

        if self.save_acquisitions.get():
            messagebox.showinfo(
                'Info',
                'Uncheck "Save Acquisitions" or use "Acquire Single" if you want to save data.'
            )
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
        if self.running and not startup:
            messagebox.showwarning(
                'Warning',
                'Stop continuous acquisition first before saving or single acquisitions.'
            )
            return

        try:
            self.update_config()
            if not self.save_acquisitions.get():
                galvo = Galvo(self.config)
                if startup or self.simulation_mode.get():
                    data = self.generate_data()
                else:
                    data = lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)
                self.display(data)
            else:
                num_frames_str = self.save_num_entry.get().strip()
                filename = self.save_file_entry.get().strip()

                if not filename:
                    messagebox.showerror('Error', 'Please specify a valid TIFF filename.')
                    return
                try:
                    num_frames = int(num_frames_str)
                    if num_frames < 1:
                        raise ValueError
                except ValueError:
                    messagebox.showerror('Error', 'Invalid number of frames.')
                    return

                galvo = Galvo(self.config)
                images = []

                self.progress_label.config(text=f'(0/{num_frames})')
                self.root.update_idletasks()

                for i in range(num_frames):
                    if self.simulation_mode.get():
                        data = self.generate_data()
                    else:
                        data = lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)

                    self.display(data)

                    data_flipped = np.flipud(data)

                    arr_norm = (data_flipped - data_flipped.min()) / (data_flipped.max() - data_flipped.min() + 1e-9)
                    arr_uint8 = (arr_norm * 255).astype(np.uint8)
                    pil_img = Image.fromarray(arr_uint8)
                    images.append(pil_img)

                    self.progress_label.config(text=f'({i + 1}/{num_frames})')
                    self.root.update_idletasks()

                dirpath = os.path.dirname(filename)
                if dirpath:
                    os.makedirs(dirpath, exist_ok=True)

                if len(images) > 1:
                    images[0].save(
                        filename,
                        save_all=True,
                        append_images=images[1:],
                        format='TIFF'
                    )
                else:
                    images[0].save(filename, format='TIFF')

                messagebox.showinfo('Done', f'Saved {num_frames} frames to {filename}')
                self.progress_label.config(text=f'(0/{num_frames})') 

        except Exception as e:
            messagebox.showerror('Error', f'Cannot collect/save data: {e}')



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
            self.ax_hslice = self.fig.add_axes([0.1, 0.83, 0.63, 0.1])  # top area

        self.ax_hslice.plot(
            np.linspace(-self.config['amp_x'], self.config['amp_x'], data.shape[1]),
            x_slice,
            color='blue'
        )
        self.ax_hslice.set_title('X-Slice')
        self.ax_hslice.set_xticks([])

        if hasattr(self, 'ax_vslice') and self.ax_vslice:
            self.ax_vslice.clear()
        else:
            self.ax_vslice = self.fig.add_axes([0.92, 0.1, 0.05, 0.8])  # right side

        self.ax_vslice.plot(
            y_slice,
            np.linspace(-self.config['amp_y'], self.config['amp_y'], data.shape[0]),
            color='red'
        )
        self.ax_vslice.set_title('Y-Slice', rotation=-90)
        self.ax_vslice.set_yticks([])

        self.canvas.draw()

    def close(self):
        self.running = False
        self.root.quit()
        self.root.destroy()
        os._exit(0)

    def show_feedback(self, entry):
        original = entry.cget('background')
        entry.configure(background='lightgreen')
        self.root.after(500, lambda: entry.configure(background=original))

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind('<Enter>', self.show_tooltip)
        widget.bind('<Leave>', self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tip_window:
            return
        x, y, _, _ = self.widget.bbox('insert')
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.geometry(f'+{x}+{y}')
        label = tk.Label(
            tw, text=self.text, justify='left',
            background='#ffffe0', relief='solid', borderwidth=1, padx=10, pady=5,
            font=('Calibri', 14)
        )
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


if __name__ == '__main__':
    root = tk.Tk()
    app = GUI(root)
    root.mainloop()
