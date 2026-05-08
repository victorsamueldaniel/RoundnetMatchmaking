$version = Read-Host "Enter version (e.g. 1.2.3)"
if (-not $version) {
    Write-Host "Aborted: no version entered." -ForegroundColor Yellow
    exit 1
}
$tag = "v$version"
Write-Host "Tagging $tag..." -ForegroundColor Cyan
git tag $tag
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create tag (already exists?). Delete it first with: git tag -d $tag" -ForegroundColor Red
    exit 1
}
git push origin $tag
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to push tag." -ForegroundColor Red
    exit 1
}
Write-Host "Tag $tag pushed - build started on GitHub Actions." -ForegroundColor Green
