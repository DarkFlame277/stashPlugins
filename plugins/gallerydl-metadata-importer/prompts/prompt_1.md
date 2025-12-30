You are an expert in developing plugins for the Stash app (the open-source media organizer). Your task is to create a complete, functional Stash plugin that imports metadata from Gallery-DL JSON files into Stash images (individual images, not galleries) and  scenes (videos). Write the plugin in Python 3.12. Follow these requirements precisely—do not add, omit, or alter functionality unless specified.

### Key Requirements and Details:
- **Content Structure**: All Stash content (images and videos) is stored in subdirectories under "/data". The plugin must scan recursively through "/data" and subdirectories to find media files and corresponding JSON files.
- **JSON Files**: Each Gallery-DL JSON file shares the media file's filename with ".json" appended (e.g., "video.mp4.json" for "video.mp4"; "image.jpg.json" for "image.jpg"). JSON files are in the same directory as the media.
- **Applicable Media Types**: Apply metadata only to individual images (Stash "images") and videos (Stash "scenes").
- **Example JSON Structure**: Parse based on this format (fields may vary slightly in content):
  ```json
  {
      "file_url": "https://api-cdn-mp4.example.com/images/4737/73cc946ca8ff94866396562b9ec52ebfb.mp4",
      "tags": "tag1 tag2 tag3 tag4",
      "id": "15865334",
      "md5": "73cc946ca8ff94866396562b9ec52ebfb",
      "creator_id": "5714143",
      "source": "https://example2.com/Username/status/1868411136816849239 https://example3.com/",
      "date": "2025-12-19 00:08:22"
  }
  ```
- **Metadata Mapping**:
  - **Tags**: Extract tags from the "tags" field, which is a space-separated string (e.g., "tag1 tag2 tag3 tag4"). Split this string into individual tags. For each:
    - Query Stash's GraphQL API to check if it exists.
    - Create it if missing.
    - Apply all tags to the Stash image (images) or scene (videos).
  - **Date**: Parse from "date" in "YYYY-MM-DD HH:MM:SS" format (e.g., "2025-12-19 00:08:22"). Convert to ISO date-only "YYYY-MM-DD" (discard time). Apply to Stash's 'date' field.

### Plugin Behavior:
- Implement as a Stash "task" plugin runnable on demand via the Stash interface.
- Identify media by extension: Images (.jpg, .jpeg, .png, .gif, .webp); Videos (.mp4, .mkv, .avi, .webm).
- For each media file under "/data":
  - Check for matching ".json" in the same directory.
  - If present, parse JSON, extract and map the metadata as specified.
  - Use Stash's GraphQL API to locate the image or scene (match by path or checksum).
  - Update with tags and date.
  - Skip files without matching JSON. Do not log these skips.
- Handle duplicates: Avoid re-adding existing tags.
- Logging: Use Stash's system for progress (e.g., "Processing file: /data/subdir/video.mp4") and errors.
- Make idempotent: Multiple runs avoid duplicate tags or unnecessary date overwrites.
- Error Handling: Catch/log issues like JSON errors, API failures, file not found.

### Technical Implementation:
- Use Python 3.12.
- Import: os, json, stashapi (or raw GraphQL via requests if unavailable).
- Structure as a single file (e.g., importer.py) with a main function for Stash.
- The user will be using a YAML manifest with task hooks.
- Test the logic mentally with the example JSON and ensure it matches the mapping.

### Output:
- Provide the complete Python script.

Generate the full plugin code now.