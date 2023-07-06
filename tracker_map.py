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
crs_gps = pyproj.CRS.from_epsg(4326)
lat_lon_to_east_north = pyproj.Transformer.from_crs(crs_gps, crs_osgb)
east_north_to_lat_lon = pyproj.Transformer.from_crs(crs_osgb, crs_gps)

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

class AltMarker:

    def __init__(self, parent_tape, line_style='-', marker_style='o'):
        self.parent_tape = parent_tape
        self.alt = None
        self.alt_line = None
        self.alt_mark = None
        if line_style:
            self.alt_line, = parent_tape.ax.plot([],[],line_style)
        if marker_style:
            self.alt_mark, = parent_tape.ax.plot([],[],marker_style)

    def plot(self):
        if self.alt is not None:
            if self.alt_line:
                self.alt_line.set_data([-0.5,0.5],[self.alt, self.alt])
            if self.alt_mark:
                self.alt_mark.set_data([0.],[self.alt])

    def wipe(self):
        self.alt = None
        self.plot()

    def update_alt(self,alt):
        self.alt = alt
        self.plot()

class AltTape(FigureCanvasTkAgg):

    def __init__(self, master):
        fig = Figure(figsize=(1, 4), dpi=100)
        super().__init__(fig,master=master)
        self.ax = fig.add_subplot()
        self.ax.axis([-0.5,0.5,-50,200])
        self.draw()

    def add_marker(self, line_style='-', marker_style='o'):
        new_marker = AltMarker(self, line_style, marker_style)
        return new_marker

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
        self.buttons['HOV'] = tkinter.Button(master=self,
                                             text='HOV',
                                             command=parent_app.brake)
        self.buttons['HOV'].grid(row=0,column=4)
        self.buttons['CIR'] = tkinter.Button(master=self,
                                             text='CIR',
                                             command=parent_app.circle)
        self.buttons['CIR'].grid(row=0,column=5)
        self.buttons['CAN'] = tkinter.Button(master=self,
                                             text='CAN',
                                             command=parent_app.cancel_fly_to)
        self.buttons['CAN'].grid(row=0,column=6)

def distance(p1,p2):
    x1,y1 = p1
    x2,y2 = p2
    return sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2))

class TrackerApp:

    def __init__(self, tile_file_name, mav_connect_str, chat_url):
        self.root = tkinter.Tk()
        self.timer_count = 0
        self.root.wm_title("Tracker Map")
        left_pane = tkinter.Frame(master=self.root)
        middle_pane = tkinter.Frame(master=self.root)
        right_pane = tkinter.Frame(master=self.root)
        self.tracker_map = TkTrackerMap(middle_pane, tile_file_name)
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
        self.click_mode = 'NAV'
        self.tracker_map.mpl_connect("button_press_event", self.click_handler)
        self.track_toolbar = TrackerToolbar(middle_pane, self)
        # display coordinates etc
        self.status_msgs = tkinter.StringVar(master=middle_pane, value='Status')
        status_label = tkinter.Label(master=self.root, textvariable=self.status_msgs, height=3, justify=tkinter.LEFT)
        self.tracker_map.mpl_connect("motion_notify_event", self.hover_handler)
        # chat window
        self.chat_var = tkinter.StringVar(master=right_pane, value='Chat')
        chat_label = tkinter.Label(master=right_pane, textvariable=self.chat_var, height=3, justify=tkinter.LEFT)
        self.chat_msgs = []
        # include built-in toolbar for map zoom and pan etc
        self.nav_toolbar = NavigationToolbar2Tk(self.tracker_map, middle_pane, pack_toolbar=False)
        self.nav_toolbar.update()
        # altitude tape
        self.alt_tape = AltTape(left_pane)
        self.alt_marks = {}
        self.alt_marks['HOME'] = self.alt_tape.add_marker('k-',None)
        self.alt_marks['HOME'].update_alt(0.0)
        self.alt_marks['MAX'] = self.alt_tape.add_marker('r-',None)
        self.alt_marks['MAX'].update_alt(120.0)
        self.alt_marks['WARN'] = self.alt_tape.add_marker('y-',None)
        self.alt_marks['WARN'].update_alt(110.0)
        self.alt_marks['TARGET'] = self.alt_tape.add_marker('b--',None)
        self.alt_marks['TARGET'].update_alt(20.0)
        self.alt_tape.mpl_connect("button_press_event", self.alt_click_handler)
        # assemble the right pane
        self.alt_tape.get_tk_widget().pack(side=tkinter.RIGHT, fill=tkinter.X, expand=True)
        # assemble the middle pane
        self.nav_toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        status_label.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        self.track_toolbar.pack(side=tkinter.TOP)
        self.tracker_map.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)
        # assemble the right pane
        chat_label.pack(side=tkinter.LEFT, fill=tkinter.BOTH)
        # assemble the panes
        left_pane.pack(side = tkinter.LEFT)
        middle_pane.pack(side = tkinter.LEFT)
        right_pane.pack(side = tkinter.LEFT)
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

    def fly_to(self,x,y,yaw_rate=0.0,alt=None):
        lat, lon = east_north_to_lat_lon.transform(x,y)
        self.fly_target = (lat,lon,yaw_rate)
        self.tracks['TARGET'].wipe()
        self.tracks['TARGET'].update_latlon(lat,lon)
        if alt:
            self.alt_marks['TARGET'].update_alt(alt)

    def get_target_drone_name(self):
        return [tn for tn in self.tracks.keys() if tn.startswith('DRONE')][0]

    def get_target_drone_num(self):
        drone_name = self.get_target_drone_name()
        return int(drone_name[5:])

    def cancel_fly_to(self):
        self.fly_target = None
        self.tracks['TARGET'].wipe()

    def brake(self):
        pos = self.tracks[self.get_target_drone_name()].get_current_pos()
        if pos:
            self.fly_to(pos[0], pos[1], 0.0)

    def circle(self):
        pos = self.tracks[self.get_target_drone_name()].get_current_pos()
        if pos:
            self.fly_to(pos[0], pos[1], 0.25)

    def send_fly_target(self):
        if self.fly_target:
            # hack to get the target ID
            
            self.mav.mav.set_position_target_global_int_send(
                0,  # timestamp
                self.get_target_drone_num(),  # target system_id
                1,  # target component id
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,  # mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VX_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VY_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VZ_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE,
                int(self.fly_target[0] * 1.0e7),  # lat
                int(self.fly_target[1] * 1.0e7),  # lon
                self.alt_marks['TARGET'].alt,  # alt
                0,  # vx
                0,  # vy
                0,  # vz
                0,  # afx
                0,  # afy
                0,  # afz
                0,  # yaw
                self.fly_target[2],  # yawrate
            )

    def alt_click_handler(self,e):
        self.alt_marks['TARGET'].update_alt(e.ydata)
        self.alt_tape.draw()

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
            self.status_msgs.set(f'''Cursor {lat:.6f},{lon:.6f}  Mode {self.click_mode}
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
                chat_inbox_req = requests.get(self.chat_url, verify=False, timeout=1.0)
            chat_inbox = json.loads(chat_inbox_req.content)
            for chat_item in chat_inbox:
                chat_name = chat_item['name']
                chat_msg = chat_item['msg']
                if chat_msg:
                    chat_summary = f'{chat_name}: {chat_msg}'
                    if len(self.chat_msgs)==3:
                        self.chat_msgs.pop(0)
                    self.chat_msgs.append(chat_summary)
                    self.chat_var.set("\n".join(self.chat_msgs))
                if chat_item['lat']:
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
                drone_num = msg.get_srcSystem()
                drone_name = f'DRONE{drone_num}'
                sensor_name = f'SENSOR{drone_num}'
                if drone_name in self.tracks.keys():
                    # seen this drone before
                    if msg.get_type()=='GLOBAL_POSITION_INT':
                        self.tracks[drone_name].update_latlon(msg.lat/1e7,msg.lon/1e7)
                        self.alt_marks[drone_name].update_alt(msg.relative_alt/1e3)
                        sensor_offset = 1.0*(msg.relative_alt/1.0e3)
                        drone_x, drone_y = self.tracks[drone_name].get_current_pos()
                        sensor_x = drone_x + sensor_offset*sin(msg.hdg*1.0e-2*2*pi/360.0)
                        sensor_y = drone_y + sensor_offset*cos(msg.hdg*1.0e-2*2*pi/360.0)
                        self.tracks[sensor_name].update(sensor_x,sensor_y)
                else:
                    # not seen drone before
                    self.tracks[drone_name] = self.tracker_map.add_track('Drone',head_style='bx',track_style='b-')
                    self.tracks[sensor_name] = self.tracker_map.add_track('Sensor',head_style='go',track_style='g-')
                    self.tracks[sensor_name].track_line.set_lw(10)
                    self.tracks[sensor_name].track_line.set_c((0.,1.,0.,0.5))
                    self.alt_marks[drone_name] = self.alt_tape.add_marker(line_style=None, marker_style='bx')
                    # request data
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
        self.alt_tape.draw()
        # update target if there is one
        if self.mav:
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