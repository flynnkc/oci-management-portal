package main

import (
	"fmt"
	"log/slog"

	"github.com/gorilla/mux"
)

// getRouter initializes the router & handlers to de-clutter main
func getRouter(host string) *mux.Router {

	log := slog.Default()
	log.Debug("Setting handlers on Router")

	rtr := mux.NewRouter()

	/*
		// Middleware
		// Adding middleware is called in LIFO (Last In First Out) order
		rtr.Use(handlers.RecoveryHandler)
		rtr.Use(handlers.LogRequest)
		rtr.Use(handlers.CompressRequest)

		// Other Routes
		rtr.PathPrefix("/health").Handler(http.HandlerFunc(handlers.HandleHealth)).Methods("GET")
		rtr.PathPrefix("/").Handler(http.HandlerFunc(handlers.WriteHandler)).Methods("POST")

		// 404 Page
		rtr.NotFoundHandler = http.HandlerFunc(handlers.MinimalNotFound404Handler)
	*/

	// Walk routes to add Host to each if host is provided
	if host != "" {
		log.Debug("Walking routes")
		err := rtr.Walk(func(route *mux.Route, router *mux.Router,
			ancestors []*mux.Route) error {
			route.Host(host)
			return nil
		})
		if err != nil {
			panic(err)
		}
	}

	log.Debug("Returning new Router",
		"Router", fmt.Sprintf("%+v", rtr))

	return rtr
}
