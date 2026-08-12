#!/usr/bin/env bash
# Bring .env up to date with .env.example, generating any missing secrets.
#
# Non-destructive by design, because .env holds the DocILE token and that is
# not regenerable — you have to go back to the website for it. Existing values
# are never touched; only absent keys get appended and only empty secrets get
# filled.
set -euo pipefail

cd "$(dirname "$0")/.."

EXAMPLE=.env.example
ENV_FILE=.env

# Keys that get a generated value when empty. Everything else is left blank for
# a human to fill (DOCILE_TOKEN) or already has a working default.
SECRETS=(
	POSTGRES_PASSWORD
	REDIS_PASSWORD
	CLICKHOUSE_PASSWORD
	MINIO_ROOT_PASSWORD
	LANGFUSE_SECRET_KEY
	LANGFUSE_ENCRYPTION_KEY
	LANGFUSE_SALT
	LANGFUSE_NEXTAUTH_SECRET
	LANGFUSE_INIT_USER_PASSWORD
)

if [[ ! -f $ENV_FILE ]]; then
	cp "$EXAMPLE" "$ENV_FILE"
	echo "created $ENV_FILE from $EXAMPLE"
fi

# A file not ending in a newline would have the first appended key run onto the
# end of the last line — which, for a .env whose last line is the DocILE token,
# silently corrupts the token.
if [[ -s $ENV_FILE && -n $(tail -c1 "$ENV_FILE") ]]; then
	printf '\n' >>"$ENV_FILE"
fi

# Append keys added to the example since this .env was written.
added=0
while IFS= read -r line; do
	[[ $line =~ ^([A-Z0-9_]+)= ]] || continue
	key=${BASH_REMATCH[1]}
	if ! grep -qE "^${key}=" "$ENV_FILE"; then
		printf '%s\n' "$line" >>"$ENV_FILE"
		echo "added $key"
		added=$((added + 1))
	fi
done <"$EXAMPLE"
[[ $added -gt 0 ]] && echo "note: $added key(s) appended at the end, out of section order"

# Fill empty secrets. Hex keeps them safe to paste into a URL, which
# DATABASE_URL and REDIS_URL both do. Langfuse requires ENCRYPTION_KEY to be
# exactly 32 bytes of hex; the rest just need to be unguessable.
for key in "${SECRETS[@]}"; do
	if grep -qE "^${key}=$" "$ENV_FILE"; then
		value=$(openssl rand -hex 32)
		[[ $key == LANGFUSE_SECRET_KEY ]] && value="sk-lf-${value:0:32}"
		# The delimiter is | because a generated value is hex, never |.
		sed -i.bak "s|^${key}=$|${key}=${value}|" "$ENV_FILE"
		rm -f "${ENV_FILE}.bak"
		echo "generated $key"
	fi
done

if grep -qE '^DOCILE_TOKEN=$' "$ENV_FILE"; then
	echo
	echo "DOCILE_TOKEN is still empty — register at https://docile.rossum.ai/"
	echo "and set it before running scripts/download_dataset.sh."
fi
