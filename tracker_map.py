import rasterio
from rasterio.plot import show

import tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

import functools

import pyproj

import argparse

from math import sqrt, cos, sin, pi

from pymavlink import mavutil

import requests
import json
import warnings

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

    def plot(self):
        if self.track_points:
            self.head_marker.set_data([self.track_points[-1][0]],[self.track_points[-1][1]])
        else:
            self.head_marker.set_data([],[])
        self.track_line.set_data([p[0] for p in self.track_points],
                                 [p[1] for p in self.track_points])

    def update(self,x,y):
        self.track_points.append((x,y))
        self.plot()

    def wipe(self):
        self.track_points.clear()
        self.plot()

    def update_latlon(self,lat,lon):
        x,y = lat_lon_to_east_north.transform(lat, lon)
        self.update(x,y)

    def get_current_pos(self):
        if self.track_points:
            return(self.track_points[-1])

class RingedTrack(MapTrack):

    def __init__(self, name, parent_map, track_style='-', head_style='x'):
        super().__init__(name, parent_map, track_style, head_style)
        self.radii = []
        self.ring_lines = []

    def add_ring(self, radius, line_style='-'):
        self.radii.append(radius)
        new_ring, = self.parent_map.ax.plot([],[],line_style)
        self.ring_lines.append(new_ring)

    def plot(self):
        super().plot()
        if self.track_points:
            angles = [2*pi*kk/100 for kk in range(100)] + [0]
            num_rings = len(self.radii)
            for ii in range(num_rings):
                ctr_x, ctr_y = self.get_current_pos()
                ring_x = [ctr_x + self.radii[ii]*cos(a) for a in angles]
                ring_y = [ctr_y + self.radii[ii]*sin(a) for a in angles]
                self.ring_lines[ii].set_data(ring_x, ring_y)

class TkTrackerMap(FigureCanvasTkAgg):

    def __init__(self, master, tile_file_name):
        fig = Figure(figsize=(5, 4), dpi=100)
        super().__init__(fig,master=master)
        self.ax = fig.add_subplot()
        base_map = rasterio.open(tile_file_name)
        show(base_map, ax=self.ax)
        self.tile_limits = self.ax.axis()

    def add_track(self,name, track_style='-', head_style='x', track_type=MapTrack):
        new_track = track_type(name, self, track_style, head_style)
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
        self.buttons['CAN'] = tkinter.Button(master=self,
                                             text='CAN',
                                             command=parent_app.cancel_fly_to)
        self.buttons['CAN'].grid(row=0,column=4)

def distance(p1,p2):
    x1,y1 = p1
    x2,y2 = p2
    return sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2))

class TrackerApp:

    def __init__(self, tile_file_name, mav_connect_str, chat_url):
        self.root = tkinter.Tk()
        self.timer_count = 0
        self.root.wm_title("Tracker Map")
        self.tracker_map = TkTrackerMap(self.root, tile_file_name)
        self.tracks = {}
        # special high level track for MISPER
        self.tracks['MISPER'] = self.tracker_map.add_track('MISPER', track_type=RingedTrack)
        self.tracks['MISPER'].add_ring(350,'g-')
        self.tracks['MISPER'].add_ring(550,'m-')
        self.tracks['MISPER'].add_ring(1100,'b-')
        self.tracks['MISPER'].add_ring(1300,'y-')
        self.tracks['MISPER'].add_ring(1800,'k-')
        # another one for the pilot
        self.tracks['PILOT'] = self.tracker_map.add_track('PILOT', track_type=RingedTrack)
        self.tracks['PILOT'].add_ring(500,'r--')
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
        # connect to the MAV
        self.mav = self.setup_mav(mav_connect_str)
        self.fly_target = None
        self.tracks['TARGET'] = self.tracker_map.add_track('TARGET', track_style='', head_style='bs')
        # connect to chat server
        self.chat_url = chat_url

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

    def fly_to(self,x,y):
        print(f'Fly to {x},{y}')
        lat, lon = east_north_to_lat_lon.transform(x,y)
        print(f'That is {lat}, {lon}')
        if self.mav:
            self.fly_target = (lat,lon)
            self.tracks['TARGET'].update_latlon(lat,lon)

    def cancel_fly_to(self):
        self.fly_target = None
        self.tracks['TARGET'].wipe()

    def send_fly_target(self):
        if self.fly_target:
            self.mav.mav.set_position_target_global_int_send(
                0,  # timestamp
                1,  # target system_id
                1,  # target component id
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,  # mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VX_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VY_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VZ_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE, # |
                # mavutil.mavlink.POSITION_TARGET_TYPEMASK_FORCE_SET |
                # mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE |
                # mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE,
                int(self.fly_target[0] * 1.0e7),  # lat
                int(self.fly_target[1] * 1.0e7),  # lon
                10,  # alt
                0,  # vx
                0,  # vy
                0,  # vz
                0,  # afx
                0,  # afy
                0,  # afz
                0,  # yaw
                0,  # yawrate
            )

    def click_handler(self,e):
        if self.click_mode=='MISPER':
            self.tracks['MISPER'].update(e.xdata,e.ydata)
        elif self.click_mode=='POI':
            self.add_poi(e.xdata, e.ydata)
        elif self.click_mode=='FLY':
            self.fly_to(e.xdata,e.ydata)
            self.set_click_mode('NAV')
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

    def setup_mav(self, mav_connect_str):
        if mav_connect_str:
            print(f'Connecting to {mav_connect_str}')
            mav_connection = mavutil.mavlink_connection(mav_connect_str)
            print(f'Connected to {mav_connect_str}')
        else:
            mav_connection = None
        return mav_connection

    def process_chat(self):
        if self.chat_url:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                chat_inbox_req = requests.get(self.chat_url, verify=False, timeout=0.5)
            chat_inbox = json.loads(chat_inbox_req.content)
            for chat_item in chat_inbox:
                if chat_item['lat']:
                    chat_name = chat_item['name']
                    if chat_name.upper()=='PILOT':
                        self.tracks['PILOT'].wipe()
                        self.tracks['PILOT'].update_latlon(chat_item['lat'], chat_item['lon'])
                    elif chat_name in self.tracks.keys():
                        self.tracks[chat_name].update_latlon(chat_item['lat'], chat_item['lon'])
                    else:
                        self.tracks[chat_name] = self.tracker_map.add_track(chat_name, head_style='m^')
                        self.tracks[chat_name].update_latlon(chat_item['lat'], chat_item['lon'])

    def process_mavlink(self):
        if self.mav:
            msg = self.mav.recv_match(type=['HEARTBEAT',
                                            'GLOBAL_POSITION_INT'
                                            ], blocking=False)
            if msg:
                if 'DRONE' in self.tracks.keys():
                    # seen this drone before
                    if msg.get_type()=='GLOBAL_POSITION_INT':
                        self.tracks['DRONE'].update_latlon(msg.lat/1e7,msg.lon/1e7)
                else:
                    # not seen drone before
                    self.tracks['DRONE'] = self.tracker_map.add_track('Drone',head_style='bx',track_style='b-')
                    self.mav.mav.request_data_stream_send(msg.get_srcSystem(),
                                                        msg.get_srcComponent(),
                                                        mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

    def fast_loop(self):
        self.process_mavlink()
        self.root.after(1, self.fast_loop)

    def slow_loop(self):
        # process chat
        self.process_chat()
        # redraw the canvas every second
        self.tracker_map.draw()
        # update target if there is one
        self.send_fly_target()
        self.root.after(500, self.slow_loop)

    def run(self):
        self.slow_loop()
        self.fast_loop()
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--tile_file',
                        help='Path to GeoTIFF file for basemap',
                        default='llanbedr_rgb.tif')
    parser.add_argument('-c', '--connect',
                        help='Connection string e.g. tcp:localhost:14550',
                        default=None)
    parser.add_argument('-s','--server',
                        help='URL for chat server',
                        default=None)
    args = parser.parse_args()
    app = TrackerApp(args.tile_file, args.connect, args.server)
    app.run()


if __name__=='__main__':
    main()