package service

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestClassifyReadyServiceLockedExternal(t *testing.T) {
	h := HealthResult{Probe: ProbeReady, SessionRequired: true, SessionMatch: false}
	got := classifyReadyService(false, "", h)
	if got.LocalService != "port_conflict" {
		t.Fatalf("got %q want port_conflict", got.LocalService)
	}
	if got.AppSession != "" {
		t.Fatal("must not leak session")
	}
}

func TestClassifyReadyServiceExternalUnlocked(t *testing.T) {
	h := HealthResult{Probe: ProbeReady, SessionRequired: false, SessionMatch: false, NapcatOnline: true}
	got := classifyReadyService(false, "", h)
	if got.LocalService != "ready" || got.StartedByUs {
		t.Fatalf("got %+v", got)
	}
}

func TestClassifyReadyServiceOwned(t *testing.T) {
	h := HealthResult{Probe: ProbeReady, SessionRequired: true, SessionMatch: true}
	got := classifyReadyService(true, "sess", h)
	if got.LocalService != "ready" || !got.StartedByUs || got.AppSession != "sess" {
		t.Fatalf("got %+v", got)
	}
}

func TestWaitForHealthMismatchAfterChildExit(t *testing.T) {
	prevTO, prevIV := WaitHealthTimeout, WaitHealthInterval
	WaitHealthTimeout = 2 * time.Second
	WaitHealthInterval = 50 * time.Millisecond
	t.Cleanup(func() {
		WaitHealthTimeout, WaitHealthInterval = prevTO, prevIV
	})

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":               true,
			"service":          ServiceID,
			"session_required": true,
			"session_match":    false,
			"napcat_online":    true,
		})
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()
	prev := HealthURL
	HealthURL = srv.URL + "/health"
	t.Cleanup(func() { HealthURL = prev })

	m := &Manager{startedByUs: true, sessionID: "ours", cmd: nil}
	start := time.Now()
	got := m.waitForHealth("x", true)
	elapsed := time.Since(start)
	if got.LocalService != "port_conflict" {
		t.Fatalf("got %q want port_conflict msg=%q", got.LocalService, got.Message)
	}
	if elapsed > 1500*time.Millisecond {
		t.Fatalf("took too long: %v", elapsed)
	}
}


func TestWaitForHealthChildGoneUnavailable(t *testing.T) {
	prevTO, prevIV := WaitHealthTimeout, WaitHealthInterval
	WaitHealthTimeout = 5 * time.Second
	WaitHealthInterval = 50 * time.Millisecond
	t.Cleanup(func() {
		WaitHealthTimeout, WaitHealthInterval = prevTO, prevIV
	})

	prev := HealthURL
	// Connection refused -> ProbeUnavailable (not port-conflict JSON).
	HealthURL = "http://127.0.0.1:1/health"
	t.Cleanup(func() { HealthURL = prev })

	m := &Manager{startedByUs: true, sessionID: "ours", cmd: nil}
	start := time.Now()
	got := m.waitForHealth("x", true)
	elapsed := time.Since(start)
	if got.LocalService != "error" {
		t.Fatalf("got %q want error msg=%q", got.LocalService, got.Message)
	}
	if !strings.Contains(got.Message, "exited before health") {
		t.Fatalf("unexpected message %q", got.Message)
	}
	if elapsed > 3*time.Second {
		t.Fatalf("took too long: %v", elapsed)
	}
}
