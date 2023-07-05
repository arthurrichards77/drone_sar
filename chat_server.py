from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/hello/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/loc_test/")
def loc_test():
    return render_template('loc_test.html')

@app.route("/form_test/")
def form_test():
    return render_template('form_test.html',name=None)

@app.route("/result_test/")
def result_test():
    name = request.args.get('name',None)
    print(name)
    return render_template('form_test.html',name=name)

@app.route("/post_test/")
def post_test():
    return render_template('post_test.html',name=None)

@app.route("/post_result/", methods=['GET', 'POST'])
def post_result():
    name = request.form['name']
    print(name)
    return render_template('post_test.html',name=name)

@app.route("/")
@app.route("/chat/", methods=['GET', 'POST'])
def chat():
    if request.method=='POST':
        name = request.form['name']
        return render_template('chat.html', name=name)
    else:
        return render_template('chat.html', name=None)

