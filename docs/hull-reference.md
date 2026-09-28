# StarTrek exterior: original Galaxy-inspired hull

`pipeline/hull.py` constructs original parametric meshes through the shared
`aw_world.Mesh` interface. No third-party mesh, texture or blueprint was copied.
The intended visual reference is the Enterprise-D: a broad elliptical saucer,
layered primary hull, swept dorsal neck, rounded lower engineering hull, paired
swept nacelle supports, red forward collectors and long blue warp grilles.

## Primary references

- [StarTrek.com: Designing a New Era of Technology for Encounter at Farpoint](https://www.startrek.com/en-un/news/designing-a-new-era-of-technology-for-encounter-at-farpoint)
  includes the original designers discussing the new ship, an Enterprise-D
  image and its approximately 2,108-foot length. The softly curved, broad
  silhouette and family-capable exploration setting informed this design.
- [StarTrek.com: Celebrating the Ships of the Line — USS Enterprise NCC-1701-D](https://www.startrek.com/en-un/news/celebrating-the-ships-of-the-line-uss-enterprise-ncc-1701-d)
  identifies the Galaxy-class vessel and its 42 decks, and illustrates the ship.
  The exterior retains recognizable component relationships while providing
  deliberate clearances for the three explorable rooms in this world.

These are visual and contextual references. The playable proportions, window
layout, hull panel pattern and room arrangement are original approximations,
not a claim to reproduce a licensed engineering plan exactly.

## Coordinates and integration

Bow is **+Z**; up is **+Y**. All coordinates below are metres.

| Component | Arrangement |
| --- | --- |
| Saucer | Centre `[0,180,100]`; radii X232 / Z180; shell Y157–205 |
| Bridge | Furnished room X±13, Z87–113, floor208, ceiling212.8 |
| Bridge shell | Ellipse radii20/18; sidewalls to213; cap reaches217 |
| Aft bridge lift | Clear corridor X±2.1, Z80–87, Y208–212.8 |
| Ten Forward | Clear room X±18, Z240–264, Y174–178.4 |
| Forward view | Open shell band X±24, Z239–282, Y173.7–178.65 |
| Engineering | Clear room X±14, Z−157..−123, Y130–139 |
| Engineering lift | X±2.1, Z−164..−157, Y130–139 |
| Warp nacelles | Centres X±142, Y180; aft tips Z−362 |

The continuous upper saucer skin stays above the lounge's ceiling. Only the
vertical window band is opened, so Ten Forward can look out without leaving a
large notch in the top of the ship. The bridge pod encloses the rectangular
interior and leaves its aft lift passage open. The engineering hull consists of
outer shell surfaces, with no interior cross-section caps through the room.

Every hull placement has `create solid off`; separately generated room floors
and walls provide collision. No hull code performs a database operation or
starts, stops or modifies a server.

## Mesh output

`build_hull()` returns `(models, placements, metadata)`:

- `models` maps each `st_...` model name to its Mesh.
- `placements` contains model, position, yaw, description and action.
- `metadata` includes actual bounds, triangle/vertex/model counts, maximum
  component span, room clearances, material keys and the registry decal surface.

The hull is split into radial saucer bands, azimuth sectors and lengthwise hull
segments, using local origins. No component spans more than 98 m. The complete
silhouette is approximately **642 m long, 464.3 m wide and 113 m high**; the extra
0.3 m of width comes from slightly raised window faces.

Materials used are `hull`, `hull_light`, `hull_dark`, `window`, `red`, `blue`,
`cyan`, `amber` and `black`. The shared palette controls color, texture and
emission. Fine surface seams, alternating panels, windows and phaser arcs are
geometry, keeping the silhouette independent of any external object path.

`top_saucer_y(x,z)` supplies exact profile heights for additional details. The
registry graphic should use the metadata's 5×9 vertex tessellation grid, which
follows the curved front-upper surface with a small clearance. Each grid cell
is ordered `[j,i], [j,i+1], [j+1,i+1], [j+1,i]`, facing upward. A separate, lifted
single-quad alternative and UV coordinates are included for simple previews.

## Validation performed

- Built through the actual shared Mesh implementation.
- Checked all vertex values, UV lengths, triangle indices and nonzero areas.
- Checked exterior triangle intersections against the room and lift clearance
  boxes using a triangle/AABB separating-axis test.
- Rendered front-quarter, top and side views for visual inspection. This caught
  and corrected collector-tip winding and an unnecessarily tall lounge cutout.
- Verified the final overall bounds and bounded component dimensions.

These checks validate the generated geometry. Native-client arrival, room
movement, streamed loading and final palette appearance belong to the parent
world integration and acceptance run.
