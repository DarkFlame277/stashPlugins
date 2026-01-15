# version: 0.5.0

import json
import os
import sys
import datetime
from stashapi.stashapp import StashInterface
import stashapi.log as log

BLACKLIST_PATH = "/data/tag_blacklist.txt"
EXISTING_JSON_LOG = "/data/existing-jsons.log"

# Normalize tags by replacing "_" with " "
def normalize_tag(tag: str) -> str:
    return tag.strip().replace("_", " ").strip()

# Load the blacklist
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
                blacklist.add(line)
        log.info(f"Loaded {len(blacklist)} blacklisted tags")
    except Exception as e:
        log.error(f"Failed to read tag_blacklist.txt: {str(e)}")

    return blacklist

# Delete blacklisted tags from Stash
def clean_blacklisted_tags(client: StashInterface, tag_blacklist: set):
    for tag_name in tag_blacklist:
        # Search and delete the normalized (spaced) version
        tags = client.find_tags(q=tag_name)
        if tags:
            tag_id = tags[0]['id']
            try:
                client.call_GQL("mutation { tagDestroy(input: {id: \"" + tag_id + "\"}) }")
                log.info(f"Deleted blacklisted tag globally: {tag_name}")
            except Exception as e:
                log.error(f"Failed to delete {tag_name}: {str(e)}")
        
        # Compute and delete the underscored version if different
        underscored = tag_name.replace(" ", "_")
        if underscored != tag_name:
            tags = client.find_tags(q=underscored)
            if tags:
                tag_id = tags[0]['id']
                try:
                    client.call_GQL("mutation { tagDestroy(input: {id: \"" + tag_id + "\"}) }")
                    log.info(f"Deleted blacklisted underscored tag globally: {underscored}")
                except Exception as e:
                    log.error(f"Failed to delete {underscored}: {str(e)}")

def main():
    try:
        json_input = json.loads(sys.stdin.read())
        client = StashInterface(json_input["server_connection"])
    except Exception as e:
        log.error(f"Failed to initialize StashInterface: {str(e)}")
        sys.exit(1)

    tag_blacklist = load_tag_blacklist()

    # Delete blacklisted tags from Stash
    clean_blacklisted_tags(client, tag_blacklist)

    config = client.get_configuration()
    root_dirs = [path["path"] for path in config.get("general", {}).get("stashes", [])]

    if not root_dirs:
        log.warning("No Stash library paths found via API; falling back to /data")
        root_dirs = ["/data"]

    # Prepare JSON discovery log
    json_log = None
    try:
        json_log = open(EXISTING_JSON_LOG, "w", encoding="utf-8")
        json_log.write(f"--- Scan started {datetime.datetime.now().isoformat()} ---\n")
    except Exception as e:
        log.error(f"Failed to open existing-jsons.txt: {str(e)}")

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    video_extensions = {'.mp4', '.mkv', '.avi', '.webm'}
    media_extensions = image_extensions | video_extensions

    for root_dir in root_dirs:
        log.info(f"Scanning library path: {root_dir}")

        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in media_extensions:
                    continue

                media_path = os.path.join(dirpath, filename)
                json_path = media_path + ".json"
                if not os.path.exists(json_path):
                    continue

                if json_log:
                    json_log.write(json_path + "\n")

                log.info(f"Processing file: {media_path}")

                try:
                    with open(json_path, 'r', encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    log.error(f"Invalid JSON in {json_path}: {str(e)}")
                    continue

                # Extract tags
                new_tags = set()

                # Parse "tags" field (comma or space delimited)
                if "tags" in data and isinstance(data["tags"], str):
                    raw_tags = data["tags"].strip()
                    if "," in raw_tags:
                        new_tags.update(t.strip() for t in raw_tags.split(","))
                    else:
                        new_tags.update(raw_tags.split())

                # Parse "tags_general" field (space delimited)
                if "tags_general" in data and isinstance(data["tags_general"], str):
                    new_tags.update(data["tags_general"].split())

                # Normalize and filter blacklist
                new_tags = {normalize_tag(t) for t in new_tags if t.strip() and normalize_tag(t) not in tag_blacklist}

                # Extract performers (tags_character)
                new_performers = set()
                if "tags_character" in data and isinstance(data["tags_character"], str):
                    new_performers = {p.strip() for p in data["tags_character"].split() if p.strip()}

                # Extract date
                date = None
                if "date" in data:
                    try:
                        dt = datetime.datetime.strptime(data["date"], "%Y-%m-%d %H:%M:%S")
                        date = dt.date().isoformat()
                    except ValueError:
                        log.error(f"Invalid date format in {json_path}: {data['date']}")

                # Extract title
                title = data.get("id")

                # Extract URLs
                new_urls = set()
                if "file_url" in data:
                    new_urls.add(data["file_url"])
                if "source" in data and isinstance(data["source"], str):
                    new_urls.update(data["source"].split())

                # Determine type
                item_type = 'image' if ext in image_extensions else 'scene'

                # Find item in Stash
                filter_dict = {"path": {"value": media_path, "modifier": "EQUALS"}}
                find_func = client.find_images if item_type == 'image' else client.find_scenes
                items = find_func(filter_dict)

                if len(items) != 1:
                    log.error(f"Item not found or multiple matches for {media_path}. Have you scanned in your new files yet?")
                    continue

                item = items[0]
                if item.get("organized"):
                    log.info(f"Skipping organized item: {media_path}")
                    continue

                item_id = item['id']

                # Get current tags, normalized and filtered
                current_tags = {normalize_tag(t['name']) for t in item.get('tags', [])}
                blacklisted_removed = any(normalize_tag(t['name']) in tag_blacklist for t in item.get('tags', []))

                if blacklisted_removed:
                    current_tags = {t for t in current_tags if t not in tag_blacklist}

                # Get current performers
                current_performers = {p['name'] for p in item.get('performers', []) if 'name' in p}

                current_date = item.get('date')
                current_title = item.get('title')
                current_urls = set(item.get('urls') or [])

                # Combine data
                all_tags = current_tags | new_tags
                all_performers = current_performers | new_performers
                all_urls = current_urls | new_urls

                # Detect changes
                tags_changed = all_tags != {normalize_tag(t['name']) for t in item.get('tags', []) if normalize_tag(t['name']) not in tag_blacklist}
                performers_changed = all_performers != current_performers
                date_changed = date and current_date != date
                title_changed = title and current_title != title
                urls_changed = all_urls != current_urls

                if not (tags_changed or performers_changed or date_changed or title_changed or urls_changed or blacklisted_removed):
                    log.info(f"No changes needed for {media_path}")
                    continue

                # Get/Create tag IDs
                tag_ids = []
                for tag_name in all_tags:
                    tags = client.find_tags({"name": {"value": tag_name, "modifier": "EQUALS"}})
                    tag = tags[0] if tags else client.create_tag({"name": tag_name})
                    tag_ids.append(tag['id'])

                # Get/Create performer IDs
                performer_ids = []
                for performer_name in all_performers:
                    performers = client.find_performers({"name": {"value": performer_name, "modifier": "EQUALS"}})
                    performer = performers[0] if performers else client.create_performer({"name": performer_name})
                    performer_ids.append(performer['id'])

                # Prepare update
                update_data = {
                    "id": item_id,
                    "tag_ids": tag_ids,
                    "performer_ids": performer_ids
                }
                if date_changed:
                    update_data["date"] = date
                if title_changed:
                    update_data["title"] = title
                if urls_changed:
                    update_data["urls"] = list(all_urls)

                # Update item
                update_func = client.update_image if item_type == 'image' else client.update_scene
                try:
                    update_func(update_data)
                    log.info(f"Updated metadata for {media_path}")
                except Exception as e:
                    log.error(f"Failed to update {media_path}: {str(e)}")

    if json_log:
        json_log.close()

    log.info("Import completed")
    sys.exit(0)

if __name__ == '__main__':
    main()
    