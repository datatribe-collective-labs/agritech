title: "Interactive Prototype — Walkthrough & Feature Flow",
text: `<p>This journey steps through a live user interaction sequence with the prototype interface—demonstrating how a grower moves from initial configuration to receiving tailored agronomic advice.</p>
        <p>Phase 1 begins on the Farm & Site Setup panel: the grower sets their location coordinates, date, soil pH (e.g., 6.5), soil type (e.g., sandy loam), and specifies their desired planting group allocations.</p>
        <p>Phase 2 moves to Crop Selection & Companion Matching: the grower inputs their primary focus crop (e.g., Cocoa) and target additions. The interface queries backend relational feature tables to display an expanded, complementary crop list.</p>
        <p>Phase 3 completes the workflow with the Daily Planting Planner: the system converts microclimate parameters and seasonal windows into a date-stamped action list (e.g., 'Plant Today: Cassava, Yam, Ginger') ready for field implementation.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EEEDFE', 'primaryBorderColor': '#534AB7', 'primaryTextColor': '#26215C', 'lineColor': '#888780', 'secondaryColor': '#E1F5EE', 'fontSize': '13px'}}}%%

    subgraph Phase_1 [1. Panel 1: Farm & Site Setup]
        VIEW_CONFIG["User Views 'Farm' Configuration Card"] ---> SET_LOC["Enter Location: Osonkoti, Anapansu, Ghana"]
        SET_LOC --> SET_SOIL["Set Soil Parameters: pH 6.5 & Sandy Loam"]
        SET_SOIL --> SET_GROUPS["Select Target Plant Groups (e.g., 2 Groups)"]
    end

    subgraph Phase_2 [2. Panel 2: Planting Group Companion Selection]
        SET_GROUPS ---> SELECT_BASE["Define Primary Crop: Cocoa"]
        SELECT_BASE --> SELECT_ADD["Add Desired Intercrops: Wild Ground Nut, Hyacinth Bean, Velvet Bean"]
        SELECT_ADD --> COMPANION_CALC["System Evaluates Relational Compatibility & Regenerative Value"]
        COMPANION_CALC --> DISPLAY_FINAL["Render Final Plant List: Cocoa, Cassava, Yam, Ginger, Turmeric, Citrus..."]
    end

    subgraph Phase_3 [3. Panel 3: Planting Schedule & Daily Action]
        DISPLAY_FINAL ---> FILTER_DATE["Cross-Reference Date Window: 2027-04-01"]
        FILTER_DATE --> GENERATE_TODAY["Filter Activities for Current Weather & Season"]
        GENERATE_TODAY --> VIEW_SCHEDULE["Display 'Plant Today' Recommendations: Plantain, Banana, Cassava, Yam..."]
    end

    classDef setup fill:#FBE6E8,stroke:#A61C1C,color:#5C0A0A
    classDef selection fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef schedule fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class VIEW_CONFIG,SET_LOC,SET_SOIL,SET_GROUPS setup
    class SELECT_BASE,SELECT_ADD,COMPANION_CALC,DISPLAY_FINAL selection
    class FILTER_DATE,GENERATE_TODAY,VIEW_SCHEDULE schedule`
    
