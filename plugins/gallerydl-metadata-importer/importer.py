# version: 0.6.0

import json
import os
import sys
import time
import datetime
from stashapi.stashapp import StashInterface
import stashapi.log as log

BLACKLIST_PATH = "/data/tag_blacklist.txt"
EXISTING_JSON_LOG = "/data/existing-jsons.log"
BATCH_SIZE = 50
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 1  # seconds; actual delays are 1s, 2s, 4s


def normalize_tag(tag: str) -> str:
    return tag.strip().replace("_", " ").strip()


def load_tag_blacklist() -> set:
    blacklist = set()

    if not os.path.exists(BLACKLIST_PATH):
        log.info("No tag_blacklist.txt file found; skipping blacklist filtering")
        return blacklist

    try:
        with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                blacklist.add(normalize_tag(line))
        log.info(f"Loaded {len(blacklist)} blacklisted tags")
    except Exception as e:
        log.error(f"Failed to read tag_blacklist.txt: {str(e)}")

    return blacklist


def retry_call(fn, *args, **kwargs):
    """
    Calls fn(*args, **kwargs) with exponential backoff on failure.
    Retries up to RETRY_ATTEMPTS times before re-raising the last exception.
    Delays: RETRY_BACKOFF_BASE * 2^attempt  (e.g. 1s, 2s, 4s by default).
    """
    last_exc = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            log.warning(f"API call failed (attempt {attempt + 1}/{RETRY_ATTEMPTS}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    raise last_exc


def get_stash_config(client: StashInterface):
    """
    Fetches the plugin configuration directly from Stash.
    Uses the standard get_configuration() method to avoid GraphQL schema errors.
    """
    try:
        # Get the full configuration object
        config = client.get_configuration()
        
        # Access the plugins map (which is a dict of {plugin_id: settings})
        plugins_map = config.get("plugins")
        
        if not plugins_map:
            log.warning("No plugins configuration found in Stash.")
            return None

        plugin_id = "gallerydl-importer"
        if plugin_id in plugins_map:
            log.info(f"Found plugin config under key: {plugin_id}")
            return plugins_map[plugin_id]

        log.warning(f"Plugin config key '{plugin_id}' not found in Stash. Available keys:")
        for k in plugins_map.keys():
            log.warning(f" - {k}")
        return None
                
    except Exception as e:
        log.error(f"Failed to fetch config from Stash API: {str(e)}")
        return None


def clean_blacklisted_tags(client: StashInterface, tag_blacklist: set, dry_run: bool):
    for tag_name in tag_blacklist:
        for variant in {tag_name, tag_name.replace(" ", "_")}:
            tags = retry_call(client.find_tags, {"name": {"value": variant, "modifier": "EQUALS"}})
            if tags:
                tag_id = tags[0]["id"]
                if dry_run:
                    log.info(f"[DRY-RUN] Would delete blacklisted tag: {variant}")
                else:
                    try:
                        retry_call(
                            client.call_GQL,
                            f'mutation {{ tagDestroy(input: {{id: "{tag_id}"}}) }}'
                        )
                        log.info(f"Deleted blacklisted tag globally: {variant}")
                    except Exception as e:
                        log.error(f"Failed to delete {variant}: {str(e)}")


def flush_updates(client: StashInterface, pending_updates: list):
    """
    Sends all pending updates to Stash in batches, using aliased GraphQL mutations
    so each batch is a single HTTP request rather than one request per item.
    """
    if not pending_updates:
        return

    image_updates = [u for item_type, u in pending_updates if item_type == "image"]
    scene_updates = [u for item_type, u in pending_updates if item_type == "scene"]

    for updates, gql_type, input_type in (
        (image_updates, "imageUpdate", "ImageUpdateInput"),
        (scene_updates, "sceneUpdate", "SceneUpdateInput"),
    ):
        for batch_start in range(0, len(updates), BATCH_SIZE):
            batch = updates[batch_start : batch_start + BATCH_SIZE]

            # Build a single mutation with one alias per item, e.g.:
            #   mutation BatchUpdate($input0: ImageUpdateInput!, ...) {
            #     u0: imageUpdate(input: $input0) { id }
            #     ...
            #   }
            var_decls = ", ".join(
                f"$input{i}: {input_type}!" for i in range(len(batch))
            )
            ops = "\n".join(
                f"  u{i}: {gql_type}(input: $input{i}) {{ id }}"
                for i in range(len(batch))
            )
            mutation = f"mutation BatchUpdate({var_decls}) {{\n{ops}\n}}"
            variables = {f"input{i}": u for i, u in enumerate(batch)}

            try:
                retry_call(client.call_GQL, mutation, variables)
                log.info(
                    f"Flushed batch of {len(batch)} {gql_type} updates "
                    f"(items {batch_start}–{batch_start + len(batch) - 1})"
                )
            except Exception as e:
                log.error(f"Batch update failed: {str(e)}")


def main():
    try:
        json_input = json.loads(sys.stdin.read())
        client = StashInterface(json_input["server_connection"])
        settings = json_input.get("args", {})
    except Exception as e:
        log.error(f"Failed to initialize plugin: {str(e)}")
        sys.exit(1)

    # ---------------------------------------------------------
    # FIX FOR EMPTY SETTINGS
    # ---------------------------------------------------------
    # If args is empty (common when running from Tasks menu), 
    # fetch the settings manually from Stash's database.
    if not settings:
        log.warning("No arguments received from Stash. Fetching configuration from API...")
        settings = get_stash_config(client)
        if settings:
            log.info(f"Fetched settings from API: {settings}")
        else:
            log.error("Could not load settings. Using defaults (Dry Run ON).")
    # ---------------------------------------------------------

    # Load settings (Default False)
    disable_tagging = settings.get("disable_tagging", False)
    include_organized = settings.get("include_organized", False)
    disable_title_changes = settings.get("disable_title_changes", False)
    disable_performer_adding = settings.get("disable_performer_adding", False)
    disable_url_mapping = settings.get("disable_url_mapping", False)
    enable_dating = settings.get("enable_dating", False)

    disable_dry_run = settings.get("disable_dry_run", False)
    dry_run = not disable_dry_run

    log.info(f"Dry-run mode: {dry_run}")
    if dry_run:
        log.warning("!!! DRY RUN IS ACTIVE. NO CHANGES WILL BE SAVED !!!")
    else:
        log.warning("!!! DRY RUN IS DISABLED. CHANGES WILL BE APPLIED !!!")

    tag_blacklist = load_tag_blacklist()
    clean_blacklisted_tags(client, tag_blacklist, dry_run)

    config = client.get_configuration()
    root_dirs = [p["path"] for p in config.get("general", {}).get("stashes", [])] or ["/data"]

    json_log = None
    try:
        json_log = open(EXISTING_JSON_LOG, "w", encoding="utf-8")
        json_log.write(f"--- Scan started {datetime.datetime.now().isoformat()} ---\n")
    except Exception as e:
        log.error(f"Failed to open existing-jsons.log: {str(e)}")

    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    video_exts = {".mp4", ".mkv", ".avi", ".webm"}
    all_exts = image_exts | video_exts

    # --- Optimization 1: caches to avoid repeat API lookups per name ---
    # Maps normalized name -> id (or None if created only in dry-run)
    tag_cache: dict[str, str | None] = {}
    performer_cache: dict[str, str | None] = {}

    # --- Optimization 2: collect updates; flush in batches at the end ---
    pending_updates: list[tuple[str, dict]] = []  # [(item_type, update_dict), ...]

    for root in root_dirs:
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in all_exts:
                    continue

                media_path = os.path.join(dirpath, filename)
                json_path = media_path + ".json"
                if not os.path.exists(json_path):
                    continue

                if json_log:
                    json_log.write(json_path + "\n")

                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                item_type = "image" if ext in image_exts else "scene"
                finder = client.find_images if item_type == "image" else client.find_scenes

                items = retry_call(finder, {"path": {"value": media_path, "modifier": "EQUALS"}})
                if len(items) != 1:
                    continue

                item = items[0]
                
                # If we are NOT including organized items (Default), skip organized ones
                if not include_organized and item.get("organized"):
                    continue

                item_id = item["id"]
                update = {"id": item_id}

                # ---- TAGS ----
                # Run if tagging is NOT disabled
                if not disable_tagging:
                    new_tags = set()

                    for field in ("tags", "tags_general"):
                        if isinstance(data.get(field), str):
                            tag_string = data[field]
                            
                            # Check if comma exists to determine delimiter
                            if "," in tag_string:
                                # If commas are present, split strictly by comma
                                new_tags.update(tag_string.split(","))
                            else:
                                # If no commas, fallback to splitting by space
                                new_tags.update(tag_string.split())

                    # Filter against blacklist
                    new_tags = {
                        normalized
                        for t in new_tags
                        if (normalized := normalize_tag(t)) not in tag_blacklist
                    }

                    if new_tags:
                        tag_ids = []
                        for t in new_tags:
                            if t not in tag_cache:
                                # First time seeing this tag name — hit the API once
                                tags = retry_call(client.find_tags, {"name": {"value": t, "modifier": "EQUALS"}})
                                if tags:
                                    tag_cache[t] = tags[0]["id"]
                                else:
                                    # Tag does not exist
                                    if not dry_run:
                                        # Only create if NOT in dry run
                                        tag = retry_call(client.create_tag, {"name": t})
                                        tag_cache[t] = tag["id"]
                                        log.info(f"Created new tag: {t}")
                                    else:
                                        # If Dry Run, log intent but do not create
                                        log.info(f"[DRY-RUN] Would create tag: {t}")
                                        tag_cache[t] = None  # sentinel: known-missing in dry run

                            if tag_cache[t] is not None:
                                tag_ids.append(tag_cache[t])
                        
                        # Only add tag_ids to update if we actually have IDs
                        if tag_ids:
                            update["tag_ids"] = tag_ids

                # ---- PERFORMERS ----
                # Run if performer adding is NOT disabled
                if not disable_performer_adding and isinstance(data.get("tags_character"), str):
                    performer_ids = []
                    char_string = data["tags_character"]
                    char_names = char_string.split(",") if "," in char_string else char_string.split()
                    for name in char_names:
                        name = name.strip()
                        if name not in performer_cache:
                            # First time seeing this performer name — hit the API once
                            performers = retry_call(
                                client.find_performers,
                                {"name": {"value": name, "modifier": "EQUALS"}}
                            )
                            if performers:
                                performer_cache[name] = performers[0]["id"]
                            else:
                                # Performer does not exist
                                if not dry_run:
                                    # Only create if NOT in dry run
                                    performer = retry_call(client.create_performer, {"name": name})
                                    performer_cache[name] = performer["id"]
                                    log.info(f"Created new performer: {name}")
                                else:
                                    # If Dry Run, log intent but do not create
                                    log.info(f"[DRY-RUN] Would create performer: {name}")
                                    performer_cache[name] = None  # sentinel: known-missing in dry run

                        if performer_cache[name] is not None:
                            performer_ids.append(performer_cache[name])

                    if performer_ids:
                        update["performer_ids"] = performer_ids

                # ---- DATE ----
                if enable_dating and "date" in data:
                    try:
                        dt = datetime.datetime.strptime(data["date"], "%Y-%m-%d %H:%M:%S")
                        update["date"] = dt.date().isoformat()
                    except ValueError:
                        pass

                # ---- TITLE ----
                # Run if title changes are NOT disabled
                if not disable_title_changes and data.get("id"):
                    update["title"] = data["id"]

                # ---- URLS ----
                # Run if URL mapping is NOT disabled
                if not disable_url_mapping:
                    urls = set(item.get("urls") or [])
                    if "file_url" in data:
                        urls.add(data["file_url"])
                    if isinstance(data.get("source"), str):
                        urls.update(data["source"].split())
                    update["urls"] = list(urls)

                if len(update) <= 1:
                    continue

                if dry_run:
                    log.info(f"[DRY-RUN] Would update {media_path}: {update}")
                    continue

                # Queue the update instead of sending it immediately
                pending_updates.append((item_type, update))

    if json_log:
        json_log.close()

    # Flush all queued updates in batches
    flush_updates(client, pending_updates)

    if dry_run:
        log.info("Dry run completed")
    else:
        log.info("Import completed")

    sys.exit(0)


if __name__ == "__main__":
    main()