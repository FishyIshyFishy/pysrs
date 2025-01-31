import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw

class DrawMaskApp:
    def __init__(self, root, image=None):
        self.root = root
        self.root.title('Draw Mask')
        self.root.geometry('600x600')

        try:
            if image is not None:
                self.image = image.convert('L')
            else:
                self.image = Image.open('data/image.jpg').convert('L')
                self.image = self.image.copy().resize((400, 400))
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

        # Image displayed on mask canvas
        self.mask_image = self.image.copy().convert('RGB')
        self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)

        self.mask_canvas = tk.Canvas(self.mask_window, width=self.mask_image.width, height=self.mask_image.height)
        self.mask_canvas.pack()
        self.mask_image_id = self.mask_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_mask_image)

        # Binary mask for thresholding
        self.binary_mask = self.image.copy()

        # Separate mask for drawing
        self.mask = Image.new('L', self.image.size, 0)
        self.draw = ImageDraw.Draw(self.mask)

        # Threshold slider
        self.threshold = tk.DoubleVar(value=128)
        self.threshold_slider = tk.Scale(
            self.mask_window, from_=0, to=255, orient=tk.HORIZONTAL, 
            variable=self.threshold, label='Threshold', command=self.apply_threshold
        )
        self.threshold_slider.pack()

        # Fill loop checkbox
        self.fill_loop_var = tk.BooleanVar()
        self.fill_loop_checkbox = tk.Checkbutton(self.mask_window, text='Fill Loop', variable=self.fill_loop_var)
        self.fill_loop_checkbox.pack()

        # Save mask button
        self.save_mask_button = tk.Button(self.mask_window, text='Save Mask', command=self.save_mask)
        self.save_mask_button.pack()

        # Event bindings for drawing
        self.mask_canvas.bind('<ButtonPress-1>', self.start_drawing)
        self.mask_canvas.bind('<B1-Motion>', self.draw_mask)
        self.mask_canvas.bind('<ButtonRelease-1>', self.stop_drawing)

        # Apply the initial threshold
        self.apply_threshold(self.threshold.get())

    def apply_threshold(self, threshold_value):
        """Apply thresholding while preserving user-drawn mask."""
        threshold = int(float(threshold_value))
        self.binary_mask = self.image.point(lambda p: 255 if p >= threshold else 0)

        # Combine thresholded mask and drawn mask
        combined_mask = Image.composite(self.mask, self.binary_mask, self.mask)
        self.tk_mask_image = ImageTk.PhotoImage(combined_mask)
        self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

    def start_drawing(self, event):
        self.drawing = True
        self.last_x, self.last_y = event.x, event.y
        self.points = [(self.last_x, self.last_y)]

    def draw_mask(self, event):
        if self.drawing:
            self.draw.line([self.last_x, self.last_y, event.x, event.y], fill=255, width=2)  # Keeps grayscale mask logic
            draw_display = ImageDraw.Draw(self.mask_image)  # Draw red on display image
            draw_display.line([self.last_x, self.last_y, event.x, event.y], fill='red', width=2)  # Draw red

            # Update the displayed mask by merging drawn and thresholded mask
            combined_mask = Image.composite(self.mask, self.binary_mask, self.mask)
            self.tk_mask_image = ImageTk.PhotoImage(combined_mask)
            self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

            self.last_x, self.last_y = event.x, event.y
            self.points.append((self.last_x, self.last_y))

    def stop_drawing(self, event):
        self.drawing = False
        if len(self.points) > 2:
            self.draw.line([self.points[-1], self.points[0]], fill=255, width=2)  # Keeps grayscale mask logic
            draw_display = ImageDraw.Draw(self.mask_image)
            draw_display.line([self.points[-1], self.points[0]], fill='red', width=2)  # Draw red

            if self.fill_loop_var.get():
                self.draw.polygon(self.points, outline=255, fill=255)  # Keeps grayscale logic
                draw_display.polygon(self.points, outline=(255, 0, 0), fill='red')  # Draw red

            # Update display after completing drawing
            combined_mask = Image.composite(self.mask, self.binary_mask, self.mask)
            self.tk_mask_image = ImageTk.PhotoImage(combined_mask)
            self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

    def save_mask(self):
        mask_path = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG files', '*.png')])
        if mask_path:
            combined_mask = Image.composite(self.mask, self.binary_mask, self.mask)
            combined_mask.save(mask_path)

if __name__ == '__main__':
    root = tk.Tk()
    app = DrawMaskApp(root)
    root.mainloop()
