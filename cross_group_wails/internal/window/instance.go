package window

import (
	"fmt"
	"net"
	"os"
	"sync"
	"time"

	"golang.org/x/sys/windows"

	"cross_group_wails/internal/applog"
)

const (
	mutexName      = "Global\\QQCrossGroupInvite_SingleInstance"
	localMutexName = "Local\\QQCrossGroupInvite_SingleInstance"
	focusPort      = "17889"
	focusMessage   = "focus"
)

var (
	focusListenerOnce sync.Once
	instanceMutex     windows.Handle
)

func tryCreateMutex(name string) (owned bool, err error) {
	ptr, err := windows.UTF16PtrFromString(name)
	if err != nil {
		return false, err
	}
	h, err := windows.CreateMutex(nil, false, ptr)
	if err == windows.ERROR_ALREADY_EXISTS {
		if h != 0 {
			_ = windows.CloseHandle(h)
		}
		return false, nil
	}
	if err != nil {
		return false, err
	}
	instanceMutex = h
	return true, nil
}

func AcquireSingleInstance() (bool, error) {
	ok, err := tryCreateMutex(mutexName)
	if err == nil {
		return ok, nil
	}
	applog.Error("Global single-instance mutex failed: %v; trying Local fallback", err)
	ok2, err2 := tryCreateMutex(localMutexName)
	if err2 != nil {
		return false, fmt.Errorf("global mutex: %v; local mutex: %v", err, err2)
	}
	return ok2, nil
}

func RequestFocusExisting() {
	conn, err := net.DialTimeout("tcp", "127.0.0.1:"+focusPort, 500*time.Millisecond)
	if err != nil {
		applog.Warn("request focus failed: %v", err)
		return
	}
	defer conn.Close()
	_, _ = conn.Write([]byte(focusMessage))
}

func StartFocusListener(onFocus func()) {
	focusListenerOnce.Do(func() {
		go func() {
			listener, err := net.Listen("tcp", "127.0.0.1:"+focusPort)
			if err != nil {
				applog.Error("focus listener listen failed: %v", err)
				return
			}
			for {
				conn, err := listener.Accept()
				if err != nil {
					continue
				}
				buf := make([]byte, 16)
				n, _ := conn.Read(buf)
				conn.Close()
				if n > 0 && string(buf[:n]) == focusMessage {
					onFocus()
				}
			}
		}()
	})
}

func FocusOrExit() error {
	ok, err := AcquireSingleInstance()
	if err != nil {
		return err
	}
	if !ok {
		RequestFocusExisting()
		os.Exit(0)
	}
	return nil
}

func MustFocusOrExit() {
	if err := FocusOrExit(); err != nil {
		applog.Error("single instance error: %v", err)
		fmt.Fprintf(os.Stderr, "single instance error: %v\n", err)
		os.Exit(1)
	}
}

func ReleaseSingleInstance() {
	if instanceMutex != 0 {
		_ = windows.CloseHandle(instanceMutex)
		instanceMutex = 0
	}
}
