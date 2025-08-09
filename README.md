# 🚀 SDCI - Sistema de Deploy Continuo Integrado

SDCI (Sistema de Deploy Continuo Integrado - Integrated Continuous Deployment System) is a lightweight continuous deployment system consisting of a server and client tool. It allows you to run predefined tasks remotely through a simple command-line interface.

**⚠️ NOTE: This project is currently in ALPHA. A better documentation will be provided soon.**

## ✨ Features

- Server component built with FastAPI
- Command-line client tool for easy task execution
- Token-based authentication
- Real-time task output streaming
- Task status monitoring


## 📥 Installation

### Requirements

- Python 3.13 or higher

### Installing the client

```bash
pip install sdci
```

## 📖 Usage

### Starting the server

Run the server component:

```bash
python -m src.server
```

By default, the server runs on `0.0.0.0:8842`.

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
