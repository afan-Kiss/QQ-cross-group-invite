package applog

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"cross_group_wails/internal/config"
)

var (
	mu     sync.Mutex
	logFile *os.File
)

func Init() {
	mu.Lock()
	defer mu.Unlock()
	if logFile != nil {
		return
	}
	path := filepath.Join(config.LogsDir(), "app.log")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "applog open failed: %v\n", err)
		return
	}
	logFile = f
	writeUnlocked("INFO", "app logger initialized path=%s", path)
}

func Close() {
	mu.Lock()
	defer mu.Unlock()
	if logFile != nil {
		_ = logFile.Close()
		logFile = nil
	}
}

func Info(format string, args ...any) {
	logf("INFO", format, args...)
}

func Error(format string, args ...any) {
	logf("ERROR", format, args...)
}

func Warn(format string, args ...any) {
	logf("WARN", format, args...)
}

func logf(level, format string, args ...any) {
	mu.Lock()
	defer mu.Unlock()
	writeUnlocked(level, format, args...)
}

func writeUnlocked(level, format string, args ...any) {
	msg := fmt.Sprintf(format, args...)
	line := fmt.Sprintf("%s [%s] %s\n", time.Now().Format("2006-01-02 15:04:05"), level, msg)
	if logFile != nil {
		_, _ = logFile.WriteString(line)
	}
	fmt.Fprint(os.Stderr, line)
}
