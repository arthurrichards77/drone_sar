import time
from pymavlink import mavutil

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
        self.takeoff_pos_msg = None
        self.takeoff_time = None
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
                    #print(f'Ignoring message from system ID {msg.get_srcSystem()}')
                    return
            msg_type = msg.get_type()
            if msg_type=='GLOBAL_POSITION_INT':
                if self.takeoff_time is None:
                    if msg.relative_alt > 50.0:
                        self.takeoff_time = time.time()
                        self.takeoff_pos_msg = msg
            elif msg_type=='BATTERY_STATUS':
                pass
            elif msg_type=='HEARTBEAT':
                pass
            self.last_msg_dict[msg_type] = msg

    def has_message(self,message_type):
        return message_type in self.last_msg_dict.keys()
    
    def has_position(self):
        return self.has_message('GLOBAL_POSITION_INT')

    def current_lat_lon(self):
        "(latitude, longitude) in decimal degrees, or None if unknown"
        if self.has_message('GLOBAL_POSITION_INT'):
            return (self.last_msg_dict['GLOBAL_POSITION_INT'].lat/1e7,
                    self.last_msg_dict['GLOBAL_POSITION_INT'].lon/1e7)

    def current_hdg_deg(self):
        if self.has_message('GLOBAL_POSITION_INT'):
            return self.last_msg_dict['GLOBAL_POSITION_INT'].hdg/1e2

    def current_alt_asl(self):
        "in m, or None if unknown"
        if self.has_message('GLOBAL_POSITION_INT'):
            return self.last_msg_dict['GLOBAL_POSITION_INT'].alt/1e3

    def takeoff_lat_lon(self):
        "(latitude, longitude) in decimal degrees, or None if unknown"
        if self.takeoff_pos_msg:
            return (self.takeoff_pos_msg.lat/1e7,
                    self.takeoff_pos_msg.lon/1e7)

    def takeoff_alt_asl(self):
        "in m, or None if unknown"
        if self.takeoff_pos_msg:
            return self.takeoff_pos_msg.alt/1e3

    def time_since_takeoff(self):
        "In seconds"
        return time.time()-self.takeoff_time

    def last_status(self):
        if self.has_message('HEARTBEAT'):
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

    def battery_time_remaining(self, target_percent):
        "Time to capacity target in seconds"
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
