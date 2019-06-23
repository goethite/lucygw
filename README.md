# lucygw - Experiments in Microservices Loose Coupling with Go, Kafka and Python
(formally called `lucy_proxy`)

Provide a generic ingress api routing to Kafka topic queues for backend apps
to consume (e.g. using kubeless functions or dedicated services to loosely
couple with backend apis).

## Setup Environment
Port-Forward:
```bash
kubectl -n kubeless port-forward --address 0.0.0.0 service/kafka 9092
```

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

Start a test listener for the callback (e.g. with netcat, in this case in the
vagrant instance):
```bash
$ nc -l 18080
```

Post a request with the `X-Lucygw-Cb` header:
```bash
$ curl -sS \
  'http://127.0.0.1:3303/automation/v1/play?group=goethite&name=dump.yml' \
  -X POST \
  -H "Content-type: application/json" \
  --data '{}' \
  -H 'X-Lucygw-Cb: http://127.0.0.1:18080/callback'
```

returns immediately with:
```json
{"callback_url":"http://127.0.0.1:18080/callback","event_uuid":"66bf0e1f-95ca-11e9-8b4a-0242ac110002"}
```

and later netcat reports the completed job:
```
POST /callback HTTP/1.1
Host: 127.0.0.1:18080
User-Agent: Go-http-client/1.1
Content-Length: 904
Content-Type: application/json
Accept-Encoding: gzip

{"data":{"log":"\nPLAY [all] *********************************************************************\n\nTASK [Gathering Facts] *********************************************************\nok: [127.0.0.1]\n\nTASK [debug] *******************************************************************\nok: [127.0.0.1] =\u003e {\n    \"ansible_password\": \"VARIABLE IS NOT DEFINED!\"\n}\n\nTASK [debug] *******************************************************************\nok: [127.0.0.1] =\u003e {\n    \"ansible_connection\": \"local\"\n}\n\nTASK [shell] *******************************************************************\nchanged: [127.0.0.1]\n\nPLAY RECAP *********************************************************************\n127.0.0.1                  : ok=4    changed=1    unreachable=0    failed=0   \n\n","status":{"active":null,"failed":null,"succeeded":1}},"event_uuid":"66bf0e1f-95ca-11e9-8b4a-0242ac110002"}
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
