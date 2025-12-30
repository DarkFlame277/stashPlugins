Give me a detailed prompt with specific instructions that I can send to an LLM to have it make this Stash app plugin for me based on the following info:

**Details and Requirements:**
- All my Stash content (images & videos) is stored in subdirectories under "/data".
- My .json files from Gallery-DL have the same filename as the video/image file (e.g., image.jpg -> image.jpg.json). Each of these .json files are stored alongside (in the same directory as) their corresponding file.
- The metadata from the Gallery-DL .json files should apply to **images** (I do ***NOT*** mean galleries) and to my videos (scenes).
- Here is an example .json file from Gallery-DL:
```json
{
    "file_url": "https://api-cdn-mp4.example.com/images/4737/73cc946ca8ff94189d8f62b9ec52ebfb.mp4",
    "tags": "tag1 tag2 tag3 tag4",
    "id": "15865334",
    "md5": "73cc946ca8ff94189d8f62b9ec52ebfb",
    "creator_id": "5714143",
    "source": "https://example3.com/Staleko3/status/1868411136816849239 https://example2.com/",
    "date": "2025-12-19 00:08:22"
}
```
- Metadata Mapping:
   - Tags should be extracted from the "tags" field in the JSON. Automatically create the tag in Stash if it doesn't exist, then apply it to the file.
  - Parse the "created-at" field and apply it to Stash's 'date' field.