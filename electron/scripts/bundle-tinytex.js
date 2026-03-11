#!/usr/bin/env node

/**
 * bundle-tinytex.js — Download and bundle TinyTeX for LaTeX compilation.
 *
 * Implements: TASK-030 M3 — Downloads platform-specific TinyTeX build and
 * installs required LaTeX packages for resume compilation.
 *
 * Usage: node electron/scripts/bundle-tinytex.js [--platform <win|mac|linux>]
 *
 * Output: electron/resources/tinytex/ directory with pdflatex binary and packages.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const https = require('https');

// TinyTeX download URLs (from yihui/tinytex-releases)
const TINYTEX_URLS = {
  win: 'https://github.com/rstudio/tinytex-releases/releases/download/v2024.11/TinyTeX-1-v2024.11.zip',
  mac: 'https://github.com/rstudio/tinytex-releases/releases/download/v2024.11/TinyTeX-1-v2024.11.tgz',
  linux: 'https://github.com/rstudio/tinytex-releases/releases/download/v2024.11/TinyTeX-1-v2024.11.tar.gz',
};

// LaTeX packages required for resume templates
const REQUIRED_PACKAGES = [
  'geometry', 'enumitem', 'titlesec', 'hyperref', 'xcolor',
  'inputenc', 'fontenc', 'palatino', 'helvet',
];

const RESOURCES_DIR = path.join(__dirname, '..', 'resources', 'tinytex');

function detectPlatform() {
  const arg = process.argv.find(a => a === '--platform');
  if (arg) {
    const idx = process.argv.indexOf(arg);
    const val = process.argv[idx + 1];
    if (['win', 'mac', 'linux'].includes(val)) return val;
  }
  switch (process.platform) {
    case 'win32': return 'win';
    case 'darwin': return 'mac';
    default: return 'linux';
  }
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    console.log(`Downloading: ${url}`);
    const file = fs.createWriteStream(dest);

    const request = (url) => {
      https.get(url, (response) => {
        // Follow redirects
        if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
          request(response.headers.location);
          return;
        }
        if (response.statusCode !== 200) {
          reject(new Error(`HTTP ${response.statusCode}`));
          return;
        }
        response.pipe(file);
        file.on('finish', () => { file.close(); resolve(); });
      }).on('error', reject);
    };

    request(url);
  });
}

function extract(archivePath, destDir, platform) {
  fs.mkdirSync(destDir, { recursive: true });

  if (platform === 'win') {
    // Use PowerShell to extract zip on Windows
    execSync(`powershell -Command "Expand-Archive -Path '${archivePath}' -DestinationPath '${destDir}' -Force"`, { stdio: 'inherit' });
  } else {
    execSync(`tar -xf "${archivePath}" -C "${destDir}"`, { stdio: 'inherit' });
  }
}

function installPackages(tinytexDir) {
  // Find tlmgr binary
  const binDirs = fs.readdirSync(path.join(tinytexDir, 'bin'), { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => path.join(tinytexDir, 'bin', d.name));

  let tlmgr = null;
  for (const binDir of binDirs) {
    const candidate = path.join(binDir, process.platform === 'win32' ? 'tlmgr.bat' : 'tlmgr');
    if (fs.existsSync(candidate)) {
      tlmgr = candidate;
      break;
    }
  }

  if (!tlmgr) {
    console.warn('tlmgr not found — skipping package installation (packages may already be included)');
    return;
  }

  console.log(`Installing LaTeX packages: ${REQUIRED_PACKAGES.join(', ')}`);
  try {
    execSync(`"${tlmgr}" install ${REQUIRED_PACKAGES.join(' ')}`, { stdio: 'inherit' });
  } catch (e) {
    console.warn(`Package installation warning (some may already be present): ${e.message}`);
  }
}

async function main() {
  const platform = detectPlatform();
  console.log(`Platform: ${platform}`);
  console.log(`Output: ${RESOURCES_DIR}`);

  if (fs.existsSync(RESOURCES_DIR)) {
    console.log('TinyTeX already bundled — skipping download');
    return;
  }

  const url = TINYTEX_URLS[platform];
  const ext = platform === 'win' ? '.zip' : '.tar.gz';
  const tmpDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'tinytex-'));
  const archivePath = path.join(tmpDir, `tinytex${ext}`);

  try {
    await download(url, archivePath);
    console.log('Download complete. Extracting...');

    extract(archivePath, RESOURCES_DIR, platform);
    console.log('Extraction complete.');

    // Find the actual TinyTeX directory (may be nested)
    const entries = fs.readdirSync(RESOURCES_DIR);
    const tinytexSubdir = entries.find(e => e.toLowerCase().includes('tinytex'));
    const tinytexDir = tinytexSubdir
      ? path.join(RESOURCES_DIR, tinytexSubdir)
      : RESOURCES_DIR;

    installPackages(tinytexDir);
    console.log('TinyTeX bundling complete.');

  } finally {
    // Cleanup temp files
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error('TinyTeX bundling failed:', err.message);
  process.exit(1);
});
