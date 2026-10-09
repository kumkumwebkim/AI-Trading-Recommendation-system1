import openpyxl
path = r"other Resources/Agile_Template_SoumodipGhosh.xlsx"
wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
for ws in wb:
    print("=" * 70)
    print("SHEET:", ws.title)
    print("=" * 70)
    for r in ws.iter_rows(values_only=True):
        vals = [str(c).strip() if c is not None else "" for c in r]
        if any(vals):
            print(" | ".join(vals))
    print()

