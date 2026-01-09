# 1st Addition Prompt for ChatGPT

Now, lets add more mappings.
**Additional Metadata Mappings:**
    - **Title:** Map JSON `id` to Stash `title`.
    - **URLs:**
        - Add JSON `file_url` to Stash `urls`.
        - The JSON `source` field contains a string with one or more URLs separated by spaces. Split this string dynamically and add every resulting URL to the Stash `urls` list.


# 2nd Addition Prompt for ChatGPT

Awesome. Thank you.
Now add a feature that reads a separate, user created file called "tag_blacklist" which will have a list of user defined tags (one tag per-line). The file format for the "tag_blacklist" file should be whatever is best for the this use case. There will be only one "tag_blacklist" file used for all Stash content. This file will be present at "/data". The plugin script should treat this file as a blacklist for tags. All tags read from the JSON files should be checked against "tag_blacklist". If any tag appears in the blacklist, then it should be ignored/skipped and not added to the Stash content. Additionally, any blacklisted tags found already applied to Stash content should be removed.


# 3rd Addition Prompt for ChatGPT

Adjust this script so that it skips over Stash content marked as "organized".


# 4th Addition Prompt for ChatGPT

Add a feature to this Stash app plugin so that it will log all the Gallery-DL json files it finds into a file named "existing-jsons.log" in Stash's main content directory. (For debugging purposes.)


# 5th Addition Prompt for ChatGPT

Update `importer.py` to combine tags from two JSON fields:
1. `tags`: Automatically parse this string using either commas or spaces as the delimiter—whichever is present in the file.
2. `tags_general`: Parse this string using spaces as the delimiter.
Merge results from both fields into a single, deduplicated list for the Stash content tags.

Also add a feature that maps `tags_character` (space separated) to the Stash app `Performers` field.
