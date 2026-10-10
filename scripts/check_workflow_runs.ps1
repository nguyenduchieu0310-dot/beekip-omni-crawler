$gitExe = 'C:\Users\Hieu Maico\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe'
$credentialInput = "protocol=https`nhost=github.com`nusername=nguyenduchieu0310-dot`n`n"
$lines = $credentialInput | & $gitExe credential fill
$token = ($lines | Where-Object { $_ -match '^password=' }) -replace '^password=', ''
$headers = @{ Authorization = "Bearer $token"; Accept = 'application/vnd.github+json' }
$runs = Invoke-RestMethod -Uri 'https://api.github.com/repos/nguyenduchieu0310-dot/beekip-omni-crawler/actions/runs?per_page=3' -Headers $headers
$runs.workflow_runs | Select-Object id, name, status, conclusion, html_url, created_at | Format-Table
