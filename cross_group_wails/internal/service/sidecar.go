package service

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"github.com/google/uuid"
	"golang.org/x/sys/windows"

	"cross_group_wails/internal/applog"
	"cross_group_wails/internal/config"
)

type BootstrapStatus struct {
	LocalService  string `json:"localService"`
	Message       string `json:"message"`
	StartedByUs   bool   `json:"startedByUs"`
	NapcatOnline  bool   `json:"napcatOnline"`
	NapcatMessage string `json:"napcatMessage"`
	// AppSession is the sidecar session for X-App-Session. Only set when we own the live service.
	AppSession string `json:"appSession"`
}

var (
	WaitHealthTimeout  = 45 * time.Second
	WaitHealthInterval = 400 * time.Millisecond
)

const lockedServiceMsg = "port 17888 occupied by a protected cross-group-invite service without session access"

func classifyReadyService(startedByUs bool, session string, result HealthResult) BootstrapStatus {
	if result.Probe != ProbeReady {
		return BootstrapStatus{LocalService: "error", Message: "backend not running", StartedByUs: startedByUs, AppSession: ""}
	}
	owned := OwnsRunningService(startedByUs, result)
	if owned {
		msg := "service ready"
		if !result.NapcatOnline {
			msg = "service started, waiting for NapCat..."
		}
		return BootstrapStatus{
			LocalService:  "ready",
			Message:       msg,
			StartedByUs:   true,
			NapcatOnline:  result.NapcatOnline,
			NapcatMessage: result.NapcatMsg,
			AppSession:    appSessionIfOwned(true, session),
		}
	}
	// External unlocked services remain usable without X-App-Session.
	if !result.SessionRequired {
		msg := "service ready"
		if !result.NapcatOnline {
			msg = "service started, waiting for NapCat..."
		}
		return BootstrapStatus{
			LocalService:  "ready",
			Message:       msg,
			StartedByUs:   false,
			NapcatOnline:  result.NapcatOnline,
			NapcatMessage: result.NapcatMsg,
			AppSession:    "",
		}
	}
	// Protected external service: never pretend ready without session.
	return BootstrapStatus{
		LocalService:  "port_conflict",
		Message:       lockedServiceMsg,
		StartedByUs:   false,
		NapcatOnline:  result.NapcatOnline,
		NapcatMessage: result.NapcatMsg,
		AppSession:    "",
	}
}

func sessionFingerprint(session string) string {
	if session == "" {
		return ""
	}
	sum := sha256.Sum256([]byte(session))
	return hex.EncodeToString(sum[:])[:8]
}

func (m *Manager) probeOwned() HealthResult {
	session := m.SessionID()
	if session == "" {
		return ProbeHealth()
	}
	return ProbeHealthWithSession(session)
}

func appSessionIfOwned(owned bool, session string) string {
	if owned && session != "" {
		return session
	}
	return ""
}

type Manager struct {
	mu          sync.Mutex
	cmd         *exec.Cmd
	pid         int
	startedByUs bool
	sessionID   string
	exePath     string
	job         windows.Handle
}

func NewManager(exePath string) *Manager {
	return &Manager{exePath: exePath}
}

func (m *Manager) StartedByUs() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.startedByUs
}

func (m *Manager) SessionID() string {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.sessionID
}

func (m *Manager) PID() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.pid
}

func (m *Manager) SnapshotOwnership() (startedByUs bool, sessionID string, pid int) {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.startedByUs, m.sessionID, m.pid
}

func (m *Manager) EnsureBackend() BootstrapStatus {
	session := m.SessionID()
	var result HealthResult
	if session != "" {
		result = ProbeHealthWithSession(session)
	} else {
		result = ProbeHealth()
	}
	switch result.Probe {
	case ProbeReady:
		return classifyReadyService(m.StartedByUs(), session, result)
	case ProbePortConflict:
		return BootstrapStatus{
			LocalService: "port_conflict",
			Message:      result.ConflictMsg,
			StartedByUs:  false,
			AppSession:   "",
		}
	}

	m.mu.Lock()
	alreadyStarting := m.startedByUs && m.cmd != nil
	m.mu.Unlock()
	if alreadyStarting {
		return m.waitForHealth("connecting to local service...", true)
	}

	if err := m.startSidecar(); err != nil {
		applog.Error("sidecar start failed: %v", err)
		return BootstrapStatus{
			LocalService: "error",
			Message:      fmt.Sprintf("failed to start sidecar: %v", err),
			StartedByUs:  false,
			AppSession:   "",
		}
	}

	return m.waitForHealth("starting local service...", true)
}

func (m *Manager) ProbeHealthStatus() BootstrapStatus {
	session := m.SessionID()
	var result HealthResult
	if session != "" {
		result = ProbeHealthWithSession(session)
	} else {
		result = ProbeHealth()
	}
	switch result.Probe {
	case ProbeReady:
		return classifyReadyService(m.StartedByUs(), session, result)
	case ProbePortConflict:
		return BootstrapStatus{
			LocalService: "port_conflict",
			Message:      result.ConflictMsg,
			StartedByUs:  false,
			AppSession:   "",
		}
	default:
		return BootstrapStatus{
			LocalService: "error",
			Message:      "backend not running",
			StartedByUs:  m.StartedByUs(),
			AppSession:   "",
		}
	}
}

// Shutdown stops the sidecar only when we started it and still own the live session.
// External services on 17888 are left alone (no stop/shutdown network calls).
func (m *Manager) Shutdown() {
	m.mu.Lock()
	started := m.startedByUs
	session := m.sessionID
	cmd := m.cmd
	pid := m.pid
	job := m.job
	m.mu.Unlock()

	if !started || session == "" {
		applog.Info("shutdown skipped: not our sidecar (startedByUs=%v session empty=%v)", started, session == "")
		return
	}

	// Re-probe before any network side-effect: our process may have died and
	// an external service may now own 17888.
	health := ProbeHealthWithSession(session)
	owned := health.Probe == ProbeReady && health.SessionMatch
	if !owned {
		applog.Info("shutdown skipped network/kill: session mismatch or not ready (fp=%s match=%v probe=%d)",
			sessionFingerprint(session), health.SessionMatch, health.Probe)
		// Safest on mismatch: do not kill by PID (may be reused by external).
		// Only drop our job handle and clear local ownership state.
		if job != 0 {
			_ = windows.CloseHandle(job)
		}
		m.mu.Lock()
		m.cmd = nil
		m.startedByUs = false
		m.sessionID = ""
		m.pid = 0
		m.job = 0
		m.mu.Unlock()
		return
	}

	PostStopInvite(session)
	if err := PostShutdown(session); err != nil {
		applog.Warn("POST /shutdown failed: %v", err)
	}

	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		h := ProbeHealthWithSession(session)
		if h.Probe != ProbeReady || !h.SessionMatch {
			break
		}
		time.Sleep(150 * time.Millisecond)
	}

	// Fallback: kill process tree we started (covers PyInstaller parent/child).
	if pid > 0 {
		killProcessTree(pid)
	}
	if cmd != nil && cmd.Process != nil {
		_ = cmd.Process.Kill()
	}
	if job != 0 {
		_ = windows.CloseHandle(job)
	}

	m.mu.Lock()
	m.cmd = nil
	m.startedByUs = false
	m.sessionID = ""
	m.pid = 0
	m.job = 0
	m.mu.Unlock()
}

func (m *Manager) startSidecar() error {
	path := m.exePath
	if path == "" {
		path = ResolveSidecarPath()
	}
	if path == "" {
		return fmt.Errorf("cross-group-service.exe not found")
	}

	sessionID := uuid.NewString()
	args := []string{"--session-id", sessionID, "--no-browser", "--parent-pid", fmt.Sprintf("%d", os.Getpid())}
	cmd := exec.Command(path, args...)
	cmd.Dir = filepath.Dir(path)
	hideWindow(cmd)

	if err := cmd.Start(); err != nil {
		return err
	}

	pid := 0
	if cmd.Process != nil {
		pid = cmd.Process.Pid
	}

	m.mu.Lock()
	m.cmd = cmd
	m.pid = pid
	m.startedByUs = true
	m.sessionID = sessionID
	m.mu.Unlock()

	if job, err := assignToKillOnCloseJob(pid); err != nil {
		applog.Warn("job object assign failed: %v", err)
	} else {
		m.mu.Lock()
		m.job = job
		m.mu.Unlock()
		applog.Info("sidecar assigned to kill-on-close job pid=%d", pid)
	}

	applog.Info("sidecar started pid=%d session_fp=%s path=%s", pid, sessionFingerprint(sessionID), path)

	go m.reap(cmd, sessionID)
	return nil
}

func (m *Manager) reap(cmd *exec.Cmd, session string) {
	_ = cmd.Wait()
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.cmd != cmd {
		return
	}
	applog.Info("sidecar exited pid=%d session_fp=%s", m.pid, sessionFingerprint(session))
	m.cmd = nil
	m.startedByUs = false
	m.pid = 0
	if m.job != 0 {
		_ = windows.CloseHandle(m.job)
		m.job = 0
	}
	if m.sessionID == session {
		m.sessionID = ""
	}
}

func (m *Manager) processAlive(cmd *exec.Cmd) bool {
	if cmd == nil || cmd.Process == nil {
		return false
	}
	m.mu.Lock()
	alive := m.cmd == cmd
	m.mu.Unlock()
	return alive
}

func (m *Manager) clearLocalStateIfDead() {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.cmd == nil {
		m.startedByUs = false
		m.sessionID = ""
		m.pid = 0
	}
}

func (m *Manager) waitForHealth(initial string, startedByUs bool) BootstrapStatus {
	_ = initial
	deadline := time.Now().Add(WaitHealthTimeout)
	ourSession := m.SessionID()
	mismatchSince := time.Time{}

	for time.Now().Before(deadline) {
		var result HealthResult
		if ourSession != "" {
			result = ProbeHealthWithSession(ourSession)
		} else {
			result = ProbeHealth()
		}
		switch result.Probe {
		case ProbeReady:
			if startedByUs && ourSession != "" && !result.SessionMatch {
				// Our child may still be booting; allow a short grace window.
				alive := false
				m.mu.Lock()
				if m.cmd != nil && m.sessionID == ourSession {
					alive = true
				}
				m.mu.Unlock()
				if !alive {
					return BootstrapStatus{
						LocalService: "port_conflict",
						Message:      lockedServiceMsg,
						StartedByUs:  false,
						AppSession:   "",
					}
				}
				if mismatchSince.IsZero() {
					mismatchSince = time.Now()
				} else if time.Since(mismatchSince) > 3*time.Second {
					// Child still "alive" but never matches: treat as ownership conflict.
					return BootstrapStatus{
						LocalService: "port_conflict",
						Message:      lockedServiceMsg,
						StartedByUs:  false,
						AppSession:   "",
					}
				}
				time.Sleep(WaitHealthInterval)
				continue
			}
			return classifyReadyService(startedByUs, ourSession, result)
		case ProbePortConflict:
			return BootstrapStatus{
				LocalService: "port_conflict",
				Message:      result.ConflictMsg,
				StartedByUs:  false,
				AppSession:   "",
			}
		default:
			// If our process already exited while port is still down/unavailable, keep waiting briefly.
			m.mu.Lock()
			childGone := startedByUs && ourSession != "" && (m.cmd == nil || m.sessionID != ourSession)
			m.mu.Unlock()
			if childGone {
				// Port may still be coming up for an external service; one more probe cycle handled above.
				time.Sleep(WaitHealthInterval)
				continue
			}
			time.Sleep(WaitHealthInterval)
		}
	}

	return BootstrapStatus{
		LocalService: "error",
		Message:      "local service startup timeout, check port 17888",
		StartedByUs:  startedByUs,
		AppSession:   "",
	}
}

func ResolveSidecarPath() string {
	candidates := []string{}

	if exe, err := os.Executable(); err == nil {
		dir := filepath.Dir(exe)
		candidates = append(candidates,
			filepath.Join(dir, "cross-group-service.exe"),
			filepath.Join(dir, "bin", "cross-group-service.exe"),
		)
	}

	candidates = append(candidates,
		filepath.Join(config.RuntimeDir(), "cross-group-service.exe"),
		filepath.Join("bin", "cross-group-service.exe"),
		filepath.Join("..", "dist", "cross-group-service.exe"),
		filepath.Join("..", "..", "dist", "cross-group-service.exe"),
	)

	for _, p := range candidates {
		if abs, err := filepath.Abs(p); err == nil {
			p = abs
		}
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}
