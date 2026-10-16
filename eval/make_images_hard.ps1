# Draws the v2 vision test images into eval\images (answers are in tasks_hard.VISION).
Add-Type -AssemblyName System.Drawing
$d = Join-Path $PSScriptRoot 'images'; New-Item -ItemType Directory -Force $d | Out-Null
function New-Img($w, $h) { $b = New-Object System.Drawing.Bitmap $w, $h; $g = [System.Drawing.Graphics]::FromImage($b); $g.Clear([System.Drawing.Color]::White); $g.SmoothingMode = 'AntiAlias'; $g.TextRenderingHint = 'AntiAlias'; return $b, $g }
$black = [System.Drawing.Brushes]::Black; $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), 1.5
$f16 = New-Object System.Drawing.Font('Arial', 16); $f16b = New-Object System.Drawing.Font('Arial', 16, [System.Drawing.FontStyle]::Bold)

# 1-2: table (Q2 sum = 1167, highest Q3 = Delta)
$rows = @(@('Product','Q1','Q2','Q3','Q4'), @('Alpha','210','188','240','199'), @('Beta','175','260','198','221'), @('Gamma','302','145','260','287'),
          @('Delta','150','301','312','175'), @('Epsilon','220','273','255','240'))
$b, $g = New-Img 720 330
for ($r = 0; $r -lt $rows.Count; $r++) { for ($c = 0; $c -lt 5; $c++) { $x = 15 + $c * 138; $y = 12 + $r * 50; $g.DrawRectangle($pen, $x, $y, 138, 50); $g.DrawString($rows[$r][$c], $(if ($r -eq 0) { $f16b } else { $f16 }), $black, $x + 12, $y + 13) } }
$b.Save("$d\h_table_sum.png"); $b.Save("$d\h_table_lookup.png"); $g.Dispose(); $b.Dispose()

# 3: bar chart with gridlines, Thu = 37
$vals = [ordered]@{ Mon = 22; Tue = 31; Wed = 18; Thu = 37; Fri = 29; Sat = 12 }
$b, $g = New-Img 720 420; $x0 = 70; $y0 = 360; $sc = 7
$grid = New-Object System.Drawing.Pen ([System.Drawing.Color]::LightGray), 1
foreach ($t in 0, 10, 20, 30, 40) { $y = $y0 - $t * $sc; $g.DrawLine($grid, $x0, $y, 690, $y); $g.DrawString("$t", $f16, $black, 25, $y - 11) }
$i = 0; foreach ($k in $vals.Keys) { $x = $x0 + 15 + $i * 102; $h = $vals[$k] * $sc; $g.FillRectangle([System.Drawing.Brushes]::SeaGreen, $x, $y0 - $h, 62, $h); $g.DrawString($k, $f16, $black, $x + 10, $y0 + 8); $i++ }
$g.DrawString('Orders per day', $f16b, $black, 270, 8); $b.Save("$d\h_chart_value.png"); $g.Dispose(); $b.Dispose()

# 4: 17 black dots + 6 grey distractors
$b, $g = New-Img 600 400; $rnd = New-Object System.Random 42; $pts = @()
while ($pts.Count -lt 23) { $p = @($rnd.Next(30, 570), $rnd.Next(30, 370)); if (-not ($pts | Where-Object { [math]::Abs($_[0] - $p[0]) -lt 40 -and [math]::Abs($_[1] - $p[1]) -lt 40 })) { $pts += , $p } }
for ($i = 0; $i -lt 23; $i++) { $br = $(if ($i -lt 17) { $black } else { [System.Drawing.Brushes]::Silver }); $g.FillEllipse($br, $pts[$i][0] - 11, $pts[$i][1] - 11, 22, 22) }
$b.Save("$d\h_count_dots.png"); $g.Dispose(); $b.Dispose()

# 5: small serial number in a busy label
$b, $g = New-Img 800 500; $big = New-Object System.Drawing.Font('Arial', 40, [System.Drawing.FontStyle]::Bold); $tiny = New-Object System.Drawing.Font('Arial', 10)
$g.DrawString('POWER SUPPLY UNIT', $big, $black, 60, 60); $g.DrawString('Input: 100-240V ~ 50/60Hz 10A    Output: +12V 62.5A', $f16, $black, 60, 160)
$g.DrawString('Model PS-750G    Made in EU    Batch 0923', $f16, $black, 60, 200); $g.DrawRectangle($pen, 40, 40, 720, 420)
$g.DrawString('SN-4471-XQ', $tiny, $black, 640, 432); $b.Save("$d\h_small_text.png"); $g.Dispose(); $b.Dispose()

# 6: grid of shapes, the yellow square is directly below the red circle
$b, $g = New-Img 600 600
$g.FillEllipse([System.Drawing.Brushes]::Blue, 60, 60, 120, 120);    $g.FillEllipse([System.Drawing.Brushes]::Red, 240, 60, 120, 120);  $g.FillRectangle([System.Drawing.Brushes]::Green, 420, 60, 120, 120)
$g.FillRectangle([System.Drawing.Brushes]::Purple, 60, 240, 120, 120); $g.FillRectangle([System.Drawing.Brushes]::Gold, 240, 240, 120, 120); $g.FillEllipse([System.Drawing.Brushes]::Orange, 420, 240, 120, 120)
$g.FillEllipse([System.Drawing.Brushes]::Gray, 60, 420, 120, 120);   $g.FillRectangle([System.Drawing.Brushes]::Cyan, 240, 420, 120, 120); $g.FillEllipse([System.Drawing.Brushes]::Pink, 420, 420, 120, 120)
$b.Save("$d\h_spatial.png"); $g.Dispose(); $b.Dispose()

# 7: analog clock at 4:50
$b, $g = New-Img 400 400; $cx = 200; $cy = 200; $R = 170; $g.DrawEllipse((New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), 4), $cx - $R, $cy - $R, 2 * $R, 2 * $R)
for ($i = 1; $i -le 12; $i++) { $a = ($i * 30 - 90) * [math]::PI / 180; $g.DrawString("$i", $f16b, $black, [float]($cx + 140 * [math]::Cos($a) - 10), [float]($cy + 140 * [math]::Sin($a) - 12)) }
$hm = (4 + 50 / 60) * 30 - 90; $mm = 50 * 6 - 90
$g.DrawLine((New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), 9), $cx, $cy, [float]($cx + 85 * [math]::Cos($hm * [math]::PI / 180)), [float]($cy + 85 * [math]::Sin($hm * [math]::PI / 180)))
$g.DrawLine((New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), 5), $cx, $cy, [float]($cx + 135 * [math]::Cos($mm * [math]::PI / 180)), [float]($cy + 135 * [math]::Sin($mm * [math]::PI / 180)))
$b.Save("$d\h_clock.png"); $g.Dispose(); $b.Dispose()

# 8: receipt: 12.50 + 3 x 4.20 + 8.90 + 9.00 = 43.00, -10% = 38.70
$b, $g = New-Img 420 520; $mono = New-Object System.Drawing.Font('Consolas', 15)
$lines = @('   CORNER CAFE', '', 'Pasta           12.50', '3 x Espresso     12.60', 'Salad            8.90', 'Cake             9.00', '----------------------', 'Subtotal        43.00', 'Discount 10%    -?.??', 'TOTAL           ??.??', '', '  Thank you!')
for ($i = 0; $i -lt $lines.Count; $i++) { $g.DrawString($lines[$i], $mono, $black, 40, 30 + $i * 36) }
$b.Save("$d\h_receipt.png"); $g.Dispose(); $b.Dispose()
Get-ChildItem $d -Filter 'h_*.png' | Select-Object Name, Length
