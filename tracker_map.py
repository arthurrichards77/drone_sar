import rasterio
from rasterio.plot import show

import tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

import functools

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

    def get_current_pos(self):
        if self.track_points:
            return(self.track_points[-1])


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
    
class TrackerToolbar(tkinter.Frame):

    def __init__(self, master, parent_app):
        super().__init__(master=master)
        self.parent_app = parent_app
        self.buttons = {}
        mode_button_list = ['NAV','MISPER','POI','FLY']
        for (ii,txt) in enumerate(mode_button_list):
            self.buttons[txt] = tkinter.Button(master=self,
                                               text=txt,
                                               command=functools.partial(parent_app.set_click_mode, new_mode=txt))
            self.buttons[txt].grid(row=0,column=ii)

def distance(p1,p2):
    x1,y1 = p1
    x2,y2 = p2
    return sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2))

class TrackerApp:

    def __init__(self, tile_file_name, mav_connect_str):
        self.root = tkinter.Tk()
        self.root.wm_title("Tracker Map")
        self.tracker_map = TkTrackerMap(self.root, 'llanbedr_rgb.tif')
        self.tracks = {}
        self.tracks['MISPER'] = self.tracker_map.add_track('MISPER')
        # click event handler and toolbar work together
        self.click_mode = None
        self.tracker_map.mpl_connect("button_press_event", self.click_handler)
        self.track_toolbar = TrackerToolbar(self.root, self)
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
        self.track_toolbar.pack(side=tkinter.TOP)
        self.tracker_map.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)

    def set_click_mode(self, new_mode):
        self.click_mode = new_mode
        print(f'Click mode is {new_mode}')
        if new_mode=='NAV':
            nav_state = tkinter.NORMAL
        else:
            nav_state = tkinter.DISABLED
        for btn in self.nav_toolbar._buttons:
            self.nav_toolbar._buttons[btn]['state'] = nav_state
        #for btn in self.track_toolbar.buttons:
        #    if btn==new_mode:
        #        self.track_toolbar.buttons[btn]['state'] = tkinter.ACTIVE
        #    else:
        #        self.track_toolbar.buttons[btn]['state'] = tkinter.NORMAL

    def add_poi(self,x,y):
        num_poi = len([t for t in self.tracks if t.startswith('POI')])
        new_poi = f'POI{num_poi+1}'
        self.tracks[new_poi] = self.tracker_map.add_track(new_poi, head_style='b^')
        self.tracks[new_poi].update(x,y)

    def click_handler(self,e):
        if self.click_mode=='MISPER':
            self.tracks['MISPER'].update(e.xdata,e.ydata)
        elif self.click_mode=='POI':
            self.add_poi(e.xdata, e.ydata)
        elif self.click_mode=='FLY':
            print(f'Fly to {e.xdata},{e.ydata}')
        self.tracker_map.draw()
    
    def hover_handler(self, e):
        if e.xdata:
            lat, lon = east_north_to_lat_lon.transform(e.xdata, e.ydata)
            dist_msg = 'Distances: '
            for t in self.tracks:
                pos = self.tracks[t].get_current_pos()
                if pos:
                    dist_msg += f'{t}: {distance(pos,(e.xdata,e.ydata)):.0f}m; '
            self.status_msgs.set(f'''Cursor {lat:.6f},{lon:.6f}
                                 {dist_msg}''')
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