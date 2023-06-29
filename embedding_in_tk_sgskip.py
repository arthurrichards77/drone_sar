"""
===============
Embedding in Tk
===============

"""
import os

import tkinter

import rasterio
from rasterio.plot import show

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

import numpy as np


root = tkinter.Tk()
root.wm_title("Embedding in Tk")

fig = Figure(figsize=(5, 4), dpi=100)
ax = fig.add_subplot()

track = []

#tiles_path = 'Download_2292886/raster-25k_5099296/sh'
#data_files = os.listdir(tiles_path)
#map_files = [f for f in data_files if f.endswith('.tif')]
#base_maps = [rasterio.open(tiles_path + '/' + f) for f in map_files]
#for m in base_maps:
#    show(m, ax=ax, cmap='Blues')

base_map = rasterio.open('llanbedr_rgb.tif')
show(base_map, ax=ax)

limits = ax.axis()
print(limits)

line, = ax.plot([p[0] for p in track],[p[1] for p in track],'gx-')

canvas = FigureCanvasTkAgg(fig, master=root)  # A tk.DrawingArea.
canvas.draw()

# pack_toolbar=False will make it easier to use a layout manager later on.
#toolbar = NavigationToolbar2Tk(canvas, root, pack_toolbar=False)
#toolbar.update()

def button_handler(e):
    track.append((e.xdata, e.ydata))
    line.set_data([p[0] for p in track],[p[1] for p in track])
    canvas.draw()

canvas.mpl_connect("button_press_event", button_handler)

var_mouse = tkinter.StringVar(master=root, value='Current coordinates')
label_mouse = tkinter.Label(master=root, textvariable=var_mouse)

def hover_handler(e):
    var_mouse.set(f'{e.xdata},{e.ydata}')

canvas.mpl_connect("motion_notify_event", hover_handler)

def zoom_in():
    limits = ax.axis()
    zoom_factor = 0.75
    ctr_x = 0.5*(limits[0]+limits[1])
    ctr_y = 0.5*(limits[2]+limits[3])
    xmin = ctr_x - int(zoom_factor*(ctr_x - limits[0]))
    xmax = ctr_x + int(zoom_factor*(limits[1] - ctr_x))
    ymin = ctr_y - int(zoom_factor*(ctr_y - limits[2]))
    ymax = ctr_y + int(zoom_factor*(limits[3] - ctr_y))
    ax.axis([xmin,xmax,ymin,ymax])
    canvas.draw()

button_zoom = tkinter.Button(master=root, text="Zoom In", command=zoom_in)

button_quit = tkinter.Button(master=root, text="Quit", command=root.destroy)


# Packing order is important. Widgets are processed sequentially and if there
# is no space left, because the window is too small, they are not displayed.
# The canvas is rather flexible in its size, so we pack it last which makes
# sure the UI controls are displayed as long as possible.
button_quit.pack(side=tkinter.BOTTOM)
#toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
label_mouse.pack(side=tkinter.TOP)
button_zoom.pack(side=tkinter.RIGHT)
canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)

tkinter.mainloop()
