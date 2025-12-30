Now, lets add more mappings.
**Additional Metadata Mappings:**
    - **Title:** Map JSON `id` to Stash `title`.
    - **URLs:**
        - Add JSON `file_url` to Stash `urls`.
        - The JSON `source` field contains a string with one or more URLs separated by spaces. Split this string dynamically and add every resulting URL to the Stash `urls` list.