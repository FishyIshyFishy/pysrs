import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import os
import sys
import time
from PIL import Image
from matplotlib.figure import Figure
from pysrs.instruments.zaber import ZaberStage
from pysrs.instruments.galvo_funcs import Galvo
from pysrs.runners.run_image_2d import lockin_scan
from pysrs.utils.rpoc2 import RPOC

class GUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Stimulated Raman Coordinator')
        self.root.geometry('1200x1200')

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        self.simulation_mode = tk.BooleanVar(value=True)
        self.running = False
        self.acquiring = False
        self.save_acquisitions = tk.BooleanVar(value=False)

        self.root.protocol('WM_DELETE_WINDOW', self.close)

        self.config = {
            'device': 'Dev1',
            'ao_chans': ['ao1', 'ao0'],
            'ai_chan': 'ai1',
            'amp_x': 0.5,
            'amp_y': 0.5,
            'rate': 1e5,
            'numsteps_x': 200,
            'numsteps_y': 200,
            'numsteps_extra': 50,
            'dwell': 1e-5
        }

        self.zaber_stage = ZaberStage(port='COM3')
        self.hyperspectral_enabled = tk.BooleanVar(value=False)
        self.hyper_config = {
            'start_um': 20000,
            'stop_um': 30000,
            'single_um': 25000
        }

        self.rpoc_enabled = tk.BooleanVar(value=False)

        self.colorbar = None
        self.ax_hslice = None
        self.ax_vslice = None

        self.create_widgets()
        threading.Thread(target=self.acquire, kwargs={"startup": True}, daemon=True).start() # thread so that UI doesnt lag on startup

    def create_widgets(self):
        style = ttk.Style()
        style.configure('TButton', font=('Calibri', 16, 'bold'), padding=8)
        style.configure('TLabel', font=('Calibri', 16))
        style.configure('TEntry', font=('Calibri', 16), padding=3)
        style.configure('TCheckbutton', font=('Calibri', 16))

        ################# CONTROL PANEL #################
        control_frame = ttk.LabelFrame(self.root, text='Control Panel', padding=(8, 8))
        control_frame.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')

        self.continuous_button = ttk.Button(
            control_frame, text='Acquire Continuously',
            command=self.start_scan, style='TButton'
        )
        self.continuous_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(
            control_frame, text='Stop',
            command=self.stop_scan, state='disabled', style='TButton'
        )
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        self.single_button = ttk.Button(
            control_frame, text='Acquire',
            command=lambda: threading.Thread(target=self.acquire, daemon=True).start(), # need to thread to stop early
            style='TButton'
        )
        self.single_button.grid(row=0, column=2, padx=5, pady=5)

        save_frame = ttk.Frame(control_frame)
        save_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='w')

        self.save_checkbutton = ttk.Checkbutton(
            save_frame, text='Save Acquisitions',
            variable=self.save_acquisitions,
            command=self.toggle_save_options
        )
        self.save_checkbutton.pack(side=tk.LEFT, padx=5)

        info_button = ttk.Label(save_frame, text='ⓘ', foreground='blue', cursor='hand2',
                                font=('Calibri', 16, 'bold'))
        info_button.pack(side=tk.LEFT)
        tooltip_text = (
            '• Press "Acquire Continuously" to continuously update the display.\n'
            '• Press "Acquire" for one image if "Save Acquisitions" is OFF.\n'
            '• If "Save Acquisitions" is ON, "Acquire" will collect the number of specified frames\n'
            '  and save them all to a single multi-page TIFF file.'
        )
        Tooltip(info_button, tooltip_text)

        self.simulation_mode_checkbutton = ttk.Checkbutton(
            control_frame, text='Simulate Data', variable=self.simulation_mode
        )
        self.simulation_mode_checkbutton.grid(row=1, column=1, padx=5, pady=5, sticky='w')

        frames_label = ttk.Label(control_frame, text='Frames to acquire')
        frames_label.grid(row=4, column=0, sticky='w', padx=5, pady=3)

        frames_frame = ttk.Frame(control_frame)
        frames_frame.grid(row=4, column=1, padx=5, pady=3, sticky='w')

        self.save_num_entry = ttk.Entry(frames_frame, width=8, font=('Calibri', 16))
        self.save_num_entry.insert(0, '1')
        self.save_num_entry.pack(side=tk.LEFT, padx=(0, 5))

        self.progress_label = ttk.Label(frames_frame, text='(0/0)', font=('Calibri', 16, 'bold'))
        self.progress_label.pack(side=tk.LEFT)

        ttk.Label(control_frame, text='Save to').grid(row=5, column=0,
                                                      sticky='w', padx=5, pady=3)
        self.file_path_frame = ttk.Frame(control_frame)
        self.file_path_frame.grid(row=5, column=1, pady=3, sticky='w')

        self.save_file_entry = ttk.Entry(self.file_path_frame, width=35, font=('Calibri', 16))
        self.save_file_entry.insert(0, 'Documents/example.tiff')
        self.save_file_entry.pack(side=tk.LEFT, padx=(0, 5))

        browse_button = ttk.Button(self.file_path_frame, text='Browse...',
                                   command=self.browse_save_path, style='TButton')
        browse_button.pack(side=tk.LEFT)
 
        ################# DELAY STAGE PANEL #################
        delay_stage_frame = ttk.LabelFrame(self.root, text='Delay Stage Settings', padding=(8, 8))
        delay_stage_frame.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')

        self.delay_hyperspec_checkbutton = ttk.Checkbutton(delay_stage_frame, text='Enable Hyperspectral Scanning', variable=self.hyperspectral_enabled, command=self.toggle_hyperspectral_fields)
        self.delay_hyperspec_checkbutton.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='w')

        lbl_start = ttk.Label(delay_stage_frame, text='Start (µm)')
        lbl_start.grid(row=1, column=0, sticky='e', padx=5, pady=3)
        self.entry_start_um = ttk.Entry(delay_stage_frame, width=10, font=('Calibri', 16))
        self.entry_start_um.insert(0, str(self.hyper_config['start_um']))
        self.entry_start_um.grid(row=1, column=1, padx=5, pady=3, sticky='w')

        lbl_stop = ttk.Label(delay_stage_frame, text='Stop (µm)')
        lbl_stop.grid(row=2, column=0, sticky='e', padx=5, pady=3)
        self.entry_stop_um = ttk.Entry(delay_stage_frame, width=10, font=('Calibri', 16))
        self.entry_stop_um.insert(0, str(self.hyper_config['stop_um']))
        self.entry_stop_um.grid(row=2, column=1, padx=5, pady=3, sticky='w')

        lbl_single = ttk.Label(delay_stage_frame, text='Single Delay (µm)')
        lbl_single.grid(row=3, column=0, sticky='e', padx=5, pady=3)
        self.entry_single_um = ttk.Entry(delay_stage_frame, width=10, font=('Calibri', 16))
        self.entry_single_um.insert(0, str(self.hyper_config['single_um']))
        self.entry_single_um.grid(row=3, column=1, padx=5, pady=3, sticky='w')

        lbl_shifts = ttk.Label(delay_stage_frame, text='Number of Shifts')
        lbl_shifts.grid(row=4, column=0, sticky='e', padx=5, pady=3)
        self.entry_numshifts = ttk.Entry(delay_stage_frame, width=10, font=('Calibri', 16))
        self.entry_numshifts.insert(0, '10')  
        self.entry_numshifts.grid(row=4, column=1, padx=5, pady=3, sticky='w')

        self.entry_single_um.bind('<Return>', self.single_delay_changed)
        self.entry_single_um.bind('<FocusOut>', self.single_delay_changed)

        calibrate_button = ttk.Button(delay_stage_frame, text='Calibrate', command=self.calibrate, style='TButton')
        calibrate_button.grid(row=1, column=2, columnspan=1, padx=5, pady=10)

        movestage_button = ttk.Button(delay_stage_frame, text = 'Move Stage', command = self.force_zaber, style='TButton')
        movestage_button.grid(row=3, column=2, columnspan=1, padx=5, pady=10)

        self.toggle_hyperspectral_fields()
        self.toggle_save_options()

        ################# RPOC PANEL #################
        rpoc_frame = ttk.LabelFrame(self.root, text='RPOC', padding=(8,8))
        rpoc_frame.grid(row=0, column=2, padx=10, pady=5, sticky='nsew')

        self.rpoc_checkbutton = ttk.Checkbutton(rpoc_frame, text='Enable RPOC', variable=self.rpoc_enabled, command=self.toggle_rpoc_fields)
        self.rpoc_checkbutton.grid(row=0, column=0)

        newmask_button = ttk.Button(rpoc_frame, text='Create New Mask', command=self.create_mask, style='TButton')
        newmask_button.grid(row=2, column=0, columnspan=1, padx=5, pady=10)

        loadmask_button = ttk.Button(rpoc_frame, text='Load Saved Mask', command=self.update_mask, style='TButton')
        loadmask_button.grid(row=1, column=0, columnspan=1, padx=5, pady=10)

        ################# GALVO PANEL #################
        param_frame = ttk.LabelFrame(self.root, text='Galvo Parameters', padding=(8, 8))
        param_frame.grid(row=1, column=0, columnspan=4, padx=10, pady=5, sticky='ew')

        self.param_entries = {}
        param_groups = [
            ('Device', 'device'),
            ('Galvo AO Chans', 'ao_chans'),
            ('Lockin AI Chan', 'ai_chan'),
            ('Sampling Rate (Hz)', 'rate'),
            ('Amp X', 'amp_x'),
            ('Amp Y', 'amp_y'),
            ('Steps X', 'numsteps_x'),
            ('Steps Y', 'numsteps_y'),
            ('Padding steps', 'numsteps_extra'),
            ('Dwell Time (us)', 'dwell')
        ]
        for col, (label, key) in enumerate(param_groups):
            ttk.Label(param_frame, text=label).grid(row=0, column=col, sticky='w', padx=5, pady=3)
            entry = ttk.Entry(param_frame, width=12, font=('Calibri', 16))
            if key != 'ao_chans':
                entry.insert(0, str(self.config[key]))
            else:
                entry.insert(0, ','.join(self.config[key]))
            entry.grid(row=1, column=col, padx=5, pady=3)
            self.param_entries[key] = entry

        info_button = ttk.Label(param_frame, text='ⓘ', foreground='blue', cursor='hand2',
                                font=('Calibri', 16, 'bold'))
        info_button.grid(row=0, column=len(param_groups), sticky='w', padx=5, pady=3)
        galvo_tooltip_text = (
            "• Device: NI-DAQ device identifier (e.g., 'Dev1')\n"
            "• Galvo AO Chans: Analog output channels controlling galvos (e.g., 'ao1,ao0')\n"
            "• Lockin AI Chan: Analog input channel for lock-in amplifier (e.g., 'ai1')\n"
            "• Sampling Rate (Hz): Rate at which voltage signals are sampled (e.g., 100000 Hz)\n"
            "• Amp X / Amp Y: Voltage amplitudes for galvo movement (e.g., 0.5 V)\n"
            "• Steps X / Steps Y: Number of discrete points scanned in X and Y directions\n"
            "• Padding steps: Extra steps scanned outside the main region to stabilize the system\n"
            "• Dwell Time (us): Time spent at each (X, Y) position in microseconds"
        )
        Tooltip(info_button, galvo_tooltip_text)

        ################# DATA PANEL #################
        display_frame = ttk.LabelFrame(self.root, text='Data Display', padding=(15, 15))
        display_frame.grid(row=2, column=0, columnspan=4, padx=10, pady=10, sticky='nsew')
        display_frame.grid_rowconfigure(0, weight=1)
        display_frame.grid_columnconfigure(0, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(14, 14))
        self.canvas = FigureCanvasTkAgg(self.fig, master=display_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, padx=10, pady=10)



############################################################################################################
#################################### Zaber Stage  Functions ###############################################
############################################################################################################
    def calibrate(self):
        cal_win = tk.Toplevel(self.root)
        cal_win.title("Stage Calibration")
        cal_win.geometry("900x600")

        config_frame = ttk.Frame(cal_win, padding=10)
        config_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(config_frame, text='Start Position (µm)').grid(row=0, column=0, sticky='w', padx=5, pady=3)
        start_entry = ttk.Entry(config_frame, width=12, font=('Calibri', 14))
        start_entry.insert(0, str(self.hyper_config['start_um']))
        start_entry.grid(row=0, column=1, padx=5, pady=3)

        ttk.Label(config_frame, text='Stop Position (µm)').grid(row=1, column=0, sticky='w', padx=5, pady=3)
        stop_entry = ttk.Entry(config_frame, width=12, font=('Calibri', 14))
        stop_entry.insert(0, str(self.hyper_config['stop_um']))
        stop_entry.grid(row=1, column=1, padx=5, pady=3)

        ttk.Label(config_frame, text='Number of Steps').grid(row=2, column=0, sticky='w', padx=5, pady=3)
        cal_steps_entry = ttk.Entry(config_frame, width=10, font=('Calibri', 14))
        cal_steps_entry.insert(0, '10')
        cal_steps_entry.grid(row=2, column=1, padx=5, pady=3)

        start_button = ttk.Button(config_frame, text='Start Calibration', style='TButton')
        start_button.grid(row=3, column=0, columnspan=2, padx=5, pady=10)

        fig = Figure(figsize=(5, 3), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title('Calibration Data')
        ax.set_xlabel('Stage Position (µm)')
        ax.set_ylabel('Average Intensity')

        canvas = FigureCanvasTkAgg(fig, master=cal_win)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        cal_running = [False]

        def run_calibration():
            cal_running[0] = True
            try:
                start_val = float(start_entry.get().strip())
                stop_val = float(stop_entry.get().strip())
                n_steps = int(cal_steps_entry.get().strip())
                if n_steps < 1 or start_val >= stop_val:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Invalid calibration settings.")
                cal_running[0] = False
                return

            try:
                self.zaber_stage.connect()
            except Exception as e:
                messagebox.showerror("Zaber Error", str(e))
                cal_running[0] = False
                return

            if n_steps == 1:
                positions_to_scan = [start_val]
            else:
                step_size = (stop_val - start_val) / (n_steps - 1)
                positions_to_scan = [start_val + i * step_size for i in range(n_steps)]

            positions, intensities = [], []

            for pos in positions_to_scan:
                if not cal_running[0]:
                    break

                try:
                    self.zaber_stage.move_absolute_um(pos)
                except Exception as e:
                    messagebox.showerror("Zaber Error", str(e))
                    cal_running[0] = False
                    break

                if self.simulation_mode.get():
                    data = self.generate_data()
                else:
                    galvo = Galvo(self.config)
                    data = lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)

                avg_val = data.mean()
                positions.append(pos)
                intensities.append(avg_val)

                ax.clear()
                ax.set_title('Calibration Data')
                ax.set_xlabel('Stage Position (µm)')
                ax.set_ylabel('Average Intensity')
                ax.plot(positions, intensities, '-o', color='blue')
                canvas.draw()
                canvas.flush_events()

                time.sleep(0.2)

            cal_running[0] = False

        def start_cal():
            if not cal_running[0]:
                thread = threading.Thread(target=run_calibration, daemon=True)
                thread.start()

        start_button.configure(command=start_cal)

        stop_button = ttk.Button(config_frame, text='Stop Calibration', style='TButton',
                                 command=lambda: stop_cal())
        stop_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5)

        def stop_cal():
            cal_running[0] = False

    def single_delay_changed(self, event=None):
        try:
            val = float(self.entry_single_um.get().strip())
            self.hyper_config['single_um'] = val  
        except ValueError:
            print("[INFO] Invalid single delay value entered. Ignoring.")

    def force_zaber(self):
        try:
            move_position = self.hyper_config['single_um'] 
            self.zaber_stage.connect()
            self.zaber_stage.move_absolute_um(move_position)
            print(f"[INFO] Stage moved to {move_position} µm successfully.")
        except Exception as e:
            messagebox.showerror("Stage Move Error", f"Error moving stage: {e}")



############################################################################################################
########################################### RPOC Functions #################################################
############################################################################################################
    def create_mask(self):
        # Open a new window for the RPOC mask editor
        mask_window = tk.Toplevel(self.root)
        mask_window.title('RPOC Mask Editor')
        # Instantiate the RPOC class with the new Toplevel window
        rpoc_app = RPOC(mask_window, image=self.data)

    def update_mask(self):
        print('update mask successfully called')

############################################################################################################
####################################### Data Acquisition Functions #########################################
############################################################################################################
    def start_scan(self):
        # start continuous acquisition - not used in non-continuous functions
        if self.running:
            messagebox.showwarning('Warning', 'Scan is already running.')
            return

        self.running = True
        self.continuous_button['state'] = 'disabled'
        self.stop_button['state'] = 'normal'

        scan_thread = threading.Thread(target=self.scan, daemon=True)
        scan_thread.start()

    def stop_scan(self):
        # stop acquisitions, either continuous or finite
        self.running = False
        self.acquiring = False
        self.continuous_button['state'] = 'normal'
        self.stop_button['state'] = 'disabled'
        self.single_button['state'] = 'normal'
    
    def scan(self):
        # threaded scan function
        try:
            while self.running:
                self.update_config()
                galvo = Galvo(self.config)

                if self.simulation_mode.get():
                    data = self.generate_data()
                else:
                    data = lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)

                self.root.after(0, self.display, data)
        except Exception as e:
            messagebox.showerror('Error', f'Cannot display data: {e}')
        finally:
            self.running = False
            self.continuous_button['state'] = 'normal'
            self.stop_button['state'] = 'disabled'

    def acquire(self, startup=False):
        # main function for when "acquire" button is clicked
        if self.running and not startup:
            messagebox.showwarning(
                'Warning',
                'Stop continuous acquisition first before saving or single acquisitions.'
            )
            return

        self.acquiring = True
        self.stop_button['state'] = 'normal'  # Enable stop button immediately
        
        try:
            self.update_config()

            if self.hyperspectral_enabled.get() and self.save_acquisitions.get():
                numshifts_str = self.entry_numshifts.get().strip()
                filename = self.save_file_entry.get().strip()
                if not filename:
                    messagebox.showerror('Error', 'Please specify a valid TIFF filename.')
                    return None, None
            elif self.hyperspectral_enabled.get() and not self.save_acquisitions.get():
                numshifts_str = self.entry_numshifts.get().strip()
                filename = None
            elif not self.hyperspectral_enabled.get() and self.save_acquisitions.get():
                numshifts_str = self.save_num_entry.get().strip()
                filename = self.save_file_entry.get().strip()
                if not filename:
                    messagebox.showerror('Error', 'Please specify a valid TIFF filename.')
                    return None, None
            else:
                numshifts_str = self.save_num_entry.get().strip()
                filename = None

            try:
                numshifts = int(numshifts_str)
                if numshifts < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror('Error', 'Invalid number of steps.')
                return

            if not self.hyperspectral_enabled.get():
                images = self.acquire_multiple(numshifts)
                if self.save_acquisitions.get():
                    if images: self.save_images(images, filename)

            elif self.hyperspectral_enabled.get():
                images = self.acquire_hyperspectral(numshifts)
                if self.save_acquisitions.get():
                    if images: self.save_images(images, filename)
                
        except Exception as e:
            messagebox.showerror('Error', f'Cannot collect/save data: {e}')
        finally:
            self.acquiring = False  
            self.stop_button['state'] = 'disabled' 

    def acquire_multiple(self, numshifts):
        # non-hyperspectral acquisitions done for the number of times specified in entry box
        numframes = numshifts # nomenclature so i dont get confused

        images = []
        self.progress_label.config(text=f'(0/{numframes})')
        self.root.update_idletasks()
        galvo = Galvo(self.config)

        for i in range(numframes):
            if not self.acquiring:
                break

            data = self.generate_data() if self.simulation_mode.get() else lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)
            self.root.after(0, self.display, data)
            images.append(self.convert(data))

            self.progress_label.config(text=f'({i + 1}/{numframes})')
            self.root.update_idletasks()

        return images

    def acquire_hyperspectral(self, numshifts):
        # acquire multiple but now with zaber stage shifting
        start_val = float(self.entry_start_um.get().strip())
        stop_val = float(self.entry_stop_um.get().strip())
        if numshifts == 1:
            positions =  [start_val]
        else:
            step_size = (stop_val - start_val) / (numshifts - 1)
            positions =  [start_val + i * step_size for i in range(numshifts)]

        try:
            self.zaber_stage.connect()
        except Exception as e:
            messagebox.showerror("Zaber Error", str(e))
            return None

        images = []
        self.progress_label.config(text=f'(0/{numshifts})')
        self.root.update_idletasks()

        for i, pos in enumerate(positions):
            if not self.acquiring:
                break
            try:
                self.zaber_stage.move_absolute_um(pos)
            except Exception as e:
                messagebox.showerror("Stage Move Error", str(e))
                return None

            galvo = Galvo(self.config)
            data = self.generate_data() if self.simulation_mode.get() else lockin_scan(self.config['device'] + '/' + self.config['ai_chan'], galvo)

            self.root.after(0, self.display, data)
            images.append(self.convert(data))

            self.progress_label.config(text=f'({i + 1}/{numshifts})')
            self.root.update_idletasks()

        return images

    def save_images(self, images, filename):
        # save images but do not overwrite
        dirpath = os.path.dirname(filename)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        base, ext = os.path.splitext(filename)
        counter = 1
        new_filename = filename  

        while os.path.exists(new_filename): 
            new_filename = f"{base}_{counter}{ext}"
            counter += 1

        if len(images) > 1:
            images[0].save(
                new_filename,
                save_all=True,
                append_images=images[1:],
                format='TIFF'
            )
        else:
            images[0].save(new_filename, format='TIFF')

        messagebox.showinfo('Done', f'Saved {len(images)} frames to {new_filename}')
        self.progress_label.config(text=f'(0/{len(images)})')

    def convert(self, data, type=np.uint8):
        # encapsulation of image logic, can add real time smoothing etc. into here
        data_flipped = np.flipud(data)
        arr_norm = (data_flipped - data_flipped.min()) / (data_flipped.max() - data_flipped.min() + 1e-9)
        arr_typed = (arr_norm * 255).astype(type)
        return Image.fromarray(arr_typed)



############################################################################################################
####################################### Parameter Management Functions #####################################
############################################################################################################
    def toggle_save_options(self):
        # conditions to verify whenever save acquisition checkbox is updated
        if self.save_acquisitions.get():
            if self.hyperspectral_enabled.get():
                self.save_num_entry.configure(state='disabled')
            else: 
                self.save_num_entry.configure(state='normal')
            self.save_file_entry.configure(state='normal')
            self.file_path_frame.winfo_children()[1].configure(state='normal')
            self.continuous_button.configure(state='disabled')
        else:
            self.save_num_entry.configure(state='disabled')
            self.save_file_entry.configure(state='disabled')
            self.file_path_frame.winfo_children()[1].configure(state='disabled')
            self.continuous_button.configure(state='normal')
            self.toggle_hyperspectral_fields()

    def toggle_hyperspectral_fields(self):
        # conditions to verify whenever hyperspectral is checked/unchecked
        if self.hyperspectral_enabled.get():
            if self.save_acquisitions.get():
                self.save_num_entry.configure(state='disabled')
            self.entry_start_um.config(state='normal')
            self.entry_stop_um.config(state='normal')
            self.entry_single_um.config(state='disabled')
            self.entry_numshifts.config(state='normal')  
            self.continuous_button.configure(state='disabled')
        else:
            if self.save_acquisitions.get():
                self.save_num_entry.configure(state='normal')
            self.entry_start_um.config(state='disabled')
            self.entry_stop_um.config(state='disabled')
            self.entry_single_um.config(state='normal')
            self.entry_numshifts.config(state='disabled')  
            self.continuous_button.configure(state='normal')

    def toggle_rpoc_fields(self):
        parent = self.rpoc_checkbutton.winfo_parent()
        parent = self.rpoc_checkbutton.nametowidget(parent)

        state = tk.NORMAL if self.rpoc_enabled.get() else tk.DISABLED
        for widget in parent.winfo_children():
            if widget != self.rpoc_checkbutton:
                widget.configure(state=state)

    def update_config(self):
        # self explanatory
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
    
    def browse_save_path(self):
        # boy i sure wonder what this does
        filepath = filedialog.asksaveasfilename(
            defaultextension='.tiff',
            filetypes=[('TIFF files', '*.tiff *.tif'), ('All files', '*.*')],
            title='Choose a file name to save'
        )
        if filepath:
            self.save_file_entry.delete(0, tk.END)
            self.save_file_entry.insert(0, filepath)



############################################################################################################
####################################### Display Functions ##################################################
############################################################################################################
    def display(self, data):
        self.data = data  

        if not hasattr(self, 'img_handle'):
            self.img_handle = self.ax.imshow(
                data,
                extent=[-self.config['amp_x'], self.config['amp_x'],
                        -self.config['amp_y'], self.config['amp_y']],
                origin='lower',
                aspect='equal',
                cmap='cool'
            )
            self.ax.set_title('Live Data')
            self.ax.set_xlabel('X Amplitude')
            self.ax.set_ylabel('Y Amplitude')
            self.colorbar = self.fig.colorbar(self.img_handle, ax=self.ax, orientation='vertical', pad=0.1)
            self.colorbar.set_label('Intensity')

            self.slice_x = data.shape[1] // 2
            self.slice_y = data.shape[0] // 2

            x_extent = np.linspace(-self.config['amp_x'], self.config['amp_x'], self.data.shape[1])
            y_extent = np.linspace(-self.config['amp_y'], self.config['amp_y'], self.data.shape[0])

            self.vline = self.ax.axvline(x=x_extent[self.slice_x], color='red', linestyle='--', lw=2)  # Vertical slice
            self.hline = self.ax.axhline(y=y_extent[self.slice_y], color='blue', linestyle='--', lw=2)  # Horizontal slice

            # for the toolbar that normally pops up when using basic mpl stuff
            if not hasattr(self, 'toolbar'):
                toolbar_frame = ttk.Frame(self.root)
                toolbar_frame.grid(row=3, column=0, columnspan=2, sticky='ew')
                self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
                self.toolbar.update()
                self.toolbar.pack(side=tk.LEFT)
        else:
            self.img_handle.set_data(data)
            self.img_handle.set_clim(vmin=data.min(), vmax=data.max())  
            self.img_handle.set_extent([-self.config['amp_x'], self.config['amp_x'],
                                        -self.config['amp_y'], self.config['amp_y']])  

        x_extent = np.linspace(-self.config['amp_x'], self.config['amp_x'], self.data.shape[1])
        y_extent = np.linspace(-self.config['amp_y'], self.config['amp_y'], self.data.shape[0])

        self.vline.set_xdata([x_extent[self.slice_x]]) 
        self.hline.set_ydata([y_extent[self.slice_y]]) 

        self.update_slices()
        self.canvas.draw()
        self.canvas.mpl_connect('button_press_event', self.on_image_click)

    def on_image_click(self, event):
        if str(self.toolbar.mode) in ["zoom rect", "pan/zoom"] or event.inaxes != self.ax: # dont change slices if zooming or panning
            return 

        x_extent = np.linspace(-self.config['amp_x'], self.config['amp_x'], self.data.shape[1])
        y_extent = np.linspace(-self.config['amp_y'], self.config['amp_y'], self.data.shape[0])

        self.slice_x = np.argmin(np.abs(x_extent - event.xdata))  
        self.slice_y = np.argmin(np.abs(y_extent - event.ydata))  

        self.root.after(0, self.display, self.data)

    def update_slices(self):
        # update slices whenever a new image is taken
        x_slice = self.data[self.slice_y, :]
        y_slice = self.data[:, self.slice_x]

        if hasattr(self, 'ax_hslice') and self.ax_hslice:
            self.ax_hslice.clear()
        else:
            self.ax_hslice = self.fig.add_axes([0.11, 0.88, 0.63, 0.07])  

        self.ax_hslice.plot(
            np.linspace(-self.config['amp_x'], self.config['amp_x'], self.data.shape[1]),
            x_slice,
            color='blue'
        )
        self.ax_hslice.set_title('X-Slice')
        self.ax_hslice.set_xticks([])

        if hasattr(self, 'ax_vslice') and self.ax_vslice:
            self.ax_vslice.clear()
        else:
            self.ax_vslice = self.fig.add_axes([0.92, 0.1, 0.06, 0.8])  

        self.ax_vslice.plot(
            y_slice,
            np.linspace(-self.config['amp_y'], self.config['amp_y'], self.data.shape[0]),
            color='red'
        )
        self.ax_vslice.set_title('Y-Slice')
        self.ax_vslice.set_yticks([])
        self.ax_vslice.set_yticklabels(self.ax_vslice.get_yticks(), rotation=90)

        self.canvas.draw()


    def generate_data(self):
        # :)
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
                if ((x - (center_x - eye_offset))**2 + (y - (center_y + eye_offset))**2) < eye_radius**2:
                    data[y, x] = 1.0
                if ((x - (center_x + eye_offset))**2 + (y - (center_y + eye_offset))**2) < eye_radius**2:
                    data[y, x] = 1.0

        for x in range(numsteps_x):
            for y in range(numsteps_y):
                dist = ((x - center_x)**2 + (y - (center_y + eye_offset // 2))**2)**0.5
                if mouth_radius - mouth_thickness < dist < mouth_radius + mouth_thickness and y < center_y:
                    data[y, x] = 1.0

        return data



############################################################################################################
####################################### Misc Functions ######################################################
############################################################################################################    
    def show_feedback(self, entry):
        original = entry.cget('background')
        entry.configure(background='lightgreen')
        self.root.after(500, lambda: entry.configure(background=original))

    def close(self):
        self.running = False
        self.zaber_stage.disconnect()  
        self.root.quit()
        self.root.destroy()
        os._exit(0)



class Tooltip:
    # for the little info things to hover over with descriptions
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