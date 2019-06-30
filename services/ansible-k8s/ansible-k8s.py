
# import sys
import os
import traceback
import time
import json
from yaml import load, dump
import base64
# import tempfile

from kubernetes import client, config
from kafka import KafkaProducer, KafkaConsumer

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GROUP_CONFIG_FILE = "./group_config.yaml"

group_config = load(open(GROUP_CONFIG_FILE, 'r'))
print("group_config:", group_config)

# config.load_incluster_config()
config.load_kube_config(config_file=os.environ['KUBECONFIG'])

v1 = client.CoreV1Api()

consumer = KafkaConsumer(
    "automation_v1_request",
    bootstrap_servers=['127.0.0.1:9092']
    # bootstrap_servers=['kafka.kubeless.svc.cluster.local:9092']
)


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


def sendError(event_uuid, code, err, producer):
    try:
        response = {
            "event_uuid": event_uuid,
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


def wrapped(evbody, producer):
    # NOTE: if you catch any errors here then they wont be reported back to the
    # user.  See usage of sendError() for reporting errors back
    path = evbody["path"]
    form = evbody["form"]  # e.g. ?group=goethite&name=my-task
    method = evbody["method"]   # POST/GET/etc
    headers = evbody["headers"]

    data = {}
    try:
        dataStr = base64.b64decode(evbody["body"])
    except TypeError as err:
        sendError(
            evbody["event_uuid"],
            400,
            "Failed to decode base64 data: %s, err: %s" % (
                evbody["body"], err),
            producer
        )
        return

    try:
        data = json.loads(dataStr)
    except json.JSONDecodeError as err:
        sendError(
            evbody["event_uuid"],
            400,
            "Failed to decode json data: %s, err: %s" % (dataStr, err),
            producer
        )
        return

    print("%s: %s form: %s, data: %s, evbody: %s" %
          (method, path, form, data, evbody))
    print("headers: %s" % (headers))

    if "targets" not in data:
        sendError(evbody["event_uuid"], 400,
                  "request body must have targets", producer)
        return

    # body: {
    #   targets: { // equiv to ansible inv
    #     hosts: {"host_a": {host_vars_here...}, ...}, or
    #     hosts: ["host_a", ...],
    #     groups: {
    #       a_group: {
    #         hosts: as hosts above,
    #         params: {group_vars_here...}
    #       }, ...
    #     },
    #     params: {inv vars for all groups}
    #   },
    #   params: {overriding global vars, i.e. ansible --extra-vars=...}
    # }
    inv = {
        "all": {
            "hosts": {},
            "children": {}
        }
    }
    # hosts and host_vars in default "all" group
    if "hosts" in data["targets"]:
        for host_name in data["targets"]["hosts"]:  # dicts of hosts objs
            if isinstance(data["targets"]["hosts"], list):
                inv["all"]["hosts"][host_name] = {}
            else:
                inv["all"]["hosts"][host_name] = data["targets"]["hosts"][host_name]

    if "groups" in data["targets"]:
        all_children = inv["all"]["children"]
        for group_name in data["targets"]["groups"]:
            group = data["targets"]["groups"][group_name]
            # hosts and host_vars for hosts in this group
            if "hosts" in group:
                for host_name in group["hosts"]:
                    if isinstance(group["hosts"], list):
                        all_children[group_name] = {}
                    else:
                        all_children[group_name] = group["hosts"][host_name]
            # group_vars
            if "params" in group:
                all_children[group_name]["vars"] = group["params"]

    # group "all" vars in inventory
    if "params" in data["targets"]:
        inv["all"]["vars"] = data["targets"]["params"]

    extra_vars = {}
    if "params" in data:
        extra_vars = data["params"]

    inv_yaml = dump(inv)
    print("inv_yaml:\n%s" % inv_yaml)
    inv_b64 = base64.b64encode(
        bytearray(inv_yaml, encoding="utf-8")
    )

    # Encode data params to be injected as a extra_vars file (YAML)
    extra_vars_yaml = dump(extra_vars)
    print("extra_vars_yaml:\n%s" % extra_vars_yaml)
    extra_vars_b64 = base64.b64encode(
        bytearray(extra_vars_yaml, encoding='utf-8')
    )

    # Create inv/vars init container to prepopulate container
    volumes = [
        {
            "name": "inventory",
            "medium": "Memory",
            "emptyDir": {}
        }
    ]
    volume_mounts = [
        {
            "mountPath": "/tmp/inv",
            "name": "inventory"
        }
    ]
    inv_init_container = {
        "name": "init-inventory",
        "image": "busybox",
        "command": [
            "sh",
            "-c",
            """
            echo %s | base64 -d > /tmp/inv/hosts.yaml &&
            echo %s | base64 -d > /tmp/inv/vars.yaml
            """ % (
                inv_b64.decode('utf-8'),
                extra_vars_b64.decode('utf-8')
            )
        ],
        "volumeMounts": volume_mounts
    }

    namespace = "default"

    body = {}
    # Routing
    if path == "/ping":
        body = {
            "api_version": "batch/v1",
            "kind": "Job",
            "metadata": {"name": "myjob"},
            "spec": {
                "template": {
                    "spec": {
                        "initContainers": [
                            inv_init_container
                        ],
                        "containers": [
                            {
                                "name": "myjob",
                                "image": "goethite/gostint-ansible:2.7.5",
                                "imagePullPolicy": "Always",
                                "command": ["ansible"],
                                "args": [
                                    "-i", "/tmp/inv/hosts.yaml",
                                    "-m", "ping", "127.0.0.1"
                                ],
                                "volumeMounts": volume_mounts,
                                "env": [
                                    # TODO: for hashivault_vars plugin
                                    {"name": "HASHIVAULT_VARS_DEBUG", "value": "1"},
                                    {"name": "VAULT_SKIP_VERIFY", "value": "1"},
                                    {"name": "VAULT_ADDR", "value": "TODO"},
                                    {"name": "VAULT_TOKEN", "value": "TODO"}
                                    # TODO: resolve token from pull-mode approle
                                ]
                            }
                        ],
                        "volumes": volumes,
                        "restartPolicy": "Never"
                    }
                }
            }
        }
        send(evbody["event_uuid"], namespace, body, producer)

    elif path == "/play":
        # TODO: demo loose coupling here
        group = form.get("group")[0]
        name = form.get("name")[0]

        if group is None or group == "":
            sendError(evbody["event_uuid"], 400,
                      "param group is missing", producer)
            return
        if name is None or name == "":
            sendError(evbody["event_uuid"], 400,
                      "param name is missing", producer)
            return

        if group not in group_config["groups"]:
            sendError(
                evbody["event_uuid"],
                400,
                "param group does not have entry in group_config",
                producer
            )
            return
        image = group_config["groups"][group]["image"]

        body = {
            "api_version": "batch/v1",
            "kind": "Job",
            "metadata": {"name": "myjob"},  # TODO:
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "spec": {
                        "initContainers": [
                            inv_init_container
                        ],
                        "containers": [
                            {
                                "name": "myjob",  # TODO:
                                "image": image,
                                "imagePullPolicy": "Always",
                                "args": [
                                    "-i", "/tmp/inv/hosts.yaml",
                                    name,
                                    "--extra-vars", "@/tmp/inv/vars.yaml"
                                ],
                                "volumeMounts": volume_mounts
                            }
                        ],
                        "volumes": volumes,
                        "restartPolicy": "Never"
                    }
                }
            }
        }
        send(evbody["event_uuid"], namespace, body, producer)

    else:
        sendError(evbody["event_uuid"], 501,
                  "Path %s not implemented" % path, producer)


def send(event_uuid, namespace, body, producer):
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
        "event_uuid": event_uuid,
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


for event in consumer:
    # print(event)

    # Establish the producer for each function call, cannot be global...?
    producer = KafkaProducer(
        bootstrap_servers=['127.0.0.1:9092'])

    evbody = {}
    value = event.value
    if value is not None and value != "":
        evbody = json.loads(value)
    # print("evbody:", evbody)

    try:
        wrapped(evbody, producer)
    except Exception as err:
        try:
            response = {
                "event_uuid": evbody["event_uuid"],
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
