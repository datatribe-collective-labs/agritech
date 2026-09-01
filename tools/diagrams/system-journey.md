title: "User Journey — Daily Planting & Companion Selection",
text: `<p>This journey traces the end-to-end experience of a grower using the AgriTech interface to generate optimized companion planting arrangements and seasonal work schedules.</p>
        <p>Phase 1 captures site definition: the user inputs their regional location, soil parameters (pH and soil type), and primary target crops directly into the application.</p>
        <p>Phase 2 illustrates the dynamic calculation: the frontend requests evaluated pairings from the backend, which matches the inputs against precomputed compatibility matrices and regional seasonal windows.</p>
        <p>Phase 3 depicts actionable output: the grower receives a tailored companion plant grouping alongside a daily planting planner to maximize soil regeneration and harvest yield.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EEEDFE', 'primaryBorderColor': '#534AB7', 'primaryTextColor': '#26215C', 'lineColor': '#888780', 'secondaryColor': '#E1F5EE', 'fontSize': '13px'}}}%%

    subgraph Phase_1 [1. User Input & Site Selection]
        FARMER["Farmer Accesses Web Interface"] ---> INPUT_SITE["Enter Location, Date & Soil Parameters (pH / Type)"]
        INPUT_SITE --> INPUT_CROPS["Select Primary Crops & Target Yield Preferences"]
    end

    subgraph Phase_2 [2. Real-Time Logic Evaluation]
        INPUT_CROPS ---> FETCH_MATRIX["Query Relational Companion Matrix"]
        FETCH_MATRIX --> MATCH_SEASON["Filter Activities by Seasonal & Weather Windows"]
        MATCH_SEASON --> VALIDATE["Validate Soil & Microclimate Compatibility"]
    end

    subgraph Phase_3 [3. Interactive Schedule & Delivery]
        VALIDATE ---> RENDER_GROUPS["Display Companion Groups (e.g., Plant Group 1)"]
        RENDER_GROUPS --> RENDER_PLANNER["Generate 'Plant Today' Daily Planting Schedule"]
        RENDER_PLANNER --> ACTION["Farmer Executes Sustainable Field Plan"]
    end

    classDef user fill:#FBE6E8,stroke:#A61C1C,color:#5C0A0A
    classDef logic fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef plan fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class FARMER,INPUT_SITE,INPUT_CROPS user
    class FETCH_MATRIX,MATCH_SEASON,VALIDATE logic
    class RENDER_GROUPS,RENDER_PLANNER,ACTION plan`
    
