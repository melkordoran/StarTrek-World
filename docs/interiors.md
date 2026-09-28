# StarTrek interior layout

These are original geometric interiors inspired by the warm, legible spaces of a Galaxy-class exploration ship. They use no extracted models, film screenshots, or licensed texture files. All coordinates are metres with Y up and ship-forward along +Z.

`pipeline/interiors.py` exposes `build_interiors() -> (models, placements, metadata)` and imports the shared `aw_world.Mesh` helper. It performs no file or server writes. The parent generator supplies the stated material palette and exports the returned meshes.

## Bridge

The bridge floor is centred on **[0,208,100]**, 26 ×26 metres. Ceiling undersides are at212.8. Rounded, faceted corner bulkheads soften the footprint; a layered cream and wood ceiling cove with an amber underside light band follows the room perimeter. A flat command-circle carpet inlay surrounds a captain's chair and two companion chairs; conn and operations sit forward; two curved science/tactical console banks flank the open aft lift door. LCARS wall banks and a procedural stellar viewscreen complete the perimeter. The command seating has no raised step to trap arriving avatars.

The lift corridor is X±2.1, Z80..87 and stays at the main floor height. Its doorway is3.6m wide and3.05m high. Visitors arrive in the corridor looking forward and can reach both sides of the command area and the viewscreen by clear side aisles.

## Ten Forward

Floor **[0,174,252]**, 36 ×24m, ceiling178.4. Eight transparent forward window bays span the forward wall atZ264. A closed sill and lintel frame the windows; transparent polygons are visible from both sides. The hull must leave the supplied viewing aperture unobstructed.

The lounge has an open-ended curved bar, service cabinet and stools, three table groups, two panorama settees, and a replicator panel. The central promenade runs directly from the open aft lift to the windows. Tables and bar furniture remain off that route.

## Engineering

Floor **[0,130,-140]**, 28 ×34m, ceiling139. The illuminated core is an original ring-and-strut construction. Workstations surround it without blocking the main observation aisle. An upper port gallery and aft crosswalk stand4.2m above the main deck.

A real3.2m-wide ramp runs along starboard, from localZ11 at floor level toZ−11.4 at height4.2m: **18.75% slope**. The ramp joins the aft crosswalk without a step; the lower entry and upper mouth remain open. Handrails protect both ramp edges and all exposed balcony edges. No teleport is required to reach the upper level. An optional upper arrival is also supplied for the parent atlas or lift menu.

## Integration and validation

- Hull clearance must include each room's `bounds_min`/`bounds_max`, not only its nominal floor rectangle. Those bounds include the aft lift vestibule and ceiling thickness.
- `arrivals` contains safe eye-height positions,1.8m above their floor, with yaw0 facing ship-forward.
- `lift_buttons` provides wall-mounted sign positions, face normals, yaw and destination room IDs. Root supplies the common sign mesh and teleport actions.
- `floor_surfaces`, `floor_probes`, `walk_routes` and per-piece `obstruction_aabbs` describe walkability. Route widths target at least2m. Furniture blockers are conservative rotated bounds; structural blockers are individual wall/rail pieces, not a single whole-room box.
- Every deck/ceiling slab is closed geometry. Ceilings have actual underside faces. Doors are openings, not black painted rectangles. Ramp faces are oriented outward by a centroid check.
- Geometry is split into room deck and ceiling tiles, room bulkheads, lift corridors, and reusable furniture models. No single model spans the ship.

The three room origins are fixed integration contracts. The integrating generator is responsible for native-client acceptance, ambient lighting, material opacity/collision policy, external hull apertures, signs, and travel actions.
