package service

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"cross_group_wails/internal/config"
)

type BootstrapStatus struct {
	LocalService  string `json:"localService"`
	Message       string `json:"message"`
	StartedByUs   bool   `json:"startedByUs"`
	NapcatOnline  bool   `json:"napcatOnline"`
	NapcatMessage string `json:"napcatMessage"`
}

type Manager struct {
	mu          sync.Mutex
	cmd         *exec.Cmd
	startedByUs bool
	exePath     string
}

func NewManager(exePath string) *Manager {
	return &Manager{exePath: exePath}
}

func (m *Manager) StartedByUs() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.startedByUs
}

func (m *Manager) EnsureBackend() BootstrapStatus {
	result := ProbeHealth()
	switch result.Probe {
	case ProbeReady:
		return BootstrapStatus{
			LocalService:  "ready",
			Message:       "service ready",
			StartedByUs:   false,
			NapcatOnline:  result.NapcatOnline,
			NapcatMessage: result.NapcatMsg,
		}
	case ProbePortConflict:
		return BootstrapStatus{
			LocalService: "port_conflict",
			Message:      result.ConflictMsg,
			StartedByUs:  false,
		}
	}

	m.mu.Lock()
	if m.startedByUs {
		m.mu.Unlock()
		return m.waitForHealth("connecting to local service...", true)
	}
	m.mu.Unlock()

	if err := m.startSidecar(); err != nil {
		return BootstrapStatus{
			LocalService: "error",
			Message:      fmt.Sprintf("failed to start sidecar: %v", err),
			StartedByUs:  false,
		}
	}

	return m.waitForHealth("starting local service...", true)
}

func (m *Manager) ProbeHealthStatus() BootstrapStatus {
	result := ProbeHealth()
	switch result.Probe {
	case ProbeReady:
		msg := "service ready"
		if !result.NapcatOnline {
			msg = "service started, waiting for NapCat..."
		}
		return BootstrapStatus{
			LocalService:  "ready",
			Message:       msg,
			StartedByUs:   m.StartedByUs(),
			NapcatOnline:  result.NapcatOnline,
			NapcatMessage: result.NapcatMsg,
		}
	case ProbePortConflict:
		return BootstrapStatus{
			LocalService: "port_conflict",
			Message:      result.ConflictMsg,
			StartedByUs:  m.StartedByUs(),
		}
	default:
		return BootstrapStatus{
			LocalService: "error",
			Message:      "backend not running",
			StartedByUs:  m.StartedByUs(),
		}
	}
}

func (m *Manager) Shutdown() {
	PostStopInvite()

	m.mu.Lock()
	defer m.mu.Unlock()
	if !m.startedByUs {
		return
	}
	if m.cmd != nil && m.cmd.Process != nil {
		_ = m.cmd.Process.Kill()
		time.Sleep(800 * time.Millisecond)
	}
	m.cmd = nil
	m.startedByUs = false
}

func (m *Manager) startSidecar() error {
	path := m.exePath
	if path == "" {
		path = resolveSidecarPath()
	}
	if path == "" {
		return fmt.Errorf("cross-group-service.exe not found")
	}

	cmd := exec.Command(path, "--no-browser")
	cmd.Dir = filepath.Dir(path)
	hideWindow(cmd)

	if err := cmd.Start(); err != nil {
		return err
	}

	m.mu.Lock()
	m.cmd = cmd
	m.startedByUs = true
	m.mu.Unlock()
	return nil
}

func (m *Manager) waitForHealth(initial string, startedByUs bool) BootstrapStatus {
	deadline := time.Now().Add(45 * time.Second)

	for time.Now().Before(deadline) {
		result := ProbeHealth()
		switch result.Probe {
		case ProbeReady:
			msg := "service ready"
			if !result.NapcatOnline {
				msg = "service started, waiting for NapCat..."
			}
			return BootstrapStatus{
				LocalService:  "ready",
				Message:       msg,
				StartedByUs:   startedByUs,
				NapcatOnline:  result.NapcatOnline,
				NapcatMessage: result.NapcatMsg,
			}
		case ProbePortConflict:
			return BootstrapStatus{
				LocalService: "port_conflict",
				Message:      result.ConflictMsg,
				StartedByUs:  startedByUs,
			}
		default:
			time.Sleep(400 * time.Millisecond)
		}
	}

	return BootstrapStatus{
		LocalService: "error",
		Message:      "local service startup timeout, check port 17888",
		StartedByUs:  startedByUs,
	}
}

func resolveSidecarPath() string {
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
