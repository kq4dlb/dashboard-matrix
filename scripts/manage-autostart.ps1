param(
    [ValidateSet("Enable", "Disable", "Start", "Stop", "Restart", "Status", "Logs")]
    [string]$Action = "Status",
    [string]$TaskName = "Dashboard Matrix",
    [string]$InstallDir = "$env:ProgramFiles\Dashboard Matrix",
    [string]$StateDir = "$env:ProgramData\Dashboard Matrix"
)

$ErrorActionPreference = "Stop"
$runner = Join-Path $InstallDir "run-dashboard-matrix.cmd"
$logDir = Join-Path $StateDir "logs"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run PowerShell as Administrator."
    }
}

function Get-DashboardTask {
    Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}

function Show-Status {
    $task = Get-DashboardTask
    if (-not $task) {
        Write-Host "Autostart task: not installed"
        return
    }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "Autostart task: $($task.State)"
    Write-Host "Enabled: $($task.Settings.Enabled)"
    Write-Host "Last run: $($info.LastRunTime)"
    Write-Host "Last result: $($info.LastTaskResult)"
    Write-Host "Next run: at system startup"
}

switch ($Action) {
    "Enable" {
        Assert-Administrator
        $task = Get-DashboardTask
        if (-not $task) {
            if (-not (Test-Path $runner)) {
                throw "Runner not found at $runner. Install Dashboard Matrix first."
            }
            $actionDef = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" -Argument "/c `"$runner`""
            $trigger = New-ScheduledTaskTrigger -AtStartup
            $settings = New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Days 3650)
            Register-ScheduledTask -TaskName $TaskName -Action $actionDef -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
        } else {
            Enable-ScheduledTask -TaskName $TaskName | Out-Null
        }
        Start-ScheduledTask -TaskName $TaskName
        Show-Status
    }
    "Disable" {
        Assert-Administrator
        if (Get-DashboardTask) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            Disable-ScheduledTask -TaskName $TaskName | Out-Null
        }
        Show-Status
    }
    "Start" {
        Assert-Administrator
        Start-ScheduledTask -TaskName $TaskName
        Show-Status
    }
    "Stop" {
        Assert-Administrator
        Stop-ScheduledTask -TaskName $TaskName
        Show-Status
    }
    "Restart" {
        Assert-Administrator
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        Start-ScheduledTask -TaskName $TaskName
        Show-Status
    }
    "Logs" {
        $stdout = Join-Path $logDir "dashboard-matrix-stdout.log"
        $stderr = Join-Path $logDir "dashboard-matrix-stderr.log"
        Write-Host "Standard output: $stdout"
        Write-Host "Standard error:  $stderr"
        if (Test-Path $stdout) { Get-Content $stdout -Tail 50 }
        if (Test-Path $stderr) { Get-Content $stderr -Tail 50 }
    }
    default { Show-Status }
}
