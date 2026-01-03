#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FileMaker Server Remote Service Monitor - Linux to Windows Edition

Überwacht den FileMaker Server-Dienst auf Remote Windows Server über WinRM.
Zeigt einen statischen, farbenfrohen Status-Bildschirm.

Author:     Roman Poeller-Six
GitHub:     https://github.com/svrroot
Version:    4.0 (Remote Edition)
Python:     3.6+
Platform:   Linux (Arch) → Windows 2019 Server

Abhängigkeiten:
    pip install pypsrp colorama

Ausführung:
    python FileMakerServiceMonitorRemote.py
"""

import os
import sys
import time
import json
import getpass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

# ============================================================================
# ABHÄNGIGKEITEN IMPORTIEREN
# ============================================================================

try:
    from pypsrp.client import Client
    from pypsrp.exceptions import WinRMTransportError, AuthenticationError
except ImportError:
    print("FEHLER: pypsrp nicht installiert!")
    print("Bitte installieren mit: pip install pypsrp")
    sys.exit(1)

try:
    from colorama import init, Fore, Style, Back
    init()
except ImportError:
    print("FEHLER: colorama nicht installiert!")
    print("Bitte installieren mit: pip install colorama")
    sys.exit(1)


# ============================================================================
# KONFIGURATION
# ============================================================================

@dataclass
class RemoteHost:
    """Remote Windows Host Konfiguration."""
    hostname: str
    username: str
    password: str
    port: int = 5985
    ssl: bool = False
    auth: str = "basic"
    encryption: str = "never"  # Tailscale verschlüsselt bereits


class Config:
    """Zentrale Konfigurationsklasse für den Service Monitor."""
    
    # Remote Windows Server
    REMOTE_HOST: str = "100.91.65.107"
    REMOTE_USER: str = "Administrator"
    REMOTE_PASS: str = ""  # Wird zur Laufzeit abgefragt
    
    # Service Details
    SERVICE_NAME: str = "FileMaker Server"
    CHECK_INTERVAL: int = 60
    
    # Lokale Einstellungen (auf Linux)
    LOG_FILE: Path = Path.home() / ".local" / "share" / "FileMakerServiceMonitor" / "monitor.log"
    CREDENTIALS_FILE: Path = Path.home() / ".config" / "FileMakerServiceMonitor" / "credentials.json"
    MAX_LOG_SIZE: int = 5 * 1024 * 1024
    
    # Fenstergrö��e
    WINDOW_WIDTH: int = 90
    WINDOW_HEIGHT: int = 35
    
    # Retry-Einstellungen
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: int = 5


# ============================================================================
# KONSOLEN-STEUERUNG
# ============================================================================

class Console:
    """Klasse für statische Konsolen-Anzeige (funktioniert auf Linux)."""
    
    CLEAR_SCREEN = "\033[2J"
    CURSOR_HOME = "\033[H"
    CURSOR_HIDE = "\033[?25l"
    CURSOR_SHOW = "\033[?25h"
    CLEAR_LINE = "\033[2K"
    
    # Zeilen-Positionen
    POS_LOGO = 2
    POS_CONNECTION_INFO = 9
    POS_STATUS_BOX = 11
    POS_TIMER = 22
    POS_STATS = 25
    POS_LOG = 27
    POS_HELP = 33
    
    @staticmethod
    def setup():
        """Initialisiert die Linux-Konsole."""
        # Terminal auf UTF-8 setzen (meist bereits default)
        os.system(f"resize -s {Config.WINDOW_HEIGHT} {Config.WINDOW_WIDTH} 2>/dev/null || true")
        sys.stdout.write(f"\033]0;FileMaker Server Remote Monitor - {Config.REMOTE_HOST}\007")
        sys.stdout.flush()
    
    @staticmethod
    def goto(row: int, col: int = 1):
        print(f"\033[{row};{col}H", end="", flush=True)
    
    @staticmethod
    def clear():
        print(Console.CLEAR_SCREEN + Console.CURSOR_HOME, end="", flush=True)
    
    @staticmethod
    def hide_cursor():
        print(Console.CURSOR_HIDE, end="", flush=True)
    
    @staticmethod
    def show_cursor():
        print(Console.CURSOR_SHOW, end="", flush=True)
    
    @staticmethod
    def print_at(row: int, text: str, col: int = 1):
        Console.goto(row, col)
        print(Console.CLEAR_LINE + text, end="", flush=True)
    
    @staticmethod
    def center(text: str, width: int = None) -> str:
        """Zentriert Text."""
        if width is None:
            width = Config.WINDOW_WIDTH
        # ANSI-Codes nicht mitzählen
        visible = text
        for code in [Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.CYAN, 
                     Fore.MAGENTA, Fore.WHITE, Style.RESET_ALL, Style.BRIGHT,
                     Back.RED, Back.GREEN, Back.BLUE, Back.BLACK, Back.WHITE]:
            visible = visible.replace(code, "")
        padding = (width - len(visible)) // 2
        return " " * max(0, padding) + text


# ============================================================================
# ASCII ART & DESIGN
# ============================================================================

class Design:
    """Design-Elemente und ASCII-Art."""
    
    # Box-Zeichen
    BOX_TL = "╔"
    BOX_TR = "╗"
    BOX_BL = "╚"
    BOX_BR = "╝"
    BOX_H = "═"
    BOX_V = "║"
    BOX_LT = "╠"
    BOX_RT = "╣"
    
    @staticmethod
    def get_logo() -> List[str]:
        """Gibt das kompakte ASCII-Logo mit Namen zurück."""
        logo = [
            f"{Fore.CYAN}{Style.BRIGHT}  ╔═╗╦╦  ╔═╗╔╦╗╔═╗╦╔═╔═╗╦═╗  ╦═╗╔═╗╔╦╗╔═╗╔╦╗╔═╗{Style.RESET_ALL}",
            f"{Fore.CYAN}{Style.BRIGHT}  ╠╣ ║║  ║╣ ║║║╠═╣╠╩╗║╣ ╠╦╝  ╠╦╝║╣ ║║║║ ║ ║ ║╣ {Style.RESET_ALL}",
            f"{Fore.CYAN}{Style.BRIGHT}  ╚  ╩╩═╝╚═╝╩ ╩╩ ╩╩ ╩╚═╝╩╚═  ╩╚═╚═╝╩ ╩╚═╝ ╩ ╚═╝{Style.RESET_ALL}",
            f"",
            f"{Fore.YELLOW}         ╔══════════════════════════════════════════╗{Style.RESET_ALL}",
            f"{Fore.YELLOW}         ║{Fore.WHITE}{Style.BRIGHT}  M O N I T O R   v4.0   ·   2024       {Style.RESET_ALL}{Fore.YELLOW}║{Style.RESET_ALL}",
            f"{Fore.YELLOW}         ║{Fore.MAGENTA}       by Roman Poeller-Six             {Style.RESET_ALL}{Fore.YELLOW}║{Style.RESET_ALL}",
            f"{Fore.YELLOW}         ╚══════════════════════════════════════════╝{Style.RESET_ALL}",
        ]
        return logo
    
    @staticmethod
    def box_top(width: int, color: str = Fore.WHITE) -> str:
        return f"{color}{Design.BOX_TL}{Design.BOX_H * (width - 2)}{Design.BOX_TR}{Style.RESET_ALL}"
    
    @staticmethod
    def box_bottom(width: int, color: str = Fore.WHITE) -> str:
        return f"{color}{Design.BOX_BL}{Design.BOX_H * (width - 2)}{Design.BOX_BR}{Style.RESET_ALL}"
    
    @staticmethod
    def box_row(content: str, width: int, color: str = Fore.WHITE) -> str:
        visible = content
        for code in [Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.CYAN, 
                     Fore.MAGENTA, Fore.WHITE, Style.RESET_ALL, Style.BRIGHT,
                     Back.RED, Back.GREEN, Back.BLUE, Back.BLACK, Back.WHITE]:
            visible = visible.replace(code, "")
        
        padding = width - 4 - len(visible)
        return f"{color}{Design.BOX_V}{Style.RESET_ALL} {content}{' ' * max(0, padding)} {color}{Design.BOX_V}{Style.RESET_ALL}"
    
    @staticmethod
    def box_separator(width: int, color: str = Fore.WHITE) -> str:
        return f"{color}{Design.BOX_LT}{Design.BOX_H * (width - 2)}{Design.BOX_RT}{Style.RESET_ALL}"


# ============================================================================
# LOGGING
# ============================================================================

class Logger:
    """Logging mit Farb-Support."""
    
    def __init__(self, log_file: Path, max_display_lines: int = 4):
        self.log_file = log_file
        self.max_display_lines = max_display_lines
        self.recent_logs: List[Tuple[str, str, str]] = []
        
        # Erstelle Log-Verzeichnis falls nötig
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        """Schreibt Log-Eintrag."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        try:
            if self.log_file.exists() and self.log_file.stat().st_size > Config.MAX_LOG_SIZE:
                backup = self.log_file.with_suffix(".log.old")
                if backup.exists():
                    backup.unlink()
                self.log_file.rename(backup)
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except Exception:
            pass
        
        self.recent_logs.append((timestamp, level, message))
        if len(self.recent_logs) > self.max_display_lines:
            self.recent_logs.pop(0)
    
    def get_recent(self) -> List[Tuple[str, str, str]]:
        """Gibt letzte Log-Einträge zurück."""
        return self.recent_logs.copy()


# ============================================================================
# CREDENTIAL MANAGEMENT
# ============================================================================

class CredentialManager:
    """Verwaltet gespeicherte Credentials (einfache Version, nicht verschlüsselt)."""
    
    @staticmethod
    def load_credentials() -> Optional[Dict[str, str]]:
        """Lädt gespeicherte Credentials."""
        try:
            if Config.CREDENTIALS_FILE.exists():
                with open(Config.CREDENTIALS_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return None
    
    @staticmethod
    def save_credentials(username: str, password: str, save: bool = False):
        """Speichert Credentials wenn gewünscht."""
        if not save:
            return
        
        try:
            Config.CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(Config.CREDENTIALS_FILE, 'w') as f:
                json.dump({
                    'username': username,
                    'password': password,
                    'host': Config.REMOTE_HOST
                }, f)
            # Setze sichere Permissions
            os.chmod(Config.CREDENTIALS_FILE, 0o600)
        except Exception as e:
            print(f"{Fore.YELLOW}Warnung: Konnte Credentials nicht speichern: {e}{Style.RESET_ALL}")
    
    @staticmethod
    def prompt_credentials() -> Tuple[str, str, bool]:
        """Fragt Benutzer nach Credentials."""
        print(f"\n{Fore.CYAN}=== Remote Windows Server Credentials ==={Style.RESET_ALL}\n")
        print(f"Host: {Fore.WHITE}{Style.BRIGHT}{Config.REMOTE_HOST}{Style.RESET_ALL}")
        
        # Prüfe gespeicherte Credentials
        saved = CredentialManager.load_credentials()
        if saved and saved.get('host') == Config.REMOTE_HOST:
            print(f"{Fore.GREEN}✓ Gespeicherte Credentials gefunden{Style.RESET_ALL}")
            use_saved = input(f"Verwenden? (J/n): ").strip().lower()
            if use_saved != 'n':
                return saved['username'], saved['password'], False
        
        username = input(f"\nUsername [{Config.REMOTE_USER}]: ").strip() or Config.REMOTE_USER
        password = getpass.getpass(f"Password: ")
        
        save = input(f"\n{Fore.YELLOW}Credentials speichern? (j/N): {Style.RESET_ALL}").strip().lower() == 'j'
        
        return username, password, save


# ============================================================================
# REMOTE SERVICE MONITOR
# ============================================================================

class RemoteFileMakerServiceMonitor:
    """Hauptklasse für den Remote Service Monitor."""
    
    # Windows Service Status Codes
    STATUS_RUNNING = 4
    STATUS_STOPPED = 1
    STATUS_STARTING = 2
    STATUS_STOPPING = 3
    STATUS_PAUSED = 7
    
    STATUS_INFO = {
        1: ("GESTOPPT", Fore.RED, "✖", "Der Dienst ist nicht aktiv"),
        2: ("STARTET...", Fore.YELLOW, "◐", "Dienst wird gestartet"),
        3: ("STOPPT...", Fore.YELLOW, "◐", "Dienst wird beendet"),
        4: ("AKTIV", Fore.GREEN, "●", "Dienst läuft einwandfrei"),
        5: ("STOP AUSSTEHEND", Fore.YELLOW, "◐", "Stop wird vorbereitet"),
        6: ("START AUSSTEHEND", Fore.YELLOW, "◐", "Start wird vorbereitet"),
        7: ("PAUSIERT", Fore.YELLOW, "▲", "Dienst ist pausiert"),
    }
    
    def __init__(self, host: RemoteHost):
        self.host = host
        self.service_name = Config.SERVICE_NAME
        self.check_interval = Config.CHECK_INTERVAL
        self.logger = Logger(Config.LOG_FILE)
        self.running = True
        self.client: Optional[Client] = None
        self.connection_healthy = False
        
        self.start_time = datetime.now()
        self.check_count = 0
        self.restart_count = 0
        self.connection_errors = 0
        self.last_status = None
        self.last_check_time = None
        self.animation_frame = 0
    
    def connect(self) -> bool:
        """Stellt Verbindung zum Remote Server her."""
        try:
            self.client = Client(
                self.host.hostname,
                username=self.host.username,
                password=self.host.password,
                ssl=self.host.ssl,
                port=self.host.port,
                auth=self.host.auth,
                encryption=self.host.encryption
            )
            
            # Test-Verbindung
            output, streams, had_errors = self.client.execute_cmd("echo OK")
            
            if had_errors:
                self.connection_healthy = False
                return False
            
            self.connection_healthy = True
            self.connection_errors = 0
            return True
            
        except AuthenticationError:
            self.logger.log("Authentifizierung fehlgeschlagen!", "ERROR")
            self.connection_healthy = False
            return False
        except WinRMTransportError as e:
            self.logger.log(f"Verbindungsfehler: {e}", "ERROR")
            self.connection_healthy = False
            return False
        except Exception as e:
            self.logger.log(f"Unerwarteter Fehler: {e}", "ERROR")
            self.connection_healthy = False
            return False
    
    def get_service_status(self) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """Holt den aktuellen Dienst-Status über Remote PowerShell."""
        if not self.connection_healthy:
            return None, None, None
        
        # PowerShell-Script für Service-Abfrage
        ps_script = f"""
$service = Get-Service -Name '{self.service_name}' -ErrorAction SilentlyContinue
if ($service) {{
    $status = $service.Status.value__
    $displayName = $service.DisplayName
    $startType = $service.StartType.ToString()
    Write-Output "$status|$displayName|$startType"
}} else {{
    Write-Output "NOT_FOUND"
}}
"""
        
        try:
            output, streams, had_errors = self.client.execute_ps(ps_script)
            
            if had_errors or not output.strip():
                return None, None, None
            
            result = output.strip()
            
            if result == "NOT_FOUND":
                return None, None, None
            
            parts = result.split('|')
            if len(parts) >= 3:
                status_code = int(parts[0])
                display_name = parts[1]
                start_type = parts[2]
                return status_code, display_name, start_type
            
            return None, None, None
            
        except Exception as e:
            self.logger.log(f"Fehler beim Abfragen: {e}", "ERROR")
            self.connection_errors += 1
            
            # Bei zu vielen Fehlern Verbindung als unhealthy markieren
            if self.connection_errors > Config.MAX_RETRY_ATTEMPTS:
                self.connection_healthy = False
            
            return None, None, None
    
    def start_service(self) -> bool:
        """Startet den Dienst über Remote PowerShell."""
        if not self.connection_healthy:
            self.logger.log("Keine Verbindung zum Server!", "ERROR")
            return False
        
        ps_script = f"""
try {{
    Start-Service -Name '{self.service_name}' -ErrorAction Stop
    
    # Warte bis Service läuft (max 60 Sekunden)
    $timeout = 60
    $count = 0
    while ($count -lt $timeout) {{
        $service = Get-Service -Name '{self.service_name}'
        if ($service.Status -eq 'Running') {{
            Write-Output "SUCCESS"
            exit 0
        }}
        Start-Sleep -Seconds 1
        $count++
    }}
    Write-Output "TIMEOUT"
    exit 1
}} catch {{
    Write-Output "ERROR: $($_.Exception.Message)"
    exit 1
}}
"""
        
        try:
            output, streams, had_errors = self.client.execute_ps(ps_script)
            
            result = output.strip()
            
            if "SUCCESS" in result:
                return True
            elif "already running" in result.lower():
                return True
            else:
                self.logger.log(f"Start fehlgeschlagen: {result}", "ERROR")
                return False
                
        except Exception as e:
            self.logger.log(f"Fehler beim Starten: {e}", "ERROR")
            return False
    
    def restart_service(self) -> bool:
        """Startet den Dienst neu."""
        if not self.connection_healthy:
            return False
        
        ps_script = f"""
try {{
    Restart-Service -Name '{self.service_name}' -Force -ErrorAction Stop
    Write-Output "SUCCESS"
}} catch {{
    Write-Output "ERROR: $($_.Exception.Message)"
}}
"""
        
        try:
            output, streams, had_errors = self.client.execute_ps(ps_script)
            return "SUCCESS" in output
        except Exception as e:
            self.logger.log(f"Neustart fehlgeschlagen: {e}", "ERROR")
            return False
    
    def get_status_display(self, status: Optional[int]) -> Tuple[str, str, str, str]:
        """Gibt Status-Informationen zurück."""
        if status is None:
            if not self.connection_healthy:
                return ("KEINE VERBINDUNG", Fore.RED, "✖", "Verbindung zum Server fehlgeschlagen!")
            return ("NICHT GEFUNDEN", Fore.RED, "✖", "Dienst existiert nicht!")
        return self.STATUS_INFO.get(status, ("UNBEKANNT", Fore.WHITE, "?", "Status unbekannt"))
    
    def draw_header(self):
        """Zeichnet den Header mit Logo."""
        logo = Design.get_logo()
        for i, line in enumerate(logo):
            Console.print_at(Console.POS_LOGO + i, Console.center(line))
    
    def draw_connection_info(self):
        """Zeichnet Verbindungsinformationen."""
        if self.connection_healthy:
            conn_status = f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT} ● VERBUNDEN {Style.RESET_ALL}"
        else:
            conn_status = f"{Back.RED}{Fore.WHITE}{Style.BRIGHT} ✖ GETRENNT {Style.RESET_ALL}"
        
        info = (
            f"{Fore.CYAN}Remote:{Style.RESET_ALL} {Fore.WHITE}{self.host.username}@{self.host.hostname}{Style.RESET_ALL}  "
            f"{conn_status}  "
            f"{Fore.CYAN}Fehler:{Style.RESET_ALL} {Fore.YELLOW}{self.connection_errors}{Style.RESET_ALL}"
        )
        Console.print_at(Console.POS_CONNECTION_INFO, Console.center(info))
    
    def draw_status_box(self, status: Optional[int], display_name: str, start_type: str):
        """Zeichnet die Status-Box."""
        box_width = 70
        box_start = (Config.WINDOW_WIDTH - box_width) // 2
        
        status_name, color, symbol, description = self.get_status_display(status)
        
        # Box-Rahmen
        Console.print_at(Console.POS_STATUS_BOX, " " * box_start + Design.box_top(box_width, Fore.BLUE))
        
        # Großer Status-Indikator
        if status == self.STATUS_RUNNING:
            status_badge = f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}   ● AKTIV   {Style.RESET_ALL}"
        elif status is None:
            if not self.connection_healthy:
                status_badge = f"{Back.RED}{Fore.WHITE}{Style.BRIGHT}   ✖ OFFLINE {Style.RESET_ALL}"
            else:
                status_badge = f"{Back.RED}{Fore.WHITE}{Style.BRIGHT}   ✖ FEHLER  {Style.RESET_ALL}"
        else:
            status_badge = f"{Back.YELLOW}{Fore.BLACK}{Style.BRIGHT}   ◐ WARTEN  {Style.RESET_ALL}"
        
        Console.print_at(Console.POS_STATUS_BOX + 1, " " * box_start + Design.box_row("", box_width, Fore.BLUE))
        Console.print_at(Console.POS_STATUS_BOX + 2, " " * box_start + Design.box_row(
            f"    {Fore.WHITE}Status:{Style.RESET_ALL}      {status_badge}  {color}{Style.BRIGHT}{status_name}{Style.RESET_ALL}", 
            box_width, Fore.BLUE))
        Console.print_at(Console.POS_STATUS_BOX + 3, " " * box_start + Design.box_row("", box_width, Fore.BLUE))
        Console.print_at(Console.POS_STATUS_BOX + 4, " " * box_start + Design.box_separator(box_width, Fore.BLUE))
        Console.print_at(Console.POS_STATUS_BOX + 5, " " * box_start + Design.box_row("", box_width, Fore.BLUE))
        
        service_display = display_name if display_name else self.service_name
        Console.print_at(Console.POS_STATUS_BOX + 6, " " * box_start + Design.box_row(
            f"    {Fore.CYAN}Dienst:{Style.RESET_ALL}      {Fore.WHITE}{service_display[:40]}{Style.RESET_ALL}", 
            box_width, Fore.BLUE))
        Console.print_at(Console.POS_STATUS_BOX + 7, " " * box_start + Design.box_row(
            f"    {Fore.CYAN}Starttyp:{Style.RESET_ALL}    {Fore.WHITE}{start_type or 'Unbekannt'}{Style.RESET_ALL}", 
            box_width, Fore.BLUE))
        
        last_check = self.last_check_time.strftime("%H:%M:%S") if self.last_check_time else "--:--:--"
        Console.print_at(Console.POS_STATUS_BOX + 8, " " * box_start + Design.box_row(
            f"    {Fore.CYAN}Geprüft:{Style.RESET_ALL}     {Fore.YELLOW}{last_check}{Style.RESET_ALL}", 
            box_width, Fore.BLUE))
        Console.print_at(Console.POS_STATUS_BOX + 9, " " * box_start + Design.box_row("", box_width, Fore.BLUE))
        Console.print_at(Console.POS_STATUS_BOX + 10, " " * box_start + Design.box_bottom(box_width, Fore.BLUE))
    
    def draw_timer(self, countdown: int):
        """Zeichnet den Countdown-Timer."""
        minutes, seconds = divmod(countdown, 60)
        
        # Animation Spinner
        spinners = ["◜", "◠", "◝", "◞", "◡", "◟"]
        spinner = spinners[self.animation_frame % len(spinners)]
        self.animation_frame += 1
        
        # Farbe basierend auf verbleibender Zeit
        if countdown > 30:
            time_color = Fore.GREEN
        elif countdown > 10:
            time_color = Fore.YELLOW
        else:
            time_color = Fore.RED
        
        timer_display = (
            f"{Fore.CYAN}{spinner}{Style.RESET_ALL}  "
            f"{Fore.WHITE}Nächste Prüfung in{Style.RESET_ALL}  "
            f"{time_color}{Style.BRIGHT}[ {minutes:02d}:{seconds:02d} ]{Style.RESET_ALL}"
            f"  {Fore.CYAN}{spinner}{Style.RESET_ALL}"
        )
        
        Console.print_at(Console.POS_TIMER, Console.center(timer_display))
    
    def draw_stats(self):
        """Zeichnet die Statistiken."""
        runtime = datetime.now() - self.start_time
        hours, remainder = divmod(int(runtime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        stats = (
            f"{Fore.MAGENTA}⏱{Style.RESET_ALL} Laufzeit: {Fore.WHITE}{Style.BRIGHT}{hours:02d}:{minutes:02d}:{seconds:02d}{Style.RESET_ALL}"
            f"    {Fore.BLUE}●{Style.RESET_ALL} Prüfungen: {Fore.WHITE}{Style.BRIGHT}{self.check_count}{Style.RESET_ALL}"
            f"    {Fore.GREEN}↻{Style.RESET_ALL} Neustarts: {Fore.WHITE}{Style.BRIGHT}{self.restart_count}{Style.RESET_ALL}"
        )
        Console.print_at(Console.POS_STATS, Console.center(stats))
    
    def draw_logs(self):
        """Zeichnet die Log-Anzeige."""
        box_width = 70
        box_start = (Config.WINDOW_WIDTH - box_width) // 2
        
        Console.print_at(Console.POS_LOG, " " * box_start + 
            f"{Fore.YELLOW}┌{'─' * 20} {Style.BRIGHT}EREIGNISSE{Style.RESET_ALL}{Fore.YELLOW} {'─' * (box_width - 34)}┐{Style.RESET_ALL}")
        
        logs = self.logger.get_recent()
        for i in range(4):
            if i < len(logs):
                timestamp, level, message = logs[-(i+1)]
                time_short = timestamp.split(" ")[1][:8]
                
                if level == "ERROR":
                    icon = f"{Fore.RED}✖{Style.RESET_ALL}"
                    color = Fore.RED
                elif level == "WARN":
                    icon = f"{Fore.YELLOW}▲{Style.RESET_ALL}"
                    color = Fore.YELLOW
                else:
                    icon = f"{Fore.GREEN}●{Style.RESET_ALL}"
                    color = Fore.WHITE
                
                text = f"{icon} {Fore.CYAN}{time_short}{Style.RESET_ALL} │ {color}{message[:50]}{Style.RESET_ALL}"
            else:
                text = f"{Fore.WHITE}  · · ·{Style.RESET_ALL}"
            
            Console.print_at(Console.POS_LOG + 1 + i, " " * box_start + f"{Fore.YELLOW}│{Style.RESET_ALL} {text}")
        
        Console.print_at(Console.POS_LOG + 5, " " * box_start + 
            f"{Fore.YELLOW}└{'─' * (box_width - 2)}┘{Style.RESET_ALL}")
    
    def draw_help(self):
        """Zeichnet die Hilfe-Leiste."""
        help_text = (
            f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT} ENTER {Style.RESET_ALL} Sofort prüfen   "
            f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT}   R   {Style.RESET_ALL} Neustart   "
            f"{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT}   C   {Style.RESET_ALL} Reconnect   "
            f"{Back.RED}{Fore.WHITE}{Style.BRIGHT} Q/ESC {Style.RESET_ALL} Beenden"
        )
        Console.print_at(Console.POS_HELP, Console.center(help_text))
    
    def draw_screen(self, status: Optional[int], display_name: str, start_type: str, countdown: int):
        """Zeichnet den kompletten Bildschirm."""
        self.draw_header()
        self.draw_connection_info()
        self.draw_status_box(status, display_name, start_type)
        self.draw_timer(countdown)
        self.draw_stats()
        self.draw_logs()
        self.draw_help()
    
    def check_keypress(self) -> Optional[str]:
        """Prüft auf Tastendruck (Linux-kompatibel)."""
        import select
        
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == '\x1b':  # ESC
                # Prüfe ob es ein ESC-Sequence ist
                if select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.read(2)  # Lese restliche Sequenz
                return 'ESC'
            elif key in ('\r', '\n'):
                return 'ENTER'
            return key.upper()
        return None
    
    def run(self):
        """Hauptschleife des Monitors."""
        Console.setup()
        Console.clear()
        Console.hide_cursor()
        
        # Terminal in raw mode für Tastatureingaben
        import termios
        import tty
        
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            
            self.logger.log(f"Remote Service Monitor gestartet für {self.host.hostname}", "INFO")
            
            # Initiale Verbindung
            if not self.connect():
                self.logger.log("Initiale Verbindung fehlgeschlagen!", "ERROR")
            else:
                self.logger.log("Verbindung hergestellt", "INFO")
            
            while self.running:
                # Versuche Reconnect bei Verbindungsproblemen
                if not self.connection_healthy:
                    self.logger.log("Versuche Verbindung wiederherzustellen...", "WARN")
                    if self.connect():
                        self.logger.log("Verbindung wiederhergestellt!", "INFO")
                    else:
                        time.sleep(Config.RETRY_DELAY)
                        continue
                
                self.check_count += 1
                self.last_check_time = datetime.now()
                
                status, display_name, start_type = self.get_service_status()
                
                if status is None and self.connection_healthy:
                    self.logger.log(f"Dienst '{self.service_name}' nicht gefunden!", "ERROR")
                elif status is not None and status != self.STATUS_RUNNING:
                    status_name = self.STATUS_INFO.get(status, ("UNBEKANNT",))[0]
                    self.logger.log(f"Dienst ist {status_name} - starte neu...", "WARN")
                    
                    if self.start_service():
                        self.restart_count += 1
                        self.logger.log("Dienst erfolgreich gestartet", "INFO")
                        status = self.STATUS_RUNNING
                    else:
                        self.logger.log("Dienst konnte nicht gestartet werden!", "ERROR")
                elif status == self.STATUS_RUNNING:
                    if self.last_status != status:
                        self.logger.log("Dienst läuft einwandfrei", "INFO")
                
                self.last_status = status
                
                # Countdown-Loop
                for countdown in range(self.check_interval, 0, -1):
                    self.draw_screen(status, display_name or self.service_name, start_type or "Unbekannt", countdown)
                    
                    # Check für Input alle 100ms
                    for _ in range(10):
                        time.sleep(0.1)
                        key = self.check_keypress()
                        
                        if key in ('ESC', 'Q'):
                            self.running = False
                            break
                        elif key == 'ENTER':
                            self.logger.log("Manuelle Prüfung gestartet", "INFO")
                            break
                        elif key == 'R':
                            self.logger.log("Manueller Neustart angefordert", "INFO")
                            if self.restart_service():
                                self.restart_count += 1
                                self.logger.log("Dienst neu gestartet", "INFO")
                            else:
                                self.logger.log("Neustart fehlgeschlagen!", "ERROR")
                            break
                        elif key == 'C':
                            self.logger.log("Manuelle Reconnect-Anfrage", "INFO")
                            self.connection_healthy = False
                            break
                    
                    if not self.running or key in ('ENTER', 'R', 'C'):
                        break
        
        finally:
            # Stelle Terminal-Einstellungen wieder her
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            Console.show_cursor()
            Console.clear()
            print(f"{Fore.GREEN}{Style.BRIGHT}Remote Service Monitor beendet.{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Log-Datei: {Config.LOG_FILE}{Style.RESET_ALL}")
            self.logger.log("Remote Service Monitor beendet", "INFO")


# ============================================================================
# HAUPTPROGRAMM
# ============================================================================

def main() -> int:
    """Haupteinstiegspunkt."""
    try:
        # Banner
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("=" * 60)
        print("  FileMaker Server Remote Monitor v4.0")
        print("  Linux → Windows Remote Service Monitoring")
        print("  by Roman Poeller-Six")
        print("=" * 60)
        print(f"{Style.RESET_ALL}\n")
        
        # Credentials abfragen/laden
        username, password, save_creds = CredentialManager.prompt_credentials()
        
        if save_creds:
            CredentialManager.save_credentials(username, password, True)
        
        # Remote Host konfigurieren
        host = RemoteHost(
            hostname=Config.REMOTE_HOST,
            username=username,
            password=password
        )
        
        print(f"\n{Fore.GREEN}Starte Monitor...{Style.RESET_ALL}\n")
        time.sleep(1)
        
        # Monitor starten
        monitor = RemoteFileMakerServiceMonitor(host)
        monitor.run()
        
        return 0
        
    except KeyboardInterrupt:
        Console.show_cursor()
        print(f"\n{Fore.YELLOW}Abgebrochen durch Benutzer.{Style.RESET_ALL}")
        return 0
    except Exception as e:
        Console.show_cursor()
        print(f"\n{Fore.RED}FEHLER: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        input("\nEnter drücken zum Beenden...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
