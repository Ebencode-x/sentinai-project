use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn load_env(project_root: &str) -> Vec<(String, String)> {
    let env_path = std::path::Path::new(project_root).join(".env");
    let mut vars = Vec::new();
    if let Ok(contents) = std::fs::read_to_string(env_path) {
        for line in contents.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some((key, value)) = line.split_once('=') {
                vars.push((key.trim().to_string(), value.trim().to_string()));
            }
        }
    }
    vars
}

fn start_backend() -> Option<Child> {
    let project_root = "C:/Users/ermas/Documents/sentinai-project";
    let env_vars = load_env(project_root);

    let mut cmd = Command::new("python");
    cmd.args([
        "-m", "uvicorn",
        "src.main:app",
        "--host", "127.0.0.1",
        "--port", "8000",
    ])
    .current_dir(project_root);

    for (key, value) in env_vars {
        cmd.env(key, value);
    }

    cmd.spawn().ok()
}

fn wait_for_backend() {
    for _ in 0..20 {
        if std::net::TcpStream::connect("127.0.0.1:8000").is_ok() {
            return;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let child = start_backend();
            app.manage(BackendProcess(Mutex::new(child)));

            wait_for_backend();

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(child) = guard.as_mut() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}