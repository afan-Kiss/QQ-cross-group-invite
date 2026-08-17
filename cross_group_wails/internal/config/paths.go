package config

import (
	"os"
	"path/filepath"
)

const AppFolderName = "QQCrossGroupInvite"

func LocalAppDataDir() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	dir := filepath.Join(base, AppFolderName)
	_ = os.MkdirAll(dir, 0o755)
	return dir
}

func LogsDir() string {
	dir := filepath.Join(LocalAppDataDir(), "logs")
	_ = os.MkdirAll(dir, 0o755)
	return dir
}

func RuntimeDir() string {
	dir := filepath.Join(LocalAppDataDir(), "runtime")
	_ = os.MkdirAll(dir, 0o755)
	return dir
}

func ConfigPath() string {
	return filepath.Join(LocalAppDataDir(), "config.json")
}

func ServiceLogPath() string {
	return filepath.Join(LogsDir(), "service.log")
}
