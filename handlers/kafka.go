package handlers

import (
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
		h.AddCorrelator(evReq.EventUUID, &respChan)

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

		// wait for response event (by uuid) from kafka
		resp := <-respChan
		log.Printf("resp from chan: %v", resp)

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
	})

	return r
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

	go func(c *map[string]*chan jsonutils.JSONMap) {
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
			cc := h.GetCorrelator(ccUUID)
			if cc != nil {
				log.Printf("Found correlator channel")
				*cc <- payload
				h.DeleteCorrelator(ccUUID)
			} else {
				log.Printf("NOT Found correlator channel")
			}
		}
	}(&correlator)

	return w
}
