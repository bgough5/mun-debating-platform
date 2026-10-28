# Builds assets\soc_launcher.ico (the desktop shortcut's icon) from the College crest, app\static\soc_crest.png.
# Windows-only (uses System.Drawing, built into Windows PowerShell). Run again only if the crest changes:
#   powershell -ExecutionPolicy Bypass -File tools\make_launcher_icon.ps1
param([string]$Source = (Join-Path $PSScriptRoot "..\app\static\soc_crest.png"),
      [string]$Out = (Join-Path $PSScriptRoot "..\assets\soc_launcher.ico"))

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile((Resolve-Path $Source).Path)
$sizes = @(16, 24, 32, 48, 64, 128, 256)
$pngs = New-Object System.Collections.ArrayList

foreach ($s in $sizes) {
    # Square, transparent canvas with the crest centred and scaled to fit (the crest isn't square).
    $bmp = New-Object System.Drawing.Bitmap $s, $s
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)
    $scale = [Math]::Min($s / $src.Width, $s / $src.Height)
    $w = [int][Math]::Round($src.Width * $scale); $h = [int][Math]::Round($src.Height * $scale)
    $g.DrawImage($src, [int](($s - $w) / 2), [int](($s - $h) / 2), $w, $h)
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    [void]$pngs.Add($ms.ToArray())
    $g.Dispose(); $bmp.Dispose(); $ms.Dispose()
}
$src.Dispose()

# ICO container with PNG-compressed entries (supported since Windows Vista).
$fs = [System.IO.File]::Create((Join-Path (Resolve-Path (Split-Path $Out)).Path (Split-Path $Out -Leaf)))
$bw = New-Object System.IO.BinaryWriter $fs
$bw.Write([UInt16]0); $bw.Write([UInt16]1); $bw.Write([UInt16]$sizes.Count)
$offset = 6 + 16 * $sizes.Count
for ($i = 0; $i -lt $sizes.Count; $i++) {
    $s = $sizes[$i]; $data = [byte[]]$pngs[$i]
    $dim = if ($s -ge 256) { 0 } else { $s }      # 0 means 256 in the ICO format
    $bw.Write([byte]$dim); $bw.Write([byte]$dim); $bw.Write([byte]0); $bw.Write([byte]0)
    $bw.Write([UInt16]1); $bw.Write([UInt16]32); $bw.Write([UInt32]$data.Length); $bw.Write([UInt32]$offset)
    $offset += $data.Length
}
foreach ($p in $pngs) { $bw.Write([byte[]]$p) }
$bw.Close()
Write-Host "Wrote $Out ($($sizes -join ', ') px)"
