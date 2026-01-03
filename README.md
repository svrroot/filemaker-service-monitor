# FileMaker Server Remote Service Monitor

🔍 Monitor FileMaker Server services on Windows Server 2019 from Linux via WinRM/Tailscale

![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🌟 Features

- **Remote Monitoring**: Monitor Windows services from Linux via WinRM
- **Auto-Restart**: Automatically restart crashed services
- **Real-time Display**: Beautiful colored console interface
- **Secure Connection**: Via Tailscale VPN
- **Credential Management**: Optional credential storage
- **Logging**: Complete activity logs
- **Hotkeys**: Interactive control (C=Reconnect, R=Restart, Q=Quit)

## 📋 Requirements

### Remote Windows Server
- Windows Server 2019 (or similar)
- WinRM enabled
- Administrator account
- Tailscale installed

### Linux Client (Arch)
- Python 3.6+
- Tailscale installed
- Network access to Windows server

## 🚀 Installation

### 1. Clone Repository
```bash
git clone https://github.com/svrroot/filemaker-service-monitor.git
cd filemaker-service-monitor
