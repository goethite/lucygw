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

curl -sS \
  'http://127.0.0.1:3303/automation/v1/play?group=goethite%2fgostint-ansible%3a2.7.5&name=dump.yml' \
  -X POST \
  -H "Content-type: application/json" \
  --data '{}' | jq .data.log -r

Returns:

PLAY [all] *********************************************************************

TASK [Gathering Facts] *********************************************************
ok: [127.0.0.1]

TASK [debug] *******************************************************************
ok: [127.0.0.1] => {
    "ansible_password": "VARIABLE IS NOT DEFINED!"
}

TASK [debug] *******************************************************************
ok: [127.0.0.1] => {
    "ansible_connection": "local"
}

TASK [shell] *******************************************************************
changed: [127.0.0.1]

PLAY RECAP *********************************************************************
127.0.0.1                  : ok=4    changed=1    unreachable=0    failed=0

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
    print("event:", event)

    # Establish the producer for each function call, cannot be global...
    producer = KafkaProducer(
        bootstrap_servers=['kafka.kubeless.svc.cluster.local:9092'])

    try:
        wrapped(event, context, producer)
    except Exception as err:
        try:
            response = {
                "event_uuid": event["data"]["event_uuid"],
                "code": 500,
                "error": str(err),
                "stacktrace": traceback.format_exc()
            }

            new_event = bytearray(json.dumps(response), encoding='utf-8')
            producer.send('automation_v1_response', key=b'event',
                          value=new_event).get(timeout=30)
            producer.flush(timeout=5)
        except Exception as err:
            print(str(err))
            print(traceback.format_exc())


def sendError(event, code, err, producer):
    try:
        response = {
            "event_uuid": event["data"]["event_uuid"],
            "code": code,
            "error": err,
            "stacktrace": ""
        }

        new_event = bytearray(json.dumps(response), encoding='utf-8')
        producer.send('automation_v1_response', key=b'event',
                      value=new_event).get(timeout=30)
        producer.flush(timeout=5)
    except Exception as err:
        print(str(err))
        print(traceback.format_exc())


def wrapped(event, context, producer):
    body = {}
    if event["data"]["body"] is not None and event["data"]["body"] != "":
        body = json.loads(
            base64.b64decode(event["data"]["body"])
        )
    path = event["data"]["path"]
    form = event["data"]["form"]
    method = event["data"]["method"]
    headers = event["data"]["headers"]

    print("%s: %s form: %s, body: %s" % (method, path, form, body))

    namespace = "default"

    # Routing
    if path == "/ping":
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
                                # "image": "jmal98/ansiblecm:2.5.5",
                                "image": "goethite/gostint-ansible:2.7.5",
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
        send(event, namespace, body, producer)

    elif path == "/play":
        # TODO: demo loose coupling here
        group = form.get("group")[0]
        name = form.get("name")[0]

        if group is None or group == "":
            sendError(event, 501, "param group is missing", producer)
            return
        if name is None or name == "":
            sendError(event, 501, "param name is missing", producer)
            return

        body = {
            "api_version": "batch/v1",
            "kind": "Job",
            "metadata": {"name": "myjob"},  # TODO:
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "spec": {
                        "initContainers": [
                            {
                                "name": "init-inventory",
                                "image": "busybox",
                                "command": [
                                    "sh",
                                    "-c",
                                    "echo '127.0.0.1 ansible_connection=local' > /tmp/inv/hosts"
                                ],
                                "volumeMounts": [
                                    {
                                        "mountPath": "/tmp/inv",
                                        "name": "inventory"
                                    }
                                ]
                            }
                        ],
                        "containers": [
                            {
                                "name": "myjob",  # TODO:
                                # "image": "jmal98/ansiblecm:2.5.5",
                                # "image": "goethite/gostint-ansible:2.7.5",
                                "image": group,
                                "imagePullPolicy": "Always",
                                # "command": ["ansible"],
                                "args": [
                                    "-i", "/tmp/inv/hosts",
                                    # "dump.yml"
                                    name
                                ],
                                "volumeMounts": [
                                    {
                                        "mountPath": "/tmp/inv",
                                        "name": "inventory"
                                    }
                                ]
                            }
                        ],
                        "volumes": [
                            {
                                "name": "inventory",
                                "medium": "Memory",
                                "emptyDir": {}
                            }
                        ],
                        "restartPolicy": "Never"
                    }
                }
            }
        }
        send(event, namespace, body, producer)

    else:
        sendError(event, 501, "Path %s not implemented" % path, producer)


def send(event, namespace, body, producer):
    batchApi = client.BatchV1Api()
    batchApi_resp = batchApi.create_namespaced_job(
        namespace=namespace,
        body=body
    )

    # print("create batchApi_resp:", batchApi_resp)

    job_status = {}
    while True:
        time.sleep(1)
        job_status = get_job_status(batchApi, namespace, "myjob")  # TODO:
        if job_status.active is None:
            break

    pods = v1.list_namespaced_pod(
        namespace, label_selector="job-name=myjob")  # TODO:

    pod = pods.items[0]
    pod_name = pod.metadata.name

    # Get log from job pod
    pod_log = v1.read_namespaced_pod_log(
            pod_name,
            namespace,
            # timestamps=True
            tail_lines=100  # limit to last n lines
        )
    # print("pod_log:", pod_log)

    batchApi.delete_namespaced_job(
        namespace=namespace,
        name="myjob",
        body={}
    )

    v1.delete_namespaced_pod(pod_name, namespace, body={})
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
