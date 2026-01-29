# Universal Git Deployment Script
# Automatically saves, commits, uploads, and creates versioned releases
# Works with any git repository
#
# Prerequisites:
#   - Git installed and repository initialized
#   - GitHub CLI installed: winget install GitHub.cli
#   - Authenticated: Run 'gh auth login' before first use
#
# Usage:
# Basic usage (uses main branch)
#   .\deploy.ps1 -CommitMessage "Your commit message"
# Use different branch
#   .\deploy.ps1 -CommitMessage "Feature update" -Branch "develop"
# Custom version file location
#   .\deploy.ps1 -CommitMessage "Update" -VersionFile "VERSION"

param(
    [string]$CommitMessage = "Update version",
    [string]$Branch = "main",
    [string]$ManifestFile = "custom_components/hive_schedule/manifest.json"
)

# Auto-detect repository information
Write-Host "Detecting repository information..." -ForegroundColor Cyan
$repoInfo = gh repo view --json nameWithOwner,url 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Not in a GitHub repository or gh CLI not authenticated" -ForegroundColor Red
    Write-Host "Make sure you're in a git repository and run: gh auth login" -ForegroundColor Yellow
    exit 1
}

$repoData = $repoInfo | ConvertFrom-Json
$repoName = $repoData.nameWithOwner
$repoUrl = $repoData.url

# Get current version from manifest.json
if (Test-Path $ManifestFile) {
    try {
        $manifestRaw = Get-Content $ManifestFile -Raw
        $manifest = $manifestRaw | ConvertFrom-Json
    } catch {
        Write-Host "Error: Failed to read/parse $ManifestFile" -ForegroundColor Red
        exit 1
    }
    if (-not $manifest.version) {
        Write-Host "Error: 'version' key not found in $ManifestFile" -ForegroundColor Red
        exit 1
    }
    $currentVersion = $manifest.version.Trim()
} else {
    Write-Host "Error: Manifest file not found at $ManifestFile" -ForegroundColor Red
    exit 1
}

# Parse version - flexible format handler (optional non-numeric prefix, any number of numeric parts)
$raw = $currentVersion.Trim()
if ($raw -match '^(?<prefix>[^\d]*)(?<nums>\d+(?:\.\d+)*)$') {
    $prefix = $matches['prefix']
    $numericVersion = $matches['nums']
} else {
    Write-Host "Invalid version format in $ManifestFile" -ForegroundColor Red
    Write-Host "Current content: '$currentVersion'" -ForegroundColor Red
    exit 1
}

$versionParts = $numericVersion -split '\.'
$lastIndex = $versionParts.Length - 1
$versionParts[$lastIndex] = ([int]$versionParts[$lastIndex] + 1).ToString()
$newNumericVersion = $versionParts -join '.'
$newVersion = "$prefix$newNumericVersion"

# Display deployment information
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Git Deployment Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Repository:      $repoName" -ForegroundColor White
Write-Host "Branch:          $Branch" -ForegroundColor White
Write-Host "Current version: $currentVersion" -ForegroundColor Cyan
Write-Host "New version:     $newVersion" -ForegroundColor Green
Write-Host "Commit message:  $CommitMessage" -ForegroundColor White
Write-Host ""

# Confirm deployment
$confirm = Read-Host "Continue with deployment? (y/n)"
if ($confirm -ne 'y' -and $confirm -ne 'Y') {
    Write-Host "Deployment cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""

# 1. Verify we're on correct branch
Write-Host "[1/8] Verifying branch..." -ForegroundColor Yellow
$currentBranch = git branch --show-current
if ($currentBranch -ne $Branch) {
    Write-Host "Error: Not on $Branch branch. Current branch: $currentBranch" -ForegroundColor Red
    $switchBranch = Read-Host "Switch to $Branch branch? (y/n)"
    if ($switchBranch -eq 'y' -or $switchBranch -eq 'Y') {
        git checkout $Branch
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to switch to $Branch branch" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Deployment cancelled." -ForegroundColor Yellow
        exit 1
    }
}
Write-Host "OK - On $Branch branch" -ForegroundColor Green

# 2. Sync with remote
Write-Host "[2/8] Syncing with remote $Branch branch..." -ForegroundColor Yellow
git pull origin $Branch
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Warning: Failed to pull from remote. Continuing anyway..." -ForegroundColor Yellow
}

# 3. Update manifest version (in-place, preserve formatting)
Write-Host "[3/8] Updating manifest version..." -ForegroundColor Yellow
try {
    $manifestPath = Resolve-Path $ManifestFile
    $content = Get-Content $manifestPath -Raw -ErrorAction Stop

    # Backup original file
    $backup = "$($manifestPath.Path).bak"
    $content | Out-File $backup -Encoding utf8

    # Replace only the version value, preserving surrounding whitespace/formatting
    $pattern = '("version"\s*:\s*)"[^"]*"'
    $replacement = '$1"' + $newVersion + '"'
    $newContent = [regex]::Replace($content, $pattern, $replacement)

    if ($newContent -eq $content) {
        Write-Host "Warning: No version field replaced in $ManifestFile" -ForegroundColor Yellow
    }

    # Write updated content back
    $newContent | Out-File $manifestPath -Encoding utf8

    Write-Host "OK - Manifest updated to $newVersion (backup: $backup)" -ForegroundColor Green
} catch {
    Write-Host "Error: Failed to update $ManifestFile - $_" -ForegroundColor Red
    exit 1
}

# 4. Stage all changes
Write-Host "[4/8] Staging changes..." -ForegroundColor Yellow
git add .
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Error staging changes" -ForegroundColor Red
    exit 1 
}

# Check if there are changes to commit
$changes = git diff --cached --name-only
if (-not $changes) {
    Write-Host "Warning: No changes to commit" -ForegroundColor Yellow
    $continueAnyway = Read-Host "Continue with tag and release creation? (y/n)"
    if ($continueAnyway -ne 'y' -and $continueAnyway -ne 'Y') {
        Write-Host "Deployment cancelled." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "OK - Changes staged:" -ForegroundColor Green
    $changes | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
}

# 5. Commit changes
Write-Host "[5/8] Committing changes..." -ForegroundColor Yellow
git commit -m "$CommitMessage - $newVersion"
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Warning: No changes to commit (may be normal)" -ForegroundColor Yellow
}

# 6. Create annotated tag
Write-Host "[6/8] Creating tag $newVersion..." -ForegroundColor Yellow
git tag -a $newVersion -m "Release version $newVersion - $CommitMessage"
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Error creating tag. Tag may already exist." -ForegroundColor Red
    Write-Host "To delete existing tag locally: git tag -d $newVersion" -ForegroundColor Yellow
    Write-Host "To delete existing tag remotely: git push origin --delete $newVersion" -ForegroundColor Yellow
    exit 1 
}
Write-Host "OK - Tag $newVersion created" -ForegroundColor Green

# 7. Push everything to GitHub
Write-Host "[7/8] Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "  - Pushing branch: $Branch" -ForegroundColor Gray
git push origin $Branch
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Error pushing branch to GitHub" -ForegroundColor Red
    exit 1 
}

Write-Host "  - Pushing tag: $newVersion" -ForegroundColor Gray
git push origin $newVersion
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Error pushing tag to GitHub" -ForegroundColor Red
    exit 1 
}
Write-Host "OK - Pushed to GitHub" -ForegroundColor Green

# 8. Create GitHub Release
Write-Host "[8/8] Creating GitHub release..." -ForegroundColor Yellow

# Build release notes
$releaseNotes = "$CommitMessage`n`nSee commit history for full details."

# Create release (without --target to avoid issues)
gh release create $newVersion --title "Release $newVersion" --notes $releaseNotes
if ($LASTEXITCODE -ne 0) { 
    Write-Host "Warning: Failed to create GitHub release" -ForegroundColor Yellow
    Write-Host "The code and tag are pushed successfully, but release creation failed." -ForegroundColor Yellow
    Write-Host "You can create the release manually at: $repoUrl/releases/new?tag=$newVersion" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  - Check GitHub CLI authentication: gh auth status" -ForegroundColor Gray
    Write-Host "  - Verify repository permissions" -ForegroundColor Gray
    Write-Host "  - Check if release already exists: gh release list" -ForegroundColor Gray
} else {
    Write-Host "OK - GitHub release created" -ForegroundColor Green
}

# Final summary
Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "Repository: $repoName" -ForegroundColor White
Write-Host "Version:    $newVersion" -ForegroundColor White
Write-Host "Branch:     $Branch" -ForegroundColor White
Write-Host "Release:    $repoUrl/releases/tag/$newVersion" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Verify the release on GitHub" -ForegroundColor White
Write-Host "2. Test the deployment in your environment" -ForegroundColor White
Write-Host "3. Update documentation if needed" -ForegroundColor White
Write-Host ""