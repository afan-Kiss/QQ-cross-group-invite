use serde::Serialize;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

pub const HEALTH_URL: &str = "http://127.0.0.1:17888/health";
pub const STOP_URL: &str = "http://127.0.0.1:17888/invite/stop";
pub const SERVICE_ID: &str = "cross-group-invite";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BootstrapStatus {
    pub local_service: String,
    pub message: String,
    pub started_by_us: bool,
    pub napcat_online: bool,
    pub napcat_message: String,
}

#[derive(Debug)]
pub struct SidecarState {
    child: Mutex<Option<CommandChild>>,
    started_by_us: AtomicBool,
}

impl SidecarState {
    pub fn new() -> Self {
        Self {
            child: Mutex::new(None),
            started_by_us: AtomicBool::new(false),
        }
    }

    pub fn started_by_us(&self) -> bool {
        self.started_by_us.load(Ordering::SeqCst)
    }
}

#[derive(Debug)]
enum HealthProbe {
    Ready {
        napcat_online: bool,
        napcat_message: String,
    },
    Unavailable,
    PortConflict(String),
}

fn probe_health() -> HealthProbe {
    let response = match ureq::get(HEALTH_URL).timeout(Duration::from_secs(2)).call() {
        Ok(resp) => resp,
        Err(ureq::Error::ConnectionFailed(_)) => return HealthProbe::Unavailable,
        Err(err) => {
            return HealthProbe::PortConflict(format!("17888 端口不可访问：{err}"));
        }
    };

    let body: serde_json::Value = match response.into_json() {
        Ok(v) => v,
        Err(_) => {
            return HealthProbe::PortConflict(
                "17888 端口被占用，响应不是本服务 JSON。".to_string(),
            );
        }
    };

    let service = body
        .get("service")
        .and_then(|v| v.as_str())
        .unwrap_or_default();
    if service != SERVICE_ID {
        return HealthProbe::PortConflict(format!(
            "17888 端口被占用，service={service}。"
        ));
    }

    HealthProbe::Ready {
        napcat_online: body
            .get("napcat_online")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        napcat_message: body
            .get("napcat_message")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
    }
}

pub fn ensure_backend(app: &AppHandle) -> BootstrapStatus {
    match probe_health() {
        HealthProbe::Ready {
            napcat_online,
            napcat_message,
        } => {
            return BootstrapStatus {
                local_service: "ready".into(),
                message: "服务已就绪".into(),
                started_by_us: false,
                napcat_online,
                napcat_message,
            };
        }
        HealthProbe::PortConflict(message) => {
            return BootstrapStatus {
                local_service: "port_conflict".into(),
                message,
                started_by_us: false,
                napcat_online: false,
                napcat_message: String::new(),
            };
        }
        HealthProbe::Unavailable => {}
    }

    let state = app.state::<SidecarState>();
    if state.started_by_us() {
        return wait_for_health("正在连接本地服务...", false);
    }

    let sidecar = match app.shell().sidecar("cross-group-service") {
        Ok(cmd) => cmd,
        Err(err) => {
            return BootstrapStatus {
                local_service: "error".into(),
                message: format!("无法启动本地服务 sidecar：{err}"),
                started_by_us: false,
                napcat_online: false,
                napcat_message: String::new(),
            };
        }
    };

    let sidecar = sidecar.args(["--no-browser"]);
    match sidecar.spawn() {
        Ok((_rx, child)) => {
            if let Ok(mut guard) = state.child.lock() {
                *guard = Some(child);
            }
            state.started_by_us.store(true, Ordering::SeqCst);
        }
        Err(err) => {
            return BootstrapStatus {
                local_service: "error".into(),
                message: format!("本地服务启动失败：{err}"),
                started_by_us: false,
                napcat_online: false,
                napcat_message: String::new(),
            };
        }
    }

    wait_for_health("正在启动本地服务...", true)
}

fn wait_for_health(initial_message: &str, started_by_us: bool) -> BootstrapStatus {
    let deadline = Instant::now() + Duration::from_secs(45);
    let mut message = initial_message.to_string();

    while Instant::now() < deadline {
        match probe_health() {
            HealthProbe::Ready {
                napcat_online,
                napcat_message,
            } => {
                let msg = if napcat_online {
                    "服务已就绪".to_string()
                } else {
                    "服务已启动，正在等待 NapCat...".to_string()
                };
                return BootstrapStatus {
                    local_service: "ready".into(),
                    message: msg,
                    started_by_us,
                    napcat_online,
                    napcat_message,
                };
            }
            HealthProbe::PortConflict(err) => {
                return BootstrapStatus {
                    local_service: "port_conflict".into(),
                    message: err,
                    started_by_us,
                    napcat_online: false,
                    napcat_message: String::new(),
                };
            }
            HealthProbe::Unavailable => {
                message = if started_by_us {
                    "正在启动本地服务...".to_string()
                } else {
                    "正在连接本地服务...".to_string()
                };
                thread::sleep(Duration::from_millis(400));
            }
        }
    }

    BootstrapStatus {
        local_service: "error".into(),
        message: "本地服务启动超时，请检查 17888 端口或依赖环境。".into(),
        started_by_us,
        napcat_online: false,
        napcat_message: String::new(),
    }
}

pub fn shutdown_backend(app: &AppHandle) {
    let _ = ureq::post(STOP_URL)
        .timeout(Duration::from_secs(2))
        .send_json(serde_json::json!({}));

    let state = app.state::<SidecarState>();
    if !state.started_by_us() {
        return;
    }

    let child = state.child.lock().ok().and_then(|mut g| g.take());
    if let Some(mut child) = child {
        let _ = child.kill();
        thread::sleep(Duration::from_millis(800));
    }
    state.started_by_us.store(false, Ordering::SeqCst);
}

#[tauri::command]
pub fn ensure_backend_command(app: AppHandle) -> BootstrapStatus {
    ensure_backend(&app)
}

#[tauri::command]
pub fn shutdown_backend_command(app: AppHandle) {
    shutdown_backend(&app);
}

#[tauri::command]
pub fn probe_health_command() -> BootstrapStatus {
    match probe_health() {
        HealthProbe::Ready {
            napcat_online,
            napcat_message,
        } => BootstrapStatus {
            local_service: "ready".into(),
            message: "服务已就绪".into(),
            started_by_us: false,
            napcat_online,
            napcat_message,
        },
        HealthProbe::PortConflict(message) => BootstrapStatus {
            local_service: "port_conflict".into(),
            message,
            started_by_us: false,
            napcat_online: false,
            napcat_message: String::new(),
        },
        HealthProbe::Unavailable => BootstrapStatus {
            local_service: "error".into(),
            message: "后端服务未启动".into(),
            started_by_us: false,
            napcat_online: false,
            napcat_message: String::new(),
        },
    }
}
