from flask import Flask, render_template, request
from datetime import datetime
import json

app = Flask(__name__)

msgs = []

@app.route("/")
@app.route("/chat/", methods=['GET', 'POST'])
def chat():
    if request.method=='POST':
        sender_name = request.form['name']
        msg_time = datetime.now().isoformat()
        msg_text = request.form['msg']
        msgs.append({'name': sender_name,
                     'time': msg_time,
                     'msg': msg_text,
                     'lat': request.form['lat'],
                     'lon': request.form['lon'],
                     })
        summary = f'Received "{msg_text}" from {sender_name} at time {msg_time}'
        return render_template('chat.html', name=sender_name, recv=summary)
    else:
        return render_template('chat.html', name=None, recv=None)

@app.route("/monitor/")
def monitor():
    return json.dumps(msgs)

@app.route("/inbox/")
def inbox():
    received_msgs = []
    num_msgs = len(msgs)
    for ii in range(num_msgs):
        received_msgs.append(msgs.pop(0))
    return json.dumps(received_msgs)

if __name__ == "__main__":
    app.run(ssl_context='adhoc', host='0.0.0.0')