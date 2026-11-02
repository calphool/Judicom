"""
Judicom 2.0 - parametric FreeCAD model, split into bolt-together printable parts
================================================================================

Run it from FreeCAD:  Macro > Macros... > Create (paste this) > Execute
or headless:          freecadcmd judicom_freecad.py

Coordinates:  X = width (left -> right), Y = depth (front -> back), Z = up.
Origin is the front-left-bottom corner of the assembled body.  Units are mm.

PARTS (each one is exported as its own STL, already laid flat and ready to slice)
---------------------------------------------------------------------------------
  Panel         the sloped front face: 87 x 154 screen window, two 27 x 27 button
                holes, the Merlin cradle pocket + collar + seat tabs, and the two
                long screen mounting strips.  Prints face-down.
  SideLeft      triangular side wall, 3 bottom-plate bosses, and the PHONE-CORD JACK
                port: a 12.4 x 16.4 window for the jack's front lip, flush with the
                outside, plus a tunnel behind it for the 22 mm tall body and two bosses
                for the retaining cap.  The latch slot of the jack is UP.
  PhoneJackCap  the small plate that closes the back of that tunnel (2 screws).  Its
                pressure pad squeezes the jack against the wall so it is held firmly;
                the bottom of the jack's rear face is left open for the wires.
  SideRight     triangular side wall, speaker grille + four speaker standoffs on a
                42 mm square, 3 bottom-plate bosses.
  Back          back wall, with the DC barrel-jack hole and a tunnel on the inside
                that holds the jack (one clamp screw makes it tight; undo to remove).
  BottomPlate   Raspberry Pi standoffs, vents, feet recesses, cable slot, and the
                short front wall as an upturned lip.
  ButtonSlider x2, ButtonAnchor_Frank / _Ann, ButtonFrame_Frank / _Ann
                the printed parts that turn YOUR arcade buttons into short-throw buttons (see THE BUTTONS).
  DCJackFitTest     a small slice of the back wall around the DC-jack tunnel - print
                this first (about 20 minutes) to check the jack fits before printing Back.
  PhoneJackFitTest  the same idea for the phone jack: a slice of the left wall around
                the window and tunnel.  Print it with PhoneJackCap and try the real jack.
  HangupAdapter holder for the BIS-10 hook switch, with two flaps that clamp to the Panel's cradle collar (see THE HANG-UP SWITCH).
  HookSwitchInsert_x3  three small inserts (slab pad 0.3 mm thinner / nominal / 0.3 mm thicker) that go under the switch in the holder so it cannot rock.
  REF_*         grey ghost blocks (screen module, cradle, speaker, DC jack, phone jack,
                the two BLEE microswitches, the hook switch) - reference only.

HOW IT GOES TOGETHER  (33 heat-set brass inserts, 27 x M3 x 8 + 6 x M3 x 6 machine screws)
-------------------------------------------------------------------------------------
Every screwed joint is a 4 x 4 mm brass insert melted into a 3.8 mm hole that is 5.5 mm deep
(INSERT_* parameters).  The hole is 1.5 mm deeper than the insert, so the plastic the hot insert
pushes aside collects under it and never reaches the threads.  Push each insert in flush with the
face of its block; the screw then passes through a plain 3.4 mm hole in the part it fastens.

Every block that holds an insert is a TRAPEZOID, not a round post: wide where it joins its parent
surface, narrowing to 8.8 mm at the free edge (2.5 mm of plastic around every hole).  A long base
spreads the tightening torque over a large area, so the block cannot twist off the wall.

  8  side walls -> panel      4 per side: M3 x 8 flat head from the OUTSIDE of the side wall into
                              trapezoid lugs on the panel's underside (20 mm wide at the panel)
  4  back wall  -> panel      M3 x 8 from the OUTSIDE of the back wall into trapezoid lugs on
                              the panel's underside
  4  side walls -> back wall  2 per side, M3 x 8 from the outside into trapezoid lugs on the back wall
  6  bottom plate -> sides    M3 x 8 flat head from underneath into trapezoid bosses on the side
                              walls (18 mm wide at the wall, the insert opens on the bottom face)
  4  bottom plate -> back wall  the same kind of boss along the bottom edge of the back wall
                              (x = 30, 60, 170, 200 - clear of the cable slot and the DC-jack tower),
                              so the back wall is held at the bottom as well as at the top and sides
The front lip on the bottom plate is captured between the plate and the panel, so it needs no
screws.  Every through hole is countersunk on the outside.
Extra hardware that is not part of those 26:
  4  inserts + M3 x 6 pan head   speaker -> its four trapezoid standoffs (the speaker's own ear holes;
                                 the insert hole runs 1.5 mm into the wall, leaving a 1.5 mm skin outside)
  1  insert + M3 x 8             clamp screw on top of the DC jack tunnel (top wall is 6.5 mm thick:
                                 insert + relief + a 1 mm ring with a 3.4 mm passage for the screw tip)
  2  inserts + M3 x 6 flat head  PhoneJackCap -> its two trapezoid bosses
Not on inserts (on purpose):
  * Raspberry Pi standoffs: the Pi's holes are M2.5, so the four standoffs keep a 2.2 mm self-tapping
    pilot (M2.5 x 6).  They are trapezoids too.
  * The 4 cradle seat tabs (3 mm thick - far too thin for a 4 mm insert) just carry a 3.4 mm clearance
    hole for an M3 screw from below.  They are placeholders until I know how the Merlin cradle fastens.

THE BUTTONS  (built on your own arcade buttons; Panel and BottomPlate untouched)
------------------------------------------------------------------------------
Kept from each original button: black housing (lip, square collar, front pocket), the 34 x 8 mounting
nut, the white plunger HEAD with its clear snap-on cover, frosted insert and photo, and the BLEE switch.
The long part - 29 mm of barrel, 23 mm plunger legs and the 22 mm spring - is replaced by printed parts:
  ButtonSlider (print 2)       spigot (10.9 mm, pressed and glued into the 11 mm hole of the cut plunger), a 19 mm
                               guide that slides in the barrel from behind, and a 26 mm flange that stays BEHIND the
                               barrel's cut end.  At rest the flange touches that end, so the plunger cannot be pulled out;
                               pressing moves it 3.0 mm and it pushes the switch plunger.
  ButtonAnchor_Frank / _Ann    (print one each - mirror images)  "A" in the drawings: a 2.5 mm ring that the mounting nut
                               clamps against the panel - no glue, no friction grip - joined to a 6 mm plate that runs down
                               beside the nut, toward the screen.  The plate has two vertical slots (+-1 mm); behind each
                               is a pocket for an M3 nut.  A small block at its +u end (-u for Ann) locates the frame.
  ButtonAnchorNarrow_Frank / _Ann   ONLY for the one button that sits next to the HDMI plug (print one, instead of that button's
                               normal anchor).  The same anchor with the plate cut back to 18 mm (BT_NARROW_W), measured from the
                               plunger end; the ring under the nut is untouched.  Its far end - and so the nut for the FAR screw -
                               is gone: hold the switch with the near screw and nut, and put a short M3 (about 12 mm, hot-glued or
                               just a snug fit) in the far hole, or leave it empty.  The frame is the same for both buttons.
                               In the macro: BT_NARROW_SIDE = "Frank" or "Ann" puts it on that button in the model and in its
                               ButtonAnchor_<side>.stl.  Left at None, the normal anchors are used, the two ButtonAnchorNarrow_*.stl
                               are still written, and the model holds them hidden as ALT_ButtonAnchorNarrow_* (tick them on to look).
  ButtonFrame_Frank / _Ann     (print one each - mirror images)  "B": an end wall (the hard stop, exactly 3.0 mm below the
                               flange) and two walls that hold the BLEE switch by its own two 3.4 mm holes.  The switch is
                               put in it, and the whole frame is lowered from behind onto the anchor plate.
  The switch plunger sits on the button axis, 10 mm toward the screen; the terminals point away from the other button.
  Return force: the switch's own spring only (you judged it as firm as the original spring).
  1. CUT THE BARREL so it ends 15 mm behind the back face of the lip (BT_STUB_END).  Sand the cut square: the flange rests on it.
  2. CUT THE PLUNGER (legs and body) so only 5 mm of its round collar is left under the head (PL_RING_KEEP).
  3. Housing into the panel from the front.  Anchor ring over the barrel from behind (plate toward the screen), up
     against the panel; then the mounting nut from behind: the nut clamps the ring.  Hold the anchor by its plate while
     you turn the nut, and only snug it up: the ring needs no more than that.
  4. Plunger (cover, frosted insert and photo on the head) into the housing from the front.  Slider from behind: its
     guide goes up the barrel and its spigot pushes into the plunger's hole (a dot of glue).  The flange stays outside.
  5. Switch into the frame (its two holes on the frame's holes), then bring the frame straight up from behind (the
     Panel lying face down on the bench) next to the anchor plate until its +u end (-u for Ann) meets the locating
     block.  The end wall goes under the flange.  (Sliding it in sideways does not work for Frank: the cradle rim of the
     Panel is in the way after 27 mm, so both buttons use this straight-on route.)
  6. Two M3 x 25 pan-head screws from the outside of the frame (from the bottom edge of the Panel, BEFORE the bottom
     plate is fitted), through the frame, the switch and the slots of the plate, a nut in each pocket.  Before tightening, slide the frame up or down in the slots until the switch plunger just
     touches the flange at rest (about 0.1 mm), then tighten.  The slots allow +-1 mm.
  Travel: 3.0 mm.  The flange sits 0.1 mm above the switch plunger at rest and presses it 2.9 of its 3.0 mm at the
  stop, which leaves 0.1 mm to the switch body.  If your switch needs less than 2.9 mm to click, nothing to do; if it
  does not click, tell me where it does (BT_GAP / BT_TRAVEL set this).
  Hardware for both buttons: 4 x M3 x 25 pan-head screws + 4 M3 nuts (no brass inserts - 33 in the whole Judicom).
  With M3 x 20 screws set BT_SCREW_L = 20: it works, but the web behind each nut gets thin (the macro prints it).
  Tuning the height: how far the cover stands above the lip face depends on the cut length of the barrel.  The
  cover now stands about 1 mm proud of the lip face (head 4 + cover 5 on a head that rests 4 mm behind the lip); if yours
  is higher or lower, trim the barrel by 0.5 mm steps (shorter = higher) - the end wall and switch then move with the slots; trim more than 1 mm and the slots run out.
  The mounting nut (behind the 2.5 mm ring) ends 0.5 mm above the cut end of the barrel: do not cut the stub shorter
  than 14.5 mm, or the nut sticks out past it and the flange rests on the nut instead of the barrel.
  ASSUMED (please check on the real parts): the head's underside rests 4 mm below the back face of the lip
  (PL_HEAD_BOT; the slider is 12.5 mm tall - it was 14.5 mm and you found it 2 mm too tall), the housing front pocket is about 25.5 mm square with its floor 3 mm below that, the plunger collar
  is 18 mm and the hole 11 mm (your numbers).  The ghosts of the housing, nut and plunger (REF_Housing, REF_Nut,
  REF_Plunger) are drawn from your numbers, not scanned.  REF_Screws shows the screws and nuts.

THE HANG-UP SWITCH  (adapter for the BIS-10 hook switch; Panel and BottomPlate untouched)
------------------------------------------------------------------------------
The switch (37 x 29 x 14 mm, pins on the thin face, spring lever with a 4 mm wide shaft and an 11 mm finger) hangs behind the
cradle with its lever finger resting on the cradle's white actuator, about 11 mm of the body sticking out past the cradle's
module-side wall.  Everything is placed from the ACTUATOR (HU_* settings): the switch top edge is 53 mm from the cradle's top edge.
  HangupAdapter (print 1)   a holder: four walls and two floor rails grip the body (0.3 mm clearance plus four tiny crush ribs); the
                            front (pin face) is open, so pins, wires and the lever stay free; the end wall has an opening for the
                            lever shaft, the opposite end wall has a window (7 x 6.5 mm, HU_PLUNGER_*) for the switch's plunger, which
                            pushes out when the lever moves; the floor is open in the middle for the two alignment knobs.  Above and below the holder a
                            3 mm plate reaches out to a 4.5 mm flap that lies against the OUTSIDE of the collar wall (the 2.4 mm wall
                            of the Panel around the cradle opening, module side).  Each flap has a 3.4 mm hole and a hexagonal pocket
                            for an M3 nut on its outer face.  The plates butt against the END FACE of the collar wall: that is the
                            depth stop.
  HookSwitchInsert_x3 (print 3, try one)   the rear face of the switch is stepped (14 mm at the lever end, about 10.5 mm over the slab along the
                            top edge, 7.5 mm over the cover-plate strip, 5 mm base), so on the flat floor it rested only on the lever-end block and rocked.
                            The insert lies on the two floor rails: a pad under the slab (about 2.6 mm thick) and a pad under the strip (about 6.6 mm, 5 mm wide),
                            tied together by a 1.6 mm spine along the module-side end.  Three are printed because the slab height is estimated
                            from your photos (your first print: the slab pad was 1 mm too thick, the strip pad too narrow): slab pad -0.3 / nominal / +0.3 mm (HU_INS_VARIANTS; one, two or three small grooves across the spine tell them apart).
                            The one that stops the rocking is the right one;
                            if it is between two, set HU_SLAB_H / HU_STRIP_H to your caliper readings (rear face to pin face, over the slab and over
                            the strip) and the macro redraws everything.
  The pin face sits at w = -22: 4 mm behind the cradle's back edge (-18) and 1 mm behind the end of the collar (-21).  The actuator
  moves, so those few mm make no difference (you said), and the switch body stays clear of the collar.  HU_PIN_W sets it.
  Hardware: 2 x M3 x 10 pan head + 2 M3 nuts.  No inserts.
  1. Solder the wires to the switch pins first (the pin face is hidden once the adapter is on).
  2. Insert into the holder first (pads up, it lies on the two rails), then the switch from the front (pin face toward you), lever out
     through the opening, rear face down onto the pads; the ribs hold it.
  3. A nut into each hexagonal pocket (press it in flush).
  4. Panel face down on the bench, cradle in it.  Bring the adapter straight up from behind, module side, until both plates touch the
     end of the collar wall; the flaps now lie against the outside of the collar wall.
  5. Through each 3.4 mm flap hole drill a 3.4 mm hole through the collar wall AND the cradle's own wall (the flap is the guide).  The screen
     strip is only 2.4 mm away from the flap, so use a pin vise or a bit with 25 mm showing.  Take the nut out, or do it before step 3.
  6. M3 x 10 from INSIDE the cradle (head on the cradle's inner face, 14 mm up from its back edge), through the cradle wall and the collar wall
     and the flap, into the nut.  Snug, no more.
  ASSUMED (please check): cradle walls 2 mm; the cradle is 69 x 220 x 18 as you measured (your photo outlines it at 74 x 224 - if the
  collar does not hug it as drawn, the flap distances change); lever shaft 2 mm thick at the pin-face level; finger tip 5 mm in front of
  the pin face; nothing else (posts, bulges) inside the cradle at the two screw heads (46 mm and 89 mm from the cradle's top edge).

Things I could NOT take from your drawings - please check them:
  * Inserts: I took them as 4.0 mm outside diameter x 4.0 mm long (your numbers) and made the holes
    3.8 mm (0.2 mm under the OD so the knurls bite) and 5.5 mm deep.  If yours go in too hard or too
    loose, change INSERT_HOLE_D in 0.1 mm steps; INSERT_RELIEF sets the extra depth.
  * Button switch: from your photo (27 x 15.9 x 10.3, holes 22.2 x 10.3 apart, 3 x 3 plunger 5.5 mm from
    the edge).  The terminal tabs are modelled as 6.5 mm stubs; leave room on the open (outer) end for the connectors.
  * The ear-hole spacing (SCR_HOLE_SPAN_*) was scaled off your dimension drawing,
    good to about +-1 mm.  The strips are wide enough to forgive that.
  * Cradle mounting: I still don't know how the Merlin cradle fastens down.  The 4
    corner tabs are placeholders - see CRADLE_SCREW_INSET.
  * Body size: to keep the sloped panel under 250 mm long (so it prints flat on a
    256 mm bed) the slope is 35 degrees and 248 mm long, which makes the body
    230 wide x ~203 deep x ~160 tall.  The cradle needs this much length; a
    steeper slope will not fit it.  Change SLOPE_LEN / SLOPE_ANGLE to experiment -
    the report at the end warns you if something stops fitting.
  * Under the cradle: your photos show posts hanging about 19 mm below it and cup
    bulges of about 6 mm.  The pocket is open to the inside of the box, and there is
    more than 20 mm of room underneath everywhere except the front ~15 mm of the
    pocket (about 8 mm of room at the very front edge) - keep hardware out of there.

  * Speaker: the 42 mm hole spacing is from you; the frame size (52 mm square), magnet
    (42 mm) and depth (18 mm) are estimated from the photo and are used only for the grey
    ghost and the keep-out checks.  Standoffs are 4 mm tall and take M3 inserts, so the speaker's
    ear holes must pass an M3 screw - if they are M2.5, tell me.  Speaker wires are not routed.
  * DC jack: dimensions are from your photos.  The labels said the body is 13 mm wide
    near the terminals but the end-on photo measures 14, so JACK_BODY_W = 14 (set 13 if
    your calipers say so).  The jack slides in from inside, barrel first, until its shoulder
    stops; the metal ring ends flush with the outside.  DCJackFitTest.stl is a small slice
    of the back wall with the same tunnel - print that first.
  * Phone-cord jack: read from your three photos.  I took it to be a modular jack 12 mm
    wide x 22 mm tall with a 16 mm tall, ~3 mm deep front lip (top-aligned) that passes
    through the wall, and a ~13 x 22 x 9 mm body behind it with the wires leaving the lower
    rear.  If the lip turns out to be the full 22 mm tall, set RJ_NOSE_H = 22 - but then
    there is no shoulder to stop it being pulled outwards (only the pad's friction does),
    so tell me and I will add a stop.  RJ_Y / RJ_Z0 place it: it is 105 mm from the front and 20 mm
    up, which keeps it 10 mm under the cradle collar and clear of the plate bosses.
    PhoneJackFitTest.stl + PhoneJackCap.stl let you check all of this in about 30 minutes
    (the fit-test slice has the cap's two trapezoid bosses - press the two inserts in as well).
    If the jack has a little play, raise RJ_PRELOAD (pad squeeze) in 0.1 mm steps.

Tested headless in FreeCAD 26.3: every part is one valid solid, no two parts overlap, all 32 blind
insert holes are 3.8 mm x 5.5 mm with at least 2.5 mm of plastic around them and line up with their
3.4 mm through-holes, a 4 x 4 mm insert is surrounded by plastic along its whole length in every hole,
the speaker, DC jack and phone jack ghosts clear every other part (and both jacks seat in their
holders with zero interference), no round post is left, the STLs are watertight, and every part
fits within 250 x 250 mm.  Everything except the buttons is byte-identical to v6 (Panel and BottomPlate
unchanged).  The buttons were also swept through every assembly step in 3-D (anchor, nut, plunger, slider,
frame + switch, screws, nuts, screwdriver access) with the Panel as the only obstacle, at all three slot
positions, and the cap travel / hard stop / switch gap were measured (3.00 mm, 0.10 mm, 0.10 mm).
"""
import math
import os

import FreeCAD as App
import Part

V = App.Vector

# =============================================================================
# PARAMETERS (mm)
# =============================================================================
# --- body envelope -----------------------------------------------------------
W = 230.0            # width  (X)
SLOPE_LEN = 248.0    # length of the sloped face (the panel's long edge) - keep <= ~250
SLOPE_ANGLE = 35.0   # slope angle above horizontal, degrees
FRONT_H = 18.0       # height of the short vertical front face where the slope starts
EDGE_R = 5.0         # rounding on the outside edges (bottom edges stay sharp)
WALL = 3.0           # side / front / back wall
SLOPE_WALL = 4.0     # thickness of the sloped face
PLATE_T = 3.0        # bottom plate thickness

# --- heat-set brass inserts (M3) - every screwed joint uses one ------------------
INSERT_OD = 4.0                  # outside diameter of the brass insert (nominal)
INSERT_L = 4.0                   # length of the insert
INSERT_HOLE_D = 3.8              # hole in the plastic: a little under the OD so the knurls bite
INSERT_RELIEF = 1.5              # hole is this much deeper than the insert, so the plastic the
                                 # hot insert displaces never reaches its threads
INSERT_DEPTH = INSERT_L + INSERT_RELIEF     # = 5.5 mm blind hole
INSERT_WALL = 2.5                # minimum plastic around the hole (side and end)
BLOCK_TOP_W = INSERT_HOLE_D + 2 * INSERT_WALL    # 8.8 - the narrow edge of every trapezoid block
BLOCK_HALF = BLOCK_TOP_W / 2.0                   # hole centre -> narrow edge

# --- print bed ----------------------------------------------------------------
BED_X, BED_Y, BED_Z = 256.0, 256.0, 256.0    # Elegoo Centauri Carbon
BED_LIMIT = 250.0                            # the parts are kept at or under this

# --- Merlin BIS-10 handset cradle (measured by you) --------------------------
CRADLE_W = 69.0
CRADLE_L = 220.0
CRADLE_T = 18.0
CRADLE_CLEAR = 0.6   # total slack added to both CRADLE_W and CRADLE_L
COLLAR_WALL = 2.4    # wall of the rectangular collar that holds the cradle
TAB_T = 3.0          # thickness of the 4 corner tabs the cradle sits on
TAB_SIZE = 12.0      # tab footprint (square) - keep under ~14 so it clears the cup bulges
CRADLE_SCREW_INSET = 6.0   # screw-hole centre, measured in from the pocket edges
CRADLE_SCREW_D = 3.4       # M3 clearance hole through the tabs (placeholder - the tabs are only
                           # 3 mm thick, too thin for an insert; see the note in the docstring)

# --- 7" HDMI screen module, mounted PORTRAIT (from your dimension drawing) ----
SCR_MOD_L = 165.0          # module length (runs up the slope)
SCR_MOD_W = 107.0          # board width WITHOUT the mounting ears (runs across)
SCR_MOD_T = 7.5            # module thickness
SCR_HOLE_SPAN_W = 116.0    # ear-hole spacing across the module
SCR_HOLE_SPAN_L = 156.0    # ear-hole spacing along the module
WIN_W = 87.0               # window through the front wall, across
WIN_L = 154.0              # window through the front wall, along the slope

# mounting strips (two, one each side of the module, running up the slope)
STRIP_W = 10.0             # width of each strip
STRIP_DEPTH = 7.0          # how far each strip stands off the inside of the wall
STRIP_CLEAR = 0.5          # gap between the module's side edge and the strip
STRIP_EXTRA = 9.0          # strip extends this far past each end of the module

# reference ghost of the module (used only for the SHOW_REFERENCE blocks)
EAR_W, EAR_L, EAR_T = 9.0, 8.5, 1.6
EAR_HOLE_D = 3.2

# --- photo buttons ------------------------------------------------------------
BTN_HOLE_W, BTN_HOLE_L = 27.0, 27.0   # square holes in the front wall
BTN_GAP = 10.0                 # between the two button holes
BTN_FRONT_MARGIN = 12.0        # front edge of slope -> button hole
BTN_SCREEN_GAP = 20.0          # top of button hole -> bottom of screen window
PHOTO_W, PHOTO_L, PHOTO_DEPTH = 21.0, 21.0, 0.8   # photo / name-card recess in the cap

# --- short-throw photo buttons built on YOUR arcade-button parts (nothing here touches the Panel or plate) ---
# Button-local axes: x = u (across the slope), y = v (up the slope, toward the screen), z = w (out of the panel face).
# w = 0 is the OUTSIDE face of the panel (= back face of the housing's lip), w = -4 its inside face; origin = hole centre.
BT_LIP_W, BT_LIP_T = 33.0, 4.0            # black housing: lip
BT_COLLAR_W, BT_COLLAR_T = 27.0, 3.0      #   square collar that sits in the panel hole
BT_BARREL_OD, BT_BARREL_ID = 23.0, 19.5   #   threaded barrel (cut down to a stub)
BT_NUT_D, BT_NUT_T = 34.0, 8.0            # the mounting nut that came with the button
BT_STUB_END = 15.0                        # CUT the barrel here: 15 mm behind the back face of the lip
PL_HEAD_W, PL_HEAD_T = 22.0, 4.0          # white plunger head (keeps the clear cover, insert and photo)
PL_RING_D, PL_HOLE_D = 18.0, 11.0         #   its round collar and the hole through it
PL_HEAD_BOT = -4.0                        #   rest position of the head's underside.  The slider's middle section (the guide)
                                          #   is as long as PL_HEAD_BOT - PL_RING_KEEP - W_STUB below: -4 gives a 12.5 mm slider
                                          #   (-2 was the first, 14.5 mm one: 2 mm too tall on your parts)
PL_RING_KEEP = 5.0                        #   CUT the plunger so 5 mm of its round collar is left under the head
BT_TRAVEL = 3.0                           # cap travel = original button travel
BT_GAP = 0.1                              # gap between the flange and the switch plunger at rest
BT_SPIGOT_D = 10.9                        # slider spigot pressed into the 11 mm hole
BT_GUIDE_D = 19.0                         # slider guide in the 19.5 mm bore
BT_FLANGE_D, BT_FLANGE_T = 26.0, 1.5      # slider flange: rests on the barrel's cut end, pushes the switch plunger
BT_RING_T = 2.5                           # anchor ring, clamped between the panel and the mounting nut (was 1.5 and broke;
                                          #   3.0 is the most that fits: the nut would then end flush with a 15 mm barrel stub)
BT_RING_ID = 24.6                         # its hole (barrel OD 23 + 1.6, the 1.5 mm ring's 0.6 was too tight)
BT_END_T = 2.5                            # frame end wall (the hard stop for the flange)
BT_THIN_T, BT_INNER_T = 2.8, 2.4          # frame: outer and inner switch walls
BT_SW_CLEAR = 0.15                        # slack between the switch and each frame wall (the screws clamp it)
BT_SLIDE_GAP = 0.25                       # slack between the frame's inner wall and the anchor plate
BT_PLATE_T = 6.0                          # anchor plate thickness
BT_FRAME_FRONT_V = -14.5                  # the frame's end wall reaches this far toward the front edge (under the flange)
BT_SIDE_RIM = 2.5                         # frame walls extend this far beyond the switch ends
BT_STOP_W = 2.5                           # width of the little block on the anchor that locates the frame
BT_PIN_V = 10.0                           # switch plunger sits 10 mm toward the screen (more room behind the panel)
BT_SW_CU = -8.0                           # switch centre: plunger is 8 mm from its edge, so it lands on the axis
BT_SCREW_L = 25.0                         # M3 pan-head screws through frame + switch + anchor plate (20 also works,
                                          #   but leaves a thinner web behind the nut)
BT_SCREW_HEAD_D, BT_SCREW_HEAD_H = 5.6, 2.0
BT_NUT3_AF, BT_NUT3_H = 5.5, 2.4          # M3 nut: across flats, thickness
BT_NARROW_W = 18.0                        # plate width of the NARROW anchors (ButtonAnchorNarrow_*): for the button next to the HDMI plug
BT_NARROW_SIDE = None                     # "Frank" or "Ann": the button next to the HDMI plug gets the narrow anchor in the model AND in
                                          #   its ButtonAnchor_<side>.stl.  None: both buttons get the normal anchor (the two ButtonAnchorNarrow_*
                                          #   files are exported either way, and shown hidden in the model as ALT_ButtonAnchorNarrow_*)
BT_SLOT = 1.0                             # +- tuning travel of the frame along the press axis (slots in the anchor plate)

# --- speaker on the right side wall: 4 standoffs on a square + grille ---------
SPK_Y, SPK_Z = 135.0, 45.0     # centre of the speaker: depth from the front, height
SPK_HOLE_SPACING = 42.0        # ear-hole spacing (square pattern), from your photo
SPK_POST_H = 4.0               # standoff height = gap between wall and speaker front
SPK_BLOCK_BASE_W = 16.0        # trapezoid standoff: wide edge (along y), pointing away from the speaker
SPK_BLOCK_LEN = 12.0           # wide edge -> narrow edge (along z); the insert sits near the narrow edge
SPK_FRAME = 52.0               # speaker frame, square   (estimated from the photo)
SPK_MAGNET_D = 42.0            # magnet diameter         (estimated from the photo)
SPK_DEPTH = 18.0               # ear plane -> back of magnet (estimated; keep-out only)
GRILLE_R, GRILLE_HOLE, GRILLE_PITCH = 19.5, 3.0, 5.5

# --- DC barrel-jack adapter (female jack + green screw terminals), back wall --
JACK_X, JACK_Z = 40.0, 40.0    # centre of the jack on the back wall (x across, z up)
JACK_BARREL_D = 10.0           # round barrel the plug goes into
JACK_BORE_D = 10.4             # hole through the wall for that barrel
JACK_BARREL_L = 8.0            # black barrel length
JACK_RING = 2.0                # metal ring that sticks out beyond the barrel
JACK_TIP_OUT = 0.0             # ring tip relative to the outside of the wall (0 = flush)
JACK_SQ_W = 11.0               # body width where it starts, behind the barrel
JACK_SQ_L = 3.5                # that straight 11 mm section
JACK_TAPER_L = 11.0            # ribbed section that widens
JACK_BODY_W = 14.0             # body width at the rear (your photos say 13 and 14)
JACK_BODY_T = 12.0             # body thickness (the face with the + / - marks to the back)
JACK_CLEAR = 0.3               # slack per side in the tunnel
JACK_TUNNEL_L = 18.0           # how much of the body the tunnel wraps (the rest + green stays free)
JACK_SIDE_WALL, JACK_FLOOR = 2.5, 2.5   # tunnel wall thicknesses
JACK_TOP = INSERT_DEPTH + 1.0   # top wall: room for the clamp insert + its relief + a 1 mm ring (6.5)
JACK_CLAMP_AT = 12.0           # clamp screw position, measured back from the shoulder

# --- phone-cord jack (modular jack with 4 pigtail wires), LEFT wall ------------
# The plug goes in from outside the left wall.  The jack's 16 mm tall front lip goes
# through a window in the wall (flush with the outside); its taller body sits in a tunnel
# on the inside.  The shoulder of the body rests on the wall (stops it being pulled out)
# and a screw-on cap behind it stops it being pushed in.  Latch slot of the jack is UP.
RJ_Y, RJ_Z0 = 105.0, 20.0      # centre of the jack along the wall (y); height of the BOTTOM of its body (z)
RJ_W = 12.0                    # width of the front lip (across the wall)
RJ_NOSE_H = 16.0               # height of the front lip (top-aligned with the body)
RJ_NOSE_L = 3.0                # depth of the front lip (3.0 = the wall thickness -> flush)
RJ_BODY_W = 13.0               # width of the body behind the lip  (photos say 12 - 13)
RJ_H = 22.0                    # overall height of the body
RJ_BODY_L = 9.0                # depth of the full-height body behind the lip
RJ_CLEAR = 0.2                 # slack per side
RJ_SIDE_WALL, RJ_FLOOR, RJ_TOP = 2.5, 2.5, 2.5   # tunnel wall thicknesses
RJ_WIRE_H = 9.0                # bottom of the jack's rear face left open for the wires
RJ_CAP_STAND = 0.5             # gap between the jack's rear face and the cap plate (tolerance)
RJ_PRELOAD = 0.2               # how far the cap's pressure pad squeezes the jack (0 = just touching)
RJ_CAP_T = 2.5                 # cap plate thickness
RJ_SCREW_DY = 12.0             # the 2 cap screws sit this far either side of the jack centre
RJ_BOSS_Y0 = 8.7               # trapezoid boss: wide edge, this far from the jack centre (inside the tunnel wall)
RJ_BOSS_Y1 = RJ_SCREW_DY + BLOCK_HALF   # ... narrow edge (insert centre + 4.4)
RJ_BOSS_BASE_H = 15.0          # height (z) of the wide edge of each cap boss
RJ_PAD_W, RJ_PAD_H = 10.0, 8.0         # pressure pad on the cap

# --- bottom plate / Raspberry Pi 3B+ -----------------------------------------
BOSS_BASE_W = 18.0             # plate bosses on the side walls: trapezoid, wide edge on the wall (along y)
BOSS_XC = 2.2                  # insert centre, measured from the inside face of the side wall
                               # (small enough that the front bosses clear the cradle collar by 0.6 mm)
BOSS_H = 10.0                  # boss height (the insert hole opens on its bottom face)
BACK_BOSS_X = [30.0, 60.0, 170.0, 200.0]   # x of the 4 bosses along the bottom of the back wall
                               # (kept clear of the plate's cable slot, x 70..160, and of the DC-jack tower)
SCREW_HOLE_D, SCREW_HEAD_D = 3.4, 6.4           # plate screw holes (countersunk)
PI_L, PI_W = 85.0, 56.0
PI_HOLE_DX, PI_HOLE_DY, PI_HOLE_OFF = 58.0, 49.0, 3.5
# Pi standoffs: trapezoid, narrow edge towards the board, wide edge outboard.  The Pi's holes
# are M2.5 so these keep their small self-tapping pilot (NOT an M3 insert).
PI_STANDOFF_H, PI_PILOT_D = 6.0, 2.2
PI_BLOCK_TOP_W, PI_BLOCK_BASE_W, PI_BLOCK_LEN, PI_BLOCK_IN = 6.4, 12.0, 12.5, 3.2
PI_BACK_GAP = 24.0   # Pi back edge to inside of back wall
FOOT_D, FOOT_DEPTH, FOOT_INSET = 14.0, 1.5, 24.0
VENT_SLOT_W, VENT_SLOT_L, VENT_PITCH, VENT_COUNT, VENT_Y = 2.5, 30.0, 6.0, 8, 50.0
CABLE_SLOT_W, CABLE_SLOT_L = 90.0, 11.0

# --- screw joints between the printed parts ----------------------------------
SCREW_CLEAR_D = 3.4        # clearance hole in the wall the screw passes through
SCREW_CSK_D = 6.4          # countersink diameter on the outside
LUG_BASE_W = 20.0          # lugs are trapezoids: this wide where they join the panel / back wall ...
                           # ... narrowing to BLOCK_TOP_W at the free edge
LUG_DEPTH = 9.0            # how far side lugs stand off the panel's underside
SIDE_SCREWS = 4            # screws per side wall into the panel
PANEL_BACK_X = [40.0, 110.0, 150.0, 190.0]   # x of the 4 back-wall -> panel screws
BACK_LUG_Y = 9.0           # how far the back-wall lugs on the panel stand forward
BACK_LUG_DROP = 12.0       # lug height below the panel's underside at the back wall
BACK_SIDE_Z = [30.0, 80.0]  # heights of the side wall -> back wall screws
BACK_LUG_W = 8.5           # thickness of the lugs on the back wall (insert is 5.5 deep -> 3 mm left)

# --- hang-up switch adapter (the BIS-10 hook switch that the cradle's white actuator presses) -------------------------
# Measured from the ACTUATOR, because that is what the switch lever must line up with (all taken from your photos):
#   m = distance from the cradle's centre line toward the screen module (the switch body hangs out this way)
#   y = distance down from the top edge of the cradle (the 224 mm outline in your photo)
#   w = depth: 0 = outside of the panel, -4 = inside, the cradle's back edge is -18, the Panel's cradle collar ends at -21
HU_ENABLE = True
HU_SW_L, HU_SW_H, HU_SW_T = 37.0, 29.0, 14.0    # switch body: along m, along y, thickness (pins are on the thin face)
HU_SW_M0 = 10.0            # lever-side end of the body, from the cradle's centre line (your photo: 27 mm from the cradle's edge)
HU_SW_Y0 = 53.0            # top edge of the body, from the cradle's top edge
HU_PIN_W = -22.0           # w of the switch's pin face.  The cradle's back edge is -18 and the actuator moves, so a few mm
                           # behind it make no difference; -22 also keeps the pins (1-2 mm proud) clear of the collar's end (-21)
HU_SHAFT_Y = (65.5, 69.5)  # the lever's shaft: 4 mm wide ...
HU_SHAFT_T = 2.0           # ... 2 mm thick, in front of the pin face
HU_FINGER_Y = (65.5, 76.5) # the finger at its end: 11 mm long ...
HU_FINGER_M = (-2.0, 2.0)  # ... 4 mm wide, centred on the actuator
HU_FINGER_DROP = 5.0       # its tip is this far in front of the pin face
HU_CLEAR = 0.3             # gap around the switch body in the holder
HU_WALL = 2.0              # holder walls
HU_FLOOR_T = 2.4           # holder floor (two rails, the middle is open for the two alignment knobs)
HU_RAIL = 8.0              # width of each floor rail, from the long edges of the body
HU_RIB = 0.45              # four crush ribs inside the holder (0.15 mm net interference with HU_CLEAR = 0.3)
HU_SLOT_Y = (63.0, 72.0)   # opening in the end wall for the lever shaft
HU_PLUNGER_Y = (53.2, 60.0)    # window in the module-side end wall for the switch's plunger, which pushes out when the lever moves:
HU_PLUNGER_W = (-35.0, -28.5)  # your cut was 6 x 6, 2.5 mm from the corner; the plunger itself is 2.5-3.4 mm square, y 55.7-59.1, w -33.2 to -30.0
# The rear face of the switch is NOT flat (your front, side and top views).  Heights above the pin face of its four levels:
HU_TOP_H = 14.0            # the lever-end block (14 mm long, with the L-shaped top plate): the highest part
HU_SLAB_H = 11.5           # the slab along the top edge, module side (about 23 x 11 mm); the first insert's slab pad (3.6 mm) had to be ~1 mm thinner, so 14.1 - 2.6
HU_STRIP_H = 7.5           # the cover-plate strip near the bottom edge (about 22.5 x 5.5 mm): 5 + 2.5 as in your front view
HU_BASE_H = 5.0            # the base plate
# The insert fills the gaps under the slab and under the strip so that all three bearing areas end up in one plane with the lever-end block:
HU_INS_SPINE_T = 1.6       # thickness of the spine along the module-side end and of the webs that tie the pads to it
HU_INS_VARIANTS = (-0.3, 0.0, 0.3)   # three are printed: the slab pad this much thinner / nominal / thicker (spares around your 'about 1 mm')
HU_INS_STRIP_Y = (19.5, 24.5)        # the pad under the cover strip: 5 mm wide (the strip is about 5.5 mm), measured from the switch's top edge
HU_LUG_T = 3.0             # the plate that sits behind the end of the Panel's collar and reaches out to the flap
HU_LUG_LEN = 9.4           # how far it reaches beyond the holder (the flap's width), along y
HU_FLAP_T = 4.5            # the flap that lies against the OUTSIDE of the collar wall (module side)
HU_FLAP_CLEAR = 0.3        # gap between flap and collar wall
HU_FLAP_TOP = -8.0         # the flap ends here (the collar joins the panel at -4)
HU_SCREW_W = -14.0         # the M3 x 10 screw goes through flap, collar wall and cradle wall at this depth
HU_SCREW_D = 3.4           # clearance hole - also the drill guide for the collar wall and the cradle wall (use a 3.4 mm drill)
HU_TOP_EDGE = 112.0        # cradle outline 224 mm: half of it, from the cradle's centre line to its top edge

# --- output -------------------------------------------------------------------
SHOW_REFERENCE = True    # add the grey ghost blocks for the screen module and cradle
EXPORT_STL = True
EXPORT_DIR = os.path.join(os.path.expanduser("~"), "Judicom_stl")

# =============================================================================
# DERIVED GEOMETRY
# =============================================================================
ALPHA = math.radians(SLOPE_ANGLE)
SA, CA, TA = math.sin(ALPHA), math.cos(ALPHA), math.tan(ALPHA)
SLOPE_L = SLOPE_LEN
D = SLOPE_LEN * CA                 # depth  (Y)
H = FRONT_H + SLOPE_LEN * SA       # height (Z) at the back wall

cradle_open_w = CRADLE_W + CRADLE_CLEAR
cradle_open_l = CRADLE_L + CRADLE_CLEAR
collar_w = cradle_open_w + 2 * COLLAR_WALL

# strips: centre line offset from the screen's centre line, and overall footprint
strip_c = SCR_MOD_W / 2.0 + STRIP_CLEAR + STRIP_W / 2.0
strips_w = 2 * (strip_c + STRIP_W / 2.0)
strip_l = SCR_MOD_L + 2 * STRIP_EXTRA

# u = across the slope (same as X), v = up the slope from the front edge,
# w = out of the slope face (w = 0 is the outer surface, inside is negative).
# Left to right: wall | gap | cradle collar | gap | strips + screen | gap | wall
side_gap = (W - 2 * WALL - collar_w - strips_w) / 3.0
cradle_u0 = WALL + side_gap + COLLAR_WALL
scr_cu = WALL + side_gap + collar_w + side_gap + strips_w / 2.0
LUG_W = side_gap + 0.5             # side lugs overlap the collar / strips by 0.5

CAGE_DEPTH = CRADLE_T + TAB_T
# furthest the collar's far end may run up the slope before it hits the back wall
v_reach = (D - WALL - 1.0 - CAGE_DEPTH * SA) / CA
cradle_v0 = min((SLOPE_L - cradle_open_l) / 2.0,
                v_reach - COLLAR_WALL - cradle_open_l)

btn_v0 = BTN_FRONT_MARGIN
win_v0 = btn_v0 + BTN_HOLE_L + BTN_SCREEN_GAP
win_cv = win_v0 + WIN_L / 2.0
strip_v0 = win_cv - strip_l / 2.0

SLOPE_PLACEMENT = App.Placement(V(0, 0, FRONT_H),
                                App.Rotation(V(1, 0, 0), math.degrees(ALPHA)))

# bottom-plate screw bosses live on the side walls; kept clear of the front/back walls
_BY = WALL + BOSS_BASE_W / 2.0 + 0.5          # corner bosses keep 0.5 mm off the front / back wall
BOSS_PTS = [(WALL + BOSS_XC, _BY), (W - WALL - BOSS_XC, _BY),
            (WALL + BOSS_XC, D - _BY), (W - WALL - BOSS_XC, D - _BY),
            (WALL + BOSS_XC, D / 2.0), (W - WALL - BOSS_XC, D / 2.0)]

BACK_BOSS_PTS = [(x, D - WALL - BOSS_XC) for x in BACK_BOSS_X]      # plate screws up into the back wall

side_screw_v = [35.0 + i * (SLOPE_LEN - 70.0) / (SIDE_SCREWS - 1) for i in range(SIDE_SCREWS)]
# depth of the side screws below the face: the insert sits BLOCK_HALF above the lug's free edge
side_screw_w = -(SLOPE_WALL + LUG_DEPTH - BLOCK_HALF)
BACK_SCREW_Y = D - WALL - BACK_LUG_Y / 2.0          # depth (y) of the side wall -> back wall screws

# speaker standoff positions relative to the speaker centre (y, z)
spk_pts = [(sy * SPK_HOLE_SPACING / 2.0, sz * SPK_HOLE_SPACING / 2.0)
           for sy in (-1, 1) for sz in (-1, 1)]

# DC jack: ring tip -> shoulder (where the barrel meets the body), tunnel block
jack_y_tip = D + JACK_TIP_OUT
jack_y_shoulder = jack_y_tip - (JACK_RING + JACK_BARREL_L)
jack_pocket_t = JACK_BODY_T + JACK_CLEAR
jack_pocket_w_front = JACK_SQ_W + 2 * JACK_CLEAR
jack_pocket_w_rear = JACK_BODY_W + 2 * JACK_CLEAR
jack_out_w = jack_pocket_w_rear + 2 * JACK_SIDE_WALL
jack_z0 = JACK_Z - jack_pocket_t / 2.0              # pocket floor
jack_z1 = JACK_Z + jack_pocket_t / 2.0              # pocket ceiling
jack_tower_z0 = jack_z0 - JACK_FLOOR
jack_tower_z1 = jack_z1 + JACK_TOP

# phone-cord jack on the left wall
rj_in_w = RJ_BODY_W + 2 * RJ_CLEAR                  # tunnel inside width
rj_out_w = rj_in_w + 2 * RJ_SIDE_WALL               # tunnel outside width
rj_win_w = RJ_W + 2 * RJ_CLEAR                      # window width
rj_x_rear = WALL + RJ_BODY_L                        # rear face of the jack body
rj_x_seat = rj_x_rear + RJ_CAP_STAND                # plane the cap plate sits on
rj_z_lo = RJ_Z0 - RJ_CLEAR - RJ_FLOOR               # underside of the tunnel
rj_z_hi = RJ_Z0 + RJ_H + RJ_CLEAR + RJ_TOP          # top of the tunnel
rj_cap_z0 = RJ_Z0 + RJ_WIRE_H                       # bottom edge of the cap
rj_screw_z = (rj_cap_z0 + rj_z_hi) / 2.0            # height of the cap screws
rj_cap_w = 2 * RJ_BOSS_Y1                           # cap plate width


def collar_bottom_z(y):
    """Height of the underside of the cradle collar (on the panel) at depth y."""
    return FRONT_H + (y - CAGE_DEPTH * SA) * TA - CAGE_DEPTH * CA


# =============================================================================
# HELPERS
# =============================================================================
def lbox(u0, v0, w0, u1, v1, w1):
    """Box in slope-local coordinates (also used as a plain box in world coords)."""
    return Part.makeBox(u1 - u0, v1 - v0, w1 - w0, V(u0, v0, w0))


def cyl(r, h, base, direction):
    return Part.makeCylinder(r, h, base, direction)


def on_slope(shape):
    s = shape.copy()
    s.Placement = SLOPE_PLACEMENT.multiply(s.Placement)
    return s


def prism_x(pts_yz, x0, x1):
    pts = [V(x0, y, z) for (y, z) in pts_yz]
    pts.append(pts[0])
    face = Part.Face(Part.makePolygon(pts))
    return face.extrude(V(x1 - x0, 0, 0))


def fillet_edges(shape, r, pred):
    try:
        edges = [e for e in shape.Edges if pred(e)]
        return shape.makeFillet(r, edges)
    except Exception as ex:  # fillets can fail on odd geometry; keep going
        App.Console.PrintWarning("Fillet r=%.1f skipped: %s\n" % (r, ex))
        return shape


def _not_on_bottom(e):
    return not all(abs(v.Point.z) < 1e-6 for v in e.Vertexes)


def _is_vertical(e):
    p = [v.Point for v in e.Vertexes]
    return len(p) == 2 and abs(p[0].x - p[1].x) < 1e-6 and abs(p[0].y - p[1].y) < 1e-6


def cut_all(shape, tools):
    """Cut a list of mutually NON-overlapping tools in one operation."""
    tools = [t for t in tools if t is not None]
    if not tools:
        return shape
    return shape.cut(Part.makeCompound(tools))


def fuse_all(shape, tools):
    for t in tools:
        shape = shape.fuse(t)
    return shape


def grille_cutters(center, ax1, ax2, direction, radius, hole_d, pitch, start, depth):
    """Hex pattern of round holes inside a circle of `radius`."""
    out = []
    n = int(radius / pitch) + 2
    for j in range(-n, n + 1):
        for i in range(-n, n + 1):
            a = i * pitch + (pitch / 2.0 if j % 2 else 0.0)
            b = j * pitch * 0.866
            if math.hypot(a, b) <= radius - hole_d / 2.0:
                p = center + ax1 * a + ax2 * b + direction * start
                out.append(cyl(hole_d / 2.0, depth, p, direction))
    return out


def refine(shape):
    try:
        return shape.removeSplitter()
    except Exception:
        return shape


def z_off(y):
    """Height of the INNER surface of the sloped wall at depth y."""
    return FRONT_H + y * TA - SLOPE_WALL / CA


# --- screw joint helpers -------------------------------------------------------
def clearance_hole(p_outer, d_in, thick):
    """Countersunk clearance hole through a wall.
    p_outer: point on the wall's OUTER face; d_in: unit vector pointing into the wall."""
    r = SCREW_CLEAR_D / 2.0
    shaft = cyl(r, thick + 3.0, p_outer - d_in * 1.5, d_in)
    csk_h = (SCREW_CSK_D - SCREW_CLEAR_D) / 2.0                 # 45 degree countersink
    cone = Part.makeCone(SCREW_CSK_D / 2.0, r, csk_h, p_outer, d_in)
    head = cyl(SCREW_CSK_D / 2.0, 1.5, p_outer - d_in * 1.5, d_in)
    return shaft.fuse(cone).fuse(head)


def insert_hole(face_pt, d_in):
    """Blind hole for one heat-set brass insert (4 mm long) - 1.5 mm deeper than the insert so the
    plastic pushed aside by the hot insert has somewhere to go.
    face_pt: point on the face the insert is pushed in through; d_in: unit vector into the material."""
    return cyl(INSERT_HOLE_D / 2.0, INSERT_DEPTH + 0.3, face_pt - d_in * 0.3, d_in)


def trap_block(c, e_len, e_up, e_ext, base_w, top_w, height, ext_len):
    """Trapezoidal prism - the shape of every insert support block.
    The trapezoid has its WIDE edge (base_w) centred on c and running along e_len; it narrows to top_w
    at `height` further along e_up.  It is then extruded by ext_len along e_ext (which must be
    perpendicular to both).  The wide edge sits on the part the block is attached to, so the
    tightening torque is spread over a long base instead of a small round post."""
    hb, ht = e_len * (base_w / 2.0), e_len * (top_w / 2.0)
    top = c + e_up * height
    pts = [c - hb, c + hb, top + ht, top - ht]
    pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(e_ext * ext_len)


def slope_point(u, v, w):
    """World coordinates of a slope-local point."""
    return SLOPE_PLACEMENT.multVec(V(u, v, w))


# =============================================================================
# SPLITTING THE SHELL INTO PRINTABLE PIECES
# =============================================================================
def split_shell():
    """Cut the rounded wedge shell into side walls, back wall, front lip and sloped panel.
    The pieces add up to exactly the original shell (checked in the test script)."""
    env = prism_x([(0, 0), (D, 0), (D, H), (0, FRONT_H)], 0, W)
    outer = fillet_edges(env, EDGE_R, _not_on_bottom)
    cavity = prism_x([(WALL, -1), (D - WALL, -1),
                      (D - WALL, z_off(D - WALL)), (WALL, z_off(WALL))],
                     WALL, W - WALL)
    shell = outer.cut(cavity)
    zt = H + 5.0
    side_l = shell.common(lbox(-1, -1, -1, WALL, D + 1, zt))
    side_r = shell.common(lbox(W - WALL, -1, -1, W + 1, D + 1, zt))
    mid = shell.common(lbox(WALL, -1, -1, W - WALL, D + 1, zt))
    # everything below the inside surface of the sloped face (= the front and back walls)
    below = prism_x([(-1, -1), (D + 1, -1), (D + 1, z_off(D + 1)), (-1, z_off(-1))],
                    WALL, W - WALL)
    walls = mid.common(below)
    front = walls.common(lbox(WALL, -1, -1, W - WALL, WALL, zt))
    back = walls.common(lbox(WALL, D - WALL, -1, W - WALL, D + 1, zt))
    panel = mid.cut(below)
    return {"env": env, "shell": shell, "side_l": side_l, "side_r": side_r,
            "front": front, "back": back, "panel": panel}


# =============================================================================
# PANEL (sloped face)
# =============================================================================
def _back_screw_z():
    return z_off(D - WALL) - 7.0          # height of the back-wall screws


def build_panel(panel_s, env):
    panel = panel_s

    # --- cradle collar (fused first, opening cut through it afterwards)
    cage = lbox(cradle_u0 - COLLAR_WALL, cradle_v0 - COLLAR_WALL, -CAGE_DEPTH,
                cradle_u0 + cradle_open_w + COLLAR_WALL,
                cradle_v0 + cradle_open_l + COLLAR_WALL, -0.5)
    cage = on_slope(cage).common(env)          # never poke outside the envelope
    panel = panel.fuse(cage)

    # --- the two screen mounting strips (long, up the slope, STRIP_DEPTH deep)
    for sgn in (-1, 1):
        cu = scr_cu + sgn * strip_c
        strip = lbox(cu - STRIP_W / 2.0, strip_v0, -(SLOPE_WALL + STRIP_DEPTH),
                     cu + STRIP_W / 2.0, strip_v0 + strip_l, -SLOPE_WALL + 0.5)
        panel = panel.fuse(on_slope(strip))

    # --- lugs the side walls screw into (4 per side).  Each is a trapezoid block: LUG_BASE_W wide
    # where it joins the panel, narrowing to BLOCK_TOP_W at its free edge, with the insert hole
    # going in through the flat face that touches the side wall.
    pilots = []
    for v in side_screw_v:
        for left in (True, False):
            u_face, s = (WALL, 1.0) if left else (W - WALL, -1.0)
            lug = trap_block(V(u_face, v, -SLOPE_WALL + 0.5), V(0, 1, 0), V(0, 0, -1), V(s, 0, 0),
                             LUG_BASE_W, BLOCK_TOP_W, LUG_DEPTH + 0.5, LUG_W)
            panel = panel.fuse(on_slope(lug))
            pilots.append(on_slope(insert_hole(V(u_face, v, side_screw_w), V(s, 0, 0))))

    # --- lugs the back wall screws into (4), hanging just in front of the back wall.  Trapezoid in
    # the x/z plane (wide against the panel, narrow at the bottom), clipped to the slope above.
    y0, y1 = D - WALL - BACK_LUG_Y, D - WALL
    zb = z_off(y1) - BACK_LUG_DROP
    for xc in PANEL_BACK_X:
        lug = trap_block(V(xc, y0, z_off(y1) + 2.0), V(1, 0, 0), V(0, 0, -1), V(0, 1, 0),
                         LUG_BASE_W, BLOCK_TOP_W, BACK_LUG_DROP + 2.0, BACK_LUG_Y)
        clip = prism_x([(y0 - 1.0, z_off(y0 - 1.0) + 0.5), (y1 + 1.0, z_off(y1 + 1.0) + 0.5),
                        (y1 + 1.0, zb - 5.0), (y0 - 1.0, zb - 5.0)],
                       xc - LUG_BASE_W, xc + LUG_BASE_W)
        panel = panel.fuse(lug.common(clip))
        pilots.append(insert_hole(V(xc, y1, _back_screw_z()), V(0, -1, 0)))

    # --- cradle opening, then the 4 seat tabs
    panel = panel.cut(on_slope(lbox(cradle_u0, cradle_v0, -CAGE_DEPTH - 1,
                                    cradle_u0 + cradle_open_w,
                                    cradle_v0 + cradle_open_l, 2)))
    for su in (0, 1):
        for sv in (0, 1):
            ue = cradle_u0 + su * cradle_open_w            # pocket edge
            ve = cradle_v0 + sv * cradle_open_l
            du = -1 if su else 1                           # direction into the pocket
            dv = -1 if sv else 1
            ua, ub = sorted((ue - du * 1.5, ue + du * TAB_SIZE))
            va, vb = sorted((ve - dv * 1.5, ve + dv * TAB_SIZE))
            panel = panel.fuse(on_slope(lbox(ua, va, -CAGE_DEPTH, ub, vb, -CRADLE_T)))
            pu_, pv_ = ue + du * CRADLE_SCREW_INSET, ve + dv * CRADLE_SCREW_INSET
            pilots.append(on_slope(cyl(CRADLE_SCREW_D / 2, TAB_T + 2,
                                       V(pu_, pv_, -CAGE_DEPTH - 1), V(0, 0, 1))))

    # --- screen window (straight through the front wall)
    panel = panel.cut(on_slope(lbox(scr_cu - WIN_W / 2.0, win_cv - WIN_L / 2.0, -SLOPE_WALL - 1,
                                    scr_cu + WIN_W / 2.0, win_cv + WIN_L / 2.0, 1)))

    # --- the two button holes
    btn_cv = btn_v0 + BTN_HOLE_L / 2.0
    for sgn in (-1, 1):
        cu = scr_cu + sgn * (BTN_HOLE_W / 2.0 + BTN_GAP / 2.0)
        panel = panel.cut(on_slope(lbox(cu - BTN_HOLE_W / 2.0, btn_cv - BTN_HOLE_L / 2.0, -SLOPE_WALL - 1,
                                        cu + BTN_HOLE_W / 2.0, btn_cv + BTN_HOLE_L / 2.0, 1)))
    return refine(cut_all(panel, pilots))


# =============================================================================
# SIDE WALLS
# =============================================================================
def build_side(side_s, left):
    side = side_s
    xs = [p for p in BOSS_PTS if (p[0] < W / 2.0) == left]
    cutters = []
    s_in = 1.0 if left else -1.0                            # direction from the outer face into the box
    x_wall = WALL if left else W - WALL                     # inside face of the wall
    for (x, y) in xs:       # bottom-plate bosses: trapezoid, wide edge on the wall, insert opens downwards
        reach = abs(x - x_wall) + BLOCK_HALF + 0.5          # wide edge (0.5 inside the wall) -> narrow edge
        side = side.fuse(trap_block(V(x_wall - s_in * 0.5, y, 0), V(0, 1, 0), V(s_in, 0, 0), V(0, 0, 1),
                                    BOSS_BASE_W, BLOCK_TOP_W, reach, BOSS_H))
        cutters.append(insert_hole(V(x, y, 0), V(0, 0, 1)))

    xo = 0.0 if left else W                                 # x of the outer face
    d_in = V(1, 0, 0) if left else V(-1, 0, 0)
    for v in side_screw_v:                                  # screws into the panel lugs
        p = slope_point(0, v, side_screw_w)
        cutters.append(clearance_hole(V(xo, p.y, p.z), d_in, WALL))
    for zc in BACK_SIDE_Z:                                  # screws into the back-wall lugs
        cutters.append(clearance_hole(V(xo, BACK_SCREW_Y, zc), d_in, WALL))

    if left:                                                # phone-cord jack: window + tunnel + cap bosses
        # solid block around the body, open at the rear (the jack slides in from inside)
        side = side.fuse(lbox(WALL - 0.5, RJ_Y - rj_out_w / 2.0, rj_z_lo,
                              rj_x_seat, RJ_Y + rj_out_w / 2.0, rj_z_hi))
        for sgn in (-1, 1):                                 # two trapezoid bosses the cap screws into
            side = side.fuse(trap_block(V(WALL - 0.5, RJ_Y + sgn * RJ_BOSS_Y0, rj_screw_z),
                                        V(0, 0, 1), V(0, sgn, 0), V(1, 0, 0),
                                        RJ_BOSS_BASE_H, BLOCK_TOP_W, RJ_BOSS_Y1 - RJ_BOSS_Y0,
                                        rj_x_seat - (WALL - 0.5)))
            cutters.append(insert_hole(V(rj_x_seat, RJ_Y + sgn * RJ_SCREW_DY, rj_screw_z), V(-1, 0, 0)))
        # window for the front lip (top-aligned with the body) + the tunnel for the body
        window = lbox(-1.0, RJ_Y - rj_win_w / 2.0, RJ_Z0 + (RJ_H - RJ_NOSE_H) - RJ_CLEAR,
                      WALL, RJ_Y + rj_win_w / 2.0, RJ_Z0 + RJ_H + RJ_CLEAR)
        tunnel = lbox(WALL, RJ_Y - rj_in_w / 2.0, RJ_Z0 - RJ_CLEAR,
                      rj_x_seat + 1.0, RJ_Y + rj_in_w / 2.0, RJ_Z0 + RJ_H + RJ_CLEAR)
        cutters.append(window.fuse(tunnel))
    else:                                                   # speaker: grille + 4 standoffs
        cutters += grille_cutters(V(W - WALL, SPK_Y, SPK_Z), V(0, 1, 0), V(0, 0, 1), V(1, 0, 0),
                                  GRILLE_R, GRILLE_HOLE, GRILLE_PITCH, -1.0, WALL + 2.0)
        x_top = W - WALL - SPK_POST_H                       # flat top of the standoffs
        for (dy, dz) in spk_pts:
            y, z = SPK_Y + dy, SPK_Z + dz
            sz = 1.0 if dz > 0 else -1.0                    # +1 top posts, -1 bottom posts
            # trapezoid standoff: narrow edge on the speaker side, wide edge pointing away from it
            side = side.fuse(trap_block(V(x_top, y, z + sz * (SPK_BLOCK_LEN - BLOCK_HALF)),
                                        V(0, 1, 0), V(0, 0, -sz), V(1, 0, 0),
                                        SPK_BLOCK_BASE_W, BLOCK_TOP_W, SPK_BLOCK_LEN, SPK_POST_H + 0.5))
            # blind insert hole: down the standoff and 1.5 mm into the wall (leaves a 1.5 mm skin outside)
            cutters.append(insert_hole(V(x_top, y, z), V(1, 0, 0)))
    return refine(cut_all(side, cutters))


# =============================================================================
# BACK WALL
# =============================================================================
def build_back(back_s):
    back = back_s
    cutters = []
    for zc in BACK_SIDE_Z:                                  # lugs the side walls screw into
        for left in (True, False):
            x_face, s = (WALL, 1.0) if left else (W - WALL, -1.0)
            # trapezoid in the y/z plane: LUG_BASE_W tall against the back wall, narrowing to
            # BLOCK_TOP_W at its free edge; the insert goes in through the face touching the side wall
            back = back.fuse(trap_block(V(x_face, D - WALL + 0.5, zc), V(0, 0, 1), V(0, -1, 0), V(s, 0, 0),
                                        LUG_BASE_W, BLOCK_TOP_W, BACK_LUG_Y + 0.5, BACK_LUG_W))
            cutters.append(insert_hole(V(x_face, BACK_SCREW_Y, zc), V(s, 0, 0)))
    for xc in PANEL_BACK_X:                                 # screws up into the panel lugs
        cutters.append(clearance_hole(V(xc, D, _back_screw_z()), V(0, -1, 0), WALL))
    for (x, y) in BACK_BOSS_PTS:      # bottom edge: trapezoid bosses (wide edge on the wall), insert opens downwards
        back = back.fuse(trap_block(V(x, D - WALL + 0.5, 0), V(1, 0, 0), V(0, -1, 0), V(0, 0, 1),
                                    BOSS_BASE_W, BLOCK_TOP_W, BOSS_XC + BLOCK_HALF + 0.5, BOSS_H))
        cutters.append(insert_hole(V(x, y, 0), V(0, 0, 1)))

    # --- DC barrel jack: a solid block on the inside of the wall, then a round bore for
    # the barrel and a rectangular tunnel for the body are cut into it.  The jack is
    # slid in from the inside (barrel first); its shoulder stops against the front of
    # the tunnel.  One M3 screw from above presses it onto the floor.
    back = back.fuse(lbox(JACK_X - jack_out_w / 2.0, jack_y_shoulder - JACK_TUNNEL_L, jack_tower_z0,
                          JACK_X + jack_out_w / 2.0, D - WALL + 0.5, jack_tower_z1))
    cutters.append(cyl(JACK_BORE_D / 2.0, (D + 1.0) - (jack_y_shoulder - 0.5),
                       V(JACK_X, D + 1.0, JACK_Z), V(0, -1, 0)))
    cutters.append(jack_pocket())
    # clamp screw: an insert hole from the top (INSERT_DEPTH deep), then a 3.4 mm passage through the
    # remaining 1 mm so the screw tip can reach the jack body.  (Fused: the two overlap by 0.5 mm.)
    y_clamp = jack_y_shoulder - JACK_CLAMP_AT
    z_pass = jack_tower_z1 - INSERT_DEPTH + 0.5
    passage = cyl(SCREW_CLEAR_D / 2.0, z_pass - (jack_z1 - 0.5), V(JACK_X, y_clamp, z_pass), V(0, 0, -1))
    cutters.append(insert_hole(V(JACK_X, y_clamp, jack_tower_z1), V(0, 0, -1)).fuse(passage))
    return refine(cut_all(back, cutters))


def jack_pocket():
    """The tunnel the jack body slides into (tapered to follow the ribbed section)."""
    ys = jack_y_shoulder
    hf, hr = jack_pocket_w_front / 2.0, jack_pocket_w_rear / 2.0
    y1 = ys - JACK_SQ_L
    y2 = y1 - JACK_TAPER_L
    y3 = ys - JACK_TUNNEL_L - 1.0                  # runs out through the rear of the block
    x = JACK_X
    pts = [V(x - hf, ys, jack_z0), V(x + hf, ys, jack_z0), V(x + hf, y1, jack_z0),
           V(x + hr, y2, jack_z0), V(x + hr, y3, jack_z0), V(x - hr, y3, jack_z0),
           V(x - hr, y2, jack_z0), V(x - hf, y1, jack_z0)]
    pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, jack_pocket_t))


# =============================================================================
# BOTTOM PLATE (with the front wall as an upturned lip)
# =============================================================================
def build_plate(front_s):
    plate = lbox(0, 0, -PLATE_T, W, D, 0)
    plate = fillet_edges(plate, EDGE_R, _is_vertical)

    pi_x0 = W / 2.0 - PI_L / 2.0
    pi_y0 = D - WALL - PI_BACK_GAP - PI_W
    stand, pilots = [], []
    for dx in (PI_HOLE_OFF, PI_HOLE_OFF + PI_HOLE_DX):
        for dy in (PI_HOLE_OFF, PI_HOLE_OFF + PI_HOLE_DY):
            x, y = pi_x0 + dx, pi_y0 + dy
            o = -1.0 if dx == PI_HOLE_OFF else 1.0          # outboard direction (away from the board)
            # trapezoid standoff: narrow edge PI_BLOCK_IN towards the board, wide edge outboard
            stand.append(trap_block(V(x + o * (PI_BLOCK_LEN - PI_BLOCK_IN), y, -0.5), V(0, 1, 0), V(-o, 0, 0),
                                    V(0, 0, 1), PI_BLOCK_BASE_W, PI_BLOCK_TOP_W, PI_BLOCK_LEN,
                                    PI_STANDOFF_H + 0.5))
            pilots.append(cyl(PI_PILOT_D / 2, PI_STANDOFF_H, V(x, y, 1.0), V(0, 0, 1)))
    plate = plate.fuse(Part.makeCompound(stand))
    plate = plate.fuse(front_s)                              # the front wall, as a lip

    holes = []
    for (x, y) in BOSS_PTS + BACK_BOSS_PTS:                  # countersunk screw holes
        h = cyl(SCREW_HOLE_D / 2, PLATE_T + 1.0, V(x, y, -PLATE_T - 0.5), V(0, 0, 1))
        cone = Part.makeCone(SCREW_HEAD_D / 2, SCREW_HOLE_D / 2, 1.5, V(x, y, -PLATE_T), V(0, 0, 1))
        holes.append(h.fuse(cone))
    for fx in (FOOT_INSET, W - FOOT_INSET):                  # rubber-foot recesses
        for fy in (FOOT_INSET, D - FOOT_INSET):
            holes.append(cyl(FOOT_D / 2, FOOT_DEPTH + 0.5, V(fx, fy, -PLATE_T - 0.5), V(0, 0, 1)))
    for gx in (55.0, W - 55.0):                              # vents: two groups of slots
        for i in range(VENT_COUNT):
            x = gx + (i - (VENT_COUNT - 1) / 2.0) * VENT_PITCH
            holes.append(lbox(x - VENT_SLOT_W / 2, VENT_Y - VENT_SLOT_L / 2, -PLATE_T - 1,
                              x + VENT_SLOT_W / 2, VENT_Y + VENT_SLOT_L / 2, 1))
    plate = cut_all(plate, holes + pilots)

    # cable slot at the back (Pi power / HDMI / USB leads)
    plate = plate.cut(lbox(W / 2 - CABLE_SLOT_W / 2, D - WALL - 3 - CABLE_SLOT_L, -PLATE_T - 1,
                           W / 2 + CABLE_SLOT_W / 2, D - WALL - 3, 1))
    return refine(plate)


# =============================================================================
# BUTTONS: printed parts and reference ghosts (button-local coordinates, origin = hole centre)
# =============================================================================
# heights along the press axis (w; 0 = outside face of the panel, -4 = inside face)
W_STUB = -BT_STUB_END                                   # cut end of the barrel: the slider's flange rests on it
W_FL_BOT = W_STUB - BT_FLANGE_T                         # rear face of the flange
W_STOP = W_FL_BOT - BT_TRAVEL                           # top face of the frame's end wall = the hard stop
W_END_BOT = W_STOP - BT_END_T
W_RING_BOT = PL_HEAD_BOT - PL_RING_KEEP                 # cut face of the plunger collar; the guide's top face touches it
W_NUT_TOP = -SLOPE_WALL - BT_RING_T                     # the mounting nut sits behind the anchor ring
SW_W, SW_H, SW_D = 27.0, 15.9, 10.3                     # BLEE switch: width, height along the plunger, thickness
SW_HOLE_D, SW_HOLE_DX, SW_HOLE_DZ = 3.4, 22.2, 10.3
SW_PIN_W, SW_PIN_D, SW_PIN_H = 3.0, 4.0, 3.0
W_SW_TOP = W_STOP - 0.1                                 # switch body top sits 0.1 mm below the stop plane
W_PIN_TOP = W_FL_BOT - BT_GAP                           # pin top at rest
W_SW_BOT = W_SW_TOP - SW_H
assert abs((W_SW_TOP + SW_PIN_H) - W_PIN_TOP) < 0.11, "pin / stop geometry no longer consistent"
W_FR_BOT = W_SW_BOT - 1.5                               # bottom of the frame's side walls
W_AN_BOT = W_SW_BOT - 4.0                               # bottom of the anchor plate (the low nut pocket needs the room)
SW_U0, SW_U1 = BT_SW_CU - SW_W / 2.0, BT_SW_CU + SW_W / 2.0
# across the switch (v): thin wall | switch | inner wall | slide gap | anchor plate
FR_V0 = BT_PIN_V - SW_D / 2.0 - BT_SW_CLEAR             # inner face of the thin (outer) wall
FR_V1 = BT_PIN_V + SW_D / 2.0 + BT_SW_CLEAR             # inner face of the inner wall
FR_VT = FR_V0 - BT_THIN_T                               # outside face of the thin wall = screw-head bearing face
FR_VI = FR_V1 + BT_INNER_T                              # outside face of the inner wall
FR_U0, FR_U1 = SW_U0 - BT_SIDE_RIM, SW_U1 + BT_SIDE_RIM
AN_V0 = FR_VI + BT_SLIDE_GAP                            # anchor plate: face toward the button axis
AN_V1 = AN_V0 + BT_PLATE_T                              #               outer face (nut pockets open here)
AN_U0 = FR_U0
AN_STOP_U0 = FR_U1 + BT_SLIDE_GAP                       # block that stops the frame when it is slid on
AN_U1 = AN_STOP_U0 + BT_STOP_W
AN_RING_V0 = 11.0                                       # the ring plate reaches from the barrel hole out to the plate
SCREW_TIP = FR_VT + BT_SCREW_L
AN_FLOOR = min(AN_V1 - (BT_NUT3_H + 0.3), SCREW_TIP - BT_NUT3_H - 0.2)   # floor of the nut pockets
AN_WEB = AN_FLOOR - AN_V0                               # plastic left between the plate's inner face and the nut
POCKET_U = BT_NUT3_AF + 0.2                             # nut pocket: across the flats ...
POCKET_W = 6.35 + 0.15 + 2.0 * BT_SLOT                  # ... and along the press axis (corners + tuning travel)
assert AN_WEB >= 1.2, "nut pockets leave too little plastic - use a longer screw"
# the switch is turned over (plunger toward +u), so the hole near the plunger is the LOW one
SW_HOLES = [(BT_SW_CU + SW_HOLE_DX / 2.0, W_SW_BOT + (SW_H - SW_HOLE_DZ) / 2.0),
            (BT_SW_CU - SW_HOLE_DX / 2.0, W_SW_TOP - (SW_H - SW_HOLE_DZ) / 2.0)]
assert min(w for (_, w) in SW_HOLES) - POCKET_W / 2.0 - W_AN_BOT >= 2.0, "nut pocket too close to the bottom of the plate"


def zc(r, w0, w1, x=0.0, y=0.0):
    """Cylinder along w between w0 and w1 (either order)."""
    lo, hi = min(w0, w1), max(w0, w1)
    return cyl(r, hi - lo, V(x, y, lo), V(0, 0, 1))


def orient_button_flip(s):
    s.rotate(V(0, 0, 0), V(1, 0, 0), 180)            # +w points down: the press-side face lies on the bed


def make_slider():
    """Printed plunger tail, 12.5 mm tall.  Spigot: press fit (and a dot of glue) into the 11 mm hole of the cut plunger,
    5 mm long, ending at the head's underside.  Guide (the middle section, 6 mm): 19 mm, slides in the barrel from
    behind, its top face touches the plunger collar.  Flange: stays BEHIND the barrel's cut end, rests on it at rest (so it can
    never be pulled out) and pushes the switch plunger.  Prints flange-down; no supports."""
    sl = zc(BT_SPIGOT_D / 2.0, W_RING_BOT - 0.01, PL_HEAD_BOT)
    sl = sl.fuse(zc(BT_GUIDE_D / 2.0, W_FL_BOT + 0.01, W_RING_BOT))
    sl = sl.fuse(zc(BT_FLANGE_D / 2.0, W_FL_BOT, W_STUB))
    return refine(sl)


def make_anchor(narrow=False):
    """Anchor: a BT_RING_T (2.5 mm) ring that the mounting nut clamps against the panel (no glue, no friction clamp)
    + a plate that runs down beside the nut, toward the screen.  The plate carries the frame: two vertical
    slots (+-BT_SLOT) with a nut pocket on the outside of each.  A little block at its +u end stops the frame.
    This is the version for the LEFT button (Frank); the right button uses its mirror image.
    narrow=True: the plate (and the ring plate) is only BT_NARROW_W wide, measured from the +u end (the end with the stop
    block and the plunger side), so the far end - and with it the plate under the FAR screw - is gone: for the button
    that sits next to the HDMI plug.  The ring under the nut is untouched.
    Prints ring-face-down (the face that touches the panel lies on the bed)."""
    u0 = (AN_U1 - BT_NARROW_W) if narrow else AN_U0
    ring_plate = lbox(u0, AN_RING_V0, W_NUT_TOP, AN_U1, AN_V1, -SLOPE_WALL)
    a = ring_plate.fuse(zc(BT_NUT_D / 2.0, W_NUT_TOP, -SLOPE_WALL))                      # ring (disc, hole cut below)
    a = a.fuse(lbox(u0, AN_V0, W_AN_BOT, AN_U1, AN_V1, W_NUT_TOP + 0.01))                 # plate
    a = a.fuse(lbox(AN_STOP_U0, FR_V1, W_FR_BOT + 2.0, AN_U1, AN_V0 + 0.01, W_STOP - 1.0))  # stop block
    a = a.cut(zc(BT_RING_ID / 2.0, W_NUT_TOP - 1.0, -SLOPE_WALL + 1.0))                  # hole for the barrel
    for (u, w) in SW_HOLES:
        if narrow and u - POCKET_U / 2.0 < u0 + 2.0:
            continue                                   # this hole has no plate left behind it: no slot, no pocket
        a = a.cut(lbox(u - SW_HOLE_D / 2.0, AN_V0 - 1.0, w - BT_SLOT,
                       u + SW_HOLE_D / 2.0, AN_FLOOR + 0.01, w + BT_SLOT))                     # slot: straight part ...
        a = a.cut(cyl(SW_HOLE_D / 2.0, AN_FLOOR - AN_V0 + 1.01, V(u, AN_V0 - 1.0, w - BT_SLOT), V(0, 1, 0)))   # ... round ends
        a = a.cut(cyl(SW_HOLE_D / 2.0, AN_FLOOR - AN_V0 + 1.01, V(u, AN_V0 - 1.0, w + BT_SLOT), V(0, 1, 0)))
        a = a.cut(lbox(u - POCKET_U / 2.0, AN_FLOOR, w - POCKET_W / 2.0,
                       u + POCKET_U / 2.0, AN_V1 + 1.0, w + POCKET_W / 2.0))                  # nut pocket, open outward
    return refine(a)


def make_frame():
    """Frame: end wall (the hard stop, exactly BT_TRAVEL below the flange) + an outer and an inner wall that
    hold the BLEE switch by its own two holes (M3 screws through plain 3.4 mm holes).  It is slid onto the
    anchor plate from the OUTSIDE (-u for Frank) with the switch already in it; the stop block on the anchor
    lines the screw holes up with the slots.  Prints end-wall-down (the flange's contact face is the bottom).
    This is the version for the LEFT button (Frank); the right button uses its mirror image."""
    f = lbox(FR_U0, BT_FRAME_FRONT_V, W_END_BOT, FR_U1, FR_VI, W_STOP)                           # end wall
    f = f.fuse(lbox(FR_U0, FR_VT, W_FR_BOT, FR_U1, FR_V0, W_END_BOT + 0.01))                      # outer wall
    f = f.fuse(lbox(FR_U0, FR_V1, W_FR_BOT, FR_U1, FR_VI, W_END_BOT + 0.01))                      # inner wall
    f = f.cut(lbox(SW_U0 - 0.25, FR_V0, W_END_BOT - 1.0, SW_U1 + 0.25, FR_V1, W_STOP + 1.0))       # switch window
    for (u, w) in SW_HOLES:                                                                       # screws along v
        f = f.cut(cyl(SW_HOLE_D / 2.0, FR_VI - FR_VT + 2.0, V(u, FR_VT - 1.0, w), V(0, 1, 0)))
        if w + BT_SCREW_HEAD_D / 2.0 + 0.3 > W_END_BOT:                       # this screw head would sit under the end wall:
            f = f.cut(lbox(FR_U0 - 1.0, BT_FRAME_FRONT_V - 1.0, w - BT_SCREW_HEAD_D / 2.0 - 0.4,   # cut the end wall's front corner away
                           u + BT_SCREW_HEAD_D / 2.0 + 0.4, FR_VT, W_STOP + 1.0))               # (it is not under the flange anyway)
    return refine(f)


def make_ref_switch():
    """Ghost of the BLEE microswitch in the frame (plunger toward +u, on the button axis)."""
    sw = lbox(SW_U0, BT_PIN_V - SW_D / 2.0, W_SW_BOT, SW_U1, BT_PIN_V + SW_D / 2.0, W_SW_TOP)
    sw = sw.fuse(lbox(-SW_PIN_W / 2.0, BT_PIN_V - SW_PIN_D / 2.0, W_SW_TOP, SW_PIN_W / 2.0,
                      BT_PIN_V + SW_PIN_D / 2.0, W_PIN_TOP))
    sw = sw.fuse(lbox(SW_U0 - 6.5, BT_PIN_V - 3.2, W_SW_BOT + 2.5, SW_U0 + 0.5, BT_PIN_V + 3.2, W_SW_BOT + 4.1))
    sw = sw.fuse(lbox(BT_SW_CU - 11.0, BT_PIN_V - 3.2, W_SW_BOT - 2.0, BT_SW_CU - 2.5, BT_PIN_V + 3.2, W_SW_BOT + 0.5))
    for (u, w) in SW_HOLES:
        sw = sw.cut(cyl(SW_HOLE_D / 2.0, SW_D + 2.0, V(u, BT_PIN_V - SW_D / 2.0 - 1.0, w), V(0, 1, 0)))
    return refine(sw)


def make_ref_hardware():
    """Ghosts of the two M3 pan-head screws and their nuts (the screws sit in the middle of the slots)."""
    items = []
    r = 0.5 * 6.35
    for (u, w) in SW_HOLES:
        parts_ = [cyl(BT_SCREW_HEAD_D / 2.0, BT_SCREW_HEAD_H, V(u, FR_VT - BT_SCREW_HEAD_H, w), V(0, 1, 0)),
                  cyl(1.5, BT_SCREW_L, V(u, FR_VT, w), V(0, 1, 0))]
        pts = [V(u + r * math.cos(math.radians(90 + 60 * k)), AN_FLOOR, w + r * math.sin(math.radians(90 + 60 * k)))
               for k in range(6)]
        pts.append(pts[0])
        nut3 = Part.Face(Part.makePolygon(pts)).extrude(V(0, BT_NUT3_H, 0)).cut(cyl(1.5, 4.0, V(u, AN_FLOOR - 1, w), V(0, 1, 0)))
        parts_.append(nut3)
        items += parts_
    return Part.makeCompound(items)


def make_ref_button_parts():
    """Ghosts of the original parts as they sit after cutting: housing (lip, collar, barrel stub),
    nut, and the plunger (head + the 5 mm of round collar left under it)."""
    hous = lbox(-BT_LIP_W / 2, -BT_LIP_W / 2, 0, BT_LIP_W / 2, BT_LIP_W / 2, BT_LIP_T)
    hous = hous.fuse(lbox(-BT_COLLAR_W / 2 + 0.05, -BT_COLLAR_W / 2 + 0.05, -BT_COLLAR_T,
                          BT_COLLAR_W / 2 - 0.05, BT_COLLAR_W / 2 - 0.05, 0.01))
    hous = hous.fuse(zc(BT_BARREL_OD / 2.0, -BT_COLLAR_T + 0.01, W_STUB))
    hous = hous.cut(lbox(-12.75, -12.75, PL_HEAD_BOT - BT_TRAVEL, 12.75, 12.75, BT_LIP_T + 1.0))   # front pocket (assumed 25.5 mm square)
    hous = hous.cut(zc(BT_BARREL_ID / 2.0, PL_HEAD_BOT - BT_TRAVEL + 0.01, W_STUB - 1.0))
    nut = zc(BT_NUT_D / 2.0, W_NUT_TOP, W_NUT_TOP - BT_NUT_T).cut(zc(BT_BARREL_OD / 2.0, 1.0, -20.0))
    pl = lbox(-PL_HEAD_W / 2, -PL_HEAD_W / 2, PL_HEAD_BOT, PL_HEAD_W / 2, PL_HEAD_W / 2, PL_HEAD_BOT + PL_HEAD_T)
    pl = pl.fuse(zc(PL_RING_D / 2.0, W_RING_BOT, PL_HEAD_BOT + 0.01))
    pl = pl.cut(zc(PL_HOLE_D / 2.0, W_RING_BOT - 1.0, PL_HEAD_BOT + PL_HEAD_T + 1.0))
    return refine(hous), refine(nut), refine(pl)


# --- hang-up switch adapter ----------------------------------------------------------------
HU_CU = cradle_u0 + cradle_open_w / 2.0          # cradle centre line (across)
HU_VTOP = cradle_v0 + cradle_open_l / 2.0 + HU_TOP_EDGE   # top edge of the cradle outline (up the slope)
HU_M_COLLAR = collar_w / 2.0                     # collar wall, outer face, measured from the centre line
HU_M_OPEN = cradle_open_w / 2.0                  # collar wall, inner face
assert HU_PIN_W <= -CAGE_DEPTH - 0.5, "HU_PIN_W: the switch must stay at least 0.5 mm behind the end of the collar"


def hu_box(m0, y0, w0, m1, y1, w1):
    """Box in the adapter's own measures (see the HU_ settings), as a slope-local solid."""
    return lbox(HU_CU + min(m0, m1), HU_VTOP - max(y0, y1), min(w0, w1),
                HU_CU + max(m0, m1), HU_VTOP - min(y0, y1), max(w0, w1))


def hu_hex_pocket(m0, m1, y, w):
    """Nut pocket for an M3 nut, axis along m (u), one corner up so it prints without support."""
    r = (BT_NUT3_AF + 0.2) / (2.0 * math.cos(math.radians(30)))
    pts = [V(HU_CU + m0, HU_VTOP - (y + r * math.cos(math.radians(90 + 60 * k))), w + r * math.sin(math.radians(90 + 60 * k)))
           for k in range(6)]
    pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(V(m1 - m0, 0, 0))


def hu_top_box(x0, x1, y0, y1, h0, h1):
    """Box in the switch's own measures: x from its module-side end, y from its top edge, h = height above the pin face."""
    m_out = HU_SW_M0 + HU_SW_L
    return hu_box(m_out - x1, HU_SW_Y0 + y0, HU_PIN_W - h1, m_out - x0, HU_SW_Y0 + y1, HU_PIN_W - h0)


def make_ref_hookswitch():
    """Ghost of the BIS-10 hook switch: stepped body, plunger, lever shaft and the finger that rests on the actuator."""
    L, Hh = HU_SW_L, HU_SW_H
    xb = L - 14.0                                   # the 14 mm long lever-end block starts here
    body = hu_top_box(0, L, 0, Hh, 0, HU_BASE_H)
    body = body.fuse(hu_top_box(0, xb, 0, 11.6, 0, HU_SLAB_H))              # slab along the top edge, module side
    body = body.fuse(hu_top_box(xb, L, 0, 22.0, 0, HU_TOP_H))               # lever-end block, full height
    body = body.fuse(hu_top_box(xb, L, 22.0, Hh, 0, HU_STRIP_H))            # its low corner
    body = body.fuse(hu_top_box(3.1, 25.0, 19.2, 24.7, 0, HU_STRIP_H))      # cover-plate strip
    plunger = hu_top_box(-2.5, 0.0, 2.7, 6.1, 8.0, 10.8)   # the plunger when it has pushed out (y 55.7-59.1, w -30 to -32.8)
    shaft = hu_box(HU_FINGER_M[0], HU_SHAFT_Y[0], HU_PIN_W, HU_SW_M0, HU_SHAFT_Y[1], HU_PIN_W + HU_SHAFT_T)
    finger = hu_box(HU_FINGER_M[0], HU_FINGER_Y[0], HU_PIN_W, HU_FINGER_M[1], HU_FINGER_Y[1], HU_PIN_W + HU_FINGER_DROP)
    return body.fuse(plunger).fuse(shaft).fuse(finger)


def _ins_box(x0, x1, y0, y1, w0, w1):
    """Box in the switch's own measures (x from its module-side end, y from its top edge) and in w."""
    m_out = HU_SW_M0 + HU_SW_L
    return hu_box(m_out - x1, HU_SW_Y0 + y0, w0, m_out - x0, HU_SW_Y0 + y1, w1)


def make_hookswitch_insert(dv=0.0, marks=0):
    """Loose insert that lies on the holder's two floor rails under the switch: two pads, one under the slab and one under the
    cover-plate strip, bring those two levels up to the level of the lever-end block, so the switch rests on three flat areas
    in one plane and cannot rock.  A spine along the module-side end and two webs tie the pads together and locate them.
    dv makes the slab pad thicker (+) or thinner (-) to cover the uncertainty in the measured height.
    marks = number of small grooves cut across the spine so the printed copies can be told apart (1 thinner, 2 nominal, 3 thicker)."""
    w0 = HU_PIN_W - HU_SW_T - 0.1                    # top of the holder's floor
    T = HU_INS_SPINE_T
    t_slab = HU_SW_T + 0.1 - HU_SLAB_H + dv          # the body's rear plane is 0.1 above the floor
    t_strip = HU_SW_T + 0.1 - HU_STRIP_H
    ys0, ys1 = HU_INS_STRIP_Y
    ins = _ins_box(0.0, 4.4, 0.0, HU_SW_H, w0, w0 + T)                                  # spine along the end (bridges the open band)
    ins = ins.fuse(_ins_box(4.0, 9.4, 1.5, 7.0, w0, w0 + T))                            # web to the slab pad
    ins = ins.fuse(_ins_box(9.0, 21.0, 1.5, 7.0, w0, w0 + t_slab))                      # pad under the slab
    ins = ins.fuse(_ins_box(4.0, 6.4, ys0, ys1, w0, w0 + T))                            # web to the strip pad
    ins = ins.fuse(_ins_box(6.0, 22.0, ys0, ys1, w0, w0 + t_strip))                     # pad under the strip, 5 mm wide (stops 1 mm short of the lever-end block)
    for i in range(marks):
        ya = 25.0 + 1.6 * i
        ins = ins.cut(_ins_box(-0.1, 4.5, ya, ya + 0.8, w0 + T - 0.6, w0 + T + 0.1))
    return refine(ins)


def make_hangup_adapter():
    """Holder for the hook switch + two flaps that lie on the OUTSIDE of the Panel's collar wall (module side).
    Slope-local coordinates; printed with the floor on the bed (w up)."""
    c, t = HU_CLEAR, HU_WALL
    m_in, m_out = HU_SW_M0, HU_SW_M0 + HU_SW_L
    y_t, y_b = HU_SW_Y0, HU_SW_Y0 + HU_SW_H
    w_rear = HU_PIN_W - HU_SW_T
    w_ftop = w_rear - 0.1                      # the body sits 0.1 mm off the floor
    w_fbot = w_ftop - HU_FLOOR_T
    w_front = HU_PIN_W                         # the walls end at the pin face: pins, wires and the lever stay in the open
    # ---- the cup
    cup = hu_box(m_in - c - t, y_t - c - t, w_fbot, m_out + c + t, y_b + c + t, w_front)
    cup = cup.cut(hu_box(m_in - c, y_t - c, w_ftop, m_out + c, y_b + c, w_front + 1.0))
    cup = cup.cut(hu_box(m_in - c, y_t + HU_RAIL, w_fbot - 1.0, m_out + c, y_b - HU_RAIL, w_ftop + 0.01))     # open middle band
    cup = cup.cut(hu_box(m_in - c - t - 0.1, HU_SLOT_Y[0], w_ftop, m_in - c + 0.1, HU_SLOT_Y[1], w_front + 1.0))  # lever opening
    cup = cup.cut(hu_box(m_out + c - 0.1, HU_PLUNGER_Y[0], HU_PLUNGER_W[0], m_out + c + t + 0.1, HU_PLUNGER_Y[1], HU_PLUNGER_W[1]))   # plunger window
    for m_rib in (m_in + 10.0, m_out - 10.0):                                                                    # crush ribs
        for (ya, yb) in ((y_t - c - 0.1, y_t - c + HU_RIB), (y_b + c - HU_RIB, y_b + c + 0.1)):
            cup = cup.fuse(hu_box(m_rib - 0.6, ya, w_front - 12.0, m_rib + 0.6, yb, w_front))
    # ---- lugs + flaps (top and bottom of the cup)
    w_lug1 = -CAGE_DEPTH                                      # front of the lug touches the end face of the collar wall
    w_lug0 = w_lug1 - HU_LUG_T
    m_lug0 = HU_M_OPEN - 0.2
    m_fl0 = HU_M_COLLAR + HU_FLAP_CLEAR
    m_fl1 = m_fl0 + HU_FLAP_T
    out = cup
    y_mid = (y_t + y_b) / 2.0
    for sgn in (-1, 1):
        ya = y_t - c - t + 0.2 if sgn < 0 else y_b + c + t - 0.2           # edge shared with the cup wall
        yb = ya + sgn * (HU_LUG_LEN)                                       # far edge of the lug
        lug = hu_box(m_lug0, ya, w_lug0, m_out + c + t, yb, w_lug1)
        # 45 degree gusset under the lug so it prints without support
        g = HU_LUG_LEN
        gus = Part.Face(Part.makePolygon([V(HU_CU + m_lug0, HU_VTOP - ya, w_lug0), V(HU_CU + m_lug0, HU_VTOP - ya, w_lug0 - g),
                                          V(HU_CU + m_lug0, HU_VTOP - yb, w_lug0), V(HU_CU + m_lug0, HU_VTOP - ya, w_lug0)])
                        ).extrude(V(m_out + c + t - m_lug0, 0, 0))
        flap = hu_box(m_fl0, ya, w_lug0, m_fl1, yb, HU_FLAP_TOP)
        out = out.fuse(lug).fuse(gus).fuse(flap)
        yc = (ya + yb) / 2.0
        hole = cyl(HU_SCREW_D / 2.0, m_fl1 - m_fl0 + 2.0, V(HU_CU + m_fl0 - 1.0, HU_VTOP - yc, HU_SCREW_W), V(1, 0, 0))
        out = out.cut(hole).cut(hu_hex_pocket(m_fl1 - (BT_NUT3_H + 0.3), m_fl1 + 0.1, yc, HU_SCREW_W))
    return refine(out)


def make_ref_module():
    """7" module with its four mounting ears, seated on the strip end faces."""
    gap = max(0.0, STRIP_DEPTH - (SCR_MOD_T - EAR_T))   # glass-to-wall gap that results
    w_front = -(SLOPE_WALL + gap)
    w_rear = w_front - SCR_MOD_T
    mod = lbox(-SCR_MOD_W / 2, -SCR_MOD_L / 2, w_rear, SCR_MOD_W / 2, SCR_MOD_L / 2, w_front)
    for su in (-1, 1):
        for sv in (-1, 1):
            hu, hv = su * SCR_HOLE_SPAN_W / 2.0, sv * SCR_HOLE_SPAN_L / 2.0
            ear = lbox(hu - EAR_W / 2, hv - EAR_L / 2, w_rear, hu + EAR_W / 2, hv + EAR_L / 2, w_rear + EAR_T)
            ear = ear.cut(cyl(EAR_HOLE_D / 2, EAR_T + 2, V(hu, hv, w_rear - 1), V(0, 0, 1)))
            mod = mod.fuse(ear)
    mod.translate(V(scr_cu, win_cv, 0))
    return refine(mod)


def build_phone_cap():
    """Rear cap of the phone-jack holder: a small plate on two M3 countersunk screws.
    Its pressure pad squeezes the jack against the wall; the bottom of the jack's rear
    face is left uncovered so the wires can leave."""
    plate = lbox(rj_x_seat, RJ_Y - rj_cap_w / 2.0, rj_cap_z0,
                 rj_x_seat + RJ_CAP_T, RJ_Y + rj_cap_w / 2.0, rj_z_hi)
    plate = fillet_edges(plate, 2.0, lambda e: len(e.Vertexes) == 2
                         and abs(e.Vertexes[0].Point.y - e.Vertexes[1].Point.y) < 1e-6
                         and abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) < 1e-6)
    pad_z0 = RJ_Z0 + 12.0
    pad = lbox(rj_x_rear - RJ_PRELOAD, RJ_Y - RJ_PAD_W / 2.0, pad_z0,
               rj_x_seat + 0.2, RJ_Y + RJ_PAD_W / 2.0, pad_z0 + RJ_PAD_H)
    cap = plate.fuse(pad)
    holes = [clearance_hole(V(rj_x_seat + RJ_CAP_T, RJ_Y + s * RJ_SCREW_DY, rj_screw_z), V(-1, 0, 0), RJ_CAP_T)
             for s in (-1, 1)]
    return refine(cut_all(cap, holes))


def make_ref_phonejack():
    """The phone jack as measured: 12 x 16 front lip + 13 x 22 body, wires out of the
    lower rear.  Sits flush with the outside, shoulder against the wall."""
    x_front = WALL - RJ_NOSE_L
    nose = lbox(x_front, RJ_Y - RJ_W / 2.0, RJ_Z0 + (RJ_H - RJ_NOSE_H),
                WALL + 0.0, RJ_Y + RJ_W / 2.0, RJ_Z0 + RJ_H)
    body = lbox(WALL, RJ_Y - RJ_BODY_W / 2.0, RJ_Z0, rj_x_rear, RJ_Y + RJ_BODY_W / 2.0, RJ_Z0 + RJ_H)
    wires = lbox(rj_x_rear, RJ_Y - 4.0, RJ_Z0 + 1.0, rj_x_rear + 10.0, RJ_Y + 4.0, RJ_Z0 + 7.0)
    return nose.fuse(body).fuse(wires)


def make_ref_cradle():
    cu = cradle_u0 + cradle_open_w / 2.0
    cv = cradle_v0 + cradle_open_l / 2.0
    return lbox(cu - CRADLE_W / 2, cv - CRADLE_L / 2, -CRADLE_T, cu + CRADLE_W / 2, cv + CRADLE_L / 2, 0)


def make_ref_speaker():
    """Square-framed speaker sitting on its four standoffs (ear plane at the post tops)."""
    x0 = W - WALL - SPK_POST_H                       # ear plane
    c = V(x0, SPK_Y, SPK_Z)
    frame = lbox(x0 - 5.0, SPK_Y - SPK_FRAME / 2, SPK_Z - SPK_FRAME / 2,
                 x0, SPK_Y + SPK_FRAME / 2, SPK_Z + SPK_FRAME / 2)
    magnet = cyl(SPK_MAGNET_D / 2.0, SPK_DEPTH - 5.0, V(x0 - 5.0, SPK_Y, SPK_Z), V(-1, 0, 0))
    return frame.fuse(magnet)


def make_ref_jack():
    """DC jack adapter as measured (ring, barrel, tapered body, green terminal block),
    resting on the floor of its tunnel."""
    zc = jack_z0 + JACK_BODY_T / 2.0
    x = JACK_X
    ring = cyl(JACK_BARREL_D / 2.0, JACK_RING + JACK_BARREL_L, V(x, jack_y_tip, zc), V(0, -1, 0))
    ys = jack_y_shoulder
    y1, y2 = ys - JACK_SQ_L, ys - JACK_SQ_L - JACK_TAPER_L
    y_end = ys - 22.0                                # black body is about 22 mm long
    hs, hb = JACK_SQ_W / 2.0, JACK_BODY_W / 2.0
    pts = [V(x - hs, ys, zc - JACK_BODY_T / 2), V(x + hs, ys, zc - JACK_BODY_T / 2),
           V(x + hs, y1, zc - JACK_BODY_T / 2), V(x + hb, y2, zc - JACK_BODY_T / 2),
           V(x + hb, y_end, zc - JACK_BODY_T / 2), V(x - hb, y_end, zc - JACK_BODY_T / 2),
           V(x - hb, y2, zc - JACK_BODY_T / 2), V(x - hs, y1, zc - JACK_BODY_T / 2)]
    pts.append(pts[0])
    body = Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, JACK_BODY_T))
    green = lbox(x - 5.5, y_end - 3.0, zc - 5.5, x + 5.5, y_end + 4.0, zc + 5.5)
    return ring.fuse(body).fuse(green)


# =============================================================================
# PRINT ORIENTATION: each function lays a part flat, outer face on the bed
# =============================================================================
def orient_panel(s):
    s.Placement = SLOPE_PLACEMENT.inverse().multiply(s.Placement)   # slope face -> XY plane
    s.rotate(V(0, 0, 0), V(1, 0, 0), 180)                           # outer face down


def orient_side_left(s):
    s.rotate(V(0, 0, 0), V(0, 1, 0), -90)


def orient_side_right(s):
    s.rotate(V(0, 0, 0), V(0, 1, 0), 90)


def orient_phone_cap(s):
    s.rotate(V(0, 0, 0), V(0, 1, 0), 90)             # screw-head face down, pad up


def orient_back(s):
    s.rotate(V(0, 0, 0), V(1, 0, 0), -90)


def oriented(shape, orient):
    s = shape.copy()
    if orient is not None:
        orient(s)
    bb = s.BoundBox
    s.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    return s


# =============================================================================
# BUILD
# =============================================================================
def layout_warnings():
    w = []
    if side_gap < 5:
        w.append("Only %.1f mm between cradle, strips and walls - increase W." % side_gap)
    top_margin = SLOPE_L - (win_v0 + WIN_L)
    if top_margin < 8:
        w.append("Screen window leaves only %.1f mm above it - lengthen the slope." % top_margin)
    if SLOPE_L - (strip_v0 + strip_l) < 5:
        w.append("Mounting strips run too close to the top of the slope.")
    if cradle_v0 < 4:
        w.append("Cradle starts only %.1f mm from the front edge - shallower slope or longer SLOPE_LEN."
                 % cradle_v0)
    if abs(SCR_HOLE_SPAN_W / 2.0 - strip_c) > STRIP_W / 2.0 - 2.0:
        w.append("Ear holes (%.1f mm off centre) are not inside the strips (%.1f +- %.1f)."
                 % (SCR_HOLE_SPAN_W / 2.0, strip_c, STRIP_W / 2.0))
    if strip_l < SCR_HOLE_SPAN_L + 12:
        w.append("Strips are barely longer than the ear-hole spacing - little room to slide.")
    if SLOPE_L > BED_LIMIT:
        w.append("Sloped panel is %.0f mm long - longer than the %.0f mm print limit." % (SLOPE_L, BED_LIMIT))
    if max(W, D, H) > BED_LIMIT:
        w.append("Body is larger than the print limit in at least one direction.")
    gap = collar_bottom_z(RJ_Y - RJ_BOSS_Y1) - rj_z_hi
    if gap < 3.0:
        w.append("Phone-jack holder is only %.1f mm below the cradle collar - lower RJ_Z0 or move RJ_Y." % gap)
    if RJ_Z0 - RJ_CLEAR - RJ_FLOOR < BOSS_H + 1.0 and abs(RJ_Y - D / 2.0) < rj_cap_w / 2.0 + BOSS_BASE_W / 2.0:
        w.append("Phone-jack holder is touching the plate boss at mid-depth - raise RJ_Z0.")
    # plastic left behind the bottom of each insert hole (should be >= 2 mm; the speaker skin and the
    # DC-jack passage ring are deliberately thinner)
    for name, avail in (("Side-wall lugs (LUG_W)", LUG_W), ("Back-wall lugs (BACK_LUG_W)", BACK_LUG_W),
                        ("Panel back lugs (BACK_LUG_Y)", BACK_LUG_Y)):
        if avail - INSERT_DEPTH < 2.0:
            w.append("%s leave only %.1f mm of plastic behind the insert hole." % (name, avail - INSERT_DEPTH))
    nut_margin = BT_STUB_END - (SLOPE_WALL + BT_RING_T + BT_NUT_T)
    if nut_margin < 0.0:
        w.append("The mounting nut (behind the %.1f mm anchor ring) sticks out %.1f mm past the barrel stub - the flange "
                 "would rest on the nut. Make BT_RING_T smaller or BT_STUB_END longer." % (BT_RING_T, -nut_margin))
    if WALL - (INSERT_DEPTH - SPK_POST_H) < 1.0:
        w.append("Speaker insert holes leave only %.1f mm of skin on the outside of the wall."
                 % (WALL - (INSERT_DEPTH - SPK_POST_H)))
    return w


def add_part(doc, name, shape, color, transparency=0):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if App.GuiUp:
        try:
            obj.ViewObject.ShapeColor = color
            obj.ViewObject.Transparency = transparency
        except Exception:
            pass
    return obj


def export_stl(name, shape, orient=None):
    import MeshPart
    s = oriented(shape, orient)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, name + ".stl")
    mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.08, AngularDeflection=0.35)
    mesh.write(path)
    return path, s.BoundBox


def dc_jack_fit_test(back):
    """A slice of the finished back wall around the DC-jack tunnel - same geometry, tiny print."""
    return refine(back.common(lbox(JACK_X - 20.0, jack_y_shoulder - JACK_TUNNEL_L - 2.0, jack_tower_z0 - 7.0,
                                   JACK_X + 20.0, D + 1.0, jack_tower_z1 + 7.0)))


def phone_jack_fit_test(side_left):
    """A slice of the finished left wall around the phone-jack window and tunnel.
    Print it together with PhoneJackCap to try the real jack before printing the whole wall."""
    return refine(side_left.common(lbox(-1.0, RJ_Y - 24.0, RJ_Z0 - 8.0,
                                        rj_x_seat + 4.0, RJ_Y + 24.0, rj_z_hi + 6.0)))


def build_parts():
    pieces = split_shell()
    return {
        "Panel": build_panel(pieces["panel"], pieces["env"]),
        "SideLeft": build_side(pieces["side_l"], True),
        "SideRight": build_side(pieces["side_r"], False),
        "Back": build_back(pieces["back"]),
        "BottomPlate": build_plate(pieces["front"]),
        "PhoneJackCap": build_phone_cap(),
    }


PRINT_ORIENT = {"Panel": orient_panel, "SideLeft": orient_side_left,
                "SideRight": orient_side_right, "Back": orient_back, "BottomPlate": None,
                "PhoneJackCap": orient_phone_cap}
PART_COLORS = {"Panel": (0.16, 0.16, 0.18), "SideLeft": (0.10, 0.11, 0.14),
               "SideRight": (0.10, 0.11, 0.14), "Back": (0.13, 0.11, 0.11),
               "BottomPlate": (0.20, 0.20, 0.21), "PhoneJackCap": (0.30, 0.30, 0.34)}


def main():
    doc = App.newDocument("Judicom")
    parts = build_parts()
    for name, shp in parts.items():
        add_part(doc, name, shp, PART_COLORS[name])

    # buttons: printed slider + anchor + frame per button (Ann's anchor and frame are mirror images of Frank's)
    slider, anchor, frame = make_slider(), make_anchor(), make_frame()
    anchor_narrow = make_anchor(narrow=True)
    anchor_ann = anchor.mirror(V(0, 0, 0), V(1, 0, 0))
    narrow_ann = anchor_narrow.mirror(V(0, 0, 0), V(1, 0, 0))
    assert BT_NARROW_SIDE in (None, "Frank", "Ann"), 'BT_NARROW_SIDE must be None, "Frank" or "Ann"'
    use_anchor = {"Frank": anchor_narrow if BT_NARROW_SIDE == "Frank" else anchor,
                  "Ann": narrow_ann if BT_NARROW_SIDE == "Ann" else anchor_ann}
    frame_ann = frame.mirror(V(0, 0, 0), V(1, 0, 0))
    ref_sw, ref_hw = make_ref_switch(), make_ref_hardware()
    ref_hous, ref_nut, ref_pl = make_ref_button_parts()
    btn_cv = btn_v0 + BTN_HOLE_L / 2.0
    for sgn, label in ((-1, "Frank"), (1, "Ann")):
        cu = scr_cu + sgn * (BTN_HOLE_W / 2.0 + BTN_GAP / 2.0)
        items = [("ButtonSlider_" + label, slider, (0.85, 0.85, 0.80)),
                 ("ButtonAnchor_" + label, use_anchor[label], (0.30, 0.34, 0.46)),
                 ("ButtonFrame_" + label, frame if sgn < 0 else frame_ann, (0.18, 0.55, 0.52))]
        if SHOW_REFERENCE:
            items += [("REF_Housing_" + label, ref_hous, (0.08, 0.08, 0.08)), ("REF_Nut_" + label, ref_nut, (0.5, 0.5, 0.5)),
                      ("REF_Plunger_" + label, ref_pl, (0.95, 0.95, 0.95)),
                      ("REF_Switch_" + label, ref_sw if sgn < 0 else ref_sw.mirror(V(0, 0, 0), V(1, 0, 0)), (0.10, 0.25, 0.80)),
                      ("REF_Screws_" + label, ref_hw if sgn < 0 else ref_hw.mirror(V(0, 0, 0), V(1, 0, 0)), (0.75, 0.75, 0.78))]
        for name, shp, col in items:
            c = shp.copy()
            c.translate(V(cu, btn_cv, 0))
            add_part(doc, name, on_slope(c), col, 30 if name.startswith("REF") else 0)
        if BT_NARROW_SIDE is None:      # the alternative anchor, in place but hidden: switch it on in the tree to look at it
            c = (anchor_narrow if sgn < 0 else narrow_ann).copy()
            c.translate(V(cu, btn_cv, 0))
            alt = add_part(doc, "ALT_ButtonAnchorNarrow_" + label, on_slope(c), (0.75, 0.30, 0.28))
            if App.GuiUp:
                try:
                    alt.ViewObject.Visibility = False
                except Exception:
                    pass

    hangup = make_hangup_adapter() if HU_ENABLE else None
    ins_set = None
    if hangup is not None:
        add_part(doc, "HangupAdapter", on_slope(hangup), (0.20, 0.50, 0.35))
        add_part(doc, "HookSwitchInsert", on_slope(make_hookswitch_insert(0.0)), (0.85, 0.80, 0.30))
        # three of them side by side for printing: pads thinner / nominal / thicker
        parts_ins = []
        for k, dv in enumerate(HU_INS_VARIANTS):
            si = make_hookswitch_insert(dv, marks=k + 1)
            si.translate(V(0, k * (HU_SW_H + 6.0), 0))
            parts_ins.append(si)
        ins_set = Part.makeCompound(parts_ins)

    if SHOW_REFERENCE:
        add_part(doc, "REF_ScreenModule", on_slope(make_ref_module()), (0.25, 0.45, 0.75), 55)
        add_part(doc, "REF_Cradle", on_slope(make_ref_cradle()), (0.65, 0.65, 0.65), 55)
        add_part(doc, "REF_Speaker", make_ref_speaker(), (0.55, 0.55, 0.30), 40)
        add_part(doc, "REF_DCJack", make_ref_jack(), (0.10, 0.45, 0.20), 30)
        add_part(doc, "REF_PhoneJack", make_ref_phonejack(), (0.80, 0.72, 0.50), 30)
        if HU_ENABLE:
            add_part(doc, "REF_HookSwitch", on_slope(make_ref_hookswitch()), (0.85, 0.55, 0.10), 30)

    doc.recompute()

    msg = ["", "Judicom model built (%d printed parts + 6 button parts)." % len(parts),
           "  Assembled body %.0f x %.0f x %.0f mm, slope %.0f deg, slope length %.1f mm"
           % (W, D, H, SLOPE_ANGLE, SLOPE_L),
           "  Cradle opening %.1f x %.1f mm at u=%.1f, v=%.1f"
           % (cradle_open_w, cradle_open_l, cradle_u0, cradle_v0),
           "  Screen window %.0f x %.0f mm centred at u=%.1f, v=%.1f;  strips %.0f x %.0f x %.0f mm"
           % (WIN_W, WIN_L, scr_cu, win_cv, STRIP_W, strip_l, STRIP_DEPTH)]
    for name, shp in parts.items():
        msg.append("  %-12s valid=%s solids=%d" % (name, shp.isValid(), len(shp.Solids)))
    msg.append("  Buttons: slider + anchor + frame each; M3 x %.0f screws, web behind the nuts %.2f mm, travel %.1f mm, "
               "frame slots +-%.1f mm" % (BT_SCREW_L, AN_WEB, BT_TRAVEL, BT_SLOT))
    msg.append("           narrow anchors (ButtonAnchorNarrow_Frank / _Ann, plate %.1f mm wide): %s"
               % (BT_NARROW_W, ("used on the %s button (BT_NARROW_SIDE)" % BT_NARROW_SIDE) if BT_NARROW_SIDE
                  else "exported as extra files and kept hidden in the model as ALT_ButtonAnchorNarrow_*; set BT_NARROW_SIDE to use one"))
    msg.append("           anchor ring %.1f mm thick, hole %.1f mm; nut ends %.1f mm above the barrel's cut end"
               % (BT_RING_T, BT_RING_ID, BT_STUB_END - (SLOPE_WALL + BT_RING_T + BT_NUT_T)))
    if HU_ENABLE:
        msg.append("  HookSwitchInsert_x3: three inserts (left to right, 1/2/3 grooves) with the slab pad %s mm thinner/thicker than nominal; nominal pads: slab %.1f, strip %.1f mm"
                   % (", ".join("%+.1f" % dv for dv in HU_INS_VARIANTS), HU_SW_T + 0.1 - HU_SLAB_H, HU_SW_T + 0.1 - HU_STRIP_H))
        msg.append("  Hang-up switch adapter (HangupAdapter): switch pin face at w=%.1f (cradle back edge -%.0f, collar ends -%.0f), "
                   "lever finger tip at w=%.1f; two flaps on the OUTSIDE of the collar wall, M3 x 10 + nut each"
                   % (HU_PIN_W, CRADLE_T, CAGE_DEPTH, HU_PIN_W + HU_FINGER_DROP))
    for w in layout_warnings():
        msg.append("  WARNING: " + w)

    if EXPORT_STL:
        jobs = [(n, parts[n], PRINT_ORIENT[n]) for n in parts] + [
            ("ButtonSlider_x2", slider, None),
            ("ButtonAnchor_Frank", use_anchor["Frank"], orient_button_flip),
            ("ButtonAnchor_Ann", use_anchor["Ann"], orient_button_flip),
            ("ButtonFrame_Frank", frame, orient_button_flip),
            ("ButtonFrame_Ann", frame_ann, orient_button_flip),
            ("ButtonAnchorNarrow_Frank", anchor_narrow, orient_button_flip),                          # only for the button next to the HDMI plug
            ("ButtonAnchorNarrow_Ann", narrow_ann, orient_button_flip),
            ] + ([("HangupAdapter", hangup, None), ("HookSwitchInsert_x3", ins_set, None)] if hangup is not None else []) + [
            ("DCJackFitTest", dc_jack_fit_test(parts["Back"]), orient_back),
            ("PhoneJackFitTest", phone_jack_fit_test(parts["SideLeft"]), orient_side_left)]
        for (name, shp, orient) in jobs:
            try:
                path, bb = export_stl("Judicom_" + name, shp, orient)
                fits = bb.XLength <= BED_X and bb.YLength <= BED_Y and bb.ZLength <= BED_Z
                msg.append("  %s  (%.0f x %.0f x %.0f mm)%s"
                           % (path, bb.XLength, bb.YLength, bb.ZLength, "" if fits else "  ** TOO BIG **"))
            except Exception as ex:
                msg.append("  STL export failed for %s: %s" % (name, ex))

    text = "\n".join(msg) + "\n"
    App.Console.PrintMessage(text)
    print(text)

    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.ActiveDocument.ActiveView.viewIsometric()
        Gui.SendMsgToActiveView("ViewFit")
    return doc


main()
