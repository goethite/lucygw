# ansible-k8s service PoC

## Setup Dev

Port-Forward:
```bash
kubectl -n kubeless port-forward --address 0.0.0.0 service/kafka 9092
```

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
  --data '{}' | jq .data.log -r
```
