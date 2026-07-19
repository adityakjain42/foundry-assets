# Foundry browser card library

This directory is the public source of truth for the website's Card Library and Deck Builder.

- `card_database.json` contains the current collectible Heroes, Visionaries, and Crises.
- Hero art uses `<pathname>_1.png`, `<pathname>_2.png`, and `<pathname>_3.png`.
- Visionary and Crisis art use the `path` values in the database.

After changing cards in the Foundry game repository, regenerate the browser database from the Foundry repository root:

```sh
/Applications/Godot.app/Contents/MacOS/Godot \
  --headless \
  --path "$PWD" \
  --script web/scripts/export-card-library.gd \
  -- ../foundry-assets/CardLibrary/card_database.json
```

Then sync any changed card images into this directory and push this repository. The website reads the raw GitHub file directly:

`https://raw.githubusercontent.com/adityakjain42/foundry-assets/main/CardLibrary/card_database.json`
