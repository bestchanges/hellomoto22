import json

f = open('coins.json')
data = json.load(f)
fout = open('coins1.json', 'w')
json.dump(data, fout, indent=2)
