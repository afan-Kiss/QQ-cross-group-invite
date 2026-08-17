package service

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const (
	HealthURL = "http://127.0.0.1:17888/health"
	StopURL   = "http://127.0.0.1:17888/invite/stop"
	ServiceID = "cross-group-invite"
)

type healthPayload struct {
	OK           bool   `json:"ok"`
	Service      string `json:"service"`
	Version      string `json:"version"`
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

	var payload healthPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: "port 17888 occupied: invalid JSON response",
		}
	}

	if payload.Service != ServiceID {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: fmt.Sprintf("port 17888 occupied: service=%s", payload.Service),
		}
	}

	if !payload.OK {
		return HealthResult{
			Probe:       ProbePortConflict,
			ConflictMsg: "backend service unhealthy",
		}
	}

	return HealthResult{
		Probe:        ProbeReady,
		NapcatOnline: payload.NapcatOnline,
		NapcatMsg:    payload.NapcatMsg,
	}
}

func PostStopInvite() {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Post(StopURL, "application/json", bytes.NewBufferString("{}"))
	if err != nil {
		return
	}
	resp.Body.Close()
}
