package service

import "testing"

func TestClassifyHealthBodyReady(t *testing.T) {
	body := []byte(`{
		"ok": true,
		"service": "cross-group-invite",
		"version": "1.2.3",
		"session_match": true,
		"session_required": true,
		"pid": 4242,
		"napcat_online": true,
		"napcat_message": "ok"
	}`)
	got := ClassifyHealthBody(body)
	if got.Probe != ProbeReady {
		t.Fatalf("probe=%v want ready conflict=%q", got.Probe, got.ConflictMsg)
	}
	if !got.SessionMatch {
		t.Fatal("expected session_match")
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

func TestClassifyHealthBodyNoRawSessionEcho(t *testing.T) {
	// Legacy payloads may still contain session_id; we must ignore it and never treat it as ownership.
	body := []byte(`{
		"ok": true,
		"service": "cross-group-invite",
		"session_id": "should-not-be-used",
		"session_match": false
	}`)
	got := ClassifyHealthBody(body)
	if got.Probe != ProbeReady {
		t.Fatalf("probe=%v", got.Probe)
	}
	if got.SessionMatch {
		t.Fatal("must not infer ownership from echoed session_id")
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
	got := ClassifyHealthBody([]byte(`{"ok":false,"service":"cross-group-invite","session_match":true}`))
	if got.Probe != ProbePortConflict {
		t.Fatalf("probe=%v want port conflict", got.Probe)
	}
}
