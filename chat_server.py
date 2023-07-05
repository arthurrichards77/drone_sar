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

