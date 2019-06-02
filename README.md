# Lucy_Proxy - Experiments in Microservices Loose Coupling

## Smart Proxy / Ingress

Provide a generic ingress api routing to Kafka topic queues for backend apps
to consume (e.g. using kubeless functions to loosely couple the apis from
backend apis)

### Setup Environment
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

### Configure
See `config.yaml` for exposed api paths and related kafka queue topics.

### Feed requests to a Kafka Queue
(e.g. to be picked up by Kubeless function)

#### POST a Request
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
