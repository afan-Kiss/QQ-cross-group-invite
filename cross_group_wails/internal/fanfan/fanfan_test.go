package fanfan

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestIsValidInstall(t *testing.T) {
	dir := t.TempDir()
	if IsValidInstall(dir) {
		t.Fatal("empty dir should be invalid")
	}
	if err := os.WriteFile(filepath.Join(dir, "napcat.mjs"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	if IsValidInstall(dir) {
		t.Fatal("mjs alone should be invalid")
	}
	if err := os.WriteFile(filepath.Join(dir, "launcher-user.bat"), []byte("@echo off"), 0o644); err != nil {
		t.Fatal(err)
	}
	if !IsValidInstall(dir) {
		t.Fatal("mjs + launcher-user.bat should be valid")
	}
}

func TestResolveInstallParent(t *testing.T) {
	root := t.TempDir()
	shell := filepath.Join(root, "NapCat.Shell")
	if err := os.MkdirAll(shell, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(shell, "napcat.mjs"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(shell, "launcher-user.bat"), []byte("@echo off"), 0o644); err != nil {
		t.Fatal(err)
	}
	resolved, kind, ok := ResolveInstall(root)
	if !ok || kind != "shell" {
		t.Fatalf("got ok=%v kind=%q path=%q", ok, kind, resolved)
	}
	if resolved != shell {
		t.Fatalf("resolved=%q want=%q", resolved, shell)
	}
}

func TestDetectEmpty(t *testing.T) {
	r := Detect("", "")
	if r.PathValid {
		t.Fatal("empty path should not be valid")
	}
	if r.Message == "" {
		t.Fatal("expected message")
	}
}

func TestProbeAPIDefault(t *testing.T) {
	_, endpoint := ProbeAPI("")
	if endpoint == "" {
		t.Fatal("expected endpoint")
	}
}

func TestHeadedLauncherScriptDisablesBypass(t *testing.T) {
	fw := headedLauncherScript("framework")
	sh := headedLauncherScript("shell")
	for _, script := range []string{fw, sh} {
		for _, needle := range headedEnvVars() {
			key := strings.SplitN(needle, "=", 2)[0]
			if !strings.Contains(script, "set "+needle) {
				t.Fatalf("script missing %s", needle)
			}
			if key == "NAPCAT_DISABLE_BYPASS" && !strings.Contains(script, "NAPCAT_DISABLE_BYPASS=1") {
				t.Fatal("headed script must disable bypass")
			}
		}
		if strings.Contains(script, `start ""`) {
			t.Fatal("headed script must not detach with start, or env/window state can be lost")
		}
	}
	if !strings.Contains(fw, "napimain.exe") {
		t.Fatal("framework script should launch napimain.exe")
	}
	if !strings.Contains(sh, "NapCatWinBootMain.exe") {
		t.Fatal("shell script should launch NapCatWinBootMain.exe")
	}
}

func TestLaunchInvalidDir(t *testing.T) {
	err := Launch(t.TempDir())
	if err != os.ErrNotExist {
		t.Fatalf("want ErrNotExist, got %v", err)
	}
}
