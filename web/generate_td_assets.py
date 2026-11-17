import os

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "td")

def save_svg(relative_path, content):
    full_path = os.path.join(ASSETS_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"Created: {relative_path}")

# ==============================================================================
# BUILDINGS
# ==============================================================================

def make_castle_svg(roof_color, flag_color, banner_color):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160">
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="6" stdDeviation="4" flood-color="#141a24" flood-opacity="0.35"/>
    </filter>
  </defs>
  <!-- Ground Shadow -->
  <ellipse cx="80" cy="144" rx="70" ry="14" fill="#000000" opacity="0.25"/>

  <!-- Main Stone Keep -->
  <rect x="42" y="70" width="76" height="68" rx="4" fill="#8d99ae" stroke="#2b2d42" stroke-width="3.5" filter="url(#shadow)"/>
  <rect x="46" y="74" width="68" height="60" fill="#a4b0c6"/>

  <!-- Stone Wall Bricks Texture -->
  <rect x="52" y="82" width="14" height="6" rx="1" fill="#758299"/>
  <rect x="74" y="82" width="16" height="6" rx="1" fill="#758299"/>
  <rect x="96" y="82" width="12" height="6" rx="1" fill="#758299"/>
  <rect x="62" y="94" width="16" height="6" rx="1" fill="#758299"/>
  <rect x="84" y="94" width="14" height="6" rx="1" fill="#758299"/>
  <rect x="54" y="106" width="14" height="6" rx="1" fill="#758299"/>
  <rect x="92" y="106" width="16" height="6" rx="1" fill="#758299"/>

  <!-- Main Keep Battlements -->
  <rect x="40" y="58" width="80" height="14" fill="#8d99ae" stroke="#2b2d42" stroke-width="3.5"/>
  <rect x="48" y="52" width="12" height="8" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>
  <rect x="74" y="52" width="12" height="8" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>
  <rect x="100" y="52" width="12" height="8" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>

  <!-- Left Tower -->
  <rect x="14" y="56" width="34" height="82" rx="3" fill="#8d99ae" stroke="#2b2d42" stroke-width="3.5"/>
  <rect x="17" y="60" width="28" height="74" fill="#a4b0c6"/>
  <rect x="12" y="46" width="38" height="12" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>
  <path d="M12 46 L31 16 L50 46 Z" fill="{roof_color}" stroke="#2b2d42" stroke-width="3.5"/>
  <!-- Left Flag -->
  <line x1="31" y1="16" x2="31" y2="4" stroke="#2b2d42" stroke-width="2.5"/>
  <path d="M31 4 L45 9 L31 15 Z" fill="{flag_color}" stroke="#2b2d42" stroke-width="1.5"/>

  <!-- Right Tower -->
  <rect x="112" y="56" width="34" height="82" rx="3" fill="#8d99ae" stroke="#2b2d42" stroke-width="3.5"/>
  <rect x="115" y="60" width="28" height="74" fill="#a4b0c6"/>
  <rect x="110" y="46" width="38" height="12" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>
  <path d="M110 46 L129 16 L148 46 Z" fill="{roof_color}" stroke="#2b2d42" stroke-width="3.5"/>
  <!-- Right Flag -->
  <line x1="129" y1="16" x2="129" y2="4" stroke="#2b2d42" stroke-width="2.5"/>
  <path d="M129 4 L143 9 L129 15 Z" fill="{flag_color}" stroke="#2b2d42" stroke-width="1.5"/>

  <!-- Center Spire -->
  <path d="M60 52 L80 18 L100 52 Z" fill="{roof_color}" stroke="#2b2d42" stroke-width="3.5"/>
  <line x1="80" y1="18" x2="80" y2="2" stroke="#2b2d42" stroke-width="3"/>
  <path d="M80 2 L98 8 L80 15 Z" fill="{flag_color}" stroke="#2b2d42" stroke-width="2"/>

  <!-- Arched Wooden Gate -->
  <path d="M64 138 L64 108 Q80 96 96 108 L96 138 Z" fill="#583115" stroke="#2b2d42" stroke-width="3"/>
  <line x1="80" y1="102" x2="80" y2="138" stroke="#361f0f" stroke-width="2.5"/>
  <!-- Iron Studs on Gate -->
  <circle cx="70" cy="115" r="1.8" fill="#ffd166"/>
  <circle cx="70" cy="128" r="1.8" fill="#ffd166"/>
  <circle cx="90" cy="115" r="1.8" fill="#ffd166"/>
  <circle cx="90" cy="128" r="1.8" fill="#ffd166"/>

  <!-- Faction Crest Banner above Gate -->
  <path d="M72 88 L88 88 L88 102 L80 108 L72 102 Z" fill="{banner_color}" stroke="#2b2d42" stroke-width="2"/>
  <circle cx="80" cy="96" r="3" fill="#ffffff"/>
</svg>'''

def make_watchtower_svg(flag_color):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 150" width="120" height="150">
  <!-- Shadow -->
  <ellipse cx="60" cy="136" rx="46" ry="10" fill="#000000" opacity="0.25"/>

  <!-- Tower Base & Shaft -->
  <path d="M36 132 L42 56 L78 56 L84 132 Z" fill="#8d99ae" stroke="#2b2d42" stroke-width="3.5"/>
  <path d="M40 128 L45 60 L75 60 L80 128 Z" fill="#a4b0c6"/>

  <!-- Arrow Slits -->
  <rect x="58" y="72" width="4" height="14" rx="2" fill="#2b2d42"/>
  <rect x="58" y="96" width="4" height="14" rx="2" fill="#2b2d42"/>

  <!-- Wooden Arched Door -->
  <path d="M52 132 L52 116 Q60 110 68 116 L68 132 Z" fill="#583115" stroke="#2b2d42" stroke-width="2.5"/>

  <!-- Tower Parapet Battlements -->
  <rect x="30" y="42" width="60" height="16" rx="2" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>
  <rect x="34" y="34" width="10" height="10" fill="#8d99ae" stroke="#2b2d42" stroke-width="2.5"/>
  <rect x="55" y="34" width="10" height="10" fill="#8d99ae" stroke="#2b2d42" stroke-width="2.5"/>
  <rect x="76" y="34" width="10" height="10" fill="#8d99ae" stroke="#2b2d42" stroke-width="2.5"/>

  <!-- Dual Flags -->
  <line x1="39" y1="34" x2="39" y2="12" stroke="#2b2d42" stroke-width="2.5"/>
  <path d="M39 12 L22 18 L39 24 Z" fill="{flag_color}" stroke="#2b2d42" stroke-width="1.5"/>

  <line x1="81" y1="34" x2="81" y2="12" stroke="#2b2d42" stroke-width="2.5"/>
  <path d="M81 12 L98 18 L81 24 Z" fill="{flag_color}" stroke="#2b2d42" stroke-width="1.5"/>

  <!-- Crest Banner -->
  <path d="M54 58 L66 58 L66 70 L60 74 L54 70 Z" fill="{flag_color}" stroke="#2b2d42" stroke-width="1.5"/>
</svg>'''

def make_barracks_svg(flag_color):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 120" width="140" height="120">
  <ellipse cx="70" cy="108" rx="55" ry="10" fill="#000000" opacity="0.25"/>
  <!-- Fortified Stone Block -->
  <rect x="25" y="44" width="90" height="62" rx="3" fill="#8d99ae" stroke="#2b2d42" stroke-width="3.5"/>
  <rect x="29" y="48" width="82" height="54" fill="#a4b0c6"/>

  <!-- Battlements -->
  <rect x="20" y="34" width="100" height="12" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>
  <rect x="26" y="26" width="12" height="10" fill="#8d99ae" stroke="#2b2d42" stroke-width="2.5"/>
  <rect x="48" y="26" width="12" height="10" fill="#8d99ae" stroke="#2b2d42" stroke-width="2.5"/>
  <rect x="80" y="26" width="12" height="10" fill="#8d99ae" stroke="#2b2d42" stroke-width="2.5"/>
  <rect x="102" y="26" width="12" height="10" fill="#8d99ae" stroke="#2b2d42" stroke-width="2.5"/>

  <!-- Double Wooden Doors -->
  <rect x="52" y="72" width="36" height="34" fill="#583115" stroke="#2b2d42" stroke-width="3"/>
  <line x1="70" y1="72" x2="70" y2="106" stroke="#2b2d42" stroke-width="2"/>
  <circle cx="64" cy="90" r="2" fill="#ffd166"/>
  <circle cx="76" cy="90" r="2" fill="#ffd166"/>

  <!-- Crest Banner hanging over door -->
  <path d="M62 46 L78 46 L78 62 L70 68 L62 62 Z" fill="{flag_color}" stroke="#2b2d42" stroke-width="2"/>
  <polygon points="70,52 73,58 67,58" fill="#ffffff"/>
</svg>'''

def make_relic_shrine_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 170" width="160" height="170">
  <defs>
    <radialGradient id="relicGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffe600" stop-opacity="0.8"/>
      <stop offset="60%" stop-color="#ffb703" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#fb8500" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <!-- Ground Shadow -->
  <ellipse cx="80" cy="150" rx="60" ry="12" fill="#000000" opacity="0.3"/>

  <!-- Stepped Ancient Altar Dais -->
  <polygon points="20,146 140,146 128,124 32,124" fill="#6c757d" stroke="#2b2d42" stroke-width="3.5"/>
  <polygon points="36,124 124,124 116,106 44,106" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>

  <!-- Ancient Carved Runes on Stone -->
  <path d="M50 134 L54 140 L58 134 M76 132 L84 142 L80 132 M102 136 L108 136 L105 142" stroke="#ffb703" stroke-width="2.5" stroke-linecap="round"/>

  <!-- Twin Stone Monolith Pillars -->
  <path d="M38 106 L44 32 L58 32 L64 106 Z" fill="#6c757d" stroke="#2b2d42" stroke-width="3.5"/>
  <path d="M48 42 L52 48 L48 54 M52 70 L50 78" stroke="#ffb703" stroke-width="2" stroke-linecap="round"/>

  <path d="M96 106 L102 32 L116 32 L122 106 Z" fill="#6c757d" stroke="#2b2d42" stroke-width="3.5"/>
  <path d="M106 42 L110 48 L106 54 M110 70 L108 78" stroke="#ffb703" stroke-width="2" stroke-linecap="round"/>

  <!-- Relic Golden Aura Aura Pulse -->
  <circle cx="80" cy="52" r="42" fill="url(#relicGlow)"/>

  <!-- Floating Golden Crystal Monolith -->
  <polygon points="80,18 96,52 80,86 64,52" fill="#ffd166" stroke="#d48b00" stroke-width="3"/>
  <polygon points="80,18 96,52 80,86" fill="#ffe066" opacity="0.8"/>
  <polygon points="80,26 90,52 80,78 70,52" fill="#ffffff" opacity="0.5"/>
</svg>'''

# ==============================================================================
# CHARACTERS / UNITS (Cartoon Soldiers matching reference image)
# ==============================================================================

def make_knight_guard_svg(team_color):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <!-- Shadow -->
  <ellipse cx="40" cy="72" rx="24" ry="6" fill="#000000" opacity="0.25"/>

  <!-- Steel Boots -->
  <ellipse cx="30" cy="68" rx="6" ry="4" fill="#495057" stroke="#212529" stroke-width="2"/>
  <ellipse cx="48" cy="68" rx="6" ry="4" fill="#495057" stroke="#212529" stroke-width="2"/>

  <!-- Armored Body / Tunic -->
  <path d="M26 38 L54 38 L50 64 L30 64 Z" fill="{team_color}" stroke="#212529" stroke-width="3"/>
  <!-- Belt -->
  <rect x="28" y="52" width="24" height="5" fill="#583115" stroke="#212529" stroke-width="1.5"/>
  <rect x="38" y="51" width="4" height="7" fill="#ffd166"/>

  <!-- Knight Pot Helm -->
  <circle cx="40" cy="24" r="16" fill="#ced4da" stroke="#212529" stroke-width="3"/>
  <!-- Helmet Brow & Visor Slit -->
  <path d="M28 24 L52 24" stroke="#212529" stroke-width="4" stroke-linecap="round"/>
  <path d="M30 24 L50 24" stroke="#ffd166" stroke-width="1.5" stroke-linecap="round"/>
  <!-- Helmet Plume / Crest -->
  <path d="M38 8 C38 0 46 2 46 8 Z" fill="{team_color}" stroke="#212529" stroke-width="2"/>

  <!-- Big Steel Tower Shield (Left Arm) -->
  <path d="M12 28 L30 28 L28 58 Q21 68 12 58 Z" fill="#6c757d" stroke="#212529" stroke-width="3"/>
  <path d="M15 31 L27 31 L25 55 Q20 63 15 55 Z" fill="{team_color}"/>
  <!-- Shield Cross -->
  <rect x="18" y="38" width="5" height="14" fill="#ffffff"/>
  <rect x="14" y="42" width="13" height="5" fill="#ffffff"/>

  <!-- Steel Broadsword (Right Arm) -->
  <path d="M52 46 L68 28 L72 32 L56 50 Z" fill="#dee2e6" stroke="#212529" stroke-width="2.5"/>
  <line x1="50" y1="44" x2="56" y2="52" stroke="#ffd166" stroke-width="3" stroke-linecap="round"/>
  <circle cx="48" cy="42" r="2.5" fill="#ffd166"/>
</svg>'''

def make_rogue_raider_svg(team_color):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <!-- Shadow -->
  <ellipse cx="40" cy="72" rx="22" ry="5" fill="#000000" opacity="0.25"/>

  <!-- Running Boots -->
  <ellipse cx="24" cy="68" rx="6" ry="4" fill="#343a40" stroke="#1b1d20" stroke-width="2"/>
  <ellipse cx="54" cy="64" rx="6" ry="4" fill="#343a40" stroke="#1b1d20" stroke-width="2"/>

  <!-- Rogue Cloak & Leathers -->
  <path d="M26 36 L54 36 L48 62 L32 62 Z" fill="{team_color}" stroke="#1b1d20" stroke-width="3"/>

  <!-- Hood & Shadow Mask (Like goblin/rogue in image) -->
  <circle cx="40" cy="24" r="14" fill="#2b2d42" stroke="#1b1d20" stroke-width="3"/>
  <path d="M26 24 Q40 8 54 24 Z" fill="{team_color}" stroke="#1b1d20" stroke-width="2.5"/>

  <!-- Glowing Yellow Eyes -->
  <circle cx="35" cy="24" r="2.5" fill="#ffd166"/>
  <circle cx="45" cy="24" r="2.5" fill="#ffd166"/>

  <!-- Dual Curved Daggers -->
  <!-- Left Dagger -->
  <path d="M16 46 Q22 36 28 42 L24 46 Z" fill="#e9ecef" stroke="#1b1d20" stroke-width="2"/>
  <!-- Right Dagger -->
  <path d="M64 42 Q58 32 52 38 L56 42 Z" fill="#e9ecef" stroke="#1b1d20" stroke-width="2"/>
</svg>'''

def make_siege_cannon_svg(team_color):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 80" width="90" height="80">
  <!-- Shadow -->
  <ellipse cx="45" cy="70" rx="34" ry="7" fill="#000000" opacity="0.28"/>

  <!-- Wooden Carriage Chassis -->
  <polygon points="18,60 72,60 64,48 26,48" fill="#583115" stroke="#212529" stroke-width="2.5"/>

  <!-- Heavy Iron Cannon Barrel (Angled Upward) -->
  <path d="M20 48 L64 22 L72 32 L30 58 Z" fill="#343a40" stroke="#1b1d20" stroke-width="3"/>
  <ellipse cx="68" cy="27" rx="5" ry="7" fill="#1b1d20" transform="rotate(-30 68 27)"/>
  <!-- Team Color Ring on Barrel -->
  <path d="M38 38 L44 34 L48 42 L42 46 Z" fill="{team_color}"/>

  <!-- Big Wooden Wheel with Iron Rim -->
  <circle cx="45" cy="58" r="14" fill="#583115" stroke="#212529" stroke-width="3"/>
  <circle cx="45" cy="58" r="11" fill="none" stroke="#ffd166" stroke-width="1.5"/>
  <circle cx="45" cy="58" r="4" fill="#212529"/>
  <line x1="33" y1="58" x2="57" y2="58" stroke="#212529" stroke-width="2"/>
  <line x1="45" y1="46" x2="45" y2="70" stroke="#212529" stroke-width="2"/>

  <!-- Stack of Cannonballs -->
  <circle cx="78" cy="62" r="5" fill="#212529"/>
  <circle cx="72" cy="65" r="5" fill="#343a40"/>
  <circle cx="77" cy="68" r="4" fill="#495057"/>
</svg>'''

def make_flying_scout_svg(team_color):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80" width="80" height="80">
  <!-- Soft Flying Shadow on Ground Below -->
  <ellipse cx="40" cy="74" rx="16" ry="4" fill="#000000" opacity="0.2"/>

  <!-- Scout Falcon / Gryphon (Spread Wings) -->
  <!-- Left Wing -->
  <path d="M40 38 Q18 14 6 26 Q24 38 40 44 Z" fill="#7f4f24" stroke="#212529" stroke-width="2.5"/>
  <path d="M38 38 Q20 20 12 28 Q25 36 38 42 Z" fill="{team_color}" opacity="0.85"/>

  <!-- Right Wing -->
  <path d="M40 38 Q62 14 74 26 Q56 38 40 44 Z" fill="#7f4f24" stroke="#212529" stroke-width="2.5"/>
  <path d="M42 38 Q60 20 68 28 Q55 36 42 42 Z" fill="{team_color}" opacity="0.85"/>

  <!-- Tail Feathers -->
  <polygon points="36,44 44,44 48,58 32,58" fill="#583115" stroke="#212529" stroke-width="2"/>

  <!-- Bird Body & Head -->
  <ellipse cx="40" cy="38" rx="8" ry="12" fill="#936639" stroke="#212529" stroke-width="2.5"/>
  <circle cx="40" cy="24" r="7" fill="#ffffff" stroke="#212529" stroke-width="2"/>
  <!-- Sharp Golden Beak -->
  <polygon points="38,22 42,22 40,15" fill="#ffd166" stroke="#212529" stroke-width="1.5"/>
  <!-- Eyes -->
  <circle cx="37" cy="23" r="1.5" fill="#212529"/>
  <circle cx="43" cy="23" r="1.5" fill="#212529"/>
</svg>'''

# ==============================================================================
# ENVIRONMENT DECORATIONS (Trees, Rocks, Fences, Huts matching image)
# ==============================================================================

def make_cartoon_tree_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 100" width="90" height="100">
  <ellipse cx="45" cy="92" rx="28" ry="7" fill="#000000" opacity="0.22"/>
  <!-- Brown Trunk -->
  <path d="M40 92 L42 62 L48 62 L50 92 Z" fill="#6f4e37" stroke="#382923" stroke-width="2.5"/>

  <!-- Fluffy Cartoon Green Foliage Lobes (Like reference image) -->
  <circle cx="32" cy="52" r="20" fill="#52b788" stroke="#1b4332" stroke-width="3"/>
  <circle cx="58" cy="52" r="20" fill="#52b788" stroke="#1b4332" stroke-width="3"/>
  <circle cx="45" cy="34" r="24" fill="#74c69d" stroke="#1b4332" stroke-width="3"/>
  <!-- Highlight Lobes -->
  <circle cx="40" cy="28" r="10" fill="#95d5b2"/>
  <circle cx="52" cy="46" r="8" fill="#95d5b2"/>
</svg>'''

def make_rock_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 45" width="60" height="45">
  <ellipse cx="30" cy="38" rx="24" ry="6" fill="#000000" opacity="0.22"/>
  <path d="M12 36 Q10 22 24 14 Q42 10 50 24 Q54 34 46 38 Z" fill="#8d99ae" stroke="#2b2d42" stroke-width="3"/>
  <path d="M18 30 Q16 20 28 16 Q38 14 44 24" fill="#a4b0c6"/>
</svg>'''

def make_hut_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 90" width="90" height="90">
  <ellipse cx="45" cy="80" rx="36" ry="8" fill="#000000" opacity="0.25"/>
  <!-- Thatched Hut Body -->
  <circle cx="45" cy="52" r="26" fill="#583115" stroke="#212529" stroke-width="3"/>
  <!-- Thatched Straw Cone Roof -->
  <path d="M14 56 L45 16 L76 56 Q45 64 14 56 Z" fill="#d4a373" stroke="#212529" stroke-width="3"/>
  <path d="M22 52 L45 22 L68 52" stroke="#a98467" stroke-width="2"/>
  <!-- Small Dark Doorway -->
  <ellipse cx="45" cy="62" rx="7" ry="9" fill="#1b1d20"/>
</svg>'''

def make_fence_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 40" width="60" height="40">
  <ellipse cx="30" cy="36" rx="26" ry="3" fill="#000000" opacity="0.2"/>
  <!-- Posts -->
  <rect x="8" y="10" width="6" height="26" rx="1" fill="#7f4f24" stroke="#212529" stroke-width="2"/>
  <rect x="27" y="10" width="6" height="26" rx="1" fill="#7f4f24" stroke="#212529" stroke-width="2"/>
  <rect x="46" y="10" width="6" height="26" rx="1" fill="#7f4f24" stroke="#212529" stroke-width="2"/>
  <!-- Rails -->
  <rect x="6" y="14" width="48" height="5" rx="1" fill="#936639" stroke="#212529" stroke-width="1.8"/>
  <rect x="6" y="24" width="48" height="5" rx="1" fill="#936639" stroke="#212529" stroke-width="1.8"/>
</svg>'''

# ==============================================================================
# MAIN GENERATOR ROUTINE
# ==============================================================================

if __name__ == "__main__":
    print("Generating Cartoon Tower Defense Game Assets...")

    # Buildings
    save_svg("buildings/castle_p1.svg", make_castle_svg("#3a86ff", "#00b4d8", "#3a86ff")) # P1 Cyan/Blue
    save_svg("buildings/castle_p2.svg", make_castle_svg("#e63946", "#ff4d6d", "#e63946")) # P2 Crimson/Red
    save_svg("buildings/castle_neutral.svg", make_castle_svg("#6c757d", "#adb5bd", "#6c757d"))
    save_svg("buildings/tower_stone.svg", make_watchtower_svg("#e63946"))
    save_svg("buildings/barracks.svg", make_barracks_svg("#3a86ff"))
    save_svg("buildings/relic_shrine.svg", make_relic_shrine_svg())

    # Units
    save_svg("units/knight_guard_p1.svg", make_knight_guard_svg("#3a86ff"))
    save_svg("units/knight_guard_p2.svg", make_knight_guard_svg("#e63946"))
    save_svg("units/rogue_raider_p1.svg", make_rogue_raider_svg("#3a86ff"))
    save_svg("units/rogue_raider_p2.svg", make_rogue_raider_svg("#e63946"))
    save_svg("units/cannon_siege_p1.svg", make_siege_cannon_svg("#3a86ff"))
    save_svg("units/cannon_siege_p2.svg", make_siege_cannon_svg("#e63946"))
    save_svg("units/eagle_scout_p1.svg", make_flying_scout_svg("#3a86ff"))
    save_svg("units/eagle_scout_p2.svg", make_flying_scout_svg("#e63946"))

    # Environment
    save_svg("env/tree_large.svg", make_cartoon_tree_svg())
    save_svg("env/rock.svg", make_rock_svg())
    save_svg("env/hut.svg", make_hut_svg())
    save_svg("env/fence.svg", make_fence_svg())

    print("All Cartoon Tower Defense Game Assets Generated Successfully!")
