# Lucy_Proxy - Experiments in Microservices Loose Coupling

Provide a generic ingress api routing to Kafka topic queues for backend apps
to consume (e.g. using kubeless functions to loosely couple the apis from
backend apis).

## Setup Environment
Port-Forward:
```bash
kubectl -n kubeless port-forward --address 0.0.0.0 service/kafka 9092
```

```bash
vagrant up
vagrant ssh
cd lucy_proxy
go run main.go
```

## Configure
See [config.yaml](./config.yaml) for exposed api paths and related kafka queue topics.

## API Discovery
```bash
curl -sS http://127.0.0.1:3303 | jq
{
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
  "description": "Lucy_Proxy - Loose Coupling API Proxy",
  "title": "Lucy_Proxy - Loose Coupling API Proxy"
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

## Kubeless consumer examples

See:
* [ansible-coupler.py](kubeless/ansible-coupler.py) run ansible in docker
  containers as k8s batch jobs.
* [gostint-coupler.py](kubeless/gostint-coupler.py) (in progress) PoC stub for
  gostint api.
