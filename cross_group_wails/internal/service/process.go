package service

import (
	"fmt"
	"os"
	"os/exec"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

func hideWindow(cmd *exec.Cmd) {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	cmd.SysProcAttr.HideWindow = true
	cmd.SysProcAttr.CreationFlags = 0x08000000 // CREATE_NO_WINDOW
}

func killProcessTree(pid int) {
	if pid <= 0 {
		return
	}
	c := exec.Command("taskkill", "/PID", fmt.Sprintf("%d", pid), "/T", "/F")
	hideWindow(c)
	_ = c.Run()
}

// assignToKillOnCloseJob puts the process in a Windows Job Object that kills
// all children when the job handle is closed (i.e. when this process exits).
func assignToKillOnCloseJob(pid int) (windows.Handle, error) {
	if pid <= 0 {
		return 0, fmt.Errorf("invalid pid")
	}
	job, err := windows.CreateJobObject(nil, nil)
	if err != nil {
		return 0, err
	}

	info := windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION{
		BasicLimitInformation: windows.JOBOBJECT_BASIC_LIMIT_INFORMATION{
			LimitFlags: windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
		},
	}
	if _, err := windows.SetInformationJobObject(
		job,
		windows.JobObjectExtendedLimitInformation,
		uintptr(unsafe.Pointer(&info)),
		uint32(unsafe.Sizeof(info)),
	); err != nil {
		_ = windows.CloseHandle(job)
		return 0, err
	}

	hProc, err := windows.OpenProcess(windows.PROCESS_SET_QUOTA|windows.PROCESS_TERMINATE|windows.PROCESS_QUERY_INFORMATION, false, uint32(pid))
	if err != nil {
		_ = windows.CloseHandle(job)
		return 0, err
	}
	defer windows.CloseHandle(hProc)

	if err := windows.AssignProcessToJobObject(job, hProc); err != nil {
		_ = windows.CloseHandle(job)
		return 0, err
	}
	return job, nil
}

// Keep a process handle reference so the OS does not reuse semantics oddly.
var _ = os.Getpid
