import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw

class DrawMaskApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Draw Mask")
        self.root.geometry("1000x1000")

        self.path = "image.jpg"  
        self.image = Image.open(self.path).convert("RGB")
        self.image = self.image.copy().resize((400, 400))
        self.tk_image = ImageTk.PhotoImage(self.image)

        self.canvas = tk.Canvas(root, width=self.image.width, height=self.image.height)
        self.canvas.pack()

        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.mask = Image.new("L", self.image.size, 0)  #
        self.draw = ImageDraw.Draw(self.mask)

        self.canvas.bind("<ButtonPress-1>", self.start_drawing)
        self.canvas.bind("<B1-Motion>", self.draw_mask)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drawing)

        self.drawing = False

    def start_drawing(self, event):
        self.drawing = True
        self.last_x, self.last_y = event.x, event.y

    def draw_mask(self, event):
        if self.drawing:
            self.draw.line([self.last_x, self.last_y, event.x, event.y], fill=255, width=10)

            draw = ImageDraw.Draw(self.image)
            draw.line([self.last_x, self.last_y, event.x, event.y], fill="white", width=10)

            self.tk_image = ImageTk.PhotoImage(self.image)
            self.canvas.itemconfig(self.image_id, image=self.tk_image)

            self.last_x, self.last_y = event.x, event.y

    def stop_drawing(self, event):
        self.drawing = False

if __name__ == "__main__":
    root = tk.Tk()
    app = DrawMaskApp(root)
    root.mainloop()
