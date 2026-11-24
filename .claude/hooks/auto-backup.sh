#!/usr/bin/env bash
# Backup automático: commit + push da branch atual depois de cada lote de ferramentas (hook PostToolBatch).
# Roda sem o modelo (zero tokens), em segundo plano, com trava contra execuções simultâneas.
# Log: .git/auto-backup.log (dentro de .git, então nunca vira alteração a ser commitada).
SKIP_CI="${AUTO_BACKUP_SKIP_CI:-0}"   # 1 = adiciona [skip ci] ao commit (evita rodar o build do GitHub Actions a cada backup)
MAX_MB=50                              # arquivos maiores que isso nunca são enviados (limite do GitHub: 100 MB)

# --- 1) reexecuta em segundo plano para não travar o Claude ---------------------------------------------
if [ -z "${AUTO_BACKUP_BG:-}" ]; then
  cat >/dev/null 2>&1 || true          # descarta o JSON que o hook recebe na entrada
  AUTO_BACKUP_BG=1 setsid nohup "$0" >/dev/null 2>&1 < /dev/null &
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
GITDIR="$(git rev-parse --absolute-git-dir)"
LOG="$GITDIR/auto-backup.log"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# --- 2) trava: se já houver outra execução, sai sem fazer nada -------------------------------------------
LOCK="$GITDIR/auto-backup.lock"
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"; flock -n 9 || exit 0
else
  mkdir "$LOCK.d" 2>/dev/null || exit 0
  trap 'rmdir "$LOCK.d" 2>/dev/null' EXIT
fi

# Não mexe no meio de rebase/merge/cherry-pick, nem em HEAD solto.
for f in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD; do [ -e "$GITDIR/$f" ] && exit 0; done
BRANCH="$(git symbolic-ref --short -q HEAD)" || { log "HEAD solto; backup ignorado"; exit 0; }

# --- 3) sem alterações: não faz nada ---------------------------------------------------------------------
[ -z "$(git status --porcelain)" ] && [ -z "$(git log '@{u}..HEAD' --oneline 2>/dev/null)" ] && exit 0

# --- 4) adiciona tudo (criados, modificados, excluídos), respeitando o .gitignore ------------------------
git add -A >>"$LOG" 2>&1

# Segurança: tira do commit segredos e arquivos grandes, mesmo que o .gitignore não os cubra.
SEGREDO='(^|/)(\.env(\..*)?|.*\.pem|.*\.key|.*\.p12|.*\.pfx|.*\.jks|.*\.keystore|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|credentials(\..*)?|.*secrets?(\..*)?|\.netrc|\.npmrc|\.pypirc|service-account.*\.json|google-services\.json)$'
while IFS= read -r -d '' f; do
  bloquear=0
  printf '%s' "$f" | grep -Eiq "$SEGREDO" && ! printf '%s' "$f" | grep -Eiq '\.env\.(example|sample|template)$' && bloquear=1
  if [ "$bloquear" = 0 ] && [ -f "$f" ] && [ "$(stat -c %s "$f")" -gt $((MAX_MB*1024*1024)) ]; then bloquear=1; fi
  if [ "$bloquear" = 1 ]; then
    git reset -q HEAD -- "$f" 2>/dev/null || git rm -q --cached -- "$f" 2>/dev/null
    grep -qxF "/$f" "$GITDIR/info/exclude" 2>/dev/null || { mkdir -p "$GITDIR/info"; printf '/%s\n' "$f" >> "$GITDIR/info/exclude"; }
    log "BLOQUEADO (segredo ou arquivo grande): $f"
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

# --- 5) commit com data e hora ---------------------------------------------------------------------------
if ! git diff --cached --quiet; then
  MSG="auto-backup: $(date '+%Y-%m-%d %H:%M:%S %z')"; [ "$SKIP_CI" = 1 ] && MSG="$MSG [skip ci]"
  git -c user.name="${GIT_AUTHOR_NAME:-$(git config user.name || echo auto-backup)}" \
      -c user.email="${GIT_AUTHOR_EMAIL:-$(git config user.email || echo auto-backup@localhost)}" \
      commit -q --no-verify -m "$MSG" >>"$LOG" 2>&1 || { log "commit falhou"; exit 0; }
  log "commit: $MSG"
fi

# --- 6) push da branch atual; se o remoto estiver à frente, rebase sem conflito ou desiste ---------------
push() { git push -q origin "HEAD:refs/heads/$BRANCH" >>"$LOG" 2>&1; }
if push; then log "push ok ($BRANCH)"; exit 0; fi
if git pull --rebase --autostash -q origin "$BRANCH" >>"$LOG" 2>&1 && push; then log "push ok após rebase ($BRANCH)"; exit 0; fi
git rebase --abort >/dev/null 2>&1
log "push NÃO feito (conflito ou sem rede); tenta de novo no próximo lote. Nada foi perdido: o commit está local."
exit 0
