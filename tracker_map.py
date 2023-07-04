import rasterio
from rasterio.plot import show

import tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

import pyproj

import argparse

from math import sqrt

crs_osgb = pyproj.CRS.from_epsg(27700)
lat_lon_to_east_north = pyproj.Transformer.from_crs(crs_osgb.geodetic_crs, crs_osgb)
east_north_to_lat_lon = pyproj.Transformer.from_crs(crs_osgb, crs_osgb.geodetic_crs)

class MapTrack:

    def __init__(self, name, parent_map, track_style='-', head_style='x'):
        self.name = name
        self.parent_map = parent_map
        self.track_line, = parent_map.ax.plot([],[],track_style)
        self.head_marker, = parent_map.ax.plot([],[],head_style)
        self.track_points = []

    def update(self,x,y):
        self.track_points.append((x,y))
        self.head_marker.set_data([x],[y])
        self.track_line.set_data([p[0] for p in self.track_points],
                                 [p[1] for p in self.track_points])
        
    def update_latlon(self,lat,lon):
        x,y = lat_lon_to_east_north.transform(lat, lon)
        self.update(x,y)


class TkTrackerMap(FigureCanvasTkAgg):

    def __init__(self, master, tile_file_name):
        fig = Figure(figsize=(5, 4), dpi=100)
        super().__init__(fig,master=master)
        self.ax = fig.add_subplot()
        base_map = rasterio.open(tile_file_name)
        show(base_map, ax=self.ax)
        self.tile_limits = self.ax.axis()
        self.tracks = []

    def add_track(self,name, track_style='-', head_style='x'):
        new_track = MapTrack(name, self, track_style, head_style)
        self.tracks.append(new_track)
        return new_track
    
def distance(x1,y1,x2,y2):
    return sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2))

class TrackerApp:

    def __init__(self, tile_file_name, mav_connect_str):
        self.root = tkinter.Tk()
        self.root.wm_title("Tracker Map")
        self.tracker_map = TkTrackerMap(self.root, 'llanbedr_rgb.tif')
        self.misper_track = self.tracker_map.add_track('MISPER')
        self.poi_tracks = []
        # click event handler and toolbar work together
        self.click_mode = None
        self.tracker_map.mpl_connect("button_press_event", self.click_handler)
        track_toolbar = self.build_track_toolbar()
        # display coordinates etc
        self.status_msgs = tkinter.StringVar(master=self.root, value='Status')
        status_label = tkinter.Label(master=self.root, textvariable=self.status_msgs, height=3)
        self.tracker_map.mpl_connect("motion_notify_event", self.hover_handler)
        # include built-in toolbar for map zoom and pan etc
        self.nav_toolbar = NavigationToolbar2Tk(self.tracker_map, self.root, pack_toolbar=False)
        self.nav_toolbar.update()
        # assemble the GUI
        self.nav_toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        status_label.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        track_toolbar.pack(side=tkinter.TOP)
        self.tracker_map.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)

    def set_click_mode(self, new_mode):
        self.click_mode = new_mode
        if new_mode:
            nav_state = tkinter.DISABLED
        else:
            nav_state = tkinter.NORMAL
        for btn in self.nav_toolbar._buttons:
            self.nav_toolbar._buttons[btn]['state'] = nav_state

    def click_handler(self,e):
        if self.click_mode=='MISPER':
            self.misper_track.update(e.xdata,e.ydata)
        elif self.click_mode=='POI':
            next_poi = len(self.poi_tracks)+1
            new_poi = self.tracker_map.add_track(f'POI{next_poi}', head_style='b^')
            self.poi_tracks.append(new_poi)
            new_poi.update(e.xdata,e.ydata)
        self.tracker_map.draw()

    def build_track_toolbar(self):
        toolbar_frame = tkinter.Frame(master=self.root)
        nav_button = tkinter.Button(master=toolbar_frame, text='NAV', command=lambda: self.set_click_mode(None))
        nav_button.grid(row=0,column=0)
        misper_button = tkinter.Button(master=toolbar_frame, text='MISPER', command=lambda: self.set_click_mode('MISPER'))
        misper_button.grid(row=0,column=1)
        poi_button = tkinter.Button(master=toolbar_frame, text='POI', command=lambda: self.set_click_mode('POI'))
        poi_button.grid(row=0,column=2)
        fly_button = tkinter.Button(master=toolbar_frame, text='FLY', command=lambda: self.set_click_mode('FLY'))
        fly_button.grid(row=0,column=3)
        return toolbar_frame
    
    def hover_handler(self, e):
        if e.xdata:
            lat, lon = east_north_to_lat_lon.transform(e.xdata, e.ydata)
            self.status_msgs.set(f'''Cursor {lat:.6f},{lon:.6f}''')
        else:
            self.status_msgs.set('')

    def run(self):
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--tile_file',
                        help='Path to GeoTIFF file for basemap',
                        default='llanbedr_rgb.tif')
    parser.add_argument('-c', '--connect',
                        help='Connection string e.g. tcp:localhost:14550',
                        default=None)
    args = parser.parse_args()
    app = TrackerApp(args.tile_file, args.connect)
    app.run()


if __name__=='__main__':
    main()