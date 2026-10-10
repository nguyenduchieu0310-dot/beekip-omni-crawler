$gitExe = 'C:\Users\Hieu Maico\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe'
$credentialInput = "protocol=https`nhost=github.com`nusername=nguyenduchieu0310-dot`n`n"
$lines = $credentialInput | & $gitExe credential fill
$token = ($lines | Where-Object { $_ -match '^password=' }) -replace '^password=', ''
$headers = @{ Authorization = "Bearer $token"; Accept = 'application/vnd.github+json' }
$jobs = Invoke-RestMethod -Uri 'https://api.github.com/repos/nguyenduchieu0310-dot/beekip-omni-crawler/actions/runs/38039540416/jobs' -Headers $headers
$jobId = $jobs.jobs[0].id
$logUri = "https://api.github.com/repos/nguyenduchieu0310-dot/beekip-omni-crawler/actions/jobs/$jobId/logs"
$logResponse = Invoke-WebRequest -Uri $logUri -Headers $headers -MaximumRedirection 10
$logText = $logResponse.Content
$logLines = $logText -split "`n"
$logLines | Where-Object { $_ -match '(Ingested|Published|QA|documents|Success|processed|COMPLETED|Queue|Queue stats|Finished)' } | Select-Object -Last 35
