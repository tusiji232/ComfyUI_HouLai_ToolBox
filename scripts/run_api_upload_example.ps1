$ErrorActionPreference = "Stop"

$workflow = Join-Path $HOME "Downloads\test_workflow.json"
$server = "http://127.0.0.1:8000"
$outDir = Join-Path $HOME "Downloads\api_upload_test_out"

$img1 = Join-Path $HOME "Pictures\example_1.jpg"
$img2 = Join-Path $HOME "Pictures\example_2.jpg"

python "$PSScriptRoot\comfy_api_upload_router.py" `
  --workflow $workflow `
  --server $server `
  --slot 1 $img1 `
  --slot 2 $img2 `
  --route-n 2 `
  --resize-mode pixel_count_1m `
  --resize-value 1 `
  --resample-method lanczos `
  --max-side-limit 1536 `
  --align-to-multiple 1 `
  --out-dir $outDir

Write-Host ""
Write-Host "Done. Check output in: $outDir"
