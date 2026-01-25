# 🚀 SDCI - Sistema de Deploy Continuo Integrado

SDCI (Sistema de Deploy Continuo Integrado - Integrated Continuous Deployment System) is a lightweight continuous deployment system consisting of a server and client tool. It allows you to run predefined tasks remotely through a simple command-line interface.

**⚠️ NOTE: This project is currently in ALPHA. A better documentation will be provided soon.**

## ✨ Features

- Server component built with FastAPI
- Command-line client tool for easy task execution
- Token-based authentication
- Real-time task output streaming
- Task status monitoring
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


## 👤 Author

- Jonhnatha Trigueiro <joepreludian@gmail.com>
