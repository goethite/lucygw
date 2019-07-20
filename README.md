# lucygw - Experiments in Microservices Loose Coupling with Go, Kafka and Python

Provide a generic ingress api routing to Kafka topic queues for backend apps
to consume (e.g. using kubeless functions or dedicated services) as loosely
couple apis.

This project is a playground for loose-coupling microservice apis. Contributions
are welcome - so feel free to raise Issues/Discussions/PRs.

## Setup Environment
My current setup is a MicroK8s server running the
[incubator/kafka](https://github.com/helm/charts/tree/master/incubator/kafka)
helm chart (with a few minor tweaks (for NodePort access to the brokers) -
which I will post soon on github) and Vagrant running lucygw:

```bash
vagrant up
vagrant ssh
cd lucygw
go run main.go
```

## Configure
See [config.yaml](./config.yaml) for exposed api paths and related kafka queue topics.

## API Discovery
```bash
curl -sS http://127.0.0.1:3303 | jq
{
  "services": [
    {
      "handler": "Kafka",
      "name": "ping",
      "path": "/ping",
      "request_topic": "ping",
      "response_topic": "ping"
    },
    {
      "handler": "Kafka",
      "name": "automation_v1",
      "path": "/automation/v1",
      "request_topic": "automation_v1_request",
      "response_topic": "automation_v1_response"
    }
  ],
  "site": {
    "_links": {
      "curies": [
        {
          "href": "https://github.example.com/mysite/docs.md",
          "name": "Site API"
        }
      ],
      "self": {
        "href": "/"
      }
    },
    "description": "lucygw - Loose Coupling API Proxy",
    "title": "lucygw - Loose Coupling API Proxy"
  }
}
```

## Feed requests to a Kafka Queue
(e.g. to be picked up by Kubeless function)

### POST a Request
```bash
curl -sS http://127.0.0.1:3303/ping \
  -X POST \
  -H "Content-type: application/json" \
  --data '{"foo":"bar"}'
```

```bash
curl -sS http://127.0.0.1:3303/automation/v1 \
  -X POST \
  -H "Content-type: application/json" \
  --data '{"foo":"bar"}'
```

Ansible ping:
```bash
curl -sS http://127.0.0.1:3303/automation/v1/ping \
  -X POST \
  -H "Content-type: application/json" \
  --data '{}' \
  | jq .data.log -r
```

```
[WARNING]: Unable to parse /etc/ansible/hosts as an inventory source
[WARNING]: No inventory was parsed, only implicit localhost is available
[WARNING]: provided hosts list is empty, only localhost is available. Note
that the implicit localhost does not match 'all'
127.0.0.1 | SUCCESS => {
   "changed": false,
   "ping": "pong"
}
```

Run playbook
```bash
curl -sS \
  'http://127.0.0.1:3303/automation/v1/play?group=goethite%2fgostint-ansible%3a2.7.5&name=dump.yml' \
  -X POST \
  -H "Content-type: application/json" \
  --data '{}' | jq .data.log -r
```

```
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
```

### POST a request with Asynchronous Callback
NOTE: This PoC implementation is currently for demo purposes only.

Start a test listener for the callback:
```bash
(ansible-k8s) > FLASK_APP=test/callback-listener.py flask run -h 0.0.0.0
```
(defaults to port 5000)

Post a request with the `X-Lucygw-Cb` header:
```bash
$ curl -sS \
  'http://127.0.0.1:3303/automation/v1/play?group=goethite&name=dump.yml' \
  -X POST \
  -H "Content-type: application/json" \
  --data '{}' \
  -H 'X-Lucygw-Cb: http://172.17.0.1:5000/callback'
```
(the IP 172.17.0.1 is the default docker ip of the parent host in the lucygw
service container )

returns immediately with:
```json
{"callback_url":"http://172.17.0.1:5000/callback","event_uuid":"ee85d16d-96ae-11e9-ba39-0242ac110002"}
```

and later `callback-listener.py` reports the completed job:
```
req: {
  "data": {
    "log": "\nPLAY [all] *********************************************************************\n\nTASK [Gathering Facts] *********************************************************\nok: [127.0.0.1]\n\nTASK [debug] *******************************************************************\nok: [127.0.0.1] => {\n    \"ansible_password\": \"VARIABLE IS NOT DEFINED!\"\n}\n\nTASK [debug] *******************************************************************\nok: [127.0.0.1] => {\n    \"ansible_connection\": \"local\"\n}\n\nTASK [shell] *******************************************************************\nchanged: [127.0.0.1]\n\nPLAY RECAP *********************************************************************\n127.0.0.1                  : ok=4    changed=1    unreachable=0    failed=0   \n\n",
    "status": {
      "active": null,
      "failed": null,
      "succeeded": 1
    }
  },
  "event_uuid": "ee85d16d-96ae-11e9-ba39-0242ac110002"
}
172.17.0.2 - - [24/Jun/2019 19:36:17] "POST /callback HTTP/1.1" 200 -
```

## Kubeless consumer examples

See:
* [ansible-coupler.py](kubeless/ansible-coupler.py) run ansible in docker
  containers as k8s batch jobs.
* [gostint-coupler.py](kubeless/gostint-coupler.py) (in progress) PoC stub for
  gostint api.

## Consumer service examples

See:
* [ansible-k8s](services/ansible-k8s) like ansible-coupler above, but as a
kafka consumer service.
* [callback-listener.py](services/ansible-k8s/test/callback-listener.py) - a
demo callback listener.
