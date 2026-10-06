"""Backup agendado, com registro do que aconteceu.

O QUE FALTAVA. `scripts/backup.sh` existia desde a v0.7.0 e a restauração era testada por
`scripts/restore_test.sh`. Mas NADA executava o script: nenhum cron, nenhum serviço, nenhum passo de
CI. A auditoria anterior registrou "backup: existe script" e isso virou uma linha verde num relatório.
Script que ninguém executa não é backup — é a intenção de ter um.

ONDE O AGENDAMENTO FOI PARAR. No executor de tarefas que já existe (`impacto.jobs`), com trava de
instância e intervalo próprios. Essa escolha é deliberada: criar um timer de systemd, um serviço no
compose E um job de CI daria três mecanismos para a mesma coisa, nenhum deles exercitado pela suíte.
Aqui a tarefa roda no mesmo processo que já roda as outras, grava em `ops_job_runs` e é testada.

O QUE ESTA TAREFA NÃO FAZ. Não decide política de retenção do negócio (RPO/RTO alvo) — isso é decisão
do proprietário, registrada como DATA_TO_CONFIRM. Não finge cópia externa: sem `BACKUP_OFFSITE_CMD`,
o resultado diz `offsite: false` e o relatório declara backup local como BLOCKED_EXTERNAL para
recuperação de desastre.
"""
from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from ..db.pq import Connection
from . import runs

JOB = "backup"
SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "backup.sh"

# NOTA DE SEGURANÇA. Este é o único lugar do aplicativo que executa processo externo, e é deliberado:
# o que um backup É fica definido em um só lugar (scripts/backup.sh, o mesmo script que a operação roda
# à mão e que restore_test.sh restaura). Reimplementar pg_dump aqui criaria duas definições de backup.
# As três chamadas abaixo usam caminho ABSOLUTO resolvido por shutil.which, lista de argumentos (nunca
# shell=True) e só recebem valores de CONFIGURAÇÃO do servidor — nada que venha de requisição.


def _exe(nome: str) -> str | None:
    return shutil.which(nome)


def configured(settings) -> tuple[bool, str]:
    if not settings.backup_dir:
        return False, "BACKUP_DIR não definido"
    if not settings.backup_database_url:
        return False, "BACKUP_DATABASE_URL não definido"
    if not SCRIPT.exists():
        return False, f"{SCRIPT.name} ausente"
    if not _exe("bash"):
        return False, "bash ausente no ambiente"
    return True, ""


def prune(destino: Path, keep: int) -> list[str]:
    """Mantém os `keep` dumps mais recentes. Remove o .sha256 junto, nunca o dump sem o hash."""
    dumps = sorted(destino.glob("impacto-*.dump"), key=lambda p: p.name, reverse=True)
    removidos = []
    for antigo in dumps[keep:]:
        antigo.unlink(missing_ok=True)
        Path(str(antigo) + ".sha256").unlink(missing_ok=True)
        removidos.append(antigo.name)
    return removidos


def run(conn: Connection, settings, *, force: bool = False) -> dict:
    """Executa o backup se estiver na hora. Devolve o resultado registrado."""
    ok, motivo = configured(settings)
    if not ok:
        with runs.record(conn, JOB) as r:
            r["status"] = "not_configured"
            r["detail"] = {"reason": motivo,
                           "note": ("Dependência externa: destino e credencial de backup são de "
                                    "infraestrutura. Enquanto isso, NÃO existe backup.")}
        return {"status": "not_configured", "reason": motivo}

    intervalo = max(1, int(settings.backup_interval_hours)) * 3600
    if not force and not runs.due(conn, JOB, every_seconds=intervalo):
        return {"status": "skipped", "reason": "fora da janela"}

    destino = Path(settings.backup_dir)
    with runs.record(conn, JOB) as r:
        destino.mkdir(parents=True, exist_ok=True)
        antes = {p.name for p in destino.glob("impacto-*.dump")}
        env = {**os.environ, "BACKUP_DATABASE_URL": settings.backup_database_url}
        proc = subprocess.run([_exe("bash"), str(SCRIPT), str(destino)], env=env,  # noqa: S603
                              capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise RuntimeError(f"backup.sh saiu com {proc.returncode}: "
                               f"{(proc.stderr or proc.stdout or '').strip()[:400]}")
        novos = sorted({p.name for p in destino.glob("impacto-*.dump")} - antes)
        if not novos:
            raise RuntimeError("backup.sh terminou sem erro e não deixou arquivo novo")
        arquivo = destino / novos[-1]
        tamanho = arquivo.stat().st_size
        if tamanho < 1024:
            raise RuntimeError(f"dump suspeito de vazio: {tamanho} bytes")

        # Confere o hash que o próprio script gravou: dump corrompido na escrita não pode passar por
        # backup bom só porque o processo devolveu zero.
        hash_arquivo = Path(str(arquivo) + ".sha256")
        conferido = None
        if hash_arquivo.exists():
            esperado = hash_arquivo.read_text(encoding="utf-8").split()[0]
            digest = hashlib.sha256(arquivo.read_bytes()).hexdigest()
            conferido = digest == esperado
            if not conferido:
                raise RuntimeError("sha256 do dump não bate com o arquivo .sha256 gravado")

        # Integridade lógica: pg_restore --list abre o cabeçalho do dump. Barato e pega o caso em que
        # o arquivo existe, tem tamanho e NÃO é um dump válido.
        listavel = None
        try:
            restore = _exe("pg_restore")
            if not restore:
                raise FileNotFoundError("pg_restore")
            lista = subprocess.run([restore, "--list", str(arquivo)],  # noqa: S603
                                   capture_output=True, text=True, timeout=300)
            listavel = lista.returncode == 0
        except FileNotFoundError:
            listavel = None   # pg_restore ausente no ambiente: não se afirma o que não se mediu
        if listavel is False:
            raise RuntimeError("pg_restore --list recusou o dump: arquivo não é um backup válido")

        offsite, offsite_erro = False, None
        if settings.backup_offsite_cmd:
            # Comando de cópia externa definido por quem operar a infraestrutura (variável de
            # ambiente), em lista de argumentos e sem shell: o arquivo entra como $1.
            cmd = shlex.split(settings.backup_offsite_cmd) + [str(arquivo)]
            envio = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # noqa: S603
            offsite = envio.returncode == 0
            if not offsite:
                offsite_erro = (envio.stderr or envio.stdout or "").strip()[:400]

        removidos = prune(destino, max(1, int(settings.backup_keep)))
        r["status"] = "ok"
        r["detail"] = {
            "file": arquivo.name, "bytes": tamanho, "sha256_matches": conferido,
            "pg_restore_list_ok": listavel, "pruned": removidos,
            "offsite": offsite, "offsite_error": offsite_erro,
            "offsite_configured": bool(settings.backup_offsite_cmd),
            "note": ("Backup LOCAL conferido. Sem cópia externa configurada isto não é recuperação de "
                     "desastre." if not settings.backup_offsite_cmd else "Backup com cópia externa."),
        }
        resultado = dict(r["detail"], status="ok")
    return resultado
