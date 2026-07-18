#!/usr/bin/env python3
"""Sync each member's personal role colour to their Discord profile.

Colour source, in order of preference:
  1. Profile accent colour (if the user has set one)
  2. Dominant colour of their avatar image
If a user has neither (default avatar, no accent), their role is left alone.
"""
import colorsys
import io
import os
import sys
import requests
from PIL import Image

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID      = os.environ["GUILD_ID"]

# user_id -> role_id
MEMBERS = {
    "794545469589553163":  "1523061120745734316",  # Stitch
    "1281958110445178965": "1523061070665879702",  # Drago
    "1258117136904359967": "1523061001111470300",  # CK
}

API = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "User-Agent": "DiscordBot (https://github.com/discord/discord-api-docs, 1.0.0)",
}


def get_user(user_id):
    r = requests.get(f"{API}/users/{user_id}", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def dominant_avatar_color(user_id, avatar_hash):
    url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size=128"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB").resize((64, 64))

    # Reduce to a small palette, then pick the most "vibrant" prominent colour.
    pal = img.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    counts = pal.getcolors(64 * 64)  # [(count, (r, g, b)), ...]
    counts.sort(reverse=True)

    best, best_score = None, -1.0
    for count, (cr, cg, cb) in counts:
        h, s, v = colorsys.rgb_to_hsv(cr / 255, cg / 255, cb / 255)
        weight = count / (64 * 64)
        # Favour saturated, reasonably bright colours; ignore near-black/white.
        if v < 0.15 or (s < 0.08 and v > 0.9):
            continue
        score = (s * 0.7 + v * 0.3) * (0.5 + weight)
        if score > best_score:
            best, best_score = (cr, cg, cb), score

    if best is None:  # grayscale avatar - use the most common colour anyway
        best = counts[0][1]
    return (best[0] << 16) | (best[1] << 8) | best[2]


def desired_color(user):
    if user.get("accent_color"):
        return user["accent_color"], "accent colour"
    if user.get("avatar"):
        return dominant_avatar_color(user["id"], user["avatar"]), "avatar colour"
    return None, None


def current_role_colors():
    r = requests.get(f"{API}/guilds/{GUILD_ID}/roles", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return {role["id"]: role["color"] for role in r.json()}


def set_role_color(role_id, color):
    r = requests.patch(
        f"{API}/guilds/{GUILD_ID}/roles/{role_id}",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"color": color},
        timeout=20,
    )
    if not r.ok:
        print(f"Discord responded {r.status_code}: {r.text}")
    r.raise_for_status()


def main():
    roles = current_role_colors()
    for user_id, role_id in MEMBERS.items():
        user = get_user(user_id)
        name = user.get("global_name") or user.get("username") or user_id
        color, source = desired_color(user)
        if color is None:
            print(f"{name}: no accent colour or avatar - skipped")
            continue
        if roles.get(role_id) == color:
            print(f"{name}: #{color:06x} unchanged")
            continue
        set_role_color(role_id, color)
        print(f"{name}: role -> #{color:06x} (from {source})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
