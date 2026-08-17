package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const apiBase = "http://127.0.0.1:17888"

type Member struct {
	QQ       int64  `json:"qq"`
	Nickname string `json:"nickname"`
	Token    string `json:"token"`
	Role     string `json:"role"`
	Card     string `json:"card"`
}

type InviteRecord struct {
	QQ       int64  `json:"qq"`
	Nickname string `json:"nickname"`
	Reason   string `json:"reason"`
}

type Status struct {
	Running         bool           `json:"running"`
	Total           int            `json:"total"`
	Done            int            `json:"done"`
	Success         int            `json:"success"`
	CurrentQQ       int64          `json:"current_qq"`
	CurrentNickname string         `json:"current_nickname"`
	Message         string         `json:"message"`
	Frequent        []InviteRecord `json:"frequent"`
	Errors          []InviteRecord `json:"errors"`
	Logs            []string       `json:"logs"`
}

type AppConfig struct {
	TargetGroupID string `json:"target_group_id"`
	SourceGroupID string `json:"source_group_id"`
	BatchCount    string `json:"batch_count"`
	IntervalMs    string `json:"interval_ms"`
	FilterStaff   bool   `json:"filter_staff"`
}

type APIClient struct {
	client *http.Client
}

func NewAPIClient() *APIClient {
	return &APIClient{client: &http.Client{Timeout: 120 * time.Second}}
}

func (c *APIClient) Health() bool {
	resp, err := c.client.Get(apiBase + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

func (c *APIClient) GetConfig() (*AppConfig, error) {
	resp, err := c.client.Get(apiBase + "/config")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("http %d: %s", resp.StatusCode, string(raw))
	}
	var cfg AppConfig
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}

func (c *APIClient) GetStatus() (*Status, error) {
	resp, err := c.client.Get(apiBase + "/status")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var st Status
	if err := json.NewDecoder(resp.Body).Decode(&st); err != nil {
		return nil, err
	}
	return &st, nil
}

func (c *APIClient) post(path string, body any) error {
	b, err := json.Marshal(body)
	if err != nil {
		return err
	}
	resp, err := c.client.Post(apiBase+path, "application/json", bytes.NewReader(b))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		var obj map[string]any
		_ = json.Unmarshal(raw, &obj)
		if msg, ok := obj["error"].(string); ok && msg != "" {
			return fmt.Errorf("%s", msg)
		}
		return fmt.Errorf("http %d: %s", resp.StatusCode, string(raw))
	}
	return nil
}

func (c *APIClient) SaveConfig(cfg map[string]any) error {
	return c.post("/config", cfg)
}

func (c *APIClient) LoadMembers(sourceGroupID int64, filterStaff bool) ([]Member, error) {
	b, _ := json.Marshal(map[string]any{
		"source_group_id": sourceGroupID,
		"filter_staff":    filterStaff,
	})
	resp, err := c.client.Post(apiBase+"/members/load", "application/json", bytes.NewReader(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		var obj map[string]any
		_ = json.Unmarshal(raw, &obj)
		if msg, ok := obj["error"].(string); ok && msg != "" {
			return nil, fmt.Errorf("%s", msg)
		}
		return nil, fmt.Errorf("http %d: %s", resp.StatusCode, string(raw))
	}
	var obj struct {
		Members []Member `json:"members"`
		Error   string   `json:"error"`
	}
	if err := json.Unmarshal(raw, &obj); err != nil {
		return nil, err
	}
	if obj.Error != "" {
		return nil, fmt.Errorf("%s", obj.Error)
	}
	return obj.Members, nil
}

func (c *APIClient) StartInvite(target, source int64, count, intervalMs int, filterStaff bool) error {
	return c.post("/invite/start", map[string]any{
		"target_group_id": target,
		"source_group_id": source,
		"count":           count,
		"interval_ms":     intervalMs,
		"filter_staff":    filterStaff,
	})
}

func (c *APIClient) StopInvite() error {
	return c.post("/invite/stop", map[string]any{})
}
