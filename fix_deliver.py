with open('D:/AI_ONE/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the exact position
idx = content.find('} + chr(96) + 'r')
if idx < 0:
    idx = content.find('}\x60r\x60n@app.post("/api/deliver/list")')
if idx < 0:
    idx = content.find('
@app.post("/api/deliver/list")')
if idx < 0:
    # Try to find it another way
    for i in range(len(content)):
        if content[i] == chr(96) and i+5 < len(content) and content[i:i+6] == chr(96)+'r'+chr(96)+'n'+chr(64):
            idx = i
            break

if idx >= 0:
    print(f"Found at {idx}: {repr(content[idx:idx+40])}")
    # The } should be before this
    # Find the } before the backticks
    brace_idx = content.rfind('}', idx-10, idx)
    if brace_idx >= 0:
        content = content[:brace_idx+1] + '\n' + content[idx:]
        with open('D:/AI_ONE/app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed!")
    else:
        print("No brace found")
else:
    print("Pattern not found - trying broader search")
    # Just find any occurrence of 
@
    idx2 = content.find(chr(96)+'r'+chr(96)+'n'+chr(64))
    if idx2 >= 0:
        print(f"Found at {idx2}")
        brace_idx = content.rfind('}', idx2-30, idx2)
        if brace_idx >= 0:
            content = content[:brace_idx+1] + '\n' + content[idx2:]
            with open('D:/AI_ONE/app.py', 'w', encoding='utf-8') as f:
                f.write(content)
            print("Fixed!")
        else:
            print("No brace found before pattern")
    else:
        print("Still not found - showing raw around line 1570")
        lines = content.split('\n')
        print(repr(lines[1569]))
