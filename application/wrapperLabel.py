import tkinter as tk
from tkinter import ttk

class WrapperLabel(ttk.Label):
    def __init__(self,master=None,**kwargs):
        ttk.Label.__init__(self,master,**kwargs)
        self.bind('<Configure>',lambda e: self.config(wraplength=master.winfo_width()))