# 1st ChatGPT

Now, lets add more mappings.
**Additional Metadata Mappings:**
    - **Title:** Map JSON `id` to Stash `title`.
    - **URLs:**
        - Add JSON `file_url` to Stash `urls`.
        - The JSON `source` field contains a string with one or more URLs separated by spaces. Split this string dynamically and add every resulting URL to the Stash `urls` list.


# 2nd ChatGPT

Awesome. Thank you.
Now add a feature that reads a separate, user created file called "tag_blacklist" which will have a list of user defined tags (one tag per-line). The file format for the "tag_blacklist" file should be whatever is best for the this use case. There will be only one "tag_blacklist" file used for all Stash content. This file will be present at "/data". The plugin script should treat this file as a blacklist for tags. All tags read from the JSON files should be checked against "tag_blacklist". If any tag appears in the blacklist, then it should be ignored/skipped and not added to the Stash content. Additionally, any blacklisted tags found already applied to Stash content should be removed.


# 3rd ChatGPT

Adjust this script so that it skips over Stash content marked as "organized".


# 4th ChatGPT

Add a feature to this Stash app plugin so that it will log all the Gallery-DL json files it finds into a file named "existing-jsons.log" in Stash's main content directory. (For debugging purposes.)


# 0.2.0

Update `importer.py` to combine tags from two JSON fields:
1. `tags`: Automatically parse this string using either commas or spaces as the delimiter—whichever is present in the file.
2. `tags_general`: Parse this string using spaces as the delimiter.
Merge results from both fields into a single, deduplicated list for the Stash content tags.

Also add a feature that maps `tags_character` (space separated) to the Stash app `Performers` field.


# 6th ChatGPT

I lost the 6th prompt.


# 0.4.0

Optimize my script for clarity and efficiency. Explain what you have changed.


# 0.5.0

Update my `gallerydl-importer.yml` to have a `settings:` section that uses BOOLEAN values to turn on or off the following features:
* Exclusion of "organized" items.
* The dating feature.
* Title changes.
* Performer adding.
* URL mapping.
* The tagging feature.
Also add a dry run option here.
Do not generate the python script yet. Only provide the `gallerydl-importer.yml` with the requested changed.

The format for the settings section should be:

textsettings:
  SettingName: 
    displayName: Display name of the setting
    type: BOOLEAN



This is a plugin for the Stash app. It is meant to import metadata from Gallery-DL sidecar files into Stash app content. The plugin files (`gallerydl-importer.yml` and `importer.py`) **are attached to the project.**

Based on the settings in my `gallerydl-importer.yml`, change the `importer.py` script so that it makes use of the new settings which can be toggled from within Stash's UI on the Plugin Settings page.
Do not remove any features from the plugin. Use every setting listed in `gallerydl-importer.yml`.


**GLM-4.7 says**
The error happens because Stash stores plugin configurations as a "Map" (a dictionary of keys and values), not a list of objects. My previous query tried to look for fields like id and name inside that map, which Stash doesn't support directly in the way I wrote it.

The good news is that your script already uses client.get_configuration() further down to get your library paths. We can reuse that same function to get the plugin settings, which avoids the complex GraphQL error entirely.

Here is the fixed importer.py. I have updated get_stash_config to use client.get_configuration() and added logic to automatically find your plugin's ID in the list.
