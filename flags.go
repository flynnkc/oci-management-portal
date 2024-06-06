package main

import (
	"errors"
	"net"
	"os"
	"strings"

	flag "github.com/spf13/pflag"
)

var localAddr net.IP = net.IPv4(127, 0, 0, 1)

type opts struct {
	address net.IP
	//bucket   string
	certFile string
	//file     string
	format string
	host   string
	//instancePrincipal bool
	keyFile    string
	logErrFile string
	logFile    string
	logLevel   string
	port       int
	//profile           string
	tlsPort int
}

func getOpts() (*opts, error) {
	//usr, _ := user.Current()

	fs := flag.NewFlagSet("default", flag.ExitOnError)

	// Mandatory Flags
	//bucket := fs.StringP("bucket", "b", "",
	//	"Bucket name containing page data (e.g. My-Bucket)")

	// Optional Fields
	address := fs.IPP("address", "a", localAddr, "Host IPv4 Address")
	certFile := fs.String("cert", "", "TLS Certificate [Required for TLS]")
	//file := fs.String("file", filepath.Join(usr.HomeDir, ".oci/config"),
	//	"OCI Config file location")
	format := fs.String("format", "text", "Logging format [text, json]")
	host := fs.StringP("host", "H", "", "Hostname to serve content on")
	//instancePrincipal := fs.Bool("ip", false, "Use Instance Principal authentication")
	keyFile := fs.String("key", "", "TLS Key File [Required for TLS]")
	logErrFile := fs.String("log-error", "stderr", "File to log errors to")
	logFile := fs.String("log-file", "stdout", "File to use for logging")
	logLevel := fs.String("log", "info",
		"Set log level [debug, info, warn, error]")
	port := fs.IntP("port", "p", 8080, "HTTP Host port number")
	//profile := fs.String("profile", "DEFAULT", "OCI Config Profile to use")
	tlsPort := fs.IntP("tlsport", "t", 4443, "HTTPS Host port number")

	fs.Parse(os.Args[1:])

	o := opts{
		address: *address,
		//bucket:            *bucket,
		certFile: *certFile,
		//file:     *file,
		format: strings.ToLower(*format),
		host:   *host,
		//instancePrincipal: *instancePrincipal,
		keyFile:    *keyFile,
		logErrFile: *logErrFile,
		logFile:    *logFile,
		logLevel:   *logLevel,
		port:       *port,
		//profile:           *profile,
		tlsPort: *tlsPort,
	}

	if err := o.validateFlags(); err != nil {
		return nil, err
	}

	return &o, nil
}

// validateFlags contains logic to validate flag values
// TODO All of this
func (o *opts) validateFlags() error {

	// Check if appropriate logging level is set
	switch o.logLevel {
	case "debug", "log", "info", "warn", "error":
		break
	default:
		return errors.New("--log undefined logging level")
	}

	// Validate format
	switch o.format {
	case "text", "json":
		break
	default:
		return errors.New("--format undefined format")
	}

	// Validate ports
	ports := []int{o.port, o.tlsPort}
	for _, port := range ports {
		if port > 65535 || port < 0 {
			return errors.New("-p invalid port number")
		}
	}

	return nil
}
