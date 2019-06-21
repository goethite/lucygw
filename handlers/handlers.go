package handlers

import (
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"

	"github.com/google/uuid"

	"github.com/gbevan/lucygw/jsonutils"
)

// HandlerEventReq a generic event struct for forwarding via an event queue
// embedded by handlers as a base structure
type HandlerEventReq struct {
	EventUUID        string              `json:"event_uuid"`
	Method           string              `json:"method"`
	Path             string              `json:"path"`
	Headers          map[string][]string `json:"headers"`
	Body             []byte              `json:"body"`
	TransferEncoding []string            `json:"transfer_encoding"`
	Form             url.Values          `json:"form"`
}

// GetBytes get event structure as json byte array
func (hreq *HandlerEventReq) GetBytes() ([]byte, error) {
	reqBytes, err := json.Marshal(hreq)
	if err != nil {
		return nil, err
	}
	log.Printf("reqBytes: %s", reqBytes)
	return reqBytes, nil
}

// CreateEventReq map event to event structure
func CreateEventReq(servicePath *string, w http.ResponseWriter, r *http.Request) (*HandlerEventReq, error) {
	log.Printf("%s: %s:", r.Method, r.URL.Path)

	// Remove the service routing path to get the remaining target path
	targetPath := strings.TrimPrefix(r.URL.Path, (*servicePath))
	log.Printf("targetPath: %s", targetPath)

	bodyBytes, err := ioutil.ReadAll(r.Body)
	if err != nil {
		return nil, err
	}

	err = r.ParseForm()
	if err != nil {
		return nil, err
	}

	evUUID, err := uuid.NewUUID()
	if err != nil {
		return nil, err
	}

	// Build event from request
	evReq := HandlerEventReq{
		EventUUID:        evUUID.String(),
		Method:           r.Method,
		Path:             targetPath,
		Headers:          r.Header,
		Body:             bodyBytes,
		TransferEncoding: r.TransferEncoding,
		Form:             r.Form,
	}

	return &evReq, nil
}

var (
	correlator    = make(map[string]*chan jsonutils.JSONMap)
	correlatorMux sync.Mutex
)

// Handlers smart proxy api handlers
type Handlers struct {
}

// Init - initialise the handlers with kafka
// func (h *Handlers) Init(cfg *jsonutils.JSONMap) {
// }

// AddCorrelator adds UUID lookup for a request's response to be fed back to
// the requestor.
func (h *Handlers) AddCorrelator(ccUUID string, cc *chan jsonutils.JSONMap) {
	correlatorMux.Lock()
	correlator[ccUUID] = cc
	correlatorMux.Unlock()
}

// GetCorrelator Gets the response channel by request UUID
func (h *Handlers) GetCorrelator(ccUUID string) *chan jsonutils.JSONMap {
	correlatorMux.Lock()
	cc := correlator[ccUUID]
	correlatorMux.Unlock()
	return cc
}

// DeleteCorrelator deletes the UUID/response channel
func (h *Handlers) DeleteCorrelator(ccUUID string) {
	correlatorMux.Lock()
	delete(correlator, ccUUID)
	correlatorMux.Unlock()
}
