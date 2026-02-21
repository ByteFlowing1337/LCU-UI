// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command as StdCommand;
use tauri::{Manager, Runtime};


fn log_to_file(msg: &str) {
    use std::fs::OpenOptions;
    use std::io::Write;
    let path = "C:\\Users\\Public\\lcu_debug.txt";
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{}", msg);
    }
}

fn spawn_backend<R: Runtime>(_app: &tauri::AppHandle<R>) {
    log_to_file("Attempting to spawn sidecar...");
    // 使用 Tauri 内置的 Sidecar 机制启动
    // 这会自动处理路径和 target triple (例如 desktop_main-x86_64-pc-windows-msvc.exe)
    match tauri::api::process::Command::new_sidecar("desktop_main") {
        Ok(cmd) => {
            log_to_file("Sidecar command created successfully.");
            let (mut rx, child) = cmd.args(["--no-browser"]).spawn().expect("Failed to spawn sidecar");
            log_to_file(&format!("Sidecar spawned with PID: {}", child.pid()));
            
            // 可以在这里监听输出（可选）
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        tauri::api::process::CommandEvent::Stdout(line) => {
                            log_to_file(&format!("[PY STDOUT] {}", line));
                        }
                        tauri::api::process::CommandEvent::Stderr(line) => {
                            log_to_file(&format!("[PY STDERR] {}", line));
                        }
                        _ => {}
                    }
                }
                log_to_file("Sidecar channel closed.");
            });
        }
        Err(e) => {
            log_to_file(&format!("Sidecar failed to start: {}", e));
             // Fallback: 如果 sidecar 失败（例如在 dev 模式），尝试本地 python
            eprintln!("Sidecar failed to start: {}", e);
             // Try local exe copies (dev / unpacked)
            let candidates = [
                "desktop_main.exe",
                "../dist/desktop_main.exe",
                "dist/desktop_main.exe",
                "../desktop_main.exe",
            ];
            for path in candidates.iter() {
                if StdCommand::new(path).arg("--no-browser").spawn().is_ok() {
                    return;
                }
            }
             // Fallback to venv
            let _ = StdCommand::new("..\\.venv\\Scripts\\python.exe")
                .args(["main.py", "--no-browser"])
                .spawn();
        }
    }
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let handle = app.handle();
            spawn_backend(&handle);

            if let Some(_window) = app.get_window("main") {
                // let _ = window.eval("window.location.replace('http://127.0.0.1:5000/')");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
