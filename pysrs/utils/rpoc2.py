import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw

class RPOC:
    def __init__(self, root, image=None):
        self.root = root
        self.root.title('rpoc testing')
        self.root.geometry('600x600')

        try:
            if image is not None:
                grayscale = image.convert('L')  # Convert to grayscale first
            else:
                grayscale = Image.open('data/image.jpg').convert('L')
                grayscale = grayscale.copy().resize((400, 400))

            self.image = Image.merge("RGB", (grayscale, grayscale, grayscale))  

        except FileNotFoundError:
            print("Error: Image not found. Make sure 'data/image.jpg' exists.")
            return

        self.tk_image = ImageTk.PhotoImage(self.image)
        self.create_widgets()

    def create_widgets(self):
        self.canvas = tk.Canvas(self.root, width=self.image.width, height=self.image.height)
        self.canvas.pack(padx=10, pady=10)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.create_mask_button = tk.Button(self.root, text='Create Mask', command=self.open_mask_window)
        self.create_mask_button.pack()

    def open_mask_window(self):
        self.mask_window = tk.Toplevel(self.root)
        self.mask_window.title('Draw Mask')
        self.mask_window.geometry('600x600')

        self.mask_image = self.image.copy()  
        self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)

        self.mask_canvas = tk.Canvas(self.mask_window, width=self.mask_image.width, height=self.mask_image.height)
        self.mask_canvas.pack()
        self.mask_image_id = self.mask_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_mask_image)

        self.binary_mask = Image.new('L', self.image.size, 0)
        self.draw = ImageDraw.Draw(self.binary_mask)

        self.threshold = tk.DoubleVar(value=128)
        self.threshold_slider = tk.Scale(
            self.mask_window, from_=0, to=255, orient=tk.HORIZONTAL, 
            variable=self.threshold, label='Threshold', command=self.apply_threshold,
            length=400,
            width=40,
            sliderlength=20
        )
        self.threshold_slider.pack()

        self.fill_loop_var = tk.BooleanVar(value=True)
        self.fill_loop_checkbox = tk.Checkbutton(self.mask_window, text='Fill Loop', variable=self.fill_loop_var)
        self.fill_loop_checkbox.pack()


        self.save_mask_button = tk.Button(self.mask_window, text='Save Mask', command=self.save_mask)
        self.save_mask_button.pack()

        self.mask_canvas.bind('<ButtonPress-1>', self.start_drawing)
        self.mask_canvas.bind('<B1-Motion>', self.draw_mask)
        self.mask_canvas.bind('<ButtonRelease-1>', self.stop_drawing)

        self.apply_threshold(self.threshold.get())

    def apply_threshold(self, threshold_value):
        threshold = int(float(threshold_value))
        
        grayscale = self.image.convert('L')  
        binary_threshold = grayscale.point(lambda p: 255 if p >= threshold else 0)

        thresholded_rgb = Image.merge("RGB", (binary_threshold, binary_threshold, binary_threshold))
        
        for x in range(self.mask_image.width):
            for y in range(self.mask_image.height):
                r, g, b = self.mask_image.getpixel((x, y))
                
                if r > g and r > b:  
                    thresholded_rgb.putpixel((x, y), (255, 0, 0))  

        self.tk_mask_image = ImageTk.PhotoImage(thresholded_rgb)
        self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

        self.mask_image = thresholded_rgb.copy()

        self.tk_mask_image = ImageTk.PhotoImage(thresholded_rgb)
        self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

    def start_drawing(self, event):
        self.drawing = True
        self.last_x, self.last_y = event.x, event.y
        self.points = [(self.last_x, self.last_y)]

    def draw_mask(self, event):
        if self.drawing:
            self.draw.line([self.last_x, self.last_y, event.x, event.y], fill=255, width=2)  

            draw_display = ImageDraw.Draw(self.mask_image)
            draw_display.line([self.last_x, self.last_y, event.x, event.y], fill=(255, 0, 0), width=2)

            self.apply_threshold(self.threshold.get())

            self.last_x, self.last_y = event.x, event.y
            self.points.append((self.last_x, self.last_y))

    def stop_drawing(self, event):
        self.drawing = False
        if len(self.points) > 2:
            self.draw.line([self.points[-1], self.points[0]], fill=255, width=2)  

            draw_display = ImageDraw.Draw(self.mask_image)
            draw_display.line([self.points[-1], self.points[0]], fill=(255, 0, 0), width=2)

            if self.fill_loop_var.get():
                self.draw.polygon(self.points, outline=255, fill=255) 
                draw_display.polygon(self.points, outline=(255, 0, 0), fill=(255, 0, 0))  

            self.apply_threshold(self.threshold.get())

    def save_mask(self):
        mask_path = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG files', '*.png')])
        if mask_path:
            self.binary_mask.save(mask_path)

if __name__ == '__main__':
    root = tk.Tk()
    app = RPOC(root)
    root.mainloop()