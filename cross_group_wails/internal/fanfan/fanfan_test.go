package fanfan

import (
	"os"
	"path/filepath"
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
	r := Detect("")
	if r.PathValid {
		t.Fatal("empty path should not be valid")
	}
	if r.Message == "" {
		t.Fatal("expected message")
	}
}
