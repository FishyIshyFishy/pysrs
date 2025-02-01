import tkinter as tk
from tkinter import ttk, messagebox, filedialog, PhotoImage
import threading, os
from pysrs.instruments.zaber import ZaberStage
from pysrs.old_utils.rpoc2 import RPOC
from utils import Tooltip, generate_data, convert, show_feedback
import acquisition
import calibration
import display
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from pathlib import Path
from PIL import Image, ImageTk 

BASE_DIR = Path(__file__).resolve().parent.parent
FOLDERICON_PATH = BASE_DIR / "data" / "folder_icon.png"

class CollapsiblePane(ttk.Frame):
    def __init__(self, parent, text="", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.show = tk.BooleanVar(value=True)
        self.header = ttk.Frame(self)
        self.header.pack(fill="x", expand=True)
        self.toggle_button = ttk.Checkbutton(
            self.header, text=text, variable=self.show, command=self.toggle, style="Toolbutton"
        )
        self.toggle_button.pack(side="left", fill="x", expand=True)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

    def toggle(self):
        if self.show.get():
            self.container.pack(fill="both", expand=True)
        else:
            self.container.forget()
        if hasattr(self.master.master.master, "update_sidebar_visibility"):
            self.master.master.master.update_sidebar_visibility()

class ScrollableFrame(ttk.Frame):
    """A frame that becomes scrollable when its contents overflow."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.bg_color = "#3A3A3A"
        style = ttk.Style()
        style.configure("Dark.TFrame", background=self.bg_color) 

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=self.bg_color)

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_frame = ttk.Frame(self.canvas, style="Dark.TFrame")  # Use custom style
        self.scrollable_frame.bind("<Configure>", self.update_scroll_region)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.bind("<Configure>", self.update_background)

    def update_scroll_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def update_background(self, event=None):
        self.canvas.config(bg=self.bg_color)
        self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())

class GUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Stimulated Raman Coordinator')
        self.root.geometry('1200x800')
        self.bg_color = '#3A3A3A'
        self.root.configure(bg=self.bg_color)

        self.simulation_mode = tk.BooleanVar(value=True)
        self.running = False
        self.acquiring = False
        self.save_acquisitions = tk.BooleanVar(value=False)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

        self.config = {
            'device': 'Dev1',
            'ao_chans': ['ao1', 'ao0'],
            'ai_chan': ['ai1'],
            'amp_x': 0.5,
            'amp_y': 0.5,
            'rate': 1e5,
            'numsteps_x': 200,
            'numsteps_y': 200,
            'numsteps_extra': 50,
            'dwell': 1e-5
        }
        self.hyper_config = {
            'start_um': 20000,
            'stop_um': 30000,
            'single_um': 25000
        }
        self.hyperspectral_enabled = tk.BooleanVar(value=False)
        self.rpoc_enabled = tk.BooleanVar(value=False)
        self.mask_file_path = tk.StringVar(value="No mask loaded")

        self.channel_axes = []
        self.slice_x = []
        self.slice_y = []
        self.data = None

        self.zaber_stage = ZaberStage(port='COM3')

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)
        self.paned = ttk.PanedWindow(self.main_frame, orient="horizontal")
        self.paned.pack(fill="both", expand=True)


        self.sidebar_container = ScrollableFrame(self.paned)
        self.paned.add(self.sidebar_container, weight=0)
        self.root.update_idletasks() 
        self.root.after(100, lambda: self.paned.sashpos(0, 0))
        self.sidebar = self.sidebar_container.scrollable_frame

        self.display_area = ttk.Frame(self.paned)
        self.paned.add(self.display_area, weight=1)
        self.display_area.rowconfigure(0, weight=1)
        self.display_area.columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar",
                        troughcolor=self.bg_color,
                        background=self.bg_color,
                        bordercolor=self.bg_color,
                        arrowcolor="#888888")

        self.create_widgets()

        threading.Thread(target=acquisition.acquire, args=(self,), kwargs={"startup": True}, daemon=True).start()

    def update_sidebar_visibility(self):
        visible = any(pane.show.get() for pane in self.sidebar.winfo_children() if isinstance(pane, CollapsiblePane))
        if not visible:
            try:
                self.paned.sash_place(0, 0, 0)
            except Exception as e:
                pass  
        else:
            try:
                self.paned.sash_place(0, 250, 0)
            except Exception as e:
                pass

    def create_widgets(self):
        self.bg_color = '#2E2E2E'
        self.fg_color = '#D0D0D0'
        self.highlight_color = '#4A90E2'
        self.button_bg = '#444'
        self.entry_bg = '#3A3A3A'
        self.entry_fg = '#FFFFFF'
        default_font = ('Calibri', 12)
        bold_font = ('Calibri', 12, 'bold')

        self.root.configure(bg=self.bg_color)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabelFrame', background=self.bg_color, borderwidth=2, relief="groove")
        style.configure('TLabelFrame.Label', background=self.bg_color, foreground=self.fg_color, font=bold_font)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color, font=default_font)
        style.configure('TButton', background=self.button_bg, foreground=self.fg_color, font=bold_font, padding=8)
        style.map('TButton', background=[('active', self.highlight_color)])
        style.configure('TCheckbutton', background=self.bg_color, foreground=self.fg_color, font=default_font)
        style.map('TCheckbutton',
                  background=[('active', '#4A4A4A')],
                  foreground=[('active', '#D0D0D0')])
        style.configure('TEntry', fieldbackground=self.entry_bg, foreground=self.entry_fg,
                        insertcolor="#CCCCCC", font=default_font, padding=3)
        style.map('TEntry',
                  fieldbackground=[('readonly', '#303030'), ('disabled', '#505050')],
                  foreground=[('readonly', '#AAAAAA'), ('disabled', '#888888')],
                  insertcolor=[('readonly', '#666666'), ('disabled', '#888888')])
        style.configure('TLabelframe', background=self.bg_color)
        style.configure('TLabelframe.Label', background=self.bg_color, foreground=self.fg_color, font=bold_font)



        self.cp_pane = CollapsiblePane(self.sidebar, text='Control Panel')
        self.cp_pane.pack(fill="x", padx=10, pady=5)

        control_frame = ttk.Frame(self.cp_pane.container, padding=(12, 12))
        control_frame.grid(row=0, column=0, sticky="nsew")
        for col in range(3):
            control_frame.columnconfigure(col, weight=1)

        self.continuous_button = ttk.Button(
            control_frame, text='Acquire Continuously',
            command=lambda: acquisition.start_scan(self)
        )
        self.continuous_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')

        self.single_button = ttk.Button(
            control_frame, text='Acquire',
            command=lambda: threading.Thread(target=acquisition.acquire, args=(self,), daemon=True).start()
        )
        self.single_button.grid(row=1, column=0, padx=5, pady=5, sticky='ew')

        self.stop_button = ttk.Button(
            control_frame, text='Stop',
            command=lambda: acquisition.stop_scan(self), state='disabled'
        )
        self.stop_button.grid(row=2, column=0, padx=5, pady=5, sticky='ew')

        save_frame = ttk.Frame(control_frame)
        save_frame.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky='w')
        self.save_checkbutton = ttk.Checkbutton(
            save_frame, text='Save Acquisitions',
            variable=self.save_acquisitions, command=self.toggle_save_options
        )
        self.save_checkbutton.pack(side=tk.LEFT, padx=5)
        info_button = ttk.Label(save_frame, text='ⓘ', foreground=self.highlight_color,
                                cursor='hand2', font=bold_font)
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
        self.simulation_mode_checkbutton.grid(row=0, column=1, padx=5, pady=5, sticky='w')

        ttk.Label(control_frame, text='Images to acquire').grid(row=3, column=0, sticky='w', padx=5, pady=3)
        frames_frame = ttk.Frame(control_frame)
        frames_frame.grid(row=3, column=1, padx=5, pady=3, sticky='w')
        self.save_num_entry = ttk.Entry(frames_frame, width=8)
        self.save_num_entry.insert(0, '1')
        self.save_num_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.progress_label = ttk.Label(frames_frame, text='(0/0)', font=bold_font)
        self.progress_label.pack(side=tk.LEFT)

        self.file_path_frame = ttk.Frame(control_frame)
        self.file_path_frame.grid(row=2, column=1, pady=3, sticky='w')
        self.save_file_entry = ttk.Entry(self.file_path_frame, width=30)  # Reduced width
        self.save_file_entry.insert(0, 'Documents/example.tiff')
        self.save_file_entry.pack(side=tk.LEFT, padx=(0, 5))

        style = ttk.Style()
        style.configure("Small.TButton", padding=(2, 2), font=("Calibri", 12))  # Adjust padding & font size

        browse_button = ttk.Button(self.file_path_frame, text="📂", width=2, style="Small.TButton", command=self.browse_save_path)
        browse_button.pack(side=tk.LEFT, padx=(2, 0))




        self.delay_pane = CollapsiblePane(self.sidebar, text='Delay Stage Settings')
        self.delay_pane.pack(fill="x", padx=10, pady=5)

        delay_stage_frame = ttk.Frame(self.delay_pane.container, padding=(12, 12))
        delay_stage_frame.grid(row=0, column=0, sticky="nsew")
        for col in range(3):
            delay_stage_frame.columnconfigure(col, weight=1)

        self.delay_hyperspec_checkbutton = ttk.Checkbutton(
            delay_stage_frame, text='Enable Hyperspectral Scanning',
            variable=self.hyperspectral_enabled, command=self.toggle_hyperspectral_fields
        )
        self.delay_hyperspec_checkbutton.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='w')

        ttk.Label(delay_stage_frame, text='Start (µm)').grid(row=1, column=0, sticky='e', padx=5, pady=3)
        self.entry_start_um = ttk.Entry(delay_stage_frame, width=10)
        self.entry_start_um.insert(0, str(self.hyper_config['start_um']))
        self.entry_start_um.grid(row=1, column=1, padx=5, pady=3, sticky='w')

        ttk.Label(delay_stage_frame, text='Stop (µm)').grid(row=2, column=0, sticky='e', padx=5, pady=3)
        self.entry_stop_um = ttk.Entry(delay_stage_frame, width=10)
        self.entry_stop_um.insert(0, str(self.hyper_config['stop_um']))
        self.entry_stop_um.grid(row=2, column=1, padx=5, pady=3, sticky='w')

        ttk.Label(delay_stage_frame, text='Single Delay (µm)').grid(row=3, column=0, sticky='e', padx=5, pady=3)
        self.entry_single_um = ttk.Entry(delay_stage_frame, width=10)
        self.entry_single_um.insert(0, str(self.hyper_config['single_um']))
        self.entry_single_um.grid(row=3, column=1, padx=5, pady=3, sticky='w')

        ttk.Label(delay_stage_frame, text='Number of Shifts').grid(row=4, column=0, sticky='e', padx=5, pady=3)
        self.entry_numshifts = ttk.Entry(delay_stage_frame, width=10)
        self.entry_numshifts.insert(0, '10')
        self.entry_numshifts.grid(row=4, column=1, padx=5, pady=3, sticky='w')

        self.entry_single_um.bind('<Return>', self.single_delay_changed)
        self.entry_single_um.bind('<FocusOut>', self.single_delay_changed)

        calibrate_button = ttk.Button(delay_stage_frame, text='Calibrate',
                                      command=lambda: calibration.calibrate_stage(self))
        calibrate_button.grid(row=1, column=2, padx=5, pady=10, sticky='ew')
        movestage_button = ttk.Button(delay_stage_frame, text='Move Stage', command=self.force_zaber)
        movestage_button.grid(row=3, column=2, padx=5, pady=10, sticky='ew')




        self.rpoc_pane = CollapsiblePane(self.sidebar, text='RPOC')
        self.rpoc_pane.pack(fill="x", padx=10, pady=5)

        rpoc_frame = ttk.Frame(self.rpoc_pane.container, padding=(12, 12))
        rpoc_frame.grid(row=0, column=0, sticky="nsew")
        for col in range(2):
            rpoc_frame.columnconfigure(col, weight=1)

        self.rpoc_checkbutton = ttk.Checkbutton(
            rpoc_frame, text='Enable RPOC',
            variable=self.rpoc_enabled, command=self.toggle_rpoc_fields
        )
        self.rpoc_checkbutton.grid(row=0, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        loadmask_button = ttk.Button(rpoc_frame, text='Load Saved Mask', command=self.update_mask)
        loadmask_button.grid(row=1, column=0, padx=5, pady=10, sticky='ew')
        newmask_button = ttk.Button(rpoc_frame, text='Create New Mask', command=self.create_mask)
        newmask_button.grid(row=2, column=0, padx=5, pady=10, sticky='ew')

        self.mask_status_entry = ttk.Entry(rpoc_frame, width=20, font=default_font, justify="center",
                                           textvariable=self.mask_file_path)
        self.mask_status_entry.configure(state="readonly")
        self.mask_status_entry.grid(row=1, column=1, padx=5, pady=10, sticky="w")




        self.param_pane = CollapsiblePane(self.sidebar, text='Parameters')
        self.param_pane.pack(fill="x", padx=10, pady=5)

        param_frame = ttk.Frame(self.param_pane.container, padding=(12, 12))
        param_frame.grid(row=0, column=0, sticky="ew")
        for col in range(10):
            param_frame.columnconfigure(col, weight=1)

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

        num_cols = 3  

        for index, (label_text, key) in enumerate(param_groups):
            row = index // num_cols 
            col = index % num_cols   

            ttk.Label(param_frame, text=label_text).grid(row=row * 2, column=col, padx=5, pady=3)
            entry = ttk.Entry(param_frame, width=12)

            if key not in ['ao_chans', 'ai_chan']:
                entry.insert(0, str(self.config[key]))
            else:
                entry.insert(0, ",".join(self.config[key]))

            entry.grid(row=row * 2 + 1, column=col, padx=5, pady=3)  
            self.param_entries[key] = entry

        info_button_param = ttk.Label(param_frame, text='ⓘ', foreground=self.highlight_color,
                                      cursor='hand2', font=bold_font)
        info_button_param.grid(row=0, column=len(param_groups), padx=5, pady=3)
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
        Tooltip(info_button_param, galvo_tooltip_text)





        display_frame = ttk.LabelFrame(self.display_area, text='Data Display', padding=(10, 10))
        display_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        display_frame.rowconfigure(0, weight=1)
        display_frame.columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=display_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)




        toolbar_frame = ttk.Frame(self.display_area, padding=(5, 5))
        toolbar_frame.grid(row=1, column=0, sticky="ew")
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

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