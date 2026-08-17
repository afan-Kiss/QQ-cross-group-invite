package service

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
)

func TestOwnsRunningService(t *testing.T) {
	ready := HealthResult{Probe: ProbeReady, SessionID: "sess-a"}
	cases := []struct {
		name        string
		startedByUs bool
		ourSession  string
		health      HealthResult
		want        bool
	}{
		{"owned match", true, "sess-a", ready, true},
		{"not started", false, "sess-a", ready, false},
		{"empty our session", true, "", ready, false},
		{"session mismatch", true, "sess-b", ready, false},
		{"empty health session", true, "sess-a", HealthResult{Probe: ProbeReady, SessionID: ""}, false},
		{"unavailable", true, "sess-a", HealthResult{Probe: ProbeUnavailable}, false},
		{"port conflict", true, "sess-a", HealthResult{Probe: ProbePortConflict, SessionID: "sess-a"}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := OwnsRunningService(tc.startedByUs, tc.ourSession, tc.health)
			if got != tc.want {
				t.Fatalf("got %v want %v", got, tc.want)
			}
		})
	}
}

func TestShouldAttemptShutdown(t *testing.T) {
	// Mirrors Shutdown gate: only when startedByUs AND health session matches.
	started, session := true, "s1"
	health := HealthResult{Probe: ProbeReady, SessionID: "s1"}
	if !OwnsRunningService(started, session, health) {
		t.Fatal("expected ownership for shutdown")
	}

	health.SessionID = "other"
	if OwnsRunningService(started, session, health) {
		t.Fatal("must not shutdown external/mismatched session")
	}
}

func TestShutdownSkipsNetworkOnSessionMismatch(t *testing.T) {
	var stopCalls, shutdownCalls atomic.Int32

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":            true,
			"service":       ServiceID,
			"session_id":    "session-B",
			"napcat_online": true,
		})
	})
	mux.HandleFunc("/invite/stop", func(w http.ResponseWriter, r *http.Request) {
		stopCalls.Add(1)
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/shutdown", func(w http.ResponseWriter, r *http.Request) {
		shutdownCalls.Add(1)
		w.WriteHeader(http.StatusOK)
	})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	prevHealth, prevStop, prevShutdown := HealthURL, StopURL, ShutdownURL
	HealthURL = srv.URL + "/health"
	StopURL = srv.URL + "/invite/stop"
	ShutdownURL = srv.URL + "/shutdown"
	t.Cleanup(func() {
		HealthURL, StopURL, ShutdownURL = prevHealth, prevStop, prevShutdown
	})

	m := &Manager{
		startedByUs: true,
		sessionID:   "session-A",
		pid:         424242,
	}
	m.Shutdown()

	if stopCalls.Load() != 0 || shutdownCalls.Load() != 0 {
		t.Fatalf("expected no stop/shutdown calls on session mismatch, got stop=%d shutdown=%d",
			stopCalls.Load(), shutdownCalls.Load())
	}
	if m.StartedByUs() {
		t.Fatal("expected startedByUs cleared")
	}
	if m.SessionID() != "" {
		t.Fatalf("expected session cleared, got %q", m.SessionID())
	}
	if m.PID() != 0 {
		t.Fatalf("expected pid cleared, got %d", m.PID())
	}
}

func TestShutdownPostsWhenSessionMatches(t *testing.T) {
	var stopCalls, shutdownCalls atomic.Int32
	var shutDown atomic.Bool
	var gotStopSession, gotShutdownSession atomic.Value

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if shutDown.Load() {
			http.Error(w, "gone", http.StatusServiceUnavailable)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":            true,
			"service":       ServiceID,
			"session_id":    "session-A",
			"napcat_online": true,
		})
	})
	mux.HandleFunc("/invite/stop", func(w http.ResponseWriter, r *http.Request) {
		stopCalls.Add(1)
		gotStopSession.Store(r.Header.Get("X-App-Session"))
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/shutdown", func(w http.ResponseWriter, r *http.Request) {
		shutdownCalls.Add(1)
		gotShutdownSession.Store(r.Header.Get("X-App-Session"))
		shutDown.Store(true)
		w.WriteHeader(http.StatusOK)
	})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	prevHealth, prevStop, prevShutdown := HealthURL, StopURL, ShutdownURL
	HealthURL = srv.URL + "/health"
	StopURL = srv.URL + "/invite/stop"
	ShutdownURL = srv.URL + "/shutdown"
	t.Cleanup(func() {
		HealthURL, StopURL, ShutdownURL = prevHealth, prevStop, prevShutdown
	})

	m := &Manager{
		startedByUs: true,
		sessionID:   "session-A",
		// pid 0 avoids killProcessTree side effects in unit test
	}
	m.Shutdown()

	if stopCalls.Load() != 1 {
		t.Fatalf("expected 1 stop call, got %d", stopCalls.Load())
	}
	if shutdownCalls.Load() != 1 {
		t.Fatalf("expected 1 shutdown call, got %d", shutdownCalls.Load())
	}
	if s, _ := gotStopSession.Load().(string); s != "session-A" {
		t.Fatalf("stop session header = %q", s)
	}
	if s, _ := gotShutdownSession.Load().(string); s != "session-A" {
		t.Fatalf("shutdown session header = %q", s)
	}
}

func TestPostStopInviteEmptySessionNoPost(t *testing.T) {
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		fmt.Fprint(w, "ok")
	}))
	defer srv.Close()

	prev := StopURL
	StopURL = srv.URL
	t.Cleanup(func() { StopURL = prev })

	PostStopInvite("")
	PostStopInvite("   ")
	if calls.Load() != 0 {
		t.Fatalf("expected no posts for empty session, got %d", calls.Load())
	}
}

func TestAppSessionOnlyWhenOwned(t *testing.T) {
	if got := appSessionIfOwned(true, "abc"); got != "abc" {
		t.Fatalf("owned: got %q", got)
	}
	if got := appSessionIfOwned(false, "abc"); got != "" {
		t.Fatalf("not owned: got %q", got)
	}
	if got := appSessionIfOwned(true, ""); got != "" {
		t.Fatalf("empty session: got %q", got)
	}
}
