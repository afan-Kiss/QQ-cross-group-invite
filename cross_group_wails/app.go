package main

import (
	"context"
	"os/exec"
	"runtime"

	"cross_group_wails/internal/config"
	"cross_group_wails/internal/service"
	"cross_group_wails/internal/window"
)

type AppInfo struct {
	AppVersion      string `json:"appVersion"`
	WailsVersion    string `json:"wailsVersion"`
	GoVersion       string `json:"goVersion"`
	FrontendVersion string `json:"frontendVersion"`
	PythonVersion   string `json:"pythonServiceVersion"`
	LogsDir         string `json:"logsDir"`
}

type App struct {
	ctx     context.Context
	sidecar *service.Manager
}

func NewApp() *App {
	return &App{
		sidecar: service.NewManager(""),
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	window.StartFocusListener(func() {
		window.FocusMain(a.ctx)
	})
}

func (a *App) domReady(ctx context.Context) {
	a.ctx = ctx
}

func (a *App) beforeClose(ctx context.Context) bool {
	a.sidecar.Shutdown()
	return false
}

func (a *App) EnsureBackend() service.BootstrapStatus {
	return a.sidecar.EnsureBackend()
}

func (a *App) ProbeHealth() service.BootstrapStatus {
	return a.sidecar.ProbeHealthStatus()
}

func (a *App) ShutdownBackend() {
	a.sidecar.Shutdown()
}

func (a *App) OpenLogsDir() error {
	return exec.Command("explorer", config.LogsDir()).Start()
}

func (a *App) GetAppInfo() AppInfo {
	return AppInfo{
		AppVersion:      "1.0.0",
		WailsVersion:    "2.12.0",
		GoVersion:       runtime.Version(),
		FrontendVersion: "1.0.0",
		PythonVersion:   "",
		LogsDir:         config.LogsDir(),
	}
}
