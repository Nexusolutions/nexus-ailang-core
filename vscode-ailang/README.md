# AILang VS Code Extension

Syntax highlighting, LSP, DAP, and commands for the AILang programming language.

## Features

- **Syntax highlighting** for `.ailang` and `.ail` files
- **Snippets** for `fn`, `class`, `record`, `enum`, `interface`, `match`, etc.
- **Commands**:
  - `AILang: Run File` — run with default backend
  - `AILang: Run File (VM)` — run with VM backend
  - `AILang: Run File (AIR + Capabilities)` — run with AIR + capability verification
  - `AILang: Check (Analysis)` — capability + effect analysis without execution
  - `AILang: Format File` — format using `ailang fmt`
  - `AILang: Doctor` — diagnostic check
  - `AILang: New Project` — scaffold a new project
- **Format on save** (configurable)
- **Debugger** integration via DAP (breakpoints, step over/into/out)
- **LSP** integration (completion, hover, diagnostics, references, rename)

## Installation

```bash
cd vscode-ailang
code --install-extension .
```

Or package and install:
```bash
npm install -g @vscode/vsce
vsce package
code --install-extension ailang-1.1.0.vsix
```

## Configuration

| Setting | Default | Description |
|---|---|---|
| `ailang.pythonPath` | `python3` | Python interpreter with ailang installed |
| `ailang.lspEnabled` | `true` | Enable Language Server Protocol |
| `ailang.dapEnabled` | `true` | Enable Debug Adapter Protocol |
| `ailang.formatOnSave` | `false` | Format .ailang files on save |
| `ailang.defaultBackend` | `vm` | Default backend (interp/vm/air) |
| `ailang.capabilities` | `[]` | Capabilities to grant (--allow flags) |

## Debugging

1. Open a `.ailang` file
2. Set breakpoints by clicking in the gutter
3. Press `F5` or use the "AILang: Debug" launch configuration
4. Step through code with F10 (step over), F11 (step into), Shift+F11 (step out)
