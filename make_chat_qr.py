import qrcode
import socket

host_name = socket.gethostname()
ip_addr = socket.gethostbyname(host_name)
chat_url = 'https://'+ip_addr+':5000'
img = qrcode.make(chat_url)
img.save("chat_qr_code.png")