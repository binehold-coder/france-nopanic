#!/usr/bin/env bash
# Server side of the deploy. Runs on the IONOS VPS as DEPLOY_USER, one stage per call,
# so a failing step in GitHub Actions names the stage that broke.
#
#   server.sh python | env | service
#
#   /opt/france_nopanic/app    code, uploaded by GitHub Actions
#   /opt/france_nopanic/venv   virtualenv
#   /opt/france_nopanic/data   SQLite database
#   /opt/france_nopanic/.env   settings (chmod 600), rebuilt on every deploy
#
# Other bots on the server (budget-v2 etc.) are not touched.

set -euo pipefail

ROOT=/opt/france_nopanic
APP=$ROOT/app
VENV=$ROOT/venv
DATA=$ROOT/data
ENV_FILE=$ROOT/.env
SERVICE=france-nopanic
RUN_USER=$(id -un)

if [[ $(id -u) -eq 0 ]]; then SUDO=(); else SUDO=(sudo -n); fi

say() { printf '\n==> %s\n' "$*"; }
die() { printf '\n!!! %s\n' "$*" >&2; exit 1; }

# Value of KEY from an env file, quotes stripped; empty if file or key is missing.
env_value() {
	local file=$1 key=$2 line
	[[ -e $file ]] || return 0
	if [[ -r $file ]]; then line=$(grep -E "^${key}=" "$file" | tail -n1 || true)
	else line=$("${SUDO[@]}" grep -E "^${key}=" "$file" | tail -n1 || true); fi
	line=${line#*=}
	line=${line%$'\r'}
	line=${line#\"}; line=${line%\"}
	line=${line#\'}; line=${line%\'}
	printf '%s' "$line"
}

stage_python() {
	say "Python"
	local py=""
	for candidate in python3.13 python3.12 python3.11; do
		if command -v "$candidate" >/dev/null && "$candidate" -c 'import venv, ensurepip' 2>/dev/null; then
			py=$(command -v "$candidate"); break
		fi
	done
	[[ -n $py ]] || die "Нет Python 3.11+ с venv"
	echo "Использую $py ($("$py" --version))"
	[[ -x $VENV/bin/python ]] || "$py" -m venv "$VENV"
	"$VENV/bin/pip" install --quiet --upgrade pip
	"$VENV/bin/pip" install --quiet "$APP"
	"$VENV/bin/python" -c 'import nopanic, aiogram, anthropic; print("Пакет установлен, anthropic", anthropic.__version__)'
}

# Owner = Женя. Kept from the existing .env; on first deploy taken from the budget bot,
# where the first id in USERS / ALLOWED_USER_IDS is Женя.
find_owner_ids() {
	local ids users
	ids=$(env_value "$ENV_FILE" OWNER_IDS)
	if [[ -z $ids ]]; then
		users=$(env_value /opt/budget_v2/.env USERS)
		ids=${users%%:*}
	fi
	if [[ ! $ids =~ ^[0-9]+ ]]; then
		ids=$(env_value /opt/family_budget_bot/.env ALLOWED_USER_IDS)
		ids=${ids%%,*}; ids=${ids// /}
	fi
	printf '%s' "$ids"
}

stage_env() {
	say ".env"
	[[ -n ${BOT_TOKEN:-} ]] || die "Нет секрета FRANCE_NOPANIC_BOT (токен @france_nopanic_bot) в GitHub"
	for other in /opt/budget_v2/.env /opt/family_budget_bot/.env; do
		[[ $(env_value "$other" BOT_TOKEN) != "$BOT_TOKEN" ]] || die "Токен совпадает с ботом из $other — нужен токен @france_nopanic_bot"
	done

	local key owners
	key=${ANTHROPIC_API_KEY:-}
	[[ -n $key ]] || key=$(env_value "$ENV_FILE" ANTHROPIC_API_KEY)
	owners=$(find_owner_ids)
	[[ $owners =~ ^[0-9]+(,[0-9]+)*$ ]] || die "Не нашёл Telegram ID владельца (OWNER_IDS). Впиши руками в $ENV_FILE: OWNER_IDS=123456789"

	mkdir -p "$DATA"
	umask 077
	{
		echo "# Rebuilt by deploy/server.sh on every deploy. Secrets come from GitHub; settings from deploy/settings.env."
		echo "BOT_TOKEN=$BOT_TOKEN"
		echo "ANTHROPIC_API_KEY=$key"
		echo "OWNER_IDS=$owners"
		echo "DATABASE_PATH=$DATA/nopanic.db"
		echo "CONTENT_DIR=$APP/content"
		grep -E '^[A-Z_]+=' "$APP/deploy/settings.env"
	} >"$ENV_FILE.new"
	mv "$ENV_FILE.new" "$ENV_FILE"
	echo "OWNER_IDS=$owners; Anthropic-ключ: $([[ -n $key ]] && echo есть || echo НЕТ — разбор писем отключён)"
	grep -E '^(ACCESS_MODE|CHANNEL|LETTER_MODEL|CHAT_MODEL|FREE_LETTERS)=' "$ENV_FILE"
}

stage_service() {
	say "systemd: $SERVICE"
	local tmp; tmp=$(mktemp)
	sed -e "s|@USER@|$RUN_USER|g" -e "s|@ROOT@|$ROOT|g" "$APP/deploy/$SERVICE.service" >"$tmp"
	"${SUDO[@]}" install -m 644 "$tmp" "/etc/systemd/system/$SERVICE.service"
	rm -f "$tmp"
	"${SUDO[@]}" systemctl daemon-reload
	"${SUDO[@]}" systemctl enable "$SERVICE" >/dev/null 2>&1
	"${SUDO[@]}" systemctl reset-failed "$SERVICE" 2>/dev/null || true
	local since; since=$(date '+%Y-%m-%d %H:%M:%S')
	"${SUDO[@]}" systemctl restart "$SERVICE"

	for _ in $(seq 1 30); do
		if "${SUDO[@]}" journalctl -u "$SERVICE" --since "$since" --no-pager 2>/dev/null | grep -q "Started @"; then
			"${SUDO[@]}" journalctl -u "$SERVICE" --since "$since" --no-pager | grep "Started @" | tail -n1
			systemctl is-active "$SERVICE"; return
		fi
		sleep 1
	done
	"${SUDO[@]}" journalctl -u "$SERVICE" -n 40 --no-pager || true
	die "Бот не запустился за 30 секунд"
}

stage_feeds() {
	say "RSS-источники (проверка с сервера)"
	"$VENV/bin/python" -m nopanic.news || true
}

stage_dry() {
	say "Пробный отбор новостей (ничего не публикуется)"
	set -a; . "$ENV_FILE"; set +a
	"$VENV/bin/python" -m nopanic.news dry
}

case ${1:-} in
	dry) stage_dry ;;
	feeds) stage_feeds ;;
	python) stage_python ;;
	env) stage_env ;;
	service) stage_service ;;
	*) die "Использование: server.sh python|env|service|feeds" ;;
esac
