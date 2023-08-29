import time
from pymavlink import mavutil
#from sklearn.linear_model import LinearRegression
#import numpy as np

class DroneInterface:

    def __init__(self,mav_connect_str):
        self.connected = False
        self.mav_connection = None
        if mav_connect_str:
            print(f'Connecting to {mav_connect_str}')
            try:
                self.mav_connection = mavutil.mavlink_connection(mav_connect_str)
                print(f'Connected to {mav_connect_str}')
                self.connected = True
            except ConnectionError:
                print(f'Failed to connect to {mav_connect_str}')
                self.mav_connection = None
        self.drone_id = None
        self.drone_target = None
        self.takeoff_pos = None
        self.takeoff_time = None
        self.current_pos = None
        self.current_hdg_deg = None
        self.battery_history = []
        self.battery_averages = {'CAPACITY': 3300,
                                 'CURRENT': 30}
        self.last_msg_dict = {}

    def set_target(self,lat,lon,rel_alt,yaw_rate):
        self.drone_target = (lat, lon, rel_alt, yaw_rate)

    def clear_target(self):
        self.drone_target = None

    def send_target(self):
        if self.drone_target:
            self.mav_connection.mav.set_position_target_global_int_send(
                0,  # timestamp
                self.drone_id,  # target system_id
                1,  # target component id
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,  # mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VX_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VY_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_VZ_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
                mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE,
                int(self.drone_target[0] * 1.0e7),  # lat
                int(self.drone_target[1] * 1.0e7),  # lon
                self.drone_target[2],  # alt rel home
                0,  # vx
                0,  # vy
                0,  # vz
                0,  # afx
                0,  # afy
                0,  # afz
                0,  # yaw
                self.drone_target[3],  # yawrate
            )

    def process_mavlink(self):
        msg = self.mav_connection.recv_match(type=['HEARTBEAT',
                                                   'GLOBAL_POSITION_INT',
                                                   'BATTERY_STATUS'
                                                  ], blocking=False)
        if msg:
            if self.drone_id is None:
                self.drone_id = msg.get_srcSystem()
                # request data
                self.mav_connection.mav.request_data_stream_send(msg.get_srcSystem(),
                                                                 msg.get_srcComponent(),
                                                                 mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
            else:
                if msg.get_srcSystem() != self.drone_id:
                    print(f'Ignoring message from system ID {msg.get_srcSystem()}')
                    return
            msg_type = msg.get_type()
            if msg_type=='GLOBAL_POSITION_INT':
                self.current_pos = (msg.lat/1e7,
                                    msg.lon/1e7,
                                    msg.relative_alt/1e3)
                self.current_hdg_deg = msg.hdg*1.0e-2
            elif msg_type=='BATTERY_STATUS':
                self.battery_history.append((time.time(),msg.battery_remaining))
                self.battery_averages['CURRENT'] += 0.01*(msg.current_battery - self.battery_averages['CURRENT'])
                capacity_estimate = msg.current_consumed*100.0/(100.0-msg.battery_remaining)
                self.battery_averages['CAPACITY'] += 0.01*(capacity_estimate - self.battery_averages['CAPACITY'])
            elif msg_type=='HEARTBEAT':
                if msg.system_status==4:
                    if 'HEARTBEAT' not in self.last_msg_dict:
                        print('Warning - drone already in the air on connection')
                        self.takeoff_pos = self.current_pos
                        self.takeoff_time = time.time()
                    elif self.last_status()!=4:
                        # first heartbeat after takeoff
                        self.takeoff_pos = self.current_pos
                        self.takeoff_time = time.time()
            self.last_msg_dict[msg_type] = msg

    def time_since_takeoff(self):
        "In seconds"
        return time.time()-self.takeoff_time

    def last_status(self):
        return self.last_msg_dict['HEARTBEAT'].system_status

    def in_air(self):
        "True if off ground"
        return self.last_status()>3

    def endurance(self):
        "In seconds"
        return 1800
    
    def speed(self):
        "In m/s"
        return 10
    
    def battery_time_remaining(self, target_percent=30):
        "Time to capacity target in seconds"
        #if len(self.battery_history)<10:
        #    return None
        #model = LinearRegression()
        #model.fit(np.array([b[1] for b in self.battery_history]).reshape((-1,1)),
        #          np.array([b[0] for b in self.battery_history]).reshape((-1,1)))
        #return model.predict(np.array([target_level]).reshape((1,-1)))
        if 'BATTERY_STATUS' in self.last_msg_dict:
            used_charge  = self.last_msg_dict['BATTERY_STATUS'].current_consumed
            percent_remain = self.last_msg_dict['BATTERY_STATUS'].battery_remaining
            if percent_remain==100:
                return None
            percent_used = 100 - percent_remain
            capacity_estimate = used_charge * 100.0/percent_used #in mAh
            #print(f'Estimate battery cap {capacity_estimate}')
            last_current = self.last_msg_dict['BATTERY_STATUS'].current_battery*10.0 #to mA
            if last_current==0.0:
                return None
            charge_over_target = capacity_estimate - used_charge - 0.01*target_percent*capacity_estimate
            #print(f'Estimate {charge_over_target}mAh above target')
            time_to_target = charge_over_target/last_current
            return time_to_target*3600.0 #to seconds
        else:
            return None
