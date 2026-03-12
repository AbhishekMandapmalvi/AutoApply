/**
 * bundle-python.js — Download a platform-appropriate Python distribution,
 * install all pip dependencies, and download Playwright Chromium.
 *
 * The result is placed in electron/python-runtime/ for inclusion
 * in the installer via electron-builder extraResources.
 *
 * Usage: node electron/scripts/bundle-python.js
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const https = require('https');
const http = require('http');

// ─── Configuration ──────────────────────────────────────────────────────

const PYTHON_VERSION = '3.11.9';
const PBS_TAG = '20240814'; // python-build-standalone release tag

const RUNTIME_DIR = path.join(__dirname, '..', 'python-runtime');
const PYPROJECT_PATH = path.join(__dirname, '..', '..', 'pyproject.toml');

// Platform-specific download URLs
const DOWNLOADS = {
  'win32-x64': {
    url: `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`,
    type: 'zip',
    pythonExe: 'python.exe',
  },
  'darwin-x64': {
    url: `https://github.com/indygreg/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PYTHON_VERSION}+${PBS_TAG}-x86_64-apple-darwin-install_only.tar.gz`,
    type: 'tar.gz',
    pythonExe: 'bin/python3',
  },
  'darwin-arm64': {
    url: `https://github.com/indygreg/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PYTHON_VERSION}+${PBS_TAG}-aarch64-apple-darwin-install_only.tar.gz`,
    type: 'tar.gz',
    pythonExe: 'bin/python3',
  },
  'linux-x64': {
    url: `https://github.com/indygreg/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PYTHON_VERSION}+${PBS_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz`,
    type: 'tar.gz',
    pythonExe: 'bin/python3',
  },
};

// ─── Helpers ────────────────────────────────────────────────────────────

function getPlatformKey() {
  const platform = process.platform;
  const arch = process.arch;
  const key = `${platform}-${arch}`;
  if (!DOWNLOADS[key]) {
    console.error(`Unsupported platform: ${key}`);
    console.error(`Supported: ${Object.keys(DOWNLOADS).join(', ')}`);
    process.exit(1);
  }
  return key;
}

function downloadFile(url, destPath) {
  return new Promise((resolve, reject) => {
    console.log(`  Downloading: ${url}`);
    const handler = (res) => {
      // Follow redirects (GitHub releases use 302)
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        const redirectUrl = res.headers.location;
        const client = redirectUrl.startsWith('https') ? https : http;
        client.get(redirectUrl, handler).on('error', reject);
        return;
      }
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode} for ${url}`));
        return;
      }
      const totalBytes = parseInt(res.headers['content-length'] || '0', 10);
      let downloaded = 0;
      const file = fs.createWriteStream(destPath);
      res.on('data', (chunk) => {
        downloaded += chunk.length;
        if (totalBytes > 0) {
          const pct = ((downloaded / totalBytes) * 100).toFixed(1);
          process.stdout.write(`\r  Progress: ${pct}% (${(downloaded / 1024 / 1024).toFixed(1)}MB)`);
        }
      });
      res.pipe(file);
      file.on('finish', () => {
        file.close();
        console.log('');
        resolve();
      });
      file.on('error', reject);
    };

    const client = url.startsWith('https') ? https : http;
    client.get(url, handler).on('error', reject);
  });
}

function rmrf(dir) {
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function getDirSize(dir) {
  let size = 0;
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        size += getDirSize(fullPath);
      } else {
        size += fs.statSync(fullPath).size;
      }
    }
  } catch {
    // Ignore permission errors
  }
  return size;
}

function parseDependencies() {
  const content = fs.readFileSync(PYPROJECT_PATH, 'utf-8');
  const match = content.match(/dependencies\s*=\s*\[([\s\S]*?)\]/);
  if (!match) {
    console.error('Could not parse dependencies from pyproject.toml');
    process.exit(1);
  }
  const deps = match[1]
    .split('\n')
    .map((line) => line.replace(/#.*/, '').trim().replace(/,$/, '').replace(/^"/, '').replace(/"$/, ''))
    .filter((line) => line.length > 0);
  return deps;
}

function run(cmd, opts = {}) {
  console.log(`  Running: ${cmd}`);
  try {
    execSync(cmd, {
      stdio: opts.silent ? 'pipe' : 'inherit',
      timeout: opts.timeout || 300000,
      ...opts,
    });
  } catch (err) {
    if (!opts.ignoreError) {
      console.error(`  Command failed: ${cmd}`);
      throw err;
    }
  }
}

// ─── Main ───────────────────────────────────────────────────────────────

async function main() {
  const platformKey = getPlatformKey();
  const config = DOWNLOADS[platformKey];
  console.log(`\n=== Bundling Python ${PYTHON_VERSION} for ${platformKey} ===\n`);

  // Step 1: Clean
  console.log('Step 1: Cleaning previous runtime...');
  rmrf(RUNTIME_DIR);
  fs.mkdirSync(RUNTIME_DIR, { recursive: true });

  // Step 2: Download
  console.log('Step 2: Downloading Python distribution...');
  const archiveExt = config.type === 'zip' ? '.zip' : '.tar.gz';
  const archivePath = path.join(RUNTIME_DIR, `python${archiveExt}`);
  await downloadFile(config.url, archivePath);

  // Step 3: Extract
  console.log('Step 3: Extracting...');
  if (config.type === 'zip') {
    // Windows: use PowerShell to extract
    run(
      `powershell -Command "Expand-Archive -Path '${archivePath}' -DestinationPath '${RUNTIME_DIR}' -Force"`,
      { timeout: 60000 }
    );
  } else {
    // macOS/Linux: tar extract
    // python-build-standalone tarballs have a 'python/' prefix
    run(`tar -xzf "${archivePath}" -C "${RUNTIME_DIR}" --strip-components=1`, {
      timeout: 60000,
    });
  }
  fs.unlinkSync(archivePath);

  const pythonExe = path.join(RUNTIME_DIR, config.pythonExe);
  if (!fs.existsSync(pythonExe)) {
    console.error(`Python executable not found at: ${pythonExe}`);
    console.error('Contents of runtime dir:');
    run(`ls -la "${RUNTIME_DIR}"`, { ignoreError: true });
    process.exit(1);
  }
  console.log(`  Python found: ${pythonExe}`);

  // Step 4: Windows-only — patch ._pth file to enable imports
  if (process.platform === 'win32') {
    console.log('Step 4: Patching Windows embeddable Python...');
    const pthFiles = fs.readdirSync(RUNTIME_DIR).filter((f) => f.endsWith('._pth'));
    for (const pthFile of pthFiles) {
      const pthPath = path.join(RUNTIME_DIR, pthFile);
      let content = fs.readFileSync(pthPath, 'utf-8');
      // Uncomment "import site" to enable pip
      content = content.replace(/^#\s*import site/m, 'import site');
      // Add Lib/site-packages to path
      if (!content.includes('Lib/site-packages')) {
        content += '\nLib/site-packages\n';
      }
      // Add python-backend to path so packaged app can find project modules
      // (python-runtime and python-backend are siblings under resources/)
      if (!content.includes('python-backend')) {
        content += '../python-backend\n';
      }
      fs.writeFileSync(pthPath, content);
      console.log(`  Patched: ${pthFile}`);
    }

    // Bootstrap pip
    console.log('  Bootstrapping pip...');
    const getPipUrl = 'https://bootstrap.pypa.io/get-pip.py';
    const getPipPath = path.join(RUNTIME_DIR, 'get-pip.py');
    await downloadFile(getPipUrl, getPipPath);
    run(`"${pythonExe}" "${getPipPath}" --no-warn-script-location`, { timeout: 120000 });
    fs.unlinkSync(getPipPath);
  } else {
    console.log('Step 4: (skip — pip included on macOS/Linux)');
  }

  // Step 5: Install dependencies
  console.log('Step 5: Installing dependencies...');
  const deps = parseDependencies();
  console.log(`  Dependencies (${deps.length}): ${deps.map((d) => d.split('==')[0]).join(', ')}`);
  // Write deps to a temp requirements file to avoid shell quoting issues
  const reqsPath = path.join(RUNTIME_DIR, '_requirements.txt');
  fs.writeFileSync(reqsPath, deps.join('\n') + '\n');
  run(`"${pythonExe}" -m pip install -r "${reqsPath}" --no-cache-dir --no-warn-script-location`, {
    timeout: 600000,
  });
  fs.unlinkSync(reqsPath);

  // Step 6: Install Playwright Chromium
  console.log('Step 6: Installing Playwright Chromium...');
  const browsersPath = path.join(RUNTIME_DIR, 'playwright-browsers');
  fs.mkdirSync(browsersPath, { recursive: true });
  const env = { ...process.env, PLAYWRIGHT_BROWSERS_PATH: browsersPath };
  run(`"${pythonExe}" -m playwright install chromium`, {
    timeout: 600000,
    env,
  });

  // Step 7: Cleanup
  console.log('Step 7: Cleaning up...');
  // Remove pip cache, __pycache__, test directories
  const cleanupPatterns = ['__pycache__', 'tests', 'test', '*.dist-info'];
  const sitePackages = process.platform === 'win32'
    ? path.join(RUNTIME_DIR, 'Lib', 'site-packages')
    : path.join(RUNTIME_DIR, 'lib', `python3.11`, 'site-packages');

  if (fs.existsSync(sitePackages)) {
    // Only clean __pycache__ dirs (safe to remove)
    const removePycache = (dir) => {
      try {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
          const fullPath = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            if (entry.name === '__pycache__') {
              rmrf(fullPath);
            } else {
              removePycache(fullPath);
            }
          }
        }
      } catch {
        // Ignore
      }
    };
    removePycache(sitePackages);
  }

  // Remove pip cache
  const pipCache = path.join(RUNTIME_DIR, 'pip');
  rmrf(pipCache);

  // Step 8: Verify
  console.log('Step 8: Verifying...');
  try {
    run(
      `"${pythonExe}" -c "import flask; import playwright; import reportlab; import pydantic; print('All imports OK')"`,
      { timeout: 30000, env }
    );
  } catch {
    console.error('VERIFICATION FAILED: Could not import required packages.');
    process.exit(1);
  }

  // Step 9: Report size
  const totalSize = getDirSize(RUNTIME_DIR);
  const sizeMB = (totalSize / 1024 / 1024).toFixed(1);
  console.log(`\n=== Bundle complete: ${sizeMB}MB ===\n`);

  if (totalSize > 500 * 1024 * 1024) {
    console.warn(`WARNING: Bundle exceeds 500MB (${sizeMB}MB)`);
  }
}

main().catch((err) => {
  console.error('\nBundle failed:', err.message);
  process.exit(1);
});
