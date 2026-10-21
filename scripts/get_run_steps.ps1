$gitExe = 'C:\Users\Hieu Maico\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe'
$credentialInput = "protocol=https`nhost=github.com`nusername=nguyenduchieu0310-dot`n`n"
$lines = $credentialInput | & $gitExe credential fill
$token = ($lines | Where-Object { $_ -match '^password=' }) -replace '^password=', ''
$headers = @{ Authorization = "Bearer $token"; Accept = 'application/vnd.github+json' }
$r = Invoke-RestMethod -Uri 'https://api.github.com/repos/nguyenduchieu0310-dot/beekip-omni-crawler/actions/runs/38039540416/jobs' -Headers $headers
$r.jobs | Select-Object name, status, conclusion, started_at, completed_at | Format-Table -AutoSize
$r.jobs.steps | Select-Object number, name, status, conclusion | Format-Table -AutoSize
