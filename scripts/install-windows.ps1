# One-line install (Administrator PowerShell):
# irm https://raw.githubusercontent.com/KQ4DLB/dashboard-matrix/main/scripts/install-windows.ps1 | iex

$ErrorActionPreference = "Stop"

$Repo = if ($env:DASHBOARD_MATRIX_REPO) { $env:DASHBOARD_MATRIX_REPO } else { "KQ4DLB/dashboard-matrix" }
$Channel = if ($env:DASHBOARD_MATRIX_RELEASE_CHANNEL) { $env:DASHBOARD_MATRIX_RELEASE_CHANNEL.ToLowerInvariant() } else { "beta" }
$InstallDir = if ($env:DASHBOARD_MATRIX_INSTALL_DIR) { $env:DASHBOARD_MATRIX_INSTALL_DIR } else { "$env:ProgramFiles\Dashboard Matrix" }
$StateDir = if ($env:DASHBOARD_MATRIX_STATE_DIR) { $env:DASHBOARD_MATRIX_STATE_DIR } else { "$env:ProgramData\Dashboard Matrix" }
$TaskName = "Dashboard Matrix"
$DefaultPort = if ($env:DASHBOARD_MATRIX_DEFAULT_PORT) { [int]$env:DASHBOARD_MATRIX_DEFAULT_PORT } else { 8080 }
$Port = if ($env:DASHBOARD_MATRIX_PORT) { [int]$env:DASHBOARD_MATRIX_PORT } else {
    $answer = Read-Host "Dashboard Matrix web port [$DefaultPort]"
    if ([string]::IsNullOrWhiteSpace($answer)) { $DefaultPort } else { [int]$answer }
}
if ($Port -lt 1 -or $Port -gt 65535) { throw "Port must be between 1 and 65535." }
if ($Channel -notin @("stable", "beta")) { throw "Release channel must be stable or beta." }

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator."
}

$headers = @{ "User-Agent" = "Dashboard-Matrix-Installer" }
$releases = Invoke-RestMethod -Headers $headers "https://api.github.com/repos/$Repo/releases?per_page=30"
$release = $releases |
    Where-Object { -not $_.draft -and ($Channel -eq "beta" -or -not $_.prerelease) } |
    Select-Object -First 1
if (-not $release) { throw "No $Channel release was found for $Repo." }

$asset = $release.assets |
    Where-Object { $_.name -match '^Dashboard-Matrix-Windows-x64-v?[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?\.zip$' } |
    Select-Object -First 1
if (-not $asset) {
    throw "Release $($release.tag_name) does not contain the Windows x64 ZIP bundle."
}

$temp = Join-Path $env:TEMP "dashboard-matrix-windows.zip"
Invoke-WebRequest -Headers $headers $asset.browser_download_url -OutFile $temp
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
$LogDir = Join-Path $StateDir "logs"
New-Item -ItemType Directory -Force -Path \
    $InstallDir, "$StateDir\data", "$StateDir\user_plugins", \
    "$StateDir\user_scripts", "$StateDir\user_themes", $LogDir | Out-Null
Expand-Archive $temp -DestinationPath $InstallDir -Force

$secret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
$password = if ($env:DASHBOARD_MATRIX_ADMIN_PASSWORD) { $env:DASHBOARD_MATRIX_ADMIN_PASSWORD } else { [guid]::NewGuid().ToString("N").Substring(0,16) }
$exe = Join-Path $InstallDir "dashboard-matrix.exe"
if (-not (Test-Path $exe)) { throw "The Windows bundle does not contain dashboard-matrix.exe." }

$runner = Join-Path $InstallDir "run-dashboard-matrix.cmd"
$stdout = Join-Path $LogDir "dashboard-matrix-stdout.log"
$stderr = Join-Path $LogDir "dashboard-matrix-stderr.log"
@"
@echo off
set "DASHBOARD_MATRIX_SESSION_SECRET=$secret"
set "DASHBOARD_MATRIX_ADMIN_PASSWORD=$password"
set "DASHBOARD_MATRIX_DATA_DIR=$StateDir\data"
set "DASHBOARD_MATRIX_USER_PLUGINS_DIR=$StateDir\user_plugins"
set "DASHBOARD_MATRIX_USER_SCRIPTS_DIR=$StateDir\user_scripts"
set "DASHBOARD_MATRIX_USER_THEMES_DIR=$StateDir\user_themes"
"$exe" --host 0.0.0.0 --port $Port 1>>"$stdout" 2>>"$stderr"
"@ | Set-Content $runner -Encoding ASCII

$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" -Argument "/c `"$runner`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Get-NetFirewallRule -DisplayName "Dashboard Matrix TCP *" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName "Dashboard Matrix TCP $Port" -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private,Domain | Out-Null
Start-ScheduledTask -TaskName $TaskName

$ip = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1 -ExpandProperty IPAddress
@"
Dashboard Matrix URL: http://${ip}:$Port/
Release: $($release.tag_name) ($Channel channel)
Initial admin password: $password
Application: $InstallDir
Persistent state: $StateDir
Standard output log: $stdout
Standard error log: $stderr
"@ | Set-Content "$StateDir\install-credentials.txt"
Write-Host "Dashboard Matrix installed. Credentials: $StateDir\install-credentials.txt"
