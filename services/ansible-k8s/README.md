# ansible-k8s service PoC

## Setup Dev

```bash
cd services/ansible-k8s
virtualenv -p python3 .
source bin/activate
(ansible-k8s) $ pip3 install -r requirements.txt
```

### Running
See file [group_config.yaml](./group_config.yaml) for group to docker image
mapping.

```bash
(ansible-k8s) $ export KUBECONFIG=...
(ansible-k8s) $ python3 ansible-k8s.py
```

```bash
curl -sS \
  'http://127.0.0.1:3303/automation/v1/play?group=goethite&name=dump.yml' \
  -X POST \
  -H "Content-type: application/json" \
  --data '{"params": {"ansible_connection": "local"}, "targets": {"hosts": ["127.0.0.1"]}}' \
  | jq .data.log -r
```

```
PLAY [all] *********************************************************************
Error: Failed to authenticate with Vault: HTTPConnectionPool(host='127.0.0.1', port=8200): Max retries exceeded with url: /v1/auth/token/lookup-self (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f496f253550>: Failed to establish a new connection: [Errno 111] Connection refused',))

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
127.0.0.1                  : ok=4    changed=1    unreachable=0    failed=
```
