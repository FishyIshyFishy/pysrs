import tkinter as tk
from tkinter import ttk, messagebox, filedialog, PhotoImage
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import threading, os
from pathlib import Path
from PIL import Image, ImageTk
from pysrs.instruments.zaber import ZaberStage
from pysrs.mains.rpoc2 import RPOC
from utils import Tooltip, generate_data, convert
import acquisition
import calibration
import display
import math
from utils import Tooltip, generate_data, convert

BASE_DIR = Path(__file__).resolve().parent.parent # directory definition to access icons that i will add later 
FOLDERICON_PATH = BASE_DIR / "data" / "folder_icon.png" # for browsing the save path

# each block of components can be collapsed, will be particularly useful when i add more stuff (z stage etc.)
class CollapsiblePane(ttk.Frame):
    def __init__(self, parent, text="", gui=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.gui = gui  
        self.show = tk.BooleanVar(value=True)

        self.header = ttk.Frame(self, padding=(5, 2))
        self.header.pack(fill="x", expand=True)

        self.toggle_button = ttk.Checkbutton(
            self.header, text=text, variable=self.show, command=self.toggle, style="Toolbutton"
        )
        self.toggle_button.pack(side="left", fill="x", expand=True)

        self.container = ttk.Frame(self, padding=(5, 5))
        self.container.pack(fill="both", expand=True)

    def toggle(self):
        if self.show.get():
            self.container.pack(fill="both", expand=True)
        else:
            self.container.forget()
        if self.gui is not None:  # dont crash the whole thing pretty please
            self.gui.update_sidebar_visibility()



class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.bg_color = "#3A3A3A"
        style = ttk.Style()
        style.configure("Dark.TFrame", background=self.bg_color)

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=self.bg_color)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_frame = ttk.Frame(self.canvas, style="Dark.TFrame")
        self.scrollable_frame.bind("<Configure>", self.update_scroll_region)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.bind("<Configure>", self.update_background)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def update_scroll_region(self, event=None): # wrapper to make it obvious what this thing actually does
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def update_background(self, event=None): # background was acting weird but this fixes it so ill just keep it i guess thanks chatgpt
        self.canvas.config(bg=self.bg_color)
        self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")




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
        self.collapsed = False
        self.save_acquisitions = tk.BooleanVar(value=False)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind("<Button-1>", self.on_global_click, add="+")

        self.config = {
            'device': 'Dev1',
            'ao_chans': ['ao1', 'ao0'],
            'ai_chans': ['ai1'],
            'channel_names': ['ai1'], 
            'zaber_chan': 'COM3',
            'amp_x': 0.5,
            'amp_y': 0.5,
            'rate': 1e5,
            'numsteps_x': 200,
            'numsteps_y': 200,
            'numsteps_extra': 50,
            'dwell': 1e-5
        }
        self.param_entries = {} # gets populated later with the params from config

        # delay stage config, handled within calibration.py so separate the config as well
        self.hyper_config = {
            'start_um': 20000,
            'stop_um': 30000,
            'single_um': 25000
        }
        self.hyperspectral_enabled = tk.BooleanVar(value=False)
        self.rpoc_enabled = tk.BooleanVar(value=False)
        self.mask_file_path = tk.StringVar(value="No mask loaded")
        self.zaber_stage = ZaberStage(port=self.config['zaber_chan'])

        # variable number of inputs means we have to handle the channels weirdly
        self.channel_axes = []
        self.slice_x = []
        self.slice_y = []
        self.data = None
        
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        self.paned = ttk.PanedWindow(self.main_frame, orient="horizontal")
        self.paned.pack(fill="both", expand=True)

        # left side of the GUI, for all the controls and parameters
        self.sidebar_container = ScrollableFrame(self.paned)
        self.paned.add(self.sidebar_container, weight=0)
        self.root.update_idletasks() 
        self.sidebar = self.sidebar_container.scrollable_frame

        # right side of GUI, for display of flexible size
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

        self.root.after(100, lambda: self.paned.sashpos(0, 450))
        self.update_sidebar_visibility()
        
        self.root.after(500, self.update_sidebar_visibility)

        threading.Thread(target=acquisition.acquire, args=(self,), kwargs={"startup": True}, daemon=True).start()

    def update_sidebar_visibility(self):
        panes = [child for child in self.sidebar.winfo_children() if hasattr(child, 'show')] # python moment
        visible = any(pane.show.get() for pane in panes)  

        try:
            if not visible:
                desired_width = 150  
                self.paned.sashpos(0, desired_width)
                self.sidebar_container.configure(width=desired_width)
            else:
                desired_width = 450  
                self.paned.sashpos(0, desired_width)
                self.sidebar_container.configure(width=desired_width)

            self.paned.event_generate("<Configure>") # make the display think i pressed the sash because for some reason that works
            self.root.update_idletasks()

        except Exception as e:
            print("Error updating sidebar visibility:", e)
            
    def create_widgets(self):
        # TODO: need to put these colors into a separate config
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

        # configure all the various settings
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabelFrame', background=self.bg_color, borderwidth=2, relief="groove")
        style.configure('TLabelFrame.Label', background=self.bg_color, foreground=self.fg_color, font=bold_font)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color, font=default_font)
        style.configure('TLabelframe', background=self.bg_color)
        style.configure('TLabelframe.Label', background=self.bg_color, foreground=self.fg_color, font=bold_font)

        # need to use style.map for these ones bc they r fancy
        style.configure('TButton', background=self.button_bg, foreground=self.fg_color, font=bold_font, padding=8)
        style.map('TButton', background=[('active', self.highlight_color)])
        style.configure('TCheckbutton', background=self.bg_color, foreground=self.fg_color, font=default_font)
        style.map('TCheckbutton', background=[('active', '#4A4A4A')], foreground=[('active', '#D0D0D0')])
        style.configure('TEntry', fieldbackground=self.entry_bg, foreground=self.entry_fg,
                        insertcolor="#CCCCCC", font=default_font, padding=3)
        style.map('TEntry',
                  fieldbackground=[('readonly', '#303030'), ('disabled', '#505050')],
                  foreground=[('readonly', '#AAAAAA'), ('disabled', '#888888')],
                  insertcolor=[('readonly', '#666666'), ('disabled', '#888888')])
        

        ###################################################################
        ####################### CONTROL PANEL STUFF #######################
        ###################################################################
        self.cp_pane = CollapsiblePane(self.sidebar, text='Control Panel', gui=self)
        self.cp_pane.pack(fill="x", padx=10, pady=5)

        self.control_frame = ttk.Frame(self.cp_pane.container, padding=(12, 12))
        self.control_frame.grid(row=0, column=0, sticky="ew")
        for col in range(3):
            self.control_frame.columnconfigure(col, weight=1)

        self.continuous_button = ttk.Button(
            self.control_frame, text='Acq. Continuous',
            command=lambda: acquisition.start_scan(self)
        )
        self.continuous_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')

        self.single_button = ttk.Button(
            self.control_frame, text='Acquire',
            command=lambda: threading.Thread(target=acquisition.acquire, args=(self,), daemon=True).start()
        )
        self.single_button.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        self.stop_button = ttk.Button(
            self.control_frame, text='Stop',
            command=lambda: acquisition.stop_scan(self), state='disabled'
        )
        self.stop_button.grid(row=0, column=2, padx=5, pady=5, sticky='ew')

        self.checkbox_frame = ttk.Frame(self.control_frame)
        self.checkbox_frame.grid(row=1, column=0, columnspan=3, pady=(5, 5), sticky='ew')
        self.checkbox_frame.columnconfigure(0, weight=1)
        self.checkbox_frame.columnconfigure(1, weight=1)

        self.save_checkbutton = ttk.Checkbutton(
            self.checkbox_frame, text='Save Acquisitions',
            variable=self.save_acquisitions, command=self.toggle_save_options
        )
        self.save_checkbutton.grid(row=0, column=0, padx=0, sticky='w')

        self.simulation_mode_checkbutton = ttk.Checkbutton(
            self.checkbox_frame, text='Simulate Data', variable=self.simulation_mode
        )
        self.simulation_mode_checkbutton.grid(row=0, column=1, padx=0, sticky='w')

        self.io_frame = ttk.Frame(self.control_frame)
        self.io_frame.grid(row=2, column=0, columnspan=3, pady=(5, 5), sticky='ew')
        self.io_frame.columnconfigure(0, weight=0)
        self.io_frame.columnconfigure(1, weight=0)
        self.io_frame.columnconfigure(2, weight=0)


        ttk.Label(self.io_frame, text='Images to acquire').grid(row=0, column=0, sticky='w', padx=(5, 0))
        self.save_num_entry = ttk.Entry(self.io_frame, width=8)
        self.save_num_entry.insert(0, '1')
        self.save_num_entry.grid(row=0, column=1, sticky='w', padx=(5, 5))

        self.progress_label = ttk.Label(self.io_frame, text='(0/0)', font=('Calibri', 12, 'bold'))
        self.progress_label.grid(row=0, column=2, padx=5)

        self.path_frame = ttk.Frame(self.control_frame)
        self.path_frame.grid(row=3, column=0, columnspan=3, pady=(5, 5), sticky='ew')
        self.path_frame.columnconfigure(0, weight=1)

        self.save_file_entry = ttk.Entry(self.path_frame, width=30)
        self.save_file_entry.insert(0, 'Documents/example.tiff')
        self.save_file_entry.grid(row=0, column=0, padx=5, sticky='ew')

        browse_button = ttk.Button(self.path_frame, text="📂", width=2, command=self.browse_save_path)
        browse_button.grid(row=0, column=1, padx=5)

        ###################################################################
        ######################## DELAY STAGE STUFF ########################
        ###################################################################
        self.delay_pane = CollapsiblePane(self.sidebar, text='Delay Stage Settings', gui=self)
        self.delay_pane.pack(fill="x", padx=10, pady=5)
        self.delay_stage_frame = ttk.Frame(self.delay_pane.container, padding=(12, 12))
        self.delay_stage_frame.grid(row=0, column=0, sticky="nsew")
        for col in range(3):
            self.delay_stage_frame.columnconfigure(col, weight=1)

        self.delay_hyperspec_checkbutton = ttk.Checkbutton(
            self.delay_stage_frame, text='Enable Hyperspectral Scanning',
            variable=self.hyperspectral_enabled, command=self.toggle_hyperspectral_fields
        )
        self.delay_hyperspec_checkbutton.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='w')

        ttk.Label(self.delay_stage_frame, text='Start (µm)').grid(row=1, column=0, sticky='e', padx=5, pady=3)
        self.entry_start_um = ttk.Entry(self.delay_stage_frame, width=10)
        self.entry_start_um.insert(0, str(self.hyper_config['start_um']))
        self.entry_start_um.grid(row=1, column=1, padx=5, pady=3, sticky='w')

        ttk.Label(self.delay_stage_frame, text='Stop (µm)').grid(row=2, column=0, sticky='e', padx=5, pady=3)
        self.entry_stop_um = ttk.Entry(self.delay_stage_frame, width=10)
        self.entry_stop_um.insert(0, str(self.hyper_config['stop_um']))
        self.entry_stop_um.grid(row=2, column=1, padx=5, pady=3, sticky='w')

        ttk.Label(self.delay_stage_frame, text='Single Delay (µm)').grid(row=3, column=0, sticky='e', padx=5, pady=3)
        self.entry_single_um = ttk.Entry(self.delay_stage_frame, width=10)
        self.entry_single_um.insert(0, str(self.hyper_config['single_um']))
        self.entry_single_um.grid(row=3, column=1, padx=5, pady=3, sticky='w')
        self.entry_single_um.bind('<Return>', self.single_delay_changed) # instantly change delay stage position for convenience
        self.entry_single_um.bind('<FocusOut>', self.single_delay_changed)

        ttk.Label(self.delay_stage_frame, text='Number of Shifts').grid(row=4, column=0, sticky='e', padx=5, pady=3)
        self.entry_numshifts = ttk.Entry(self.delay_stage_frame, width=10)
        self.entry_numshifts.insert(0, '10')
        self.entry_numshifts.grid(row=4, column=1, padx=5, pady=3, sticky='w')

        # TODO: make the calibration pretty in dark mode
        # for some reason using a lambda here delays the function from running on startup, more python black magic i guess
        calibrate_button = ttk.Button(self.delay_stage_frame, text='Calibrate',
                                      command=lambda: calibration.calibrate_stage(self)) 
        calibrate_button.grid(row=1, column=2, padx=5, pady=10, sticky='ew')
        movestage_button = ttk.Button(self.delay_stage_frame, text='Move Stage', command=self.force_zaber)
        movestage_button.grid(row=3, column=2, padx=5, pady=10, sticky='ew')

        ###################################################################
        ########################### RPOC STUFF ############################
        ###################################################################
        self.rpoc_pane = CollapsiblePane(self.sidebar, text='RPOC', gui=self)
        self.rpoc_pane.pack(fill="x", padx=10, pady=5)

        self.rpoc_frame = ttk.Frame(self.rpoc_pane.container, padding=(12, 12))
        self.rpoc_frame.grid(row=0, column=0, sticky="nsew")

        for col in range(2):
            self.rpoc_frame.columnconfigure(col, weight=1)

        self.rpoc_checkbutton = ttk.Checkbutton(
            self.rpoc_frame, text='Enable RPOC',
            variable=self.rpoc_enabled, command=self.toggle_rpoc_fields
        )
        self.rpoc_checkbutton.grid(row=0, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        loadmask_button = ttk.Button(self.rpoc_frame, text='Load Saved Mask', command=self.update_mask)
        loadmask_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.mask_status_entry = ttk.Entry(self.rpoc_frame, width=20, font=('Calibri', 12), justify="center",
                                        textvariable=self.mask_file_path, state="readonly")
        self.mask_status_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        newmask_button = ttk.Button(self.rpoc_frame, text='Create New Mask', command=self.create_mask)
        newmask_button.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        self.rpoc_channel_var = tk.StringVar()
        self.rpoc_channel_entry = ttk.Entry(self.rpoc_frame, textvariable=self.rpoc_channel_var)
        self.rpoc_channel_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        self.rpoc_channel_entry.bind("<Return>", self.finalize_selection)
        self.rpoc_channel_entry.bind("<FocusOut>", self.finalize_selection)


        ###################################################################
        ###################### PARAMETER ENTRY STUFF ######################
        ###################################################################
        self.param_pane = CollapsiblePane(self.sidebar, text='Parameters', gui=self)
        self.param_pane.pack(fill="x", padx=10, pady=5)
        self.param_frame = ttk.Frame(self.param_pane.container, padding=(0, 0))
        self.param_frame.grid(row=0, column=0, sticky="ew")

        # order of parameters is given row-filling by this dictionary
        num_cols = 3 # i have no idea how many columns looks cleanest so just make it flexible
        param_groups = [
            ('Device', 'device'), ('Amp X', 'amp_x'), ('Amp Y', 'amp_y'),
            ('Delay Chan', 'zaber_chan'), ('Steps X', 'numsteps_x'), ('Steps Y', 'numsteps_y'),
            ('AO Chans', 'ao_chans'),  ('Sampling Rate (Hz)', 'rate'), ('Dwell Time (us)', 'dwell'),
            ('AI Chans', 'ai_chans'), ('Input Names', 'channel_names'), ('Padding steps', 'numsteps_extra'),
        ]

        for index, (label_text, key) in enumerate(param_groups): # enumeration black magic to cleanly make all the entries
            row = (index // num_cols) * 2
            col = index % num_cols
            ttk.Label(self.param_frame, text=label_text).grid(row=row, column=col, padx=5, pady=(5, 0), sticky='w')
            entry = ttk.Entry(self.param_frame, width=18)
            if key in ['ao_chans', 'ai_chans', 'channel_names']:
                entry.insert(0, ",".join(self.config[key]))
            else:
                entry.insert(0, str(self.config[key]))
            entry.grid(row=row+1, column=col, padx=5, pady=(0, 5), sticky='ew')
            self.param_entries[key] = entry
            self.param_frame.columnconfigure(col, weight=1)
            entry.bind("<FocusOut>", lambda event: self.update_config())
            entry.bind("<Return>", lambda event: self.update_config())

        self.info_frame = ttk.Frame(self.param_frame)
        self.info_frame.grid(row=0, column=0, columnspan=1, sticky="ew")
        self.info_frame.grid_propagate(False) 

        info_button_param = ttk.Label(self.info_frame, text='ⓘ', foreground=self.highlight_color,
                                    cursor='hand2', font=bold_font)
        info_button_param.pack(side="left", padx=5, pady=(0, 2)) 

        galvo_tooltip_text = (
            "• Device (enter below): NI-DAQ device identifier (e.g., 'Dev1')\n"
            "• Delay Chan: channel input for delay stage (e.g., 'COM3')\n"
            "• AO Chans: analog output channels to the galvo mirrors (e.g., 'ao1,ao0')\n"
            "• AI Chan: analog input channels from amplifier (e.g., 'ai1,ai2,ai3') \n"
            "• Sampling Rate (Hz): resolution of signal output and input\n"
            "• Amp X / Amp Y: voltage amplitudes for galvo movement\n"
            "• Steps X / Steps Y: discrete points in X,Y\n"
            "• Padding steps: extra steps outside the main region\n"
            "• Dwell Time (us): time spent at each position in microseconds\n"
            "No quotes are needed for text inputs."
        )
        Tooltip(info_button_param, galvo_tooltip_text)


        ###################################################################
        ####################### DATA DISPLAY STUFF ########################
        ###################################################################
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

        # set all the initial states by calling all the toggles
        self.toggle_hyperspectral_fields()
        self.toggle_save_options()
        self.toggle_rpoc_fields()

    def on_global_click(self, event):
        # force focus off of text entry boxes whenever clicked out of them
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    def single_delay_changed(self, event=None):
        # set the delay stage to be moved once move stage is clicked
        try:
            val = float(self.entry_single_um.get().strip())
            if val < 0 or val > 50000:
                raise ValueError
            self.hyper_config['single_um'] = val
        except ValueError:
            messagebox.showerror("Value Error", "Invalid single delay value entered. Max is 50,000 um, min is 0 um.") 

    def force_zaber(self):
        # move the zaber stage with a reminder to change to ASCII protocol in zaber console
        # TODO: fix error handling when no zaber stage is connected at all, it just crashes right now
        move_position = self.hyper_config['single_um']
        try: 
            self.zaber_stage.connect()
        except Exception as e:
            messagebox.showerror("Connection Error", f'Could not connect to Zaber stage. Make sure that the protocol is set to ASCII in Zaber console: {e}')

        try:
            self.zaber_stage.move_absolute_um(move_position)
            print(f"[INFO] Stage moved to {move_position} µm successfully.")
        except Exception as e:
            messagebox.showerror("Stage Move Error", f"Error moving stage: {e}")

    
    def create_mask(self):
        if self.data is None or len(np.shape(self.data)) != 3:
            messagebox.showerror("Data Error", "No valid data available. Try acquiring an image first.")
            return

        selected_channel = self.rpoc_channel_var.get()

        if selected_channel not in self.config["channel_names"]:
            messagebox.showerror("Selection Error", "Please select a valid input channel.")
            return

        channel_index = self.config["channel_names"].index(selected_channel)

        if channel_index >= np.shape(self.data)[0]:
            messagebox.showerror("Data Mismatch", f"No data occupies channel {selected_channel}. Try acquiring an image.")
            return

        selected_image = self.data[channel_index] 

        mask_window = tk.Toplevel(self.root)
        mask_window.title(f'RPOC Mask Editor - {selected_channel}')
        RPOC(mask_window, image=selected_image) 

    def update_rpoc_options(self):
        if self.config["channel_names"]:
            if self.rpoc_channel_var.get() not in self.config["channel_names"]:
                self.rpoc_channel_var.set(self.config["channel_names"][0])  
        else:
            self.rpoc_channel_var.set("No channels available")


    def finalize_selection(self, event):
        current_text = self.rpoc_channel_var.get().strip()

        if current_text in self.config["channel_names"]:
            self.show_feedback(self.rpoc_channel_entry) 
        else:
            messagebox.showerror("Invalid Selection", f"'{current_text}' is not a valid channel.")  

    def update_mask(self):
        # load mask button function
        file_path = filedialog.askopenfilename(
            title="Select Mask File",
            filetypes=[("Mask Files", "*.mask *.json *.txt"), ("All Files", "*.*")]
        )
        if file_path:
            filename = os.path.basename(file_path)
            self.mask_file_path.set(filename)
        else:
            self.mask_file_path.set("No mask loaded")

    def update_config(self):
        for key, entry in self.param_entries.items():
            value = entry.get().strip()
            try:
                if key in ['ao_chans', 'ai_chans', 'channel_names']:
                    channels = [v.strip() for v in value.split(',') if v.strip()]
                    if channels != self.config[key]:
                        self.config[key] = channels
                        self.show_feedback(entry)
                        self.update_rpoc_options() 
                elif key == 'zaber_chan':
                    if value != self.config['zaber_chan']:  
                        if self.zaber_stage.is_connected():
                            self.zaber_stage.disconnect()
                            print(f"[INFO] Disconnected from previous Zaber stage at {self.config['zaber_chan']}.")

                        self.config[key] = value 

                        try:
                            self.zaber_stage.port = value
                            self.zaber_stage.connect()
                            print(f"[INFO] Successfully connected to Zaber stage at {value}.")
                        except Exception as e:
                            messagebox.showerror('Connection Error', 
                                                f'Could not connect to Zaber stage on port {value}.\n'
                                                f'Make sure the connection is on ASCII protocol in Zaber console.\n\nError: {e}')
                            return 

                        self.show_feedback(entry)  
                elif key == 'device':
                    if value != self.config[key]:
                        self.config[key] = value
                        self.show_feedback(entry)
                elif key in ['amp_x', 'amp_y', 'rate', 'dwell']:
                    if float(value) != self.config[key]:
                        self.config[key] = float(value)
                        self.show_feedback(entry)
                else:
                    if int(value) != self.config[key]:
                        self.config[key] = int(value)
                        self.show_feedback(entry)
                        
            except ValueError:
                messagebox.showerror('Error', f'Invalid value for {key}. Please check your input.')
                return  

        self.update_rpoc_options()
        self.toggle_hyperspectral_fields()
        self.toggle_save_options()
        self.toggle_rpoc_fields()

            
    def show_feedback(self, widget):
        local_style = ttk.Style()
        local_style.configure("Feedback.TEntry", fieldbackground="lightgreen")

        widget.configure(style="Feedback.TEntry")  
        self.root.after(500, lambda: widget.configure(style="TEntry"))  #
            
    def browse_save_path(self):
        # open file selector when the file folder emoji is pressed
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
            self.path_frame.winfo_children()[1].configure(state='normal')
            self.continuous_button.configure(state='disabled')
        else:
            self.save_num_entry.configure(state='disabled')
            self.save_file_entry.configure(state='disabled')
            self.path_frame.winfo_children()[1].configure(state='disabled')
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
        state = "normal" if self.rpoc_enabled.get() else "disabled"

        for widget in parent.winfo_children():
            if widget != self.rpoc_checkbutton:
                widget.configure(state=state)
        
        self.update_rpoc_options()  


    def close(self):
        # make sure closing the window also stops the code, basically just a cleanup function
        self.running = False
        self.zaber_stage.disconnect()
        self.root.quit()
        self.root.destroy()
        os._exit(0)