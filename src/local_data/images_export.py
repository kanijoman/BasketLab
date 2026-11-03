"""The crest and the photos of a team, published for the DOCX of the individual scouting (#717, 17a).

The DOCX is made in the browser for the rival of the week, so it needs that team's crest, the photo of each player and his date of birth and height (the server used to fetch them from the
FEB while it wrote the document; the FEB sends no CORS header, so the browser cannot). They are published **per team**, sealed for the competition and every club of it (as a rival scouting
is), for the **current season only**, reduced (a photo to 200 px high in JPEG on white, a crest to 128 px in PNG), and each one once.

FBCYL (#721) has the crest and a photo per player too, but not the date of birth nor the height (no public source): they are asked of the ESB of the federation, by team id (crest) and by the uuid of
the player (photo; it says which photo he has now, so it is asked every time, and the image is downloaded only if its size changed).

The publisher is the one that downloads, and only what changed: an image already in the previous publication is kept when the size the FEB announces (a ``HEAD``) is the one it had, since
the FEB honours no conditional request (no ETag, a ``Last-Modified`` that is always now); a new one is downloaded; identity (birth date, height) is scraped once.
"""
from __future__ import annotations

import base64
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from src.live_prep.package_scopes import open_sealed, scope_key
from src.live_prep.package_sealing import Sealer
from src.local_data.export import FORMAT
from src.local_data.team_reports import report_scopes, seal_file
from src.utils.collection_utils import is_fbcyl

WORKERS = 8                  # the FEB answers in about a quarter of a second: a competition has ~300 images, so they are asked eight at a time
PHOTO_HEIGHT = 200
LOGO_HEIGHT = 128
TEAM_LOGO = "https://imagenes.feb.es/imagen.aspx?i={tid}&ti=1"
FBCYL_ESB = "https://esb.optimalwayconsulting.com/fbcyl/1/jR4rgA5K6Chhh5vyfrxo9wTScdg2NT7K"
_YEARS = re.compile(r"^\d{4}$")


class Source:
    """What the FEB answers: the bytes of an image, the size it announces, and the identity of a player. Replaced by a fake in the tests."""

    def get(self, url: str) -> Optional[bytes]:
        import requests

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception:  # noqa: BLE001 - an image that cannot be had is left out, not a failure of the publication
            return None

    def length(self, url: str) -> Optional[int]:
        import requests

        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            return int(response.headers["content-length"])
        except Exception:  # noqa: BLE001
            return None

    def identity(self, team_id: str, player_id: str) -> Tuple[Optional[str], Optional[str]]:
        """``(birth date dd/mm/yyyy, height "NNN cm")`` as the server scraped them from the FEB's player page (``PlayerDataFetcher``)."""
        from src.services.player_data_fetcher import PlayerDataFetcher

        birth, _age, height = PlayerDataFetcher(None, "").get_player_birth_info(player_id, team_id)
        return birth, height


    def _esb(self, path: str) -> Any:
        import requests

        try:
            response = requests.get(f"{FBCYL_ESB}{path}", timeout=10)
            response.raise_for_status()
            return json.loads(base64.b64decode(response.text)).get("messageData")
        except Exception:  # noqa: BLE001 - an answer that cannot be had is a blank, not a failure of the publication
            return None

    def photo_url(self, uuid: str) -> Optional[str]:
        """FBCYL: the URL of the photo a player (by uuid) has now, or ``None``."""
        found = self._esb(f"/Federateds/getPhotobyUuidFederat/{uuid}")
        return (found[0].get("photoUrl") or None) if isinstance(found, list) and found else None

    def team_logo_url(self, team_id: str) -> Optional[str]:
        """FBCYL: the URL of the crest of a team (by ``teamIdExtern``), or ``None``."""
        found = self._esb(f"/Clubs/getImageByTeamId/{team_id}")
        return found if isinstance(found, str) and found.startswith("http") else None


def reduce_photo(raw: bytes) -> Optional[bytes]:
    """The photo as a JPEG of ``PHOTO_HEIGHT`` px at most, on white (the PNG ones carry transparency); ``None`` if it is not an image."""
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:  # noqa: BLE001
        return None
    rgba = image.convert("RGBA")
    page = Image.new("RGB", rgba.size, (255, 255, 255))
    page.paste(rgba, mask=rgba.split()[3])
    if page.height > PHOTO_HEIGHT:
        page = page.resize((max(1, round(page.width * PHOTO_HEIGHT / page.height)), PHOTO_HEIGHT), Image.LANCZOS)
    out = io.BytesIO()
    page.save(out, format="JPEG", quality=78, optimize=True)
    return out.getvalue()


def reduce_logo(raw: bytes) -> Optional[bytes]:
    """The crest as a PNG of ``LOGO_HEIGHT`` px at most, keeping its transparency; ``None`` if it is not an image."""
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:  # noqa: BLE001
        return None
    image = image.convert("RGBA")
    if image.height > LOGO_HEIGHT:
        image = image.resize((max(1, round(image.width * LOGO_HEIGHT / image.height)), LOGO_HEIGHT), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _data_url(kind: str, raw: bytes) -> str:
    return f"data:image/{kind};base64,{base64.b64encode(raw).decode('ascii')}"


def current_season_collections(names: Iterable[str]) -> Set[str]:
    """The competitions of the newest season of each league among ``names`` (a season is the leading years of the name: ``2026_2027``, FBCYL's ``2026``)."""
    def season(name: str) -> str:
        years = []
        for part in name.split("_"):
            if _YEARS.match(part):
                years.append(part)
            elif years:
                break
        return "_".join(years)

    kept: Set[str] = set()
    for family in (False, True):                                 # FEB and FBCYL write the season differently (`2026_2027`, `2026`): each has its own newest
        seasons = {name: season(name) for name in names if is_fbcyl(name) is family}
        newest = max((s for s in seasons.values() if s), default=None)
        kept |= {name for name, s in seasons.items() if s and s == newest}
    return kept


def _fbcyl_team_sources(collection: Any) -> Dict[str, Dict[str, Any]]:
    """FBCYL: ``{teamIdExtern: {name, logo: None, fbcyl: True, players: {uuid: {name, no, photo: None}}}}``; neither the crest nor the photo are in the games (the ESB says where they are) and
    a player that came without uuid in every game cannot be asked for."""
    teams: Dict[str, Dict[str, Any]] = {}
    for doc in collection.find({}, {"stats.teams.teamIdExtern": 1, "stats.teams.name": 1, "stats.teams.players.uuid": 1, "stats.teams.players.name": 1, "stats.teams.players.dorsal": 1}).sort("_id", 1):
        for team in ((doc.get("stats") or {}).get("teams")) or []:
            if team.get("teamIdExtern") is None:
                continue
            entry = teams.setdefault(str(team["teamIdExtern"]), {"name": None, "logo": None, "fbcyl": True, "players": {}})
            entry["name"] = (team.get("name") or "").strip() or entry["name"]
            for player in team.get("players") or []:
                if player.get("uuid"):
                    entry["players"][str(player["uuid"])] = {"name": player.get("name"), "no": str(player["dorsal"]) if player.get("dorsal") is not None else None, "photo": None}
    return {tid: entry for tid, entry in teams.items() if entry["players"]}


def team_sources(collection: Any) -> Dict[str, Dict[str, Any]]:
    """``{team id: {name, logo, players: {player id: {name, no, photo}}}}`` as the last game of each says it (the photo URL is in ``player.logo``, as the server read it); FBCYL's by uuid."""
    if is_fbcyl(collection.name):
        return _fbcyl_team_sources(collection)
    teams: Dict[str, Dict[str, Any]] = {}
    projection = {"HEADER.TEAM": 1, "BOXSCORE.TEAM.id": 1, "BOXSCORE.TEAM.PLAYER.id": 1, "BOXSCORE.TEAM.PLAYER.no": 1, "BOXSCORE.TEAM.PLAYER.name": 1, "BOXSCORE.TEAM.PLAYER.logo": 1}
    for doc in collection.find({}, projection).sort("_id", 1):
        for team in (doc.get("HEADER") or {}).get("TEAM") or []:
            entry = teams.setdefault(str(team["id"]), {"name": None, "logo": None, "players": {}})
            entry["name"], entry["logo"] = team.get("name") or entry["name"], team.get("logo") or entry["logo"]
        for team in (doc.get("BOXSCORE") or {}).get("TEAM") or []:
            entry = teams.setdefault(str(team.get("id")), {"name": None, "logo": None, "players": {}})
            for player in team.get("PLAYER") or []:
                if player.get("id"):
                    url = player.get("logo") or ""
                    entry["players"][str(player["id"])] = {"name": player.get("name"), "no": player.get("no"), "photo": url if url.startswith("http") else None}
    return {tid: entry for tid, entry in teams.items() if entry["players"]}


def _previous(out_dir: Path, sealer: Sealer, collection: str, entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The payload of the previous publication of a team, opened with the key of the competition (the publisher holds the master); empty when there is none or it cannot be opened."""
    master = getattr(sealer, "master", None)
    if not entry or not master:
        return {}
    scope = f"competicion:{collection}"
    try:
        envelope = json.loads((out_dir / entry["file"]).read_text(encoding="utf-8"))
        return json.loads(open_sealed(envelope, entry["wraps"], {scope: scope_key(master, scope)}))
    except Exception:  # noqa: BLE001 - a missing or unreadable file is a team built from scratch
        return {}


def _image(url: Optional[str], kind: str, reduce: Callable[[bytes], Optional[bytes]], kept: Dict[str, Any], source: Source) -> Tuple[Optional[str], Optional[int]]:
    """``(data URL, size the FEB announced)`` of an image: the previous copy (``kept``: its URL, size and data) when the URL and the size are the same, else downloaded and reduced;
    ``(None, None)`` when it cannot be had."""
    if not url:
        return None, None
    if kept.get("data") and kept.get("url") == url and source.length(url) == kept.get("size"):
        return kept["data"], kept["size"]
    raw = source.get(url)
    reduced = reduce(raw) if raw else None
    return (_data_url(kind, reduced), len(raw)) if reduced else (None, None)


def team_payload(collection: str, team_id: str, team: Dict[str, Any], previous: Dict[str, Any], source: Source, workers: int = WORKERS) -> Dict[str, Any]:
    """The images and the identity of a team: its crest and, per player, his photo, date of birth and height. ``previous`` is what the last publication said of the team;
    ``sources`` keeps, per image, the URL and the size the FEB announced, to tell next time whether it changed."""
    old_sources = previous.get("sources") or {}
    fbcyl = bool(team.get("fbcyl"))
    logo_url = (source.team_logo_url(team_id) if fbcyl else team.get("logo") or TEAM_LOGO.format(tid=team_id))
    ordered = sorted(team["players"].items())

    def one(item: Tuple[str, Dict[str, Any]]) -> Tuple[Tuple[Optional[str], Optional[int]], Tuple[Optional[str], Optional[str]], Optional[str]]:
        pid, player = item
        known = (previous.get("players") or {}).get(pid) or {}
        url = source.photo_url(pid) if fbcyl else player["photo"]
        photo = _image(url, "jpeg", reduce_photo, {**((old_sources.get("players") or {}).get(pid) or {}), "data": known.get("photo")}, source)
        if fbcyl:
            return photo, (None, None), url
        identity = (known.get("birth_date"), known.get("height")) if ("birth_date" in known or "height" in known) else source.identity(team_id, pid)
        return photo, identity, url

    with ThreadPoolExecutor(max_workers=workers) as pool:
        crest = pool.submit(_image, logo_url, "png", reduce_logo, {**(old_sources.get("logo") or {}), "data": previous.get("logo")}, source)
        found = list(pool.map(one, ordered))
        logo, logo_size = crest.result()
    players: Dict[str, Any] = {}
    sources: Dict[str, Any] = {"logo": {"url": logo_url, "size": logo_size}, "players": {}}
    for (pid, player), ((photo, size), (birth, height), url) in zip(ordered, found):
        sources["players"][pid] = {"url": url, "size": size}
        players[pid] = {"name": player["name"], "no": player["no"], "photo": photo, "birth_date": birth, "height": height}
    return {"format": FORMAT, "collection": collection, "team_id": team_id, "team": team["name"], "logo": logo, "players": players, "sources": sources}


def seal_images(collection_handle: Any, collection: str, out_dir: Path, sealer: Sealer, old: Dict[Any, Dict[str, Any]], subdir: str = "",
                source: Optional[Source] = None) -> List[Dict[str, Any]]:
    """The sealed file of every team of the competition (``old``: the previous entries by ``(collection, team id, mode, scope)``) and its entries, ``mode`` ``images``."""
    source = source or Source()
    teams = team_sources(collection_handle)
    team_ids = sorted(teams)
    entries = []
    for team_id in team_ids:
        previous_entry = old.get((collection, team_id, "images", None))
        payload = team_payload(collection, team_id, teams[team_id], _previous(out_dir, sealer, collection, previous_entry), source)
        fields = seal_file(out_dir, f"{collection}|images|{team_id}", json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True), report_scopes("rival", team_id, team_ids, collection),
                           sealer, previous_entry, subdir)
        entries.append({"collection": collection, "team_id": team_id, "team": teams[team_id]["name"] or team_id, "mode": "images", **fields})
    return entries
