package main

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"time"
)

var ErrInvalidHandler error = errors.New("invalid log handler selection")

func main() {
	opts, err := getOpts()
	if err != nil {
		fmt.Println("Exiting due to invalid flag values:", err)
		os.Exit(2)
	}

	run(opts)
}

func run(opts *opts) {
	// Set logging behavior
	// Default log handler
	handler, err := createLogHandler(opts.format, opts.logLevel, opts.logFile)
	log := slog.New(handler)
	slog.SetDefault(log)
	if err != nil {
		log.Error("Error creating handler",
			"Error", err,
			"Failed to handler", fmt.Sprintf("%+v", handler))
	}

	// Server Error Log Handler
	eh, err := createLogHandler(opts.format, opts.logLevel, opts.logErrFile)
	if err != nil {
		log.Error("Error creating error handler",
			"Error", err,
			"Failed to handler", fmt.Sprintf("%+v", eh))
	}

	log.Debug("Flag variables set",
		"Options", fmt.Sprintf("%+v", opts),
	)

	m := getRouter(opts.host)

	// Run server(s) in goroutine
	// Running HTTP & HTTPS concurrently is unreasonable due to the way hugo
	// writes URLs directly into pages, will not support both protocols
	var servers []*http.Server
	s := &http.Server{
		Addr:         fmt.Sprintf("%v:%v", opts.address, opts.port),
		WriteTimeout: time.Second * 15,
		ReadTimeout:  time.Second * 15,
		IdleTimeout:  time.Second * 60,
		Handler:      m,
		ErrorLog:     slog.NewLogLogger(eh, slog.LevelError),
	}
	servers = append(servers, s)
	go func() {
		log.Info(fmt.Sprintf("Starting HTTP Server at %v", s.Addr))
		if err := s.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("%v", err)
		}
	}()

	if opts.keyFile != "" && opts.certFile != "" {
		s := &http.Server{
			Addr: fmt.Sprintf("%v:%v", opts.address,
				opts.tlsPort),
			WriteTimeout: time.Second * 15,
			ReadTimeout:  time.Second * 15,
			IdleTimeout:  time.Second * 60,
			Handler:      m,
			ErrorLog:     slog.NewLogLogger(eh, slog.LevelError),
			TLSConfig:    &tls.Config{MinVersion: tls.VersionTLS12},
		}
		servers = append(servers, s)
		go func() {
			log.Info(fmt.Sprintf("Starting HTTPS Server at %v", s.Addr))
			err := s.ListenAndServeTLS(opts.certFile, opts.keyFile)
			if err != nil && err != http.ErrServerClosed {
				log.Error("Server error", "Error", err)
			}
		}()
	}

	// Create channel that takes signal interrupt
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)

	// Block until signal
	<-c

	var wg sync.WaitGroup
	for _, server := range servers {

		wg.Add(1)
		go func(server *http.Server) {
			ctx, cancel := context.WithTimeout(context.Background(), time.Second*3)
			defer cancel()
			defer wg.Done()

			log.Info("Shutting down server...", "Server", server.Addr)
			if err := server.Shutdown(ctx); err != nil {
				log.Error("Server shutdown failed", "error", err)
			}
			<-ctx.Done()
		}(server)
	}

	wg.Wait()
	log.Info("Shutdown Complete")
}

// setLogLevel translates the level flag into slog level
func setLogLevel(level string) slog.Level {
	m := map[string]slog.Level{
		"debug": slog.LevelDebug,
		"warn":  slog.LevelWarn,
		"error": slog.LevelError,
		"info":  slog.LevelInfo,
	}

	return m[level]
}

func createLogHandler(format, logLevel, file string) (slog.Handler, error) {

	writer, err := setLogFile(file)
	if err != nil {
		writer = os.Stdout
	}

	if format == "text" {
		return slog.NewTextHandler(writer, &slog.HandlerOptions{
			Level: setLogLevel(logLevel)}), err
	} else if format == "json" {
		return slog.NewJSONHandler(writer, &slog.HandlerOptions{
			Level: setLogLevel(logLevel)}), err
	} else {
		return slog.NewTextHandler(os.Stdout, nil),
			ErrInvalidHandler
	}

}

func setLogFile(file string) (io.Writer, error) {

	switch file {
	case "stdout":
		return os.Stdout, nil
	case "stderr":
		return os.Stderr, nil
	}

	f, err := os.OpenFile(file, os.O_WRONLY|os.O_APPEND|os.O_CREATE, 0640)
	if err != nil {
		return nil, err
	}

	return f, nil
}
