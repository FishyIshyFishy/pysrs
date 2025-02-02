import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk, ImageDraw, ImageOps
import numpy as np

class ColorSlider(tk.Canvas):
    def __init__(self, master, min_val=0, max_val=255, init_val=0, width=200, height=20,
                 fill_side='left', accent_color='#4A90E2', bg_color='#505050', command=None, **kwargs):
        super().__init__(master, width=width, height=height, bg=bg_color, highlightthickness=0, **kwargs)
        self.min_val = min_val
        self.max_val = max_val
        self.value = init_val
        self.slider_width = width
        self.slider_height = height
        self.fill_side = fill_side
        self.accent_color = accent_color
        self.track_color = '#808080'  # neutral track color
        self.command = command
        self.knob_radius = height // 2
        self.margin = self.knob_radius  # leave room for the knob on either side
        self.bind("<Button-1>", self.click)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        self.draw_slider()
    
    def draw_slider(self):
        self.delete("all")
        self.create_line(self.margin, self.slider_height/2,
                         self.slider_width - self.margin, self.slider_height/2,
                         fill=self.track_color, width=4)
        pos = self.margin + (self.value - self.min_val) / (self.max_val - self.min_val) * (self.slider_width - 2*self.margin)

        if self.fill_side == 'left':
            self.create_line(self.margin, self.slider_height/2, pos, self.slider_height/2,
                             fill=self.accent_color, width=4)
        else: 
            self.create_line(pos, self.slider_height/2, self.slider_width - self.margin, self.slider_height/2,
                             fill=self.accent_color, width=4)
        self.create_oval(pos - self.knob_radius, self.slider_height/2 - self.knob_radius,
                         pos + self.knob_radius, self.slider_height/2 + self.knob_radius,
                         fill='#D0D0D0', outline="")
    
    def click(self, event):
        self.set_value_from_event(event.x)
    
    def drag(self, event):
        self.set_value_from_event(event.x)
    
    def release(self, event):
        self.set_value_from_event(event.x)
    
    def set_value_from_event(self, x):
        x = max(self.margin, min(self.slider_width - self.margin, x))
        ratio = (x - self.margin) / (self.slider_width - 2*self.margin)
        new_val = int(self.min_val + ratio * (self.max_val - self.min_val))
        self.value = new_val
        self.draw_slider()
        if self.command:
            self.command(new_val)
    
    def get(self):
        return self.value
    
    def set(self, value):
        self.value = value
        self.draw_slider()
        if self.command:
            self.command(value)

class RPOC:
    def __init__(self, root, image=None):
        self.root = root

        # TODO: move this into a config
        style = ttk.Style()
        style.theme_use('clam')
        self.bg_color = '#3A3A3A'
        self.fg_color = '#D0D0D0'
        self.highlight_color = '#4A90E2'
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        style.configure("TButton", background='#444', foreground=self.fg_color, padding=6)
        style.configure("TCheckbutton", background=self.bg_color, foreground=self.fg_color)

        self.root.title('RPOC - Dark Mode')
        self.root.geometry('600x600')
        self.root.configure(bg=self.bg_color)
         
        try:
            if image is not None:
                if isinstance(image, np.ndarray):
                    image = 255 * image / np.max(image)
                    image = Image.fromarray(image.astype(np.uint8))
                grayscale = image.convert('L')
            else:
                grayscale = Image.open(r'C:\Users\ishaa\Documents\ZhangLab\RamanSCPI\pysrs\pysrs\data\image.jpg').convert('L')  # for testing
                grayscale = grayscale.copy().resize((400, 400))
            # convert to RGB (so display is in color) even though it’s grayscale
            self.image = Image.merge("RGB", (grayscale, grayscale, grayscale))
        except FileNotFoundError:
            print("Error: Image not found. Make sure 'data/image.jpg' exists.")
            return
        
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.create_widgets()
    
    def create_widgets(self):
        self.canvas = tk.Canvas(self.root, width=self.image.width, height=self.image.height,
                                bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.create_mask_button = ttk.Button(self.root, text='Create Mask', command=self.open_mask_window)
        self.create_mask_button.pack(pady=(0, 10))
    
    def get_base_image(self):
        if hasattr(self, 'invert_var') and self.invert_var.get():
            return ImageOps.invert(self.image)
        return self.image

    def update_mask_image(self):
        base = self.get_base_image()
        gray = base.convert('L')
        lower = self.lower_threshold.get()
        upper = self.upper_threshold.get()

        gray_np = np.array(gray)
        rgb_np = np.stack([gray_np, gray_np, gray_np], axis=-1)
        rgb_np[gray_np < lower] = [0, 0, 255] 
        rgb_np[gray_np > upper] = [255, 0, 0]  
        thresholded = Image.fromarray(rgb_np.astype('uint8'), 'RGB')
        
        mask_np = np.array(self.binary_mask)
        drawn = mask_np == 255
        thresholded_np = np.array(thresholded)
        thresholded_np[drawn] = [255, 0, 0]
        thresholded = Image.fromarray(thresholded_np, 'RGB')
        
        self.mask_image = thresholded
        self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)
        self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)
    
    def get_mask_applied_image(self):
        base = self.get_base_image()
        black_bg = Image.new("RGB", base.size, (0, 0, 0))
        return Image.composite(base, black_bg, self.binary_mask)
    
    def update_preview(self):
        preview = self.get_mask_applied_image()
        self.tk_preview_image = ImageTk.PhotoImage(preview)
        self.preview_canvas.itemconfig(self.preview_image_id, image=self.tk_preview_image)
    
    def update_images(self, event=None):
        self.update_mask_image()
        self.update_preview()
    
    def open_mask_window(self):
        self.mask_window = tk.Toplevel(self.root)
        self.mask_window.title('Draw Mask')
        self.mask_window.geometry('800x600')
        self.mask_window.configure(bg=self.bg_color)
        
        self.binary_mask = Image.new('L', self.image.size, 0)
        self.draw = ImageDraw.Draw(self.binary_mask)
  
        self.lower_threshold = tk.IntVar(value=80)
        self.upper_threshold = tk.IntVar(value=180)
        self.invert_var = tk.BooleanVar(value=False)
        self.eraser_var = tk.BooleanVar(value=False)  

        display_frame = ttk.Frame(self.mask_window)
        display_frame.pack(padx=10, pady=10, fill='both', expand=True)

        base = self.get_base_image()
        gray = base.convert('L')
        gray_np = np.array(gray)
        rgb_np = np.stack([gray_np, gray_np, gray_np], axis=-1)
        rgb_np[gray_np < self.lower_threshold.get()] = [0, 0, 255]
        rgb_np[gray_np > self.upper_threshold.get()] = [255, 0, 0]
        init_mask_image = Image.fromarray(rgb_np.astype('uint8'), 'RGB')
        self.mask_image = init_mask_image
        self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)

        self.mask_canvas = tk.Canvas(display_frame, width=self.mask_image.width, height=self.mask_image.height,
                                     bg=self.bg_color, highlightthickness=0)
        self.mask_canvas.pack(side=tk.LEFT, padx=5)
        self.mask_image_id = self.mask_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_mask_image)

        preview_img = self.get_mask_applied_image()
        self.tk_preview_image = ImageTk.PhotoImage(preview_img)
        self.preview_canvas = tk.Canvas(display_frame, width=self.mask_image.width, height=self.mask_image.height,
                                        bg=self.bg_color, highlightthickness=0)
        self.preview_canvas.pack(side=tk.RIGHT, padx=5)
        self.preview_image_id = self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_preview_image)

        controls_frame = ttk.Frame(self.mask_window)
        controls_frame.pack(padx=10, pady=10, fill='x')

        self.lower_slider = ColorSlider(
            controls_frame, min_val=0, max_val=255, init_val=self.lower_threshold.get(),
            width=200, height=20, fill_side='left', accent_color=self.highlight_color, bg_color='#505050',
            command=lambda val: [self.lower_threshold.set(val), self.update_images()]
        )
        self.lower_slider.pack(side=tk.LEFT, padx=5, pady=5)

        self.upper_slider = ColorSlider(
            controls_frame, min_val=0, max_val=255, init_val=self.upper_threshold.get(),
            width=200, height=20, fill_side='right', accent_color='#FF0000', bg_color='#505050',
            command=lambda val: [self.upper_threshold.set(val), self.update_images()]
        )
        self.upper_slider.pack(side=tk.LEFT, padx=5, pady=5)

        self.invert_checkbox = ttk.Checkbutton(
            controls_frame, text='Invert Image', variable=self.invert_var, command=self.update_images
        )
        self.invert_checkbox.pack(side=tk.LEFT, padx=5, pady=5)
 
        self.fill_loop_var = tk.BooleanVar(value=True)
        self.fill_loop_checkbox = ttk.Checkbutton(
            controls_frame, text='Fill Loop', variable=self.fill_loop_var
        )
        self.fill_loop_checkbox.pack(side=tk.LEFT, padx=5, pady=5)

        self.eraser_checkbox = ttk.Checkbutton(
            controls_frame, text='Eraser Tool', variable=self.eraser_var
        )
        self.eraser_checkbox.pack(side=tk.LEFT, padx=5, pady=5)

        self.save_mask_button = ttk.Button(controls_frame, text='Save Mask', command=self.save_mask)
        self.save_mask_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.mask_canvas.bind('<ButtonPress-1>', self.start_drawing)
        self.mask_canvas.bind('<B1-Motion>', self.draw_mask)
        self.mask_canvas.bind('<ButtonRelease-1>', self.stop_drawing)
        
        self.update_images() 
    
    def start_drawing(self, event):
        self.drawing = True
        self.last_x, self.last_y = event.x, event.y
        self.points = [(self.last_x, self.last_y)]
    
    def draw_mask(self, event):
        if self.drawing:
            fill_val = 0 if self.eraser_var.get() else 255
            self.draw.line([self.last_x, self.last_y, event.x, event.y], fill=fill_val, width=2)
            draw_display = ImageDraw.Draw(self.mask_image)
            draw_color = (0, 0, 0) if self.eraser_var.get() else (255, 0, 0)
            draw_display.line([self.last_x, self.last_y, event.x, event.y], fill=draw_color, width=2)
            self.last_x, self.last_y = event.x, event.y
            self.points.append((self.last_x, self.last_y))
            self.update_images()
    
    def stop_drawing(self, event):
        self.drawing = False
        if len(self.points) > 2:
            fill_val = 0 if self.eraser_var.get() else 255
            self.draw.line([self.points[-1], self.points[0]], fill=fill_val, width=2)
            draw_display = ImageDraw.Draw(self.mask_image)
            draw_color = (0, 0, 0) if self.eraser_var.get() else (255, 0, 0)
            draw_display.line([self.points[-1], self.points[0]], fill=draw_color, width=2)
            if self.fill_loop_var.get():
                self.draw.polygon(self.points, outline=fill_val, fill=fill_val)
                draw_display.polygon(self.points, outline=draw_color, fill=draw_color)
            self.update_images()
    
    def save_mask(self):
        mask_path = filedialog.asksaveasfilename(defaultextension='.png',
                                                 filetypes=[('PNG files', '*.png')])
        if mask_path:
            self.binary_mask.save(mask_path)

if __name__ == '__main__':
    root = tk.Tk()
    app = RPOC(root)
    root.mainloop()
