use std::{
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::PathBuf,
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use anyhow::{anyhow, Context, Result};
use tauri::{AppHandle, Manager, RunEvent};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const BACKEND_SIDECAR_NAME: &str = "hephaes-backend-sidecar";
const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8000;
const BACKEND_STARTUP_TIMEOUT: Duration = Duration::from_secs(20);
const BACKEND_HEALTHCHECK_INTERVAL: Duration = Duration::from_millis(250);

#[derive(Default)]
struct BackendProcessState {
    child: Mutex<Option<CommandChild>>,
}

struct BackendRuntime {
    base_url: String,
    data_dir: PathBuf,
    raw_data_dir: PathBuf,
    outputs_dir: PathBuf,
    log_dir: PathBuf,
    database_path: PathBuf,
}

fn resolve_backend_runtime(app: &AppHandle) -> Result<BackendRuntime> {
    let data_root = app
        .path()
        .app_local_data_dir()
        .context("could not resolve app-local data directory")?
        .join("backend");
    let base_url = format!("http://{BACKEND_HOST}:{BACKEND_PORT}");

    Ok(BackendRuntime {
        base_url,
        raw_data_dir: data_root.join("raw"),
        outputs_dir: data_root.join("outputs"),
        database_path: data_root.join("app.db"),
        log_dir: app
            .path()
            .app_log_dir()
            .context("could not resolve app log directory")?
            .join("backend"),
        data_dir: data_root,
    })
}

fn ensure_backend_port_available() -> Result<()> {
    TcpListener::bind((BACKEND_HOST, BACKEND_PORT))
        .map(drop)
        .with_context(|| format!("backend port {BACKEND_PORT} is already in use"))
}

fn wait_for_backend_health(base_url: &str) -> Result<()> {
    let deadline = Instant::now() + BACKEND_STARTUP_TIMEOUT;
    let healthcheck_request = format!(
        "GET /health HTTP/1.1\r\nHost: {BACKEND_HOST}:{BACKEND_PORT}\r\nConnection: close\r\n\r\n"
    );

    while Instant::now() < deadline {
        match TcpStream::connect((BACKEND_HOST, BACKEND_PORT)) {
            Ok(mut stream) => {
                stream.set_read_timeout(Some(Duration::from_secs(1)))?;
                stream.set_write_timeout(Some(Duration::from_secs(1)))?;
                stream.write_all(healthcheck_request.as_bytes())?;

                let mut response = String::new();
                stream.read_to_string(&mut response)?;

                if response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200") {
                    log::info!("backend is healthy at {base_url}");
                    return Ok(());
                }
            }
            Err(_) => {}
        }

        thread::sleep(BACKEND_HEALTHCHECK_INTERVAL);
    }

    Err(anyhow!("backend did not become healthy at {base_url}"))
}

fn stop_backend_sidecar(app: &AppHandle) {
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

fn spawn_backend_sidecar(app: &AppHandle) -> Result<()> {
    ensure_backend_port_available()?;
    let runtime = resolve_backend_runtime(app)?;

    let sidecar = app
        .shell()
        .sidecar(BACKEND_SIDECAR_NAME)
        .context("could not prepare backend sidecar command")?
        .args(["--host", BACKEND_HOST, "--port", &BACKEND_PORT.to_string()])
        .env("HEPHAES_DESKTOP_MODE", "1")
        .env("HEPHAES_BACKEND_DATA_DIR", &runtime.data_dir)
        .env("HEPHAES_BACKEND_RAW_DATA_DIR", &runtime.raw_data_dir)
        .env("HEPHAES_BACKEND_OUTPUTS_DIR", &runtime.outputs_dir)
        .env("HEPHAES_BACKEND_DB_PATH", &runtime.database_path)
        .env("HEPHAES_BACKEND_LOG_DIR", &runtime.log_dir);

    let (mut receiver, child) = sidecar
        .spawn()
        .context("could not spawn backend sidecar process")?;

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
                    log::info!("backend process terminated: {payload:?}")
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

    if let Err(error) = wait_for_backend_health(&runtime.base_url) {
        stop_backend_sidecar(app);
        return Err(error);
    }

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcessState::default());

    let builder = if cfg!(debug_assertions) {
        builder.plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
    } else {
        builder
    };

    let app = builder
        .setup(|app| {
            spawn_backend_sidecar(app.handle()).map_err(tauri::Error::from)?;
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
