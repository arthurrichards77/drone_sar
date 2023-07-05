# SAR HF - Search and Rescue Human Factors

Prototyping different interfaces for drone-supported search and rescue.

## Quick start

Run `python tracker_map.py -t llanbedr_rgb.tif`

You should see a map of Llanbedr airfield and the surroundings.

- Click NAV and you can use the figure toolbar to move and zoom the map scale
- Click MISPER and click the map to place the last known location of the missing person
- Click POI to mark a point of interest

Move your cursor over the map and you should see distances to all marked points.

## Drone functionality

Run up a SITL drone somewhere near LLanbedr through Mission Planner.  Now run `python tracker_map.py -t llanbedr_rgb.tif -c tcp:127.0.0.1:5762` to start the map with the drone connected.

You should see the map with a blue X marking the drone location.

- Arm and takeoff the SITL drone and put it in Guided mode.  Click FLY and then click on the map to direct the drone.

- Click CAN to cancel the drone target.  The drone may keep moving to the target though, unless directed elsewhere.

- TODO: click BRK to stop the drone at current location.

## Chat functionality

Fire up the chat server using `python chat_server.py`.  It will show you its URLs.

Now launch the map using `python tracker_map.py --server <chat server URL>/inbox`.  It will typically be 
```python tracker_map.py --server https://127.0.0.1:5000/inbox```

On any device connected to the same network, visit the URL, and you should see a simple messaging form.

- Fill in your name (compulsory)
- Enter a message
- Click `Locate` to enter your location.  You might need to grant permission.
- Click `Submit`

You should see a fresh chat window with a response confirming your message.  Over on the map, you should see your location pop up as a purple triangle.