"""
PoC Execute Ansible in docker containers via K8s Batch Jobs.

Triggered from a kafka topic queue from lucy_proxy.

kubeless function deploy ansible-coupler \
  --from-file ansible-coupler.py \
  --handler ansible-coupler.handler \
  --runtime python3.7 \
  --dependencies requirements.txt

kubeless function update ansible-coupler \
  --from-file ansible-coupler.py

kubeless function delete ansible-coupler

kubeless trigger kafka create ansible-coupler \
  --function-selector created-by=kubeless,function=ansible-coupler \
  --trigger-topic automation_v1_request

curl -sS http://127.0.0.1:3303/automation/v1 \
    -X POST \
    -H "Content-type: application/json" \
    --data '{"foo":"bar"}'
{"data":{"data":{"value":"my response"},"event_uuid":"2a8bdf29-8568-11e9-86b3-0242ac110002"}
"""

import sys
import traceback
import time
import json
import base64
import tempfile

from kubernetes import client, config
from kafka import KafkaProducer

config.load_incluster_config()

v1 = client.CoreV1Api()


def get_job_status(batchApi, namespace, job_name):
    batchApi_resp = {}
    try:
        batchApi_resp = batchApi.read_namespaced_job(
            namespace=namespace,
            name=job_name
        )
    except client.rest.ApiException as e:
        print("Error calling k8s batch api: %s\n" % e)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return
    # print("read batchApi_resp:", batchApi_resp)
    return batchApi_resp.status


def handler(event, context):
    # print("event:", event)

    # Establish the producer for each function call, cannot be global...
    producer = KafkaProducer(
        bootstrap_servers=['kafka.kubeless.svc.cluster.local:9092'])

    batchApi = client.BatchV1Api()
    namespace = "default"
    body = {
        "api_version": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "myjob"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "myjob",
                            "image": "jmal98/ansiblecm:2.5.5",
                            "imagePullPolicy": "Always",
                            "command": ["ansible"],
                            "args": ["-m", "ping", "127.0.0.1"]
                        }
                    ],
                    "restartPolicy": "Never"
                }
            }
        }
    }

    try:
        batchApi_resp = batchApi.create_namespaced_job(
            namespace=namespace,
            body=body
        )
    except client.rest.ApiException as e:
        print("Error calling k8s batch api: %s\n" % e)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return

    # print("create batchApi_resp:", batchApi_resp)

    job_status = {}
    while True:
        time.sleep(1)
        job_status = get_job_status(batchApi, namespace, "myjob")
        if job_status.active is None:
            break

    try:
        pods = v1.list_namespaced_pod(
            namespace, label_selector="job-name=myjob")
    except client.rest.ApiException as e:
        print("Error calling k8s batch api: %s\n" % e)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return

    pod = pods.items[0]
    pod_name = pod.metadata.name

    # Get log from job pod
    try:
        pod_log = v1.read_namespaced_pod_log(
            pod_name,
            namespace,
            # timestamps=True
            tail_lines=100  # limit to last n lines
        )
    except client.rest.ApiException as e:
        print("Error calling k8s batch api: %s\n" % e)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return
    print("pod_log:", pod_log)

    try:
        batchApi.delete_namespaced_job(
            namespace=namespace,
            name="myjob",
            body={}
        )
    except client.rest.ApiException as e:
        print("Error calling k8s batch api: %s\n" % e)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return

    try:
        v1.delete_namespaced_pod(pod_name, namespace, body={})
    except client.rest.ApiException as e:
        print("Error calling k8s batch api: %s\n" % e)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return

    # Return response event
    try:
        response = {
            "event_uuid": event["data"]["event_uuid"],
            "data": {
                "status": {
                    "active": job_status.active,
                    "failed": job_status.failed,
                    "succeeded": job_status.succeeded
                },
                "log": pod_log
            }
        }

        new_event = bytearray(json.dumps(response), encoding='utf-8')
        producer.send('automation_v1_response', key=b'event',
                      value=new_event).get(timeout=30)
        producer.flush(timeout=5)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())
        return
