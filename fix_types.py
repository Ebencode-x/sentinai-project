from pathlib import Path

# Add vite/client reference to tsconfig so import.meta.env is typed
tsconfig = Path("frontend/tsconfig.json")
content = tsconfig.read_text(encoding="utf-8")

# Add "vite/client" to lib array
old = '"lib": ["ES2020", "DOM", "DOM.Iterable"]'
new = '"lib": ["ES2020", "DOM", "DOM.Iterable"],\n    "types": ["vite/client"]'
content = content.replace(old, new)
tsconfig.write_text(content, encoding="utf-8")
print("WROTE  tsconfig.json — added vite/client types")
