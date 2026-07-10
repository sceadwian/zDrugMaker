#!/usr/bin/env python3
"""
zpyGEMINI.py
A standard-compliant GUI viewer for the Universal Character Master Schema (zpy).
this was the Gemini version which was marginally better than Grock but infinitely better than GPT's.
Claude's is probably my favourite but this gemini version came out quite nice as well so I will use it as basis for an editor.

Naming Standard Convention:
Historically, scripts utilizing standard character schema structures were prefixed with "py".
Moving forward, compliance with the zpy schema is indicated using the "zpy" prefix.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import io

# --- EMbedded DEFAULT CANONICAL DATA ---
DEFAULT_CSV_CONTENT = """schema_version,character_id,first_name,last_name,display_name,short_name,sex,birth_year,nationality,religion,left2right,species,height_cm,weight_kg,description,strength,stamina,speed,agility,coordination,dexterity,balance,recovery,resilience,metabolism,lifespan,intelligence,perception,focus,memory,creativity,learning,technical_aptitude,tactical_awareness,willpower,faith,courage,composure,discipline,determination,adaptability,patience,risk_assessment,charisma,empathy,conversation,deception,loyalty,aggression
1.0,CHR0001,Amara,Okafor,Amara Okafor,AMA,F,1992,Nigerian,christian,46,human,174,67,"Calm, persuasive organizer with strong endurance and sound judgment.",58,81,66,68,73,70,72,78,86,62,74,79,77,82,75,67,80,63,76,88,71,77,89,87,85,74,83,88,82,86,84,42,89,36
1.0,CHR0002,Luca,Moretti,Luca Moretti,LUC,M,1998,Italian,atheist,58,human,181,76,"Fast, technically gifted risk-taker who thrives under competition.",64,74,91,88,92,86,87,72,67,81,69,71,84,78,63,83,76,88,81,73,8,86,69,62,82,85,49,61,77,55,73,68,64,72
1.0,CHR0003,Priya,Raman,Priya Raman,PRI,F,1987,Indian,hindu,39,human,165,59,"Analytical engineer with exceptional focus, memory, and patience.",43,63,48,57,69,82,65,61,76,55,82,94,79,93,91,84,92,96,74,85,62,58,88,95,89,77,92,94,58,70,67,31,83,22
1.0,CHR0004,Mateo,Álvarez,Mateo Álvarez,MAT,M,1995,Argentinian,christian,51,human,177,73,"Creative team player with excellent movement, conversation, and courage.",61,84,85,90,89,78,88,77,73,79,71,73,82,76,68,91,79,62,86,80,54,88,75,72,84,89,61,73,86,79,88,52,87,68
1.0,CHR0005,Hana,Sato,Hana Sato,HAN,F,2000,Japanese,buddhist,44,human,160,52,Quietly observant specialist with elite dexterity and composure.,39,69,71,84,90,95,91,74,72,76,86,86,94,92,87,78,88,89,87,82,48,65,94,91,78,80,90,95,53,74,58,63,81,27
1.0,CHR0006,Omar,Haddad,Omar Haddad,OMA,M,1984,Jordanian,muslim,63,human,185,88,"Steady veteran leader with high loyalty, resilience, and faith.",78,72,54,56,71,66,74,70,91,48,77,78,81,84,82,61,72,69,90,92,91,89,91,90,88,67,85,89,75,77,76,37,96,59
1.0,CHR0007,Sofia,Petrova,Sofia Petrova,SOF,F,1993,Bulgarian,atheist,31,human,172,64,Adaptable negotiator who reads people well and conceals intentions.,51,68,67,75,74,79,73,69,78,66,73,84,90,76,83,87,81,58,82,80,5,71,86,74,79,93,78,87,88,82,92,91,57,41
1.0,CHR0008,Ethan,Brooks,Ethan Brooks,ETH,M,2001,Canadian,christian,55,human,190,94,"Powerful competitor with high courage, aggression, and recovery.",93,79,76,67,72,58,75,89,88,84,68,59,70,66,55,48,64,57,73,86,47,94,62,71,92,63,44,57,69,51,64,39,84,93
1.0,CHR0009,Noor,Rahman,Noor Rahman,NOO,F,1997,Bangladeshi,muslim,42,human,168,60,"Empathetic medic with high learning, resilience, and careful judgment.",45,72,55,63,78,88,70,82,89,64,84,88,85,90,86,72,93,84,68,87,78,76,92,88,83,81,89,96,70,96,85,25,92,18
1.0,CHR0010,Kwame,Mensah,Kwame Mensah,KWA,M,1990,Ghanaian,christian,47,human,179,79,Resourceful all-rounder with balanced physical and social abilities.,74,82,77,75,78,73,79,80,84,75,78,76,80,77,72,79,78,75,80,84,65,83,81,79,86,84,75,82,80,78,81,52,86,61
1.0,CHR0011,Ingrid,Nilsen,Ingrid Nilsen,ING,F,1989,Norwegian,atheist,27,human,178,70,Endurance-oriented explorer with strong patience and environmental resilience.,67,94,70,72,74,68,85,86,95,70,88,75,89,80,78,69,77,71,78,91,4,90,88,86,93,82,91,86,62,74,65,28,88,38
1.0,CHR0012,Javier,Cruz,Javier Cruz,JAV,M,1996,Mexican,christian,60,human,175,72,Charming improviser with strong creativity and a taste for calculated danger.,59,73,82,83,84,80,81,71,68,78,67,74,76,64,61,94,75,67,72,70,52,87,65,55,78,92,47,68,93,66,95,84,61,66
1.0,CHR0013,Mei,Chen,Mei Chen,MEI,F,1985,Chinese,buddhist,53,human,163,55,"Methodical strategist with exceptional memory, discipline, and foresight.",41,65,52,61,72,81,76,66,80,57,91,96,88,95,97,76,91,87,95,90,44,62,96,98,88,73,96,98,56,65,63,71,79,24
1.0,CHR0014,Aiden,Murphy,Aiden Murphy,AID,M,2003,Irish,atheist,36,human,183,80,Energetic young athlete with elite speed but inconsistent discipline.,70,86,96,92,85,72,87,91,73,95,72,62,74,57,54,70,78,56,66,68,3,91,58,48,81,83,38,52,81,60,79,58,73,77
1.0,CHR0015,Fatima,Zahra,Fatima Zahra,FAT,F,1991,Moroccan,muslim,57,human,170,63,"Principled diplomat with strong faith, empathy, and conversational skill.",47,70,58,65,71,74,72,73,85,61,83,85,83,87,84,73,86,65,79,93,97,80,93,92,87,76,94,92,89,94,96,33,95,20
1.0,CHR0016,Darius,Cole,Darius Cole,DAR,M,1988,American,christian,72,human,193,103,"Imposing enforcer with high strength, loyalty, and tactical discipline.",97,82,63,59,76,60,82,83,94,69,65,67,79,81,64,43,69,61,88,94,69,96,84,89,95,60,67,80,71,48,62,46,97,91
1.0,CHR0017,Elena,Varga,Elena Varga,ELE,F,1994,Hungarian,atheist,49,human,176,66,Clever political operator with exceptional deception and social perception.,46,61,62,69,70,77,68,65,75,63,76,91,93,86,89,88,84,60,91,85,2,68,90,78,84,91,87,90,94,71,97,98,45,40
1.0,CHR0018,Tenzin,Dorje,Tenzin Dorje,TEN,M,1979,Tibetan,buddhist,34,human,171,65,Patient spiritual mentor with outstanding composure and emotional insight.,52,75,49,60,67,69,83,79,92,52,95,87,92,97,88,74,85,49,76,98,99,82,99,96,86,84,99,93,78,98,90,12,94,8
1.0,CHR0019,Zara,Khan,Zara Khan,ZAR,F,2002,British,muslim,29,human,167,58,"Quick-learning scout with strong perception, agility, and adaptability.",44,77,89,94,86,91,90,84,79,90,81,82,96,88,80,85,94,78,89,83,59,84,82,80,87,97,72,91,76,81,82,73,85,54
1.0,CHR0020,Gabriel,Silva,Gabriel Silva,GAB,M,1986,Brazilian,christian,41,human,182,83,"Experienced field leader combining athleticism, creativity, and teamwork.",80,88,81,84,87,76,85,85,87,72,75,78,86,83,74,90,80,69,92,90,63,92,87,84,93,88,76,85,87,80,86,56,91,74
"""

# --- ATTRIBUTE SCHEMA MAPPINGS ---
PHYSICAL_ATTRS = [
    ("strength", "Strength"),
    ("stamina", "Stamina"),
    ("speed", "Speed"),
    ("agility", "Agility"),
    ("coordination", "Coordination"),
    ("dexterity", "Dexterity"),
    ("balance", "Balance"),
    ("recovery", "Recovery"),
    ("resilience", "Resilience"),
    ("metabolism", "Metabolism"),
    ("lifespan", "Lifespan"),
]

COGNITIVE_ATTRS = [
    ("intelligence", "Intelligence"),
    ("perception", "Perception"),
    ("focus", "Focus"),
    ("memory", "Memory"),
    ("creativity", "Creativity"),
    ("learning", "Learning"),
    ("technical_aptitude", "Technical Aptitude"),
    ("tactical_awareness", "Tactical Awareness"),
]

PSYCHOLOGICAL_ATTRS = [
    ("willpower", "Willpower"),
    ("faith", "Faith"),
    ("courage", "Courage"),
    ("composure", "Composure"),
    ("discipline", "Discipline"),
    ("determination", "Determination"),
    ("adaptability", "Adaptability"),
    ("patience", "Patience"),
    ("risk_assessment", "Risk Assessment"),
]

SOCIAL_ATTRS = [
    ("charisma", "Charisma"),
    ("empathy", "Empathy"),
    ("conversation", "Conversation"),
    ("deception", "Deception"),
    ("loyalty", "Loyalty"),
    ("aggression", "Aggression"),
]


# --- INTERPRETATION COLOR & DESCRIPTION UTILITIES ---
def get_rating_color(val):
    if val <= 9:
        return "#991B1B"  # Dark Red
    elif val <= 24:
        return "#DC2626"  # Medium Red
    elif val <= 39:
        return "#D97706"  # Orange-Yellow
    elif val <= 59:
        return "#4B5563"  # Gray
    elif val <= 74:
        return "#65A30D"  # Yellow-Green
    elif val <= 89:
        return "#16A34A"  # Green
    elif val <= 98:
        return "#0D9488"  # Teal-Green
    else:
        return "#7C3AED"  # Purple (99 Max Represented)


def get_rating_desc(val):
    if val <= 9:
        return "Extremely low"
    elif val <= 24:
        return "Very low"
    elif val <= 39:
        return "Below average"
    elif val <= 59:
        return "Average range"
    elif val <= 74:
        return "Above average"
    elif val <= 89:
        return "Excellent"
    elif val <= 98:
        return "Exceptional"
    else:
        return "Maximum (99)"


def get_political_label(val):
    if val <= 15:
        return "Far Left"
    elif val <= 39:
        return "Left-Leaning"
    elif val <= 44:
        return "Center-Left"
    elif val <= 56:
        return "Political Centre"
    elif val <= 61:
        return "Center-Right"
    elif val <= 84:
        return "Right-Leaning"
    else:
        return "Far Right"


class ZpyCharacterViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("zpy Schema Character Visualizer")
        self.root.geometry("1180x800")
        self.root.minsize(1020, 600)

        self.characters = []
        self.filtered_characters = []
        self.attribute_widgets = {}

        # Configuration variables
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.sim_year_var = tk.StringVar(value="2026")
        self.sim_year_var.trace_add("write", self.on_sim_year_change)
        self.status_var = tk.StringVar(value="Ready")
        self.selected_char_name = tk.StringVar(value="No Character Selected")

        self.build_ui()
        self.load_initial_data()

    def build_ui(self):
        # 1. TOP BANNER (Naming and Compliance Standard Notice)
        banner = tk.Frame(self.root, bg="#1E293B", padx=15, pady=10)
        banner.pack(fill="x", side="top")

        title_frame = tk.Frame(banner, bg="#1E293B")
        title_frame.pack(side="left", fill="y")

        lbl_app_title = tk.Label(
            title_frame,
            text="zpy SCHEMA COMPLIANT VISUALIZATION",
            font=("Arial", 12, "bold"),
            fg="#F8FAFC",
            bg="#1E293B",
        )
        lbl_app_title.pack(anchor="w")

        lbl_naming_rule = tk.Label(
            title_frame,
            text="Notice: Scripts using this schema adopt the 'zpy' prefix (e.g. zpyCharacterViewer) to distinguish from legacy 'py' versions.",
            font=("Arial", 9, "italic"),
            fg="#94A3B8",
            bg="#1E293B",
        )
        lbl_naming_rule.pack(anchor="w")

        # Top Control Bar (File management & Sim Configuration)
        ctrl_frame = tk.Frame(banner, bg="#1E293B")
        ctrl_frame.pack(side="right", fill="y")

        lbl_sim_year = tk.Label(
            ctrl_frame,
            text="Simulation Year:",
            fg="#F8FAFC",
            bg="#1E293B",
            font=("Arial", 9, "bold"),
        )
        lbl_sim_year.pack(side="left", padx=(0, 5))

        ent_sim_year = tk.Entry(
            ctrl_frame, textvariable=self.sim_year_var, width=6, justify="center"
        )
        ent_sim_year.pack(side="left", padx=(0, 15))

        btn_load = tk.Button(
            ctrl_frame,
            text="Load CSV File (UTF-8 with BOM)",
            command=self.load_from_file,
            bg="#0F766E",
            fg="white",
            relief="flat",
            padx=10,
            activebackground="#0D9488",
            activeforeground="white",
        )
        btn_load.pack(side="right")

        # 2. MAIN PANED WORKSPACE
        self.paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

        # Left Sidebar (Roster Selection)
        sidebar_frame = ttk.Frame(self.paned, padding=10)
        self.paned.add(sidebar_frame, weight=1)

        # Search Block
        search_frame = ttk.Frame(sidebar_frame)
        search_frame.pack(fill="x", pady=(0, 10))

        lbl_search = ttk.Label(
            search_frame, text="Search Roster:", font=("Arial", 9, "bold")
        )
        lbl_search.pack(anchor="w", pady=(0, 2))

        ent_search = ttk.Entry(search_frame, textvariable=self.search_var)
        ent_search.pack(fill="x")

        # Listbox Roster List
        list_label_frame = ttk.Frame(sidebar_frame)
        list_label_frame.pack(fill="x")

        self.lbl_roster_count = ttk.Label(
            list_label_frame, text="Characters:", font=("Arial", 9, "bold")
        )
        self.lbl_roster_count.pack(anchor="w", side="left")

        # Scrollable Listbox
        self.roster_listbox = tk.Listbox(
            sidebar_frame,
            selectmode=tk.SINGLE,
            exportselection=False,
            font=("Courier", 10),
        )
        self.roster_listbox.pack(fill="both", expand=True, side="left")
        self.roster_listbox.bind("<<ListboxSelect>>", self.on_list_select)

        scroll_list = ttk.Scrollbar(
            sidebar_frame, orient="vertical", command=self.roster_listbox.yview
        )
        scroll_list.pack(fill="y", side="right")
        self.roster_listbox.config(yscrollcommand=scroll_list.set)

        # Right Detail Area (Scrollable to prevent offscreen truncation)
        right_frame = ttk.Frame(self.paned)
        self.paned.add(right_frame, weight=3)

        # Active Character Header
        header_details_frame = tk.Frame(right_frame, bg="#F1F5F9", pady=8, padx=12)
        header_details_frame.pack(fill="x")

        self.lbl_char_header = tk.Label(
            header_details_frame,
            textvariable=self.selected_char_name,
            font=("Arial", 16, "bold"),
            bg="#F1F5F9",
            fg="#1E293B",
        )
        self.lbl_char_header.pack(anchor="w")

        # Setup Scrollable Layout
        scroll_container = ttk.Frame(right_frame)
        scroll_container.pack(fill="both", expand=True)

        self.canvas_scroll = tk.Canvas(
            scroll_container, borderwidth=0, highlightthickness=0
        )
        scroll_v = ttk.Scrollbar(
            scroll_container, orient="vertical", command=self.canvas_scroll.yview
        )
        self.scroll_content = ttk.Frame(self.canvas_scroll, padding=10)

        self.scroll_content.bind(
            "<Configure>",
            lambda e: self.canvas_scroll.configure(
                scrollregion=self.canvas_scroll.bbox("all")
            ),
        )
        self.canvas_window = self.canvas_scroll.create_window(
            (0, 0), window=self.scroll_content, anchor="nw"
        )
        self.canvas_scroll.bind(
            "<Configure>",
            lambda e: self.canvas_scroll.itemconfig(
                self.canvas_window, width=e.width
            ),
        )

        self.canvas_scroll.configure(yscrollcommand=scroll_v.set)
        self.canvas_scroll.pack(side="left", fill="both", expand=True)
        scroll_v.pack(side="right", fill="y")

        # Identity & Dimensions Section
        self.build_identity_section()

        # Attributes Section Grid (2x2 Structure)
        self.build_attributes_grid()

        # 3. STATUS BAR
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            padding=(5, 2),
        )
        status_bar.pack(side="bottom", fill="x")

    def build_identity_section(self):
        bio_group = ttk.LabelFrame(
            self.scroll_content, text="Identity & Dimensions", padding=12
        )
        bio_group.pack(fill="x", pady=(0, 10))

        # Multi-column layout for fundamental attributes
        grid_frame = ttk.Frame(bio_group)
        grid_frame.pack(fill="x")

        # Construct fields dynamically
        labels = [
            ("Character ID:", 0, 0),
            ("Short Name:", 0, 2),
            ("Sex:", 0, 4),
            ("Species:", 0, 6),
            ("Dynamic Age:", 1, 0),
            ("Nationality:", 1, 2),
            ("Religion:", 1, 4),
            ("Birth Year:", 1, 6),
            ("Height:", 2, 0),
            ("Weight:", 2, 2),
            ("Schema Row Ver:", 2, 4),
        ]

        for text, r, c in labels:
            lbl = ttk.Label(grid_frame, text=text, font=("Arial", 9, "bold"))
            lbl.grid(row=r, column=c, sticky="e", padx=(10, 5), pady=4)

        # Keep widget hooks for updates
        self.lbl_id = ttk.Label(grid_frame, text="—")
        self.lbl_id.grid(row=0, column=1, sticky="w", pady=4)

        self.lbl_short = ttk.Label(grid_frame, text="—")
        self.lbl_short.grid(row=0, column=3, sticky="w", pady=4)

        self.lbl_sex = ttk.Label(grid_frame, text="—")
        self.lbl_sex.grid(row=0, column=5, sticky="w", pady=4)

        self.lbl_species = ttk.Label(grid_frame, text="—")
        self.lbl_species.grid(row=0, column=7, sticky="w", pady=4)

        self.lbl_age = ttk.Label(grid_frame, text="—", font=("Arial", 9, "bold"))
        self.lbl_age.grid(row=1, column=1, sticky="w", pady=4)

        self.lbl_nat = ttk.Label(grid_frame, text="—")
        self.lbl_nat.grid(row=1, column=3, sticky="w", pady=4)

        self.lbl_rel = ttk.Label(grid_frame, text="—")
        self.lbl_rel.grid(row=1, column=5, sticky="w", pady=4)

        self.lbl_birth = ttk.Label(grid_frame, text="—")
        self.lbl_birth.grid(row=1, column=7, sticky="w", pady=4)

        self.lbl_height = ttk.Label(grid_frame, text="—")
        self.lbl_height.grid(row=2, column=1, sticky="w", pady=4)

        self.lbl_weight = ttk.Label(grid_frame, text="—")
        self.lbl_weight.grid(row=2, column=3, sticky="w", pady=4)

        self.lbl_version = ttk.Label(grid_frame, text="—")
        self.lbl_version.grid(row=2, column=5, sticky="w", pady=4)

        # Political Spectrum Slider
        lbl_pol = ttk.Label(
            grid_frame, text="Political Line:", font=("Arial", 9, "bold")
        )
        lbl_pol.grid(row=3, column=0, sticky="e", padx=(10, 5), pady=8)

        self.pol_canvas = tk.Canvas(
            grid_frame,
            width=200,
            height=20,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#CBD5E1",
        )
        self.pol_canvas.grid(row=3, column=1, columnspan=4, sticky="w", pady=8)

        self.lbl_pol_value = ttk.Label(grid_frame, text="—")
        self.lbl_pol_value.grid(row=3, column=5, columnspan=3, sticky="w", pady=8)

        # Narrative description
        self.desc_frame = ttk.LabelFrame(
            self.scroll_content, text="Narrative Profile Description", padding=10
        )
        self.desc_frame.pack(fill="x", pady=(0, 10))

        self.lbl_desc = ttk.Label(
            self.desc_frame,
            text="Select a character profile to view narrative characteristics.",
            wraplength=750,
            font=("Arial", 10, "italic"),
        )
        self.lbl_desc.pack(fill="x")

    def build_attributes_grid(self):
        grid_attrs_frame = ttk.Frame(self.scroll_content)
        grid_attrs_frame.pack(fill="both", expand=True)

        grid_attrs_frame.columnconfigure(0, weight=1)
        grid_attrs_frame.columnconfigure(1, weight=1)

        # 1. Physical Attributes Section
        group_phys = ttk.LabelFrame(
            grid_attrs_frame, text="Physical Attributes", padding=8
        )
        group_phys.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        self.build_attribute_list(group_phys, PHYSICAL_ATTRS)

        # 2. Cognitive Attributes Section
        group_cog = ttk.LabelFrame(
            grid_attrs_frame, text="Cognitive Attributes", padding=8
        )
        group_cog.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        self.build_attribute_list(group_cog, COGNITIVE_ATTRS)

        # 3. Psychological Attributes Section
        group_psy = ttk.LabelFrame(
            grid_attrs_frame, text="Psychological Attributes", padding=8
        )
        group_psy.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)
        self.build_attribute_list(group_psy, PSYCHOLOGICAL_ATTRS)

        # 4. Social & Behavioural Attributes Section
        group_soc = ttk.LabelFrame(
            grid_attrs_frame, text="Social & Behavioural Attributes", padding=8
        )
        group_soc.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=5)
        self.build_attribute_list(group_soc, SOCIAL_ATTRS)

    def build_attribute_list(self, parent, attributes):
        for attr_key, attr_label in attributes:
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=2)

            # Attribute Label (Static Width)
            lbl = ttk.Label(row, text=attr_label, width=18, anchor="w")
            lbl.pack(side="left", padx=(0, 5))

            # Progress Bar Track (Custom Canvas to remain self-contained)
            canvas = tk.Canvas(
                row,
                width=120,
                height=14,
                borderwidth=0,
                highlightthickness=1,
                highlightbackground="#E2E8F0",
            )
            canvas.pack(side="left", padx=(0, 8))

            # Numeric Value Label
            num_lbl = ttk.Label(
                row,
                text="—",
                width=4,
                anchor="e",
                font=("Courier", 10, "bold"),
            )
            num_lbl.pack(side="left", padx=(0, 5))

            # Descriptive Assessment - Note: ttk.Label requires full "foreground" rather than "fg" shorthand
            desc_lbl = ttk.Label(
                row, text="", width=15, anchor="w", font=("Arial", 8, "italic")
            )
            desc_lbl.pack(side="left")

            self.attribute_widgets[attr_key] = {
                "canvas": canvas,
                "num_lbl": num_lbl,
                "desc_lbl": desc_lbl,
            }

    # --- CONTROLLER LOGIC ---
    def load_initial_data(self):
        """Loads default embedded database as standard."""
        self.parse_csv_string(DEFAULT_CSV_CONTENT)
        self.status_var.set(
            f"Active: Embedded canonical zpy roster loaded ({len(self.characters)} characters)."
        )

    def parse_csv_string(self, content):
        self.characters.clear()
        stream = io.StringIO(content.strip())
        reader = csv.DictReader(stream)

        for row in reader:
            cleaned_row = {
                k.strip(): v.strip() if v else "" for k, v in row.items()
            }
            if not cleaned_row.get("character_id"):
                continue

            # Cast dynamic fields
            numeric_fields = ["left2right", "birth_year", "height_cm", "weight_kg"]
            all_lists = (
                PHYSICAL_ATTRS
                + COGNITIVE_ATTRS
                + PSYCHOLOGICAL_ATTRS
                + SOCIAL_ATTRS
            )
            for attr_id, _ in all_lists:
                numeric_fields.append(attr_id)

            for key in numeric_fields:
                if key in cleaned_row and cleaned_row[key] != "":
                    try:
                        cleaned_row[key] = int(cleaned_row[key])
                    except ValueError:
                        try:
                            cleaned_row[key] = float(cleaned_row[key])
                        except ValueError:
                            pass

            self.characters.append(cleaned_row)

        self.refresh_roster_list()

    def refresh_roster_list(self):
        search_term = self.search_var.get().strip().lower()
        self.roster_listbox.delete(0, tk.END)
        self.filtered_characters.clear()

        for char in self.characters:
            name = char.get("display_name", "").lower()
            char_id = char.get("character_id", "").lower()

            if search_term in name or search_term in char_id:
                self.filtered_characters.append(char)
                display_string = (
                    f"{char.get('character_id', '???')} - "
                    f"{char.get('display_name', 'Unknown'):<20} "
                    f"({char.get('short_name', '???')})"
                )
                self.roster_listbox.insert(tk.END, display_string)

        self.lbl_roster_count.config(
            text=f"Roster Match ({len(self.filtered_characters)}):"
        )

        # Select first result by default
        if self.filtered_characters:
            self.roster_listbox.selection_clear(0, tk.END)
            self.roster_listbox.selection_set(0)
            self.on_list_select(None)
        else:
            self.clear_fields()

    def on_search_change(self, *args):
        self.refresh_roster_list()

    def on_sim_year_change(self, *args):
        # Dynamically evaluate updated age of current selection
        char = self.get_selected_character()
        if char:
            self.update_age_evaluation(char)

    def on_list_select(self, event):
        char = self.get_selected_character()
        if char:
            self.display_character(char)

    def get_selected_character(self):
        selection = self.roster_listbox.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx < len(self.filtered_characters):
            return self.filtered_characters[idx]
        return None

    def display_character(self, char):
        # Update Main Header
        self.selected_char_name.set(
            f"{char.get('display_name', 'Unnamed')} [{char.get('short_name', '—')}]"
        )

        # Update Meta fields
        self.lbl_id.config(text=char.get("character_id", "—"))
        self.lbl_short.config(text=char.get("short_name", "—"))
        self.lbl_sex.config(text=char.get("sex", "—"))
        self.lbl_species.config(text=char.get("species", "—").capitalize())
        self.lbl_nat.config(text=char.get("nationality", "—"))

        religion_text = char.get("religion", "—")
        if religion_text:
            religion_text = religion_text.capitalize()
        self.lbl_rel.config(text=religion_text)

        birth_val = char.get("birth_year", "—")
        self.lbl_birth.config(text=str(birth_val))
        self.lbl_version.config(text=char.get("schema_version", "—"))

        # Format dimensions
        height = char.get("height_cm", "—")
        self.lbl_height.config(text=f"{height} cm" if isinstance(height, (int, float)) else "—")
        
        weight = char.get("weight_kg", "—")
        self.lbl_weight.config(text=f"{weight} kg" if isinstance(weight, (int, float)) else "—")

        # Dynamic Age evaluation
        self.update_age_evaluation(char)

        # Narrative text
        self.lbl_desc.config(text=char.get("description", "No description available."))

        # Political orientation slider
        left2right = char.get("left2right", "")
        self.draw_political_gradient(left2right)

        # Fill Attribute Blocks
        all_lists = (
            PHYSICAL_ATTRS + COGNITIVE_ATTRS + PSYCHOLOGICAL_ATTRS + SOCIAL_ATTRS
        )
        for attr_key, _ in all_lists:
            val = char.get(attr_key, "")
            self.draw_attribute_row(attr_key, val)

    def update_age_evaluation(self, char):
        birth_year = char.get("birth_year", "")
        if isinstance(birth_year, (int, float)):
            try:
                sim_year = int(self.sim_year_var.get())
                calculated_age = sim_year - int(birth_year)
                self.lbl_age.config(text=f"{calculated_age} yrs")
            except ValueError:
                self.lbl_age.config(text="Invalid Year")
        else:
            self.lbl_age.config(text="—")

    def draw_political_gradient(self, value):
        self.pol_canvas.delete("all")
        if isinstance(value, (int, float)):
            val = max(1, min(99, int(value)))
            # Color bands
            self.pol_canvas.create_rectangle(0, 0, 75, 20, fill="#3B82F6", outline="")  # Soft Left Blue
            self.pol_canvas.create_rectangle(75, 0, 125, 20, fill="#9CA3AF", outline="")  # Center Gray
            self.pol_canvas.create_rectangle(125, 0, 200, 20, fill="#EF4444", outline="")  # Soft Right Red

            # Center mark
            self.pol_canvas.create_line(100, 0, 100, 20, fill="#FFFFFF", width=2)

            # Alignment arrow
            x_pos = ((val - 1) / 98.0) * 200
            self.pol_canvas.create_polygon(
                x_pos - 5, 0, x_pos + 5, 0, x_pos, 8, fill="#1E293B"
            )
            self.pol_canvas.create_polygon(
                x_pos - 5, 20, x_pos + 5, 20, x_pos, 12, fill="#1E293B"
            )

            align_text = get_political_label(val)
            self.lbl_pol_value.config(text=f"{val} ({align_text})")
        else:
            # Fallback
            self.pol_canvas.create_rectangle(0, 0, 200, 20, fill="#E2E8F0", outline="")
            self.lbl_pol_value.config(text="—")

    def draw_attribute_row(self, attr_key, val):
        widgets = self.attribute_widgets.get(attr_key)
        if not widgets:
            return

        canvas = widgets["canvas"]
        num_lbl = widgets["num_lbl"]
        desc_lbl = widgets["desc_lbl"]

        canvas.delete("all")

        if isinstance(val, (int, float)):
            int_val = int(val)
            color = get_rating_color(int_val)
            percent_width = (int_val / 99.0) * 120

            # Background bar tracks
            canvas.create_rectangle(
                0, 0, 120, 14, fill="#F1F5F9", outline=""
            )
            # Active attribute indicators
            canvas.create_rectangle(
                0, 0, percent_width, 14, fill=color, outline=""
            )

            num_lbl.config(text=str(int_val))
            # Fixed here: Changed option parameter from "fg" shorthand to "foreground"
            desc_lbl.config(text=get_rating_desc(int_val), foreground=color)
        else:
            canvas.create_rectangle(
                0, 0, 120, 14, fill="#E2E8F0", outline=""
            )
            num_lbl.config(text="—")
            # Fixed here: Changed option parameter from "fg" shorthand to "foreground"
            desc_lbl.config(text="N/A", foreground="#94A3B8")

    def clear_fields(self):
        self.selected_char_name.set("No Character Selected")
        self.lbl_id.config(text="—")
        self.lbl_short.config(text="—")
        self.lbl_sex.config(text="—")
        self.lbl_species.config(text="—")
        self.lbl_age.config(text="—")
        self.lbl_nat.config(text="—")
        self.lbl_rel.config(text="—")
        self.lbl_birth.config(text="—")
        self.lbl_height.config(text="—")
        self.lbl_weight.config(text="—")
        self.lbl_version.config(text="—")
        self.lbl_desc.config(
            text="Select a character profile to view narrative characteristics."
        )
        self.pol_canvas.delete("all")
        self.lbl_pol_value.config(text="—")

        all_lists = (
            PHYSICAL_ATTRS + COGNITIVE_ATTRS + PSYCHOLOGICAL_ATTRS + SOCIAL_ATTRS
        )
        for attr_key, _ in all_lists:
            self.draw_attribute_row(attr_key, "")

    def load_from_file(self):
        """Loads custom roster CSV files matching the schema specifications."""
        file_path = filedialog.askopenfilename(
            title="Open Universal Character Master CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        try:
            # Encoding is set to 'utf-8-sig' to support UTF-8 with BOM formats
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                content = f.read()
                self.parse_csv_string(content)
                self.status_var.set(
                    f"Loaded from: {file_path} ({len(self.characters)} characters)."
                )
                messagebox.showinfo(
                    "Success",
                    f"Successfully loaded {len(self.characters)} characters compliant with the zpy schema standard.",
                )
        except Exception as e:
            messagebox.showerror(
                "Error Reading Schema File",
                f"An error occurred while loading this CSV file:\n{str(e)}",
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = ZpyCharacterViewer(root)
    root.mainloop()