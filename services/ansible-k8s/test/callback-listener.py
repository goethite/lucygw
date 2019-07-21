# using: flask_restful:
#   https://flask-restful.readthedocs.io/en/latest/quickstart.html#a-minimal-api
import json
from flask import Flask, request, make_response
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)


class HelloWorld(Resource):
    def get(self):
        return {"msg": "Hello World!"}


class Callback(Resource):
    def post(self):
        req = request.get_json()
        print("req:", json.dumps(req, indent=2, sort_keys=True))

        return make_response(json.dumps({
            "status": "ok"
        }))


api.add_resource(HelloWorld, "/")
api.add_resource(Callback, "/callback")

# if __name__ == '__main__':
#     app.run(debug=True)
