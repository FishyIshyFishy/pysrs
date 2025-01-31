import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw

class DrawMaskApp:
    def __init__(self, root, image=None):
        self.root = root
        self.root.title('Draw Mask')
        self.root.geometry('1000x1000')

        if image is not None:
            self.image = image.convert('L')
        else:
            self.image = Image.open('data/image.jpg').convert('L')
            self.image = self.image.copy().resize((400, 400))

        self.tk_image = ImageTk.PhotoImage(self.image)

    def create_widgets(self):
        self.canvas = tk.Canvas(root, width=self.image.width, height=self.image.height)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, padx=10, pady=10)

        self.create_mask_button = tk.Button(root, text='Create Mask', command=self.open_mask_window)
        self.create_mask_button.pack()

    def open_mask_window(self):
        self.mask_window = tk.Toplevel(self.root)
        self.mask_window.title('Draw Mask')
        self.mask_window.geometry('600x600')

        self.mask_image = self.image.copy().convert('RGB')
        self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)

        self.mask_canvas = tk.Canvas(self.mask_window, width=self.mask_image.width, height=self.mask_image.height)
        self.mask_canvas.pack()

        self.mask_image_id = self.mask_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_mask_image)

        self.mask = Image.new('L', self.mask_image.size, 0)
        self.draw = ImageDraw.Draw(self.mask)

        self.mask_canvas.bind('<ButtonPress-1>', self.start_drawing)
        self.mask_canvas.bind('<B1-Motion>', self.draw_mask)
        self.mask_canvas.bind('<ButtonRelease-1>', self.stop_drawing)

        self.drawing = False
        self.points = []

        self.threshold = tk.DoubleVar()
        self.threshold.set(128)
        self.threshold_slider = tk.Scale(self.mask_window, from_=0, to=255, orient=tk.HORIZONTAL, variable=self.threshold, label='Threshold')
        self.threshold_slider.pack()

        self.fill_loop_var = tk.BooleanVar()
        self.fill_loop_checkbox = tk.Checkbutton(self.mask_window, text='Fill Loop', variable=self.fill_loop_var)
        self.fill_loop_checkbox.pack()

        self.save_mask_button = tk.Button(self.mask_window, text='Save Mask', command=self.save_mask)
        self.save_mask_button.pack()

    def start_drawing(self, event):
        self.drawing = True
        self.last_x, self.last_y = event.x, event.y
        self.points = [(self.last_x, self.last_y)]

    def draw_mask(self, event):
        if self.drawing:
            self.draw.line([self.last_x, self.last_y, event.x, event.y], fill=255, width=2)

            draw = ImageDraw.Draw(self.mask_image)
            draw.line([self.last_x, self.last_y, event.x, event.y], fill='red', width=2)

            self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)
            self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

            self.last_x, self.last_y = event.x, event.y
            self.points.append((self.last_x, self.last_y))

    def stop_drawing(self, event):
        self.drawing = False
        if len(self.points) > 2:
            self.draw.line([self.points[-1], self.points[0]], fill=255, width=2)
            draw = ImageDraw.Draw(self.mask_image)
            draw.line([self.points[-1], self.points[0]], fill='red', width=2)
            self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)
            self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

            if self.fill_loop_var.get():
                self.draw.polygon(self.points, outline=255, fill=255)
                draw.polygon(self.points, outline='red', fill='red')
                self.tk_mask_image = ImageTk.PhotoImage(self.mask_image)
                self.mask_canvas.itemconfig(self.mask_image_id, image=self.tk_mask_image)

    def save_mask(self):
        mask_path = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG files', '*.png')])
        if mask_path:
            self.mask.save('data/' + str(mask_path))

if __name__ == '__main__':
    root = tk.Tk()
    app = DrawMaskApp(root)
    root.mainloop()