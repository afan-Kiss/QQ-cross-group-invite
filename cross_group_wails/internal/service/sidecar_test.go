package service

import "testing"

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
