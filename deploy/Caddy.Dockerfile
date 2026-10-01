# Caddy with the rate_limit directive, which the standard image does not include.
# Both are pinned so a rebuild gives the same server: the plugin has no release
# newer than v0.1.0, so it is pinned to a commit.
FROM caddy:2.11.4-builder AS builder
RUN xcaddy build --with github.com/mholt/caddy-ratelimit@5625512f24f6f59d6f64fb3aafe5eecff0b286db

FROM caddy:2.11.4
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
