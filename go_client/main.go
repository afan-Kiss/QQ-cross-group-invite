package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("usage: go run . <Api_Name> [k=v ...]")
		os.Exit(1)
	}
	base := "http://127.0.0.1:8889"
	token := "110"
	q := url.Values{}
	q.Set("function", os.Args[1])
	q.Set("token", token)
	for _, a := range os.Args[2:] {
		for i := 0; i < len(a); i++ {
			if a[i] == '=' {
				q.Set(a[:i], a[i+1:])
				break
			}
		}
	}
	resp, err := http.Get(base + "/?" + q.Encode())
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	fmt.Println(string(b))
}
