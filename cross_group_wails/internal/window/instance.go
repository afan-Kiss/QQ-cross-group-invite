package window

import (
	"fmt"
	"net"
	"os"
	"sync"
	"time"

	"golang.org/x/sys/windows"
)

const (
	mutexName    = "Global\\QQCrossGroupInvite_SingleInstance"
	focusPort    = "17889"
	focusMessage = "focus"
)

var focusListenerOnce sync.Once

func AcquireSingleInstance() (bool, error) {
	name, err := windows.UTF16PtrFromString(mutexName)
	if err != nil {
		return false, err
	}
	_, err = windows.CreateMutex(nil, true, name)
	if err != nil {
		return false, err
	}
	if windows.GetLastError() == windows.ERROR_ALREADY_EXISTS {
		return false, nil
	}
	return true, nil
}

func RequestFocusExisting() {
	conn, err := net.DialTimeout("tcp", "127.0.0.1:"+focusPort, 500*time.Millisecond)
	if err != nil {
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
		fmt.Fprintf(os.Stderr, "single instance error: %v\n", err)
	}
}
