import requests
import json
import warnings
from datetime import datetime
import argparse
import qrcode
import socket

def make_qr_code():
    host_name = socket.gethostname()
    ip_addr = socket.gethostbyname(host_name)
    chat_url = 'https://'+ip_addr+':5000'
    img = qrcode.make(chat_url)
    img.save("chat_qr_code.png")

class ChatMessage:

    def __init__(self, sender=None, text=None, time=None, lat=None, lon=None, input_dict=None):
        self.sender = sender
        self.text = text
        self.time = time
        self.lat = lat
        self.lon = lon
        if input_dict:
            self.load_dict(input_dict)

    def load_dict(self,input_dict):
        self.sender = input_dict['name']
        self.text = input_dict['msg']
        self.time = datetime.fromisoformat(input_dict['time'])
        self.lat = input_dict['lat']
        self.lon = input_dict['lon']

    def has_location(self):
        if self.lat is None:
            return False
        if self.lon is None:
            return False
        return True
    
    def format_time(self, format='%H:%M'):
        return self.time.strftime(format)
    
    def __repr__(self):
        return f"{self.sender}@{self.format_time()}:{self.text}"

class ChatClient:

    def __init__(self, base_url):
        self.base_url = base_url
        if not self.base_url.endswith('/'):
            self.base_url += '/'

    def get_new_messages(self):
        messages = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chat_inbox_req = requests.get(self.base_url+'inbox', verify=False, timeout=1.0)
        chat_inbox = json.loads(chat_inbox_req.content)
        for chat_dict in chat_inbox:
            messages.append(ChatMessage(input_dict=chat_dict))
            #print(messages)
        return messages

    def send_message(self, sender, message, position):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chat_post_response = requests.post(self.base_url+'chat', verify=False, timeout=1.0,
                                                data={'name': sender,
                                                        'msg': message,
                                                        'lat': position[0],
                                                        'lon': position[1]})
        print(chat_post_response.status_code)

def test_client():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u','--url',default='https://127.0.0.1:5000')
    parser.add_argument('-r','--read',action='store_true')
    parser.add_argument('-s','--sender', default='Test client')
    parser.add_argument('-m','--message', default='Test message')
    parser.add_argument('-p','--position', nargs=2, default=[52.8,-4.1])
    parser.add_argument('-q','--qrcode',action='store_true')
    args = parser.parse_args()
    client = ChatClient(args.url)
    if args.qrcode:
        print('Saving QR code')
        make_qr_code()
    if args.read:
        print('Checking inbox')
        print(client.get_new_messages())
    else:
        print(f'Sending {args.message} as {args.sender} at {args.position}')
        client.send_message(args.sender,
                            args.message,
                            args.position)

if __name__=='__main__':
    test_client()