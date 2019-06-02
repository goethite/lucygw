package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"reflect"

	"github.com/go-chi/chi"
	"github.com/go-chi/chi/middleware"
	"github.com/go-chi/render"
	yaml "gopkg.in/yaml.v2"

	"github.com/gbevan/lucy_proxy/handlers"
	"github.com/gbevan/lucy_proxy/jsonutils"
)

var (
	serverPort int
	config     string
	cfgYAML    interface{}
)

func init() {
	flag.IntVar(&serverPort, "port", 3303, "Port to listen on")
	flag.StringVar(&config, "config", "./config.yaml", "Config file (json)")
}

func loadCfg() jsonutils.JSONMap {
	file, err := os.Open(config)
	if err != nil {
		panic(err)
	}
	decoder := yaml.NewDecoder(file)
	err = decoder.Decode(&cfgYAML)
	if err != nil {
		panic(err)
	}
	log.Printf("cfgYAML: %v", cfgYAML)

	cfg := jsonutils.RecursiveToJSON(cfgYAML)
	log.Printf("cfg: %v", cfg)

	return cfg.(jsonutils.JSONMap)
}

func main() {
	flag.Parse()

	cfg := loadCfg()
	// log.Printf("cfg: %v", cfg)
	log.Printf("Site: %v", cfg["site"])
	// log.Printf("Site Title: %v", cfg.Site.Title)
	// log.Printf("Site Description: %v", cfg.Site.Description)
	// log.Printf("Site Links: %v", cfg.Site.Links)
	kafkaCfg := cfg["kafka"].(jsonutils.JSONMap)
	handlers := handlers.Handlers{}
	// handlers.Init(&cfg)

	router := chi.NewRouter()
	router.Use(
		render.SetContentType(render.ContentTypeJSON),
		middleware.Logger,
		middleware.DefaultCompress,
		middleware.RedirectSlashes,
		middleware.Recoverer,
		// authenticate,
	)

	// Default site doc
	router.Get("/", func(w http.ResponseWriter, r *http.Request) {
		render.JSON(w, r, cfg["site"])
	})

	// Establish service handlers
	for _, s := range cfg["services"].(jsonutils.JSONArray) {
		service := s.(jsonutils.JSONMap)
		name := service["name"].(string)
		path := service["path"].(string)
		handler := service["handler"].(string)
		requestTopic := service["request_topic"].(string)
		responseTopic := service["response_topic"].(string)

		log.Printf(
			"loading service: %s at path %s with handler %s, topics(req/resp): %s/%s",
			name,
			path,
			handler,
			requestTopic,
			responseTopic,
		)

		// Get Named handler for path mount
		h := reflect.ValueOf(&handlers)
		m := h.MethodByName(handler)
		if !m.IsValid() {
			panic(
				fmt.Sprintf(
					"Failed lookup of service handler '%s', from config yaml, in handlers module",
					handler,
				),
			)
		}

		// Mount the service path
		router.Mount(path, func() http.Handler {
			// Call the service handler
			return m.Call(
				[]reflect.Value{
					reflect.ValueOf(&service),
					reflect.ValueOf(&kafkaCfg),
				},
			)[0].Interface().(http.Handler)
		}())
	}

	log.Printf("lucy_proxy listening on https port %d", serverPort)
	// log.Fatal(http.ListenAndServeTLS(
	log.Fatal(http.ListenAndServe(
		fmt.Sprintf(":%d", serverPort),
		router,
	))
}
