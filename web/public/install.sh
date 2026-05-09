#!/usr/bin/env sh
# =============================================================
# tranquera · install
# Configura Claude Code para que cada prompt pase por el firewall
# de tu organización antes de salir hacia Anthropic.
#
# Uso:
#   curl -fsSL https://<dominio-tranquera>/install.sh | sh
#
# Override del proxy (opcional):
#   curl -fsSL https://<dominio-tranquera>/install.sh \
#     | TRANQUERA_PROXY_URL=https://otro-proxy.tu-org.dev sh
# =============================================================
set -eu

PROXY_URL="${TRANQUERA_PROXY_URL:-https://platanus-hack-26-ar-team-22-production.up.railway.app}"
MARKER="# tranquera · firewall de Claude Code"

# ---- Detectar shell -----------------------------------------
shell_name="$(basename "${SHELL:-}")"
case "$shell_name" in
    zsh)
        RC="$HOME/.zshrc"
        EXPORT_LINE="export ANTHROPIC_BASE_URL=\"$PROXY_URL\""
        ;;
    bash)
        # En macOS bash usa .bash_profile; en Linux .bashrc.
        if [ "$(uname -s)" = "Darwin" ]; then
            RC="$HOME/.bash_profile"
        else
            RC="$HOME/.bashrc"
        fi
        EXPORT_LINE="export ANTHROPIC_BASE_URL=\"$PROXY_URL\""
        ;;
    fish)
        RC="$HOME/.config/fish/config.fish"
        EXPORT_LINE="set -gx ANTHROPIC_BASE_URL \"$PROXY_URL\""
        ;;
    *)
        printf "✗ no reconocí tu shell (\$SHELL=%s).\n" "${SHELL:-vacío}" >&2
        printf "  agregá manualmente esta línea al rc de tu shell:\n\n" >&2
        printf "    export ANTHROPIC_BASE_URL=\"%s\"\n\n" "$PROXY_URL" >&2
        exit 1
        ;;
esac

# ---- Plan ----------------------------------------------------
printf "\n  ▎tranquera · install\n"
printf "  ├─ proxy  %s\n" "$PROXY_URL"
printf "  ├─ shell  %s\n" "$shell_name"
printf "  └─ rc     %s\n\n" "$RC"

# ---- Idempotencia -------------------------------------------
if [ -f "$RC" ] && grep -Fq "$MARKER" "$RC"; then
    printf "  · ya estaba configurado en %s — no toco nada\n" "$RC"
else
    mkdir -p "$(dirname "$RC")"
    {
        printf "\n%s\n" "$MARKER"
        printf "%s\n" "$EXPORT_LINE"
    } >> "$RC"
    printf "  · agregué la export a %s\n" "$RC"
fi

# ---- Verificar proxy ----------------------------------------
if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 5 "$PROXY_URL/health" >/dev/null 2>&1; then
        printf "  · proxy responde en /health ✓\n"
    else
        printf "  · ⚠ no pude alcanzar %s/health — verificá conectividad\n" "$PROXY_URL"
    fi
fi

# ---- Mensaje final ------------------------------------------
cat <<EOF

  Listo. Reabrí tu terminal o corré:

      source $RC

  Después usá Claude Code igual que siempre. Cada prompt va a
  pasar por la tranquera de tu organización. Si te bloquea algo
  legítimo, contactá a tu admin con el trace id que te devuelva
  la respuesta.

EOF
