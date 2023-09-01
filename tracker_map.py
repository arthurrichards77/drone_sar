import time

import tkinter
import functools

import argparse

from math import sqrt, cos, sin, pi

import pyproj

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import rasterio
from rasterio.plot import show

from terrain import TerrainTileCollection
from drone_interface import DroneInterface
from chat_client import ChatClient

crs_osgb = pyproj.CRS.from_epsg(27700)
crs_gps = pyproj.CRS.from_epsg(4326)
lat_lon_to_east_north = pyproj.Transformer.from_crs(crs_gps, crs_osgb)
east_north_to_lat_lon = pyproj.Transformer.from_crs(crs_osgb, crs_gps)

deg_to_rad = pi/180.0

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
        fig = Figure(figsize=(5, 5), dpi=100)
        super().__init__(fig,master=master)
        self.ax = fig.add_subplot()
        base_map = rasterio.open(tile_file_name)
        show(base_map, ax=self.ax)
        self.tile_limits = self.ax.axis()
        fig.tight_layout()

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
                                             command=parent_app.hover)
        self.buttons['HOV'].grid(row=0,column=4)
        self.buttons['CIR'] = tkinter.Button(master=self,
                                             text='CIR',
                                             command=parent_app.circle)
        self.buttons['CIR'].grid(row=0,column=5)
        self.buttons['CAN'] = tkinter.Button(master=self,
                                             text='CAN',
                                             command=parent_app.cancel_fly_to)
        self.buttons['CAN'].grid(row=0,column=6)

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
        fig = Figure(figsize=(1, 5), dpi=100)
        super().__init__(fig,master=master)
        self.ax = fig.add_subplot()
        self.ax.axis([-0.5,0.5,-50,200])
        fig.tight_layout()

    def add_marker(self, line_style='-', marker_style='o'):
        new_marker = AltMarker(self, line_style, marker_style)
        return new_marker


class TimeMarker:

    def __init__(self, parent_tape, line_style='-', marker_style='o'):
        self.parent_tape = parent_tape
        self.time_secs = None
        self.time_line = None
        self.time_mark = None
        if line_style:
            self.time_line, = parent_tape.ax.plot([],[],line_style)
        if marker_style:
            self.time_mark, = parent_tape.ax.plot([],[],marker_style)

    def plot(self):
        if self.time_secs is not None:
            if self.time_line:
                self.time_line.set_data([self.time_secs, self.time_secs],[-0.5,0.5])
            if self.time_mark:
                self.time_mark.set_data([self.time_secs],[0.])

    def wipe(self):
        self.time_secs = None
        self.plot()

    def update_time(self,time_secs):
        self.time_secs = time_secs
        self.plot()

    def update_now(self, offset=0.0):
        self.update_time(time.time()+offset)
        self.plot()

class TimeTape(FigureCanvasTkAgg):

    def __init__(self, master):
        fig = Figure(figsize=(5, 1), dpi=100)
        super().__init__(fig,master=master)
        self.ax = fig.add_subplot()
        self.time_range = [-3600,3600]
        self.ax.axis([self.time_range[0],self.time_range[1],-0.5,0.5])
        #fig.autofmt_xdate()
        fig.tight_layout()

    def add_marker(self, line_style='-', marker_style='o'):
        new_marker = TimeMarker(self, line_style, marker_style)
        return new_marker

    def draw_now(self):
        time_now = time.time()
        # lots of work to label the axis intuitively
        str_now = time.localtime()
        first_tick = time.mktime((str_now.tm_year, str_now.tm_mon, str_now.tm_mday,
                                  str_now.tm_hour-1, 0, 0,
                                  str_now.tm_wday, str_now.tm_yday, str_now.tm_isdst))
        tick_range = [first_tick + ii*900 for ii in range(12)]
        self.ax.set_xticks(tick_range)
        self.ax.set_xticklabels([time.strftime('%H:%M',time.localtime(t)) for t in tick_range])
        # range is either side of current time
        self.ax.axis([self.time_range[0]+time_now,
                      self.time_range[1]+time_now,
                      -0.5,0.5])
        self.draw()

def distance(p1,p2):
    x1,y1 = p1
    x2,y2 = p2
    return sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2))

class TrackerApp:

    def __init__(self, tile_file_name, mav_connect_str, chat_url, terrain_path):
        print('Starting...')
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
        # include built-in toolbar for map zoom and pan etc
        self.nav_toolbar = NavigationToolbar2Tk(self.tracker_map, self.root, pack_toolbar=False)
        self.nav_toolbar.update()
        # click event handler and toolbar work together
        self.tracker_map.mpl_connect("button_press_event", self.click_handler)
        self.track_toolbar = TrackerToolbar(self.root, self)
        self.click_mode = None
        self.set_click_mode('NAV')
        # display coordinates etc
        self.status_msgs = tkinter.StringVar(master=self.root, value='Status')
        self.tracker_map.mpl_connect("motion_notify_event", self.hover_handler)
        # altitude tape
        self.alt_tape = AltTape(self.root)
        self.alt_marks = {}
        self.alt_marks['SEA_LEVEL'] = self.alt_tape.add_marker('b-',None)
        self.alt_marks['SEA_LEVEL'].update_alt(0.0)
        self.alt_tape.mpl_connect("button_press_event", self.alt_click_handler)
        # timeline
        self.time_tape = TimeTape(self.root)
        self.time_markers = {'NOW': self.time_tape.add_marker(line_style='k-',marker_style=None),
                             'TAKEOFF': self.time_tape.add_marker(line_style='b-',marker_style=None),
                             'TURNBATT': self.time_tape.add_marker(line_style='y-',marker_style='ys'),
                             'TURNTIME': self.time_tape.add_marker(line_style='y-',marker_style='yo'),
                             'BATTERY': self.time_tape.add_marker(line_style='r-',marker_style='rs'),
                             'ENDURANCE': self.time_tape.add_marker(line_style='r-',marker_style='ro'),}
        # connect to the MAV
        self.mav = DroneInterface(mav_connect_str)
        # add loads of tracking for the drone
        self.tracks['DRONE'] = self.tracker_map.add_track('Drone',head_style='bx',track_style='b-')
        self.tracks['TARGET'] = self.tracker_map.add_track('TARGET', track_style='', head_style='bs')
        self.tracks['TAKEOFF'] = self.tracker_map.add_track('Takeoff',head_style='bs',track_style='bs')
        self.tracks['SENSOR'] = self.tracker_map.add_track('Sensor',head_style='go',track_style='g-')
        self.tracks['SENSOR'].track_line.set_lw(10)
        self.tracks['SENSOR'].track_line.set_c((0.,1.,0.,0.5))
        self.alt_marks['DRONE'] = self.alt_tape.add_marker(line_style=None, marker_style='bx')
        self.alt_marks['TARGET'] = self.alt_tape.add_marker('b--',None)
        self.alt_marks['TAKEOFF'] = self.alt_tape.add_marker(line_style=None, marker_style='bs')
        self.alt_marks['TERRAIN'] = self.alt_tape.add_marker(line_style='g-', marker_style=None)
        self.alt_marks['MAX'] = self.alt_tape.add_marker('r-',None)
        # connect to chat server
        self.chat_client = None
        if chat_url:
            self.chat_client = ChatClient(chat_url)
        # load terrain
        self.terrain = TerrainTileCollection(terrain_path)
        self.assemble_gui()

    def assemble_gui(self):
        # assemble the left pane
        self.alt_tape.get_tk_widget().grid(row=2,column=0)
        # assemble the middle pane
        self.track_toolbar.grid(row=0,column=1)
        self.nav_toolbar.grid(row=1,column=1)
        self.tracker_map.get_tk_widget().grid(row=2,column=1)
        self.time_tape.get_tk_widget().grid(row=3,column=1)
        # assemble the right pane
        status_label = tkinter.Label(master=self.root, textvariable=self.status_msgs, height=3, justify=tkinter.LEFT)
        status_label.grid(row=0,column=2)
        # chat window
        self.detail_frame = tkinter.Frame(master=self.root)
        self.dist_box = tkinter.Listbox(master=self.detail_frame)
        self.chat_box = tkinter.Listbox(master=self.detail_frame,width=50)
        tkinter.Label(self.detail_frame, text='Distances').grid(row=0,column=0)
        self.dist_box.grid(row=1,column=0)
        tkinter.Label(self.detail_frame, text='Messages').grid(row=2,column=0)
        self.chat_box.grid(row=3,column=0)
        self.detail_frame.grid(row=2,column=2)

    def set_click_mode(self, new_mode):
        self.click_mode = new_mode
        # disable the plot navigation toolbar unless in NAV
        if new_mode=='NAV':
            nav_state = tkinter.NORMAL
        else:
            nav_state = tkinter.DISABLED
        for btn in self.nav_toolbar._buttons:
            self.nav_toolbar._buttons[btn]['state'] = nav_state
        # make the chosen mode green
        for btn in self.track_toolbar.buttons:
            if btn==new_mode:
                self.track_toolbar.buttons[btn].configure(bg="LimeGreen")
            else:
                self.track_toolbar.buttons[btn].configure(bg="light gray")

    def add_poi(self,x,y):
        num_poi = len([t for t in self.tracks if t.startswith('POI')])
        new_poi = f'POI{num_poi+1}'
        self.tracks[new_poi] = self.tracker_map.add_track(new_poi, head_style='b^')
        self.tracks[new_poi].update(x,y)

    def fly_to(self,x,y,asl,yaw_rate):
        # can only command if know takeoff altitude
        if self.alt_marks['TAKEOFF']:
            self.tracks['TARGET'].wipe()
            self.tracks['TARGET'].update(x,y)
            self.alt_marks['TARGET'].update_alt(asl)
            lat, lon = east_north_to_lat_lon.transform(x,y)
            self.mav.set_target(lat,lon,asl,yaw_rate)

    def hover(self, yaw_rate=0.0):
        x,y = self.tracks['DRONE'].get_current_pos()
        asl = self.alt_marks['DRONE'].alt
        self.fly_to(x,y,asl,yaw_rate)

    def circle(self, yaw_rate=0.25):
        self.hover(yaw_rate=yaw_rate)

    def cancel_fly_to(self):
        self.tracks['TARGET'].wipe()
        self.mav.clear_target()

    def alt_click_handler(self,e):
        self.alt_marks['TARGET'].update_alt(e.ydata)
        self.alt_tape.draw()

    def click_handler(self,e):
        if self.click_mode=='MISPER':
            self.tracks['MISPER'].update(e.xdata,e.ydata)
        elif self.click_mode=='POI':
            self.add_poi(e.xdata, e.ydata)
        elif self.click_mode=='FLY':
            self.fly_to(e.xdata,e.ydata,self.alt_marks['TARGET'].alt, 0.0)
            self.set_click_mode('NAV')
        self.tracker_map.draw()

    def update_distances(self,cursor_pos):
        self.dist_box.delete(0,self.dist_box.size())
        for t in self.tracks:
            pos = self.tracks[t].get_current_pos()
            if pos:
                self.dist_box.insert(tkinter.END,f'{t}: {distance(pos,cursor_pos):.0f}m; ')

    def hover_handler(self, e):
        if e.xdata:
            lat, lon = east_north_to_lat_lon.transform(e.xdata, e.ydata)
            terrain_alt = self.terrain.lookup(e.xdata, e.ydata)
            self.status_msgs.set(f'{lat:.6f},\n{lon:.6f},\n{terrain_alt:.1f}m ASL')
            self.update_distances((e.xdata, e.ydata))
        else:
            self.status_msgs.set('Cursor off map')

    def process_chat(self):
        if self.chat_client:
            messages = self.chat_client.get_new_messages()
            for msg in messages:
                chat_summary = f'[{msg.format_time()}] {msg.sender}: {msg.text}'
                self.chat_box.insert(tkinter.END,chat_summary)
                self.chat_box.see(tkinter.END)
                if msg.has_location:
                    chat_track = msg.sender.upper()
                    if chat_track not in self.tracks:
                        self.tracks[chat_track] = self.tracker_map.add_track(chat_track, head_style='m^')
                    self.tracks[chat_track].update_latlon(msg.lat, msg.lon)

    def drone_update(self):
        if self.mav.connected:
            self.mav.process_mavlink()

    def draw_drone(self):
        if self.mav.has_position():
            lat, lon = self.mav.current_lat_lon()
            self.tracks['DRONE'].update_latlon(lat,lon)
            alt_asl = self.mav.current_alt_asl()
            self.alt_marks['DRONE'].update_alt(alt_asl)
            # look up terrain height at drone location
            drone_x, drone_y = self.tracks['DRONE'].get_current_pos()
            terrain_under_drone = self.terrain.lookup(drone_x, drone_y)
            self.alt_marks['TERRAIN'].update_alt(terrain_under_drone)
            self.alt_marks['MAX'].update_alt(terrain_under_drone+120.0)
            # plot the sensor footprint
            if self.mav.in_air():
                sensor_offset = 1.0*(alt_asl - terrain_under_drone)
                sensor_x = drone_x + sensor_offset*sin(self.mav.current_hdg_deg()*deg_to_rad)
                sensor_y = drone_y + sensor_offset*cos(self.mav.current_hdg_deg()*deg_to_rad)
                self.tracks['SENSOR'].update(sensor_x,sensor_y)
            # if takeoff time and loc also known
            if self.mav.takeoff_time:
                if not self.alt_marks['TAKEOFF'].alt:
                    self.alt_marks['TAKEOFF'].update_alt(self.mav.takeoff_alt_asl())
                    self.alt_marks['TARGET'].update_alt(self.mav.takeoff_alt_asl() + 20.0)
                    to_lat, to_lon = self.mav.takeoff_lat_lon()
                    self.tracks['TAKEOFF'].update_latlon(to_lat,to_lon)
                    self.time_markers['TAKEOFF'].update_time(self.mav.takeoff_time)
                    self.time_markers['ENDURANCE'].update_time(self.mav.takeoff_time+self.mav.endurance())
                # plot turnback time
                dist_home = distance((drone_x,drone_y),
                                     self.tracks['TAKEOFF'].get_current_pos())
                time_home = dist_home/self.mav.speed()
                turnback_time = self.mav.takeoff_time+self.mav.endurance()-time_home
                self.time_markers['TURNTIME'].update_time(turnback_time)
        # battery estimate is dependent only on current battery message
        battery_estimate = self.mav.battery_time_remaining(30)
        if battery_estimate:
            if self.time_markers['BATTERY'].time_secs:
                if time.time() + battery_estimate < self.time_markers['BATTERY'].time_secs:
                    self.time_markers['BATTERY'].update_now(battery_estimate)
            else:
                self.time_markers['BATTERY'].update_now(battery_estimate)



    def fast_loop(self):
        self.drone_update()
        self.root.after(1, self.fast_loop)

    def slow_loop(self):
        # process chat
        self.process_chat()
        # process drone
        self.draw_drone()
        # redraw the canvas every second
        self.tracker_map.draw()
        self.alt_tape.draw()
        self.time_markers['NOW'].update_time(time.time())
        self.time_tape.draw_now()
        # update target if there is one
        if self.mav.connected:
            self.mav.send_target()
        self.root.after(500, self.slow_loop)

    def run(self):
        self.slow_loop()
        self.fast_loop()
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--tile_file',
                        help='Path to GeoTIFF file for basemap',
                        default='map_data/llanbedr_rgb.tif')
    parser.add_argument('-c', '--connect',
                        help='Connection string e.g. tcp:localhost:14550',
                        default=None)
    parser.add_argument('-s','--server',
                        help='URL for chat server',
                        default=None)
    parser.add_argument('-p','--path_to_terrain',
                        help='Path to search for terrain files',
                        default='map_data/Download_llanbedr_terrain_2297518/terrain-5-dtm_5107396')
    args = parser.parse_args()
    app = TrackerApp(args.tile_file, args.connect, args.server, args.path_to_terrain)
    app.run()


if __name__=='__main__':
    main()
