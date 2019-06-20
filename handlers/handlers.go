package handlers

import (
	"sync"

	"github.com/gbevan/lucygw/jsonutils"
)

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
