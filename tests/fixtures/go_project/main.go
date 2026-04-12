package main

import "fmt"

type Server struct {
	Host string
	Port int
}

func NewServer(host string, port int) *Server {
	return &Server{Host: host, Port: port}
}

func (s *Server) Start() error {
	fmt.Printf("Starting server on %s:%d\n", s.Host, s.Port)
	return nil
}

func main() {
	srv := NewServer("localhost", 8080)
	if err := srv.Start(); err != nil {
		panic(err)
	}
}
