"""
kubeless function deploy gostint-coupler \
  --from-file gostint-coupler.py \
  --handler gostint-coupler.handler \
  --runtime python3.7 \
  --dependencies requirements.txt

kubeless function update gostint-coupler \
  --from-file gostint-coupler.py

kubeless trigger kafka create gostint-coupler \
  --function-selector created-by=kubeless,function=gostint-coupler \
  --trigger-topic automation_v1_request

kubeless function delete gostint-coupler

curl -sS http://127.0.0.1:3303/automation/v1 \
    -X POST \
    -H "Content-type: application/json" \
    --data '{"foo":"bar"}'
{"data":{"data":{"value":"my response"},"event_uuid":"2a8bdf29-8568-11e9-86b3-0242ac110002"}
"""

import sys
import traceback
import json
import base64
import tempfile

from kubernetes import client, config
from kafka import KafkaProducer

config.load_incluster_config()

v1 = client.CoreV1Api()


def handler(event, context):
    print("event:", event)

    # establish the producer for each function call, cannot be global...
    producer = KafkaProducer(
        bootstrap_servers=['kafka.kubeless.svc.cluster.local:9092'])

    #############################
    # Call backend api goes here
    #############################

    # Return response event
    try:
        # mock response for test
        response = {
            "event_uuid": event["data"]["event_uuid"],
            "data": {
                "value": "my response"
            }
        }

        new_event = bytearray(json.dumps(response), encoding='utf-8')
        producer.send('automation_v1_response', key=b'event',
                      value=new_event).get(timeout=30)
        # m = future.get(timeout=30)
        producer.flush(timeout=5)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return
