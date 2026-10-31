<line_geometry_contract>
Line width_px and height_px are signed endpoint deltas, not stroke thickness.
For a directed line from (sx, sy) to (tx, ty):
- left_px=min(sx,tx), top_px=min(sy,ty), width_px=tx-sx, height_px=ty-sy.
- Horizontal: height_px=0. Vertical: width_px=0.
- Both deltas may be non-zero, including a shallow diagonal.
- end_arrow=true marks (tx,ty); start_arrow=true marks (sx,sy). A negative delta
  can place the end arrow at the minimum coordinate. Do not choose the arrow flag
  from a fixed minimum/maximum corner.
- Use border_width_pt for stroke thickness.
- An arrow tip must stop on the target box boundary. Do not extend it into the box
  to compensate for the visible arrowhead. Check the actual segment, not just its bbox.
</line_geometry_contract>
