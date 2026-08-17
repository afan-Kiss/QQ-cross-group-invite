package service

import (
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
	result := ProbeHealth()
	switch result.Probe {
	case ProbeReady:
		session := m.SessionID()
		owned := OwnsRunningService(m.StartedByUs(), session, result)
		return BootstrapStatus{
			LocalService:  "ready",
			Message:       "service ready",
			StartedByUs:   owned,
			NapcatOnline:  result.NapcatOnline,
			NapcatMessage: result.NapcatMsg,
			AppSession:    appSessionIfOwned(owned, session),
		}
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
	result := ProbeHealth()
	session := m.SessionID()
	owned := OwnsRunningService(m.StartedByUs(), session, result)
	switch result.Probe {
	case ProbeReady:
		msg := "service ready"
		if !result.NapcatOnline {
			msg = "service started, waiting for NapCat..."
		}
		return BootstrapStatus{
			LocalService:  "ready",
			Message:       msg,
			StartedByUs:   owned,
			NapcatOnline:  result.NapcatOnline,
			NapcatMessage: result.NapcatMsg,
			AppSession:    appSessionIfOwned(owned, session),
		}
	case ProbePortConflict:
		return BootstrapStatus{
			LocalService: "port_conflict",
			Message:      result.ConflictMsg,
			StartedByUs:  owned,
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
	health := ProbeHealth()
	owned := health.Probe == ProbeReady && health.SessionID != "" && health.SessionID == session
	if !owned {
		applog.Info("shutdown skipped network/kill: session mismatch or not ready (ours=%s health=%s probe=%d)",
			session, health.SessionID, health.Probe)
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
		h := ProbeHealth()
		if h.Probe != ProbeReady || h.SessionID != session {
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

	applog.Info("sidecar started pid=%d session=%s path=%s", pid, sessionID, path)

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
	applog.Info("sidecar exited pid=%d session=%s", m.pid, session)
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
	deadline := time.Now().Add(45 * time.Second)
	ourSession := m.SessionID()

	for time.Now().Before(deadline) {
		result := ProbeHealth()
		switch result.Probe {
		case ProbeReady:
			if startedByUs && ourSession != "" && result.SessionID != "" && result.SessionID != ourSession {
				return BootstrapStatus{
					LocalService: "port_conflict",
					Message:      "port 17888 occupied: session ownership mismatch",
					StartedByUs:  false,
					AppSession:   "",
				}
			}
			if startedByUs && ourSession != "" && result.SessionID == "" {
				// Wait a bit longer for session_id to appear on older payloads mid-boot.
				time.Sleep(400 * time.Millisecond)
				continue
			}
			msg := "service ready"
			if !result.NapcatOnline {
				msg = "service started, waiting for NapCat..."
			}
			owned := OwnsRunningService(startedByUs, ourSession, result)
			return BootstrapStatus{
				LocalService:  "ready",
				Message:       msg,
				StartedByUs:   owned,
				NapcatOnline:  result.NapcatOnline,
				NapcatMessage: result.NapcatMsg,
				AppSession:    appSessionIfOwned(owned, ourSession),
			}
		case ProbePortConflict:
			return BootstrapStatus{
				LocalService: "port_conflict",
				Message:      result.ConflictMsg,
				StartedByUs:  startedByUs,
				AppSession:   "",
			}
		default:
			time.Sleep(400 * time.Millisecond)
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
