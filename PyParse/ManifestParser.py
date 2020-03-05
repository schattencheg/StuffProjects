import json
import pathlib

path = "d:\\Program Files (x86)\\Steam\\steamapps\\"
pathFldrs = "d:\\Program Files (x86)\\Steam\\steamapps\\common\\"

def getFiles(path, mask):
    """
    Returns list of files in the _path_ by the _mask_
    """
    return [x.name for x in pathlib.Path(path).glob(mask)]

names = []
namesForCheck = []
files = getFiles(path, "*acf*")
folders = getFiles(pathFldrs, "*")
# Check manifests
for fn in files:
    f = open(path + fn, 'r')
    #loaded_json = json.load(f)
    #for x in loaded_json:
    #    print("%s: %d" % (x, loaded_json[x]))
    for line in f:
        if "name" in line:
            name = line.split("\"")[-2]
            namesForCheck.append(name)
            if not name in folders:
                name = "!!!! " + name
            names.append(name + " - " + fn)
#Check folders
print("\nFOLDERS")
for f in folders:
    if not f in namesForCheck:
        print("!!!! "+f)
print("\nNAMES")
names.sort()
for n in names:
    print(n)
        