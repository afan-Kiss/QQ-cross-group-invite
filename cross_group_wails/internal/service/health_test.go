package service

import "testing"

func TestClassifyHealthBodyReady(t *testing.T) {
	body := []byte(`{
		"ok": true,
		"service": "cross-group-invite",
		"version": "1.2.3",
		"session_id": "abc-123",
		"pid": 4242,
		"napcat_online": true,
		"napcat_message": "ok"
	}`)
	got := ClassifyHealthBody(body)
	if got.Probe != ProbeReady {
		t.Fatalf("probe=%v want ready conflict=%q", got.Probe, got.ConflictMsg)
	}
	if got.SessionID != "abc-123" {
		t.Fatalf("session_id=%q", got.SessionID)
	}
	if got.PID != 4242 {
		t.Fatalf("pid=%d", got.PID)
	}
	if got.Version != "1.2.3" {
		t.Fatalf("version=%q", got.Version)
	}
	if !got.NapcatOnline {
		t.Fatal("expected napcat online")
	}
}

func TestClassifyHealthBodyMissingService(t *testing.T) {
	got := ClassifyHealthBody([]byte(`{"ok":true}`))
	if got.Probe != ProbePortConflict {
		t.Fatalf("probe=%v want port conflict", got.Probe)
	}
	if got.ConflictMsg == "" {
		t.Fatal("expected conflict message")
	}
}

func TestClassifyHealthBodyWrongService(t *testing.T) {
	got := ClassifyHealthBody([]byte(`{"ok":true,"service":"other-app"}`))
	if got.Probe != ProbePortConflict {
		t.Fatalf("probe=%v want port conflict", got.Probe)
	}
}

func TestClassifyHealthBodyInvalidJSON(t *testing.T) {
	got := ClassifyHealthBody([]byte(`not-json`))
	if got.Probe != ProbePortConflict {
		t.Fatalf("probe=%v want port conflict", got.Probe)
	}
}

func TestClassifyHealthBodyUnhealthy(t *testing.T) {
	got := ClassifyHealthBody([]byte(`{"ok":false,"service":"cross-group-invite","session_id":"x"}`))
	if got.Probe != ProbePortConflict {
		t.Fatalf("probe=%v want port conflict", got.Probe)
	}
}
