import tkinter

import rasterio
from rasterio.plot import show

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

import numpy as np

from pymavlink import mavutil

from math import sqrt

import pyproj

crs_osgb = pyproj.CRS.from_epsg(27700)
lat_lon_to_east_north = pyproj.Transformer.from_crs(crs_osgb.geodetic_crs, crs_osgb)

drone_track = []
poi_list = []

root = tkinter.Tk()
root.wm_title("Map view")

fig = Figure(figsize=(5, 4), dpi=100)
ax = fig.add_subplot()

drone_line, = ax.plot([p[0] for p in drone_track],[p[1] for p in drone_track],'g-')
drone_marker, = ax.plot([],[],'gx')
poi_line, = ax.plot([p[0] for p in poi_list],[p[1] for p in poi_list],'b^')

connect_str = 'tcp:localhost:5762'
mav_connection = mavutil.mavlink_connection(connect_str)
print(f'Connected to {connect_str}')

num_loops = 0
def timer_loop():
    global num_loops
    num_loops += 1
    """Process the next waiting MAVLINK message and repeat after 1ms.
    Calling this starts a new timed thread alongside GUI actions."""
    msg = mav_connection.recv_match(type=['HEARTBEAT',
                                          'GLOBAL_POSITION_INT'
                                               ], blocking=False)
    if num_loops>1000:
        if msg:
            mav_connection.mav.request_data_stream_send(msg.get_srcSystem(),
                                                        msg.get_srcComponent(),
                                                        mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
            if msg.get_type()=='GLOBAL_POSITION_INT':
                x,y = lat_lon_to_east_north.transform(msg.lat/1e7, msg.lon/1e7)
                print(msg.lat/1e7,msg.lon/1e7)
                print(x,y)
                drone_track.append((x,y))
                drone_line.set_data([p[0] for p in drone_track],[p[1] for p in drone_track])
                drone_marker.set_data(x,y)
                canvas.draw()
                num_loops = 0
    root.after(1, timer_loop)

base_map = rasterio.open('llanbedr_rgb.tif')
show(base_map, ax=ax)

tile_limits = ax.axis()

canvas = FigureCanvasTkAgg(fig, master=root)  # A tk.DrawingArea.
canvas.draw()

def click_handler(e):
    poi_list.append((e.xdata, e.ydata))
    poi_line.set_data([p[0] for p in poi_list],[p[1] for p in poi_list])
    canvas.draw()

canvas.mpl_connect("button_press_event", click_handler)

var_mouse = tkinter.StringVar(master=root, value='Current coordinates')
label_mouse = tkinter.Label(master=root, textvariable=var_mouse)

var_dist = tkinter.StringVar(master=root, value="Distances\nDrone:\t0.0")
label_dist = tkinter.Label(master=root, textvariable=var_dist)

def distance(x1,y1,x2,y2):
    return sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2))

def hover_handler(e):
    if drone_track:
        d = distance(e.xdata,e.ydata,drone_track[-1][0],drone_track[-1][1])
        var_dist.set(f'Distances\nDrone\t{int(d)}')

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

def pan_right():
    limits = ax.axis()
    pan_factor = 0.3
    xmin = limits[0] + int(pan_factor*(limits[1] - limits[0]))
    xmax = limits[1] + int(pan_factor*(limits[1] - limits[0]))
    if xmax > tile_limits[1]:
        xmin = tile_limits[1] - (xmax-xmin)
        xmax = tile_limits[1]
    ax.axis([xmin,xmax,limits[2],limits[3]])
    canvas.draw()

def pan_left():
    limits = ax.axis()
    pan_factor = 0.3
    xmin = limits[0] - int(pan_factor*(limits[1] - limits[0]))
    xmax = limits[1] - int(pan_factor*(limits[1] - limits[0]))
    if xmin < tile_limits[0]:
        xmax = tile_limits[0] + (xmax-xmin)
        xmin = tile_limits[0]
    ax.axis([xmin,xmax,limits[2],limits[3]])
    canvas.draw()

def zoom_reset():
    ax.axis(tile_limits)
    canvas.draw()

frame_zoom = tkinter.Frame(master=root)

button_zoom_in = tkinter.Button(master=frame_zoom, text="Zoom In", command=zoom_in)
button_zoom_in.grid(column=0,row=0)

button_zoom_reset = tkinter.Button(master=frame_zoom, text="Reset Zoom", command=zoom_reset)
button_zoom_reset.grid(column=1,row=1)

button_pan_right = tkinter.Button(master=frame_zoom, text="Pan right", command=pan_right)
button_pan_right.grid(column=2,row=1)

button_pan_left = tkinter.Button(master=frame_zoom, text="Pan left", command=pan_left)
button_pan_left.grid(column=0,row=1)

button_quit = tkinter.Button(master=root, text="Quit", command=root.destroy)

# Packing order is important. Widgets are processed sequentially and if there
# is no space left, because the window is too small, they are not displayed.
# The canvas is rather flexible in its size, so we pack it last which makes
# sure the UI controls are displayed as long as possible.
button_quit.pack(side=tkinter.BOTTOM)
#toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
#label_mouse.pack(side=tkinter.TOP)
label_dist.pack(side=tkinter.TOP)
frame_zoom.pack(side=tkinter.RIGHT)
canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)

timer_loop()
tkinter.mainloop()
