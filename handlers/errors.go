package handlers

import (
	"net/http"

	"github.com/go-chi/render"
)

// ErrResponse struct for http error responses
type ErrResponse struct {
	Err            error `json:"-"` // low-level runtime error
	HTTPStatusCode int   `json:"-"` // http response status code

	StatusText string `json:"status"`          // user-level status message
	AppCode    int64  `json:"code,omitempty"`  // application-specific error code
	ErrorText  string `json:"error,omitempty"` // application-level error message, for debugging
}

// Render to render a http return code
func (e *ErrResponse) Render(w http.ResponseWriter, r *http.Request) error {
	render.Status(r, e.HTTPStatusCode)
	return nil
}

// ErrInternalError return internal error
func ErrInternalError(err error) render.Renderer {
	return &ErrResponse{
		Err:            err,
		HTTPStatusCode: 500,
		StatusText:     "Internal Error.",
		ErrorText:      err.Error(),
	}
}

// ErrKafkaError return kafka error
func ErrKafkaError(err error) render.Renderer {
	return &ErrResponse{
		Err:            err,
		HTTPStatusCode: 500,
		StatusText:     "Kafka Error.",
		ErrorText:      err.Error(),
	}
}

// ErrInvalidJobRequest return invalid job request error
func ErrInvalidJobRequest(err error) render.Renderer {
	return &ErrResponse{
		Err:            err,
		HTTPStatusCode: 400,
		StatusText:     "Invalid job request.",
		ErrorText:      err.Error(),
	}
}
