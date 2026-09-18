"""Build the AtlasQuant private Windows ZIP from tracked repository files.

Safety goals:
- package only Git-tracked regular files;
- never follow symlinks or accept paths outside the repository;
- never include local secrets, virtual environments or caches;
- exclude development tests/docs/workflows from the end-user package;
- keep the Windows launcher local-only.

Usage:
    python build_windows_private_package.py
"""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path, PurePosixPath

OUTPUT_DIR = Path("dist")
OUTPUT_ZIP = OUTPUT_DIR / "AtlasQuant_Windows_Privado.zip"

BLOCKED_PARTS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
}
BLOCKED_NAMES = {
    ".env",
    "secrets.toml",
    "credentials.json",
    "service-account.json",
}
BLOCKED_SUFFIXES = {".pyc", ".pyo", ".key", ".pem", ".p12", ".pfx"}


def tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [p for p in completed.stdout.decode("utf-8").split("\0") if p]


def is_safe_package_path(path: str) -> bool:
    p = PurePosixPath(path)
    # Fail closed for absolute/traversal paths even if a malformed Git index is
    # ever presented to the builder. ZIP members must stay repository-relative.
    if p.is_absolute() or not p.parts or any(part in {"", ".", ".."} for part in p.parts):
        return False

    lower_parts = {part.lower() for part in p.parts}
    name = p.name.lower()

    if lower_parts & {part.lower() for part in BLOCKED_PARTS}:
        return False
    if name in BLOCKED_NAMES or name == ".gitignore":
        return False
    if p.suffix.lower() in BLOCKED_SUFFIXES:
        return False
    if name.startswith("test_") and p.suffix.lower() == ".py":
        return False
    if p.parts and p.parts[0].lower() == "docs":
        return False
    if p.suffix.lower() in {".md", ".yml", ".yaml"}:
        return False
    if p.suffix.lower() == ".txt" and name != "requirements.txt":
        return False
    if name == "build_windows_private_package.py":
        return False
    if "secret" in name or "credential" in name:
        return False
    return True


def package_files() -> list[str]:
    files: list[str] = []
    for rel in tracked_files():
        if not is_safe_package_path(rel):
            continue
        source = Path(rel)
        # zipfile.write() follows symlinks. Refuse them so a tracked link can
        # never make the release archive copy bytes from outside the checkout.
        if source.is_symlink() or not source.is_file():
            continue
        files.append(rel)

    required = {
        "usd_macro_pro_v4_cloud.py",
        "requirements.txt",
        "AtlasQuant_Windows_Privado.bat",
    }
    missing = sorted(required - set(files))
    if missing:
        raise RuntimeError(f"Arquivos obrigatórios ausentes do pacote: {missing}")
    return sorted(files)


def readme_text() -> str:
    return """ATLASQUANT - WINDOWS PRIVADO

1. Extraia todo o ZIP para uma pasta normal do Windows.
2. Dê dois cliques em AtlasQuant_Windows_Privado.bat.
3. Na primeira vez, escolha [1] para preparar o ambiente.
4. Depois escolha [2] para iniciar.
5. O navegador abrirá o AtlasQuant localmente em http://127.0.0.1:8501.

SEGURANÇA
- Este pacote não contém chaves de API nem arquivo secrets.toml.
- O launcher abre somente em 127.0.0.1 (computador local).
- O pacote não ativa envio de ordens reais.
- Chaves pessoais, quando necessárias, devem ser configuradas separadamente no computador.

Se a verificação falhar, use a opção [3] do launcher antes de alterar qualquer arquivo.
"""


def build(output: Path = OUTPUT_ZIP) -> Path:
    files = package_files()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(Path(rel), arcname=rel)
        zf.writestr("LEIA-ME_WINDOWS.txt", readme_text())

    return output


if __name__ == "__main__":
    built = build()
    print(f"Pacote criado: {built} ({built.stat().st_size} bytes)")
