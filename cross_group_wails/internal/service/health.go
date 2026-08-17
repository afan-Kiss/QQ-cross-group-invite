package service

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const ServiceID = "cross-group-invite"

// Overridable in tests via httptest.Server.
var (
	HealthURL   = "http://127.0.0.1:17888/health"
	StopURL     = "http://127.0.0.1:17888/invite/stop"
	ShutdownURL = "http://127.0.0.1:17888/shutdown"
)

type healthPayload struct {
	OK           bool   `json:"ok"`
	Service      string `json:"service"`
	Version      string `json:"version"`
	SessionID    string `json:"session_id"`
	PID          int    `json:"pid"`
	NapcatOnline bool   `json:"napcat_online"`
	NapcatMsg    string `json:"napcat_message"`
}

type HealthProbe int

const (
	ProbeReady HealthProbe = iota
	ProbeUnavailable
	ProbePortConflict
)

type HealthResult struct {
	Probe        HealthProbe
	NapcatOnline bool
	NapcatMsg    string
	ConflictMsg  string
	SessionID    string
	PID          int
	Version      string
	Service      string
}

func ProbeHealth() HealthResult {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(HealthURL)
	if err != nil {
		return HealthResult{Probe: ProbeUnavailable}
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: "port 17888 occupied: failed to read response",
		}
	}

	return ClassifyHealthBody(body)
}

// ClassifyHealthBody parses /health JSON and decides ready vs port conflict.
// Port conflict when JSON is ok-shaped but service != cross-group-invite,
// or the service field is missing (e.g. only {"ok":true}).
func ClassifyHealthBody(body []byte) HealthResult {
	var payload healthPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: "port 17888 occupied: invalid JSON response",
		}
	}

	service := strings.TrimSpace(payload.Service)
	if service == "" {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: "port 17888 occupied: missing service field",
			SessionID:   payload.SessionID,
			PID:         payload.PID,
			Version:     payload.Version,
		}
	}
	if service != ServiceID {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: fmt.Sprintf("port 17888 occupied: service=%s", service),
			Service:     service,
			SessionID:   payload.SessionID,
			PID:         payload.PID,
			Version:     payload.Version,
		}
	}

	if !payload.OK {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: "backend service unhealthy",
			Service:     service,
			SessionID:   payload.SessionID,
			PID:         payload.PID,
			Version:     payload.Version,
		}
	}

	return HealthResult{
		Probe:        ProbeReady,
		NapcatOnline: payload.NapcatOnline,
		NapcatMsg:    payload.NapcatMsg,
		SessionID:    payload.SessionID,
		PID:          payload.PID,
		Version:      payload.Version,
		Service:      service,
	}
}

// PostStopInvite stops the invite batch. Requires X-App-Session; empty session skips.
func PostStopInvite(sessionID string) {
	if strings.TrimSpace(sessionID) == "" {
		return
	}
	client := &http.Client{Timeout: 2 * time.Second}
	req, err := http.NewRequest(http.MethodPost, StopURL, bytes.NewBufferString("{}"))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-App-Session", sessionID)
	resp, err := client.Do(req)
	if err != nil {
		return
	}
	resp.Body.Close()
}

// PostShutdown asks the sidecar to exit. Requires matching X-App-Session.
func PostShutdown(sessionID string) error {
	if strings.TrimSpace(sessionID) == "" {
		return fmt.Errorf("empty session id")
	}
	client := &http.Client{Timeout: 3 * time.Second}
	req, err := http.NewRequest(http.MethodPost, ShutdownURL, bytes.NewBufferString("{}"))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-App-Session", sessionID)
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return fmt.Errorf("shutdown status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	return nil
}

// OwnsRunningService reports whether the local health response belongs to our session.
func OwnsRunningService(startedByUs bool, ourSession string, health HealthResult) bool {
	if !startedByUs || ourSession == "" {
		return false
	}
	if health.Probe != ProbeReady {
		return false
	}
	return health.SessionID != "" && health.SessionID == ourSession
}
