import re

files = {
    'frontend/src/components/AttractionSearch.jsx': {
        'icon': 'MapPin',
        'init': 'const [localCity, setLocalCity] = useState(globalCity || "Paris");',
        'city_state': 'localCity',
        'search_panel_cols': '1fr 1fr 1fr',
        'shimmer': '{loading ? (\\n        <Shimmer label={localCity ? `Scanning ${localCity} for things to do` : "Scanning for things to do"} />'
    },
    'frontend/src/components/RestaurantSearch.jsx': {
        'icon': 'MapPin',
        'init': 'const [localCity, setLocalCity] = useState(globalCity || "Paris");',
        'city_state': 'localCity',
        'search_panel_cols': '1fr 1fr 1fr 1fr',
        'shimmer': '{loading ? (\\n        <Shimmer label={localCity ? `Finding tables in ${localCity}` : "Finding tables"} />'
    }
}

for filepath, info in files.items():
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # 1. Add localCity state
    content = re.sub(
        r'(const \{ globalCity, setPendingRefinement \} = useGlobalState\(\);\n)',
        rf'\1  {info["init"]}\n',
        content, count=1
    )

    # 2. Update doSearch if (!globalCity) to if (!localCity.trim())
    content = re.sub(
        r'if \(!globalCity\) \{',
        r'if (!localCity.trim()) {',
        content, count=1
    )

    # 3. Update setLastCity(globalCity) to setLastCity(localCity)
    content = re.sub(
        r'setLastCity\(globalCity\);',
        r'setLastCity(localCity);',
        content, count=1
    )

    # 4. Update city: globalCity to city: localCity in fetch params
    content = re.sub(
        r'city: globalCity',
        r'city: localCity',
        content, count=1
    )

    # 5. Update dependency array [globalCity,...] to [localCity,...] in doSearch and useEffect
    content = re.sub(
        r'\[globalCity,',
        r'[localCity,',
        content
    )

    # 6. Remove the early return if (!globalCity) block entirely
    content = re.sub(
        r'  if \(!globalCity\) \{[\s\S]*?    \);\n  \}\n\n',
        r'',
        content, count=1
    )

    # 7. Update PageHeader title to use lastCity primarily
    match = re.search(r'title=\{\`(.*?) in', content)
    if match:
        kind = match.group(1)
        content = re.sub(
            r'title=\{\`.*?in \$\{lastCity \|\| globalCity\}\`\}',
            f'title={{lastCity ? `{kind} in ${{lastCity}}` : "{kind}"}}',
            content, count=1
        )

    # 8. Add SearchInput for City to SearchPanel
    new_cols = info['search_panel_cols']
    content = re.sub(
        r'<SearchPanel columns=\".*?\">',
        f'<SearchPanel columns="{new_cols}">\n        <SearchInput type="text" label="City" icon={{{info["icon"]}}} value={{localCity}} onChange={{(e) => setLocalCity(e.target.value)}} />',
        content, count=1
    )

    # 9. Update Shimmer label
    content = re.sub(
        r'\{loading \? \(\n\s*<Shimmer label=\{\`.*?\`\} \/>',
        info['shimmer'],
        content, count=1
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
