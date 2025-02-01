import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading, os
from pysrs.instruments.zaber import ZaberStage
from pysrs.old_utils.rpoc2 import RPOC
from utils import Tooltip, generate_data, convert, show_feedback
import acquisition
import calibration
import display
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

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
            'ai_chan': ['ai1'],  # comma-separated list creates multiple channels
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

        self.channel_axes = []
        self.slice_x = []
        self.slice_y = []
        self.data = None

        self.create_widgets()

        # Launch an initial (single) acquisition thread if needed.
        threading.Thread(target=acquisition.acquire, args=(self,), kwargs={"startup": True}, daemon=True).start()

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
            command=lambda: acquisition.start_scan(self), style='TButton'
        )
        self.continuous_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(
            control_frame, text='Stop',
            command=lambda: acquisition.stop_scan(self), state='disabled', style='TButton'
        )
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        self.single_button = ttk.Button(
            control_frame, text='Acquire',
            command=lambda: threading.Thread(target=acquisition.acquire, args=(self,), daemon=True).start(),
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
            '• If "Save Acquisitions" is ON, "Acquire" will collect the specified frames\n'
            '  and save them as multi-page TIFF files (one per channel).'
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

        ttk.Label(control_frame, text='Save to').grid(row=5, column=0, sticky='w', padx=5, pady=3)
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

        self.delay_hyperspec_checkbutton = ttk.Checkbutton(
            delay_stage_frame, text='Enable Hyperspectral Scanning',
            variable=self.hyperspectral_enabled, command=self.toggle_hyperspectral_fields
        )
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

        calibrate_button = ttk.Button(delay_stage_frame, text='Calibrate', command=lambda: calibration.calibrate_stage(self), style='TButton')
        calibrate_button.grid(row=1, column=2, padx=5, pady=10)

        movestage_button = ttk.Button(delay_stage_frame, text='Move Stage', command=self.force_zaber, style='TButton')
        movestage_button.grid(row=3, column=2, padx=5, pady=10)

        ################# RPOC PANEL #################
        rpoc_frame = ttk.LabelFrame(self.root, text='RPOC', padding=(8, 8))
        rpoc_frame.grid(row=0, column=2, padx=10, pady=5, sticky='nsew')

        self.rpoc_checkbutton = ttk.Checkbutton(rpoc_frame, text='Enable RPOC', variable=self.rpoc_enabled, command=self.toggle_rpoc_fields)
        self.rpoc_checkbutton.grid(row=0, column=0)
        newmask_button = ttk.Button(rpoc_frame, text='Create New Mask', command=self.create_mask, style='TButton')
        newmask_button.grid(row=2, column=0, padx=5, pady=10)
        loadmask_button = ttk.Button(rpoc_frame, text='Load Saved Mask', command=self.update_mask, style='TButton')
        loadmask_button.grid(row=1, column=0, padx=5, pady=10)
        self.mask_file_path = tk.StringVar(value="No mask loaded")
        self.mask_status_label = ttk.Label(rpoc_frame, textvariable=self.mask_file_path, relief="solid", padding=(5, 2), width=20)
        self.mask_status_label.grid(row=1, column=1, padx=5, pady=10, sticky="w")

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
            if key not in ['ao_chans', 'ai_chan']:
                entry.insert(0, str(self.config[key]))
            else:
                entry.insert(0, ",".join(self.config[key]))
            entry.grid(row=1, column=col, padx=5, pady=3)
            self.param_entries[key] = entry
        info_button = ttk.Label(param_frame, text='ⓘ', foreground='blue', cursor='hand2', font=('Calibri', 16, 'bold'))
        info_button.grid(row=0, column=len(param_groups), sticky='w', padx=5, pady=3)
        galvo_tooltip_text = (
            "• Device: NI-DAQ device identifier (e.g., 'Dev1')\n"
            "• Galvo AO Chans: e.g., 'ao1,ao0'\n"
            "• Lockin AI Chan: e.g., 'ai1,ai2,ai3' for multiple channels\n"
            "• Sampling Rate (Hz): e.g., 100000\n"
            "• Amp X / Amp Y: voltage amplitudes for galvo movement\n"
            "• Steps X / Steps Y: discrete points in X,Y\n"
            "• Padding steps: extra steps outside the main region\n"
            "• Dwell Time (us): time spent at each position in microseconds"
        )
        Tooltip(info_button, galvo_tooltip_text)

        ################# DATA PANEL #################
        display_frame = ttk.LabelFrame(self.root, text='Data Display', padding=(15, 15))
        display_frame.grid(row=2, column=0, columnspan=4, padx=10, pady=10, sticky='nsew')
        display_frame.grid_rowconfigure(0, weight=1)
        display_frame.grid_columnconfigure(0, weight=1)
        self.fig = Figure(figsize=(14, 14))
        self.canvas = FigureCanvasTkAgg(self.fig, master=display_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, padx=10, pady=10)
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.grid(row=3, column=0, columnspan=2, sticky='ew')
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
        self.toolbar.pack(side=tk.LEFT)
        self.canvas.mpl_connect('button_press_event', lambda event: display.on_image_click(self, event))

        self.toggle_hyperspectral_fields()
        self.toggle_save_options()
        self.toggle_rpoc_fields()

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

    def create_mask(self):
        mask_window = tk.Toplevel(self.root)
        mask_window.title('RPOC Mask Editor')
        rpoc_app = RPOC(mask_window, image=self.data)

    def update_mask(self):
        file_path = filedialog.askopenfilename(
            title="Select Mask File",
            filetypes=[("Mask Files", "*.mask *.json *.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.mask_file_path.set(f"Loaded: {os.path.basename(file_path)}")
        else:
            self.mask_file_path.set("No mask loaded")

    def update_config(self):
        for key, entry in self.param_entries.items():
            value = entry.get()
            try:
                if key in ['ao_chans', 'ai_chan']:
                    channels = [v.strip() for v in value.split(',') if v.strip()]
                    self.config[key] = channels
                elif key in ['device']:
                    self.config[key] = value.strip()
                elif key in ['amp_x', 'amp_y', 'rate', 'dwell']:
                    self.config[key] = float(value)
                else:
                    self.config[key] = int(value)
                show_feedback(self, entry)
            except ValueError:
                messagebox.showerror('Error', f'Invalid value for {key}. Please check your input.')

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

    def close(self):
        self.running = False
        self.zaber_stage.disconnect()
        self.root.quit()
        self.root.destroy()
        os._exit(0)
