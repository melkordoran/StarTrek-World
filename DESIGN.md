# StarTrek first release

The brief is an explorable Enterprise-D: a complete recognisable silhouette, three major interiors, normal walking and the freedom to fly around the exterior. A P100 license leaves plenty of space around a single ship without unnecessary empty-region content.

The bow points toward +Z (native north). The saucer occupies X ±232 m and Z −80..280 m; its nominal centre is [0,180,100]. The bridge sits at floor Y208, Ten Forward at Y174 near the forward rim, and engineering at Y130 in the secondary hull. The nacelles finish at Z−362. Exterior pieces are segmented into modest components to avoid a single enormous visibility/culling origin.

Interiors are separate collision geometry within the shell. Reserved hull openings keep the Ten Forward windows clear and leave actual lift entrances into each room. The ship's shell is noncolliding so it cannot create invisible barriers across interior circulation. Large opaque rooms cannot be walked through, but visitors may fly through exterior geometry; this is a deliberate first-release simplification.

The visual palette uses blue-grey hull panels, blue warp grilles, red Bussard collectors, restrained illuminated windows, warm carpet and wood, burgundy command seating, cream bulkheads and amber/lavender/blue control surfaces. The hull registry is tessellated across the saucer curve rather than floating on a flat plate.

Turbolift travel uses the native `activate teleport` action on five vertically stacked sign panels per lift bank. There is no simulated moving lift car. Engineering's upper level has both a destination and a continuous 18.75% physical ramp. Room approaches and ramps are tested against exported native triangles, not just design rectangles.

Future expansions can add the ready room, observation lounge, transporter room, sickbay, shuttle bay, crew quarters and connecting corridors after native acceptance of this foundation. Neither a functioning warp engine nor multiplayer ship controls are implied by the first release.
