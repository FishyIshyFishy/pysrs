import tkinter as tk
from gui import GUI

if __name__ == '__main__':
    root = tk.Tk()
    root.config(bg='#3A3A3A')
    app = GUI(root)
    root.mainloop()
