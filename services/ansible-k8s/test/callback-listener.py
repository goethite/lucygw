import json
from flask import Flask, request, make_response
app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello World!"


@app.route("/callback", methods=['POST'])
def callback():
    req = request.get_json()
    print("req:", json.dumps(req, indent=2, sort_keys=True))

    return make_response(json.dumps({
        "status": "ok"
    }))
