package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/go-chi/chi"
	"github.com/go-chi/render"
	"github.com/segmentio/kafka-go"

	"github.com/gbevan/lucygw/jsonutils"
)

// Kafka Subrouter for Loosely Coupled queued requests via kafka
func (h *Handlers) Kafka(service *jsonutils.JSONMap, kafkaCfg *jsonutils.JSONMap) http.Handler {
	log.Printf("Kafka service: %v", service)

	// Create a kafka writer for this service topic
	kw := h.InitKafka(service, kafkaCfg)

	r := chi.NewRouter()

	// All HTTP requests on this service path simply get forwarded to the kafka
	// queue.
	r.HandleFunc("/*", func(w http.ResponseWriter, r *http.Request) {
		servicePath := (*service)["path"].(string)
		evReq, err := CreateEventReq(&servicePath, w, r)
		if err != nil {
			render.Render(w, r, ErrInternalError(err))
			return
		}

		reqBytes, err := evReq.GetBytes()
		if err != nil {
			render.Render(w, r, ErrInternalError(err))
			return
		}

		respChan := make(chan jsonutils.JSONMap)
		cor := h.AddCorrelator(evReq.EventUUID, &respChan, evReq)

		// Send to any subscribers (e.g. a kubeless function wrapping a backend api
		// to be loosely coupled)
		err = kw.WriteMessages(
			context.Background(),
			kafka.Message{
				Key:   []byte("request"),
				Value: reqBytes,
			},
		)
		if err != nil {
			render.Render(w, r, ErrKafkaError(err))
			return
		}

		// TODO: Look into having a dedicated go routine to handle responses
		// requiring callbacks.  Would need the cb header to be passed to the
		// kubeless/service and returned in the response - removing the need to
		// persist it here in the API GW to allow for HA/stateless operation.
		// The kubeless/service would need to persist this as a meta tag in the
		// kubernetes job, so it can recover on restart...
		if val, ok := cor.preservedHeaders["X-Lucygw-Cb"]; ok {
			if val[0] != "" {
				render.JSON(w, r, jsonutils.JSONMap{
					"event_uuid":   evReq.EventUUID,
					"callback_url": val[0],
				})
				go waitForRespAndCallback(w, r, &respChan, cor)
			} else {
				render.Render(w, r, ErrInvalidJobRequest(errors.New("Header X-Lucygw-Cb has empty string")))
			}
		} else {
			waitForResp(w, r, &respChan)
		}
	})

	return r
}

func waitForResp(w http.ResponseWriter, r *http.Request, respChan *chan jsonutils.JSONMap) {
	// wait for response event (by uuid) from kafka
	resp := <-*respChan
	log.Printf("resp from chan: %v", resp)
	// log.Printf("for correlation: %v", cor)

	if _, ok := resp["error"]; ok {
		code := 500
		if _, ok := resp["code"]; ok {
			code = int(resp["code"].(float64))
		}
		render.Render(w, r, &ErrResponse{
			Err:            errors.New(resp["error"].(string)),
			HTTPStatusCode: code,
			StatusText:     "Execution Error.",
			ErrorText: fmt.Sprintf(
				"%s\n%s",
				resp["error"].(string),
				resp["stacktrace"].(string),
			),
		})
		return
	}

	render.JSON(w, r, resp)
}

// NOTE: Using the header X-Lucygw-Cb like this is a security risk and could
// be abused in a DDOS attack - a better solution would be to have a whitelist
// of authorised callback urls for the api route.
func waitForRespAndCallback(w http.ResponseWriter, r *http.Request, respChan *chan jsonutils.JSONMap, cor *Correlation) {
	// wait for response event (by uuid) from kafka
	resp := <-*respChan
	log.Printf("resp(for cb) from chan: %v", resp)
	log.Printf("for correlation: %v", cor)

	if _, ok := resp["error"]; ok {
		code := 500
		if _, ok := resp["code"]; ok {
			code = int(resp["code"].(float64))
		}
		// Callback with error
		body, err := json.Marshal(&ErrResponse{
			Err:            errors.New(resp["error"].(string)),
			HTTPStatusCode: code,
			StatusText:     "Execution Error.",
			ErrorText: fmt.Sprintf(
				"%s\n%s",
				resp["error"].(string),
				resp["stacktrace"].(string),
			),
		})
		if err != nil {
			log.Printf("Error: %s", err)
			return
		}
		res, err := http.Post(
			cor.preservedHeaders["X-Lucygw-Cb"][0],
			"application/json",
			bytes.NewBuffer(body),
		)
		if err != nil {
			log.Printf("Error: %s", err)
			return
		}
		log.Printf("callback error res: %v", res)
		return
	}

	// Callback results
	body, err := json.Marshal(resp)
	if err != nil {
		log.Printf("Error: %s", err)
		return
	}
	res, err := http.Post(
		cor.preservedHeaders["X-Lucygw-Cb"][0],
		"application/json",
		bytes.NewBuffer(body),
	)
	if err != nil {
		log.Printf("Error: %s", err)
		return
	}
	log.Printf("callback res: %v", res)
}

func openTopicReader(brokers []string, service *jsonutils.JSONMap) *kafka.Reader {
	ns, _ := time.ParseDuration("3s")
	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers: brokers,
		Topic:   (*service)["response_topic"].(string),
		MaxWait: time.Duration(ns.Nanoseconds()),
	})
	return r
}

// InitKafka - Initialise a kafka writer for service and topic
func (h *Handlers) InitKafka(service *jsonutils.JSONMap, kafkaCfg *jsonutils.JSONMap) *kafka.Writer {
	brokers := []string{}
	for _, b := range (*kafkaCfg)["brokers"].(jsonutils.JSONArray) {
		brokers = append(brokers, b.(string))
	}
	r := openTopicReader(brokers, service)
	w := kafka.NewWriter(kafka.WriterConfig{
		Brokers:  brokers,
		Topic:    (*service)["request_topic"].(string),
		Balancer: &kafka.LeastBytes{},
	})

	go func() {
		for {
			m, err := r.ReadMessage(context.Background())
			if err != nil {
				log.Printf("Failed to read from topic '%s', will retry", (*service)["response_topic"].(string))
				log.Printf("err: %v", err)
				time.Sleep(5 * time.Second)

				// Recover reader connection
				r.Close()
				r = openTopicReader(brokers, service)
				continue
			}
			log.Printf("msg rcv offset: %d: key: %s, value: %s", m.Offset, m.Key, m.Value)

			payload := jsonutils.JSONMap{}
			err = json.Unmarshal(m.Value, &payload)
			if err != nil {
				log.Printf("Failed to unmarshal json from event queue")
				continue
			}

			if payload["event_uuid"] == nil || payload["event_uuid"] == "" {
				log.Printf("Missing event uuid, skipping")
				continue
			}

			ccUUID := payload["event_uuid"].(string)
			cor := h.GetCorrelator(ccUUID)
			if cor != nil {
				log.Printf("Found correlator (channel)")
				*cor.respChan <- payload
				h.DeleteCorrelator(ccUUID)
			} else {
				log.Printf("NOT Found correlator channel")
			}
		}
	}()

	return w
}
