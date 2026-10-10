const { spawn } = require('child_process');
const path = require('path');
const vscode = require('vscode');

let lspProcess = null;
let outputChannel = null;

function activate(context) {
  outputChannel = vscode.window.createOutputChannel('AILang');
  context.subscriptions.push(outputChannel);

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('ailang.runFile', () => runFile('interp')),
    vscode.commands.registerCommand('ailang.runFileVM', () => runFile('vm')),
    vscode.commands.registerCommand('ailang.runFileAIR', () => runFile('air')),
    vscode.commands.registerCommand('ailang.checkFile', checkFile),
    vscode.commands.registerCommand('ailang.formatFile', formatFile),
    vscode.commands.registerCommand('ailang.doctor', runDoctor),
    vscode.commands.registerCommand('ailang.newProject', newProject),
  );

  // Format on save
  context.subscriptions.push(
    vscode.workspace.onWillSaveTextDocument(event => {
      const config = vscode.workspace.getConfiguration('ailang');
      if (config.get('formatOnSave') && event.document.languageId === 'ailang') {
        event.waitUntil(formatDocument(event.document));
      }
    })
  );

  // Start LSP if enabled
  const config = vscode.workspace.getConfiguration('ailang');
  if (config.get('lspEnabled')) {
    startLSP(context);
  }

  outputChannel.appendLine('[AILang] Extension activated');
}

function deactivate() {
  if (lspProcess) {
    lspProcess.kill();
    lspProcess = null;
  }
}

function getPython() {
  return vscode.workspace.getConfiguration('ailang').get('pythonPath') || 'python3';
}

function getBackendFlag(backend) {
  const config = vscode.workspace.getConfiguration('ailang');
  const defaultBackend = config.get('defaultBackend') || 'vm';
  const actual = backend || defaultBackend;
  if (actual === 'vm') return ['--vm'];
  if (actual === 'air') return ['--air'];
  return [];
}

function getCapabilityFlags() {
  const caps = vscode.workspace.getConfiguration('ailang').get('capabilities') || [];
  return caps.flatMap(c => ['--allow', c]);
}

function runFile(backend) {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'ailang') {
    vscode.window.showWarningMessage('No active .ailang file');
    return;
  }

  const filePath = editor.document.uri.fsPath;
  const python = getPython();
  const flags = getBackendFlag(backend);
  const caps = getCapabilityFlags();

  outputChannel.show(true);
  outputChannel.appendLine(`[AILang] Running ${filePath} (${backend})...`);

  const args = ['-m', 'ailang', ...flags, ...caps, filePath];
  const proc = spawn(python, args, { cwd: path.dirname(filePath) });

  proc.stdout.on('data', data => {
    outputChannel.append(data.toString());
  });
  proc.stderr.on('data', data => {
    outputChannel.append(`[stderr] ${data}`);
  });
  proc.on('close', code => {
    outputChannel.appendLine(`[AILang] Exit code: ${code}`);
  });
}

async function checkFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  const filePath = editor.document.uri.fsPath;
  const python = getPython();

  outputChannel.show(true);
  outputChannel.appendLine(`[AILang] Checking ${filePath}...`);

  const proc = spawn(python, ['-m', 'ailang', 'check', filePath]);
  proc.stdout.on('data', data => outputChannel.append(data.toString()));
  proc.stderr.on('data', data => outputChannel.append(`[stderr] ${data}`));
}

async function formatFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  await formatDocument(editor.document);
}

async function formatDocument(document) {
  const python = getPython();
  const filePath = document.uri.fsPath;

  return new Promise((resolve) => {
    const proc = spawn(python, ['-m', 'ailang', 'fmt', filePath]);
    proc.on('close', () => resolve());
  });
}

function runDoctor() {
  const python = getPython();
  outputChannel.show(true);
  outputChannel.appendLine('[AILang] Running doctor...');

  const proc = spawn(python, ['-m', 'ailang', 'doctor']);
  proc.stdout.on('data', data => outputChannel.append(data.toString()));
  proc.stderr.on('data', data => outputChannel.append(`[stderr] ${data}`));
}

async function newProject() {
  const name = await vscode.window.showInputBox({
    prompt: 'Project name',
    placeHolder: 'my-ailang-app',
  });
  if (!name) return;

  const type = await vscode.window.showQuickPick(
    ['app', 'lib', 'cli'],
    { placeHolder: 'Project type' }
  );
  if (!type) return;

  const folderUri = await vscode.window.showOpenDialog({
    canSelectFiles: false,
    canSelectFolders: true,
    canSelectMany: false,
    openLabel: 'Create project here',
  });
  if (!folderUri || folderUri.length === 0) return;

  const projectPath = path.join(folderUri[0].fsPath, name);
  const python = getPython();

  outputChannel.show(true);
  outputChannel.appendLine(`[AILang] Creating project ${name}...`);

  const proc = spawn(python, ['-m', 'ailang', 'pkg', 'init', name, '--dest', folderUri[0].fsPath]);
  proc.stdout.on('data', data => outputChannel.append(data.toString()));
  proc.stderr.on('data', data => outputChannel.append(`[stderr] ${data}`));
  proc.on('close', code => {
    if (code === 0) {
      vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(projectPath));
    }
  });
}

function startLSP(context) {
  const python = getPython();

  const serverOptions = {
    command: python,
    args: ['-m', 'ailang', '--lsp'],
  };

  const clientOptions = {
    documentSelector: [{ scheme: 'file', language: 'ailang' }],
    outputChannel: outputChannel,
  };

  // Use simple LSP client (no vscode-languageclient dependency needed for basic)
  // In production, would use vscode-languageclient node module
  outputChannel.appendLine('[AILang] LSP server configured (run with --lsp)');
}

module.exports = { activate, deactivate };
