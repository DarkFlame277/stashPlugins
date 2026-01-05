# version: 0.2.6

import json
import os
import sys
import datetime
from stashapi.stashapp import StashInterface
import stashapi.log as log

BLACKLIST_PATH = "/data/tag_blacklist.txt"
EXISTING_JSON_LOG = "/data/existing-jsons.log"

def load_tag_blacklist():
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


def main():
    try:
        json_input = json.loads(sys.stdin.read())
        client = StashInterface(json_input["server_connection"])
    except Exception as e:
        log.error(f"Failed to initialize StashInterface: {str(e)}")
        sys.exit(1)

    tag_blacklist = load_tag_blacklist()

    config = client.get_configuration()
    root_dirs = config.get("general", {}).get("stashPaths", [])

    if not root_dirs:
        log.warning(
            "No Stash library paths found via API; falling back to /data"
        )
        root_dirs = ["/data"]

    # ---------------------------------
    # Prepare JSON discovery log
    # ---------------------------------
    try:
        json_log = open(EXISTING_JSON_LOG, "w", encoding="utf-8")
        json_log.write(
            f"--- Scan started {datetime.datetime.now().isoformat()} ---\n"
        )
    except Exception as e:
        log.error(f"Failed to open existing-jsons.txt: {str(e)}")
        json_log = None

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    video_extensions = {'.mp4', '.mkv', '.avi', '.webm'}

    for root_dir in root_dirs:
        log.info(f"Scanning library path: {root_dir}")

        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in image_extensions and ext not in video_extensions:
                    continue

                media_path = os.path.join(dirpath, filename)
                json_path = media_path + ".json"
                if not os.path.exists(json_path):
                    continue

                if json_log:
                    json_log.write(json_path + "\n")

                log.info(f"Processing file: {media_path}")

                try:
                    with open(json_path, 'r') as f:
                        data = json.load(f)
                except Exception as e:
                    log.error(f"Invalid JSON in {json_path}: {str(e)}")
                    continue

                # -------------------
                # Extract tags (JSON)
                # -------------------
                new_tags = []
                if "tags" in data:
                    try:
                        new_tags = data["tags"].split()
                    except Exception as e:
                        log.error(f"Failed to parse tags in {json_path}: {str(e)}")

                # Remove blacklisted tags from JSON input
                new_tags = [t for t in new_tags if t not in tag_blacklist]

                # -------------------
                # Extract date
                # -------------------
                date = None
                if "date" in data:
                    try:
                        dt = datetime.datetime.strptime(data["date"], "%Y-%m-%d %H:%M:%S")
                        date = dt.date().isoformat()
                    except Exception as e:
                        log.error(f"Invalid date format in {json_path}: {str(e)}")

                # -------------------
                # Extract title
                # -------------------
                title = data.get("id")

                # -------------------
                # Extract URLs
                # -------------------
                new_urls = []

                if data.get("file_url"):
                    new_urls.append(data["file_url"])

                if data.get("source"):
                    new_urls.extend(data["source"].split())

                # -------------------
                # Determine type
                # -------------------
                item_type = 'image' if ext in image_extensions else 'scene'

                filter_dict = {"path": {"value": media_path, "modifier": "EQUALS"}}
                items = (
                    client.find_scenes(filter_dict)
                    if item_type == 'scene'
                    else client.find_images(filter_dict)
                )

                if len(items) != 1:
                    log.error(f"Item not found or multiple matches for {media_path}. Have you Scanned in your new files yet?")
                    continue

                item = items[0]

                if item.get("organized"):
                    log.info(f"Skipping organized item: {media_path}")
                    continue

                item_id = item['id']

                current_tags = [t['name'] for t in item['tags']]
                current_tags = [t for t in current_tags if t not in tag_blacklist]

                current_date = item.get('date')
                current_title = item.get('title')
                current_urls = item.get('urls') or []

                # -------------------
                # Combine tags
                # -------------------
                all_tag_names = list(set(current_tags + new_tags))

                # -------------------
                # Combine URLs
                # -------------------
                all_urls = list(dict.fromkeys(current_urls + new_urls))

                # -------------------
                # Detect changes
                # -------------------
                tags_changed = set(all_tag_names) != set([t['name'] for t in item['tags']])
                date_changed = date and current_date != date
                title_changed = title and current_title != title
                urls_changed = set(all_urls) != set(current_urls)

                if not (tags_changed or date_changed or title_changed or urls_changed):
                    log.info(f"No changes needed for {media_path}")
                    continue

                # -------------------
                # Get/Create tag IDs
                # -------------------
                tag_ids = []
                for tag_name in all_tag_names:
                    tags = client.find_tags(q=tag_name)
                    tag = tags[0] if tags else client.create_tag({"name": tag_name})
                    tag_ids.append(tag['id'])

                # -------------------
                # Prepare update
                # -------------------
                update_data = {
                    "id": item_id,
                    "tag_ids": tag_ids
                }

                if date_changed:
                    update_data["date"] = date
                if title_changed:
                    update_data["title"] = title
                if urls_changed:
                    update_data["urls"] = all_urls

                try:
                    if item_type == 'scene':
                        client.update_scene(update_data)
                    else:
                        client.update_image(update_data)
                    log.info(f"Updated metadata for {media_path}")
                except Exception as e:
                    log.error(f"Failed to update {media_path}: {str(e)}")

    if json_log:
        json_log.close()

    log.info("Import completed")
    sys.exit(0)


if __name__ == '__main__':
    main()
