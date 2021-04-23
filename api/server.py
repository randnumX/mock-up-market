from flask import Flask,send_from_directory
import os
app = Flask(__name__, static_folder='static')
app.config["CACHE_TYPE"] = "null"

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder+'\\favicon',
                               'favicon.ico')

@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r                       

@app.route('/getdata/<stock_ticker>')
def hello_world(stock_tick):
    return 'Hello World1'

if __name__ == '__main__':
    app.run(debug=True)