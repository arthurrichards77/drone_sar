import rasterio
from rasterio.plot import show

import tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

import pyproj

crs_osgb = pyproj.CRS.from_epsg(27700)
lat_lon_to_east_north = pyproj.Transformer.from_crs(crs_osgb.geodetic_crs, crs_osgb)

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

    def add_track(self,name, track_style='-', head_style='x'):
        return MapTrack(name, self, track_style, head_style)
    
class TrackerApp:

    def __init__(self):
        self.root = tkinter.Tk()
        self.root.wm_title("Tracker Map")
        self.tracker_map = TkTrackerMap(self.root, 'llanbedr_rgb.tif')
        self.doodle_track = self.tracker_map.add_track('Doodle')
        self.tracker_map.mpl_connect("button_press_event", self.click_handler)
        self.tracker_map.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)

    def run(self):
        self.root.mainloop()

    def click_handler(self,e):
        self.doodle_track.update(e.xdata,e.ydata)
        self.tracker_map.draw()

def main():
    
    app = TrackerApp()
    app.run()

if __name__=='__main__':
    main()