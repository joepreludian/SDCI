# 🚀 SDCI - Sistema de Deploy Continuo Integrado

SDCI (Sistema de Deploy Continuo Integrado - Integrated Continuous Deployment System) is a lightweight continuous deployment system consisting of a server and client tool. It allows you to run predefined tasks remotely through a simple command-line interface.

**⚠️ NOTE: This project is currently in ALPHA. A better documentation will be provided soon.**

## ✨ Features

- Server component built with FastAPI
- Command-line client tool for easy task execution
- Token-based authentication
- Real-time task output streaming
- Task status monitoring
- Authenticated single-file upload with progress bar
- CLI interface to manage tasks

## 🔩 Architecture Diagram
The ideal way to work with this tool is using the following structure:
<img width="431" height="471" alt="workflow_structure drawio" src="https://github.com/user-attachments/assets/8ba902b6-2c52-4159-90b1-b6179a0d1054" />

For safety purposes, the ideal way to handle such workflow is to protect SDCI connection under a Tailscale or any other VPN connection; Also you can add sdci on the internet, but a reverse proxy is strongly recommended (e.g. Traefik or Nginx)

## 📥 Installation

### Requirements

- Python 3.13 or higher

### Installing the client
The recommended approach is by using `pipx`;

```bash
pipx install sdci
```

## 📖 Usage

### Starting the server

Run the server component:

```bash
python -m src.server
```

By default, the server runs on `0.0.0.0:8842`.

## Creating tasks
The server will look up for tasks in the `tasks/` directory where you ran this server. It will look for shell scripts on this folder. The job name is the script name without the `.sh` extension.

### Using the client

The client tool can be used to trigger tasks on the server:

```bash
sdci-cli run --token YOUR_TOKEN SERVER_URL TASK_NAME [PARAMETERS...]
```

Example:

```bash
sdci-cli run --token HAPPY123 http://localhost:8842 job_1 param1 param2 param3
```

### Parameters

- `--token`: Authentication token (required)
- `SERVER_URL`: URL of the SDCI server (required)
- `TASK_NAME`: Name of the task to run (required)
- `PARAMETERS`: Optional parameters to pass to the task

### Uploading an asset

You can upload a single file (e.g. a build artifact or archive) to the server. The
file is stored under the server's upload directory, inside the relative `REMOTE_PATH`
directory (created recursively), keeping its original filename:

```bash
sdci-cli upload-asset --token YOUR_TOKEN SERVER_URL LOCAL_FILE REMOTE_PATH
```

Example (lands at `<upload-dir>/releases/v1/app.zip` on the server):

```bash
sdci-cli upload-asset --token HAPPY123 http://localhost:8842 ./app.zip releases/v1
```

Upload notes:

- The server runs **either one task OR one upload at a time** (shared global lock);
  it returns `429` while busy.
- Path traversal is rejected (`400`) and an existing destination file is **never
  overwritten** (`409`).
- A progress bar is shown during upload.

The server's upload directory is configured with the `--upload-dir` flag (or the
`UPLOAD_DIR` env var, default `./uploads`):

```bash
sdci-server --upload-dir ./uploads --server-token YOUR_TOKEN --tasks-dir ./tasks
```


## 👤 Author

- Jonhnatha Trigueiro <joepreludian@gmail.com>
