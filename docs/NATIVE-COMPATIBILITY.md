# Native compatibility and deployment

StarTrek is a P100 static Axis / Active Worlds world with 294 properties, 233 declared models, three avatars, five destinations and zero terrain pages. Arrival is `8.4N 0W 20.98a 0` in the bridge's open lift vestibule.

## Formats and movement

- Generator coordinates are metres. RWX coordinates use ten-metre units; property coordinates use centimetres and orientations use tenths of a degree.
- Native positive X is west and positive Z is north. Horizontal coordinate numbers and the altitude suffix `a` represent ten metres.
- Each model ZIP contains its matching RWX at the archive root. Avatar catalogs use version 3; the three static avatars have no animation-sequence dependencies.
- Sign surfaces use tag 100, UV coordinates and a separate unprelit material. Luminous windows, engine grilles and control panels use native vertex prelighting.
- Terrain and water are disabled. Preserve `Ground=st_gravity`, `RepeatingGround=N`, and `Gravity=1`: the invisible, noncolliding helper enables walking while physical support comes from the room models.
- Exterior hull placements use `create solid off`; interior floors, bulkheads, rails and windows provide collision. Visitors can fly through the exterior shell. This is a first-release simplification, not a fully solid ship hull.
- Engineering's upper gallery connects through a real 18.75% ramp and also has a teleport destination. Other decks connect by clickable turbolift sign teleports.

## Deployment procedure

1. Inspect the target Axis version, schema, configured data directories, world registrations and P100 capacity. Resolve an existing `StarTrek` name with its owner before proceeding. Back up the state that will be affected.
2. Generate with `--object-path` set to a client-reachable URL, validate, then run `python tools/prepare_preview.py --with-objectpath-preview` (use `--generated <directory>` for nondefault output). Host `objectpath/` at that URL with normal file responses and 404 for missing assets. The included loopback URL is only a local preview default.
3. Register a fresh world through the target's supported administration flow, with matching universe/world registration credentials. Preserve existing networking/TLS settings and citizen accounts. Select an existing caretaker and review property-owner/permission mappings; the exported defaults use citizen 1.
4. Review the destination importer/schema before loading `generated/startrek-props.db`. This is a portable property payload, not a native `cell.dat`, `world.dat` or complete server installation. Never replace shared databases with it. Coordinate and iterator-packing behavior can differ between Axis builds; use a reviewed conversion if required.
5. Apply `generated/world-settings.json` separately. Importing property data alone does not install assets, avatars, settings or universe registration. There are no terrain pages to import. Default instance 0 is implicit in the inspected Axis build; do not invent an extra zero instance if the target schema represents it implicitly.
6. Verify public listing, entry, all 294 objects, the exact arrival/settings, model and avatar delivery, every sign destination and walking/ramp behavior. Confirm unrelated worlds and accounts remain unchanged.

## Validation limits

Static checks use exported native triangles and property transforms. They do not implement the browser's complete collision, rendering or sign engine. The original installation passed protocol entry and full property/settings readback, while its native graphical walkthrough remains unverified. A different server/build requires fresh acceptance.

## Destinations

| Destination | Coordinates |
| --- | --- |
| Bridge | `8.4N 0W 20.98a 0` |
| Ten Forward | `23.7N 0W 17.58a 0` |
| Engineering | `16S 0W 13.18a 0` |
| Upper Engineering | `15.35S 1.13E 13.6a 0` |
| Observation Deck | `41N 41E 22.18a 135` |
