use std::{
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::PathBuf,
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use anyhow::{anyhow, Context, Result};
use tauri::{AppHandle, Emitter, Manager, RunEvent};
use tauri_plugin_log::{RotationStrategy, Target, TargetKind};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const BACKEND_SIDECAR_NAME: &str = "hephaes-backend-sidecar";
const BACKEND_RUNTIME_EVENT: &str = "hephaes://backend-runtime";
const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_STARTUP_TIMEOUT: Duration = Duration::from_secs(20);
const BACKEND_HEALTHCHECK_INTERVAL: Duration = Duration::from_millis(250);

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct BackendRuntimeSnapshot {
    backend_log_dir: Option<String>,
    base_url: String,
    desktop_log_dir: Option<String>,
    error: Option<String>,
    mode: String,
    status: String,
}

struct BackendProcessState {
    child: Mutex<Option<CommandChild>>,
    runtime: Mutex<BackendRuntimeSnapshot>,
    shutting_down: Mutex<bool>,
}

struct BackendRuntime {
    base_url: String,
    data_dir: PathBuf,
    desktop_log_dir: PathBuf,
    raw_data_dir: PathBuf,
    outputs_dir: PathBuf,
    log_dir: PathBuf,
    database_path: PathBuf,
    host: String,
    port: u16,
}

enum BackendRuntimeMode {
    External,
    Sidecar,
}

impl BackendRuntimeSnapshot {
    fn failed(
        mode: BackendRuntimeMode,
        base_url: String,
        error: String,
        backend_log_dir: Option<String>,
        desktop_log_dir: Option<String>,
    ) -> Self {
        Self {
            backend_log_dir,
            base_url,
            desktop_log_dir,
            error: Some(error),
            mode: mode.as_str().to_string(),
            status: "failed".to_string(),
        }
    }

    fn ready(
        mode: BackendRuntimeMode,
        base_url: String,
        backend_log_dir: Option<String>,
        desktop_log_dir: Option<String>,
    ) -> Self {
        Self {
            backend_log_dir,
            base_url,
            desktop_log_dir,
            error: None,
            mode: mode.as_str().to_string(),
            status: "ready".to_string(),
        }
    }

    fn stopped(
        mode: BackendRuntimeMode,
        base_url: String,
        error: String,
        backend_log_dir: Option<String>,
        desktop_log_dir: Option<String>,
    ) -> Self {
        Self {
            backend_log_dir,
            base_url,
            desktop_log_dir,
            error: Some(error),
            mode: mode.as_str().to_string(),
            status: "stopped".to_string(),
        }
    }
}

impl BackendRuntimeMode {
    const fn as_str(&self) -> &'static str {
        match self {
            Self::External => "external",
            Self::Sidecar => "sidecar",
        }
    }
}

impl Default for BackendProcessState {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            runtime: Mutex::new(BackendRuntimeSnapshot::failed(
                BackendRuntimeMode::Sidecar,
                String::new(),
                "backend runtime has not been initialized".to_string(),
                None,
                None,
            )),
            shutting_down: Mutex::new(false),
        }
    }
}

fn set_backend_runtime_snapshot(app: &AppHandle, snapshot: BackendRuntimeSnapshot) {
    let current_snapshot = snapshot.clone();
    *app.state::<BackendProcessState>()
        .runtime
        .lock()
        .expect("backend runtime mutex poisoned") = snapshot;

    if let Err(error) = app.emit(BACKEND_RUNTIME_EVENT, &current_snapshot) {
        log::warn!("failed to emit backend runtime event: {error}");
    }
}

fn set_backend_shutdown_requested(app: &AppHandle, requested: bool) {
    *app.state::<BackendProcessState>()
        .shutting_down
        .lock()
        .expect("backend shutdown mutex poisoned") = requested;
}

fn is_backend_shutdown_requested(app: &AppHandle) -> bool {
    *app.state::<BackendProcessState>()
        .shutting_down
        .lock()
        .expect("backend shutdown mutex poisoned")
}

fn pick_backend_port() -> Result<u16> {
    let listener = TcpListener::bind((BACKEND_HOST, 0))
        .context("could not bind an ephemeral port for the backend sidecar")?;
    let port = listener
        .local_addr()
        .context("could not resolve the ephemeral backend port")?
        .port();
    drop(listener);
    Ok(port)
}

fn resolve_external_backend_base_url() -> Option<String> {
    let configured_base_url = std::env::var("VITE_BACKEND_BASE_URL").ok()?;
    let trimmed = configured_base_url.trim().trim_end_matches('/').to_string();
    if trimmed.is_empty() {
        return None;
    }
    Some(trimmed)
}

fn resolve_backend_runtime(app: &AppHandle) -> Result<BackendRuntime> {
    let port = pick_backend_port()?;
    let desktop_log_dir = app
        .path()
        .app_log_dir()
        .context("could not resolve app log directory")?;
    let data_root = app
        .path()
        .app_local_data_dir()
        .context("could not resolve app-local data directory")?
        .join("backend");
    let base_url = format!("http://{BACKEND_HOST}:{port}");

    Ok(BackendRuntime {
        base_url,
        raw_data_dir: data_root.join("raw"),
        outputs_dir: data_root.join("outputs"),
        database_path: data_root.join("app.db"),
        desktop_log_dir: desktop_log_dir.clone(),
        host: BACKEND_HOST.to_string(),
        port,
        log_dir: desktop_log_dir.join("backend"),
        data_dir: data_root,
    })
}

fn wait_for_backend_health(runtime: &BackendRuntime) -> Result<()> {
    let deadline = Instant::now() + BACKEND_STARTUP_TIMEOUT;
    let healthcheck_request = format!(
        "GET /health HTTP/1.1\r\nHost: {}:{}\r\nConnection: close\r\n\r\n",
        runtime.host, runtime.port
    );

    while Instant::now() < deadline {
        match TcpStream::connect((runtime.host.as_str(), runtime.port)) {
            Ok(mut stream) => {
                stream.set_read_timeout(Some(Duration::from_secs(1)))?;
                stream.set_write_timeout(Some(Duration::from_secs(1)))?;
                stream.write_all(healthcheck_request.as_bytes())?;

                let mut response = String::new();
                stream.read_to_string(&mut response)?;

                if response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200") {
                    log::info!("backend is healthy at {}", runtime.base_url);
                    return Ok(());
                }
            }
            Err(_) => {}
        }

        thread::sleep(BACKEND_HEALTHCHECK_INTERVAL);
    }

    Err(anyhow!(
        "backend did not become healthy at {} within {} seconds. Check backend logs at {}",
        runtime.base_url,
        BACKEND_STARTUP_TIMEOUT.as_secs(),
        runtime.log_dir.display()
    ))
}

fn stop_backend_sidecar(app: &AppHandle) {
    set_backend_shutdown_requested(app, true);
    let backend_state = app.state::<BackendProcessState>();
    let child = backend_state
        .child
        .lock()
        .expect("backend process mutex poisoned")
        .take();

    if let Some(command_child) = child {
        if let Err(error) = command_child.kill() {
            log::warn!("failed to stop backend sidecar cleanly: {error}");
        } else {
            log::info!("stopped backend sidecar");
        }
    }
}

fn spawn_backend_sidecar(app: &AppHandle, runtime: &BackendRuntime) -> Result<()> {
    set_backend_shutdown_requested(app, false);
    let sidecar = app
        .shell()
        .sidecar(BACKEND_SIDECAR_NAME)
        .context("could not prepare backend sidecar command")?
        .args([
            "--host",
            runtime.host.as_str(),
            "--port",
            &runtime.port.to_string(),
        ])
        .env("HEPHAES_DESKTOP_MODE", "1")
        .env("HEPHAES_BACKEND_DATA_DIR", &runtime.data_dir)
        .env("HEPHAES_BACKEND_RAW_DATA_DIR", &runtime.raw_data_dir)
        .env("HEPHAES_BACKEND_OUTPUTS_DIR", &runtime.outputs_dir)
        .env("HEPHAES_BACKEND_DB_PATH", &runtime.database_path)
        .env("HEPHAES_BACKEND_LOG_DIR", &runtime.log_dir);

    let (mut receiver, child) = sidecar
        .spawn()
        .context("could not spawn backend sidecar process")?;

    let event_app = app.clone();
    let runtime_base_url = runtime.base_url.clone();
    let backend_log_dir = runtime.log_dir.display().to_string();
    let desktop_log_dir = runtime.desktop_log_dir.display().to_string();

    tauri::async_runtime::spawn(async move {
        while let Some(event) = receiver.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    log::info!("backend stdout: {}", String::from_utf8_lossy(&line))
                }
                CommandEvent::Stderr(line) => {
                    log::warn!("backend stderr: {}", String::from_utf8_lossy(&line))
                }
                CommandEvent::Error(error) => log::error!("backend process error: {error}"),
                CommandEvent::Terminated(payload) => {
                    event_app
                        .state::<BackendProcessState>()
                        .child
                        .lock()
                        .expect("backend process mutex poisoned")
                        .take();

                    let is_shutdown = is_backend_shutdown_requested(&event_app);
                    if is_shutdown {
                        log::info!("backend process terminated during shutdown: {payload:?}");
                        continue;
                    }

                    let termination_reason = if let Some(code) = payload.code {
                        format!("backend sidecar exited with status code {code}")
                    } else if let Some(signal) = payload.signal {
                        format!("backend sidecar was terminated by signal {signal}")
                    } else {
                        "backend sidecar terminated unexpectedly".to_string()
                    };

                    log::error!(
                        "{termination_reason}. Backend logs: {backend_log_dir}. Desktop logs: {desktop_log_dir}"
                    );
                    set_backend_runtime_snapshot(
                        &event_app,
                        BackendRuntimeSnapshot::stopped(
                            BackendRuntimeMode::Sidecar,
                            runtime_base_url.clone(),
                            termination_reason,
                            Some(backend_log_dir.clone()),
                            Some(desktop_log_dir.clone()),
                        ),
                    );
                }
                _ => {}
            }
        }
    });

    {
        let backend_state = app.state::<BackendProcessState>();
        *backend_state
            .child
            .lock()
            .expect("backend process mutex poisoned") = Some(child);
    }

    if let Err(error) = wait_for_backend_health(runtime) {
        stop_backend_sidecar(app);
        return Err(error);
    }

    Ok(())
}

fn initialize_backend_runtime(app: &AppHandle) {
    if let Some(external_base_url) = resolve_external_backend_base_url() {
        log::info!("using configured external backend at {external_base_url}");
        set_backend_runtime_snapshot(
            app,
            BackendRuntimeSnapshot::ready(
                BackendRuntimeMode::External,
                external_base_url,
                None,
                None,
            ),
        );
        return;
    }

    let runtime = match resolve_backend_runtime(app) {
        Ok(runtime) => runtime,
        Err(error) => {
            log::error!("could not resolve backend runtime: {error:#}");
            set_backend_runtime_snapshot(
                app,
                BackendRuntimeSnapshot::failed(
                    BackendRuntimeMode::Sidecar,
                    String::new(),
                    error.to_string(),
                    None,
                    None,
                ),
            );
            return;
        }
    };

    match spawn_backend_sidecar(app, &runtime) {
        Ok(()) => {
            set_backend_runtime_snapshot(
                app,
                BackendRuntimeSnapshot::ready(
                    BackendRuntimeMode::Sidecar,
                    runtime.base_url.clone(),
                    Some(runtime.log_dir.display().to_string()),
                    Some(runtime.desktop_log_dir.display().to_string()),
                ),
            );
        }
        Err(error) => {
            log::error!("backend sidecar failed to start: {error:#}");
            set_backend_runtime_snapshot(
                app,
                BackendRuntimeSnapshot::failed(
                    BackendRuntimeMode::Sidecar,
                    runtime.base_url.clone(),
                    error.to_string(),
                    Some(runtime.log_dir.display().to_string()),
                    Some(runtime.desktop_log_dir.display().to_string()),
                ),
            );
        }
    }
}

#[tauri::command]
fn get_backend_runtime(state: tauri::State<'_, BackendProcessState>) -> BackendRuntimeSnapshot {
    state
        .runtime
        .lock()
        .expect("backend runtime mutex poisoned")
        .clone()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut log_builder = tauri_plugin_log::Builder::default()
        .level(log::LevelFilter::Info)
        .rotation_strategy(RotationStrategy::KeepSome(5))
        .clear_targets()
        .target(Target::new(TargetKind::LogDir {
            file_name: Some("desktop".to_string()),
        }));

    if cfg!(debug_assertions) {
        log_builder = log_builder.target(Target::new(TargetKind::Stdout));
    }

    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(log_builder.build())
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcessState::default())
        .invoke_handler(tauri::generate_handler![get_backend_runtime]);

    let app = builder
        .setup(|app| {
            initialize_backend_runtime(app.handle());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            stop_backend_sidecar(app_handle);
        }
    });
}
